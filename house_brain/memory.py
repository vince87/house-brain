import re
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from sqlite3 import Connection
from threading import Lock

from pydantic import BaseModel, ConfigDict, Field, field_validator

from house_brain.database import connect_database


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="fact", min_length=1, max_length=50)
    importance: int = Field(default=5, ge=1, le=10)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def normalize_expiration(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        return value.astimezone(UTC)


class MemoryRecord(MemoryInput):
    id: int
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime
    source: str
    deleted_at: datetime | None = None


class MemoryEntityReference(BaseModel):
    """Current, policy-filtered state for an entity cited by a memory."""

    entity_id: str
    name: str | None = None
    state: str | None = None
    verified: bool = False
    home_assistant_path: str | None = None


class MemoryContextRecord(MemoryRecord):
    """Memory record enriched with current Home Assistant references."""

    referenced_entities: list[MemoryEntityReference] = Field(default_factory=list)


class MemoryStore:
    def __init__(self, database_path: str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> Connection:
        return connect_database(self.path)

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    importance INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    confirmed_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'legacy',
                    expires_at TEXT,
                    deleted_at TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(memories)"
                ).fetchall()
            }
            if "deleted_at" not in columns:
                connection.execute(
                    "ALTER TABLE memories ADD COLUMN deleted_at TEXT"
                )
            if "confirmed_at" not in columns:
                connection.execute("ALTER TABLE memories ADD COLUMN confirmed_at TEXT")
                connection.execute(
                    "UPDATE memories SET confirmed_at = updated_at "
                    "WHERE confirmed_at IS NULL"
                )
            if "source" not in columns:
                connection.execute(
                    "ALTER TABLE memories ADD COLUMN source TEXT "
                    "NOT NULL DEFAULT 'legacy'"
                )
            if "expires_at" not in columns:
                connection.execute("ALTER TABLE memories ADD COLUMN expires_at TEXT")

    def remember(self, memory: MemoryInput, *, source: str = "api") -> MemoryRecord:
        timestamp = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    key, value, category, importance,
                    created_at, updated_at, confirmed_at, source,
                    expires_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    importance = excluded.importance,
                    updated_at = excluded.updated_at,
                    confirmed_at = excluded.confirmed_at,
                    source = excluded.source,
                    expires_at = excluded.expires_at,
                    deleted_at = NULL
                """,
                (
                    memory.key,
                    memory.value,
                    memory.category,
                    memory.importance,
                    timestamp,
                    timestamp,
                    timestamp,
                    source,
                    memory.expires_at.isoformat() if memory.expires_at else None,
                ),
            )
            row = connection.execute(
                "SELECT * FROM memories WHERE key = ?",
                (memory.key,),
            ).fetchone()
        return MemoryRecord.model_validate(dict(row))

    def search(
        self,
        query: str | None = None,
        *,
        limit: int = 10,
        deleted: bool = False,
        include_expired: bool = False,
    ) -> list[MemoryRecord]:
        clauses = ["deleted_at IS NOT NULL" if deleted else "deleted_at IS NULL"]
        if not deleted and not include_expired:
            clauses.append("(expires_at IS NULL OR expires_at > ?)")
            parameters: list[object] = [datetime.now(UTC).isoformat()]
        else:
            parameters = []
        if query:
            pattern = f"%{query.strip()}%"
            clauses.append("(key LIKE ? OR value LIKE ? OR category LIKE ?)")
            parameters.extend([pattern, pattern, pattern])
        parameters.append(limit)
        sql = f"""
            SELECT * FROM memories
            WHERE {" AND ".join(clauses)}
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
        """
        with self._lock, self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [MemoryRecord.model_validate(dict(row)) for row in rows]

    def search_for_entities(
        self,
        entity_ids: set[str] | frozenset[str],
        *,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Return active memories that explicitly cite observed entities."""
        normalized = {entity_id.strip().lower() for entity_id in entity_ids if entity_id}
        if not normalized or limit < 1:
            return []
        candidates = self.search(limit=10_000)
        matches: list[MemoryRecord] = []
        entity_pattern = re.compile(
            r"\\b[a-z][a-z0-9_]*\\.[a-z0-9_]+\\b",
            flags=re.IGNORECASE,
        )
        for memory in candidates:
            referenced = {
                entity_id.lower() for entity_id in entity_pattern.findall(memory.value)
            }
            if referenced & normalized:
                matches.append(memory)
                if len(matches) >= limit:
                    break
        return matches

    def forget(self, key: str) -> bool:
        timestamp = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE memories
                SET deleted_at = ?, updated_at = ?
                WHERE key = ? AND deleted_at IS NULL
                """,
                (timestamp, timestamp, key),
            )
            return cursor.rowcount > 0

    def restore(self, key: str) -> bool:
        timestamp = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE memories
                SET deleted_at = NULL, updated_at = ?
                WHERE key = ? AND deleted_at IS NOT NULL
                """,
                (timestamp, key),
            )
            return cursor.rowcount > 0


@lru_cache(maxsize=8)
def memory_store_for(database_path: str) -> MemoryStore:
    """Reuse one initialized store per persistent database path."""
    return MemoryStore(database_path)
