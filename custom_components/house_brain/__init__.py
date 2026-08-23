"""Native Home Assistant integration for House Brain."""

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
from .const import CONF_BASE_URL
from .models import HouseBrainRuntimeData

PLATFORMS = (Platform.AI_TASK, Platform.CONVERSATION)

HouseBrainConfigEntry = ConfigEntry[HouseBrainRuntimeData]


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
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HouseBrainConfigEntry,
) -> bool:
    """Unload a House Brain configuration entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
