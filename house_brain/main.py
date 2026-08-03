import asyncio
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
from house_brain.agent import AgentRequest, AgentResponse, run_agent
from house_brain.config import Settings, get_settings
from house_brain.conversations import ConversationMessage, ConversationStore
from house_brain.home_assistant import (
    EntityNotFoundError,
    HistoryNotFoundError,
    HomeAssistantClient,
    HomeAssistantEntity,
    HomeAssistantError,
)
from house_brain.memory import MemoryInput, MemoryRecord, MemoryStore
from house_brain.ollama import OllamaClient, OllamaError, OllamaStatus

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


def get_memory_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> MemoryStore:
    return MemoryStore(settings.memory_database_path)


MemoryStoreDependency = Annotated[MemoryStore, Depends(get_memory_store)]


def get_conversation_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationStore:
    return ConversationStore(settings.memory_database_path)


ConversationStoreDependency = Annotated[
    ConversationStore,
    Depends(get_conversation_store),
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


@app.get(
    "/llm/status",
    response_model=OllamaStatus,
    tags=["llm"],
)
async def get_llm_status(
    settings: Annotated[Settings, Depends(get_settings)],
) -> OllamaStatus:
    """Return Ollama connectivity and configured-model availability."""
    try:
        async with OllamaClient(settings) as client:
            return await client.status()
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post(
    "/agent/chat",
    response_model=AgentResponse,
    tags=["llm"],
)
async def agent_chat(
    request: AgentRequest,
    client: HomeAssistantClientDependency,
    store: MemoryStoreDependency,
    conversations: ConversationStoreDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentResponse:
    """Run a bounded Ollama tool-calling loop."""
    try:
        return await run_agent(request, settings, client, store, conversations)
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post(
    "/memory",
    response_model=MemoryRecord,
    tags=["memory"],
)
async def remember(
    memory: MemoryInput,
    store: MemoryStoreDependency,
) -> MemoryRecord:
    """Create or update one persistent memory by key."""
    return await asyncio.to_thread(store.remember, memory)


@app.get(
    "/memory",
    response_model=list[MemoryRecord],
    tags=["memory"],
)
async def search_memories(
    store: MemoryStoreDependency,
    query: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    deleted: bool = False,
) -> list[MemoryRecord]:
    """List or search persistent memories."""
    return await asyncio.to_thread(
        store.search,
        query,
        limit=limit,
        deleted=deleted,
    )


@app.delete(
    "/memory/{key}",
    tags=["memory"],
)
async def forget_memory(
    key: str,
    store: MemoryStoreDependency,
) -> dict[str, bool]:
    """Move a memory to the recoverable trash."""
    deleted = await asyncio.to_thread(store.forget, key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory not found: {key}",
        )
    return {"deleted": True}


@app.post(
    "/memory/{key}/restore",
    tags=["memory"],
)
async def restore_memory(
    key: str,
    store: MemoryStoreDependency,
) -> dict[str, bool]:
    """Restore a memory from the trash."""
    restored = await asyncio.to_thread(store.restore, key)
    if not restored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deleted memory not found: {key}",
        )
    return {"restored": True}


@app.get(
    "/entity-catalog",
    tags=["home-assistant"],
)
async def search_entity_catalog(
    query: Annotated[str, Query(min_length=1, max_length=100)],
    client: HomeAssistantClientDependency,
    domain: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict[str, str]]:
    """Search compact Home Assistant entity metadata."""
    try:
        return await client.search_entities(
            query,
            domain=domain,
            limit=limit,
        )
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.get(
    "/conversations/{session_id}",
    response_model=list[ConversationMessage],
    tags=["conversations"],
)
async def get_conversation(
    session_id: str,
    store: ConversationStoreDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ConversationMessage]:
    """Return recent messages from one conversation session."""
    return await asyncio.to_thread(store.history, session_id, limit=limit)


@app.delete(
    "/conversations/{session_id}",
    tags=["conversations"],
)
async def clear_conversation(
    session_id: str,
    store: ConversationStoreDependency,
) -> dict[str, int]:
    """Permanently clear one conversation session."""
    deleted = await asyncio.to_thread(store.clear, session_id)
    return {"deleted_messages": deleted}
