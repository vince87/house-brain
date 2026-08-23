"""Typed API models for the House Brain integration."""

import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any
from uuid import uuid4

_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def server_session_id(entry_id: str, conversation_id: str | None) -> str:
    """Map one HA conversation to a stable, entry-scoped server identifier."""
    prefix = f"ha-{entry_id[:8]}-"
    if (
        conversation_id
        and conversation_id.startswith(prefix)
        and _SAFE_SESSION_ID.fullmatch(conversation_id)
    ):
        return conversation_id
    seed = conversation_id or uuid4().hex
    digest = sha256(f"{entry_id}:{seed}".encode()).hexdigest()[:40]
    return f"{prefix}{digest}"


@dataclass(slots=True, frozen=True)
class HouseBrainStatus:
    """Validated House Brain server status."""

    version: str


@dataclass(slots=True, frozen=True)
class HouseBrainAgentResult:
    """Normalized response returned by a House Brain agent endpoint."""

    response: str
    session_id: str | None = None
    event_id: str | None = None
    model: str | None = None
    tools_used: tuple[str, ...] = ()
    tool_trace: tuple[dict[str, Any], ...] = field(default_factory=tuple)


@dataclass(slots=True)
class HouseBrainRuntimeData:
    """Objects shared by the Home Assistant entity platforms."""

    client: Any
    status: HouseBrainStatus
