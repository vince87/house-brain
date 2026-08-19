import json
import re
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import datetime
from time import monotonic
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, Field, TypeAdapter
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from house_brain.autonomy import VisibilityPolicy
from house_brain.config import Settings
from house_brain.entity_capabilities import entity_requires_code, service_is_supported
from house_brain.service_catalog import ServiceCatalog, ServiceCatalogError


class HomeAssistantEntity(BaseModel):
    """Generic Home Assistant state response."""

    entity_id: str
    state: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    last_changed: datetime
    last_reported: datetime | None = None
    last_updated: datetime
    context: dict[str, Any] = Field(default_factory=dict)


HistoryResponse = TypeAdapter(list[list[HomeAssistantEntity]])
StatesResponse = TypeAdapter(list[HomeAssistantEntity])


class EntityResolution(BaseModel):
    status: Literal[
        "resolved",
        "ambiguous",
        "not_found",
        "not_controllable",
    ]
    query: str
    entity: dict[str, str] | None = None
    candidates: list[dict[str, str]] = Field(default_factory=list)


HOME_ASSISTANT_WEBSOCKET_MAX_SIZE = 16 * 1024 * 1024


PLANNER_ATTRIBUTES = {
    "azimuth",
    "brightness",
    "brightness_pct",
    "current_position",
    "current_temperature",
    "device_class",
    "elevation",
    "friendly_name",
    "hvac_action",
    "hvac_mode",
    "position",
    "temperature",
    "unit_of_measurement",
}


class HomeAssistantError(Exception):
    """Base error raised while communicating with Home Assistant."""


class EntityNotFoundError(HomeAssistantError):
    """Raised when Home Assistant does not know an entity."""


class HistoryNotFoundError(HomeAssistantError):
    """Raised when no historical state exists in the requested interval."""


class HomeAssistantClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        hidden_entities_loader: Callable[
            [], Awaitable[frozenset[str]]
        ] | None = None,
    ) -> None:
        self._visibility = settings.autonomy_policy.visibility
        self._service_cache_ttl = settings.home_assistant_service_cache_ttl
        self._service_catalog: ServiceCatalog | None = None
        self._service_catalog_loaded_at = 0.0
        self._hidden_entities: frozenset[str] | None = None
        self._hidden_entities_loaded_at = 0.0
        self._hidden_entities_loader = hidden_entities_loader
        self._home_assistant_timeout = settings.home_assistant_timeout
        self._home_assistant_token = settings.home_assistant_token.get_secret_value()
        self._websocket_url = _websocket_url(str(settings.home_assistant_url))
        if transport is not None and hidden_entities_loader is None:
            self._hidden_entities_loader = _empty_hidden_entities
        self._client = httpx.AsyncClient(
            base_url=str(settings.home_assistant_url).rstrip("/"),
            headers={
                "Authorization": (
                    f"Bearer {settings.home_assistant_token.get_secret_value()}"
                ),
                "Content-Type": "application/json",
            },
            timeout=settings.home_assistant_timeout,
            transport=transport,
        )

    async def __aenter__(self) -> "HomeAssistantClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def search_entities(
        self,
        query: str,
        *,
        domain: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, str]]:
        states = await self._read_states()
        matches = _rank_entity_matches(
            states,
            query,
            visibility=self._visibility,
            domain=domain,
        )
        return [candidate for _, candidate in matches[:limit]]

    async def resolve_entity(
        self,
        query: str,
        *,
        domain: str | None = None,
        allowed_entities: frozenset[str] | None = None,
        limit: int = 5,
    ) -> EntityResolution:
        """Resolve one entity deterministically or report ambiguity."""
        matches = _rank_entity_matches(
            await self._read_states(),
            query,
            visibility=self._visibility,
            domain=domain,
        )
        return _resolve_ranked_entities(
            query,
            matches,
            allowed_entities=allowed_entities,
            limit=limit,
        )

    async def resolve_entity_from_message(
        self,
        message: str,
        *,
        allowed_entities: frozenset[str],
        limit: int = 5,
    ) -> EntityResolution:
        """Resolve a control target from the request before invoking the LLM."""
        matches = _rank_entity_mentions(
            await self._read_states(),
            message,
            visibility=self._visibility,
        )
        return _resolve_ranked_entities(
            message,
            matches,
            allowed_entities=allowed_entities,
            limit=limit,
        )

    async def list_entities(
        self,
        *,
        domains: set[str],
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return a compact state snapshot for planning across device domains."""
        states = await self._read_states()
        hidden_entities = await self._get_hidden_entities()

        snapshot: list[dict[str, Any]] = []
        for item in states:
            if self._visibility.is_hidden(item.entity_id):
                continue
            domain = item.entity_id.partition(".")[0]
            if domain not in domains:
                continue
            sanitized_attributes = _sanitize_mapping(
                item.attributes,
                self._visibility,
                hidden_entities,
            )
            attributes = {
                key: value
                for key, value in sanitized_attributes.items()
                if key in PLANNER_ATTRIBUTES
            }
            effective_state = _planner_effective_state(item)
            snapshot.append(
                {
                    "entity_id": item.entity_id,
                    "state": effective_state,
                    "effective_state": effective_state,
                    "attributes": attributes,
                    "last_changed": item.last_changed.isoformat(),
                }
            )
            if len(snapshot) >= limit:
                break
        return snapshot

    async def list_entities_for_configuration(self) -> list[dict[str, str]]:
        """Return every HA entity for the authenticated policy configurator."""
        states = await self._read_states()
        return [
            {
                "entity_id": item.entity_id,
                "domain": item.entity_id.partition(".")[0],
                "friendly_name": str(
                    item.attributes.get("friendly_name", item.entity_id)
                ),
                "state": item.state,
            }
            for item in sorted(states, key=lambda entity: entity.entity_id)
        ]

    async def get_entity(self, entity_id: str) -> HomeAssistantEntity:
        hidden_entities = await self._ensure_visible(entity_id)
        response = await self._get(f"/api/states/{entity_id}")

        if response.status_code == httpx.codes.NOT_FOUND:
            raise EntityNotFoundError(entity_id)

        try:
            response.raise_for_status()
            entity = HomeAssistantEntity.model_validate(response.json())
            return _sanitize_entity(entity, self._visibility, hidden_entities)
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise HomeAssistantError("Invalid response from Home Assistant") from exc

    async def get_history(
        self,
        entity_id: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[HomeAssistantEntity]:
        hidden_entities = await self._ensure_visible(entity_id)
        response = await self._get(
            f"/api/history/period/{start.isoformat()}",
            params={
                "filter_entity_id": entity_id,
                "end_time": end.isoformat(),
            },
        )

        try:
            response.raise_for_status()
            history = HistoryResponse.validate_python(response.json())
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise HomeAssistantError(
                "Invalid history response from Home Assistant"
            ) from exc

        return [
            _sanitize_entity(item, self._visibility, hidden_entities)
            for item in (history[0] if history else [])
        ]

    async def get_state_before(
        self,
        entity_id: str,
        *,
        before: datetime,
        search_start: datetime,
    ) -> HomeAssistantEntity:
        history = await self.get_history(
            entity_id,
            start=search_start,
            end=before,
        )
        candidates = [item for item in history if item.last_updated < before]
        if not candidates:
            raise HistoryNotFoundError(entity_id)

        return max(candidates, key=lambda item: item.last_updated)

    async def call_service(
        self,
        domain: str,
        service: str,
        *,
        entity_id: str,
        data: dict[str, Any],
    ) -> Any:
        await self._ensure_visible(entity_id)
        response = await self._post(
            f"/api/services/{domain}/{service}",
            json={"entity_id": entity_id, **data},
        )
        try:
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise HomeAssistantError(
                "Invalid service response from Home Assistant"
            ) from exc

    async def get_service_catalog(
        self, *, force_refresh: bool = False
    ) -> ServiceCatalog:
        now = monotonic()
        if (
            not force_refresh
            and self._service_catalog is not None
            and now - self._service_catalog_loaded_at < self._service_cache_ttl
        ):
            return self._service_catalog
        response = await self._get("/api/services")
        try:
            response.raise_for_status()
            catalog = ServiceCatalog.from_home_assistant(response.json())
        except (httpx.HTTPStatusError, ValueError, ServiceCatalogError) as exc:
            raise HomeAssistantError(
                "Invalid service catalog response from Home Assistant"
            ) from exc
        self._service_catalog = catalog
        self._service_catalog_loaded_at = now
        return catalog

    async def list_services(self, domain: str | None = None) -> list[dict[str, Any]]:
        return (await self.get_service_catalog()).list(domain)

    async def list_services_for_entity(
        self,
        entity_id: str,
    ) -> list[dict[str, Any]]:
        """Return domain services filtered by target capability metadata."""
        entity = await self.get_entity(entity_id)
        domain, separator, _ = entity.entity_id.partition(".")
        if not separator:
            raise ServiceCatalogError(f"Invalid Home Assistant entity_id: {entity_id}")
        catalog = await self.get_service_catalog()
        services: list[dict[str, Any]] = []
        for definition in catalog.list(domain):
            service = str(definition["service"])
            if not service_is_supported(domain, service, entity.attributes):
                continue
            item = dict(definition)
            if catalog.accepts_field(domain, service, "code"):
                item["device_code_required"] = entity_requires_code(
                    domain,
                    service,
                    entity.attributes,
                )
            services.append(item)
        return services

    async def validate_service_call(
        self,
        domain: str,
        service: str,
        data: dict[str, Any],
    ) -> None:
        (await self.get_service_catalog()).validate(domain, service, data)

    async def prepare_service_data(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: dict[str, Any],
        *,
        supplied_codes: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Prepare secret service inputs entirely on the trusted server side."""
        catalog = await self.get_service_catalog()
        entity = await self.get_entity(entity_id)
        if not service_is_supported(domain, service, entity.attributes):
            available = [
                item["service"]
                for item in await self.list_services_for_entity(entity_id)
            ]
            detail = (
                "; services supported by this entity: " + ", ".join(available)
                if available
                else "; this entity exposes no supported services"
            )
            raise ServiceCatalogError(
                "Home Assistant entity does not support service: "
                f"{entity_id}:{domain}.{service}{detail}"
            )
        if (
            catalog.accepts_field(domain, service, "code")
            and "code" not in data
            and not supplied_codes
        ):
            if entity_requires_code(domain, service, entity.attributes):
                raise ServiceCatalogError(
                    "Home Assistant service parameter is required: code"
                )
        return catalog.prepare(
            domain,
            service,
            data,
            supplied_codes=supplied_codes,
        )

    async def entity_declares_device_code(self, entity_id: str) -> bool:
        """Report target-specific code metadata without exposing a secret."""
        return _entity_declares_device_code(await self.get_entity(entity_id))

    def ensure_visible(self, entity_id: str) -> None:
        if self._visibility.is_hidden(entity_id):
            raise EntityNotFoundError(entity_id)

    async def ensure_accessible(self, entity_id: str) -> None:
        """Reject entities hidden by either policy or Home Assistant."""
        await self._ensure_visible(entity_id)

    async def hidden_entity_ids(self) -> frozenset[str]:
        """Return entity IDs hidden in the Home Assistant registry."""
        return await self._get_hidden_entities()

    async def _ensure_visible(self, entity_id: str) -> frozenset[str]:
        self.ensure_visible(entity_id)
        hidden_entities = await self._get_hidden_entities()
        if entity_id in hidden_entities:
            raise EntityNotFoundError(entity_id)
        return hidden_entities

    async def _get_hidden_entities(
        self,
        *,
        force_refresh: bool = False,
    ) -> frozenset[str]:
        now = monotonic()
        if (
            not force_refresh
            and self._hidden_entities is not None
            and now - self._hidden_entities_loaded_at < self._service_cache_ttl
        ):
            return self._hidden_entities

        if self._hidden_entities_loader is not None:
            hidden = await self._hidden_entities_loader()
        else:
            hidden = await self._load_hidden_entities_from_registry()

        self._hidden_entities = frozenset(hidden)
        self._hidden_entities_loaded_at = now
        return self._hidden_entities

    async def _load_hidden_entities_from_registry(self) -> frozenset[str]:
        try:
            async with connect(
                self._websocket_url,
                open_timeout=self._home_assistant_timeout,
                close_timeout=self._home_assistant_timeout,
                max_size=HOME_ASSISTANT_WEBSOCKET_MAX_SIZE,
            ) as websocket:
                required = json.loads(await websocket.recv())
                if required.get("type") != "auth_required":
                    raise ValueError("Home Assistant did not request authentication")
                await websocket.send(
                    json.dumps(
                        {
                            "type": "auth",
                            "access_token": self._home_assistant_token,
                        }
                    )
                )
                authenticated = json.loads(await websocket.recv())
                if authenticated.get("type") != "auth_ok":
                    raise ValueError("Home Assistant WebSocket authentication failed")
                await websocket.send(
                    json.dumps(
                        {
                            "id": 1,
                            "type": "config/entity_registry/list",
                        }
                    )
                )
                response = json.loads(await websocket.recv())
        except (
            OSError,
            TimeoutError,
            TypeError,
            ValueError,
            WebSocketException,
        ) as exc:
            raise HomeAssistantError(
                "Cannot read the Home Assistant entity registry"
            ) from exc

        if (
            response.get("type") != "result"
            or response.get("success") is not True
            or not isinstance(response.get("result"), list)
        ):
            raise HomeAssistantError(
                "Invalid Home Assistant entity registry response"
            )
        return _hidden_entity_ids_from_registry(response["result"])

    async def _read_states(self) -> list[HomeAssistantEntity]:
        response = await self._get("/api/states")
        try:
            response.raise_for_status()
            states = StatesResponse.validate_python(response.json())
            hidden_entities = await self._get_hidden_entities()
            return [
                item
                for item in states
                if item.entity_id not in hidden_entities
            ]
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise HomeAssistantError(
                "Invalid states response from Home Assistant"
            ) from exc

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.get(path, params=params)
        except httpx.RequestError as exc:
            raise HomeAssistantError("Home Assistant is unreachable") from exc

    async def _post(
        self,
        path: str,
        *,
        json: dict[str, Any],
    ) -> httpx.Response:
        try:
            return await self._client.post(path, json=json)
        except httpx.RequestError as exc:
            raise HomeAssistantError("Home Assistant is unreachable") from exc


async def _empty_hidden_entities() -> frozenset[str]:
    return frozenset()


def _websocket_url(home_assistant_url: str) -> str:
    parsed = urlsplit(home_assistant_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, "/api/websocket", "", ""))


def _hidden_entity_ids_from_registry(
    entries: list[object],
) -> frozenset[str]:
    return frozenset(
        str(entry["entity_id"])
        for entry in entries
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("entity_id"), str)
            and entry.get("hidden_by") is not None
        )
    )


_HIDDEN_VALUE = object()


def _sanitize_entity(
    entity: HomeAssistantEntity,
    visibility: VisibilityPolicy,
    hidden_entities: frozenset[str] = frozenset(),
) -> HomeAssistantEntity:
    return entity.model_copy(
        update={
            "attributes": _sanitize_mapping(
                entity.attributes, visibility, hidden_entities
            ),
            "context": _sanitize_mapping(
                entity.context, visibility, hidden_entities
            ),
        }
    )


def _sanitize_mapping(
    value: dict[str, Any],
    visibility: VisibilityPolicy,
    hidden_entities: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        clean = _sanitize_value(item, visibility, hidden_entities)
        if clean is not _HIDDEN_VALUE:
            sanitized[key] = clean
    return sanitized


def _sanitize_value(
    value: Any,
    visibility: VisibilityPolicy,
    hidden_entities: frozenset[str] = frozenset(),
) -> Any:
    if isinstance(value, str):
        return (
            _HIDDEN_VALUE
            if visibility.is_hidden(value) or value in hidden_entities
            else value
        )
    if isinstance(value, list):
        return [
            clean
            for item in value
            if (
                clean := _sanitize_value(item, visibility, hidden_entities)
            )
            is not _HIDDEN_VALUE
        ]
    if isinstance(value, tuple):
        return tuple(
            clean
            for item in value
            if (
                clean := _sanitize_value(item, visibility, hidden_entities)
            )
            is not _HIDDEN_VALUE
        )
    if isinstance(value, dict):
        return _sanitize_mapping(value, visibility, hidden_entities)
    return value


def _planner_effective_state(item: HomeAssistantEntity) -> str:
    """Normalize cover state because reported state can lag its position."""
    if item.entity_id.startswith("cover."):
        position = item.attributes.get("current_position")
        if isinstance(position, (int, float)) and not isinstance(position, bool):
            if position <= 0:
                return "closed"
            if position >= 100:
                return "open"
            return "partially_open"
    return item.state


def _normalize_entity_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", without_accents))


def _entity_declares_device_code(entity: HomeAssistantEntity) -> bool:
    attributes = entity.attributes
    code_format = attributes.get("code_format")
    if code_format is not None and str(code_format).strip().casefold() not in {
        "",
        "none",
    }:
        return True
    return any(
        attributes.get(name) is True
        for name in ("code_required", "requires_code", "code_arm_required")
    )


def _rank_entity_matches(
    states: list[HomeAssistantEntity],
    query: str,
    *,
    visibility: VisibilityPolicy,
    domain: str | None,
) -> list[tuple[int, dict[str, str]]]:
    normalized_query = _normalize_entity_text(query)
    words = normalized_query.split()
    if not words:
        return []

    matches: list[tuple[int, dict[str, str]]] = []
    for item in states:
        if visibility.is_hidden(item.entity_id):
            continue
        item_domain, _, object_id = item.entity_id.partition(".")
        if domain and item_domain != domain:
            continue

        friendly_name = str(item.attributes.get("friendly_name", "")).strip()
        normalized_entity_id = item.entity_id.casefold()
        normalized_object_id = _normalize_entity_text(object_id)
        normalized_name = _normalize_entity_text(friendly_name)
        combined = f"{normalized_object_id} {normalized_name}".strip()

        if query.casefold().strip() == normalized_entity_id:
            score = 1000
        elif normalized_query == normalized_name and normalized_name:
            score = 900
        elif normalized_query == normalized_object_id:
            score = 850
        elif all(word in normalized_name.split() for word in words):
            score = 700 + len(words)
        elif all(word in combined.split() for word in words):
            score = 600 + len(words)
        else:
            matched_words = sum(word in combined.split() for word in words)
            if matched_words == 0:
                continue
            score = 100 + matched_words

        matches.append(
            (
                score,
                {
                    "entity_id": item.entity_id,
                    "friendly_name": friendly_name,
                    "state": item.state,
                },
            )
        )

    matches.sort(key=lambda item: (-item[0], item[1]["entity_id"]))
    return matches


def _rank_entity_mentions(
    states: list[HomeAssistantEntity],
    message: str,
    *,
    visibility: VisibilityPolicy,
) -> list[tuple[int, dict[str, str]]]:
    message_words = set(_normalize_entity_text(message).split())
    if not message_words:
        return []

    matches: list[tuple[int, dict[str, str]]] = []
    for item in states:
        if visibility.is_hidden(item.entity_id):
            continue
        _, _, object_id = item.entity_id.partition(".")
        friendly_name = str(item.attributes.get("friendly_name", "")).strip()
        name_words = set(_normalize_entity_text(friendly_name).split())
        object_words = set(_normalize_entity_text(object_id).split())

        if name_words and name_words <= message_words:
            score = 900 + len(name_words)
        elif object_words and object_words <= message_words:
            score = 850 + len(object_words)
        else:
            overlap = max(
                len(name_words & message_words),
                len(object_words & message_words),
            )
            if overlap == 0:
                continue
            score = 100 + overlap

        matches.append(
            (
                score,
                {
                    "entity_id": item.entity_id,
                    "friendly_name": friendly_name,
                    "state": item.state,
                },
            )
        )

    matches.sort(key=lambda item: (-item[0], item[1]["entity_id"]))
    return matches


def _resolve_ranked_entities(
    query: str,
    matches: list[tuple[int, dict[str, str]]],
    *,
    allowed_entities: frozenset[str] | None,
    limit: int,
) -> EntityResolution:
    if not matches:
        return EntityResolution(status="not_found", query=query)

    if allowed_entities is not None:
        best_global_score = matches[0][0]
        allowed_matches = [
            item for item in matches if item[1]["entity_id"] in allowed_entities
        ]
        if not allowed_matches or allowed_matches[0][0] < best_global_score:
            return EntityResolution(
                status="not_controllable",
                query=query,
                candidates=[candidate for _, candidate in matches[:limit]],
            )
        matches = allowed_matches

    best_score = matches[0][0]
    candidates = [candidate for _, candidate in matches[:limit]]
    best_matches = [candidate for score, candidate in matches if score == best_score]
    if best_score < 600 or len(best_matches) != 1:
        return EntityResolution(
            status="ambiguous",
            query=query,
            candidates=candidates,
        )

    return EntityResolution(
        status="resolved",
        query=query,
        entity=matches[0][1],
        candidates=candidates,
    )
