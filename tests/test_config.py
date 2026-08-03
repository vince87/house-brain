import pytest

from house_brain.config import Settings


@pytest.fixture
def required_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://homeassistant.test:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "test-home-assistant-token")
    monkeypatch.setenv("HOUSE_BRAIN_API_KEY", "test-house-brain-api-key")


def test_autonomous_execution_is_disabled_by_default(
    required_environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTONOMOUS_EXECUTION_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.autonomous_execution_enabled is False


def test_autonomous_execution_requires_explicit_true(
    required_environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTONOMOUS_EXECUTION_ENABLED", "true")

    settings = Settings.from_env()

    assert settings.autonomous_execution_enabled is True


def test_settings_load_autonomous_action_constraints(
    required_environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AUTONOMOUS_ACTION_CONSTRAINTS",
        '{"cover.set_cover_position:cover.cucina":'
        '{"position":{"allowed":[0,20,100]}}}',
    )

    settings = Settings.from_env()

    constraint = settings.autonomous_action_constraints[
        "cover.set_cover_position:cover.cucina"
    ]["position"]
    assert constraint.allowed == (0, 20, 100)


def test_settings_load_optional_web_search(
    required_environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SEARXNG_URL", "http://searxng.test:8081")
    monkeypatch.setenv("WEB_SEARCH_TIMEOUT", "7")
    monkeypatch.setenv("WEB_SEARCH_MAX_RESULTS", "6")

    settings = Settings.from_env()

    assert str(settings.searxng_url) == "http://searxng.test:8081/"
    assert settings.web_search_timeout == 7
    assert settings.web_search_max_results == 6


def test_web_search_is_disabled_without_searxng_url(
    required_environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SEARXNG_URL", raising=False)

    settings = Settings.from_env()

    assert settings.searxng_url is None


def test_web_search_defaults_to_ten_results_per_query() -> None:
    configured = Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
    )

    assert configured.web_search_max_results == 10


def test_settings_load_execute_canary_guardrails(
    required_environment: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AUTONOMOUS_EXECUTE_EVENT_ALLOWLIST",
        "canary_light_control",
    )
    monkeypatch.setenv("AUTONOMOUS_EXECUTE_MAX_ACTIONS", "1")

    settings = Settings.from_env()

    assert settings.autonomous_execute_event_allowlist == frozenset(
        {"canary_light_control"}
    )
    assert settings.autonomous_execute_max_actions == 1
