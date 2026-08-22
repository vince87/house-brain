import asyncio
import json

import httpx

from house_brain.config import Settings
from house_brain.openai import OpenAIClient


def _settings() -> Settings:
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
        llm_provider="openai",
        openai_api_key="openai-test-secret",
        openai_model="test-model",
    )


def test_openai_chat_returns_normalized_content_without_exposing_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer openai-test-secret"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ready"}}]},
        )

    async def chat() -> dict[str, object]:
        async with OpenAIClient(
            _settings(), transport=httpx.MockTransport(handler)
        ) as client:
            return await client.chat([{"role": "user", "content": "hello"}], [])

    assert asyncio.run(chat())["content"] == "ready"


def test_openai_chat_normalizes_tool_call_and_sends_tool_result() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content)
        if calls == 1:
            assert payload["tool_choice"] == "auto"
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_entity",
                                            "arguments": (
                                                '{"entity_id":"light.example_room"}'
                                            ),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                },
            )
        assert payload["messages"][-1] == {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": '{"state":"off"}',
        }
        assert isinstance(
            payload["messages"][-2]["tool_calls"][0]["function"]["arguments"],
            str,
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "done"}}]},
        )

    async def chat() -> dict[str, object]:
        async with OpenAIClient(
            _settings(), transport=httpx.MockTransport(handler)
        ) as client:
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_entity",
                        "description": "Read an entity",
                        "parameters": {"type": "object"},
                    },
                }
            ]
            assistant = await client.chat(
                [{"role": "user", "content": "state"}], tools
            )
            tool_call = assistant["tool_calls"][0]
            assert tool_call["function"]["arguments"] == {
                "entity_id": "light.example_room"
            }
            return await client.chat(
                [
                    {"role": "user", "content": "state"},
                    assistant,
                    {
                        "role": "tool",
                        "tool_name": "get_entity",
                        "tool_call_id": "call_1",
                        "content": '{"state":"off"}',
                    },
                ],
                tools,
            )

    assert asyncio.run(chat())["content"] == "done"


def test_openai_status_checks_selected_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models/test-model"
        return httpx.Response(200, json={"id": "test-model"})

    async def status() -> bool:
        async with OpenAIClient(
            _settings(), transport=httpx.MockTransport(handler)
        ) as client:
            return (await client.status()).model_available

    assert asyncio.run(status()) is True
