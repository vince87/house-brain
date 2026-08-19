import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from house_brain.actions import ActionRequest
from house_brain.agent import (
    MAX_AGENT_ITERATIONS,
    SYSTEM_PROMPT,
    TOOLS,
    EntityResolutionGuard,
    _clean_model_response,
    _entity_resolution_requires_retry,
    _event_mode_instruction,
    _execute_tool,
    _finalize_observe_response,
    _incomplete_inventory_requires_retry,
    _memory_compliance_review_required,
    _relevant_service_contract_context,
    _sanitize_tool_arguments,
    _sanitize_tool_error,
    _tool_outcome,
    _tools_for_entity_resolution,
    _unresolved_entity_response,
)
from house_brain.autonomy import AutonomyPolicy, AutonomyPolicyError
from house_brain.config import Settings
from house_brain.events import ToolAuditRecord
from house_brain.home_assistant import (
    EntityResolution,
    HomeAssistantClient,
    HomeAssistantError,
)
from house_brain.memory import MemoryInput, MemoryStore


class StubHomeAssistantClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def resolve_entity(
        self,
        query: str,
        *,
        domain: str | None = None,
        allowed_entities: frozenset[str] | None = None,
        limit: int = 5,
    ) -> EntityResolution:
        assert query == "Example Room"
        assert domain == "light"
        assert allowed_entities == frozenset({"light.example_room"})
        assert limit == 5
        return EntityResolution(
            status="resolved",
            query=query,
            entity={
                "entity_id": "light.example_room",
                "friendly_name": "Example Room",
                "state": "off",
            },
        )

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
                    "cover.example_room_shade",
                    "open",
                    {
                        "friendly_name": "Example room shade",
                        "current_position": 72,
                        "unsupported": "large-value",
                    },
                ),
                state("light.example_room", "on", {"brightness": 180}),
                state(
                    "sensor.example_temperature",
                    "24",
                    {"unit_of_measurement": "°C"},
                ),
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
        "cover.example_room_shade",
        "sensor.example_temperature",
    ]
    assert result[0]["effective_state"] == "partially_open"
    assert result[0]["attributes"] == {
        "friendly_name": "Example room shade",
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
                "cover.close_cover:cover.example_room_shade",
                "light.turn_off:light.example_kitchen",
            }
        ),
    )

    result = asyncio.run(
        _execute_tool(
            "perform_actions",
            {
                "actions": [
                    _action("cover.example_room_shade"),
                    _action("light.example_kitchen"),
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
        action_rules=frozenset({"cover.close_cover:cover.example_room_shade"}),
    )

    with pytest.raises(AutonomyPolicyError):
        asyncio.run(
            _execute_tool(
                "perform_actions",
                {
                    "actions": [
                        _action("cover.example_room_shade"),
                        _action("light.example_kitchen"),
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
                "cover.close_cover:cover.example_room_shade",
                "light.turn_off:light.example_kitchen",
            }
        ),
    )

    result = asyncio.run(
        _execute_tool(
            "perform_actions",
            {
                "actions": [
                    _action("cover.example_room_shade"),
                    _action("light.example_kitchen"),
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
                    "entity_id": "cover.example_kitchen_shade",
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


def test_unresolved_entity_response_is_server_generated() -> None:
    assert "un'unica entità controllabile" in _unresolved_entity_response("ambiguous")
    assert "Non ho trovato" in _unresolved_entity_response("not_found")
    assert "non è inclusa" in _unresolved_entity_response("not_controllable")


def test_action_tools_are_hidden_until_resolution() -> None:
    tools = [
        {"function": {"name": "resolve_entity"}},
        {"function": {"name": "perform_action"}},
        {"function": {"name": "perform_actions"}},
        {"function": {"name": "get_entity"}},
    ]
    guard = EntityResolutionGuard(required=True)

    unresolved = _tools_for_entity_resolution(tools, guard)
    assert [tool["function"]["name"] for tool in unresolved] == [
        "resolve_entity",
        "perform_actions",
        "get_entity",
    ]

    guard.record(
        {
            "status": "resolved",
            "entity": {"entity_id": "light.example_room"},
        }
    )
    assert _tools_for_entity_resolution(tools, guard) == tools


def test_required_resolution_is_language_independent() -> None:
    guard = EntityResolutionGuard(required=True)

    assert guard.required is True


def test_required_resolution_blocks_direct_action() -> None:
    guard = EntityResolutionGuard(required=True)

    with pytest.raises(
        AutonomyPolicyError,
        match="requires deterministic entity resolution",
    ):
        guard.validate(
            [
                ActionRequest(
                    domain="light",
                    service="turn_off",
                    entity_id="light.example_room",
                )
            ]
        )


def test_failed_direct_action_requests_resolver_retry() -> None:
    trace = [
        ToolAuditRecord(
            sequence=1,
            tool="perform_action",
            arguments={
                "domain": "light",
                "service": "turn_off",
                "entity_id": "light.example_room",
            },
            status="failed",
            outcome="rejected",
            error=(
                "AutonomyPolicyError: Natural-language action requires "
                "deterministic entity resolution before execution"
            ),
        )
    ]

    assert _entity_resolution_requires_retry(trace)


def test_ambiguous_resolution_blocks_action_plan() -> None:
    guard = EntityResolutionGuard()
    guard.record(
        {
            "status": "ambiguous",
            "entity": None,
            "candidates": [
                {"entity_id": "light.example_room"},
                {"entity_id": "switch.example_room"},
            ],
        }
    )

    with pytest.raises(
        AutonomyPolicyError,
        match="did not produce one controllable target",
    ):
        guard.validate(
            [
                ActionRequest(
                    domain="light",
                    service="turn_off",
                    entity_id="light.example_room",
                )
            ]
        )


def test_resolved_entity_cannot_be_substituted() -> None:
    guard = EntityResolutionGuard()
    guard.record(
        {
            "status": "resolved",
            "entity": {"entity_id": "light.example_room"},
        }
    )

    with pytest.raises(
        AutonomyPolicyError,
        match="deterministically resolved entity",
    ):
        guard.validate(
            [
                ActionRequest(
                    domain="light",
                    service="turn_off",
                    entity_id="light.example_other_room",
                )
            ]
        )


def test_resolve_entity_tool_filters_control_targets(
    tmp_path: Path,
) -> None:
    result = asyncio.run(
        _execute_tool(
            "resolve_entity",
            {
                "query": "Example Room",
                "domain": "light",
                "for_control": True,
            },
            StubHomeAssistantClient(),
            MemoryStore(str(tmp_path / "memory.db")),
            autonomy_policy=AutonomyPolicy(
                event_types=frozenset(),
                action_rules=frozenset(),
                included_entities=frozenset({"light.example_room"}),
                simple_entity_policy=True,
            ),
        )
    )

    assert result["status"] == "resolved"
    assert result["entity"]["entity_id"] == "light.example_room"


def test_generic_planner_has_room_for_reasoning_and_final_response() -> None:
    assert MAX_AGENT_ITERATIONS == 10


def test_system_prompt_forbids_unexecuted_action_claims() -> None:
    prompt = " ".join(SYSTEM_PROMPT.split())

    assert "must call perform_action" in prompt
    assert "without the tool result" in prompt
    assert "use azimuth and elevation" in prompt
    assert "not a complete inventory" in prompt
    assert "use resolve_entity" in prompt
    assert "An ambiguous result" in prompt
    assert "OPEN percentage" in prompt
    assert "Never use 100 to lower" in prompt
    assert "Never invent a generic wrapper" in prompt
    assert "ask the user which one" in prompt


def test_resolved_target_preloads_authoritative_service_contract() -> None:
    class ServiceClient:
        async def list_services_for_entity(
            self,
            entity_id: str,
        ) -> list[dict[str, object]]:
            assert entity_id == "alarm_control_panel.example_home"
            return [
                {
                    "domain": "alarm_control_panel",
                    "service": "alarm_arm_night",
                    "fields": {},
                    "device_code_required": False,
                },
                {
                    "domain": "alarm_control_panel",
                    "service": "alarm_arm_away",
                    "fields": {"code": {"required": False}},
                    "device_code_required": True,
                },
            ]

    prompt, loaded = asyncio.run(
        _relevant_service_contract_context(
            ServiceClient(),
            pre_resolution={
                "status": "resolved",
                "entity": {"entity_id": "alarm_control_panel.example_home"},
            },
            explicit_entity_ids=frozenset(),
            controllable_entities=frozenset(
                {"alarm_control_panel.example_home"}
            ),
        )
    )

    assert "alarm_arm_night" in prompt
    assert "alarm_arm_away" in prompt
    assert "supported_features" in prompt
    assert "ask for clarification" in prompt
    assert "targets declare a Home Assistant device code" in prompt
    assert "server injects it after validation" in prompt
    assert loaded == (("alarm_control_panel", 2),)


def test_model_control_markers_are_removed_from_response() -> None:
    assert (
        _clean_model_response("thought\n<channel|>Risposta finale") == "Risposta finale"
    )


def test_simulate_instruction_forbids_claiming_real_changes() -> None:
    instruction = _event_mode_instruction("simulate")

    assert "only as simulations" in instruction
    assert "actually changed" in instruction


def test_tool_audit_keeps_actions_and_redacts_memory_contents() -> None:
    action = _sanitize_tool_arguments(
        "perform_action",
        {
            "domain": "cover",
            "service": "set_cover_position",
            "entity_id": "cover.example_kitchen_shade",
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


def test_event_audit_records_server_enforced_action_mode() -> None:
    requested = {
        "domain": "lock",
        "service": "lock",
        "entity_id": "lock.example_front_door",
        "data": {},
        "dry_run": False,
    }

    simulated = _sanitize_tool_arguments(
        "perform_action",
        requested,
        action_mode="simulate",
    )
    executed = _sanitize_tool_arguments(
        "perform_action",
        {**requested, "dry_run": True},
        action_mode="execute",
    )
    batch = _sanitize_tool_arguments(
        "perform_actions",
        {"actions": [requested, {**requested, "entity_id": "lock.example_back_door"}]},
        action_mode="simulate",
    )

    assert simulated["dry_run"] is True
    assert executed["dry_run"] is False
    assert all(action["dry_run"] is True for action in batch["actions"])
    assert requested["dry_run"] is False


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
    normalized_prompt = " ".join(SYSTEM_PROMPT.split())

    assert "domain, service, entity_id, and dry_run" in normalized_prompt
    assert "no action was simulated or executed" in normalized_prompt
    assert "server authorization policy" in normalized_prompt


def test_batch_audit_reports_simulation_and_unexpected_keys() -> None:
    assert (
        _tool_outcome(
            {
                "status": "completed",
                "actions": [
                    {"status": "simulated"},
                    {"status": "simulated"},
                ],
            }
        )
        == "simulated"
    )
    assert _sanitize_tool_arguments(
        "perform_action",
        {"actions": [], "domain": "cover"},
    ) == {
        "domain": "cover",
        "unexpected_argument_keys": ["actions"],
    }


def test_multi_entity_plan_does_not_require_single_entity_resolution() -> None:
    guard = EntityResolutionGuard(required=True)

    guard.validate(
        [
            ActionRequest(
                domain="light",
                service="turn_off",
                entity_id="light.example_one",
            ),
            ActionRequest(
                domain="light",
                service="turn_off",
                entity_id="light.example_two",
            ),
        ]
    )


def test_single_item_batch_cannot_bypass_entity_resolution() -> None:
    guard = EntityResolutionGuard(required=True)

    with pytest.raises(
        AutonomyPolicyError,
        match="requires deterministic entity resolution",
    ):
        guard.validate(
            [
                ActionRequest(
                    domain="light",
                    service="turn_off",
                    entity_id="light.example_one",
                )
            ]
        )


def test_batch_tool_requires_at_least_two_actions() -> None:
    batch_tool = next(
        tool for tool in TOOLS if tool["function"]["name"] == "perform_actions"
    )

    actions = batch_tool["function"]["parameters"]["properties"]["actions"]
    assert actions["minItems"] == 2
    assert (
        "Use perform_action for a single device"
        in (batch_tool["function"]["description"])
    )


def test_observe_response_requires_successful_state_read() -> None:
    unresolved = [
        ToolAuditRecord(
            sequence=1,
            tool="resolve_entity",
            arguments={"server_side": True},
            status="completed",
            outcome="not_controllable",
        )
    ]
    grounded = [
        ToolAuditRecord(
            sequence=1,
            tool="list_entities",
            arguments={"domains": ["light"]},
            status="completed",
            outcome="completed:1_items",
        )
    ]

    assert _finalize_observe_response(
        "Invented state",
        unresolved,
        "it",
        action_mode="observe",
    ).startswith("Non ho potuto verificare")
    assert _finalize_observe_response(
        "Verified state",
        grounded,
        "it",
        action_mode="observe",
    ) == "Verified state"
    assert _finalize_observe_response(
        "Ordinary chat",
        [],
        "it",
        action_mode=None,
    ) == "Ordinary chat"



def test_agent_inventory_reports_pagination_metadata(tmp_path: Path) -> None:
    class InventoryClient:
        async def list_entities(
            self,
            *,
            domains: set[str],
            limit: int,
        ) -> list[dict[str, object]]:
            assert domains == {"light", "sensor"}
            assert limit == 1_000_000
            return [
                {"entity_id": f"sensor.example_{index}", "state": str(index)}
                for index in range(75)
            ]

    result = asyncio.run(
        _execute_tool(
            "list_entities",
            {
                "domains": ["light", "sensor"],
                "limit": 50,
                "offset": 0,
            },
            InventoryClient(),  # type: ignore[arg-type]
            MemoryStore(str(tmp_path / "memory.db")),
        )
    )

    assert result["returned"] == 50
    assert result["total"] == 75
    assert result["truncated"] is True
    assert result["next_offset"] == 50
    assert len(result["items"]) == 50
    assert _tool_outcome(result) == "truncated:50_of_75_items"


def test_recalled_memory_verifies_referenced_entity_states(tmp_path: Path) -> None:
    class Entity:
        def __init__(self, entity_id: str, state: str) -> None:
            self.entity_id = entity_id
            self.state = state

        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            return {
                "entity_id": self.entity_id,
                "state": self.state,
                "attributes": {},
            }

    class GroundingClient:
        async def get_entity(self, entity_id: str) -> Entity:
            if entity_id == "media_player.example_tv":
                return Entity(entity_id, "on")
            raise HomeAssistantError("Entity is not visible")

    store = MemoryStore(str(tmp_path / "memory.db"))
    store.remember(
        MemoryInput(
            key="viewing.preference",
            value=(
                "When media_player.example_tv is active, keep "
                "cover.example_shade closed."
            ),
            category="preference",
            importance=5,
        )
    )

    result = asyncio.run(
        _execute_tool(
            "recall_memories",
            {"query": "viewing", "limit": 10},
            GroundingClient(),  # type: ignore[arg-type]
            store,
        )
    )

    assert len(result["memories"]) == 1
    assert result["referenced_entities"] == [
        {
            "entity_id": "media_player.example_tv",
            "state": "on",
            "attributes": {},
        }
    ]
    assert result["unverified_references"] == 1
    assert _tool_outcome(result) == (
        "completed:1_items:1_entities_verified:1_unverified"
    )


def test_truncated_inventory_requires_a_focused_follow_up() -> None:
    truncated = ToolAuditRecord(
        sequence=1,
        tool="list_entities",
        arguments={"domains": ["light", "sensor"], "limit": 50, "offset": 0},
        status="completed",
        outcome="truncated:50_of_75_items",
    )
    focused = ToolAuditRecord(
        sequence=2,
        tool="get_entity",
        arguments={"entity_id": "sensor.example_temperature"},
        status="completed",
        outcome="completed",
    )

    assert _incomplete_inventory_requires_retry([truncated]) is True
    assert _incomplete_inventory_requires_retry([truncated, focused]) is False


def test_list_entities_tool_documents_pagination() -> None:
    tool = next(
        item for item in TOOLS if item["function"]["name"] == "list_entities"
    )
    properties = tool["function"]["parameters"]["properties"]

    assert "offset" in properties
    assert "truncated" in tool["function"]["description"]
    assert "Never infer the state" in SYSTEM_PROMPT



def test_observed_entity_allows_single_action_after_broad_resolution() -> None:
    guard = EntityResolutionGuard(required=True)
    guard.record({"status": "not_controllable"})
    guard.observe(
        {
            "items": [
                {
                    "entity_id": "cover.example_shade",
                    "state": "open",
                }
            ]
        }
    )

    guard.validate(
        [
            ActionRequest(
                domain="cover",
                service="close_cover",
                entity_id="cover.example_shade",
            )
        ]
    )

    tools = [
        {"function": {"name": "perform_action"}},
        {"function": {"name": "list_entities"}},
    ]
    assert _tools_for_entity_resolution(tools, guard) == tools


def test_unobserved_single_action_remains_rejected() -> None:
    guard = EntityResolutionGuard(required=True)
    guard.record({"status": "not_controllable"})
    guard.observe(
        {
            "items": [
                {
                    "entity_id": "cover.example_observed",
                    "state": "open",
                }
            ]
        }
    )

    with pytest.raises(AutonomyPolicyError):
        guard.validate(
            [
                ActionRequest(
                    domain="cover",
                    service="close_cover",
                    entity_id="cover.example_unobserved",
                )
            ]
        )


def test_verified_memories_require_one_compliance_review() -> None:
    recall = ToolAuditRecord(
        sequence=1,
        tool="recall_memories",
        arguments={"query_redacted": True, "limit": 10},
        status="completed",
        outcome="completed:2_items:2_entities_verified:0_unverified",
    )
    action = ToolAuditRecord(
        sequence=2,
        tool="perform_action",
        arguments={
            "domain": "cover",
            "service": "close_cover",
            "entity_id": "cover.example_shade",
        },
        status="completed",
        outcome="simulated",
    )

    assert _memory_compliance_review_required([recall]) is True
    assert _memory_compliance_review_required([recall, action]) is False


def test_prompt_prioritizes_verified_preferences() -> None:
    normalized = " ".join(SYSTEM_PROMPT.split())

    assert "Recalled preferences override optional" in normalized
    assert "directly verified referenced entity states" in normalized
