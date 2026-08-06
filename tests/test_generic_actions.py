import asyncio
from pathlib import Path
from typing import Any

import pytest

from house_brain.actions import ActionPolicyError, ActionRequest, validate_action
from house_brain.agent import (
    TOOLS,
    _autonomy_policy_instruction,
    _execute_tool,
)
from house_brain.autonomy import (
    AutonomyPolicy,
    AutonomyPolicyError,
    load_autonomy_policy,
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


def _policy(tmp_path: Path) -> AutonomyPolicy:
    path = tmp_path / "autonomy.yaml"
    path.write_text(
        """
version: 1
events:
  periodic_house_check:
    modes: [simulate, execute]
    max_actions: 10
    actions:
      media_player.turn_off:
        entities: [media_player.televisore_sala]
      button.press:
        entities: [button.qualcosa]
      lock.lock:
        entities: [lock.ingresso]
      select.select_option:
        entities: [select.modalita]
        parameters:
          option:
            allowed: [Auto, Manuale]
""".lstrip()
    )
    return load_autonomy_policy(path).resolve(
        "periodic_house_check",
        "simulate",
    )


def test_generic_domains_are_exposed_by_action_tools() -> None:
    tools = {
        item["function"]["name"]: item["function"]
        for item in TOOLS
    }
    single = tools["perform_action"]["parameters"]["properties"]
    batch = tools["perform_actions"]["parameters"]["properties"][
        "actions"
    ]["items"]["properties"]

    assert "enum" not in single["domain"]
    assert "enum" not in single["service"]
    assert "enum" not in batch["domain"]
    assert "enum" not in batch["service"]


@pytest.mark.parametrize(
    ("domain", "service", "entity_id"),
    [
        ("media_player", "turn_off", "media_player.televisore_sala"),
        ("button", "press", "button.qualcosa"),
        ("lock", "lock", "lock.ingresso"),
    ],
)
def test_explicit_policy_can_simulate_any_domain(
    tmp_path: Path,
    domain: str,
    service: str,
    entity_id: str,
) -> None:
    client = StubHomeAssistantClient()
    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            action_mode="simulate",
            autonomy_policy=_policy(tmp_path),
        )
    )

    assert result["status"] == "simulated"
    assert result["domain"] == domain
    assert client.calls == []


def test_generic_execute_calls_home_assistant(tmp_path: Path) -> None:
    client = StubHomeAssistantClient()
    policy = _policy(tmp_path)

    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "media_player",
                "service": "turn_off",
                "entity_id": "media_player.televisore_sala",
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            action_mode="execute",
            autonomy_policy=policy,
        )
    )

    assert result["status"] == "executed"
    assert client.calls == [
        {
            "domain": "media_player",
            "service": "turn_off",
            "entity_id": "media_player.televisore_sala",
            "data": {},
        }
    ]


def test_generic_parameter_constraints_are_enforced(tmp_path: Path) -> None:
    client = StubHomeAssistantClient()
    policy = _policy(tmp_path)
    memory = MemoryStore(str(tmp_path / "memory.db"))

    allowed = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "select",
                "service": "select_option",
                "entity_id": "select.modalita",
                "data": {"option": "Auto"},
            },
            client,
            memory,
            action_mode="simulate",
            autonomy_policy=policy,
        )
    )
    assert allowed["status"] == "simulated"

    with pytest.raises(AutonomyPolicyError, match="value is not allowed"):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "select",
                    "service": "select_option",
                    "entity_id": "select.modalita",
                    "data": {"option": "Notte"},
                },
                client,
                memory,
                action_mode="simulate",
                autonomy_policy=policy,
            )
        )


def test_generic_action_rejects_undeclared_service(tmp_path: Path) -> None:
    with pytest.raises(AutonomyPolicyError, match="not allowlisted"):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "button",
                    "service": "press",
                    "entity_id": "button.non_autorizzato",
                },
                StubHomeAssistantClient(),
                MemoryStore(str(tmp_path / "memory.db")),
                action_mode="simulate",
                autonomy_policy=_policy(tmp_path),
            )
        )


def test_generic_action_rejects_cross_domain_entity(tmp_path: Path) -> None:
    with pytest.raises(ActionPolicyError, match="domain must match"):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "button",
                    "service": "press",
                    "entity_id": "switch.qualcosa",
                },
                StubHomeAssistantClient(),
                MemoryStore(str(tmp_path / "memory.db")),
                action_mode="simulate",
                autonomy_policy=_policy(tmp_path),
            )
        )


def test_generic_action_data_must_be_scalar(tmp_path: Path) -> None:
    policy = AutonomyPolicy(
        event_types=frozenset({"test"}),
        action_rules=frozenset({"script.turn_on:script.prova"}),
    )
    with pytest.raises(ActionPolicyError, match="must be scalar"):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "script",
                    "service": "turn_on",
                    "entity_id": "script.prova",
                    "data": {"variables": {"unsafe": True}},
                },
                StubHomeAssistantClient(),
                MemoryStore(str(tmp_path / "memory.db")),
                action_mode="simulate",
                autonomy_policy=policy,
            )
        )


def test_direct_actions_keep_the_legacy_safety_boundary() -> None:
    with pytest.raises(ActionPolicyError, match="currently blocked"):
        validate_action(
            ActionRequest(
                domain="lock",
                service="lock",
                entity_id="lock.ingresso",
            )
        )


def test_event_prompt_lists_exact_policy_rules(tmp_path: Path) -> None:
    prompt = _autonomy_policy_instruction(_policy(tmp_path))

    assert "button.press -> button.qualcosa; senza parametri" in prompt
    assert "select.select_option -> select.modalita; parametri: option" in prompt
