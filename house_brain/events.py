import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EventMode = Literal["observe", "simulate", "execute"]
EventStatus = Literal["completed", "failed"]


class AutonomousExecutionDisabledError(ValueError):
    """Raised when execute mode is requested while the kill switch is off."""


def validate_execution_enabled(mode: EventMode, enabled: bool) -> None:
    if mode == "execute" and not enabled:
        raise AutonomousExecutionDisabledError(
            "Autonomous execution is disabled"
        )


class AgentEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    source: str = Field(default="home_assistant", min_length=1, max_length=80)
    mode: EventMode = "observe"
    instruction: str = Field(min_length=1, max_length=4000)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("context")
    @classmethod
    def validate_context_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
        if len(encoded.encode()) > 16_384:
            raise ValueError("context must not exceed 16 KiB")
        return value


class AgentEventResponse(BaseModel):
    event_id: str
    mode: EventMode
    status: EventStatus
    response: str
    model: str
    iterations: int
    tools_used: list[str]


class EventRecord(BaseModel):
    event_id: str
    event_type: str
    source: str
    mode: EventMode
    instruction: str
    context: dict[str, Any]
    status: EventStatus
    response: str
    tools_used: list[str]
    created_at: datetime


class EventStore:
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
                CREATE TABLE IF NOT EXISTS agent_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response TEXT NOT NULL,
                    tools_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_events_created
                ON agent_events(created_at DESC)
                """
            )

    def record(
        self,
        event_id: str,
        request: AgentEventRequest,
        *,
        status: EventStatus,
        response: str,
        tools_used: list[str],
    ) -> EventRecord:
        timestamp = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_events (
                    event_id, event_type, source, mode, instruction,
                    context_json, status, response, tools_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    request.event_type,
                    request.source,
                    request.mode,
                    request.instruction,
                    json.dumps(
                        request.context,
                        ensure_ascii=False,
                        default=str,
                    ),
                    status,
                    response,
                    json.dumps(tools_used, ensure_ascii=False),
                    timestamp,
                ),
            )
        return EventRecord(
            event_id=event_id,
            event_type=request.event_type,
            source=request.source,
            mode=request.mode,
            instruction=request.instruction,
            context=request.context,
            status=status,
            response=response,
            tools_used=tools_used,
            created_at=datetime.fromisoformat(timestamp),
        )

    def list(
        self,
        *,
        limit: int = 20,
        mode: EventMode | None = None,
    ) -> list[EventRecord]:
        sql = "SELECT * FROM agent_events"
        parameters: list[object] = []
        if mode:
            sql += " WHERE mode = ?"
            parameters.append(mode)
        sql += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(limit)

        with self._lock, self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()

        return [
            EventRecord(
                event_id=row["event_id"],
                event_type=row["event_type"],
                source=row["source"],
                mode=row["mode"],
                instruction=row["instruction"],
                context=json.loads(row["context_json"]),
                status=row["status"],
                response=row["response"],
                tools_used=json.loads(row["tools_json"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
