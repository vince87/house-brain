import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, ConfigDict, Field


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=2000)
    category: str = Field(default="fact", min_length=1, max_length=50)
    importance: int = Field(default=5, ge=1, le=10)


class MemoryRecord(MemoryInput):
    id: int
    created_at: datetime
    updated_at: datetime


class MemoryStore:
    def __init__(self, database_path: str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

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
                    updated_at TEXT NOT NULL
                )
                """
            )

    def remember(self, memory: MemoryInput) -> MemoryRecord:
        timestamp = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    key, value, category, importance, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    importance = excluded.importance,
                    updated_at = excluded.updated_at
                """,
                (
                    memory.key,
                    memory.value,
                    memory.category,
                    memory.importance,
                    timestamp,
                    timestamp,
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
    ) -> list[MemoryRecord]:
        with self._lock, self._connect() as connection:
            if query:
                pattern = f"%{query.strip()}%"
                rows = connection.execute(
                    """
                    SELECT * FROM memories
                    WHERE key LIKE ? OR value LIKE ? OR category LIKE ?
                    ORDER BY importance DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (pattern, pattern, pattern, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM memories
                    ORDER BY importance DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [MemoryRecord.model_validate(dict(row)) for row in rows]

    def forget(self, key: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM memories WHERE key = ?",
                (key,),
            )
            return cursor.rowcount > 0
