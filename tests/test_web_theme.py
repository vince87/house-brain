from house_brain.action_plan_web import action_plan_page
from house_brain.audit_web import audit_page
from house_brain.autonomy_web import autonomy_page
from house_brain.memory_web import memory_page
from house_brain.web_chat import chat_page
from house_brain.web_theme import (
    SHARED_THEME_CSS,
    browser_security_headers,
    shared_navigation,
)


def test_shared_theme_is_applied_to_every_management_interface() -> None:
    pages = (
        chat_page("it").body.decode(),
        memory_page("it").body.decode(),
        audit_page("it").body.decode(),
        action_plan_page("it").body.decode(),
        autonomy_page("it").body.decode(),
    )

    for page in pages:
        assert SHARED_THEME_CSS in page
        assert "prefers-reduced-motion" in page
        assert "focus-visible" in page
        assert "--hb-primary: #03a9f4" in page
        assert "--hb-bg: #f5f5f5" in page
        assert "prefers-color-scheme: dark" in page


def test_shared_theme_keeps_dependency_free_security_model() -> None:
    assert "http://" not in SHARED_THEME_CSS
    assert "https://" not in SHARED_THEME_CSS
    assert "@import" not in SHARED_THEME_CSS
    assert "url(" not in SHARED_THEME_CSS


def test_navigation_is_localized_and_marks_the_current_page() -> None:
    navigation = shared_navigation("memories", "it-IT")

    assert 'href="/chat"' in navigation
    assert 'href="/memories"' in navigation
    assert 'href="/audit"' in navigation
    assert 'href="/plans"' in navigation
    assert 'href="/autonomy"' in navigation
    assert 'href="/logs"' in navigation
    assert 'href="/system"' in navigation
    assert "Memorie" in navigation
    assert navigation.count('aria-current="page"') == 1
    assert 'class="hb-nav-link active"' in navigation
    assert "window.self!==window.top" in navigation


def test_browser_headers_allow_only_the_configured_home_assistant_origin() -> None:
    standalone = browser_security_headers()
    embedded = browser_security_headers("http://homeassistant.test:8123/api")

    assert standalone["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in standalone["Content-Security-Policy"]
    assert "X-Frame-Options" not in embedded
    assert (
        "frame-ancestors 'self' http://homeassistant.test:8123"
        in embedded["Content-Security-Policy"]
    )
