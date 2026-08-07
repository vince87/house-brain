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
        default="home_assistant_event",
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


def build_event_message(
    event: AgentEventRequest,
    *,
    now: datetime | None = None,
) -> str:
    """Add authoritative local time to the event context sent to the model."""
    local_now = now or datetime.now().astimezone()
    context = json.dumps(event.context, ensure_ascii=False, default=str)
    return (
        f"Evento automatico: {event.event_type}\n"
        f"Origine: {event.source}\n"
        f"Data e ora locale: {local_now.isoformat()}\n"
        f"Stagione meteorologica: {_season(local_now.month)}\n"
        f"Contesto: {context}\n"
        f"Obiettivo: {event.instruction}"
    )


class ToolAuditRecord(BaseModel):
    sequence: int = Field(ge=1)
    tool: str
    arguments: dict[str, Any]
    status: Literal["completed", "failed"]
    outcome: str
    error: str | None = None


class AgentEventResponse(BaseModel):
    event_id: str
    mode: EventMode
    status: EventStatus
    response: str
    model: str
    iterations: int
    tools_used: list[str]
    tool_trace: list[ToolAuditRecord] = Field(default_factory=list)


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
    tool_trace: list[ToolAuditRecord] = Field(default_factory=list)
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
                    tool_trace_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(agent_events)"
                ).fetchall()
            }
            if "tool_trace_json" not in columns:
                connection.execute(
                    "ALTER TABLE agent_events ADD COLUMN "
                    "tool_trace_json TEXT NOT NULL DEFAULT '[]'"
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
        tool_trace: list[ToolAuditRecord] | None = None,
    ) -> EventRecord:
        timestamp = datetime.now(UTC).isoformat()
        trace = tool_trace or []
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_events (
                    event_id, event_type, source, mode, instruction,
                    context_json, status, response, tools_json,
                    tool_trace_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps(
                        [
                            item.model_dump(mode="json")
                            for item in trace
                        ],
                        ensure_ascii=False,
                    ),
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
            tool_trace=trace,
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

        return [_row_to_event_record(row) for row in rows]

    def get(self, event_id: str) -> EventRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return _row_to_event_record(row) if row is not None else None


def _row_to_event_record(row: sqlite3.Row) -> EventRecord:
    return EventRecord(
        event_id=row["event_id"],
        event_type=row["event_type"],
        source=row["source"],
        mode=row["mode"],
        instruction=row["instruction"],
        context=json.loads(row["context_json"]),
        status=row["status"],
        response=row["response"],
        tools_used=json.loads(row["tools_json"]),
        tool_trace=[
            ToolAuditRecord.model_validate(item)
            for item in json.loads(row["tool_trace_json"])
        ],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _season(month: int) -> str:
    if month in {3, 4, 5}:
        return "primavera"
    if month in {6, 7, 8}:
        return "estate"
    if month in {9, 10, 11}:
        return "autunno"
    return "inverno"
