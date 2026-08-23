"""Safe diagnostics for the House Brain Home Assistant integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import HouseBrainConfigEntry
from .api import HouseBrainApiError
from .const import CONF_BASE_URL, CONF_CONVERSATION_MODE


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: HouseBrainConfigEntry,
) -> dict[str, Any]:
    """Return connectivity details without exposing the configured API key."""
    del hass
    result: dict[str, Any] = {
        "base_url": entry.data[CONF_BASE_URL],
        "conversation_mode": entry.data[CONF_CONVERSATION_MODE],
        "connected": False,
        "remote_version": entry.runtime_data.status.version,
    }
    try:
        status = await entry.runtime_data.client.async_validate()
    except HouseBrainApiError as exc:
        result["error"] = type(exc).__name__
    else:
        result["connected"] = True
        result["remote_version"] = status.version
    return result
