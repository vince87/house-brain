"""Native Home Assistant integration for House Brain."""

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    HouseBrainAuthenticationError,
    HouseBrainClient,
    HouseBrainConnectionError,
    HouseBrainResponseError,
)
from .const import CONF_BASE_URL, CONF_CONVERSATION_MODE, DOMAIN
from .models import HouseBrainRuntimeData
from .websocket import async_register_websocket_commands

PLATFORMS = (Platform.AI_TASK, Platform.CONVERSATION)

_PANEL_STATIC_URL = "/house_brain_static/house-brain-panel.js"
_PANEL_MODULE_URL = f"{_PANEL_STATIC_URL}?v=native-2"
_PANEL_MODULE_FILE = Path(__file__).parent / "frontend" / "house-brain-panel.js"
_PANEL_PATHS_KEY = f"{DOMAIN}_panel_paths"
_PANEL_STATIC_KEY = f"{DOMAIN}_panel_static_registered"
_PANEL_WEBSOCKET_KEY = f"{DOMAIN}_panel_websocket_registered"

HouseBrainConfigEntry = ConfigEntry[HouseBrainRuntimeData]


async def _async_register_panel(
    hass: HomeAssistant,
    entry: HouseBrainConfigEntry,
) -> str:
    """Register one admin-only sidebar panel for this House Brain server."""
    if not hass.data.get(_PANEL_STATIC_KEY):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    _PANEL_STATIC_URL,
                    str(_PANEL_MODULE_FILE),
                    False,
                )
            ]
        )
        hass.data[_PANEL_STATIC_KEY] = True

    panel_path = f"house-brain-{entry.entry_id[:8]}"
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=panel_path,
        webcomponent_name="house-brain-panel",
        sidebar_title="House Brain",
        sidebar_icon="mdi:brain",
        module_url=_PANEL_MODULE_URL,
        config={
            "entry_id": entry.entry_id,
            "mode": entry.data[CONF_CONVERSATION_MODE],
        },
        require_admin=True,
        handle_safe_area=True,
    )
    panel_paths = hass.data.setdefault(_PANEL_PATHS_KEY, {})
    panel_paths[entry.entry_id] = panel_path
    return panel_path


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HouseBrainConfigEntry,
) -> bool:
    """Set up House Brain from a configuration entry."""
    client = HouseBrainClient(
        async_get_clientsession(hass),
        entry.data[CONF_BASE_URL],
        entry.data[CONF_API_KEY],
    )
    try:
        status = await client.async_validate()
    except HouseBrainAuthenticationError as exc:
        raise ConfigEntryAuthFailed from exc
    except (HouseBrainConnectionError, HouseBrainResponseError) as exc:
        raise ConfigEntryNotReady from exc

    entry.runtime_data = HouseBrainRuntimeData(client=client, status=status)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if not hass.data.get(_PANEL_WEBSOCKET_KEY):
        async_register_websocket_commands(hass)
        hass.data[_PANEL_WEBSOCKET_KEY] = True
    await _async_register_panel(hass, entry)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HouseBrainConfigEntry,
) -> bool:
    """Unload House Brain entities and its sidebar panel."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    panel_paths = hass.data.get(_PANEL_PATHS_KEY, {})
    if panel_path := panel_paths.pop(entry.entry_id, None):
        frontend.async_remove_panel(hass, panel_path, warn_if_unknown=False)
    return True
