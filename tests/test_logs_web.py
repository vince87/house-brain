import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import house_brain.main as main_module
from house_brain.autonomy import AutonomyPolicyCatalog
from house_brain.config import Settings, get_settings
from house_brain.logs_web import MESSAGES, logs_page
from house_brain.main import app
from house_brain.runtime_logs import RuntimeLogBuffer

client = TestClient(app)


def _settings() -> Settings:
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="ha-test-secret",
        api_key="api-test-secret",
        openai_api_key="openai-test-secret",
    )


def _message(text: str, *, level: str = "INFO") -> SimpleNamespace:
    return SimpleNamespace(
        record={
            "time": datetime.now(UTC),
            "level": SimpleNamespace(name=level),
            "name": "house_brain.agent",
            "function": "run_agent",
            "message": text,
        }
    )


def test_logs_page_is_public_but_runtime_data_requires_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        page = client.get("/logs")
        protected = client.get("/runtime-logs")
    finally:
        app.dependency_overrides.clear()

    assert page.status_code == 200
    assert 'id="authForm"' in page.text
    assert 'fetch("/runtime-logs?"+params' in page.text
    assert protected.status_code == 401


def test_runtime_logs_endpoint_accepts_existing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = client.get(
            "/runtime-logs?limit=20",
            headers={"X-API-Key": "api-test-secret"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_logs_page_is_localized_safe_and_mentions_scope() -> None:
    response = logs_page("it-IT")
    page = response.body.decode()

    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "Log applicativi" in page
    assert "Non espone il socket Docker" in page
    assert "innerHTML" not in page
    assert "textContent=item.message" in page
    assert "async function responseBody(response)" in page


def test_logs_page_supports_every_installed_language() -> None:
    assert set(MESSAGES) == {
        "ar",
        "de",
        "en",
        "es",
        "fr",
        "it",
        "ja",
        "ko",
        "pt",
        "zh",
    }
    assert all(logs_page(language).status_code == 200 for language in MESSAGES)


def test_runtime_log_buffer_is_bounded_filterable_and_redacts_credentials() -> None:
    buffer = RuntimeLogBuffer(capacity=2)
    buffer.write(_message("discarded first"))
    buffer.write(_message("using ha-test-secret", level="WARNING"))
    buffer.write(_message("openai-test-secret and api-test-secret", level="ERROR"))
    buffer.write(
        SimpleNamespace(
            record={
                "time": datetime.now(UTC),
                "level": SimpleNamespace(name="ERROR"),
                "name": "third_party.module",
                "function": "ignored",
                "message": "ignored",
            }
        )
    )

    records = buffer.list(_settings(), limit=10)
    errors = buffer.list(_settings(), limit=10, level="ERROR", query="openai")

    assert len(records) == 2
    assert records[0].level == "WARNING"
    assert records[0].message == "using [redacted]"
    assert errors[0].message == "[redacted] and [redacted]"
    assert "discarded" not in " ".join(item.message for item in records)


def test_runtime_log_buffer_redacts_plain_text_policy_codes() -> None:
    settings = _settings().model_copy(
        update={
            "autonomy_policy": AutonomyPolicyCatalog(
                included_entities=frozenset({"lock.example_front_door"}),
                entity_codes={"lock.example_front_door": "2468"},
                simple_entity_policy=True,
            )
        }
    )
    buffer = RuntimeLogBuffer()
    buffer.write(_message("device code 2468 rejected", level="WARNING"))

    records = buffer.list(settings, limit=10)

    assert records[0].message == "device code [redacted] rejected"


def test_runtime_log_buffer_accepts_only_selected_standard_loggers() -> None:
    buffer = RuntimeLogBuffer()
    accepted = logging.LogRecord(
        "httpx",
        logging.INFO,
        __file__,
        1,
        "HTTP %s",
        ("200",),
        None,
        "request",
    )
    ignored = logging.LogRecord(
        "unrelated.library",
        logging.ERROR,
        __file__,
        1,
        "secret noise",
        (),
        None,
        "call",
    )

    buffer.write_standard(accepted)
    buffer.write_standard(ignored)

    records = buffer.list(_settings(), limit=10)
    assert len(records) == 1
    assert records[0].module == "httpx"
    assert records[0].message == "HTTP 200"
