import asyncio
import json

import httpx
from loguru import logger
from pydantic import BaseModel

from house_brain.config import Settings
from house_brain.ollama import OllamaError

OPENAI_CHAT_ATTEMPTS = 3
OPENAI_RETRY_DELAYS = (0.0, 0.5, 1.0)


class OpenAIStatus(BaseModel):
    status: str
    provider: str = "openai"
    url: str
    configured_model: str
    model_available: bool


class OpenAIClient:
    """OpenAI Chat Completions adapter using the agent's normalized messages."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if settings.uses_official_openai_api and settings.openai_api_key is None:
            raise OllamaError("OPENAI_API_KEY is required for the official OpenAI API")
        self.model = settings.openai_model
        self.max_output_tokens = settings.openai_max_output_tokens
        headers = {"Content-Type": "application/json"}
        if settings.openai_api_key is not None:
            headers["Authorization"] = (
                f"Bearer {settings.openai_api_key.get_secret_value()}"
            )
        self._client = httpx.AsyncClient(
            base_url=str(settings.openai_base_url).rstrip("/"),
            timeout=settings.openai_timeout,
            headers=headers,
            transport=transport,
        )

    async def __aenter__(self) -> "OpenAIClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": _openai_messages(messages),
            "max_completion_tokens": self.max_output_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        response = await self._post_chat(payload)
        try:
            body = response.json()
            message = body["choices"][0]["message"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise OllamaError("OpenAI chat returned invalid data") from exc
        if not isinstance(message, dict):
            raise OllamaError("OpenAI chat returned invalid data")

        normalized: dict[str, object] = {
            "role": "assistant",
            "content": message.get("content") or "",
        }
        calls = message.get("tool_calls")
        if isinstance(calls, list) and calls:
            normalized["tool_calls"] = [_normalize_tool_call(call) for call in calls]
        content = normalized["content"]
        if not (isinstance(content, str) and content.strip()) and not normalized.get(
            "tool_calls"
        ):
            raise OllamaError("OpenAI chat returned an empty response")
        return normalized

    async def _post_chat(self, payload: dict[str, object]) -> httpx.Response:
        for attempt in range(OPENAI_CHAT_ATTEMPTS):
            try:
                response = await self._client.post("/chat/completions", json=payload)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if _is_retryable_status(status_code) and await _retry_openai(
                    attempt,
                    reason=f"HTTP {status_code}",
                    request_id=exc.response.headers.get("x-request-id"),
                ):
                    continue
                if status_code in {401, 403}:
                    raise OllamaError("OpenAI rejected the credentials") from exc
                if status_code in {400, 404, 422} and await self._model_unavailable():
                    raise OllamaError(
                        "The configured OpenAI model is not available or is not loaded"
                    ) from exc
                raise OllamaError("OpenAI chat request failed") from exc
            except httpx.RequestError as exc:
                if await _retry_openai(
                    attempt,
                    reason=type(exc).__name__,
                    request_id=None,
                ):
                    continue
                raise OllamaError("OpenAI chat request failed") from exc
        raise OllamaError("OpenAI chat request failed")

    async def _model_unavailable(self) -> bool:
        try:
            return not (await self.status()).model_available
        except OllamaError:
            return False

    async def status(self) -> OpenAIStatus:
        try:
            response = await self._client.get(f"/models/{self.model}")
            if response.status_code in {404, 405}:
                response = await self._client.get("/models")
            response.raise_for_status()
            payload = response.json()
            if not _model_is_available(payload, self.model):
                response = await self._client.get("/models")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(
                "OpenAI is unreachable or rejected the credentials"
            ) from exc
        return OpenAIStatus(
            status="ok",
            url=str(self._client.base_url).rstrip("/"),
            configured_model=self.model,
            model_available=_model_is_available(payload, self.model),
        )


def _normalize_tool_call(call: object) -> dict[str, object]:
    if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
        raise OllamaError("OpenAI chat returned invalid tool calls")
    function = dict(call["function"])
    arguments = function.get("arguments", "{}")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise OllamaError("OpenAI chat returned invalid tool arguments") from exc
    if not isinstance(arguments, dict):
        raise OllamaError("OpenAI chat returned invalid tool arguments")
    function["arguments"] = arguments
    return {"id": call.get("id"), "type": "function", "function": function}


def _model_is_available(payload: object, model: str) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("id") == model:
        return True
    data = payload.get("data")
    return isinstance(data, list) and any(
        isinstance(item, dict) and item.get("id") == model for item in data
    )


def _openai_messages(
    messages: list[dict[str, object]],
) -> list[dict[str, object]]:
    converted: list[dict[str, object]] = []
    for message in messages:
        item = dict(message)
        if item.get("role") == "assistant" and isinstance(
            item.get("tool_calls"), list
        ):
            item["tool_calls"] = [
                _serialize_tool_call(call) for call in item["tool_calls"]
            ]
        if item.get("role") == "tool":
            item.pop("tool_name", None)
            if not item.get("tool_call_id"):
                raise OllamaError("OpenAI tool result is missing tool_call_id")
        converted.append(item)
    return converted


def _serialize_tool_call(call: object) -> dict[str, object]:
    if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
        raise OllamaError("Invalid tool call")
    serialized = dict(call)
    function = dict(call["function"])
    arguments = function.get("arguments", {})
    if isinstance(arguments, dict):
        function["arguments"] = json.dumps(arguments, ensure_ascii=False)
    serialized["function"] = function
    return serialized


def _is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 409, 429} or status_code >= 500


async def _retry_openai(
    attempt: int,
    *,
    reason: str,
    request_id: str | None,
) -> bool:
    if attempt >= OPENAI_CHAT_ATTEMPTS - 1:
        return False
    delay = OPENAI_RETRY_DELAYS[attempt + 1]
    logger.warning(
        "Transient OpenAI chat failure; retrying in {} seconds: {} "
        "request_id={}",
        delay,
        reason,
        request_id or "unavailable",
    )
    await asyncio.sleep(delay)
    return True
