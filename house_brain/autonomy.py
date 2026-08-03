import json
import re
from dataclasses import dataclass, field
from typing import Any

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

    def __post_init__(self) -> None:
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
