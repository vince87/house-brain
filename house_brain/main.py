import asyncio
import os
import tempfile
import zipfile
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from sqlite3 import Error as SQLiteError
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask
from starlette.responses import FileResponse, Response

from house_brain.action_plan_web import action_plan_page
from house_brain.action_plans import (
    ActionPlanConflictError,
    ActionPlanInput,
    ActionPlanRecord,
    ActionPlanRequest,
    ActionPlanStore,
    PlannedActionInput,
    PlannedActionRecord,
    action_plan_store_for,
    actions_from_simulation_trace,
    entity_matches_plan,
    planned_action,
)
from house_brain.actions import (
    ActionPolicyError,
    ActionRequest,
    ActionResult,
    redact_action_data,
    validate_action,
)
from house_brain.agent import (
    AgentRequest,
    AgentResponse,
    extract_explicit_entity_ids,
    run_agent,
)
from house_brain.audit_web import audit_page
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
from house_brain.context_views import (
    ContextViewCatalog,
    ContextViewError,
    save_context_views_with_backup,
)
from house_brain.context_views_web import context_views_page
from house_brain.conversations import (
    ConversationMessage,
    ConversationStore,
    conversation_store_for,
)
from house_brain.database import connect_database
from house_brain.diagnostics_web import diagnostics_page
from house_brain.events import (
    AgentEventRequest,
    AgentEventResponse,
    AutonomousExecutionDisabledError,
    EventMode,
    EventRecord,
    EventStore,
    build_event_message,
    event_store_for,
    validate_execution_enabled,
)
from house_brain.home_assistant import (
    EntityNotFoundError,
    HistoryNotFoundError,
    HomeAssistantClient,
    HomeAssistantEntity,
    HomeAssistantError,
)
from house_brain.home_context import HomeContextPage
from house_brain.installation import (
    MAX_ARCHIVE_BYTES,
    InstallationLifecycleError,
    apply_installation_restore,
    create_installation_backup,
    inspect_installation_backup,
    installation_status,
)
from house_brain.installation_web import installation_page
from house_brain.logs_web import logs_page
from house_brain.mcp_server import mcp_app, mcp_server
from house_brain.memory import (
    MemoryContextRecord,
    MemoryEntityReference,
    MemoryInput,
    MemoryRecord,
    MemoryStore,
    memory_store_for,
)
from house_brain.memory_web import memory_page
from house_brain.ollama import OllamaClient, OllamaError
from house_brain.openai import OpenAIClient
from house_brain.provider_runtime import provider_metrics
from house_brain.runtime_logs import (
    RuntimeLogRecord,
    install_runtime_log_sink,
    install_standard_log_sink,
    remove_standard_log_sink,
    runtime_log_buffer,
)
from house_brain.service_catalog import ServiceCatalogError
from house_brain.version import APP_VERSION
from house_brain.web_chat import chat_page

APP_NAME = "House Brain"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration before accepting requests."""
    get_settings()
    sink_id = install_runtime_log_sink(runtime_log_buffer)
    standard_handler, standard_loggers = install_standard_log_sink(runtime_log_buffer)
    try:
        async with mcp_server.session_manager.run():
            yield
    finally:
        remove_standard_log_sink(standard_handler, standard_loggers)
        logger.remove(sink_id)


PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/chat",
        "/autonomy",
        "/context-views",
        "/audit",
        "/memories",
        "/plans",
        "/logs",
        "/system",
        "/installation",
    }
)

AUTONOMY_WRITE_LOCK = asyncio.Lock()
CONTEXT_VIEWS_WRITE_LOCK = asyncio.Lock()
INSTALLATION_WRITE_LOCK = asyncio.Lock()
INSTALLATION_RESTORE_ACTIVE = False


def _clear_persistent_store_caches() -> None:
    """Discard stores initialized against files replaced by a restore."""
    action_plan_store_for.cache_clear()
    conversation_store_for.cache_clear()
    event_store_for.cache_clear()
    memory_store_for.cache_clear()
    get_settings.cache_clear()


def _record_installation_audit(
    settings: Settings,
    operation: str,
    *,
    outcome: str,
    context: dict[str, object],
) -> None:
    """Persist a redacted administrative lifecycle event."""
    try:
        request = AgentEventRequest(
            event_type=f"installation.{operation}",
            source="administration",
            mode="observe",
            instruction=f"Installation lifecycle operation: {operation}",
            context={"operation": operation, **context},
        )
        event_store_for(settings.memory_database_path).record(
            uuid4().hex,
            request,
            status="completed" if outcome == "completed" else "failed",
            response=outcome,
            tools_used=[],
            tool_trace=[],
        )
    except Exception:
        logger.exception(
            "Installation lifecycle audit persistence failed: operation={}",
            operation,
        )


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
    if (
        INSTALLATION_RESTORE_ACTIVE
        and request.url.path != "/health"
        and not request.url.path.startswith("/admin/installation/restores/apply")
    ):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Installation restore is in progress"},
            headers={"Retry-After": "5"},
        )
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
    return memory_store_for(settings.memory_database_path)


MemoryStoreDependency = Annotated[MemoryStore, Depends(get_memory_store)]


def get_conversation_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationStore:
    return conversation_store_for(settings.memory_database_path)


ConversationStoreDependency = Annotated[
    ConversationStore,
    Depends(get_conversation_store),
]


def get_event_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EventStore:
    return event_store_for(settings.memory_database_path)


EventStoreDependency = Annotated[EventStore, Depends(get_event_store)]


def get_action_plan_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionPlanStore:
    return action_plan_store_for(settings.memory_database_path)


ActionPlanStoreDependency = Annotated[
    ActionPlanStore,
    Depends(get_action_plan_store),
]


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


@app.get("/context-views", include_in_schema=False)
async def web_context_views(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the authenticated context-view manager shell."""
    return context_views_page(settings.house_brain_language)


@app.get("/memories", include_in_schema=False)
async def web_memories(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the authenticated persistent-memory manager shell."""
    return memory_page(settings.house_brain_language)


@app.get("/audit", include_in_schema=False)
async def web_audit(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the authenticated persistent action-audit viewer shell."""
    return audit_page(settings.house_brain_language)


@app.get("/plans", include_in_schema=False)
async def web_action_plans(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the authenticated action-plan review shell."""
    return action_plan_page(settings.house_brain_language)


@app.get("/logs", include_in_schema=False)
async def web_logs(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the authenticated in-memory application-log viewer shell."""
    return logs_page(settings.house_brain_language)


@app.get("/system", include_in_schema=False)
async def web_diagnostics(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the authenticated operational diagnostics shell."""
    return diagnostics_page(settings.house_brain_language)


@app.get("/installation", include_in_schema=False)
async def web_installation(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Serve the authenticated installation lifecycle shell."""
    return installation_page(settings.house_brain_language)


class InstallationRestoreApplyRequest(BaseModel):
    """Require an inspected token and explicit destructive confirmation."""

    model_config = ConfigDict(extra="forbid")

    restore_token: str = Field(min_length=20, max_length=200)
    confirmation: Literal["RESTORE"]


@app.get("/admin/installation", tags=["administration"])
async def get_installation_status(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Return secret-free local installation readiness and lifecycle state."""
    try:
        return await asyncio.to_thread(installation_status, settings)
    except InstallationLifecycleError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@app.post("/admin/installation/backups", tags=["administration"])
async def download_installation_backup(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Create and download a coherent, validated persistent-state archive."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="house-brain-config-",
        suffix=".zip",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    try:
        async with INSTALLATION_WRITE_LOCK, AUTONOMY_WRITE_LOCK:
            manifest = await asyncio.to_thread(
                create_installation_backup,
                settings,
                temporary,
            )
        logger.info(
            "Installation backup created: files={} format_version={}",
            len(manifest["files"]),
            manifest["format_version"],
        )
        await asyncio.to_thread(
            _record_installation_audit,
            settings,
            "backup",
            outcome="completed",
            context={
                "files": len(manifest["files"]),
                "format_version": manifest["format_version"],
            },
        )
        return FileResponse(
            temporary,
            media_type="application/zip",
            filename=f"house-brain-config-{timestamp}.zip",
            background=BackgroundTask(temporary.unlink, missing_ok=True),
        )
    except InstallationLifecycleError as exc:
        temporary.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


@app.post("/admin/installation/restores/inspect", tags=["administration"])
async def inspect_installation_restore(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Stage and validate a raw ZIP upload without changing persistent files."""
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="house-brain-upload-",
        suffix=".zip",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    received = 0
    try:
        with temporary.open("wb") as destination:
            async for chunk in request.stream():
                received += len(chunk)
                if received > MAX_ARCHIVE_BYTES:
                    raise InstallationLifecycleError(
                        "Restore archive exceeds the size limit"
                    )
                destination.write(chunk)
        if received == 0:
            raise InstallationLifecycleError("Restore archive is empty")
        staged = await asyncio.to_thread(
            inspect_installation_backup,
            temporary,
            settings,
        )
        logger.info(
            "Installation restore inspected: files={} format_version={}",
            len(staged.files),
            staged.manifest["format_version"],
        )
        await asyncio.to_thread(
            _record_installation_audit,
            settings,
            "restore_inspect",
            outcome="completed",
            context={
                "files": len(staged.files),
                "format_version": staged.manifest["format_version"],
            },
        )
        return {
            "status": "validated",
            "restore_token": staged.token,
            "expires_at": staged.expires_at.isoformat(),
            "source_version": staged.manifest.get("house_brain_version"),
            "installation_schema_version": staged.manifest.get(
                "installation_schema_version"
            ),
            "files": list(staged.files),
        }
    except (InstallationLifecycleError, zipfile.BadZipFile) as exc:
        await asyncio.to_thread(
            _record_installation_audit,
            settings,
            "restore_inspect",
            outcome="failed",
            context={"error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)


@app.post("/admin/installation/restores/apply", tags=["administration"])
async def apply_staged_installation_restore(
    request: InstallationRestoreApplyRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Apply a validated restore under maintenance mode with rollback."""
    global INSTALLATION_RESTORE_ACTIVE
    async with INSTALLATION_WRITE_LOCK, AUTONOMY_WRITE_LOCK:
        INSTALLATION_RESTORE_ACTIVE = True
        try:
            result = await asyncio.to_thread(
                apply_installation_restore,
                request.restore_token,
                settings,
            )
            _clear_persistent_store_caches()
            logger.warning(
                "Installation restore completed: files={} restart_recommended={}",
                result["files_restored"],
                result["restart_recommended"],
            )
            await asyncio.to_thread(
                _record_installation_audit,
                settings,
                "restore",
                outcome="completed",
                context={
                    "files": result["files_restored"],
                    "restart_recommended": result["restart_recommended"],
                },
            )
            return result
        except InstallationLifecycleError as exc:
            logger.error("Installation restore rejected or failed: {}", exc)
            await asyncio.to_thread(
                _record_installation_audit,
                settings,
                "restore",
                outcome="failed",
                context={"error_type": type(exc).__name__},
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        finally:
            INSTALLATION_RESTORE_ACTIVE = False


@app.get("/runtime-logs", response_model=list[RuntimeLogRecord], tags=["system"])
async def get_runtime_logs(
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    level: Annotated[
        str | None,
        Query(pattern="^(INFO|WARNING|ERROR|CRITICAL)$"),
    ] = None,
    query: Annotated[str | None, Query(max_length=200)] = None,
) -> list[RuntimeLogRecord]:
    """Return bounded, credential-redacted House Brain application logs."""
    return runtime_log_buffer.list(
        settings,
        limit=limit,
        level=level,
        query=query,
    )


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
    hidden_entities_loader = getattr(client, "hidden_entity_ids", None)
    hidden_entities = (
        await hidden_entities_loader()
        if hidden_entities_loader is not None
        else frozenset()
    )
    configured_entities = (
        settings.autonomy_policy.visible_entities
        | settings.autonomy_policy.included_entities
    ) - hidden_entities
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


@app.get("/admin/context-views", tags=["administration"])
async def get_context_view_configuration(
    client: HomeAssistantClientDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Return editable views and policy-visible selector metadata."""
    try:
        entities = await client.list_entities_for_configuration()
        hidden_entities = await client.hidden_entity_ids()
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    allowed = (
        settings.autonomy_policy.visible_entities
        | settings.autonomy_policy.included_entities
    ) - hidden_entities
    visible_entities = [
        item for item in entities if str(item.get("entity_id")) in allowed
    ]
    return {
        "configuration": settings.context_views.model_dump(mode="json"),
        "entities": visible_entities,
        "areas": sorted(
            {
                str(item["area_id"])
                for item in visible_entities
                if item.get("area_id")
            }
        ),
        "domains": sorted(
            {
                str(item["domain"])
                for item in visible_entities
                if item.get("domain")
            }
        ),
    }


@app.put("/admin/context-views", tags=["administration"])
async def update_context_view_configuration(
    request: ContextViewCatalog,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Validate and atomically replace logical context views."""
    async with CONTEXT_VIEWS_WRITE_LOCK:
        try:
            backup = await asyncio.to_thread(
                save_context_views_with_backup,
                settings.context_views_path,
                request,
                settings.autonomy_backup_path,
            )
            get_settings.cache_clear()
            updated = get_settings().context_views
        except ContextViewError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
    return {
        "status": "saved",
        "backup_created": backup is not None,
        "configuration": updated.model_dump(mode="json"),
    }


@app.get(
    "/admin/context-views/{view_id}/preview",
    response_model=HomeContextPage,
    tags=["administration"],
)
async def preview_context_view(
    view_id: str,
    client: HomeAssistantClientDependency,
    controllable_only: bool = False,
) -> HomeContextPage:
    """Preview the effective policy-safe entity selection for one view."""
    try:
        return await client.get_home_context(
            view_id=view_id,
            controllable_only=controllable_only,
            limit=100,
        )
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


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
    "/context",
    response_model=HomeContextPage,
    tags=["home-assistant"],
)
async def get_home_context(
    client: HomeAssistantClientDependency,
    domains: Annotated[list[str] | None, Query()] = None,
    areas: Annotated[list[str] | None, Query()] = None,
    query: Annotated[str | None, Query(max_length=200)] = None,
    controllable_only: bool = False,
    view_id: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> HomeContextPage:
    """Return policy-visible states enriched with HA registry relationships."""
    normalized_domains = {
        item.strip().lower() for item in domains or [] if item.strip()
    }
    normalized_areas = {item.strip() for item in areas or [] if item.strip()}
    if len(normalized_domains) > 8 or any(
        "." in domain for domain in normalized_domains
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="domains must contain at most 8 valid domains",
        )
    if len(normalized_areas) > 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="areas must contain at most 8 values",
        )
    try:
        return await client.get_home_context(
            domains=normalized_domains or None,
            areas=normalized_areas or None,
            query=query,
            controllable_only=controllable_only,
            view_id=view_id,
            limit=limit,
            offset=offset,
        )
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


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
        registry_validator = getattr(client, "ensure_accessible", None)
        if registry_validator is not None:
            await registry_validator(action.entity_id)
        else:
            visibility_validator = getattr(client, "ensure_visible", None)
            if visibility_validator is not None:
                visibility_validator(action.entity_id)
        validate_action(action)
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
            data=redact_action_data(action.data),
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
        data=redact_action_data(action.data),
        home_assistant_response=response,
    )


@app.post(
    "/action-plans",
    response_model=ActionPlanRecord,
    tags=["home-assistant"],
)
async def create_action_plan(
    request: ActionPlanInput,
    client: HomeAssistantClientDependency,
    store: ActionPlanStoreDependency,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization_code: Annotated[
        str | None,
        Header(alias="X-Authorization-Code"),
    ] = None,
    home_assistant_code: Annotated[
        str | None,
        Header(alias="X-Home-Assistant-Code"),
    ] = None,
) -> ActionPlanRecord:
    """Validate and persist an expiring action preview without executing it."""
    try:
        records, _ = await _validate_planned_actions(
            request.actions,
            client,
            settings,
            authorization_code=authorization_code,
            home_assistant_code=home_assistant_code,
        )
        return await asyncio.to_thread(
            store.create,
            records,
            expires_in_seconds=request.expires_in_seconds,
            execution_enabled=settings.autonomous_execution_enabled,
        )
    except EntityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action plan target was not found",
        ) from exc
    except (
        ActionPolicyError,
        AutonomyPolicyError,
        ServiceCatalogError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.post(
    "/action-plans/from-request",
    response_model=ActionPlanRecord,
    tags=["home-assistant"],
)
async def propose_action_plan_from_request(
    request: ActionPlanRequest,
    client: HomeAssistantClientDependency,
    memories: MemoryStoreDependency,
    conversations: ConversationStoreDependency,
    store: ActionPlanStoreDependency,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization_code: Annotated[
        str | None,
        Header(alias="X-Authorization-Code"),
    ] = None,
    home_assistant_code: Annotated[
        str | None,
        Header(alias="X-Home-Assistant-Code"),
    ] = None,
) -> ActionPlanRecord:
    """Create a plan solely from actions confirmed by a simulated tool trace."""
    sanitized_instruction, extracted_codes = extract_authorization_codes(
        request.instruction
    )
    authorization_codes = tuple(
        dict.fromkeys(
            code
            for code in (
                *extracted_codes,
                authorization_code,
                home_assistant_code,
            )
            if code
        )
    )
    if not sanitized_instruction.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The action plan instruction is empty",
        )
    request_settings = settings.model_copy(
        update={
            "house_brain_language": (request.language or settings.house_brain_language),
        }
    )
    policy = settings.autonomy_policy.resolve_chat()
    try:
        result = await run_agent(
            AgentRequest(
                message=sanitized_instruction,
                session_id=f"plan-{uuid4().hex}",
            ),
            request_settings,
            client,
            memories,
            conversations,
            action_mode="simulate",
            autonomy_policy=policy,
            persist_conversation=False,
            authorization_codes=authorization_codes,
            explicit_entity_ids=extract_explicit_entity_ids(sanitized_instruction),
        )
        actions = actions_from_simulation_trace(
            result.tool_trace,
            reason=sanitized_instruction,
        )
        if not actions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The simulated request produced no actionable plan",
            )
        records, _ = await _validate_planned_actions(
            actions,
            client,
            settings,
            authorization_code=(
                authorization_code or (extracted_codes[0] if extracted_codes else None)
            ),
            home_assistant_code=(
                home_assistant_code or (extracted_codes[0] if extracted_codes else None)
            ),
        )
        return await asyncio.to_thread(
            store.create,
            records,
            expires_in_seconds=request.expires_in_seconds,
            execution_enabled=settings.autonomous_execution_enabled,
        )
    except HTTPException:
        raise
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except (
        ActionPolicyError,
        AutonomyPolicyError,
        ServiceCatalogError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except HomeAssistantError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.get(
    "/action-plans",
    response_model=list[ActionPlanRecord],
    tags=["home-assistant"],
)
async def list_action_plans(
    store: ActionPlanStoreDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ActionPlanRecord]:
    return await asyncio.to_thread(store.list, limit=limit)


@app.get(
    "/action-plans/{plan_id}",
    response_model=ActionPlanRecord,
    tags=["home-assistant"],
)
async def get_action_plan(
    plan_id: str,
    store: ActionPlanStoreDependency,
) -> ActionPlanRecord:
    record = await asyncio.to_thread(store.get, plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Action plan was not found")
    return record


@app.post(
    "/action-plans/{plan_id}/reject",
    response_model=ActionPlanRecord,
    tags=["home-assistant"],
)
async def reject_action_plan(
    plan_id: str,
    store: ActionPlanStoreDependency,
) -> ActionPlanRecord:
    try:
        return await asyncio.to_thread(store.reject, plan_id)
    except ActionPlanConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/action-plans/{plan_id}/approve",
    response_model=ActionPlanRecord,
    tags=["home-assistant"],
)
async def approve_action_plan(
    plan_id: str,
    client: HomeAssistantClientDependency,
    store: ActionPlanStoreDependency,
    settings: Annotated[Settings, Depends(get_settings)],
    authorization_code: Annotated[
        str | None,
        Header(alias="X-Authorization-Code"),
    ] = None,
    home_assistant_code: Annotated[
        str | None,
        Header(alias="X-Home-Assistant-Code"),
    ] = None,
) -> ActionPlanRecord:
    """Claim, revalidate, and execute one unchanged action plan exactly once."""
    outcomes: list[ActionResult] = []
    try:
        record = await asyncio.to_thread(store.claim, plan_id)
    except ActionPlanConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not settings.autonomous_execution_enabled:
        await asyncio.to_thread(
            store.finish,
            plan_id,
            status="failed",
            error="Autonomous execution is disabled by the global kill switch",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Autonomous execution is disabled by the global kill switch",
        )

    try:
        for item in record.actions:
            entity = await client.get_entity(item.entity_id)
            if not entity_matches_plan(item, entity):
                await asyncio.to_thread(
                    store.finish,
                    plan_id,
                    status="invalidated",
                    error=f"Starting state changed: {item.entity_id}",
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Action plan starting state changed: {item.entity_id}",
                )

        _, prepared = await _validate_planned_actions(
            record.actions,
            client,
            settings,
            authorization_code=authorization_code,
            home_assistant_code=home_assistant_code,
        )
        for item, service_data in zip(record.actions, prepared, strict=True):
            response = await client.call_service(
                item.domain,
                item.service,
                entity_id=item.entity_id,
                data=service_data,
            )
            outcomes.append(
                ActionResult(
                    status="executed",
                    domain=item.domain,
                    service=item.service,
                    entity_id=item.entity_id,
                    data=redact_action_data(item.data),
                    home_assistant_response=response,
                )
            )
        return await asyncio.to_thread(
            store.finish,
            plan_id,
            status="executed",
            outcome=outcomes,
        )
    except HTTPException:
        raise
    except (
        ActionPolicyError,
        AutonomyPolicyError,
        ServiceCatalogError,
        ValueError,
    ) as exc:
        await asyncio.to_thread(
            store.finish,
            plan_id,
            status="failed",
            outcome=outcomes,
            error=str(exc),
        )
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HomeAssistantError as exc:
        await asyncio.to_thread(
            store.finish,
            plan_id,
            status="failed",
            outcome=outcomes,
            error=str(exc),
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _validate_planned_actions(
    actions: list[PlannedActionInput],
    client: HomeAssistantClient,
    settings: Settings,
    *,
    authorization_code: str | None,
    home_assistant_code: str | None,
) -> tuple[list[PlannedActionRecord], list[dict[str, object]]]:
    policy = settings.autonomy_policy.resolve_chat()
    if policy is None:
        raise AutonomyPolicyError("No entity control policy is configured")
    policy_codes = (authorization_code,) if authorization_code else ()
    supplied_codes = tuple(
        code for code in (authorization_code, home_assistant_code) if code is not None
    )
    records: list[PlannedActionRecord] = []
    prepared: list[dict[str, object]] = []
    for item in actions:
        action = item.action_request()
        validate_action(action)
        await client.ensure_accessible(action.entity_id)
        policy.validate_action(action, authorization_codes=policy_codes)
        service_data = await client.prepare_service_data(
            action.domain,
            action.service,
            action.entity_id,
            action.data,
            supplied_codes=supplied_codes,
        )
        entity = await client.get_entity(action.entity_id)
        records.append(planned_action(item, entity))
        prepared.append(service_data)
    return records, prepared


@app.get(
    "/llm/status",
    tags=["llm"],
)
async def get_llm_status(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Return connectivity and model availability for the selected provider."""
    try:
        if settings.llm_provider == "openai":
            async with OpenAIClient(settings) as client:
                return (await client.status()).model_dump(mode="json")
        async with OllamaClient(settings) as client:
            result = (await client.status()).model_dump(mode="json")
            result["provider"] = "ollama"
            return result
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@app.get("/diagnostics", tags=["system"])
async def get_system_diagnostics(
    client: HomeAssistantClientDependency,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Return safe component diagnostics without exposing credentials."""
    home_assistant: dict[str, object]
    model: dict[str, object]

    try:
        entities = await client.list_entities_for_configuration()
        hidden_entities = await client.hidden_entity_ids()
        services = await client.list_services()
        home_assistant = {
            "status": "ok",
            "catalog_entities": len(entities),
            "policy_visible_entities": len(
                settings.autonomy_policy.visibility.visible_entities
            ),
            "controllable_entities": len(
                settings.autonomy_policy.resolve_chat().included_entities
            ),
            "home_assistant_hidden_entities": len(hidden_entities),
            "services": len(services),
        }
    except HomeAssistantError as exc:
        home_assistant = {
            "status": "error",
            "error": str(exc),
        }

    try:
        model = await get_llm_status(settings)
        if not model.get("model_available"):
            model["status"] = "error"
            model["error"] = (
                "Configured Ollama model is not available"
                if settings.llm_provider == "ollama"
                else "Configured OpenAI model is not available"
            )
    except HTTPException as exc:
        configured_model = (
            settings.openai_model
            if settings.llm_provider == "openai"
            else settings.ollama_model
        )
        model = {
            "status": "error",
            "provider": settings.llm_provider,
            "configured_model": configured_model,
            "error": str(exc.detail),
        }

    persistence = await asyncio.to_thread(_persistence_diagnostics, settings)
    status_value = (
        "ok"
        if home_assistant["status"] == "ok"
        and model["status"] == "ok"
        and persistence["status"] == "ok"
        else "degraded"
    )
    return {
        "status": status_value,
        "version": APP_VERSION,
        "home_assistant": home_assistant,
        "llm": model,
        "provider_metrics": provider_metrics.snapshot(),
        "persistence": persistence,
        settings.llm_provider: model,
    }


def _persistence_diagnostics(settings: Settings) -> dict[str, object]:
    database = Path(settings.memory_database_path)
    policy = Path(settings.autonomy_policy_path)
    backups = Path(settings.autonomy_backup_path)
    try:
        with connect_database(database) as connection:
            integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        backup_count = sum(1 for item in backups.glob("*") if item.is_file())
        healthy = integrity == "ok" and policy.is_file() and backups.is_dir()
        return {
            "status": "ok" if healthy else "error",
            "database": {
                "exists": database.is_file(),
                "size_bytes": database.stat().st_size,
                "integrity": integrity,
            },
            "policy": {"exists": policy.is_file()},
            "backups": {
                "directory_exists": backups.is_dir(),
                "count": backup_count,
            },
        }
    except (OSError, SQLiteError, TypeError, ValueError) as exc:
        return {"status": "error", "error": type(exc).__name__}


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
    """Run a bounded provider-independent tool-calling loop."""
    try:
        if request.mode is not None:
            validate_execution_enabled(
                request.mode,
                settings.autonomous_execution_enabled,
            )
    except AutonomousExecutionDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    sanitized_message, authorization_codes = extract_authorization_codes(
        request.message
    )
    sanitized_request = request.model_copy(update={"message": sanitized_message})
    request_settings = settings.model_copy(
        update={
            "house_brain_language": request.language or settings.house_brain_language,
        }
    )
    chat_policy = settings.autonomy_policy.resolve_chat()
    try:
        return await run_agent(
            sanitized_request,
            request_settings,
            client,
            store,
            conversations,
            action_mode=request.mode,
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
    return await asyncio.to_thread(store.remember, memory, source="api")


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
    include_expired: bool = False,
) -> list[MemoryRecord]:
    """List or search persistent memories."""
    return await asyncio.to_thread(
        store.search,
        query,
        limit=limit,
        deleted=deleted,
        include_expired=include_expired,
    )


@app.get(
    "/memory/context",
    response_model=list[MemoryContextRecord],
    tags=["memory"],
)
async def search_memories_with_context(
    client: HomeAssistantClientDependency,
    store: MemoryStoreDependency,
    query: str | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 10,
    deleted: bool = False,
    include_expired: bool = False,
) -> list[MemoryContextRecord]:
    """List memories with current states for policy-visible entity references."""
    records = await asyncio.to_thread(
        store.search,
        query,
        limit=limit,
        deleted=deleted,
        include_expired=include_expired,
    )
    references = {
        record.id: sorted(extract_explicit_entity_ids(f"{record.key} {record.value}"))
        for record in records
    }
    entity_ids = sorted(
        {
            entity_id
            for record_references in references.values()
            for entity_id in record_references
        }
    )
    semaphore = asyncio.Semaphore(8)

    async def current_reference(entity_id: str) -> MemoryEntityReference:
        async with semaphore:
            try:
                entity = await client.get_entity(entity_id)
            except (EntityNotFoundError, HomeAssistantError):
                return MemoryEntityReference(entity_id=entity_id)
        return MemoryEntityReference(
            entity_id=entity.entity_id,
            name=str(entity.attributes.get("friendly_name", entity.entity_id)),
            state=entity.state,
            verified=True,
            home_assistant_path=f"/config/entities/entity/{entity.entity_id}",
        )

    current_states = {
        reference.entity_id: reference
        for reference in await asyncio.gather(
            *(current_reference(entity_id) for entity_id in entity_ids[:100])
        )
    }
    return [
        MemoryContextRecord.model_validate(
            {
                **record.model_dump(mode="python"),
                "referenced_entities": [
                    current_states.get(
                        entity_id,
                        MemoryEntityReference(entity_id=entity_id),
                    )
                    for entity_id in references[record.id]
                ],
            }
        )
        for record in records
    ]


@app.post("/memory/import", response_model=list[MemoryRecord], tags=["memory"])
async def import_memories(
    memories: Annotated[list[MemoryInput], Field(min_length=1, max_length=500)],
    store: MemoryStoreDependency,
) -> list[MemoryRecord]:
    """Import a bounded, validated set of active memories."""
    return [
        await asyncio.to_thread(store.remember, memory, source="import")
        for memory in memories
    ]


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
    request_settings = settings.model_copy(
        update={
            "house_brain_language": event.language or settings.house_brain_language,
        }
    )

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
            request_settings,
            client,
            memories,
            conversations,
            action_mode=event.mode,
            require_observation_evidence=event.mode == "observe",
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

