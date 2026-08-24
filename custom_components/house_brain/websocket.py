"""Admin-only WebSocket bridge for the native House Brain panel."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback

from .api import (
    HouseBrainApiError,
    HouseBrainAuthenticationError,
    HouseBrainConnectionError,
)
from .const import CONF_CONVERSATION_MODE, DOMAIN

_OPERATIONS = (
    "chat",
    "conversation_get",
    "conversation_clear",
    "memory_list",
    "memory_save",
    "memory_delete",
    "memory_restore",
    "memory_import",
    "events",
    "plan_list",
    "plan_propose",
    "plan_approve",
    "plan_reject",
    "autonomy_get",
    "autonomy_update",
    "logs",
    "diagnostics",
    "installation_status",
)


def _text(
    payload: dict[str, Any],
    key: str,
    *,
    maximum: int,
    required: bool = True,
) -> str | None:
    """Return a bounded text value or raise a safe validation error."""
    value = payload.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{key} is required")
    if len(value) > maximum:
        raise ValueError(f"{key} is too long")
    return value


def _memory(payload: dict[str, Any]) -> dict[str, Any]:
    """Copy one memory payload without accepting arbitrary fields."""
    memory: dict[str, Any] = {
        "key": _text(payload, "key", maximum=100),
        "value": _text(payload, "value", maximum=10_000),
        "category": _text(payload, "category", maximum=100),
    }
    importance = payload.get("importance", 5)
    if not isinstance(importance, int) or not 1 <= importance <= 10:
        raise ValueError("importance must be between 1 and 10")
    memory["importance"] = importance
    expires_at = payload.get("expires_at")
    if expires_at is not None:
        if not isinstance(expires_at, str) or len(expires_at) > 64:
            raise ValueError("expires_at is invalid")
        memory["expires_at"] = expires_at
    else:
        memory["expires_at"] = None
    return memory


async def _execute_operation(
    client: Any,
    operation: str,
    payload: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any] | list[Any]:
    """Translate a panel operation into one fixed House Brain API request."""
    if operation == "chat":
        return await client.async_panel_request(
            "POST",
            "/agent/chat",
            json={
                "message": _text(payload, "message", maximum=20_000),
                "session_id": _text(payload, "session_id", maximum=64),
                "mode": mode,
            },
        )

    if operation in {"conversation_get", "conversation_clear"}:
        session_id = _text(payload, "session_id", maximum=64)
        path = f"/conversations/{quote(session_id, safe='')}"
        if operation == "conversation_get":
            return await client.async_panel_request(
                "GET",
                path,
                params={"limit": 100},
            )
        return await client.async_panel_request("DELETE", path)

    if operation == "memory_list":
        params: dict[str, str | int | bool] = {
            "limit": 5000,
            "include_expired": "true",
            "deleted": "true" if payload.get("deleted") is True else "false",
        }
        query = _text(payload, "query", maximum=500, required=False)
        if query:
            params["query"] = query
        return await client.async_panel_request("GET", "/memory/context", params=params)

    if operation == "memory_save":
        return await client.async_panel_request(
            "POST",
            "/memory",
            json=_memory(payload),
        )

    if operation in {"memory_delete", "memory_restore"}:
        key = _text(payload, "key", maximum=100)
        path = f"/memory/{quote(key, safe='')}"
        if operation == "memory_restore":
            path += "/restore"
            return await client.async_panel_request("POST", path)
        return await client.async_panel_request("DELETE", path)

    if operation == "memory_import":
        items = payload.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= 500:
            raise ValueError("items must contain between 1 and 500 memories")
        memories = [_memory(item) for item in items if isinstance(item, dict)]
        if len(memories) != len(items):
            raise ValueError("every imported memory must be an object")
        return await client.async_panel_request(
            "POST",
            "/memory/import",
            json=memories,
        )

    if operation == "events":
        return await client.async_panel_request(
            "GET",
            "/events",
            params={"limit": 100},
        )

    if operation == "plan_list":
        return await client.async_panel_request(
            "GET",
            "/action-plans",
            params={"limit": 100},
        )

    if operation == "plan_propose":
        instruction = _text(payload, "instruction", maximum=4000)
        policy_code = _text(
            payload, "policy_code", maximum=256, required=False
        )
        home_assistant_code = _text(
            payload, "home_assistant_code", maximum=256, required=False
        )
        return await client.async_panel_request(
            "POST",
            "/action-plans/from-request",
            json={"instruction": instruction, "expires_in_seconds": 300},
            authorization_code=policy_code,
            home_assistant_code=home_assistant_code,
        )

    if operation in {"plan_approve", "plan_reject"}:
        plan_id = _text(payload, "plan_id", maximum=64)
        action = "approve" if operation == "plan_approve" else "reject"
        policy_code = _text(
            payload, "policy_code", maximum=256, required=False
        )
        home_assistant_code = _text(
            payload, "home_assistant_code", maximum=256, required=False
        )
        return await client.async_panel_request(
            "POST",
            f"/action-plans/{quote(plan_id, safe='')}/{action}",
            authorization_code=policy_code,
            home_assistant_code=home_assistant_code,
        )

    if operation == "autonomy_get":
        return await client.async_panel_request("GET", "/admin/autonomy")

    if operation == "autonomy_update":
        visible = payload.get("visible")
        include = payload.get("include")
        if not isinstance(visible, list) or not isinstance(include, list):
            raise ValueError("visible and include must be lists")
        return await client.async_panel_request(
            "PUT",
            "/admin/autonomy",
            json={"visible": visible, "include": include},
        )

    if operation == "logs":
        params = {"limit": 500}
        level = _text(payload, "level", maximum=16, required=False)
        if level:
            if level not in {"INFO", "WARNING", "ERROR", "CRITICAL"}:
                raise ValueError("level is invalid")
            params["level"] = level
        query = _text(payload, "query", maximum=200, required=False)
        if query:
            params["query"] = query
        return await client.async_panel_request(
            "GET",
            "/runtime-logs",
            params=params,
        )

    if operation == "diagnostics":
        return await client.async_panel_request("GET", "/diagnostics")

    if operation == "installation_status":
        return await client.async_panel_request("GET", "/admin/installation")

    raise ValueError("Unsupported panel operation")


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register the House Brain panel command."""
    websocket_api.async_register_command(hass, websocket_panel_request)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "house_brain/panel",
        vol.Required("entry_id"): str,
        vol.Required("operation"): vol.In(_OPERATIONS),
        vol.Optional("payload", default={}): dict,
    }
)
@websocket_api.async_response
async def websocket_panel_request(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Proxy one explicitly allowed panel operation through the config entry."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.runtime_data is None:
        connection.send_error(msg["id"], "not_loaded", "House Brain is not loaded")
        return

    try:
        result = await _execute_operation(
            entry.runtime_data.client,
            msg["operation"],
            msg["payload"],
            mode=entry.data[CONF_CONVERSATION_MODE],
        )
    except ValueError as exc:
        connection.send_error(msg["id"], "invalid_format", str(exc))
        return
    except HouseBrainAuthenticationError:
        connection.send_error(
            msg["id"],
            "invalid_auth",
            "House Brain rejected the configured API key",
        )
        return
    except HouseBrainConnectionError:
        connection.send_error(
            msg["id"],
            "cannot_connect",
            "Cannot connect to House Brain",
        )
        return
    except HouseBrainApiError as exc:
        connection.send_error(msg["id"], "request_failed", str(exc))
        return

    connection.send_result(msg["id"], result)

