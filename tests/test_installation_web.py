from house_brain.installation_web import installation_page


def test_installation_page_exposes_safe_staged_lifecycle_controls() -> None:
    html = installation_page("it").body.decode()

    assert "Gestione installazione" in html
    assert 'id="authForm"' in html
    assert 'id="download"' in html
    assert 'id="inspect"' in html
    assert 'id="confirmation"' in html
    assert 'id="apply"' in html
    assert "/admin/installation/backups" in html
    assert "/admin/installation/restores/inspect" in html
    assert "/admin/installation/restores/apply" in html
    assert "body.persistent_paths" in html
    assert "Percorso database" in html
    assert "Percorso viste contestuali" in html
    assert 'confirmation:"RESTORE"' in html
    assert "sessionStorage" in html
    assert "localStorage" not in html
    assert "innerHTML" not in html
    assert "docker.sock" not in html


def test_installation_page_uses_language_fallback_and_browser_headers() -> None:
    page = installation_page("pt-BR")
    html = page.body.decode()

    assert "Installation management" in html
    assert page.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]


def test_installation_page_allows_only_configured_frame_ancestor() -> None:
    page = installation_page(
        "en",
        "https://homeassistant.example.test/path",
    )

    assert "x-frame-options" not in page.headers
    assert (
        "frame-ancestors 'self' https://homeassistant.example.test"
        in page.headers["content-security-policy"]
    )
