from fastapi.testclient import TestClient

from house_brain.main import app
from house_brain.memory_web import MESSAGES, memory_page

client = TestClient(app)


def test_memory_page_is_public_shell_with_protected_api() -> None:
    page = client.get("/memories")

    assert page.status_code == 200
    assert 'id="authForm"' in page.text
    assert 'sessionStorage.setItem(KEY' in page.text
    assert 'headers.set("X-API-Key",apiKey())' in page.text

    protected = client.get("/memory")
    assert protected.status_code == 401


def test_memory_page_exposes_safe_browser_headers() -> None:
    response = memory_page("it-IT")

    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"
    assert "Gestione memorie" in response.body.decode()


def test_memory_page_supports_every_installed_language() -> None:
    assert set(MESSAGES) == {"ar", "de", "en", "es", "fr", "it", "ja", "ko", "pt", "zh"}
    for language in MESSAGES:
        assert memory_page(language).status_code == 200


def test_memory_page_can_edit_delete_restore_and_list_all() -> None:
    page = memory_page("en").body.decode()

    assert "/memory?limit=5000&deleted=" in page
    assert 'method:"POST"' in page
    assert 'method:"DELETE"' in page
    assert '"/restore"' in page
    assert "item?.key" in page
