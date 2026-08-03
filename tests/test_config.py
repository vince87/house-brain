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
