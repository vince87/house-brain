import asyncio
from pathlib import Path
from typing import Any

import pytest

from house_brain.actions import ActionRequest
from house_brain.agent import _execute_tool
from house_brain.autonomy import (
    AutonomyPolicy,
    AutonomyPolicyError,
    load_autonomy_policy,
    parse_action_constraints,
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


def test_parameterized_action_requires_explicit_constraint() -> None:
    rule = "cover.set_cover_position:cover.cucina"
    unconstrained = AutonomyPolicy(
        event_types=frozenset(),
        action_rules=frozenset({rule}),
    )
    constrained = AutonomyPolicy(
        event_types=frozenset(),
        action_rules=frozenset({rule}),
        action_constraints=parse_action_constraints(
            '{"cover.set_cover_position:cover.cucina":'
            '{"position":{"allowed":[0,20,100]}}}'
        ),
    )

    with pytest.raises(
        AutonomyPolicyError,
        match="parameter is not constrained",
    ):
        unconstrained.validate_action(
            ActionRequest(
                domain="cover",
                service="set_cover_position",
                entity_id="cover.cucina",
                data={"position": 0},
            )
        )

    constrained.validate_action(
        ActionRequest(
            domain="cover",
            service="set_cover_position",
            entity_id="cover.cucina",
            data={"position": 20},
        )
    )
    with pytest.raises(
        AutonomyPolicyError,
        match="parameter value is not allowed",
    ):
        constrained.validate_action(
            ActionRequest(
                domain="cover",
                service="set_cover_position",
                entity_id="cover.cucina",
                data={"position": 50},
            )
        )


def test_numeric_parameter_range_is_enforced() -> None:
    rule = "climate.set_temperature:climate.sala"
    policy = AutonomyPolicy(
        event_types=frozenset(),
        action_rules=frozenset({rule}),
        action_constraints=parse_action_constraints(
            '{"climate.set_temperature:climate.sala":'
            '{"temperature":{"min":18,"max":26}}}'
        ),
    )

    policy.validate_action(
        ActionRequest(
            domain="climate",
            service="set_temperature",
            entity_id="climate.sala",
            data={"temperature": 24},
        )
    )
    with pytest.raises(AutonomyPolicyError, match="above maximum"):
        policy.validate_action(
            ActionRequest(
                domain="climate",
                service="set_temperature",
                entity_id="climate.sala",
                data={"temperature": 27},
            )
        )


def test_toggle_is_never_allowed_for_autonomous_actions() -> None:
    policy = AutonomyPolicy(
        event_types=frozenset(),
        action_rules=frozenset({"switch.toggle:switch.ventola"}),
    )

    with pytest.raises(AutonomyPolicyError, match="toggle is not allowed"):
        policy.validate_action(
            ActionRequest(
                domain="switch",
                service="toggle",
                entity_id="switch.ventola",
            )
        )


def test_constraints_require_valid_json_and_allowlisted_rule() -> None:
    with pytest.raises(AutonomyPolicyError, match="valid JSON"):
        parse_action_constraints("{invalid")

    constraints = parse_action_constraints(
        '{"cover.set_cover_position:cover.cucina":'
        '{"position":{"allowed":[0]}}}'
    )
    with pytest.raises(
        AutonomyPolicyError,
        match="no matching action allowlist",
    ):
        AutonomyPolicy(
            event_types=frozenset(),
            action_rules=frozenset(),
            action_constraints=constraints,
        )


def test_parameter_rejection_keeps_batch_atomic(tmp_path: Path) -> None:
    client = StubHomeAssistantClient()
    memory = MemoryStore(str(tmp_path / "memory.db"))
    policy = AutonomyPolicy(
        event_types=frozenset({"sun_context_changed"}),
        action_rules=frozenset(
            {
                "cover.close_cover:cover.sala",
                "cover.set_cover_position:cover.cucina",
            }
        ),
        action_constraints=parse_action_constraints(
            '{"cover.set_cover_position:cover.cucina":'
            '{"position":{"allowed":[0,20,100]}}}'
        ),
    )

    with pytest.raises(
        AutonomyPolicyError,
        match="parameter value is not allowed",
    ):
        asyncio.run(
            _execute_tool(
                "perform_actions",
                {
                    "actions": [
                        {
                            "domain": "cover",
                            "service": "close_cover",
                            "entity_id": "cover.sala",
                        },
                        {
                            "domain": "cover",
                            "service": "set_cover_position",
                            "entity_id": "cover.cucina",
                            "data": {"position": 50},
                        },
                    ]
                },
                client,
                memory,
                action_mode="execute",
                autonomy_policy=policy,
            )
        )

    assert client.calls == []


def test_execute_event_requires_dedicated_allowlist() -> None:
    policy = AutonomyPolicy(
        event_types=frozenset({"sun_context_changed", "canary_light_control"}),
        execute_event_types=frozenset({"canary_light_control"}),
        action_rules=frozenset(),
    )

    policy.validate_event("sun_context_changed")
    policy.validate_event("canary_light_control")
    policy.validate_execute_event("canary_light_control")

    with pytest.raises(
        AutonomyPolicyError,
        match="Autonomous execute event is not allowlisted",
    ):
        policy.validate_execute_event("sun_context_changed")


def test_execute_event_allowlist_cannot_reference_orphan_event() -> None:
    with pytest.raises(
        AutonomyPolicyError,
        match="has no matching autonomous event",
    ):
        AutonomyPolicy(
            event_types=frozenset({"sun_context_changed"}),
            execute_event_types=frozenset({"canary_light_control"}),
            action_rules=frozenset(),
        )


def test_yaml_policy_groups_modes_actions_constraints_and_budget(
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "autonomy.yaml"
    policy_path.write_text(
        """
version: 1
events:
  sun_context_changed:
    modes: [observe, simulate, execute]
    max_actions: 2
    actions:
      cover.set_cover_position:
        entities:
          - cover.cucina
        parameters:
          position:
            allowed: [0, 20, 100]
""".lstrip()
    )

    catalog = load_autonomy_policy(policy_path)
    policy = catalog.resolve("sun_context_changed", "execute")

    assert policy.max_actions == 2
    assert policy.action_rules == frozenset(
        {"cover.set_cover_position:cover.cucina"}
    )
    assert policy.action_constraints[
        "cover.set_cover_position:cover.cucina"
    ]["position"].allowed == (0, 20, 100)


def test_yaml_policy_denies_undeclared_mode(tmp_path: Path) -> None:
    policy_path = tmp_path / "autonomy.yaml"
    policy_path.write_text(
        """
version: 1
events:
  sun_context_changed:
    modes: [observe, simulate]
    max_actions: 1
    actions: {}
""".lstrip()
    )
    catalog = load_autonomy_policy(policy_path)

    with pytest.raises(
        AutonomyPolicyError,
        match="event mode is not allowed",
    ):
        catalog.resolve("sun_context_changed", "execute")


@pytest.mark.parametrize(
    "content, match",
    [
        ("version: 2\nevents: {}\n", "version must be 1"),
        (
            "version: 1\nevents: {}\nevents: {}\n",
            "Duplicate autonomy policy key",
        ),
        (
            "version: 1\nevents:\n  invalid event:\n"
            "    modes: [simulate]\n    actions: {}\n",
            "Invalid autonomous event policy entry",
        ),
        (
            "version: 1\nevents:\n  valid:\n"
            "    modes: [simulate]\n    unknown: true\n",
            "Unexpected autonomy policy keys",
        ),
        (
            "version: 1\nevents:\n  valid:\n"
            "    modes: [execute]\n    max_actions: 21\n"
            "    actions: {}\n",
            "max_actions must be between 1 and 20",
        ),
    ],
)
def test_yaml_policy_rejects_invalid_configuration(
    tmp_path: Path,
    content: str,
    match: str,
) -> None:
    policy_path = tmp_path / "autonomy.yaml"
    policy_path.write_text(content)

    with pytest.raises(AutonomyPolicyError, match=match):
        load_autonomy_policy(policy_path)
