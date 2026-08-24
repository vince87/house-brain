import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, Field

from house_brain.autonomy import VisibilityPolicy


class AreaRecord(BaseModel):
    area_id: str
    name: str
    aliases: tuple[str, ...] = ()


class DeviceRecord(BaseModel):
    device_id: str
    area_id: str | None = None
    name: str | None = None


class EntityRegistryRecord(BaseModel):
    entity_id: str
    device_id: str | None = None
    area_id: str | None = None
    hidden: bool = False


class HomeContextRegistry(BaseModel):
    areas: dict[str, AreaRecord] = Field(default_factory=dict)
    devices: dict[str, DeviceRecord] = Field(default_factory=dict)
    entities: dict[str, EntityRegistryRecord] = Field(default_factory=dict)

    @classmethod
    def from_home_assistant(
        cls,
        *,
        areas: list[object],
        devices: list[object],
        entities: list[object],
    ) -> "HomeContextRegistry":
        parsed_areas: dict[str, AreaRecord] = {}
        for raw in areas:
            if not isinstance(raw, dict):
                continue
            area_id = _optional_text(raw.get("area_id"))
            name = _optional_text(raw.get("name"))
            if area_id is None or name is None:
                continue
            aliases = raw.get("aliases")
            parsed_areas[area_id] = AreaRecord(
                area_id=area_id,
                name=name,
                aliases=tuple(
                    alias
                    for item in aliases
                    if (alias := _optional_text(item)) is not None
                )
                if isinstance(aliases, list)
                else (),
            )

        parsed_devices: dict[str, DeviceRecord] = {}
        for raw in devices:
            if not isinstance(raw, dict):
                continue
            device_id = _optional_text(raw.get("id"))
            if device_id is None:
                continue
            parsed_devices[device_id] = DeviceRecord(
                device_id=device_id,
                area_id=_optional_text(raw.get("area_id")),
                name=_optional_text(raw.get("name_by_user"))
                or _optional_text(raw.get("name")),
            )

        parsed_entities: dict[str, EntityRegistryRecord] = {}
        for raw in entities:
            if not isinstance(raw, dict):
                continue
            entity_id = _optional_text(raw.get("entity_id"))
            if entity_id is None:
                continue
            parsed_entities[entity_id] = EntityRegistryRecord(
                entity_id=entity_id,
                device_id=_optional_text(raw.get("device_id")),
                area_id=_optional_text(raw.get("area_id")),
                hidden=raw.get("hidden_by") is not None,
            )

        return cls(
            areas=parsed_areas,
            devices=parsed_devices,
            entities=parsed_entities,
        )

    @property
    def hidden_entity_ids(self) -> frozenset[str]:
        return frozenset(
            entity_id for entity_id, record in self.entities.items() if record.hidden
        )

    def relationship(
        self,
        entity_id: str,
    ) -> tuple[AreaRecord | None, DeviceRecord | None]:
        entity = self.entities.get(entity_id)
        device = (
            self.devices.get(entity.device_id)
            if entity is not None and entity.device_id
            else None
        )
        area_id = (
            entity.area_id
            if entity is not None and entity.area_id
            else device.area_id
            if device is not None
            else None
        )
        return (self.areas.get(area_id) if area_id else None, device)


class HomeContextItem(BaseModel):
    entity_id: str
    domain: str
    name: str
    state: str
    effective_state: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    last_changed: str
    area_id: str | None = None
    area_name: str | None = None
    device_id: str | None = None
    device_name: str | None = None
    controllable: bool = False
    selection_reasons: list[str] = Field(default_factory=list)


class HomeContextPage(BaseModel):
    status: str = "completed"
    items: list[HomeContextItem]
    offset: int
    returned: int
    total: int
    truncated: bool
    next_offset: int | None = None
    requested_areas: list[str] = Field(default_factory=list)
    requested_domains: list[str] = Field(default_factory=list)
    query: str | None = None


def build_home_context(
    states: Iterable[Mapping[str, Any]],
    *,
    registry: HomeContextRegistry,
    visibility: VisibilityPolicy,
    entity_names: Mapping[str, str],
    controllable_entities: frozenset[str],
    domains: set[str] | None = None,
    areas: set[str] | None = None,
    query: str | None = None,
    controllable_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> HomeContextPage:
    """Build a bounded, policy-filtered view of Home Assistant relationships."""
    normalized_areas = {_normalize(item) for item in areas or set() if item.strip()}
    normalized_query = _normalize(query or "")
    query_words = normalized_query.split()
    requested_domains = sorted(domains or set())
    requested_areas = sorted(areas or set())
    matches: list[tuple[tuple[str, str, str], HomeContextItem]] = []

    for state in states:
        entity_id = str(state.get("entity_id", "")).strip().lower()
        if not entity_id or visibility.is_hidden(entity_id):
            continue
        domain = entity_id.partition(".")[0]
        if domains and domain not in domains:
            continue
        controllable = entity_id in controllable_entities
        if controllable_only and not controllable:
            continue

        entity_record = registry.entities.get(entity_id)
        if entity_record is not None and entity_record.hidden:
            continue
        area, device = registry.relationship(entity_id)
        area_terms = (
            {
                _normalize(area.area_id),
                _normalize(area.name),
                *map(_normalize, area.aliases),
            }
            if area is not None
            else set()
        )
        if normalized_areas and not normalized_areas.intersection(area_terms):
            continue

        attributes = dict(state.get("attributes") or {})
        name = entity_names.get(
            entity_id,
            str(attributes.get("friendly_name") or entity_id),
        )
        searchable = _normalize(
            " ".join(
                part
                for part in (
                    entity_id,
                    name,
                    area.name if area else None,
                    area.area_id if area else None,
                    device.name if device else None,
                )
                if part
            )
        ).split()
        if query_words and not all(word in searchable for word in query_words):
            continue

        reasons = ["policy_visible"]
        if controllable:
            reasons.append("policy_controllable")
        if normalized_areas:
            reasons.append("area_match")
        if query_words:
            reasons.append("query_match")
        if domains:
            reasons.append("domain_match")
        item = HomeContextItem(
            entity_id=entity_id,
            domain=domain,
            name=name,
            state=str(state.get("state", "unknown")),
            effective_state=str(
                state.get("effective_state", state.get("state", "unknown"))
            ),
            attributes=attributes,
            last_changed=str(state.get("last_changed", "")),
            area_id=area.area_id if area else None,
            area_name=area.name if area else None,
            device_id=device.device_id if device else None,
            device_name=device.name if device else None,
            controllable=controllable,
            selection_reasons=reasons,
        )
        matches.append(
            (
                (
                    _normalize(item.area_name or ""),
                    _normalize(item.name),
                    item.entity_id,
                ),
                item,
            )
        )

    matches.sort(key=lambda pair: pair[0])
    all_items = [item for _, item in matches]
    page = all_items[offset : offset + limit]
    next_offset = offset + len(page) if offset + len(page) < len(all_items) else None
    return HomeContextPage(
        items=page,
        offset=offset,
        returned=len(page),
        total=len(all_items),
        truncated=next_offset is not None,
        next_offset=next_offset,
        requested_areas=requested_areas,
        requested_domains=requested_domains,
        query=query.strip() if query and query.strip() else None,
    )


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", without_accents))

