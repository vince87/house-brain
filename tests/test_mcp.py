import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import AsyncIterator

import pytest

import house_brain.mcp_server as mcp_module
from house_brain.home_assistant import HomeAssistantEntity
from house_brain.memory import MemoryStore


class StubHomeAssistantClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def get_entity(self, entity_id: str) -> HomeAssistantEntity:
        self.calls.append(("get_entity", entity_id))
        return _entity(entity_id)

    async def search_entities(
        self,
        query: str,
        *,
        domain: str | None,
        limit: int,
    ) -> list[dict[str, str]]:
        self.calls.append(("search_entities", (query, domain, limit)))
        return [
            {
                "entity_id": "light.example_room",
                "friendly_name": "Example Room",
                "state": "on",
            }
        ]

    async def list_entities(
        self,
        *,
        domains: set[str],
        limit: int,
    ) -> list[dict[str, object]]:
        self.calls.append(("list_entities", (domains, limit)))
        return [{"entity_id": "light.example_room", "state": "on"}]

    async def get_history(
        self,
        entity_id: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[HomeAssistantEntity]:
        self.calls.append(("get_history", entity_id))
        assert start < end
        return [_entity(entity_id)]


def _entity(entity_id: str) -> HomeAssistantEntity:
    now = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    return HomeAssistantEntity(
        entity_id=entity_id,
        state="on",
        attributes={"friendly_name": "Example Room"},
        last_changed=now,
        last_updated=now,
    )


def test_mcp_read_tools_delegate_to_home_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubHomeAssistantClient()

    @asynccontextmanager
    async def open_stub() -> AsyncIterator[StubHomeAssistantClient]:
        yield stub

    monkeypatch.setattr(
        mcp_module,
        "open_home_assistant_client",
        open_stub,
    )

    async def call_tools() -> tuple[
        dict[str, object],
        list[dict[str, str]],
        list[dict[str, object]],
        list[dict[str, object]],
    ]:
        return (
            await mcp_module.get_entity("light.example_room"),
            await mcp_module.search_entities("room", "light", 5),
            await mcp_module.list_entities(["light"], 20),
            await mcp_module.get_history("light.example_room", 30),
        )

    entity, search, snapshot, history = asyncio.run(call_tools())

    assert entity["entity_id"] == "light.example_room"
    assert search[0]["entity_id"] == "light.example_room"
    assert snapshot == [{"entity_id": "light.example_room", "state": "on"}]
    assert history[0]["entity_id"] == "light.example_room"
    assert stub.calls == [
        ("get_entity", "light.example_room"),
        ("search_entities", ("room", "light", 5)),
        ("list_entities", ({"light"}, 20)),
        ("get_history", "light.example_room"),
    ]


def test_mcp_memory_tools_use_persistent_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = MemoryStore(str(tmp_path / "memory.db"))
    monkeypatch.setattr(mcp_module, "get_memory_store", lambda: store)

    async def manage_memory() -> tuple[
        dict[str, object],
        list[dict[str, object]],
        dict[str, bool],
        list[dict[str, object]],
        dict[str, bool],
    ]:
        created = await mcp_module.remember_memory(
            "profile.trade",
            "The user is a carpenter",
            "profile",
            9,
        )
        active = await mcp_module.search_memories("carpenter", 10, False)
        forgotten = await mcp_module.forget_memory("profile.trade")
        deleted = await mcp_module.search_memories(None, 10, True)
        restored = await mcp_module.restore_memory("profile.trade")
        return created, active, forgotten, deleted, restored

    created, active, forgotten, deleted, restored = asyncio.run(
        manage_memory()
    )

    assert created["key"] == "profile.trade"
    assert active[0]["value"] == "The user is a carpenter"
    assert forgotten == {"deleted": True}
    assert deleted[0]["key"] == "profile.trade"
    assert restored == {"restored": True}
    assert store.search()[0].key == "profile.trade"


def test_mcp_exposes_home_assistant_and_memory_tools() -> None:
    tool_names = {
        tool.name
        for tool in asyncio.run(mcp_module.mcp_server.list_tools())
    }

    assert tool_names == {
        "get_entity",
        "forget_memory",
        "get_history",
        "list_entities",
        "remember_memory",
        "restore_memory",
        "search_entities",
        "search_memories",
    }
