import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, AsyncIterator

from mcp.server import MCPServer
from pydantic import Field

from house_brain.config import get_settings
from house_brain.home_assistant import HomeAssistantClient
from house_brain.memory import MemoryInput, MemoryStore, memory_store_for
from house_brain.version import APP_VERSION

mcp_server = MCPServer(
    "house-brain",
    title="House Brain",
    description="Home Assistant read tools and persistent House Brain memory.",
    instructions=(
        "Use these tools to read Home Assistant state and history and manage "
        "persistent memories. Hidden entities are unavailable. This server "
        "cannot perform Home Assistant actions."
    ),
    version=APP_VERSION,
)


@asynccontextmanager
async def open_home_assistant_client() -> AsyncIterator[HomeAssistantClient]:
    async with HomeAssistantClient(get_settings()) as client:
        yield client


@mcp_server.tool()
async def get_entity(entity_id: str) -> dict[str, object]:
    """Return the current state of one visible Home Assistant entity."""
    async with open_home_assistant_client() as client:
        entity = await client.get_entity(entity_id)
    return entity.model_dump(mode="json")


@mcp_server.tool()
async def search_entities(
    query: str,
    domain: str | None = None,
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
) -> list[dict[str, str]]:
    """Search visible Home Assistant entities by id or friendly name."""
    async with open_home_assistant_client() as client:
        return await client.search_entities(
            query,
            domain=domain,
            limit=limit,
        )


@mcp_server.tool()
async def list_entities(
    domains: list[str],
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
) -> list[dict[str, object]]:
    """List a compact state snapshot for the requested entity domains."""
    async with open_home_assistant_client() as client:
        return await client.list_entities(
            domains=set(domains),
            limit=limit,
        )


@mcp_server.tool()
async def list_services(domain: str | None = None) -> list[dict[str, object]]:
    """List current Home Assistant services and parameter constraints."""
    async with open_home_assistant_client() as client:
        return await client.list_services(domain)


@mcp_server.tool()
async def get_history(
    entity_id: str,
    minutes: Annotated[int, Field(ge=1, le=10_080)] = 60,
) -> list[dict[str, object]]:
    """Return recent Recorder history for one visible entity."""
    end = datetime.now(UTC)
    start = end - timedelta(minutes=minutes)
    async with open_home_assistant_client() as client:
        history = await client.get_history(
            entity_id,
            start=start,
            end=end,
        )
    return [entity.model_dump(mode="json") for entity in history]


def get_memory_store() -> MemoryStore:
    """Return the persistent memory store configured for House Brain."""
    return memory_store_for(get_settings().memory_database_path)


@mcp_server.tool()
async def remember_memory(
    key: str,
    value: str,
    category: str = "fact",
    importance: Annotated[int, Field(ge=1, le=10)] = 5,
) -> dict[str, object]:
    """Create or update one persistent memory by key."""
    memory = MemoryInput(
        key=key,
        value=value,
        category=category,
        importance=importance,
    )
    record = await asyncio.to_thread(
        get_memory_store().remember,
        memory,
    )
    return record.model_dump(mode="json")


@mcp_server.tool()
async def search_memories(
    query: str | None = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 10,
    deleted: bool = False,
) -> list[dict[str, object]]:
    """Search active memories or inspect the recoverable trash."""
    records = await asyncio.to_thread(
        get_memory_store().search,
        query,
        limit=limit,
        deleted=deleted,
    )
    return [record.model_dump(mode="json") for record in records]


@mcp_server.tool()
async def forget_memory(key: str) -> dict[str, bool]:
    """Move one memory to the recoverable trash."""
    deleted = await asyncio.to_thread(
        get_memory_store().forget,
        key,
    )
    return {"deleted": deleted}


@mcp_server.tool()
async def restore_memory(key: str) -> dict[str, bool]:
    """Restore one memory from the recoverable trash."""
    restored = await asyncio.to_thread(
        get_memory_store().restore,
        key,
    )
    return {"restored": restored}


mcp_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    host="0.0.0.0",
)
