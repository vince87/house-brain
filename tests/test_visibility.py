import asyncio
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from house_brain.autonomy import (
    AutonomyPolicyError,
    AutonomyPolicyCatalog,
    VisibilityPolicy,
    load_autonomy_policy,
)
from house_brain.config import Settings
from house_brain.home_assistant import (
    EntityNotFoundError,
    HomeAssistantClient,
)


TIMESTAMP = "2026-08-06T08:00:00Z"


def _state(
    entity_id: str,
    *,
    state: str = "on",
    attributes: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "entity_id": entity_id,
        "state": state,
        "attributes": attributes or {},
        "last_changed": TIMESTAMP,
        "last_updated": TIMESTAMP,
        "context": {},
    }


def _settings(visibility: VisibilityPolicy) -> Settings:
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
        autonomy_policy=AutonomyPolicyCatalog(
            events={},
            visibility=visibility,
        ),
    )


def test_visibility_filters_search_and_planner_snapshot() -> None:
    visibility = VisibilityPolicy(
        exclude_entities=frozenset({"light.luci"}),
        exclude_patterns=("sensor.*_diagnostic",),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states"
        return httpx.Response(
            200,
            json=[
                _state(
                    "light.luci",
                    attributes={"friendly_name": "Gruppo luci"},
                ),
                _state(
                    "sensor.router_diagnostic",
                    attributes={"friendly_name": "Diagnostica router"},
                ),
                _state(
                    "sensor.temperatura_sala",
                    state="24",
                    attributes={"unit_of_measurement": "°C"},
                ),
            ],
        )

    async def read() -> tuple[list[dict[str, str]], list[dict[str, object]]]:
        async with HomeAssistantClient(
            _settings(visibility),
            transport=httpx.MockTransport(handler),
        ) as client:
            search = await client.search_entities("sala")
            snapshot = await client.list_entities(
                domains={"light", "sensor"},
                limit=20,
            )
            return search, snapshot

    search, snapshot = asyncio.run(read())

    assert [item["entity_id"] for item in search] == [
        "sensor.temperatura_sala"
    ]
    assert [item["entity_id"] for item in snapshot] == [
        "sensor.temperatura_sala"
    ]


def test_hidden_entity_is_not_requested_from_home_assistant() -> None:
    visibility = VisibilityPolicy(
        exclude_entities=frozenset({"light.luci"}),
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    async def read() -> None:
        async with HomeAssistantClient(
            _settings(visibility),
            transport=httpx.MockTransport(handler),
        ) as client:
            with pytest.raises(EntityNotFoundError):
                await client.get_entity("light.luci")
            with pytest.raises(EntityNotFoundError):
                await client.get_history(
                    "light.luci",
                    start=datetime.fromisoformat(
                        "2026-08-06T07:00:00+00:00"
                    ),
                    end=datetime.fromisoformat(
                        "2026-08-06T08:00:00+00:00"
                    ),
                )

    asyncio.run(read())
    assert requests == []


def test_group_attributes_do_not_leak_hidden_entity_ids() -> None:
    visibility = VisibilityPolicy(
        exclude_entities=frozenset({"light.luci"}),
        exclude_patterns=("sensor.*_last_seen",),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states/group.sala"
        return httpx.Response(
            200,
            json=_state(
                "group.sala",
                attributes={
                    "entity_id": [
                        "light.sala_uno",
                        "light.luci",
                        "sensor.router_last_seen",
                    ],
                    "nested": {
                        "primary": "light.luci",
                        "visible": "light.sala_uno",
                    },
                },
            ),
        )

    async def read() -> dict[str, object]:
        async with HomeAssistantClient(
            _settings(visibility),
            transport=httpx.MockTransport(handler),
        ) as client:
            entity = await client.get_entity("group.sala")
            return entity.attributes

    attributes = asyncio.run(read())

    assert attributes["entity_id"] == ["light.sala_uno"]
    assert attributes["nested"] == {"visible": "light.sala_uno"}
    assert "light.luci" not in str(attributes)
    assert "sensor.router_last_seen" not in str(attributes)


def test_yaml_visibility_is_global_and_conflicts_fail_startup(
    tmp_path: Path,
) -> None:
    valid_path = tmp_path / "valid.yaml"
    valid_path.write_text(
        """
version: 1
visibility:
  exclude_entities: [light.luci]
  exclude_patterns: [sensor.*_diagnostic]
events: {}
""".lstrip()
    )

    catalog = load_autonomy_policy(valid_path)

    assert catalog.visibility.is_hidden("light.luci")
    assert catalog.visibility.is_hidden("sensor.router_diagnostic")
    assert not catalog.visibility.is_hidden("sensor.temperatura")

    conflicting_path = tmp_path / "conflicting.yaml"
    conflicting_path.write_text(
        """
version: 1
visibility:
  exclude_entities: [light.luci]
events:
  periodic_house_check:
    modes: [simulate]
    actions:
      light.turn_off:
        entities: [light.luci]
""".lstrip()
    )

    with pytest.raises(
        AutonomyPolicyError,
        match="Hidden entities cannot be authorized",
    ):
        load_autonomy_policy(conflicting_path)
