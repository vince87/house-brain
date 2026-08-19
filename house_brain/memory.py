from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection
from threading import Lock

from pydantic import BaseModel, ConfigDict, Field

from house_brain.database import connect_database


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
    deleted_at: datetime | None = None


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

    def remember(self, memory: MemoryInput) -> MemoryRecord:
        timestamp = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    key, value, category, importance,
                    created_at, updated_at, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    importance = excluded.importance,
                    updated_at = excluded.updated_at,
                    deleted_at = NULL
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
        deleted: bool = False,
    ) -> list[MemoryRecord]:
        clauses = ["deleted_at IS NOT NULL" if deleted else "deleted_at IS NULL"]
        parameters: list[object] = []
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
