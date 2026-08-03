import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel


class ConversationMessage(BaseModel):
    id: int
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ConversationStore:
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
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_session
                ON conversation_messages(session_id, id)
                """
            )

    def history(
        self,
        session_id: str,
        *,
        limit: int = 12,
    ) -> list[ConversationMessage]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT * FROM conversation_messages
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                ORDER BY id ASC
                """,
                (session_id, limit),
            ).fetchall()
        return [ConversationMessage.model_validate(dict(row)) for row in rows]

    def add_exchange(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        timestamp = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO conversation_messages (
                    session_id, role, content, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (session_id, "user", user_message, timestamp),
                    (session_id, "assistant", assistant_message, timestamp),
                ],
            )

    def clear(self, session_id: str) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversation_messages WHERE session_id = ?",
                (session_id,),
            )
            return cursor.rowcount
