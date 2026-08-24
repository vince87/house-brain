from house_brain.action_plan_web import action_plan_page
from house_brain.main import PUBLIC_PATHS


def test_action_plan_page_is_public_but_plan_api_is_protected() -> None:
    page = action_plan_page("it")

    assert page.status_code == 200
    text = page.body.decode()
    assert "Piani d'azione" in text
    assert 'id="authForm"' in text
    assert 'fetch("/action-plans/from-request"' in text
    assert "/plans" in PUBLIC_PATHS
    assert "/action-plans" not in PUBLIC_PATHS


def test_action_plan_page_keeps_codes_ephemeral_and_uses_safe_dom() -> None:
    response = action_plan_page("it-IT")
    page = response.body.decode()

    assert 'type="password"' in page
    assert 'result["X-Authorization-Code"]' in page
    assert 'result["X-Home-Assistant-Code"]' in page
    assert "localStorage" not in page
    assert ".innerHTML" not in page
    assert "textContent" in page
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_action_plan_page_shows_authoritative_states_and_results() -> None:
    page = action_plan_page("en").body.decode()

    assert "item.initial_state" in page
    assert "plan.outcome" in page
    assert 'plan.status==="proposed"' in page
    assert 'transition(plan.plan_id,"approve")' in page
    assert 'transition(plan.plan_id,"reject")' in page

