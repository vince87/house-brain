from typing import Any

# Home Assistant AlarmControlPanelEntityFeature values. These describe device
# capabilities only; authorization remains entirely in autonomy.yaml.
_ALARM_CONTROL_PANEL_SERVICE_FEATURES = {
    "alarm_arm_home": 1,
    "alarm_arm_away": 2,
    "alarm_arm_night": 4,
    "alarm_trigger": 8,
    "alarm_arm_custom_bypass": 16,
    "alarm_arm_vacation": 32,
}


def service_is_supported(
    domain: str,
    service: str,
    attributes: dict[str, Any],
) -> bool:
    """Return whether target metadata declares support for a service.

    Services without a Home Assistant feature flag are left to the service
    catalog and Home Assistant itself. This keeps the generic engine open to
    arbitrary domains while applying target-specific capability metadata when
    Home Assistant publishes it.
    """
    feature = _service_feature(domain, service)
    if feature is None:
        return True
    supported_features = attributes.get("supported_features")
    if isinstance(supported_features, bool) or not isinstance(
        supported_features,
        int,
    ):
        return True
    return bool(supported_features & feature)


def entity_requires_code(
    domain: str,
    service: str,
    attributes: dict[str, Any],
) -> bool:
    """Interpret target- and service-specific Home Assistant code metadata."""
    if domain == "alarm_control_panel" and service.startswith("alarm_arm_"):
        code_arm_required = attributes.get("code_arm_required")
        if isinstance(code_arm_required, bool):
            return code_arm_required

    code_format = attributes.get("code_format")
    if code_format is not None and str(code_format).strip().casefold() not in {
        "",
        "none",
    }:
        return True
    return any(
        attributes.get(name) is True
        for name in ("code_required", "requires_code")
    )


def _service_feature(domain: str, service: str) -> int | None:
    if domain == "alarm_control_panel":
        return _ALARM_CONTROL_PANEL_SERVICE_FEATURES.get(service)
    return None
