import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from sqlite3 import connect

from house_brain.main import import_memories
from house_brain.memory import MemoryInput, MemoryStore


def test_memory_store_upserts_searches_and_forgets(tmp_path: Path) -> None:
    store = MemoryStore(str(tmp_path / "memory.db"))

    created = store.remember(
        MemoryInput(
            key="profile.profession",
            value="The user works as a carpenter",
            category="profile",
            importance=9,
        )
    )
    updated = store.remember(
        MemoryInput(
            key="profile.profession",
            value="The user works professionally as a carpenter",
            category="profile",
            importance=10,
        )
    )

    assert created.id == updated.id
    assert created.source == "api"
    assert updated.confirmed_at >= created.confirmed_at
    assert updated.value == "The user works professionally as a carpenter"
    assert len(store.search("carpenter")) == 1
    assert store.search("professionally")[0].key == "profile.profession"
    assert store.search("unrelated query") == []
    assert store.search()[0].importance == 10
    assert store.forget("profile.profession") is True
    assert store.search() == []
    assert len(store.search(deleted=True)) == 1
    assert store.forget("profile.profession") is False
    assert store.restore("profile.profession") is True
    assert len(store.search()) == 1
    assert store.restore("profile.profession") is False


def test_memory_expiration_is_optional_and_excluded_from_recall(tmp_path: Path) -> None:
    store = MemoryStore(str(tmp_path / "memory.db"))
    expired = MemoryInput(
        key="temporary.notice",
        value="This temporary notice has expired",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    active = MemoryInput(
        key="temporary.active",
        value="This temporary notice is active",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    store.remember(expired, source="agent")
    saved = store.remember(active, source="mcp")

    assert [item.key for item in store.search()] == ["temporary.active"]
    assert {item.key for item in store.search(include_expired=True)} == {
        "temporary.active",
        "temporary.notice",
    }
    assert saved.source == "mcp"
    assert saved.expires_at == active.expires_at


def test_memory_import_assigns_server_managed_provenance(tmp_path: Path) -> None:
    store = MemoryStore(str(tmp_path / "memory.db"))

    imported = asyncio.run(
        import_memories(
            [MemoryInput(key="imported.preference", value="Example preference")],
            store,
        )
    )

    assert imported[0].source == "import"
    assert imported[0].confirmed_at is not None


def test_existing_memory_database_is_migrated_without_data_loss(tmp_path: Path) -> None:
    database = tmp_path / "legacy.db"
    timestamp = datetime.now(UTC).isoformat()
    with connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                category TEXT NOT NULL,
                importance INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT
            )
            """
        )
        connection.execute(
            "INSERT INTO memories VALUES (1, ?, ?, ?, ?, ?, ?, NULL)",
            ("legacy.fact", "Preserved value", "fact", 5, timestamp, timestamp),
        )

    record = MemoryStore(str(database)).search()[0]

    assert record.key == "legacy.fact"
    assert record.source == "legacy"
    assert record.confirmed_at == record.updated_at
    assert record.expires_at is None
