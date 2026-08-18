import asyncio

import pytest

from house_brain import main as main_module
from house_brain.config import Settings
from house_brain.home_assistant import HomeAssistantError
from house_brain.ollama import OllamaStatus


class StubHomeAssistantClient:
    async def list_entities_for_configuration(self) -> list[dict[str, str]]:
        return [
            {
                "entity_id": "light.example_room",
                "domain": "light",
                "friendly_name": "Example Room",
                "state": "off",
            }
        ]

    async def hidden_entity_ids(self) -> frozenset[str]:
        return frozenset({"sensor.example_hidden"})

    async def list_services(self) -> list[dict[str, object]]:
        return [{"domain": "light", "service": "turn_on"}]


class StubOllamaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __aenter__(self) -> "StubOllamaClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def status(self) -> OllamaStatus:
        return OllamaStatus(
            status="ok",
            url=str(self.settings.ollama_url).rstrip("/"),
            configured_model=self.settings.ollama_model,
            model_available=True,
            available_models=[self.settings.ollama_model],
        )


def _settings(tmp_path) -> Settings:
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
        memory_database_path=str(tmp_path / "memory.db"),
    )


def test_diagnostics_report_healthy_components(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "OllamaClient", StubOllamaClient)

    result = asyncio.run(
        main_module.get_system_diagnostics(
            StubHomeAssistantClient(),
            _settings(tmp_path),
        )
    )

    assert result["status"] == "ok"
    assert result["home_assistant"] == {
        "status": "ok",
        "visible_entities": 1,
        "hidden_entities": 1,
        "services": 1,
    }
    assert result["ollama"]["model_available"] is True


def test_diagnostics_is_degraded_when_home_assistant_fails(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingHomeAssistantClient(StubHomeAssistantClient):
        async def list_entities_for_configuration(self) -> list[dict[str, str]]:
            raise HomeAssistantError("Home Assistant is unreachable")

    monkeypatch.setattr(main_module, "OllamaClient", StubOllamaClient)

    result = asyncio.run(
        main_module.get_system_diagnostics(
            FailingHomeAssistantClient(),
            _settings(tmp_path),
        )
    )

    assert result["status"] == "degraded"
    assert result["home_assistant"] == {
        "status": "error",
        "error": "Home Assistant is unreachable",
    }
    assert result["ollama"]["status"] == "ok"


def test_diagnostics_is_degraded_when_model_is_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingModelOllamaClient(StubOllamaClient):
        async def status(self) -> OllamaStatus:
            result = await super().status()
            return result.model_copy(
                update={
                    "model_available": False,
                    "available_models": ["example:latest"],
                }
            )

    monkeypatch.setattr(main_module, "OllamaClient", MissingModelOllamaClient)

    result = asyncio.run(
        main_module.get_system_diagnostics(
            StubHomeAssistantClient(),
            _settings(tmp_path),
        )
    )

    assert result["status"] == "degraded"
    assert result["ollama"]["status"] == "error"
    assert result["ollama"]["error"] == (
        "Configured Ollama model is not available"
    )
