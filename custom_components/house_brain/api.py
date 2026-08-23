"""Authenticated HTTP client for a local House Brain server."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout

from .const import DEFAULT_REQUEST_TIMEOUT
from .models import HouseBrainAgentResult, HouseBrainStatus


class HouseBrainApiError(Exception):
    """Base error raised by the House Brain API client."""


class HouseBrainAuthenticationError(HouseBrainApiError):
    """The House Brain API key was rejected."""


class HouseBrainConnectionError(HouseBrainApiError):
    """The House Brain server could not be reached."""


class HouseBrainResponseError(HouseBrainApiError):
    """The House Brain server returned an invalid or failed response."""


def normalize_base_url(value: str) -> str:
    """Return a safe normalized HTTP base URL without credentials or query data."""
    raw = value.strip().rstrip("/")
    parsed = urlsplit(raw)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("House Brain URL must be an HTTP(S) URL without credentials")
    return urlunsplit(
        (parsed.scheme.lower(), parsed.netloc, parsed.path.rstrip("/"), "", "")
    )


class HouseBrainClient:
    """Small async client that uses Home Assistant's managed HTTP session."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        api_key: str,
        *,
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        self._session = session
        self.base_url = normalize_base_url(base_url)
        self._api_key = api_key
        self._timeout = ClientTimeout(total=timeout)

    async def async_validate(self) -> HouseBrainStatus:
        """Verify authentication and return the remote application version."""
        authentication = await self._request("GET", "/auth/check")
        if authentication.get("authenticated") is not True:
            raise HouseBrainResponseError("House Brain authentication check failed")
        health = await self._request("GET", "/health", authenticated=False)
        if health.get("status") != "ok" or not isinstance(
            health.get("version"), str
        ):
            raise HouseBrainResponseError("House Brain health response is invalid")
        return HouseBrainStatus(version=health["version"])

    async def async_chat(
        self,
        message: str,
        session_id: str,
        *,
        mode: str,
        language: str,
    ) -> HouseBrainAgentResult:
        """Run one native Home Assistant conversation turn."""
        payload = await self._request(
            "POST",
            "/agent/chat",
            json={
                "message": message,
                "session_id": session_id,
                "mode": mode,
                "language": language,
            },
        )
        return self._agent_result(payload, require_session=True)

    async def async_ai_task(
        self,
        instructions: str,
        task_name: str,
        *,
        language: str,
    ) -> HouseBrainAgentResult:
        """Run an AI Task as an audited, action-free observe event."""
        payload = await self._request(
            "POST",
            "/agent/events",
            json={
                "event_type": "home_assistant_ai_task",
                "source": "home_assistant_integration",
                "mode": "observe",
                "instruction": instructions,
                "language": language,
                "context": {"task_name": task_name},
            },
        )
        return self._agent_result(payload, require_session=False)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["X-API-Key"] = self._api_key
        try:
            async with self._session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                json=json,
                timeout=self._timeout,
            ) as response:
                if response.status == 401:
                    raise HouseBrainAuthenticationError(
                        "House Brain rejected the API key"
                    )
                try:
                    payload = await self._response_payload(response)
                except HouseBrainResponseError:
                    if response.status >= 400:
                        raise HouseBrainResponseError(
                            f"House Brain request failed with HTTP {response.status}"
                        ) from None
                    raise
        except HouseBrainApiError:
            raise
        except (ClientError, TimeoutError) as exc:
            raise HouseBrainConnectionError(
                "Cannot connect to the House Brain server"
            ) from exc

        if response.status >= 400:
            detail = payload.get("detail")
            message = detail if isinstance(detail, str) else f"HTTP {response.status}"
            raise HouseBrainResponseError(message)
        return payload

    @staticmethod
    async def _response_payload(response: ClientResponse) -> dict[str, Any]:
        try:
            payload = await response.json(content_type=None)
        except (ClientError, ValueError) as exc:
            raise HouseBrainResponseError(
                "House Brain returned a non-JSON response"
            ) from exc
        if not isinstance(payload, dict):
            raise HouseBrainResponseError("House Brain returned an invalid response")
        return payload

    @staticmethod
    def _agent_result(
        payload: dict[str, Any],
        *,
        require_session: bool,
    ) -> HouseBrainAgentResult:
        response = payload.get("response")
        session_id = payload.get("session_id")
        if not isinstance(response, str) or not response.strip():
            raise HouseBrainResponseError("House Brain returned an empty response")
        if require_session and not isinstance(session_id, str):
            raise HouseBrainResponseError("House Brain returned no conversation ID")
        tools = payload.get("tools_used", [])
        trace = payload.get("tool_trace", [])
        return HouseBrainAgentResult(
            response=response,
            session_id=session_id if isinstance(session_id, str) else None,
            event_id=(
                payload["event_id"]
                if isinstance(payload.get("event_id"), str)
                else None
            ),
            model=payload["model"] if isinstance(payload.get("model"), str) else None,
            tools_used=tuple(item for item in tools if isinstance(item, str))
            if isinstance(tools, list)
            else (),
            tool_trace=tuple(item for item in trace if isinstance(item, dict))
            if isinstance(trace, list)
            else (),
        )
