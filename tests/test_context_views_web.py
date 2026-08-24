from house_brain.context_views_web import context_views_page
from house_brain.web_theme import SHARED_THEME_CSS, shared_navigation


def test_context_view_page_is_localized_and_uses_shared_theme() -> None:
    page = context_views_page("it-IT")
    html = page.body.decode()

    assert '<html lang="it">' in html
    assert "Viste contestuali" in html
    assert "possono solo restringere" in html
    assert 'sessionStorage.getItem(KEY)' in html
    assert '"/admin/context-views"' in html
    assert '"/preview"' in html
    assert "Salva la configurazione prima" in html
    assert "if(dirty)" in html
    assert SHARED_THEME_CSS in html
    assert "innerHTML" not in html


def test_context_navigation_is_available_and_marks_current_page() -> None:
    navigation = shared_navigation("context", "it")

    assert 'href="/context-views"' in navigation
    assert "Contesto" in navigation
    assert navigation.count('aria-current="page"') == 1
