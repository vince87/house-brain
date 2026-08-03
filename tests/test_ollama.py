import asyncio

import httpx

from house_brain.config import Settings
from house_brain.ollama import OllamaClient


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
