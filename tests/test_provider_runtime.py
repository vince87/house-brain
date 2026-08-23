import asyncio

import pytest

from house_brain import agent as agent_module
from house_brain.agent import AgentRequest, run_agent
from house_brain.config import Settings
from house_brain.provider_runtime import (
    ModelCapabilities,
    ProviderMetrics,
)


class ResponseOnlyClient:
    model = "response-only:test"

    def __init__(self, *, content: str = "General answer") -> None:
        self.content = content
        self.chat_calls: list[tuple[list[dict[str, object]], list[object]]] = []

    async def __aenter__(self) -> "ResponseOnlyClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            provider="ollama",
            model=self.model,
            tool_support="unsupported",
            source="test",
        )

    async def chat(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> dict[str, object]:
        self.chat_calls.append((messages, tools))
        return {"role": "assistant", "content": self.content}


class ForbiddenHomeAssistant:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"Home Assistant must not be accessed: {name}")


def _settings() -> Settings:
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
        ollama_url="http://ollama.test:11434",
        house_brain_language="it",
    )


def test_response_only_event_stops_before_home_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ResponseOnlyClient()
    monkeypatch.setattr(agent_module, "create_chat_client", lambda _settings: client)

    result = asyncio.run(
        run_agent(
            AgentRequest(message="Accendi light.example_room"),
            _settings(),
            ForbiddenHomeAssistant(),
            object(),
            object(),
            action_mode="execute",
            persist_conversation=False,
            explicit_entity_ids=frozenset({"light.example_room"}),
        )
    )

    assert "non supporta i tool" in result.response
    assert "non ha letto Home Assistant" in result.response
    assert result.tools_used == ["model_capabilities"]
    assert result.tool_trace[0].outcome == "response_only:tools_unsupported"
    assert client.chat_calls == []


def test_response_only_chat_uses_no_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ResponseOnlyClient(content="Risposta generale")
    monkeypatch.setattr(agent_module, "create_chat_client", lambda _settings: client)

    result = asyncio.run(
        run_agent(
            AgentRequest(message="Spiegami che cosa è un kilowattora"),
            _settings(),
            ForbiddenHomeAssistant(),
            object(),
            object(),
            persist_conversation=False,
        )
    )

    assert result.response.endswith("Risposta generale")
    assert len(client.chat_calls) == 1
    assert client.chat_calls[0][1] == []
    assert "Never claim that you read a" in client.chat_calls[0][0][0]["content"]


def test_provider_metrics_are_aggregate_and_content_free() -> None:
    metrics = ProviderMetrics()
    metrics.record_retry("ollama")
    metrics.record_recovery("ollama")
    metrics.record_success("ollama", 0.125)
    metrics.record_failure("ollama", 0.375)

    snapshot = metrics.snapshot()["ollama"]

    assert snapshot == {
        "requests": 2,
        "successes": 1,
        "failures": 1,
        "retries": 1,
        "recoveries": 1,
        "average_latency_ms": 250.0,
        "last_latency_ms": 375.0,
    }
    assert "prompt" not in snapshot
    assert "response" not in snapshot
