from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status

from house_brain.config import Settings, get_settings
from house_brain.home_assistant import (
    EntityNotFoundError,
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
