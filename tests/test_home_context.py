import asyncio
import json

import httpx
import pytest

from house_brain import home_assistant as home_assistant_module
from house_brain.autonomy import AutonomyPolicyCatalog, VisibilityPolicy
from house_brain.config import Settings
from house_brain.context_views import ContextView
from house_brain.home_assistant import HomeAssistantClient, HomeAssistantError
from house_brain.home_context import HomeContextRegistry, build_home_context


def _registry() -> HomeContextRegistry:
    return HomeContextRegistry.from_home_assistant(
        areas=[
            {
                "area_id": "example_kitchen",
                "name": "Example Kitchen",
                "aliases": ["Cooking Area"],
            },
            {"area_id": "example_lounge", "name": "Example Lounge"},
        ],
        devices=[
            {
                "id": "device-kitchen",
                "area_id": "example_kitchen",
                "name": "Example Ceiling Device",
            },
            {
                "id": "device-lounge",
                "area_id": "example_lounge",
                "name_by_user": "Example Television",
            },
        ],
        entities=[
            {
                "entity_id": "light.example_kitchen",
                "device_id": "device-kitchen",
                "hidden_by": None,
            },
            {
                "entity_id": "sensor.example_temperature",
                "device_id": "device-kitchen",
                "hidden_by": None,
            },
            {
                "entity_id": "media_player.example_tv",
                "device_id": "device-lounge",
                "area_id": "example_kitchen",
                "hidden_by": None,
            },
            {
                "entity_id": "sensor.example_hidden",
                "device_id": "device-kitchen",
                "hidden_by": "user",
            },
        ],
    )


def _state(entity_id: str, name: str, state: str = "on") -> dict[str, object]:
    return {
        "entity_id": entity_id,
        "state": state,
        "effective_state": state,
        "attributes": {"friendly_name": name},
        "last_changed": "2026-08-24T08:00:00+00:00",
    }


def test_registry_parses_relationships_and_hidden_entities() -> None:
    registry = _registry()

    assert registry.areas["example_kitchen"].aliases == ("Cooking Area",)
    assert registry.devices["device-lounge"].name == "Example Television"
    assert registry.entities["media_player.example_tv"].area_id == ("example_kitchen")
    assert registry.hidden_entity_ids == frozenset({"sensor.example_hidden"})


def test_context_is_default_deny_and_uses_authoritative_names() -> None:
    visibility = VisibilityPolicy(
        visible_entities=frozenset(
            {
                "light.example_kitchen",
                "sensor.example_temperature",
            }
        )
    )
    page = build_home_context(
        [
            _state("light.example_kitchen", "Original Light"),
            _state("sensor.example_temperature", "Example Temperature", "21"),
            _state("media_player.example_tv", "Example TV"),
            _state("sensor.example_hidden", "Hidden Sensor"),
        ],
        registry=_registry(),
        visibility=visibility,
        entity_names={"light.example_kitchen": "Authoritative Kitchen Light"},
        controllable_entities=frozenset({"light.example_kitchen"}),
        areas={"Cooking Area"},
    )

    assert [item.entity_id for item in page.items] == [
        "light.example_kitchen",
        "sensor.example_temperature",
    ]
    assert page.items[0].name == "Authoritative Kitchen Light"
    assert page.items[0].area_name == "Example Kitchen"
    assert page.items[0].device_name == "Example Ceiling Device"
    assert page.items[0].controllable is True
    assert page.items[1].controllable is False
    assert "area_match" in page.items[0].selection_reasons


def test_entity_area_overrides_device_area_and_filters_controls() -> None:
    visibility = VisibilityPolicy(
        visible_entities=frozenset(
            {"media_player.example_tv", "sensor.example_temperature"}
        )
    )
    page = build_home_context(
        [
            _state("media_player.example_tv", "Example TV"),
            _state("sensor.example_temperature", "Example Temperature"),
        ],
        registry=_registry(),
        visibility=visibility,
        entity_names={},
        controllable_entities=frozenset({"media_player.example_tv"}),
        areas={"example_kitchen"},
        controllable_only=True,
    )

    assert page.total == 1
    assert page.items[0].entity_id == "media_player.example_tv"
    assert page.items[0].area_name == "Example Kitchen"


def test_context_query_and_pagination_are_deterministic() -> None:
    visibility = VisibilityPolicy(
        visible_entities=frozenset(
            {"light.example_kitchen", "sensor.example_temperature"}
        )
    )
    first = build_home_context(
        [
            _state("sensor.example_temperature", "Example Temperature"),
            _state("light.example_kitchen", "Example Light"),
        ],
        registry=_registry(),
        visibility=visibility,
        entity_names={},
        controllable_entities=frozenset(),
        query="example kitchen",
        limit=1,
    )
    second = build_home_context(
        [
            _state("sensor.example_temperature", "Example Temperature"),
            _state("light.example_kitchen", "Example Light"),
        ],
        registry=_registry(),
        visibility=visibility,
        entity_names={},
        controllable_entities=frozenset(),
        query="example kitchen",
        limit=1,
        offset=1,
    )

    assert first.total == 2
    assert first.truncated is True
    assert first.next_offset == 1
    assert second.truncated is False
    assert {first.items[0].entity_id, second.items[0].entity_id} == {
        "light.example_kitchen",
        "sensor.example_temperature",
    }


def test_client_context_never_returns_policy_or_registry_hidden_entities() -> None:
    policy = AutonomyPolicyCatalog(
        visibility=VisibilityPolicy(
            visible_entities=frozenset(
                {
                    "light.example_kitchen",
                    "sensor.example_temperature",
                    "sensor.example_hidden",
                }
            )
        ),
        visible_entities=frozenset({"sensor.example_temperature"}),
        included_entities=frozenset({"light.example_kitchen"}),
        simple_entity_policy=True,
    )
    settings = Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret-token",
        autonomy_policy=policy,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states"
        return httpx.Response(
            200,
            json=[
                {
                    **_state("light.example_kitchen", "Example Light"),
                    "last_updated": "2026-08-24T08:00:00+00:00",
                    "context": {},
                },
                {
                    **_state("sensor.example_temperature", "Temperature", "21"),
                    "last_updated": "2026-08-24T08:00:00+00:00",
                    "context": {},
                },
                {
                    **_state("sensor.example_hidden", "Hidden"),
                    "last_updated": "2026-08-24T08:00:00+00:00",
                    "context": {},
                },
                {
                    **_state("switch.example_not_allowed", "Not Allowed"),
                    "last_updated": "2026-08-24T08:00:00+00:00",
                    "context": {},
                },
            ],
        )

    async def hidden_entities() -> frozenset[str]:
        return frozenset({"sensor.example_hidden"})

    async def context_registry() -> HomeContextRegistry:
        return _registry()

    async def read_context():
        async with HomeAssistantClient(
            settings,
            transport=httpx.MockTransport(handler),
            hidden_entities_loader=hidden_entities,
            context_registry_loader=context_registry,
        ) as client:
            context = await client.get_home_context(areas={"Example Kitchen"})
            configuration = await client.list_entities_for_configuration()
            return context, configuration

    result, configuration = asyncio.run(read_context())
    assert [item.entity_id for item in result.items] == [
        "light.example_kitchen",
        "sensor.example_temperature",
    ]
    assert result.items[0].controllable is True
    configured_light = next(
        item
        for item in configuration
        if item["entity_id"] == "light.example_kitchen"
    )
    assert configured_light["area_name"] == "Example Kitchen"
    assert configured_light["device_name"] == "Example Ceiling Device"


def test_context_registry_websocket_reads_all_relationship_registries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []

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
                                {"area_id": "example_room", "name": "Example Room"}
                            ],
                        }
                    ),
                    json.dumps(
                        {
                            "id": 2,
                            "type": "result",
                            "success": True,
                            "result": [
                                {
                                    "id": "device-1",
                                    "area_id": "example_room",
                                    "name": "Example Device",
                                }
                            ],
                        }
                    ),
                    json.dumps(
                        {
                            "id": 3,
                            "type": "result",
                            "success": True,
                            "result": [
                                {
                                    "entity_id": "light.example_room",
                                    "device_id": "device-1",
                                    "hidden_by": None,
                                }
                            ],
                        }
                    ),
                ]
            )

        async def recv(self) -> str:
            return next(self.messages)

        async def send(self, message: str) -> None:
            payload = json.loads(message)
            sent.append(payload["type"])

    class FakeConnection:
        async def __aenter__(self) -> FakeWebSocket:
            return FakeWebSocket()

        async def __aexit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(
        home_assistant_module,
        "connect",
        lambda *args, **kwargs: FakeConnection(),
    )

    async def load() -> HomeContextRegistry:
        async with HomeAssistantClient(
            Settings(
                home_assistant_url="http://homeassistant.test:8123",
                home_assistant_token="secret-token",
            )
        ) as client:
            return await client._load_context_registry_from_websocket()

    registry = asyncio.run(load())
    assert sent == [
        "auth",
        "config/area_registry/list",
        "config/device_registry/list",
        "config/entity_registry/list",
    ]
    assert registry.entities["light.example_room"].device_id == "device-1"
    assert registry.devices["device-1"].area_id == "example_room"


def test_policy_configuration_remains_available_when_context_registry_fails() -> None:
    policy = AutonomyPolicyCatalog(
        visibility=VisibilityPolicy(
            visible_entities=frozenset({"light.example_kitchen"})
        ),
        simple_entity_policy=True,
    )
    settings = Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret-token",
        autonomy_policy=policy,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    **_state("light.example_kitchen", "Example Light"),
                    "last_updated": "2026-08-24T08:00:00+00:00",
                    "context": {},
                }
            ],
        )

    async def broken_registry() -> HomeContextRegistry:
        raise HomeAssistantError("registry unavailable")

    async def load_configuration():
        async with HomeAssistantClient(
            settings,
            transport=httpx.MockTransport(handler),
            context_registry_loader=broken_registry,
        ) as client:
            return await client.list_entities_for_configuration()

    result = asyncio.run(load_configuration())
    assert result == [
        {
            "entity_id": "light.example_kitchen",
            "domain": "light",
            "friendly_name": "Example Light",
            "state": "on",
            "area_id": None,
            "area_name": None,
            "device_id": None,
            "device_name": None,
        }
    ]



def test_context_view_is_a_union_then_intersects_default_deny_policy() -> None:
    visibility = VisibilityPolicy(
        visible_entities=frozenset(
            {
                "light.example_kitchen",
                "sensor.example_temperature",
                "media_player.example_tv",
            }
        )
    )
    view = ContextView(
        id="example_focus",
        name="Example focus",
        areas=("example_kitchen",),
        entities=("media_player.example_tv",),
        max_entities=10,
    )

    page = build_home_context(
        [
            _state("light.example_kitchen", "Example Light"),
            _state("sensor.example_temperature", "Example Temperature"),
            _state("media_player.example_tv", "Example TV"),
            _state("switch.not_visible", "Not visible"),
        ],
        registry=_registry(),
        visibility=visibility,
        entity_names={},
        controllable_entities=frozenset({"light.example_kitchen"}),
        view=view,
        view_selection_source="explicit",
    )

    assert {item.entity_id for item in page.items} == {
        "light.example_kitchen",
        "sensor.example_temperature",
        "media_player.example_tv",
    }
    assert all("context_view" in item.selection_reasons for item in page.items)
    assert "switch.not_visible" not in {item.entity_id for item in page.items}
    assert page.view_id == "example_focus"
    assert page.view_selection_source == "explicit"


def test_context_view_limit_is_deterministic_and_reports_omissions() -> None:
    visibility = VisibilityPolicy(
        visible_entities=frozenset(
            {
                "light.example_kitchen",
                "sensor.example_temperature",
            }
        )
    )
    view = ContextView(
        id="example_limited",
        name="Example limited",
        domains=("light", "sensor"),
        max_entities=1,
    )

    page = build_home_context(
        [
            _state("sensor.example_temperature", "Example Temperature"),
            _state("light.example_kitchen", "Example Light"),
        ],
        registry=_registry(),
        visibility=visibility,
        entity_names={},
        controllable_entities=frozenset(),
        view=view,
        view_selection_source="default",
    )

    assert page.selected_before_limit == 2
    assert page.omitted_by_view_limit == 1
    assert page.total == 1
    assert page.returned == 1
    assert page.view_selection_source == "default"
