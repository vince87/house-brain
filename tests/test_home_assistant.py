import asyncio

import httpx

from house_brain.config import Settings
from house_brain.home_assistant import HomeAssistantClient


def test_client_reads_entity_with_bearer_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://homeassistant.test:8123/api/states/light.sala"
        assert request.headers["Authorization"] == "Bearer secret-token"
        return httpx.Response(
            200,
            json={
                "entity_id": "light.sala",
                "state": "on",
                "attributes": {"brightness": 180},
                "last_changed": "2026-08-03T08:00:00+00:00",
                "last_updated": "2026-08-03T08:00:00+00:00",
                "context": {"id": "test-context"},
            },
        )

    async def read_entity() -> str:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret-token",
        )
        async with HomeAssistantClient(
            settings,
            transport=httpx.MockTransport(handler),
        ) as client:
            entity = await client.get_entity("light.sala")
            return entity.state

    assert asyncio.run(read_entity()) == "on"
