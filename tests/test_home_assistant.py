import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from house_brain import home_assistant as home_assistant_module
from house_brain.config import Settings
from house_brain.home_assistant import (
    HOME_ASSISTANT_WEBSOCKET_MAX_SIZE,
    EntityNotFoundError,
    HomeAssistantClient,
    _hidden_entity_ids_from_registry,
)


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



def _state(
    entity_id: str,
    *,
    attributes: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "entity_id": entity_id,
        "state": "on",
        "attributes": attributes or {},
        "last_changed": "2026-08-03T08:00:00+00:00",
        "last_updated": "2026-08-03T08:00:00+00:00",
        "context": {},
    }


def test_registry_parser_only_marks_entities_with_hidden_by() -> None:
    assert _hidden_entity_ids_from_registry(
        [
            {"entity_id": "light.example_visible", "hidden_by": None},
            {"entity_id": "light.example_user_hidden", "hidden_by": "user"},
            {
                "entity_id": "sensor.example_integration_hidden",
                "hidden_by": "integration",
            },
            {"hidden_by": "user"},
            "invalid",
        ]
    ) == frozenset(
        {
            "light.example_user_hidden",
            "sensor.example_integration_hidden",
        }
    )


def test_hidden_entities_are_absent_from_search_and_configuration() -> None:
    calls = 0

    async def hidden_entities() -> frozenset[str]:
        nonlocal calls
        calls += 1
        return frozenset({"light.example_hidden"})

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states"
        return httpx.Response(
            200,
            json=[
                _state(
                    "light.example_visible",
                    attributes={"friendly_name": "Visible Light"},
                ),
                _state(
                    "light.example_hidden",
                    attributes={"friendly_name": "Hidden Light"},
                ),
            ],
        )

    async def read_entities() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        async with HomeAssistantClient(
            make_settings(),
            transport=httpx.MockTransport(handler),
            hidden_entities_loader=hidden_entities,
        ) as client:
            search = await client.search_entities("light")
            configuration = await client.list_entities_for_configuration()
            return search, configuration

    search, configuration = asyncio.run(read_entities())
    assert [item["entity_id"] for item in search] == ["light.example_visible"]
    assert [item["entity_id"] for item in configuration] == [
        "light.example_visible"
    ]
    assert calls == 1


def test_hidden_entity_is_rejected_before_state_or_service_request() -> None:
    requests: list[str] = []

    async def hidden_entities() -> frozenset[str]:
        return frozenset({"switch.example_hidden"})

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(500)

    async def access_hidden_entity() -> None:
        async with HomeAssistantClient(
            make_settings(),
            transport=httpx.MockTransport(handler),
            hidden_entities_loader=hidden_entities,
        ) as client:
            for operation in (
                client.get_entity("switch.example_hidden"),
                client.call_service(
                    "switch",
                    "turn_on",
                    entity_id="switch.example_hidden",
                    data={},
                ),
            ):
                try:
                    await operation
                except EntityNotFoundError:
                    pass
                else:
                    raise AssertionError("Hidden entity was accessible")

    asyncio.run(access_hidden_entity())
    assert requests == []


def test_hidden_entity_references_are_removed_from_visible_attributes() -> None:
    async def hidden_entities() -> frozenset[str]:
        return frozenset({"light.example_hidden"})

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states/group.example_lights"
        return httpx.Response(
            200,
            json=_state(
                "group.example_lights",
                attributes={
                    "entity_id": [
                        "light.example_visible",
                        "light.example_hidden",
                    ]
                },
            ),
        )

    async def read_group() -> list[str]:
        async with HomeAssistantClient(
            make_settings(),
            transport=httpx.MockTransport(handler),
            hidden_entities_loader=hidden_entities,
        ) as client:
            entity = await client.get_entity("group.example_lights")
            return entity.attributes["entity_id"]

    assert asyncio.run(read_group()) == ["light.example_visible"]


def test_registry_websocket_accepts_large_bounded_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options: dict[str, object] = {}

    class FakeWebSocket:
        def __init__(self) -> None:
            self.messages = iter(
                [
                    json.dumps({"type": "auth_required"}),
                    json.dumps({"type": "auth_ok"}),
                    json.dumps(
                        {
                            "id": 1,
                            "type": "result",
                            "success": True,
                            "result": [
                                {
                                    "entity_id": "sensor.example_hidden",
                                    "hidden_by": "integration",
                                    "padding": "x" * 1_100_000,
                                }
                            ],
                        }
                    ),
                ]
            )

        async def recv(self) -> str:
            return next(self.messages)

        async def send(self, message: str) -> None:
            assert json.loads(message)["type"] in {
                "auth",
                "config/entity_registry/list",
            }

    class FakeConnection:
        async def __aenter__(self) -> FakeWebSocket:
            return FakeWebSocket()

        async def __aexit__(self, *args: object) -> None:
            return None

    def fake_connect(url: str, **kwargs: object) -> FakeConnection:
        options.update(kwargs)
        assert url == "ws://homeassistant.test:8123/api/websocket"
        return FakeConnection()

    monkeypatch.setattr(home_assistant_module, "connect", fake_connect)

    async def read_registry() -> frozenset[str]:
        async with HomeAssistantClient(make_settings()) as client:
            return await client._load_hidden_entities_from_registry()

    assert asyncio.run(read_registry()) == frozenset({"sensor.example_hidden"})
    assert options["max_size"] == HOME_ASSISTANT_WEBSOCKET_MAX_SIZE
    assert HOME_ASSISTANT_WEBSOCKET_MAX_SIZE == 16 * 1024 * 1024
