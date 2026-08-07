from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, AsyncIterator

from mcp.server import MCPServer
from pydantic import Field

from house_brain.config import get_settings
from house_brain.home_assistant import HomeAssistantClient

mcp_server = MCPServer(
    "house-brain",
    title="House Brain",
    description="Read-only access to visible Home Assistant entities.",
    instructions=(
        "Use these tools to read Home Assistant state and history. "
        "Hidden entities are unavailable. This server cannot perform actions."
    ),
    version="0.1.0",
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


mcp_app = mcp_server.streamable_http_app(
    streamable_http_path="/",
    json_response=True,
    stateless_http=True,
    host="0.0.0.0",
)
