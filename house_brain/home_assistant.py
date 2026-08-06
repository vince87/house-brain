from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field, TypeAdapter

from house_brain.autonomy import VisibilityPolicy
from house_brain.config import Settings


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
    ) -> None:
        self._visibility = settings.autonomy_policy.visibility
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
        response = await self._get("/api/states")
        try:
            response.raise_for_status()
            states = StatesResponse.validate_python(response.json())
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise HomeAssistantError(
                "Invalid states response from Home Assistant"
            ) from exc

        words = query.casefold().split()
        preferred_domains = {"switch", "light", "cover", "climate"}
        matches: list[tuple[int, dict[str, str]]] = []
        for item in states:
            if self._visibility.is_hidden(item.entity_id):
                continue
            item_domain = item.entity_id.partition(".")[0]
            if domain and item_domain != domain:
                continue
            friendly_name = str(
                item.attributes.get("friendly_name", "")
            )
            haystack = f"{item.entity_id} {friendly_name}".casefold()
            word_score = sum(
                (len(words) - index) * (word in haystack)
                for index, word in enumerate(words)
            )
            domain_score = 100 if item_domain in preferred_domains else 0
            score = domain_score + word_score
            if words and score == 0:
                continue
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
        matches.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in matches[:limit]]

    async def list_entities(
        self,
        *,
        domains: set[str],
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return a compact state snapshot for planning across device domains."""
        response = await self._get("/api/states")
        try:
            response.raise_for_status()
            states = StatesResponse.validate_python(response.json())
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise HomeAssistantError(
                "Invalid states response from Home Assistant"
            ) from exc

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

    async def get_entity(self, entity_id: str) -> HomeAssistantEntity:
        self.ensure_visible(entity_id)
        response = await self._get(f"/api/states/{entity_id}")

        if response.status_code == httpx.codes.NOT_FOUND:
            raise EntityNotFoundError(entity_id)

        try:
            response.raise_for_status()
            entity = HomeAssistantEntity.model_validate(response.json())
            return _sanitize_entity(entity, self._visibility)
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise HomeAssistantError("Invalid response from Home Assistant") from exc

    async def get_history(
        self,
        entity_id: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[HomeAssistantEntity]:
        self.ensure_visible(entity_id)
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
            _sanitize_entity(item, self._visibility)
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
        candidates = [
            item for item in history if item.last_updated < before
        ]
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
        self.ensure_visible(entity_id)
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

    def ensure_visible(self, entity_id: str) -> None:
        if self._visibility.is_hidden(entity_id):
            raise EntityNotFoundError(entity_id)

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


_HIDDEN_VALUE = object()


def _sanitize_entity(
    entity: HomeAssistantEntity,
    visibility: VisibilityPolicy,
) -> HomeAssistantEntity:
    return entity.model_copy(
        update={
            "attributes": _sanitize_mapping(entity.attributes, visibility),
            "context": _sanitize_mapping(entity.context, visibility),
        }
    )


def _sanitize_mapping(
    value: dict[str, Any],
    visibility: VisibilityPolicy,
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, item in value.items():
        clean = _sanitize_value(item, visibility)
        if clean is not _HIDDEN_VALUE:
            sanitized[key] = clean
    return sanitized


def _sanitize_value(value: Any, visibility: VisibilityPolicy) -> Any:
    if isinstance(value, str):
        return _HIDDEN_VALUE if visibility.is_hidden(value) else value
    if isinstance(value, list):
        return [
            clean
            for item in value
            if (clean := _sanitize_value(item, visibility)) is not _HIDDEN_VALUE
        ]
    if isinstance(value, tuple):
        return tuple(
            clean
            for item in value
            if (clean := _sanitize_value(item, visibility)) is not _HIDDEN_VALUE
        )
    if isinstance(value, dict):
        return _sanitize_mapping(value, visibility)
    return value


def _planner_effective_state(item: HomeAssistantEntity) -> str:
    """Normalize cover state because reported state can lag its position."""
    if item.entity_id.startswith("cover."):
        position = item.attributes.get("current_position")
        if (
            isinstance(position, (int, float))
            and not isinstance(position, bool)
        ):
            if position <= 0:
                return "closed"
            if position >= 100:
                return "open"
            return "partially_open"
    return item.state
