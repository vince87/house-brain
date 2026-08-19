import json
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Connection
from threading import Lock
from typing import Literal

from pydantic import BaseModel, Field

from house_brain.events import ToolAuditRecord

from house_brain.database import connect_database


class ConversationMessage(BaseModel):
    id: int
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    tool_trace: list[ToolAuditRecord] = Field(default_factory=list)


class ConversationStore:
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
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    tool_trace_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = {
                str(row[1])
                for row in connection.execute(
                    "PRAGMA table_info(conversation_messages)"
                ).fetchall()
            }
            if "tool_trace_json" not in columns:
                connection.execute(
                    "ALTER TABLE conversation_messages "
                    "ADD COLUMN tool_trace_json TEXT NOT NULL DEFAULT '[]'"
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
        messages: list[ConversationMessage] = []
        for row in rows:
            payload = dict(row)
            raw_trace = payload.pop("tool_trace_json", "[]")
            try:
                payload["tool_trace"] = json.loads(raw_trace)
            except (TypeError, json.JSONDecodeError):
                payload["tool_trace"] = []
            messages.append(ConversationMessage.model_validate(payload))
        return messages

    def add_exchange(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        *,
        assistant_tool_trace: list[ToolAuditRecord] | None = None,
    ) -> None:
        timestamp = datetime.now(UTC).isoformat()
        serialized_trace = json.dumps(
            [
                item.model_dump(mode="json")
                for item in (assistant_tool_trace or [])
            ],
            ensure_ascii=False,
        )
        with self._lock, self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO conversation_messages (
                    session_id, role, content, tool_trace_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (session_id, "user", user_message, "[]", timestamp),
                    (
                        session_id,
                        "assistant",
                        assistant_message,
                        serialized_trace,
                        timestamp,
                    ),
                ],
            )

    def clear(self, session_id: str) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM conversation_messages WHERE session_id = ?",
                (session_id,),
            )
            return cursor.rowcount
