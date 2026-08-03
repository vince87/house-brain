import asyncio

import pytest
from pathlib import Path
from typing import Any

from house_brain.agent import _execute_tool
from house_brain.autonomy import AutonomyPolicy
from house_brain.events import (
    AgentEventRequest,
    AutonomousExecutionDisabledError,
    EventStore,
    validate_execution_enabled,
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


def test_simulate_mode_overrides_model_execution_request(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()
    memory = MemoryStore(str(tmp_path / "memory.db"))

    result = asyncio.run(
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
            autonomy_policy=AutonomyPolicy(
                event_types=frozenset({"test_simulated_fan_start"}),
                action_rules=frozenset(
                    {"switch.turn_on:switch.ventola"}
                ),
            ),
        )
    )

    assert result["status"] == "simulated"
    assert result["dry_run"] is True
    assert client.calls == []


def test_observe_mode_blocks_action_tool(tmp_path: Path) -> None:
    client = StubHomeAssistantClient()
    memory = MemoryStore(str(tmp_path / "memory.db"))

    result = asyncio.run(
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
            action_mode="observe",
        )
    )

    assert result["status"] == "blocked_by_event_mode"
    assert client.calls == []


def test_event_store_records_audit_log(tmp_path: Path) -> None:
    store = EventStore(str(tmp_path / "memory.db"))
    request = AgentEventRequest(
        event_type="person_left_home",
        mode="simulate",
        instruction="Controlla la casa",
        context={"person": "Vincenzo"},
    )

    store.record(
        "event-1",
        request,
        status="completed",
        response="Nessuna azione necessaria.",
        tools_used=["get_entity"],
    )

    events = store.list()
    assert len(events) == 1
    assert events[0].event_id == "event-1"
    assert events[0].context == {"person": "Vincenzo"}
    assert events[0].tools_used == ["get_entity"]


def test_execute_mode_forces_real_allowlisted_action(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()
    memory = MemoryStore(str(tmp_path / "memory.db"))
    policy = AutonomyPolicy(
        event_types=frozenset({"test_real_fan_start"}),
        action_rules=frozenset(
            {"switch.turn_on:switch.ventola"}
        ),
    )

    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "switch",
                "service": "turn_on",
                "entity_id": "switch.ventola",
                "dry_run": True,
            },
            client,
            memory,
            action_mode="execute",
            autonomy_policy=policy,
        )
    )

    assert result["status"] == "executed"
    assert client.calls == [
        {
            "domain": "switch",
            "service": "turn_on",
            "entity_id": "switch.ventola",
            "data": {},
        }
    ]


def test_execute_mode_requires_explicit_kill_switch() -> None:
    with pytest.raises(
        AutonomousExecutionDisabledError,
        match="Autonomous execution is disabled",
    ):
        validate_execution_enabled("execute", False)

    validate_execution_enabled("execute", True)
    validate_execution_enabled("simulate", False)
