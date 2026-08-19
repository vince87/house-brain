from house_brain.audit_web import audit_page
from house_brain.autonomy_web import autonomy_page
from house_brain.memory_web import memory_page
from house_brain.web_chat import chat_page
from house_brain.web_theme import SHARED_THEME_CSS


def test_shared_theme_is_applied_to_every_management_interface() -> None:
    pages = (
        chat_page("it").body.decode(),
        memory_page("it").body.decode(),
        audit_page("it").body.decode(),
        autonomy_page("it").body.decode(),
    )

    for page in pages:
        assert SHARED_THEME_CSS in page
        assert "prefers-reduced-motion" in page
        assert "focus-visible" in page
        assert "radial-gradient" in page


def test_shared_theme_keeps_dependency_free_security_model() -> None:
    assert "http://" not in SHARED_THEME_CSS
    assert "https://" not in SHARED_THEME_CSS
    assert "@import" not in SHARED_THEME_CSS
    assert "url(" not in SHARED_THEME_CSS
