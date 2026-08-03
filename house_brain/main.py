from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from loguru import logger

from house_brain.actions import (
    ActionPolicyError,
    ActionRequest,
    ActionResult,
    validate_action,
)
from house_brain.config import Settings, get_settings
from house_brain.home_assistant import (
    EntityNotFoundError,
    HistoryNotFoundError,
    HomeAssistantClient,
    HomeAssistantEntity,
    HomeAssistantError,
)

APP_NAME = "House Brain"
APP_VERSION = "0.1.0"

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="AI middleware between LLMs and Home Assistant.",
)


async def get_home_assistant_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[HomeAssistantClient]:
    async with HomeAssistantClient(settings) as client:
        yield client


HomeAssistantClientDependency = Annotated[
    HomeAssistantClient,
    Depends(get_home_assistant_client),
]


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return the service health status."""
    return {
        "status": "ok",
        "service": "house-brain",
        "version": APP_VERSION,
    }


@app.get(
    "/entities/{entity_id}",
    response_model=HomeAssistantEntity,
    tags=["home-assistant"],
)
async def get_entity(
    entity_id: str,
    client: HomeAssistantClientDependency,
) -> HomeAssistantEntity:
    """Return the current state of any Home Assistant entity."""
    try:
        return await client.get_entity(entity_id)
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        ) from exc
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.get(
    "/history",
    response_model=list[HomeAssistantEntity],
    tags=["home-assistant"],
)
async def get_history(
    entity_id: str,
    client: HomeAssistantClientDependency,
    minutes: Annotated[int, Query(ge=1, le=10_080)] = 60,
) -> list[HomeAssistantEntity]:
    """Return recent Recorder history for one entity."""
    end = datetime.now(UTC)
    start = end - timedelta(minutes=minutes)

    try:
        return await client.get_history(
            entity_id,
            start=start,
            end=end,
        )
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.get(
    "/state-before",
    response_model=HomeAssistantEntity,
    tags=["home-assistant"],
)
async def get_state_before(
    entity_id: str,
    before: datetime,
    client: HomeAssistantClientDependency,
    search_hours: Annotated[int, Query(ge=1, le=720)] = 24,
) -> HomeAssistantEntity:
    """Return the last recorded state strictly before a timestamp."""
    if before.tzinfo is None or before.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="before must include a timezone offset",
        )

    before_utc = before.astimezone(UTC)
    search_start = before_utc - timedelta(hours=search_hours)

    try:
        return await client.get_state_before(
            entity_id,
            before=before_utc,
            search_start=search_start,
        )
    except HistoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No state found for {entity_id} "
                f"in the previous {search_hours} hours"
            ),
        ) from exc
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post(
    "/actions",
    response_model=ActionResult,
    tags=["home-assistant"],
)
async def perform_action(
    action: ActionRequest,
    client: HomeAssistantClientDependency,
) -> ActionResult:
    """Validate, simulate, or execute one controlled service call."""
    log = logger.bind(
        domain=action.domain,
        service=action.service,
        entity_id=action.entity_id,
        dry_run=action.dry_run,
        data_keys=sorted(action.data),
    )

    try:
        validate_action(action)
    except ActionPolicyError as exc:
        log.warning("Home Assistant action rejected: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    if action.dry_run:
        log.info("Home Assistant action simulated")
        return ActionResult(
            status="simulated",
            domain=action.domain,
            service=action.service,
            entity_id=action.entity_id,
            data=action.data,
        )

    try:
        response = await client.call_service(
            action.domain,
            action.service,
            entity_id=action.entity_id,
            data=action.data,
        )
    except HomeAssistantError as exc:
        log.error("Home Assistant action failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    log.info("Home Assistant action executed")
    return ActionResult(
        status="executed",
        domain=action.domain,
        service=action.service,
        entity_id=action.entity_id,
        data=action.data,
        home_assistant_response=response,
    )
