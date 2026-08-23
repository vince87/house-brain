import asyncio
import json

import httpx
import pytest

from house_brain.config import Settings
from house_brain.ollama import OllamaClient, OllamaError


def test_ollama_status_finds_configured_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "gemma4:12b", "model": "gemma4:12b"},
                    {"name": "qwen3:8b", "model": "qwen3:8b"},
                ]
            },
        )

    async def get_status() -> tuple[bool, list[str]]:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
            ollama_url="http://ollama.test:11434",
            ollama_model="gemma4:12b",
        )
        async with OllamaClient(
            settings,
            transport=httpx.MockTransport(handler),
        ) as client:
            result = await client.status()
            return result.model_available, result.available_models

    available, models = asyncio.run(get_status())

    assert available is True
    assert models == ["gemma4:12b", "qwen3:8b"]


def test_ollama_chat_retries_one_empty_response() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        assert request.url.path == "/api/chat"
        calls += 1
        content = "" if calls == 1 else "ready"
        payload = json.loads(request.content)
        assert payload["options"] == {
            "num_ctx": 16384,
            "num_predict": 4096,
            "temperature": 0.1,
        }
        if calls == 1:
            assert payload["think"] is False
            assert len(payload["messages"]) == 1
        else:
            assert payload["think"] is True
            assert payload["messages"][0]["role"] == "system"
            assert "previous model response was empty" in payload["messages"][0][
                "content"
            ]
            assert "strictly follows its JSON schema" in payload["messages"][0][
                "content"
            ]
            assert payload["messages"][-1]["role"] == "user"
        return httpx.Response(200, json={"message": {"content": content}})

    async def chat() -> dict[str, object]:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
            ollama_url="http://ollama.test:11434",
        )
        async with OllamaClient(
            settings, transport=httpx.MockTransport(handler)
        ) as client:
            return await client.chat([{"role": "user", "content": "hello"}], [])

    assert asyncio.run(chat())["content"] == "ready"
    assert calls == 2


def test_ollama_chat_strips_recovery_thinking_from_tool_call() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        if calls == 1:
            assert payload["think"] is False
            return httpx.Response(200, json={"message": {"content": ""}})
        assert payload["think"] is True
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "thinking": "private recovery reasoning",
                    "tool_calls": [{"function": {"name": "get_entity"}}],
                }
            },
        )

    async def chat() -> dict[str, object]:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
            ollama_url="http://ollama.test:11434",
        )
        async with OllamaClient(
            settings, transport=httpx.MockTransport(handler)
        ) as client:
            return await client.chat([{"role": "user", "content": "hello"}], [])

    result = asyncio.run(chat())

    assert result["tool_calls"]
    assert "thinking" not in result
    assert calls == 2


def test_ollama_chat_stops_after_three_empty_responses() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"message": {"content": ""}})

    async def chat() -> None:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
            ollama_url="http://ollama.test:11434",
        )
        async with OllamaClient(
            settings, transport=httpx.MockTransport(handler)
        ) as client:
            await client.chat([{"role": "user", "content": "hello"}], [])

    with pytest.raises(OllamaError, match="empty response after 3 attempts"):
        asyncio.run(chat())
    assert calls == 3


def test_ollama_tool_call_is_not_considered_empty() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"message": {"content": "", "tool_calls": [{"function": {}}]}},
        )

    async def chat() -> dict[str, object]:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
            ollama_url="http://ollama.test:11434",
        )
        async with OllamaClient(
            settings, transport=httpx.MockTransport(handler)
        ) as client:
            return await client.chat([{"role": "user", "content": "hello"}], [])

    assert asyncio.run(chat())["tool_calls"]
    assert calls == 1


def test_ollama_chat_reports_context_exhaustion_without_retry() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "message": {"content": ""},
                "done": True,
                "done_reason": "length",
                "prompt_eval_count": 16384,
                "eval_count": 0,
            },
        )

    async def chat() -> None:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
            ollama_url="http://ollama.test:11434",
        )
        async with OllamaClient(
            settings, transport=httpx.MockTransport(handler)
        ) as client:
            await client.chat([{"role": "user", "content": "hello"}], [])

    with pytest.raises(OllamaError, match="exhausted the configured context window"):
        asyncio.run(chat())
    assert calls == 1


def test_ollama_chat_retries_transient_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"message": {"content": "ready"}})

    monkeypatch.setattr("house_brain.ollama.asyncio.sleep", record_sleep)

    async def chat() -> dict[str, object]:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
            ollama_url="http://ollama.test:11434",
        )
        async with OllamaClient(
            settings,
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.chat([{"role": "user", "content": "hello"}], [])

    assert asyncio.run(chat())["content"] == "ready"
    assert calls == 2
    assert delays == [0.5]


def test_ollama_chat_does_not_retry_client_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, request=request)

    async def chat() -> None:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
            ollama_url="http://ollama.test:11434",
        )
        async with OllamaClient(
            settings,
            transport=httpx.MockTransport(handler),
        ) as client:
            await client.chat([{"role": "user", "content": "hello"}], [])

    with pytest.raises(OllamaError, match="chat request failed"):
        asyncio.run(chat())
    assert calls == 1
