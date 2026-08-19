import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9_]+$")
ENTITY_ID_PATTERN = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


class ActionPolicyError(ValueError):
    """Raised when an action is not permitted by the local policy."""


class ActionRequest(BaseModel):
    """A single, explicitly targeted Home Assistant service call."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=1)
    service: str = Field(min_length=1)
    entity_id: str = Field(min_length=3)
    data: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True

    @field_validator("domain", "service", "entity_id")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().lower()


class ActionBatchRequest(BaseModel):
    """A bounded action plan validated before any service call."""

    model_config = ConfigDict(extra="forbid")

    actions: list[ActionRequest] = Field(min_length=1, max_length=20)


class ActionResult(BaseModel):
    status: Literal["simulated", "executed"]
    domain: str
    service: str
    entity_id: str
    data: dict[str, Any]
    home_assistant_response: Any | None = None


def validate_action(action: ActionRequest) -> None:
    """Validate language-free action structure before policy and HA checks."""
    _validate_identifiers(action)
    _validate_action_data(action.data)


def _validate_identifiers(action: ActionRequest) -> None:
    if not IDENTIFIER_PATTERN.fullmatch(action.domain):
        raise ActionPolicyError(f"Invalid action domain: {action.domain}")
    if not IDENTIFIER_PATTERN.fullmatch(action.service):
        raise ActionPolicyError(f"Invalid action service: {action.service}")
    if not ENTITY_ID_PATTERN.fullmatch(action.entity_id):
        raise ActionPolicyError(f"Invalid action entity_id: {action.entity_id}")

    entity_domain, _, _ = action.entity_id.partition(".")
    if entity_domain != action.domain:
        raise ActionPolicyError(
            "entity_id domain must match the requested service domain"
        )


def _validate_action_data(data: dict[str, Any]) -> None:
    for name, value in data.items():
        if not IDENTIFIER_PATTERN.fullmatch(name):
            raise ActionPolicyError(f"Invalid action data field: {name}")
        _validate_json_value(value, name)


def _validate_json_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ActionPolicyError(f"Action data must be finite: {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for name, item in value.items():
            if not isinstance(name, str):
                raise ActionPolicyError(
                    f"Action data object keys must be strings: {path}"
                )
            _validate_json_value(item, f"{path}.{name}")
        return
    raise ActionPolicyError(f"Action data must be JSON-compatible: {path}")
