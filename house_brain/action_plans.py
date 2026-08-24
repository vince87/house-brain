from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from sqlite3 import Connection, Row
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from house_brain.actions import ActionRequest, ActionResult, redact_action_data
from house_brain.database import connect_database
from house_brain.home_assistant import HomeAssistantEntity

PlanStatus = Literal[
    "proposed",
    "executing",
    "executed",
    "rejected",
    "expired",
    "invalidated",
    "failed",
]


class ActionPlanConflictError(ValueError):
    """Raised when a plan cannot transition from its current state."""


class PlannedActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str = Field(min_length=1)
    service: str = Field(min_length=1)
    entity_id: str = Field(min_length=3)
    data: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("domain", "service", "entity_id")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().lower()

    def action_request(self) -> ActionRequest:
        return ActionRequest(
            domain=self.domain,
            service=self.service,
            entity_id=self.entity_id,
            data=self.data,
            dry_run=False,
        )


class ActionPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[PlannedActionInput] = Field(min_length=1, max_length=20)
    expires_in_seconds: int = Field(default=300, ge=30, le=1800)


class ActionPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=4000)
    expires_in_seconds: int = Field(default=300, ge=30, le=1800)
    language: str | None = Field(default=None, max_length=35)


class PlannedActionRecord(PlannedActionInput):
    initial_state: str
    initial_attributes: dict[str, Any] = Field(default_factory=dict)
    state_fingerprint: str


class ActionPlanRecord(BaseModel):
    plan_id: str
    status: PlanStatus
    actions: list[PlannedActionRecord]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    execution_enabled_at_proposal: bool
    outcome: list[ActionResult] = Field(default_factory=list)
    error: str | None = None


class ActionPlanStore:
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
                CREATE TABLE IF NOT EXISTS action_plans (
                    plan_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    actions_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    execution_enabled_at_proposal INTEGER NOT NULL,
                    outcome_json TEXT NOT NULL DEFAULT '[]',
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_action_plans_created
                ON action_plans(created_at DESC)
                """
            )

    def create(
        self,
        actions: list[PlannedActionRecord],
        *,
        expires_in_seconds: int,
        execution_enabled: bool,
    ) -> ActionPlanRecord:
        now = datetime.now(UTC)
        record = ActionPlanRecord(
            plan_id=uuid4().hex,
            status="proposed",
            actions=actions,
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(seconds=expires_in_seconds),
            execution_enabled_at_proposal=execution_enabled,
        )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO action_plans (
                    plan_id, status, actions_json, created_at, updated_at,
                    expires_at, execution_enabled_at_proposal, outcome_json,
                    error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', NULL)
                """,
                (
                    record.plan_id,
                    record.status,
                    _json([item.model_dump(mode="json") for item in actions]),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.expires_at.isoformat(),
                    int(execution_enabled),
                ),
            )
        return record

    def get(self, plan_id: str) -> ActionPlanRecord | None:
        with self._lock, self._connect() as connection:
            self._expire(connection)
            row = connection.execute(
                "SELECT * FROM action_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        return _record(row) if row is not None else None

    def list(self, *, limit: int = 50) -> list[ActionPlanRecord]:
        with self._lock, self._connect() as connection:
            self._expire(connection)
            rows = connection.execute(
                "SELECT * FROM action_plans ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_record(row) for row in rows]

    def claim(self, plan_id: str) -> ActionPlanRecord:
        now = datetime.now(UTC)
        with self._lock, self._connect() as connection:
            self._expire(connection, now=now)
            changed = connection.execute(
                """
                UPDATE action_plans
                SET status = 'executing', updated_at = ?
                WHERE plan_id = ? AND status = 'proposed' AND expires_at > ?
                """,
                (now.isoformat(), plan_id, now.isoformat()),
            ).rowcount
            row = connection.execute(
                "SELECT * FROM action_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        if row is None:
            raise ActionPlanConflictError("Action plan was not found")
        if changed != 1:
            raise ActionPlanConflictError(
                f"Action plan cannot be approved from status: {row['status']}"
            )
        return _record(row)

    def finish(
        self,
        plan_id: str,
        *,
        status: Literal["executed", "invalidated", "failed"],
        outcome: list[ActionResult] | None = None,
        error: str | None = None,
    ) -> ActionPlanRecord:
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE action_plans
                SET status = ?, updated_at = ?, outcome_json = ?, error = ?
                WHERE plan_id = ? AND status = 'executing'
                """,
                (
                    status,
                    now,
                    _json([item.model_dump(mode="json") for item in outcome or []]),
                    error,
                    plan_id,
                ),
            ).rowcount
            row = connection.execute(
                "SELECT * FROM action_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        if changed != 1 or row is None:
            raise ActionPlanConflictError("Action plan execution state changed")
        return _record(row)

    def reject(self, plan_id: str) -> ActionPlanRecord:
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            self._expire(connection)
            changed = connection.execute(
                """
                UPDATE action_plans
                SET status = 'rejected', updated_at = ?
                WHERE plan_id = ? AND status = 'proposed'
                """,
                (now, plan_id),
            ).rowcount
            row = connection.execute(
                "SELECT * FROM action_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        if row is None:
            raise ActionPlanConflictError("Action plan was not found")
        if changed != 1:
            raise ActionPlanConflictError(
                f"Action plan cannot be rejected from status: {row['status']}"
            )
        return _record(row)

    @staticmethod
    def _expire(
        connection: Connection,
        *,
        now: datetime | None = None,
    ) -> None:
        timestamp = (now or datetime.now(UTC)).isoformat()
        connection.execute(
            """
            UPDATE action_plans
            SET status = 'expired', updated_at = ?
            WHERE status = 'proposed' AND expires_at <= ?
            """,
            (timestamp, timestamp),
        )


def planned_action(
    action: PlannedActionInput,
    entity: HomeAssistantEntity,
) -> PlannedActionRecord:
    safe_data = redact_action_data(action.data)
    if safe_data != action.data:
        raise ValueError("Authorization codes must be supplied through headers")
    snapshot = {
        "state": entity.state,
        "attributes": entity.attributes,
    }
    fingerprint = hashlib.sha256(_json(snapshot).encode("utf-8")).hexdigest()
    payload = action.model_dump(
        include={"domain", "service", "entity_id", "data", "reason"}
    )
    payload["data"] = safe_data
    return PlannedActionRecord(
        **payload,
        initial_state=entity.state,
        initial_attributes=entity.attributes,
        state_fingerprint=fingerprint,
    )


def entity_matches_plan(
    planned: PlannedActionRecord,
    entity: HomeAssistantEntity,
) -> bool:
    snapshot = {"state": entity.state, "attributes": entity.attributes}
    return hashlib.sha256(_json(snapshot).encode("utf-8")).hexdigest() == (
        planned.state_fingerprint
    )


def actions_from_simulation_trace(
    trace: list[object],
    *,
    reason: str,
) -> list[PlannedActionInput]:
    """Return only actions that the server authoritatively simulated."""
    actions: list[PlannedActionInput] = []
    seen: set[str] = set()
    for item in trace:
        tool = getattr(item, "tool", None)
        status = getattr(item, "status", None)
        outcome = getattr(item, "outcome", None)
        arguments = getattr(item, "arguments", None)
        if status != "completed" or outcome != "simulated":
            continue
        if tool == "perform_action" and isinstance(arguments, dict):
            raw_actions = [arguments]
        elif tool == "perform_actions" and isinstance(arguments, dict):
            raw_actions = arguments.get("actions", [])
        else:
            continue
        if not isinstance(raw_actions, list):
            continue
        for raw in raw_actions:
            if not isinstance(raw, dict):
                continue
            action = PlannedActionInput(
                domain=raw.get("domain", ""),
                service=raw.get("service", ""),
                entity_id=raw.get("entity_id", ""),
                data=raw.get("data", {}),
                reason=reason[:500],
            )
            identity = _json(action.model_dump(exclude={"reason"}))
            if identity not in seen:
                seen.add(identity)
                actions.append(action)
    return actions


def _record(row: Row) -> ActionPlanRecord:
    return ActionPlanRecord(
        plan_id=row["plan_id"],
        status=row["status"],
        actions=json.loads(row["actions_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        expires_at=row["expires_at"],
        execution_enabled_at_proposal=bool(row["execution_enabled_at_proposal"]),
        outcome=json.loads(row["outcome_json"]),
        error=row["error"],
    )


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@lru_cache
def action_plan_store_for(database_path: str) -> ActionPlanStore:
    return ActionPlanStore(database_path)

