from fastapi.testclient import TestClient

from house_brain.diagnostics_web import GUIDANCE, MESSAGES, diagnostics_page
from house_brain.main import app

client = TestClient(app)


def test_diagnostics_page_is_public_shell_with_protected_report() -> None:
    page = client.get("/system")

    assert page.status_code == 200
    assert 'id="authForm"' in page.text
    assert 'fetch("/diagnostics"' in page.text
    assert client.get("/diagnostics").status_code == 401


def test_diagnostics_page_is_safe_localized_and_exportable() -> None:
    response = diagnostics_page("it-IT")
    page = response.body.decode()

    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "Diagnostica di sistema" in page
    assert "innerHTML" not in page
    assert 'link.download="house-brain-diagnostics.json"' in page
    assert 'href="/system"' in page
    assert "Controlli suggeriti" in page
    assert 'if(data.status==="error")' in page
    assert "document.createTextNode(help)" in page
    assert "report.provider_metrics" in page
    assert "Metriche provider" in page
    assert "background:var(--hb-success)" in page
    assert "background:var(--hb-error)" in page
    assert "--hb-green" not in page
    assert "--hb-red" not in page


def test_diagnostics_page_supports_every_installed_language() -> None:
    assert set(MESSAGES) == {
        "ar", "de", "en", "es", "fr", "it", "ja", "ko", "pt", "zh"
    }
    assert set(GUIDANCE) == set(MESSAGES)
    for language in MESSAGES:
        assert diagnostics_page(language).status_code == 200
