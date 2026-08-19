import asyncio

import httpx

from house_brain.autonomy import AutonomyPolicyCatalog, VisibilityPolicy
from house_brain.config import Settings
from house_brain.home_assistant import HomeAssistantClient

TEST_AUTONOMY_POLICY = AutonomyPolicyCatalog(
    visibility=VisibilityPolicy(visible_entities=frozenset(["house_brain.config","house_brain.home_assistant","automation.example_fan_control","switch.example_fan_relay","switch.example_garage_light","homeassistant.test","light.example_kitchen","switch.example_fan","light.example_room_two","switch.example_room_two","lock.example_front_door","exact.status","ambiguous.status","blocked.status","light.example_room","switch.example_room","media_player.example_display","light.example_room_one","exact.entity","weak.status"])),
)



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
                autonomy_policy=TEST_AUTONOMY_POLICY,
        )
        async with HomeAssistantClient(
            settings,
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.search_entities(
                "example fan",
            )

    results = asyncio.run(search())

    assert [item["entity_id"] for item in results[:2]] == [
        "automation.example_fan_control",
        "switch.example_fan_relay",
    ]
    assert results[1]["state"] == "off"


def test_entity_search_does_not_return_unrelated_preferred_domains() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "entity_id": "light.example_kitchen",
                    "state": "off",
                    "attributes": {"friendly_name": "Luce cucina"},
                    "last_changed": "2026-08-03T08:00:00Z",
                    "last_updated": "2026-08-03T08:00:00Z",
                },
                {
                    "entity_id": "switch.example_fan",
                    "state": "off",
                    "attributes": {"friendly_name": "Ventola garage"},
                    "last_changed": "2026-08-03T08:00:00Z",
                    "last_updated": "2026-08-03T08:00:00Z",
                },
            ],
        )

    async def search() -> list[dict[str, str]]:
        async with HomeAssistantClient(
            Settings(
                home_assistant_url="http://homeassistant.test:8123",
                home_assistant_token="secret",
                autonomy_policy=TEST_AUTONOMY_POLICY,
            ),
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.search_entities("serratura ingresso")

    assert asyncio.run(search()) == []


def test_entity_resolver_reports_unique_and_ambiguous_names() -> None:
    def state(entity_id: str, friendly_name: str) -> dict[str, object]:
        return {
            "entity_id": entity_id,
            "state": "off",
            "attributes": {"friendly_name": friendly_name},
            "last_changed": "2026-08-03T08:00:00Z",
            "last_updated": "2026-08-03T08:00:00Z",
        }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                state("light.example_room_two", "Luce sala due"),
                state("switch.example_room_two", "Ventola sala due"),
                state("lock.example_front_door", "Porta ingresso"),
            ],
        )

    async def resolve() -> tuple[str, str, str]:
        async with HomeAssistantClient(
            Settings(
                home_assistant_url="http://homeassistant.test:8123",
                home_assistant_token="secret",
                autonomy_policy=TEST_AUTONOMY_POLICY,
            ),
            transport=httpx.MockTransport(handler),
        ) as client:
            exact = await client.resolve_entity("Porta ingresso")
            ambiguous = await client.resolve_entity("sala due")
            blocked = await client.resolve_entity(
                "Porta ingresso",
                allowed_entities=frozenset(
                    {"light.example_room_two"}
                ),
            )
            return exact.status, ambiguous.status, blocked.status

    assert asyncio.run(resolve()) == (
        "resolved",
        "ambiguous",
        "not_controllable",
    )


def test_entity_resolver_prefers_allowed_control_target() -> None:
    def state(entity_id: str, friendly_name: str) -> dict[str, object]:
        return {
            "entity_id": entity_id,
            "state": "off",
            "attributes": {"friendly_name": friendly_name},
            "last_changed": "2026-08-03T08:00:00Z",
            "last_updated": "2026-08-03T08:00:00Z",
        }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                state("light.example_room", "Dispositivo sala"),
                state("switch.example_room", "Dispositivo sala"),
            ],
        )

    async def resolve() -> tuple[str, str | None]:
        async with HomeAssistantClient(
            Settings(
                home_assistant_url="http://homeassistant.test:8123",
                home_assistant_token="secret",
                autonomy_policy=TEST_AUTONOMY_POLICY,
            ),
            transport=httpx.MockTransport(handler),
        ) as client:
            result = await client.resolve_entity(
                "Dispositivo sala",
                allowed_entities=frozenset(
                    {"switch.example_room"}
                ),
            )
            return (
                result.status,
                result.entity["entity_id"] if result.entity else None,
            )

    assert asyncio.run(resolve()) == (
        "resolved",
        "switch.example_room",
    )


def test_message_resolver_finds_friendly_name_before_model() -> None:
    def state(entity_id: str, friendly_name: str) -> dict[str, object]:
        return {
            "entity_id": entity_id,
            "state": "off",
            "attributes": {"friendly_name": friendly_name},
            "last_changed": "2026-08-03T08:00:00Z",
            "last_updated": "2026-08-03T08:00:00Z",
        }

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                state("media_player.example_display", "Example Tablet"),
                state("light.example_room_one", "Sala Uno"),
                state("light.example_room_two", "Sala Due"),
            ],
        )

    async def resolve() -> tuple[str, str | None, str]:
        async with HomeAssistantClient(
            Settings(
                home_assistant_url="http://homeassistant.test:8123",
                home_assistant_token="secret",
                autonomy_policy=TEST_AUTONOMY_POLICY,
            ),
            transport=httpx.MockTransport(handler),
        ) as client:
            exact = await client.resolve_entity_from_message(
                "Simula lo spegnimento di Example Tablet",
                allowed_entities=frozenset(
                    {"media_player.example_display"}
                ),
            )
            weak = await client.resolve_entity_from_message(
                "Simula lo spegnimento del dispositivo della sala",
                allowed_entities=frozenset(
                    {
                        "light.example_room_one",
                        "light.example_room_two",
                    }
                ),
            )
            return (
                exact.status,
                (
                    exact.entity["entity_id"]
                    if exact.entity is not None
                    else None
                ),
                weak.status,
            )

    assert asyncio.run(resolve()) == (
        "resolved",
        "media_player.example_display",
        "ambiguous",
    )
