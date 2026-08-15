import asyncio

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


def test_ollama_chat_stops_after_second_empty_response() -> None:
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

    with pytest.raises(OllamaError, match="empty response after retry"):
        asyncio.run(chat())
    assert calls == 2


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
