from fastapi.testclient import TestClient

from house_brain.audit_web import MESSAGES, audit_page
from house_brain.main import app

client = TestClient(app)


def test_audit_page_is_public_shell_with_protected_event_api() -> None:
    page = client.get("/audit")

    assert page.status_code == 200
    assert 'id="authForm"' in page.text
    assert 'sessionStorage.setItem(KEY' in page.text
    assert '"X-API-Key":apiKey()' in page.text

    protected = client.get("/events")
    assert protected.status_code == 401


def test_audit_page_uses_safe_dom_and_browser_headers() -> None:
    response = audit_page("it-IT")
    page = response.body.decode()

    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"
    assert "Audit azioni" in page
    assert "innerHTML" not in page
    assert "textContent=JSON.stringify(item.tool_trace" in page


def test_audit_page_supports_every_installed_language() -> None:
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
    for language in MESSAGES:
        assert audit_page(language).status_code == 200


def test_audit_page_filters_modes_and_loads_full_trace() -> None:
    page = audit_page("en").body.decode()

    assert 'api("/events?limit=100")' in page
    assert "<option>observe</option>" in page
    assert "<option>simulate</option>" in page
    assert "<option>execute</option>" in page
    assert "item.tool_trace||[]" in page
