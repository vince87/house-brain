import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.responses import Response

from house_brain.actions import (
    ActionPolicyError,
    ActionRequest,
    ActionResult,
    validate_action,
)
from house_brain.agent import (
    AgentRequest,
    AgentResponse,
    extract_explicit_entity_ids,
    run_agent,
)
from house_brain.auth import (
    API_KEY_HEADER,
    AUTHORIZATION_HEADER,
    api_key_from_headers,
    api_key_is_valid,
)
from house_brain.authorization import extract_authorization_codes
from house_brain.autonomy import AutonomyPolicyError
from house_brain.autonomy_admin import (
    AutonomyConfigurationInput,
    AutonomyPolicyWriteError,
    build_policy_yaml,
    public_configuration,
    save_policy_with_backup,
)
from house_brain.autonomy_web import autonomy_page
from house_brain.config import Settings, get_settings
from house_brain.conversations import ConversationMessage, ConversationStore
from house_brain.events import (
    AgentEventRequest,
    AgentEventResponse,
    AutonomousExecutionDisabledError,
    EventMode,
    EventRecord,
    EventStore,
    build_event_message,
    validate_execution_enabled,
)
from house_brain.home_assistant import (
    EntityNotFoundError,
    HistoryNotFoundError,
    HomeAssistantClient,
    HomeAssistantEntity,
    HomeAssistantError,
)
from house_brain.mcp_server import mcp_app, mcp_server
from house_brain.memory import MemoryInput, MemoryRecord, MemoryStore
from house_brain.memory_web import memory_page
from house_brain.ollama import OllamaClient, OllamaError, OllamaStatus
from house_brain.service_catalog import ServiceCatalogError
from house_brain.web_chat import chat_page

APP_NAME = "House Brain"
APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration before accepting requests."""
    get_settings()
    async with mcp_server.session_manager.run():
        yield


PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/chat",
        "/autonomy",
        "/memories",
    }
)

AUTONOMY_WRITE_LOCK = asyncio.Lock()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="AI middleware between LLMs and Home Assistant.",
    lifespan=lifespan,
)


def custom_openapi() -> dict[str, object]:
    """Expose API-key authentication in Swagger without weakening middleware."""
    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    components = schema.setdefault("components", {})
    security_schemes = components.setdefault("securitySchemes", {})
    security_schemes["HouseBrainApiKey"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    schema["security"] = [{"HouseBrainApiKey": []}]
    schema["paths"]["/health"]["get"]["security"] = []
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.middleware("http")
async def authenticate_api_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Require an API key for operations while leaving docs and health public."""
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    settings = get_settings()
    provided = api_key_from_headers(
        request.headers.get(API_KEY_HEADER),
        request.headers.get(AUTHORIZATION_HEADER),
    )
    if not api_key_is_valid(provided, settings.api_key):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid or missing API key"},
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return await call_next(request)


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


def get_event_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EventStore:
    return EventStore(settings.memory_database_path)


EventStoreDependency = Annotated[EventStore, Depends(get_event_store)]


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return the service health status."""
    return {
        "status": "ok",
        "service": "house-brain",
        "version": APP_VERSION,
    }


@app.get("/chat", include_in_schema=False)
async def web_chat(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the browser chat shell; API calls still require X-API-Key."""
    return chat_page(settings.house_brain_language)


@app.get("/autonomy", include_in_schema=False)
async def web_autonomy(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the policy configurator shell; its data API remains protected."""
    return autonomy_page(settings.house_brain_language)


@app.get("/memories", include_in_schema=False)
async def web_memories(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the authenticated persistent-memory manager shell."""
    return memory_page(settings.house_brain_language)


@app.get("/admin/autonomy", tags=["administration"])
async def get_autonomy_configuration(
    client: HomeAssistantClientDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Return editable policy state without exposing configured codes."""
    try:
        entities = await client.list_entities_for_configuration()
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    known_entities = {str(item["entity_id"]) for item in entities}
    configured_entities = (
        settings.autonomy_policy.included_entities
        | settings.autonomy_policy.visibility.exclude_entities
    )
    for entity_id in sorted(configured_entities - known_entities):
        entities.append(
            {
                "entity_id": entity_id,
                "domain": entity_id.partition(".")[0],
                "friendly_name": entity_id,
                "state": "unavailable",
            }
        )
    entities.sort(key=lambda item: str(item["entity_id"]))
    return {
        "configuration": public_configuration(settings.autonomy_policy),
        "entities": entities,
    }


@app.put("/admin/autonomy", tags=["administration"])
async def update_autonomy_configuration(
    request: AutonomyConfigurationInput,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Validate and atomically replace autonomy.yaml with a recoverable backup."""
    async with AUTONOMY_WRITE_LOCK:
        try:
            content = build_policy_yaml(request, settings.autonomy_policy)
            await asyncio.to_thread(
                save_policy_with_backup,
                settings.autonomy_policy_path,
                content,
                settings.autonomy_backup_path,
            )
            get_settings.cache_clear()
            updated = get_settings().autonomy_policy
        except AutonomyPolicyError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        except AutonomyPolicyWriteError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
    return {
        "status": "saved",
        "backup_created": True,
        "configuration": public_configuration(updated),
    }


@app.get("/services", tags=["home-assistant"])
async def list_home_assistant_services(
    client: HomeAssistantClientDependency,
    domain: str | None = None,
) -> list[dict[str, object]]:
    """Return the cached Home Assistant service contract."""
    try:
        return await client.list_services(domain)
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.get("/auth/check", tags=["system"])
async def check_authentication() -> dict[str, bool]:
    """Confirm that middleware accepted the supplied API key."""
    return {"authenticated": True}


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
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        ) from exc
    except HistoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No state found for {entity_id} in the previous {search_hours} hours"
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
    settings: Annotated[Settings, Depends(get_settings)],
    authorization_code: Annotated[
        str | None,
        Header(alias="X-Authorization-Code"),
    ] = None,
    home_assistant_code: Annotated[
        str | None,
        Header(alias="X-Home-Assistant-Code"),
    ] = None,
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
        visibility_validator = getattr(client, "ensure_visible", None)
        if visibility_validator is not None:
            visibility_validator(action.entity_id)
        validate_action(action, policy_controlled=True)
        policy = settings.autonomy_policy.resolve_chat()
        if policy is None:
            raise AutonomyPolicyError("No entity control policy is configured")
        policy.validate_action(
            action,
            authorization_codes=((authorization_code,) if authorization_code else ()),
        )
        if not action.dry_run and not settings.autonomous_execution_enabled:
            raise AutonomyPolicyError(
                "Autonomous execution is disabled by the global kill switch"
            )
        supplied_codes = tuple(
            code
            for code in (authorization_code, home_assistant_code)
            if code is not None
        )
        service_preparer = getattr(client, "prepare_service_data", None)
        if service_preparer is not None:
            service_data = await service_preparer(
                action.domain,
                action.service,
                action.entity_id,
                action.data,
                supplied_codes=supplied_codes,
            )
        else:
            service_validator = getattr(client, "validate_service_call", None)
            if service_validator is not None:
                await service_validator(action.domain, action.service, action.data)
            service_data = dict(action.data)
    except EntityNotFoundError as exc:
        log.warning("Hidden Home Assistant action target rejected")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {action.entity_id}",
        ) from exc
    except (ActionPolicyError, AutonomyPolicyError, ServiceCatalogError) as exc:
        log.warning("Home Assistant action rejected: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except HomeAssistantError as exc:
        log.error("Home Assistant action validation failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    if action.dry_run:
        log.info("Home Assistant action simulated")
        return ActionResult(
            status="simulated",
            domain=action.domain,
            service=action.service,
            entity_id=action.entity_id,
            data=_public_action_data(action.data),
        )

    try:
        response = await client.call_service(
            action.domain,
            action.service,
            entity_id=action.entity_id,
            data=service_data,
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
        data=_public_action_data(action.data),
        home_assistant_response=response,
    )


def _public_action_data(data: dict[str, object]) -> dict[str, object]:
    """Never echo device or policy authorization secrets in API responses."""
    return {
        key: value
        for key, value in data.items()
        if key not in {"code", "authorization_code"}
    }


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
    sanitized_message, authorization_codes = extract_authorization_codes(
        request.message
    )
    sanitized_request = request.model_copy(update={"message": sanitized_message})
    chat_policy = settings.autonomy_policy.resolve_chat()
    try:
        return await run_agent(
            sanitized_request,
            settings,
            client,
            store,
            conversations,
            autonomy_policy=chat_policy,
            authorization_codes=authorization_codes,
            explicit_entity_ids=extract_explicit_entity_ids(sanitized_request.message),
        )
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
    limit: Annotated[int, Query(ge=1, le=5000)] = 10,
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


@app.post(
    "/agent/events",
    response_model=AgentEventResponse,
    tags=["events"],
)
async def handle_agent_event(
    event: AgentEventRequest,
    client: HomeAssistantClientDependency,
    memories: MemoryStoreDependency,
    conversations: ConversationStoreDependency,
    events: EventStoreDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentEventResponse:
    """Evaluate one event under the selected server mode."""
    event_id = uuid4().hex
    sanitized_instruction, authorization_codes = extract_authorization_codes(
        event.instruction
    )
    sanitized_event = event.model_copy(update={"instruction": sanitized_instruction})
    try:
        validate_execution_enabled(
            event.mode,
            settings.autonomous_execution_enabled,
        )
    except AutonomousExecutionDisabledError as exc:
        await asyncio.to_thread(
            events.record,
            event_id,
            sanitized_event,
            status="failed",
            response=str(exc),
            tools_used=[],
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    try:
        policy = settings.autonomy_policy.resolve(
            event.event_type,
            event.mode,
        )
        policy.validate_event(event.event_type)
        if event.mode == "execute":
            policy.validate_execute_event(event.event_type)
    except AutonomyPolicyError as exc:
        await asyncio.to_thread(
            events.record,
            event_id,
            sanitized_event,
            status="failed",
            response=str(exc),
            tools_used=[],
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    message = build_event_message(sanitized_event)
    request = AgentRequest(
        message=message,
        session_id=f"event-{event_id}",
    )
    try:
        result = await run_agent(
            request,
            settings,
            client,
            memories,
            conversations,
            action_mode=event.mode,
            autonomy_policy=policy,
            persist_conversation=False,
            authorization_codes=authorization_codes,
            explicit_entity_ids=extract_explicit_entity_ids(
                sanitized_event.instruction
            ),
        )
    except OllamaError as exc:
        await asyncio.to_thread(
            events.record,
            event_id,
            sanitized_event,
            status="failed",
            response=str(exc),
            tools_used=[],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    await asyncio.to_thread(
        events.record,
        event_id,
        sanitized_event,
        status="completed",
        response=result.response,
        tools_used=result.tools_used,
        tool_trace=result.tool_trace,
    )
    return AgentEventResponse(
        event_id=event_id,
        mode=event.mode,
        status="completed",
        response=result.response,
        model=result.model,
        iterations=result.iterations,
        tools_used=result.tools_used,
        tool_trace=result.tool_trace,
    )


@app.get(
    "/events/{event_id}",
    response_model=EventRecord,
    tags=["events"],
)
async def get_agent_event(
    event_id: str,
    events: EventStoreDependency,
) -> EventRecord:
    """Return one event with its sanitized decision trace."""
    record = await asyncio.to_thread(events.get, event_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event not found: {event_id}",
        )
    return record


@app.get(
    "/events",
    response_model=list[EventRecord],
    tags=["events"],
)
async def list_agent_events(
    events: EventStoreDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    mode: EventMode | None = None,
) -> list[EventRecord]:
    """Return the persistent audit log of autonomous events."""
    return await asyncio.to_thread(events.list, limit=limit, mode=mode)


app.mount("/mcp", mcp_app, name="mcp")
