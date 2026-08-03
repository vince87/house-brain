import asyncio
import json
from datetime import UTC, datetime

import httpx

from house_brain.config import Settings
from house_brain.home_assistant import HomeAssistantClient


def make_settings() -> Settings:
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret-token",
    )


def test_client_reads_entity_with_bearer_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            str(request.url)
            == "http://homeassistant.test:8123/api/states/light.sala"
        )
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
        async with HomeAssistantClient(
            make_settings(),
            transport=httpx.MockTransport(handler),
        ) as client:
            entity = await client.get_entity("light.sala")
            return entity.state

    assert asyncio.run(read_entity()) == "on"


def test_client_returns_last_state_strictly_before_timestamp() -> None:
    def state(state: str, timestamp: str) -> dict[str, object]:
        return {
            "entity_id": "light.sala",
            "state": state,
            "attributes": {},
            "last_changed": timestamp,
            "last_updated": timestamp,
            "context": {},
        }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.startswith("/api/history/period/")
        assert request.url.params["filter_entity_id"] == "light.sala"
        assert request.url.params["end_time"] == "2026-08-03T08:00:00+00:00"
        return httpx.Response(
            200,
            json=[
                [
                    state("off", "2026-08-03T07:00:00+00:00"),
                    state("on", "2026-08-03T08:00:00+00:00"),
                ]
            ],
        )

    async def read_state_before() -> str:
        before = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
        search_start = datetime(2026, 8, 2, 8, 0, tzinfo=UTC)
        async with HomeAssistantClient(
            make_settings(),
            transport=httpx.MockTransport(handler),
        ) as client:
            entity = await client.get_state_before(
                "light.sala",
                before=before,
                search_start=search_start,
            )
            return entity.state

    assert asyncio.run(read_state_before()) == "off"


def test_client_calls_service_with_entity_and_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/services/cover/set_cover_position"
        assert json.loads(request.content) == {
            "entity_id": "cover.tapparella_cucina_uno",
            "position": 0,
        }
        return httpx.Response(200, json=[])

    async def call_service() -> object:
        async with HomeAssistantClient(
            make_settings(),
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.call_service(
                "cover",
                "set_cover_position",
                entity_id="cover.tapparella_cucina_uno",
                data={"position": 0},
            )

    assert asyncio.run(call_service()) == []
