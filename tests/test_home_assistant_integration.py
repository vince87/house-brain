import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from house_brain.version import APP_VERSION

INTEGRATION = Path("custom_components/house_brain")


class FakeClientError(Exception):
    """Stand in for aiohttp transport errors in isolated client tests."""


class FakeClientTimeout:
    """Capture the configured total timeout without importing Home Assistant."""

    def __init__(self, *, total: int) -> None:
        self.total = total


def _key_paths(value: object, prefix: str = "") -> set[str]:
    """Return every nested translation key while ignoring translated text."""
    if not isinstance(value, dict):
        return set()
    paths: set[str] = set()
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        paths.add(path)
        paths.update(_key_paths(item, path))
    return paths


@pytest.fixture
def integration_api(monkeypatch: pytest.MonkeyPatch):
    """Load the transport module without importing the Home Assistant runtime."""
    aiohttp = ModuleType("aiohttp")
    aiohttp.ClientError = FakeClientError
    aiohttp.ClientResponse = object
    aiohttp.ClientSession = object
    aiohttp.ClientTimeout = FakeClientTimeout
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp)

    package_name = "house_brain_ha_test"
    package = ModuleType(package_name)
    package.__path__ = [str(INTEGRATION.resolve())]
    monkeypatch.setitem(sys.modules, package_name, package)
    for module in ("const", "models", "api"):
        monkeypatch.delitem(sys.modules, f"{package_name}.{module}", raising=False)
    return importlib.import_module(f"{package_name}.api")


class FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self._payload = payload

    async def json(self, *, content_type=None):
        del content_type
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeRequestContext:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    async def __aenter__(self) -> FakeResponse:
        return self.response

    async def __aexit__(self, *args: object) -> None:
        del args


class FakeSession:
    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.requests: list[dict[str, Any]] = []
        self.error: Exception | None = None

    def request(self, method: str, url: str, **kwargs: Any) -> FakeRequestContext:
        if self.error is not None:
            raise self.error
        self.requests.append({"method": method, "url": url, **kwargs})
        return FakeRequestContext(self.responses.pop(0))


def test_integration_manifest_and_translations_are_release_consistent() -> None:
    manifest = json.loads(
        (INTEGRATION / "manifest.json").read_text(encoding="utf-8")
    )
    translations = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (INTEGRATION / "translations").glob("*.json")
    }
    english = translations["en"]

    assert manifest["domain"] == "house_brain"
    assert manifest["version"] == APP_VERSION
    assert manifest["config_flow"] is True
    assert manifest["dependencies"] == [
        "ai_task",
        "conversation",
        "http",
        "panel_custom",
        "websocket_api",
    ]
    assert manifest["requirements"] == []
    assert set(translations) == {
        "ar", "de", "en", "es", "fr", "it", "ja", "ko", "pt", "zh"
    }
    assert all(
        _key_paths(translation) == _key_paths(english)
        for translation in translations.values()
    )
    assert "api_key" in english["config"]["step"]["user"]["data"]
    assert "api_key" not in english["config"]["step"]["user"]["description"]
    assert not (INTEGRATION / "strings.json").exists()


def test_integration_python_files_compile_and_keep_authority_server_side() -> None:
    for path in INTEGRATION.glob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    conversation = (INTEGRATION / "conversation.py").read_text(encoding="utf-8")
    ai_task = (INTEGRATION / "ai_task.py").read_text(encoding="utf-8")
    diagnostics = (INTEGRATION / "diagnostics.py").read_text(encoding="utf-8")

    assert "conversation.ConversationEntity" in conversation
    assert "conversation.AbstractConversationAgent" in conversation
    assert "ai_task.AITaskEntity" in ai_task
    assert "AITaskEntityFeature.GENERATE_DATA" in ai_task
    assert "mode=self.entry.data[CONF_CONVERSATION_MODE]" in ai_task
    assert "/actions" not in "".join(
        path.read_text(encoding="utf-8") for path in INTEGRATION.glob("*.py")
    )
    assert "CONF_API_KEY" not in diagnostics

    panel = (INTEGRATION / "frontend" / "house-brain-panel.js").read_text(
        encoding="utf-8"
    )
    setup = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    websocket = (INTEGRATION / "websocket.py").read_text(encoding="utf-8")
    assert "house-brain-panel" in panel
    assert "house_brain/panel" in panel
    assert "callWS" in panel
    assert "iframe" not in panel.casefold()
    assert "base_url" not in panel
    assert "fetch(" not in panel
    assert "api_key" not in panel.casefold()
    assert "require_admin=True" in setup
    assert 'config={"entry_id"' not in setup
    assert '"entry_id": entry.entry_id' in setup
    assert "panel_custom.async_register_panel" in setup
    assert "frontend.async_remove_panel" in setup
    assert "@websocket_api.require_admin" in websocket
    assert 'vol.Required("operation"): vol.In(_OPERATIONS)' in websocket
    assert '"include_expired": "true"' in websocket
    assert '"/memory/context"' in websocket
    assert "referenced_entities" in panel
    assert "audit-flow" in panel
    assert "provider_metrics" in panel
    assert "state.item.area_name" in panel
    assert "state.item.device_name" in panel
    assert '"true" if payload.get("deleted") is True else "false"' in websocket
    assert '?v=native-3' in setup
    assert "StaticPathConfig(\n                    _PANEL_STATIC_URL," in setup


@pytest.mark.parametrize(
    "url",
    [
        "ftp://house-brain.local:8090",
        "http://user:password@house-brain.local:8090",
        "http://house-brain.local:8090?token=secret",
        "http://",
    ],
)
def test_normalize_base_url_rejects_unsafe_urls(integration_api, url: str) -> None:
    with pytest.raises(ValueError):
        integration_api.normalize_base_url(url)


def test_validate_checks_authentication_without_sending_key_to_health(
    integration_api,
) -> None:
    session = FakeSession(
        [
            FakeResponse(200, {"authenticated": True}),
            FakeResponse(
                200,
                {"status": "ok", "service": "house-brain", "version": APP_VERSION},
            ),
        ]
    )
    client = integration_api.HouseBrainClient(
        session,
        "http://house-brain.local:8090/",
        "example-api-key",
    )

    status = __import__("asyncio").run(client.async_validate())

    assert status.version == APP_VERSION
    assert session.requests[0]["headers"]["X-API-Key"] == "example-api-key"
    assert "X-API-Key" not in session.requests[1]["headers"]


def test_chat_forwards_authoritative_mode_language_and_session(integration_api) -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "response": "Done",
                    "session_id": "ha-session",
                    "model": "example-model",
                    "tools_used": ["get_entity"],
                    "tool_trace": [{"tool": "get_entity"}],
                },
            )
        ]
    )
    client = integration_api.HouseBrainClient(
        session,
        "http://house-brain.local:8090",
        "example-api-key",
    )

    result = __import__("asyncio").run(
        client.async_chat(
            "Check the example light",
            "ha-session",
            mode="simulate",
            language="it-IT",
        )
    )

    assert result.session_id == "ha-session"
    assert result.tools_used == ("get_entity",)
    assert session.requests[0]["json"] == {
        "message": "Check the example light",
        "session_id": "ha-session",
        "mode": "simulate",
        "language": "it-IT",
    }


def test_native_entities_default_to_server_configured_language(integration_api) -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "response": "Ciao",
                    "session_id": "ha-session",
                    "tools_used": [],
                    "tool_trace": [],
                },
            ),
            FakeResponse(
                200,
                {
                    "event_id": "event-1",
                    "response": "Riepilogo",
                    "tools_used": [],
                    "tool_trace": [],
                },
            ),
        ]
    )
    client = integration_api.HouseBrainClient(
        session,
        "http://house-brain.local:8090",
        "example-api-key",
    )

    __import__("asyncio").run(
        client.async_chat("Ciao", "ha-session", mode="observe")
    )
    __import__("asyncio").run(
        client.async_ai_task(
            "Riepiloga",
            "Riepilogo giornaliero",
            mode="observe",
        )
    )

    assert "language" not in session.requests[0]["json"]
    assert "language" not in session.requests[1]["json"]


def test_conversation_ids_are_stable_bounded_and_scoped_per_entry(
    integration_api,
) -> None:
    models = importlib.import_module(f"{integration_api.__package__}.models")

    first = models.server_session_id("entry-123456789", "conversation-1")
    repeated = models.server_session_id("entry-123456789", first)
    other_entry = models.server_session_id("entry-987654321", "conversation-1")
    unsafe = models.server_session_id("entry-123456789", "x" * 500)

    assert first == repeated
    assert first != other_entry
    assert first.startswith("ha-entry-12-")
    assert len(first) <= 64
    assert len(unsafe) <= 64


def test_ai_task_forwards_the_configured_mode(integration_api) -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "event_id": "event-1",
                    "response": "Summary",
                    "model": "example-model",
                    "tools_used": [],
                    "tool_trace": [],
                },
            )
        ]
    )
    client = integration_api.HouseBrainClient(
        session,
        "http://house-brain.local:8090",
        "example-api-key",
    )

    result = __import__("asyncio").run(
        client.async_ai_task(
            "Summarize the house",
            "Daily summary",
            mode="execute",
            language="en",
        )
    )

    assert result.event_id == "event-1"
    assert session.requests[0]["json"]["mode"] == "execute"
    assert session.requests[0]["json"]["context"] == {
        "task_name": "Daily summary"
    }


def test_panel_requests_support_lists_without_exposing_the_api_key(
    integration_api,
) -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                [{"key": "example", "value": "Example memory"}],
            )
        ]
    )
    client = integration_api.HouseBrainClient(
        session,
        "http://house-brain.local:8090",
        "example-api-key",
    )

    result = __import__("asyncio").run(
        client.async_panel_request(
            "GET",
            "/memory",
            params={"limit": 5000},
        )
    )

    assert result == [{"key": "example", "value": "Example memory"}]
    assert session.requests[0]["params"] == {"limit": 5000}
    assert session.requests[0]["headers"]["X-API-Key"] == "example-api-key"


def test_client_classifies_auth_connection_and_empty_response(integration_api) -> None:
    auth_client = integration_api.HouseBrainClient(
        FakeSession([FakeResponse(401, {"detail": "invalid"})]),
        "http://house-brain.local:8090",
        "example-api-key",
    )
    with pytest.raises(integration_api.HouseBrainAuthenticationError):
        __import__("asyncio").run(auth_client.async_validate())

    non_json_auth_client = integration_api.HouseBrainClient(
        FakeSession([FakeResponse(401, ValueError("plain-text unauthorized"))]),
        "http://house-brain.local:8090",
        "example-api-key",
    )
    with pytest.raises(integration_api.HouseBrainAuthenticationError):
        __import__("asyncio").run(non_json_auth_client.async_validate())

    failed_session = FakeSession()
    failed_session.error = FakeClientError("offline")
    connection_client = integration_api.HouseBrainClient(
        failed_session,
        "http://house-brain.local:8090",
        "example-api-key",
    )
    with pytest.raises(integration_api.HouseBrainConnectionError):
        __import__("asyncio").run(connection_client.async_validate())

    empty_client = integration_api.HouseBrainClient(
        FakeSession([FakeResponse(200, {"response": "", "session_id": "test"})]),
        "http://house-brain.local:8090",
        "example-api-key",
    )
    with pytest.raises(integration_api.HouseBrainResponseError):
        __import__("asyncio").run(
            empty_client.async_chat(
                "Hello",
                "test",
                mode="observe",
                language="en",
            )
        )
