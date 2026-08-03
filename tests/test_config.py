from pathlib import Path

import pytest

from house_brain.autonomy import AutonomyPolicyError
from house_brain.config import DEPRECATED_AUTONOMY_VARIABLES, Settings


@pytest.fixture
def required_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    for name in DEPRECATED_AUTONOMY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    policy_path = tmp_path / "autonomy.yaml"
    policy_path.write_text("version: 1\nevents: {}\n")
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://homeassistant.test:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "test-home-assistant-token")
    monkeypatch.setenv("HOUSE_BRAIN_API_KEY", "test-house-brain-api-key")
    monkeypatch.setenv("AUTONOMY_POLICY_PATH", str(policy_path))
    return policy_path


def test_autonomous_execution_is_disabled_by_default(
    required_environment: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTONOMOUS_EXECUTION_ENABLED", raising=False)

    settings = Settings.from_env()

    assert settings.autonomous_execution_enabled is False


def test_autonomous_execution_requires_explicit_true(
    required_environment: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTONOMOUS_EXECUTION_ENABLED", "true")

    settings = Settings.from_env()

    assert settings.autonomous_execution_enabled is True


def test_settings_load_yaml_autonomy_policy(
    required_environment: Path,
) -> None:
    required_environment.write_text(
        """
version: 1
events:
  canary_light_control:
    modes: [simulate, execute]
    max_actions: 1
    actions:
      light.turn_on:
        entities: [light.sala_uno]
""".lstrip()
    )

    settings = Settings.from_env()
    policy = settings.autonomy_policy.resolve(
        "canary_light_control",
        "execute",
    )

    assert policy.action_rules == frozenset(
        {"light.turn_on:light.sala_uno"}
    )
    assert policy.max_actions == 1


def test_settings_reject_invalid_autonomy_policy(
    required_environment: Path,
) -> None:
    required_environment.write_text(
        "version: 1\nevents:\n  invalid:\n    modes: [execute]\n"
        "    max_actions: 0\n    actions: {}\n"
    )

    with pytest.raises(
        AutonomyPolicyError,
        match="max_actions must be between 1 and 20",
    ):
        Settings.from_env()


def test_settings_load_optional_web_search(
    required_environment: Path,
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
    required_environment: Path,
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


def test_settings_reject_deprecated_autonomy_variables(
    required_environment: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "AUTONOMOUS_EVENT_ALLOWLIST",
        "sun_context_changed",
    )

    with pytest.raises(
        RuntimeError,
        match="Remove deprecated autonomy environment variables",
    ):
        Settings.from_env()
