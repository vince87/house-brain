import asyncio
from pathlib import Path
from typing import Any

import pytest

from house_brain.actions import ActionRequest
from house_brain.agent import _execute_tool
from house_brain.autonomy import AutonomyPolicyError, load_autonomy_policy
from house_brain.memory import MemoryStore


class StubHomeAssistantClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def call_service(
        self,
        domain: str,
        service: str,
        *,
        entity_id: str,
        data: dict[str, Any],
    ) -> list[object]:
        self.calls.append(
            {
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
                "data": data,
            }
        )
        return []


def _write_policy(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "autonomy.yaml"
    path.write_text(content)
    return path


def test_simple_policy_controls_only_included_entities(tmp_path: Path) -> None:
    catalog = load_autonomy_policy(
        _write_policy(
            tmp_path,
            """
version: 2
entities:
  include:
    - switch.example_fan_relay
  exclude: []
""".lstrip(),
        )
    )
    policy = catalog.resolve("any_valid_event", "simulate")

    policy.validate_action(
        ActionRequest(
            domain="switch",
            service="turn_on",
            entity_id="switch.example_fan_relay",
        )
    )
    with pytest.raises(AutonomyPolicyError, match="not included"):
        policy.validate_action(
            ActionRequest(
                domain="switch",
                service="turn_on",
                entity_id="switch.non_incluso",
            )
        )


def test_same_entity_policy_accepts_any_valid_event(tmp_path: Path) -> None:
    catalog = load_autonomy_policy(
        _write_policy(
            tmp_path,
            "version: 2\nentities:\n  include: []\n  exclude: []\n",
        )
    )

    assert catalog.resolve("garage_check", "observe").simple_entity_policy
    assert catalog.resolve("manual_test", "simulate").simple_entity_policy
    assert catalog.resolve("sun_context_changed", "execute").simple_entity_policy


def test_code_is_bound_to_entity_for_every_service(tmp_path: Path) -> None:
    catalog = load_autonomy_policy(
        _write_policy(
            tmp_path,
            """
version: 2
entities:
  include:
    - entity_id: lock.example_front_door
      code: "2468"
  exclude: []
""".lstrip(),
        )
    )
    policy = catalog.resolve_chat()
    assert policy is not None

    for service in ("lock", "unlock"):
        action = ActionRequest(
            domain="lock",
            service=service,
            entity_id="lock.example_front_door",
        )
        with pytest.raises(AutonomyPolicyError, match="valid authorization code"):
            policy.validate_action(action)
        policy.validate_action(action, authorization_codes=("2468",))


def test_simulation_is_rejected_before_side_effect_for_unincluded_entity(
    tmp_path: Path,
) -> None:
    catalog = load_autonomy_policy(
        _write_policy(
            tmp_path,
            "version: 2\nentities:\n  include: []\n  exclude: []\n",
        )
    )
    client = StubHomeAssistantClient()

    with pytest.raises(AutonomyPolicyError, match="not included"):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "switch",
                    "service": "turn_on",
                    "entity_id": "switch.example_fan_relay",
                },
                client,
                MemoryStore(str(tmp_path / "memory.db")),
                action_mode="simulate",
                autonomy_policy=catalog.resolve("test", "simulate"),
            )
        )
    assert client.calls == []


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("version: 1\nevents: {}\n", "version must be 2"),
        (
            "version: 2\nentities:\n  include: []\n  include: []\n",
            "Duplicate autonomy policy key",
        ),
        (
            "version: 2\nentities:\n  include: [invalid]\n  exclude: []\n",
            "Invalid included entity_id",
        ),
        (
            "version: 2\nentities:\n  include:\n"
            "    - entity_id: lock.a\n      code: x\n  exclude: []\n",
            "Invalid authorization code",
        ),
        (
            "version: 2\nentities:\n"
            "  include: [light.example_room]\n"
            "  exclude: [light.example_room]\n",
            "both included and excluded",
        ),
    ],
)
def test_policy_rejects_invalid_configuration(
    tmp_path: Path,
    content: str,
    match: str,
) -> None:
    with pytest.raises(AutonomyPolicyError, match=match):
        load_autonomy_policy(_write_policy(tmp_path, content))


def test_example_autonomy_policy_is_valid() -> None:
    catalog = load_autonomy_policy(Path("autonomy.yaml.example"))

    assert "light.example_living_room" in catalog.included_entities
    assert catalog.visibility.is_hidden("sensor.example_diagnostic")
    assert catalog.entity_codes["lock.example_front_door"] == "2468"
    assert "2468" not in repr(catalog)
