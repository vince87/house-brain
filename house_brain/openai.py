import json

import httpx
from pydantic import BaseModel

from house_brain.config import Settings
from house_brain.ollama import OllamaError


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
        if settings.openai_api_key is None:
            raise OllamaError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self.model = settings.openai_model
        self._client = httpx.AsyncClient(
            base_url=str(settings.openai_base_url).rstrip("/"),
            timeout=settings.openai_timeout,
            headers={
                "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
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
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
            message = body["choices"][0]["message"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise OllamaError("OpenAI chat request failed") from exc
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

    async def status(self) -> OpenAIStatus:
        try:
            response = await self._client.get(f"/models/{self.model}")
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
            model_available=payload.get("id") == self.model,
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
