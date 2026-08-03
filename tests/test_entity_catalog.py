import asyncio

import httpx

from house_brain.config import Settings
from house_brain.home_assistant import HomeAssistantClient


def test_entity_search_ranks_partial_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states"
        return httpx.Response(
            200,
            json=[
                {
                    "entity_id": "switch.ventola",
                    "state": "off",
                    "attributes": {"friendly_name": "Ventola"},
                    "last_changed": "2026-08-03T08:00:00Z",
                    "last_updated": "2026-08-03T08:00:00Z",
                },
                {
                    "entity_id": "switch.luce_garage",
                    "state": "off",
                    "attributes": {"friendly_name": "Luce garage"},
                    "last_changed": "2026-08-03T08:00:00Z",
                    "last_updated": "2026-08-03T08:00:00Z",
                },
            ],
        )

    async def search() -> list[dict[str, str]]:
        settings = Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
        )
        async with HomeAssistantClient(
            settings,
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.search_entities(
                "ventola garage",
                domain="switch",
            )

    results = asyncio.run(search())

    assert results[0]["entity_id"] == "switch.ventola"
    assert len(results) == 2
