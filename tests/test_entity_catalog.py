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
                    "entity_id": "automation.example_fan_control",
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Controllo device umidità Garage"
                    },
                    "last_changed": "2026-08-03T08:00:00Z",
                    "last_updated": "2026-08-03T08:00:00Z",
                },
                {
                    "entity_id": "switch.example_fan_relay",
                    "state": "off",
                    "attributes": {"friendly_name": "Device"},
                    "last_changed": "2026-08-03T08:00:00Z",
                    "last_updated": "2026-08-03T08:00:00Z",
                },
                {
                    "entity_id": "switch.example_garage_light",
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
                "example fan",
            )

    results = asyncio.run(search())

    assert results[0]["entity_id"] == "switch.example_fan_relay"
    assert results[0]["state"] == "off"
    assert any(
        item["entity_id"] == "automation.example_fan_control"
        for item in results
    )
