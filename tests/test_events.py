import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from house_brain.agent import ActionExecutionBudget, _execute_tool
from house_brain.autonomy import AutonomyPolicy, AutonomyPolicyError
from house_brain.events import (
    AgentEventRequest,
    AutonomousExecutionDisabledError,
    EventStore,
    ToolAuditRecord,
    build_event_message,
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
        tool_trace=[
            ToolAuditRecord(
                sequence=1,
                tool="get_entity",
                arguments={"entity_id": "switch.ventola"},
                status="completed",
                outcome="completed",
            )
        ],
    )

    events = store.list()
    assert len(events) == 1
    assert events[0].event_id == "event-1"
    assert events[0].context == {"person": "Vincenzo"}
    assert events[0].tools_used == ["get_entity"]
    assert events[0].tool_trace[0].arguments == {
        "entity_id": "switch.ventola"
    }
    assert store.get("event-1") == events[0]
    assert store.get("missing") is None


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


def test_event_message_includes_local_time_and_context() -> None:
    event = AgentEventRequest(
        event_type="sun_context_changed",
        mode="simulate",
        instruction="Sistema la casa",
        context={"zone": "home"},
    )

    message = build_event_message(
        event,
        now=datetime.fromisoformat("2026-08-03T13:45:00+02:00"),
    )

    assert "Data e ora locale: 2026-08-03T13:45:00+02:00" in message
    assert "Stagione meteorologica: estate" in message
    assert '"zone": "home"' in message


def test_event_store_migrates_existing_audit_table(tmp_path: Path) -> None:
    database = tmp_path / "memory.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE agent_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                mode TEXT NOT NULL,
                instruction TEXT NOT NULL,
                context_json TEXT NOT NULL,
                status TEXT NOT NULL,
                response TEXT NOT NULL,
                tools_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

    EventStore(str(database))

    with sqlite3.connect(database) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(agent_events)"
            ).fetchall()
        }

    assert "tool_trace_json" in columns


def test_execute_budget_blocks_second_tool_call(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()
    memory = MemoryStore(str(tmp_path / "memory.db"))
    policy = AutonomyPolicy(
        event_types=frozenset({"canary_light_control"}),
        execute_event_types=frozenset({"canary_light_control"}),
        action_rules=frozenset(
            {
                "light.turn_on:light.sala_uno",
                "light.turn_off:light.sala_uno",
            }
        ),
    )
    budget = ActionExecutionBudget(max_actions=1)

    first = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "light",
                "service": "turn_on",
                "entity_id": "light.sala_uno",
            },
            client,
            memory,
            action_mode="execute",
            autonomy_policy=policy,
            execution_budget=budget,
        )
    )

    assert first["status"] == "executed"
    with pytest.raises(
        AutonomyPolicyError,
        match="execute action budget exceeded",
    ):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "light",
                    "service": "turn_off",
                    "entity_id": "light.sala_uno",
                },
                client,
                memory,
                action_mode="execute",
                autonomy_policy=policy,
                execution_budget=budget,
            )
        )

    assert budget.consumed_actions == 1
    assert [call["service"] for call in client.calls] == ["turn_on"]


def test_execute_budget_rejects_batch_before_side_effect(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()
    memory = MemoryStore(str(tmp_path / "memory.db"))
    policy = AutonomyPolicy(
        event_types=frozenset({"canary_light_control"}),
        execute_event_types=frozenset({"canary_light_control"}),
        action_rules=frozenset(
            {
                "light.turn_on:light.sala_uno",
                "light.turn_off:light.sala_uno",
            }
        ),
    )

    with pytest.raises(
        AutonomyPolicyError,
        match="execute action budget exceeded",
    ):
        asyncio.run(
            _execute_tool(
                "perform_actions",
                {
                    "actions": [
                        {
                            "domain": "light",
                            "service": "turn_on",
                            "entity_id": "light.sala_uno",
                        },
                        {
                            "domain": "light",
                            "service": "turn_off",
                            "entity_id": "light.sala_uno",
                        },
                    ]
                },
                client,
                memory,
                action_mode="execute",
                autonomy_policy=policy,
                execution_budget=ActionExecutionBudget(max_actions=1),
            )
        )

    assert client.calls == []
