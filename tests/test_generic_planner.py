import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from house_brain.actions import ActionRequest
from house_brain.agent import (
    MAX_AGENT_ITERATIONS,
    SYSTEM_PROMPT,
    _clean_model_response,
    _event_mode_instruction,
    _execute_tool,
    _sanitize_tool_arguments,
    _sanitize_tool_error,
)
from house_brain.autonomy import AutonomyPolicy, AutonomyPolicyError
from house_brain.config import Settings
from house_brain.home_assistant import HomeAssistantClient
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


def _action(entity_id: str) -> dict[str, Any]:
    domain = entity_id.partition(".")[0]
    service = "close_cover" if domain == "cover" else "turn_off"
    return {
        "domain": domain,
        "service": service,
        "entity_id": entity_id,
        "dry_run": False,
    }


def test_entity_snapshot_filters_domains_and_attributes() -> None:
    timestamp = "2026-08-03T08:00:00+00:00"

    def state(
        entity_id: str,
        value: str,
        attributes: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "entity_id": entity_id,
            "state": value,
            "attributes": attributes,
            "last_changed": timestamp,
            "last_updated": timestamp,
            "context": {},
        }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/states"
        return httpx.Response(
            200,
            json=[
                state(
                    "cover.sala",
                    "open",
                    {
                        "friendly_name": "Tapparella sala",
                        "current_position": 72,
                        "unsupported": "large-value",
                    },
                ),
                state("light.sala", "on", {"brightness": 180}),
                state("sensor.temperatura", "24", {"unit_of_measurement": "°C"}),
            ],
        )

    settings = Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret-token",
    )

    async def snapshot() -> list[dict[str, Any]]:
        async with HomeAssistantClient(
            settings,
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.list_entities(
                domains={"cover", "sensor"},
                limit=10,
            )

    result = asyncio.run(snapshot())

    assert [item["entity_id"] for item in result] == [
        "cover.sala",
        "sensor.temperatura",
    ]
    assert result[0]["effective_state"] == "partially_open"
    assert result[0]["attributes"] == {
        "friendly_name": "Tapparella sala",
        "current_position": 72,
    }


def test_simulate_batch_forces_every_action_to_dry_run(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()
    policy = AutonomyPolicy(
        event_types=frozenset({"sun_changed"}),
        action_rules=frozenset(
            {
                "cover.close_cover:cover.sala",
                "light.turn_off:light.cucina",
            }
        ),
    )

    result = asyncio.run(
        _execute_tool(
            "perform_actions",
            {
                "actions": [
                    _action("cover.sala"),
                    _action("light.cucina"),
                ]
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            action_mode="simulate",
            autonomy_policy=policy,
        )
    )

    assert result["status"] == "completed"
    assert all(item["status"] == "simulated" for item in result["actions"])
    assert all(item["dry_run"] is True for item in result["actions"])
    assert client.calls == []


def test_batch_is_fully_rejected_before_first_side_effect(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()
    policy = AutonomyPolicy(
        event_types=frozenset({"sun_changed"}),
        action_rules=frozenset({"cover.close_cover:cover.sala"}),
    )

    with pytest.raises(AutonomyPolicyError):
        asyncio.run(
            _execute_tool(
                "perform_actions",
                {
                    "actions": [
                        _action("cover.sala"),
                        _action("light.cucina"),
                    ]
                },
                client,
                MemoryStore(str(tmp_path / "memory.db")),
                action_mode="execute",
                autonomy_policy=policy,
            )
        )

    assert client.calls == []


def test_execute_batch_runs_all_allowlisted_actions(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()
    policy = AutonomyPolicy(
        event_types=frozenset({"sun_changed"}),
        action_rules=frozenset(
            {
                "cover.close_cover:cover.sala",
                "light.turn_off:light.cucina",
            }
        ),
    )

    result = asyncio.run(
        _execute_tool(
            "perform_actions",
            {
                "actions": [
                    _action("cover.sala"),
                    _action("light.cucina"),
                ]
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            action_mode="execute",
            autonomy_policy=policy,
        )
    )

    assert result["status"] == "completed"
    assert [item["status"] for item in result["actions"]] == [
        "executed",
        "executed",
    ]
    assert len(client.calls) == 2


def test_cover_position_overrides_inconsistent_reported_state() -> None:
    timestamp = "2026-08-03T08:00:00+00:00"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "entity_id": "cover.cucina",
                    "state": "open",
                    "attributes": {"current_position": 0},
                    "last_changed": timestamp,
                    "last_updated": timestamp,
                    "context": {},
                }
            ],
        )

    settings = Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret-token",
    )

    async def snapshot() -> list[dict[str, Any]]:
        async with HomeAssistantClient(
            settings,
            transport=httpx.MockTransport(handler),
        ) as client:
            return await client.list_entities(domains={"cover"})

    result = asyncio.run(snapshot())

    assert result[0]["state"] == "closed"
    assert result[0]["attributes"]["current_position"] == 0
    assert result[0]["effective_state"] == "closed"


def test_generic_planner_has_room_for_reasoning_and_final_response() -> None:
    assert MAX_AGENT_ITERATIONS == 8


def test_system_prompt_forbids_unexecuted_action_claims() -> None:
    assert "devi chiamare perform_action" in SYSTEM_PROMPT
    assert "senza il risultato del" in SYSTEM_PROMPT
    assert "usare azimuth ed" in SYSTEM_PROMPT
    assert "non è un inventario completo" in SYSTEM_PROMPT
    assert "percentuale di APERTURA" in SYSTEM_PROMPT
    assert "Non usare mai posizione 100 per abbassare" in SYSTEM_PROMPT


def test_model_control_markers_are_removed_from_response() -> None:
    assert _clean_model_response(
        "thought\n<channel|>Risposta finale"
    ) == "Risposta finale"


def test_simulate_instruction_forbids_claiming_real_changes() -> None:
    instruction = _event_mode_instruction("simulate")

    assert "simulate e non eseguite" in instruction
    assert "realmente modificato" in instruction


def test_tool_audit_keeps_actions_and_redacts_memory_contents() -> None:
    action = _sanitize_tool_arguments(
        "perform_action",
        {
            "domain": "cover",
            "service": "set_cover_position",
            "entity_id": "cover.cucina",
            "data": {"position": 0},
            "dry_run": True,
        },
    )
    memory = _sanitize_tool_arguments(
        "remember_fact",
        {
            "key": "private.fact",
            "value": "contenuto riservato",
            "category": "fact",
            "importance": 5,
        },
    )
    recall = _sanitize_tool_arguments(
        "recall_memories",
        {"query": "contenuto riservato", "limit": 3},
    )

    assert action["data"] == {"position": 0}
    assert "value" not in memory
    assert "query" not in recall
    assert recall == {"query_redacted": True, "limit": 3}


def test_validation_audit_error_excludes_input_values() -> None:
    secret = "contenuto-da-non-salvare"
    with pytest.raises(Exception) as captured:
        ActionRequest.model_validate(
            {
                "domain": "cover",
                "data": {"note": secret},
            }
        )

    error = _sanitize_tool_error(captured.value)

    assert "service: Field required" in error
    assert "entity_id: Field required" in error
    assert secret not in error


def test_prompt_requires_top_level_action_fields_and_honest_failures() -> None:
    assert "domain, service, entity_id e dry_run" in SYSTEM_PROMPT
    assert "nessuna azione è stata simulata o eseguita" in SYSTEM_PROMPT
