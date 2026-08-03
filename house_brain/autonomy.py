import re
from dataclasses import dataclass

from house_brain.actions import ActionRequest

EVENT_TYPE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class AutonomyPolicyError(ValueError):
    """Raised when an autonomous event or action is not explicitly allowed."""


@dataclass(frozen=True)
class AutonomyPolicy:
    event_types: frozenset[str]
    action_rules: frozenset[str]

    def __post_init__(self) -> None:
        for event_type in self.event_types:
            if not EVENT_TYPE_PATTERN.fullmatch(event_type):
                raise AutonomyPolicyError(
                    f"Invalid autonomous event allowlist entry: {event_type}"
                )
        for rule in self.action_rules:
            _parse_action_rule(rule)

    def validate_event(self, event_type: str) -> None:
        if event_type not in self.event_types:
            raise AutonomyPolicyError(
                f"Autonomous event is not allowlisted: {event_type}"
            )

    def validate_action(self, action: ActionRequest) -> None:
        rule = action_rule(action)
        if rule not in self.action_rules:
            raise AutonomyPolicyError(
                f"Autonomous action is not allowlisted: {rule}"
            )


def parse_allowlist(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    )


def action_rule(action: ActionRequest) -> str:
    return f"{action.domain}.{action.service}:{action.entity_id}"


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
