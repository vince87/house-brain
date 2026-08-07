import asyncio
from pathlib import Path
from typing import Any

import pytest

from house_brain.actions import ActionPolicyError
from house_brain.agent import TOOLS, _autonomy_policy_instruction, _execute_tool
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
version: 2
entities:
  include:
    - media_player.example_television
    - button.example_trigger
    - lock.example_front_door
    - select.example_mode
  exclude: []
""".lstrip()
    )
    return load_autonomy_policy(path).resolve(
        "periodic_house_check",
        "simulate",
    )


def test_generic_domains_are_exposed_by_action_tools() -> None:
    tools = {item["function"]["name"]: item["function"] for item in TOOLS}
    single = tools["perform_action"]["parameters"]["properties"]
    batch = tools["perform_actions"]["parameters"]["properties"]["actions"][
        "items"
    ]["properties"]

    assert "enum" not in single["domain"]
    assert "enum" not in single["service"]
    assert "enum" not in batch["domain"]
    assert "enum" not in batch["service"]


@pytest.mark.parametrize(
    ("domain", "service", "entity_id"),
    [
        ("media_player", "turn_off", "media_player.example_television"),
        ("button", "press", "button.example_trigger"),
        ("lock", "lock", "lock.example_front_door"),
        ("select", "select_option", "select.example_mode"),
    ],
)
def test_included_entity_can_simulate_coherent_domain_service(
    tmp_path: Path,
    domain: str,
    service: str,
    entity_id: str,
) -> None:
    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
                "data": {"option": "Auto"} if domain == "select" else {},
            },
            StubHomeAssistantClient(),
            MemoryStore(str(tmp_path / "memory.db")),
            action_mode="simulate",
            autonomy_policy=_policy(tmp_path),
        )
    )

    assert result["status"] == "simulated"
    assert result["domain"] == domain


def test_generic_execute_calls_home_assistant(tmp_path: Path) -> None:
    client = StubHomeAssistantClient()
    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "media_player",
                "service": "turn_off",
                "entity_id": "media_player.example_television",
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            action_mode="execute",
            autonomy_policy=_policy(tmp_path),
        )
    )

    assert result["status"] == "executed"
    assert client.calls[0]["service"] == "turn_off"


def test_model_cannot_replace_an_explicit_entity_id(
    tmp_path: Path,
) -> None:
    client = StubHomeAssistantClient()

    with pytest.raises(AutonomyPolicyError, match="target differs"):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "media_player",
                    "service": "turn_off",
                    "entity_id": "media_player.example_television",
                },
                client,
                MemoryStore(str(tmp_path / "memory.db")),
                action_mode="simulate",
                autonomy_policy=_policy(tmp_path),
                explicit_entity_ids=frozenset(
                    {"media_player.example_missing"}
                ),
            )
        )

    assert client.calls == []


def test_generic_action_rejects_unincluded_entity(tmp_path: Path) -> None:
    with pytest.raises(AutonomyPolicyError, match="not included"):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "button",
                    "service": "press",
                    "entity_id": "button.example_not_included",
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
                    "entity_id": "switch.example_relay",
                },
                StubHomeAssistantClient(),
                MemoryStore(str(tmp_path / "memory.db")),
                action_mode="simulate",
                autonomy_policy=_policy(tmp_path),
            )
        )


def test_generic_action_data_must_be_scalar(tmp_path: Path) -> None:
    policy = AutonomyPolicy(
        event_types=frozenset(),
        action_rules=frozenset(),
        included_entities=frozenset({"script.example_action"}),
        simple_entity_policy=True,
    )
    with pytest.raises(ActionPolicyError, match="must be scalar"):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "script",
                    "service": "turn_on",
                    "entity_id": "script.example_action",
                    "data": {"variables": {"unsafe": True}},
                },
                StubHomeAssistantClient(),
                MemoryStore(str(tmp_path / "memory.db")),
                action_mode="simulate",
                autonomy_policy=policy,
            )
        )


def test_policy_prompt_lists_included_entities(tmp_path: Path) -> None:
    prompt = _autonomy_policy_instruction(_policy(tmp_path))

    assert "Entità controllabili" in prompt
    assert "button.example_trigger" in prompt
    assert "select.example_mode" in prompt
    assert "domain=button" not in prompt
