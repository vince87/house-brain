from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field, TypeAdapter

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

    async def get_entity(self, entity_id: str) -> HomeAssistantEntity:
        response = await self._request(f"/api/states/{entity_id}")

        if response.status_code == httpx.codes.NOT_FOUND:
            raise EntityNotFoundError(entity_id)

        try:
            response.raise_for_status()
            return HomeAssistantEntity.model_validate(response.json())
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise HomeAssistantError("Invalid response from Home Assistant") from exc

    async def get_history(
        self,
        entity_id: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[HomeAssistantEntity]:
        response = await self._request(
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

        return history[0] if history else []

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

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.get(path, params=params)
        except httpx.RequestError as exc:
            raise HomeAssistantError("Home Assistant is unreachable") from exc
