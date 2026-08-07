import hmac
import json
import re
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import yaml

from house_brain.actions import ActionRequest

EVENT_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
PARAMETER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ACTION_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_]+$")
ENTITY_ID_PATTERN = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
AUTHORIZATION_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
CONSTRAINT_KEYS = frozenset({"allowed", "min", "max"})
SENSITIVE_ACTIONS = frozenset({
    ("lock", "unlock"),
    ("lock", "open"),
    ("alarm_control_panel", "alarm_disarm"),
    ("siren", "turn_on"),
})


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise AutonomyPolicyError(
                "Autonomy policy mapping keys must be scalar"
            ) from exc
        if duplicate:
            raise AutonomyPolicyError(
                f"Duplicate autonomy policy key: {key}"
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


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
ActionCodes = dict[str, str]


@dataclass(frozen=True)
class VisibilityPolicy:
    """Deny-list controlling which Home Assistant entities may be observed."""

    exclude_entities: frozenset[str] = frozenset()
    exclude_patterns: tuple[str, ...] = ()

    def is_hidden(self, entity_id: str) -> bool:
        normalized = entity_id.strip().lower()
        return normalized in self.exclude_entities or any(
            fnmatchcase(normalized, pattern)
            for pattern in self.exclude_patterns
        )


@dataclass(frozen=True)
class AutonomyPolicy:
    event_types: frozenset[str]
    action_rules: frozenset[str]
    action_constraints: ActionConstraints = field(default_factory=dict)
    action_codes: ActionCodes = field(default_factory=dict, repr=False)
    execute_event_types: frozenset[str] = frozenset()
    allowed_modes: frozenset[str] = frozenset(
        {"observe", "simulate", "execute"}
    )
    max_actions: int = 10
    included_entities: frozenset[str] = frozenset()
    entity_codes: dict[str, str] = field(default_factory=dict, repr=False)
    simple_entity_policy: bool = False

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
        invalid_modes = self.allowed_modes - {
            "observe",
            "simulate",
            "execute",
        }
        if invalid_modes:
            raise AutonomyPolicyError(
                f"Invalid autonomous policy modes: {sorted(invalid_modes)}"
            )
        for rule in self.action_constraints:
            _parse_action_rule(rule)
            if rule not in self.action_rules:
                raise AutonomyPolicyError(
                    "Autonomous parameter constraint has no matching "
                    f"action allowlist entry: {rule}"
                )
        for rule in self.action_codes:
            _parse_action_rule(rule)
            if rule not in self.action_rules:
                raise AutonomyPolicyError(
                    "Autonomous authorization code has no matching "
                    f"action allowlist entry: {rule}"
                )
        for entity_id in self.included_entities:
            if not ENTITY_ID_PATTERN.fullmatch(entity_id):
                raise AutonomyPolicyError(
                    f"Invalid included entity_id: {entity_id}"
                )
        for entity_id, code in self.entity_codes.items():
            if entity_id not in self.included_entities:
                raise AutonomyPolicyError(
                    f"Authorization code entity is not included: {entity_id}"
                )
            if not AUTHORIZATION_CODE_PATTERN.fullmatch(code):
                raise AutonomyPolicyError(
                    f"Invalid authorization code for entity: {entity_id}"
                )

    def validate_event(self, event_type: str) -> None:
        if not EVENT_TYPE_PATTERN.fullmatch(event_type):
            raise AutonomyPolicyError(f"Invalid autonomous event type: {event_type}")
        if not self.simple_entity_policy and event_type not in self.event_types:
            raise AutonomyPolicyError(
                f"Autonomous event is not allowlisted: {event_type}"
            )

    def validate_execute_event(self, event_type: str) -> None:
        if self.simple_entity_policy:
            self.validate_event(event_type)
            return
        if event_type not in self.execute_event_types:
            raise AutonomyPolicyError(
                f"Autonomous execute event is not allowlisted: {event_type}"
            )

    def validate_mode(self, mode: str) -> None:
        if mode not in self.allowed_modes:
            raise AutonomyPolicyError(
                f"Autonomous action mode is not allowed: {mode}"
            )

    def validate_action(
        self,
        action: ActionRequest,
        *,
        authorization_codes: tuple[str, ...] = (),
    ) -> None:
        if self.simple_entity_policy:
            if action.entity_id not in self.included_entities:
                raise AutonomyPolicyError(
                    f"Entity is not included for control: {action.entity_id}"
                )
            required_code = self.entity_codes.get(action.entity_id)
            if (action.domain, action.service) in SENSITIVE_ACTIONS and required_code is None:
                raise AutonomyPolicyError(
                    "Sensitive action requires an authorization code configured for the entity"
                )
            if required_code is not None and not any(
                hmac.compare_digest(required_code, supplied_code)
                for supplied_code in authorization_codes
            ):
                raise AutonomyPolicyError(
                    "Autonomous action requires a valid authorization code"
                )
            return

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

        required_code = self.action_codes.get(rule)
        if required_code is not None and not any(
            hmac.compare_digest(required_code, supplied_code)
            for supplied_code in authorization_codes
        ):
            raise AutonomyPolicyError(
                "Autonomous action requires a valid authorization code"
            )


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
        or not ACTION_IDENTIFIER_PATTERN.fullmatch(domain)
        or not ACTION_IDENTIFIER_PATTERN.fullmatch(service)
        or not entity_name
        or not ENTITY_ID_PATTERN.fullmatch(entity_id)
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

    events: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    visibility: VisibilityPolicy = field(default_factory=VisibilityPolicy)
    included_entities: frozenset[str] = frozenset()
    entity_codes: dict[str, str] = field(default_factory=dict, repr=False)
    simple_entity_policy: bool = False

    @classmethod
    def empty(cls) -> "AutonomyPolicyCatalog":
        return cls(events={}, visibility=VisibilityPolicy(), simple_entity_policy=True)

    def resolve(self, event_type: str, mode: str) -> AutonomyPolicy:
        if self.simple_entity_policy:
            if not EVENT_TYPE_PATTERN.fullmatch(event_type):
                raise AutonomyPolicyError(f"Invalid autonomous event type: {event_type}")
            if mode not in {"observe", "simulate", "execute"}:
                raise AutonomyPolicyError(f"Invalid autonomous action mode: {mode}")
            return AutonomyPolicy(
                event_types=frozenset(),
                action_rules=frozenset(),
                included_entities=self.included_entities,
                entity_codes=self.entity_codes,
                simple_entity_policy=True,
                max_actions=10,
            )
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
            action_codes=definition["action_codes"],
            allowed_modes=modes,
            max_actions=definition["max_actions"],
        )

    def resolve_chat(self) -> AutonomyPolicy | None:
        if self.simple_entity_policy:
            return AutonomyPolicy(
                event_types=frozenset(),
                action_rules=frozenset(),
                included_entities=self.included_entities,
                entity_codes=self.entity_codes,
                simple_entity_policy=True,
                max_actions=10,
            )
        definition = self.events.get("chat_command")
        if definition is None:
            return None
        modes = definition["modes"]
        return AutonomyPolicy(
            event_types=frozenset({"chat_command"}),
            execute_event_types=(
                frozenset({"chat_command"})
                if "execute" in modes
                else frozenset()
            ),
            action_rules=definition["action_rules"],
            action_constraints=definition["action_constraints"],
            action_codes=definition["action_codes"],
            allowed_modes=modes,
            max_actions=definition["max_actions"],
        )


def load_autonomy_policy(path: str | Path) -> AutonomyPolicyCatalog:
    """Load the simple entity policy shared by every action channel."""
    policy_path = Path(path)
    try:
        raw = yaml.load(
            policy_path.read_text(encoding="utf-8"),
            Loader=_UniqueKeyLoader,
        )
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
    _require_keys(raw, {"version", "entities"}, "policy")
    if raw.get("version") != 2:
        raise AutonomyPolicyError(
            "Autonomy policy version must be 2; migrate to entities.include/exclude"
        )
    raw_entities = raw.get("entities")
    if not isinstance(raw_entities, dict):
        raise AutonomyPolicyError("Autonomy policy entities must be an object")
    _require_keys(raw_entities, {"include", "exclude"}, "entities")

    included, codes = _parse_included_entities(raw_entities.get("include", []))
    visibility = _parse_excluded_entities(raw_entities.get("exclude", []))
    conflicts = sorted(entity for entity in included if visibility.is_hidden(entity))
    if conflicts:
        raise AutonomyPolicyError(
            f"Entities cannot be both included and excluded: {conflicts}"
        )
    return AutonomyPolicyCatalog(
        visibility=visibility,
        included_entities=included,
        entity_codes=codes,
        simple_entity_policy=True,
    )


def _parse_included_entities(raw_include: Any) -> tuple[frozenset[str], dict[str, str]]:
    if not isinstance(raw_include, list):
        raise AutonomyPolicyError("entities.include must be a list")
    included: set[str] = set()
    codes: dict[str, str] = {}
    for item in raw_include:
        if isinstance(item, str):
            entity_id = item.strip().lower()
            code = None
        elif isinstance(item, dict):
            _require_keys(item, {"entity_id", "code"}, "entities.include item")
            entity_id = str(item.get("entity_id", "")).strip().lower()
            raw_code = item.get("code")
            code = str(raw_code).strip() if raw_code is not None else None
        else:
            raise AutonomyPolicyError(
                "entities.include items must be entity IDs or objects"
            )
        if not ENTITY_ID_PATTERN.fullmatch(entity_id):
            raise AutonomyPolicyError(f"Invalid included entity_id: {entity_id}")
        if entity_id in included:
            raise AutonomyPolicyError(f"Duplicate included entity_id: {entity_id}")
        if code is not None and not AUTHORIZATION_CODE_PATTERN.fullmatch(code):
            raise AutonomyPolicyError(
                f"Invalid authorization code for entity: {entity_id}"
            )
        included.add(entity_id)
        if code is not None:
            codes[entity_id] = code
    return frozenset(included), codes


def _parse_excluded_entities(raw_exclude: Any) -> VisibilityPolicy:
    if not isinstance(raw_exclude, list):
        raise AutonomyPolicyError("entities.exclude must be a list")
    exact: set[str] = set()
    patterns: list[str] = []
    for item in raw_exclude:
        value = str(item).strip().lower()
        if any(character in value for character in "*?[]"):
            if (
                not value
                or "." not in value
                or any(character.isspace() for character in value)
                or not set(value) <= set(
                    "abcdefghijklmnopqrstuvwxyz0123456789_.*?[]!-"
                )
            ):
                raise AutonomyPolicyError(f"Invalid excluded entity pattern: {value}")
            patterns.append(value)
        elif not ENTITY_ID_PATTERN.fullmatch(value):
            raise AutonomyPolicyError(f"Invalid excluded entity_id: {value}")
        else:
            exact.add(value)
    return VisibilityPolicy(
        exclude_entities=frozenset(exact),
        exclude_patterns=tuple(dict.fromkeys(patterns)),
    )

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
    action_codes: ActionCodes = {}
    for raw_service, raw_action in raw_actions.items():
        service_name = str(raw_service).strip().lower()
        if not isinstance(raw_action, dict):
            raise AutonomyPolicyError(
                f"Autonomous action policy must be an object: {service_name}"
            )
        _require_keys(
            raw_action,
            {"entities", "parameters", "authorization"},
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
        normalized_entities = [
            str(raw_entity_id).strip().lower()
            for raw_entity_id in entities
        ]
        codes = _parse_action_authorization(
            service_name,
            normalized_entities,
            raw_action.get("authorization", {}),
        )
        for entity_id in normalized_entities:
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
            if entity_id in codes:
                action_codes[rule] = codes[entity_id]

    return {
        "modes": modes,
        "max_actions": max_actions,
        "action_rules": frozenset(action_rules),
        "action_constraints": action_constraints,
        "action_codes": action_codes,
    }


def _parse_action_authorization(
    service_name: str,
    entities: list[str],
    raw_authorization: Any,
) -> dict[str, str]:
    if not isinstance(raw_authorization, dict):
        raise AutonomyPolicyError(
            f"Autonomous action authorization must be an object: "
            f"{service_name}"
        )
    _require_keys(
        raw_authorization,
        {"codes"},
        f"authorization {service_name}",
    )
    raw_codes = raw_authorization.get("codes", {})
    if not isinstance(raw_codes, dict):
        raise AutonomyPolicyError(
            f"Autonomous action authorization codes must be an object: "
            f"{service_name}"
        )

    codes: dict[str, str] = {}
    entity_set = set(entities)
    for raw_entity_id, raw_code in raw_codes.items():
        entity_id = str(raw_entity_id).strip().lower()
        if entity_id not in entity_set:
            raise AutonomyPolicyError(
                "Authorization code entity is not declared by action: "
                f"{service_name}:{entity_id}"
            )
        if not isinstance(raw_code, str) or not AUTHORIZATION_CODE_PATTERN.fullmatch(
            raw_code
        ):
            raise AutonomyPolicyError(
                "Authorization code must contain 4 to 64 letters, numbers, "
                "underscores, or hyphens"
            )
        codes[entity_id] = raw_code
    return codes


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
