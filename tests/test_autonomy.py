import asyncio
from pathlib import Path
from typing import Any

import pytest

from house_brain.actions import ActionRequest
from house_brain.agent import _execute_tool
from house_brain.autonomy import (
    AutonomyPolicy,
    AutonomyPolicyError,
    parse_allowlist,
)
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


def test_allowlist_denies_everything_by_default() -> None:
    policy = AutonomyPolicy(
        event_types=parse_allowlist(None),
        action_rules=parse_allowlist(None),
    )

    with pytest.raises(AutonomyPolicyError):
        policy.validate_event("test_simulated_fan_start")

    with pytest.raises(AutonomyPolicyError):
        policy.validate_action(
            ActionRequest(
                domain="switch",
                service="turn_on",
                entity_id="switch.ventola",
            )
        )


def test_allowlist_requires_exact_event_and_action_matches() -> None:
    policy = AutonomyPolicy(
        event_types=parse_allowlist("garage_fan_control"),
        action_rules=parse_allowlist(
            "switch.turn_off:switch.ventola"
        ),
    )

    policy.validate_event("garage_fan_control")
    policy.validate_action(
        ActionRequest(
            domain="switch",
            service="turn_off",
            entity_id="switch.ventola",
        )
    )

    with pytest.raises(AutonomyPolicyError):
        policy.validate_event("garage_fan_control_extra")

    with pytest.raises(AutonomyPolicyError):
        policy.validate_action(
            ActionRequest(
                domain="switch",
                service="turn_on",
                entity_id="switch.ventola",
            )
        )


def test_allowlist_rejects_wildcards_and_domain_mismatches() -> None:
    with pytest.raises(AutonomyPolicyError):
        AutonomyPolicy(
            event_types=frozenset(),
            action_rules=frozenset({"switch.turn_on:switch.*"}),
        )

    with pytest.raises(AutonomyPolicyError):
        AutonomyPolicy(
            event_types=frozenset(),
            action_rules=frozenset(
                {"switch.turn_on:light.luce_garage"}
            ),
        )


def test_agent_does_not_simulate_unallowlisted_action(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()
    memory = MemoryStore(str(tmp_path / "memory.db"))
    policy = AutonomyPolicy(
        event_types=frozenset({"test_simulated_fan_start"}),
        action_rules=frozenset(
            {"switch.turn_off:switch.ventola"}
        ),
    )

    with pytest.raises(AutonomyPolicyError):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "switch",
                    "service": "turn_on",
                    "entity_id": "switch.ventola",
                    "dry_run": False,
                },
                client,
                memory,
                action_mode="simulate",
                autonomy_policy=policy,
            )
        )

    assert client.calls == []
