import asyncio
from pathlib import Path
from typing import Any

import pytest

from house_brain.actions import ActionPolicyError, ActionRequest, validate_action
from house_brain.agent import TOOLS, _execute_tool
from house_brain.autonomy import AutonomyPolicy, parse_action_constraints
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


def test_fan_services_use_the_generic_action_tools() -> None:
    tools = {
        item["function"]["name"]: item["function"]
        for item in TOOLS
    }

    single = tools["perform_action"]["parameters"]["properties"]
    batch = tools["perform_actions"]["parameters"]["properties"][
        "actions"
    ]["items"]["properties"]

    assert single["domain"]["pattern"] == "^[a-z0-9_]+$"
    assert single["service"]["pattern"] == "^[a-z0-9_]+$"
    assert batch["domain"]["pattern"] == "^[a-z0-9_]+$"


@pytest.mark.parametrize("service", ["turn_on", "turn_off", "toggle"])
def test_fan_state_services_accept_no_data(service: str) -> None:
    validate_action(
        ActionRequest(
            domain="fan",
            service=service,
            entity_id="fan.example_ceiling_fan",
        )
    )


@pytest.mark.parametrize("percentage", [0, 10, 50, 100])
def test_fan_percentage_accepts_valid_values(percentage: int) -> None:
    validate_action(
        ActionRequest(
            domain="fan",
            service="set_percentage",
            entity_id="fan.example_ceiling_fan",
            data={"percentage": percentage},
        )
    )


@pytest.mark.parametrize("percentage", [-1, 101, "50", True])
def test_fan_percentage_rejects_invalid_values(percentage: object) -> None:
    with pytest.raises(ActionPolicyError):
        validate_action(
            ActionRequest(
                domain="fan",
                service="set_percentage",
                entity_id="fan.example_ceiling_fan",
                data={"percentage": percentage},
            )
        )


def test_fan_percentage_simulation_respects_autonomy_policy(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()
    memory = MemoryStore(str(tmp_path / "memory.db"))
    rule = "fan.set_percentage:fan.example_ceiling_fan"
    policy = AutonomyPolicy(
        event_types=frozenset({"periodic_house_check"}),
        action_rules=frozenset({rule}),
        action_constraints=parse_action_constraints(
            '{"fan.set_percentage:fan.example_ceiling_fan":'
            '{"percentage":{"allowed":[0,10,50,100]}}}'
        ),
    )

    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "fan",
                "service": "set_percentage",
                "entity_id": "fan.example_ceiling_fan",
                "data": {"percentage": 50},
            },
            client,
            memory,
            action_mode="simulate",
            autonomy_policy=policy,
        )
    )

    assert result["status"] == "simulated"
    assert result["domain"] == "fan"
    assert result["data"] == {"percentage": 50}
    assert client.calls == []
