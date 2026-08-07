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
            == "http://homeassistant.test:8123/api/states/light.example_room"
        )
        assert request.headers["Authorization"] == "Bearer secret-token"
        return httpx.Response(
            200,
            json={
                "entity_id": "light.example_room",
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
            entity = await client.get_entity("light.example_room")
            return entity.state

    assert asyncio.run(read_entity()) == "on"


def test_client_returns_last_state_strictly_before_timestamp() -> None:
    def state(state: str, timestamp: str) -> dict[str, object]:
        return {
            "entity_id": "light.example_room",
            "state": state,
            "attributes": {},
            "last_changed": timestamp,
            "last_updated": timestamp,
            "context": {},
        }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.startswith("/api/history/period/")
        assert request.url.params["filter_entity_id"] == "light.example_room"
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
                "light.example_room",
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
            "entity_id": "cover.example_kitchen_shade",
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
                entity_id="cover.example_kitchen_shade",
                data={"position": 0},
            )

    assert asyncio.run(call_service()) == []


def test_resolver_keeps_shared_name_ambiguous_before_control_filter() -> None:
    timestamp = "2026-08-07T08:00:00+00:00"

    def state(entity_id: str, friendly_name: str) -> dict[str, object]:
        return {
            "entity_id": entity_id,
            "state": "off",
            "attributes": {"friendly_name": friendly_name},
            "last_changed": timestamp,
            "last_updated": timestamp,
            "context": {},
        }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states"
        return httpx.Response(
            200,
            json=[
                state("light.example_room_one", "Example Room One"),
                state("light.example_room_two", "Example Room Two"),
            ],
        )

    async def resolve() -> str:
        async with HomeAssistantClient(
            make_settings(),
            transport=httpx.MockTransport(handler),
        ) as client:
            result = await client.resolve_entity(
                "Example Room",
                allowed_entities=frozenset(
                    {"light.example_room_one"}
                ),
            )
            return result.status

    assert asyncio.run(resolve()) == "ambiguous"
