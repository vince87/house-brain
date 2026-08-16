import pytest
from fastapi.testclient import TestClient

from house_brain.config import get_settings
from house_brain.main import app

API_KEY = "test-web-chat-api-key"
HA_TOKEN = "test-home-assistant-token"


@pytest.fixture(autouse=True)
def configured_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://homeassistant.test:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", HA_TOKEN)
    monkeypatch.setenv("HOUSE_BRAIN_API_KEY", API_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_chat_shell_is_public_but_contains_no_configured_secrets() -> None:
    response = TestClient(app).get("/chat")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "House Brain" in response.text
    assert 'type="password"' in response.text
    assert API_KEY not in response.text
    assert HA_TOKEN not in response.text


def test_chat_uses_session_api_key_header_without_local_storage() -> None:
    response = TestClient(app).get("/chat")

    assert 'headers.set("X-API-Key", apiKey())' in response.text
    assert "sessionStorage" in response.text
    assert "localStorage" not in response.text
    assert "/agent/chat" in response.text
    assert "/conversations/" in response.text


def test_chat_shell_has_strict_browser_security_headers() -> None:
    response = TestClient(app).get("/chat")

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    policy = response.headers["content-security-policy"]
    assert "default-src 'none'" in policy
    assert "connect-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    [
        ({}, 401),
        ({"X-API-Key": "wrong-key"}, 401),
        ({"X-API-Key": API_KEY}, 200),
    ],
)
def test_auth_check_requires_valid_api_key(
    headers: dict[str, str],
    expected_status: int,
) -> None:
    response = TestClient(app).get("/auth/check", headers=headers)

    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json() == {"authenticated": True}
    else:
        assert response.json() == {"detail": "Invalid or missing API key"}


def test_chat_shell_is_not_an_openapi_operation() -> None:
    schema = TestClient(app).get("/openapi.json").json()

    assert "/chat" not in schema["paths"]
    assert schema["paths"]["/auth/check"]["get"].get("security") is None
    assert schema["security"] == [{"HouseBrainApiKey": []}]


def test_chat_linkifies_urls_without_dynamic_html() -> None:
    response = TestClient(app).get("/chat")

    assert "appendTextWithLinks(text, content)" in response.text
    assert 'link.target = "_blank"' in response.text
    assert 'link.rel = "noopener noreferrer"' in response.text
    assert 'content.replaceAll("**", "")' in response.text
    assert "innerHTML" not in response.text
    assert "function actionAudit(payload)" in response.text
    assert "record.error" in response.text


def test_chat_shell_uses_configured_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOUSE_BRAIN_LANGUAGE", "en")
    get_settings.cache_clear()

    response = TestClient(app).get("/chat")

    assert '<html lang="en">' in response.text
    assert "Your home, in conversation" in response.text
    assert "Write a message to begin." in response.text
    assert "La casa, in conversazione" not in response.text
