from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_SERVICES: dict[str, set[str]] = {
    "light": {"turn_on", "turn_off", "toggle"},
    "switch": {"turn_on", "turn_off", "toggle"},
    "cover": {
        "open_cover",
        "close_cover",
        "stop_cover",
        "set_cover_position",
    },
    "climate": {
        "turn_on",
        "turn_off",
        "set_temperature",
        "set_hvac_mode",
    },
}

BLOCKED_DOMAINS = {
    "alarm_control_panel",
    "automation",
    "button",
    "lock",
    "scene",
    "script",
}

NO_DATA_SERVICES = {
    ("light", "turn_off"),
    ("light", "toggle"),
    ("switch", "turn_on"),
    ("switch", "turn_off"),
    ("switch", "toggle"),
    ("cover", "open_cover"),
    ("cover", "close_cover"),
    ("cover", "stop_cover"),
    ("climate", "turn_on"),
    ("climate", "turn_off"),
}

HVAC_MODES = {"off", "heat", "cool", "heat_cool", "auto", "dry", "fan_only"}


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
    if action.domain in BLOCKED_DOMAINS:
        raise ActionPolicyError(
            f"Domain requires human confirmation and is currently blocked: "
            f"{action.domain}"
        )

    services = ALLOWED_SERVICES.get(action.domain)
    if services is None:
        raise ActionPolicyError(f"Domain is not allowed: {action.domain}")
    if action.service not in services:
        raise ActionPolicyError(
            f"Service is not allowed for {action.domain}: {action.service}"
        )

    entity_domain, separator, _ = action.entity_id.partition(".")
    if not separator or entity_domain != action.domain:
        raise ActionPolicyError(
            "entity_id domain must match the requested service domain"
        )

    if (action.domain, action.service) in NO_DATA_SERVICES:
        _require_keys(action.data, allowed=set(), required=set())
    elif (action.domain, action.service) == ("cover", "set_cover_position"):
        _require_keys(
            action.data,
            allowed={"position"},
            required={"position"},
        )
        _require_number(action.data["position"], "position", 0, 100)
    elif (action.domain, action.service) == ("climate", "set_temperature"):
        _require_keys(
            action.data,
            allowed={"temperature"},
            required={"temperature"},
        )
        _require_number(action.data["temperature"], "temperature", 5, 35)
    elif (action.domain, action.service) == ("climate", "set_hvac_mode"):
        _require_keys(
            action.data,
            allowed={"hvac_mode"},
            required={"hvac_mode"},
        )
        if action.data["hvac_mode"] not in HVAC_MODES:
            raise ActionPolicyError("Unsupported hvac_mode")
    elif (action.domain, action.service) == ("light", "turn_on"):
        _validate_light_turn_on(action.data)


def _validate_light_turn_on(data: dict[str, Any]) -> None:
    _require_keys(
        data,
        allowed={"brightness", "brightness_pct", "transition"},
        required=set(),
    )
    if "brightness" in data:
        _require_number(data["brightness"], "brightness", 0, 255)
    if "brightness_pct" in data:
        _require_number(data["brightness_pct"], "brightness_pct", 0, 100)
    if "transition" in data:
        _require_number(data["transition"], "transition", 0, 60)
    if "brightness" in data and "brightness_pct" in data:
        raise ActionPolicyError(
            "Use either brightness or brightness_pct, not both"
        )


def _require_keys(
    data: dict[str, Any],
    *,
    allowed: set[str],
    required: set[str],
) -> None:
    unexpected = set(data) - allowed
    missing = required - set(data)
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise ActionPolicyError(f"Unexpected action data: {names}")
    if missing:
        names = ", ".join(sorted(missing))
        raise ActionPolicyError(f"Missing action data: {names}")


def _require_number(
    value: Any,
    name: str,
    minimum: float,
    maximum: float,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ActionPolicyError(f"{name} must be a number")
    if not minimum <= value <= maximum:
        raise ActionPolicyError(
            f"{name} must be between {minimum:g} and {maximum:g}"
        )
