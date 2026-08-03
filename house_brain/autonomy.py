import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from house_brain.actions import ActionRequest

EVENT_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
PARAMETER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
CONSTRAINT_KEYS = frozenset({"allowed", "min", "max"})


class AutonomyPolicyError(ValueError):
    """Raised when an autonomous event or action is not explicitly allowed."""


@dataclass(frozen=True)
class ParameterConstraint:
    allowed: tuple[str | int | float | bool, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None

    def validate(self, name: str, value: Any) -> None:
        if self.allowed is not None and not any(
            _same_value(value, candidate)
            for candidate in self.allowed
        ):
            raise AutonomyPolicyError(
                f"Autonomous parameter value is not allowed: {name}={value}; "
                f"allowed={list(self.allowed)}"
            )
        if self.minimum is not None or self.maximum is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise AutonomyPolicyError(
                    f"Autonomous parameter must be numeric: {name}"
                )
            if self.minimum is not None and value < self.minimum:
                raise AutonomyPolicyError(
                    f"Autonomous parameter is below minimum: {name}<{self.minimum:g}"
                )
            if self.maximum is not None and value > self.maximum:
                raise AutonomyPolicyError(
                    f"Autonomous parameter is above maximum: {name}>{self.maximum:g}"
                )


ActionConstraints = dict[str, dict[str, ParameterConstraint]]


@dataclass(frozen=True)
class AutonomyPolicy:
    event_types: frozenset[str]
    action_rules: frozenset[str]
    action_constraints: ActionConstraints = field(default_factory=dict)
    execute_event_types: frozenset[str] = frozenset()
    max_actions: int = 1

    def __post_init__(self) -> None:
        if not 1 <= self.max_actions <= 20:
            raise AutonomyPolicyError(
                "Autonomous max_actions must be between 1 and 20"
            )
        for event_type in self.event_types | self.execute_event_types:
            if not EVENT_TYPE_PATTERN.fullmatch(event_type):
                raise AutonomyPolicyError(
                    f"Invalid autonomous event allowlist entry: {event_type}"
                )
        orphan_execute_events = self.execute_event_types - self.event_types
        if orphan_execute_events:
            raise AutonomyPolicyError(
                "Execute event allowlist has no matching autonomous event: "
                f"{sorted(orphan_execute_events)}"
            )
        for rule in self.action_rules:
            _parse_action_rule(rule)
        for rule in self.action_constraints:
            _parse_action_rule(rule)
            if rule not in self.action_rules:
                raise AutonomyPolicyError(
                    "Autonomous parameter constraint has no matching "
                    f"action allowlist entry: {rule}"
                )

    def validate_event(self, event_type: str) -> None:
        if event_type not in self.event_types:
            raise AutonomyPolicyError(
                f"Autonomous event is not allowlisted: {event_type}"
            )

    def validate_execute_event(self, event_type: str) -> None:
        if event_type not in self.execute_event_types:
            raise AutonomyPolicyError(
                f"Autonomous execute event is not allowlisted: {event_type}"
            )

    def validate_action(self, action: ActionRequest) -> None:
        rule = action_rule(action)
        if rule not in self.action_rules:
            raise AutonomyPolicyError(
                f"Autonomous action is not allowlisted: {rule}"
            )
        if action.service == "toggle":
            raise AutonomyPolicyError(
                "toggle is not allowed for autonomous actions"
            )

        constraints = self.action_constraints.get(rule, {})
        for name, value in action.data.items():
            constraint = constraints.get(name)
            if constraint is None:
                raise AutonomyPolicyError(
                    "Autonomous action parameter is not constrained: "
                    f"{rule}[{name}]"
                )
            constraint.validate(name, value)


def parse_allowlist(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    )


def parse_action_constraints(value: str | None) -> ActionConstraints:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise AutonomyPolicyError(
            "AUTONOMOUS_ACTION_CONSTRAINTS must be valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise AutonomyPolicyError(
            "AUTONOMOUS_ACTION_CONSTRAINTS must be a JSON object"
        )

    parsed: ActionConstraints = {}
    for raw_rule, raw_parameters in payload.items():
        rule = str(raw_rule).strip().lower()
        _parse_action_rule(rule)
        if not isinstance(raw_parameters, dict) or not raw_parameters:
            raise AutonomyPolicyError(
                f"Action constraints must be a non-empty object: {rule}"
            )
        parsed[rule] = {
            str(name).strip().lower(): _parse_parameter_constraint(
                rule,
                str(name).strip().lower(),
                definition,
            )
            for name, definition in raw_parameters.items()
        }
    return parsed


def action_rule(action: ActionRequest) -> str:
    return f"{action.domain}.{action.service}:{action.entity_id}"


def _parse_parameter_constraint(
    rule: str,
    name: str,
    definition: Any,
) -> ParameterConstraint:
    if not PARAMETER_PATTERN.fullmatch(name):
        raise AutonomyPolicyError(
            f"Invalid autonomous parameter name: {rule}[{name}]"
        )
    if not isinstance(definition, dict) or not definition:
        raise AutonomyPolicyError(
            f"Invalid autonomous parameter constraint: {rule}[{name}]"
        )
    unexpected = set(definition) - CONSTRAINT_KEYS
    if unexpected:
        raise AutonomyPolicyError(
            f"Unexpected autonomous constraint keys: {rule}[{name}]"
        )

    raw_allowed = definition.get("allowed")
    allowed: tuple[str | int | float | bool, ...] | None = None
    if raw_allowed is not None:
        if not isinstance(raw_allowed, list) or not raw_allowed:
            raise AutonomyPolicyError(
                f"allowed must be a non-empty list: {rule}[{name}]"
            )
        if any(
            isinstance(item, (dict, list)) or item is None
            for item in raw_allowed
        ):
            raise AutonomyPolicyError(
                f"allowed contains an invalid value: {rule}[{name}]"
            )
        allowed = tuple(raw_allowed)

    minimum = _optional_number(definition.get("min"), rule, name, "min")
    maximum = _optional_number(definition.get("max"), rule, name, "max")
    if allowed is None and minimum is None and maximum is None:
        raise AutonomyPolicyError(
            f"Constraint must define allowed, min, or max: {rule}[{name}]"
        )
    if (
        minimum is not None
        and maximum is not None
        and minimum > maximum
    ):
        raise AutonomyPolicyError(
            f"Constraint minimum exceeds maximum: {rule}[{name}]"
        )
    return ParameterConstraint(
        allowed=allowed,
        minimum=minimum,
        maximum=maximum,
    )


def _optional_number(
    value: Any,
    rule: str,
    name: str,
    label: str,
) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AutonomyPolicyError(
            f"{label} must be numeric: {rule}[{name}]"
        )
    return float(value)


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    return type(left) is type(right) and left == right


def _parse_action_rule(rule: str) -> tuple[str, str, str]:
    service_name, separator, entity_id = rule.partition(":")
    domain, dot, service = service_name.partition(".")
    entity_domain, entity_dot, entity_name = entity_id.partition(".")
    if (
        not separator
        or not dot
        or not entity_dot
        or not domain
        or not service
        or not entity_name
        or entity_domain != domain
        or "*" in rule
    ):
        raise AutonomyPolicyError(
            f"Invalid autonomous action allowlist entry: {rule}"
        )
    return domain, service, entity_id


@dataclass(frozen=True)
class AutonomyPolicyCatalog:
    """Validated autonomous policies indexed by exact event type."""

    events: dict[str, dict[str, Any]]

    @classmethod
    def empty(cls) -> "AutonomyPolicyCatalog":
        return cls(events={})

    def resolve(self, event_type: str, mode: str) -> AutonomyPolicy:
        definition = self.events.get(event_type)
        if definition is None:
            raise AutonomyPolicyError(
                f"Autonomous event is not allowlisted: {event_type}"
            )
        modes = definition["modes"]
        if mode not in modes:
            raise AutonomyPolicyError(
                "Autonomous event mode is not allowed: "
                f"event_type={event_type}; mode={mode}"
            )
        return AutonomyPolicy(
            event_types=frozenset({event_type}),
            execute_event_types=(
                frozenset({event_type})
                if "execute" in modes
                else frozenset()
            ),
            action_rules=definition["action_rules"],
            action_constraints=definition["action_constraints"],
            max_actions=definition["max_actions"],
        )


def load_autonomy_policy(path: str | Path) -> AutonomyPolicyCatalog:
    """Load and strictly validate one YAML autonomy policy file."""
    policy_path = Path(path)
    try:
        raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AutonomyPolicyError(
            f"Cannot read autonomy policy: {policy_path}"
        ) from exc
    except yaml.YAMLError as exc:
        raise AutonomyPolicyError(
            f"Invalid autonomy policy YAML: {policy_path}"
        ) from exc

    if not isinstance(raw, dict):
        raise AutonomyPolicyError("Autonomy policy must be a YAML object")
    _require_keys(raw, {"version", "events"}, "policy")
    if raw.get("version") != 1:
        raise AutonomyPolicyError("Autonomy policy version must be 1")
    raw_events = raw.get("events")
    if not isinstance(raw_events, dict):
        raise AutonomyPolicyError("Autonomy policy events must be an object")

    events: dict[str, dict[str, Any]] = {}
    for raw_event_type, raw_event in raw_events.items():
        event_type = str(raw_event_type).strip().lower()
        if not EVENT_TYPE_PATTERN.fullmatch(event_type):
            raise AutonomyPolicyError(
                f"Invalid autonomous event policy entry: {event_type}"
            )
        events[event_type] = _parse_event_policy(event_type, raw_event)
    return AutonomyPolicyCatalog(events=events)


def _parse_event_policy(
    event_type: str,
    raw_event: Any,
) -> dict[str, Any]:
    if not isinstance(raw_event, dict):
        raise AutonomyPolicyError(
            f"Autonomous event policy must be an object: {event_type}"
        )
    _require_keys(
        raw_event,
        {"modes", "max_actions", "actions"},
        f"event {event_type}",
    )
    raw_modes = raw_event.get("modes")
    if not isinstance(raw_modes, list) or not raw_modes:
        raise AutonomyPolicyError(
            f"Autonomous event modes must be a non-empty list: {event_type}"
        )
    modes = frozenset(str(mode).strip().lower() for mode in raw_modes)
    invalid_modes = modes - {"observe", "simulate", "execute"}
    if invalid_modes:
        raise AutonomyPolicyError(
            f"Invalid autonomous event modes: {sorted(invalid_modes)}"
        )

    max_actions = raw_event.get("max_actions", 1)
    if (
        isinstance(max_actions, bool)
        or not isinstance(max_actions, int)
        or not 1 <= max_actions <= 20
    ):
        raise AutonomyPolicyError(
            f"Autonomous max_actions must be between 1 and 20: {event_type}"
        )

    raw_actions = raw_event.get("actions", {})
    if not isinstance(raw_actions, dict):
        raise AutonomyPolicyError(
            f"Autonomous actions must be an object: {event_type}"
        )
    action_rules: set[str] = set()
    action_constraints: ActionConstraints = {}
    for raw_service, raw_action in raw_actions.items():
        service_name = str(raw_service).strip().lower()
        if not isinstance(raw_action, dict):
            raise AutonomyPolicyError(
                f"Autonomous action policy must be an object: {service_name}"
            )
        _require_keys(
            raw_action,
            {"entities", "parameters"},
            f"action {service_name}",
        )
        entities = raw_action.get("entities")
        if not isinstance(entities, list) or not entities:
            raise AutonomyPolicyError(
                f"Autonomous action entities must be a non-empty list: "
                f"{service_name}"
            )
        parameters = raw_action.get("parameters", {})
        if not isinstance(parameters, dict):
            raise AutonomyPolicyError(
                f"Autonomous action parameters must be an object: "
                f"{service_name}"
            )
        for raw_entity_id in entities:
            entity_id = str(raw_entity_id).strip().lower()
            rule = f"{service_name}:{entity_id}"
            _parse_action_rule(rule)
            action_rules.add(rule)
            if parameters:
                action_constraints[rule] = {
                    str(name).strip().lower(): _parse_parameter_constraint(
                        rule,
                        str(name).strip().lower(),
                        definition,
                    )
                    for name, definition in parameters.items()
                }

    return {
        "modes": modes,
        "max_actions": max_actions,
        "action_rules": frozenset(action_rules),
        "action_constraints": action_constraints,
    }


def _require_keys(
    value: dict[Any, Any],
    allowed: set[str],
    location: str,
) -> None:
    unexpected = set(value) - allowed
    if unexpected:
        raise AutonomyPolicyError(
            f"Unexpected autonomy policy keys in {location}: "
            f"{sorted(unexpected)}"
        )
