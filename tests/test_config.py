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
    policy_path.write_text("version: 2\nentities:\n  include: []\n  exclude: []\n")
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://homeassistant.test:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "test-home-assistant-token")
    monkeypatch.setenv("HOUSE_BRAIN_API_KEY", "test-house-brain-api-key")
    monkeypatch.setenv("AUTONOMY_POLICY_PATH", str(policy_path))
    monkeypatch.delenv("HOUSE_BRAIN_LANGUAGE", raising=False)
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
version: 2
entities:
  include: [light.example_living_room]
  exclude: []
""".lstrip()
    )

    settings = Settings.from_env()
    policy = settings.autonomy_policy.resolve(
        "canary_light_control",
        "execute",
    )

    assert policy.included_entities == frozenset({"light.example_living_room"})
    assert policy.max_actions == 10


def test_settings_reject_invalid_autonomy_policy(
    required_environment: Path,
) -> None:
    required_environment.write_text(
        "version: 2\nentities:\n  visible: [light.example_room]\n"
        "  include: [light.example_room]\n  exclude: []\n"
    )

    with pytest.raises(
        AutonomyPolicyError,
        match="both visible and included",
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


def test_local_openai_compatible_provider_allows_missing_api_key(
    required_environment: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://local-model.test:8080/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = Settings.from_env()

    assert settings.llm_provider == "openai"
    assert settings.openai_api_key is None
    assert str(settings.openai_base_url) == "http://local-model.test:8080/v1"


def test_official_openai_provider_requires_api_key(
    required_environment: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="required for the official OpenAI API"):
        Settings.from_env()


def test_persistent_files_default_to_single_config_directory() -> None:
    configured = Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
    )

    assert configured.autonomy_policy_path == "/config/autonomy.yaml"
    assert configured.autonomy_backup_path == "/config/autonomy-backups"
    assert configured.memory_database_path == "/config/house_brain.db"


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


def test_response_language_defaults_to_italian(
    required_environment: Path,
) -> None:
    assert Settings.from_env().house_brain_language == "it"


def test_response_language_accepts_regional_installed_pack(
    required_environment: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOUSE_BRAIN_LANGUAGE", "pt_BR")

    assert Settings.from_env().house_brain_language == "pt-br"


def test_response_language_rejects_missing_pack(
    required_environment: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOUSE_BRAIN_LANGUAGE", "nl")

    with pytest.raises(ValueError, match="is not installed"):
        Settings.from_env()
