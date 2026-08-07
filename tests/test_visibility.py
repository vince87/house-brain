import asyncio
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from house_brain.actions import ActionRequest
from house_brain.agent import _execute_action_plan
from house_brain.autonomy import (
    AutonomyPolicyCatalog,
    AutonomyPolicyError,
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
        exclude_entities=frozenset({"light.example_group"}),
        exclude_patterns=("sensor.*_diagnostic",),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states"
        return httpx.Response(
            200,
            json=[
                _state(
                    "light.example_group",
                    attributes={"friendly_name": "Gruppo luci"},
                ),
                _state(
                    "sensor.example_diagnostic",
                    attributes={"friendly_name": "Diagnostica router"},
                ),
                _state(
                    "sensor.example_room_temperature",
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
        "sensor.example_room_temperature"
    ]
    assert [item["entity_id"] for item in snapshot] == [
        "sensor.example_room_temperature"
    ]


def test_hidden_entity_is_not_requested_from_home_assistant() -> None:
    visibility = VisibilityPolicy(
        exclude_entities=frozenset({"light.example_group"}),
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
                await client.get_entity("light.example_group")
            with pytest.raises(EntityNotFoundError):
                await client.get_history(
                    "light.example_group",
                    start=datetime.fromisoformat(
                        "2026-08-06T07:00:00+00:00"
                    ),
                    end=datetime.fromisoformat(
                        "2026-08-06T08:00:00+00:00"
                    ),
                )

    asyncio.run(read())
    assert requests == []


def test_hidden_entity_action_is_rejected_even_in_dry_run() -> None:
    visibility = VisibilityPolicy(
        exclude_entities=frozenset({"light.example_group"}),
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    async def simulate() -> None:
        async with HomeAssistantClient(
            _settings(visibility),
            transport=httpx.MockTransport(handler),
        ) as client:
            with pytest.raises(EntityNotFoundError):
                await _execute_action_plan(
                    [
                        ActionRequest(
                            domain="light",
                            service="turn_off",
                            entity_id="light.example_group",
                            dry_run=True,
                        )
                    ],
                    client,
                    action_mode=None,
                    autonomy_policy=None,
                )

    asyncio.run(simulate())
    assert requests == []



def test_group_attributes_do_not_leak_hidden_entity_ids() -> None:
    visibility = VisibilityPolicy(
        exclude_entities=frozenset({"light.example_group"}),
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
                        "light.example_living_room",
                        "light.example_group",
                        "sensor.example_last_seen",
                    ],
                    "nested": {
                        "primary": "light.example_group",
                        "visible": "light.example_living_room",
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

    assert attributes["entity_id"] == ["light.example_living_room"]
    assert attributes["nested"] == {"visible": "light.example_living_room"}
    assert "light.example_group" not in str(attributes)
    assert "sensor.example_last_seen" not in str(attributes)


def test_yaml_visibility_is_global_and_conflicts_fail_startup(
    tmp_path: Path,
) -> None:
    valid_path = tmp_path / "valid.yaml"
    valid_path.write_text(
        """
version: 2
entities:
  include: [light.example_room]
  exclude: [light.example_group, sensor.*_diagnostic]
""".lstrip()
    )

    catalog = load_autonomy_policy(valid_path)

    assert catalog.visibility.is_hidden("light.example_group")
    assert catalog.visibility.is_hidden("sensor.example_diagnostic")
    assert not catalog.visibility.is_hidden("sensor.example_temperature")

    conflicting_path = tmp_path / "conflicting.yaml"
    conflicting_path.write_text(
        """
version: 2
entities:
  include: [light.example_group]
  exclude: [light.example_group]
""".lstrip()
    )

    with pytest.raises(
        AutonomyPolicyError,
        match="both included and excluded",
    ):
        load_autonomy_policy(conflicting_path)
