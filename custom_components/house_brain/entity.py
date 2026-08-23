"""Shared Home Assistant entity for the House Brain service."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import Entity

from . import HouseBrainConfigEntry
from .const import ATTRIBUTION, DOMAIN


class HouseBrainEntity(Entity):
    """Base entity representing one capability of a House Brain server."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_attribution = ATTRIBUTION

    def __init__(self, entry: HouseBrainConfigEntry, capability: str) -> None:
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{capability}"
        self._attr_translation_key = capability
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="House Brain",
            model="Local AI middleware",
            sw_version=entry.runtime_data.status.version,
            entry_type=dr.DeviceEntryType.SERVICE,
        )
