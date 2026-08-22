import asyncio

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from house_brain.config import Settings

OLLAMA_CHAT_ATTEMPTS = 3
OLLAMA_RETRY_DELAYS = (0.0, 0.5, 1.0)
OLLAMA_RECOVERY_INSTRUCTION = (
    "The previous model response was empty. Return either a non-empty final "
    "answer or a valid tool call. When calling a tool, use its exact name and "
    "provide a complete arguments object that strictly follows its JSON "
    "schema. Do not return an empty message."
)


class OllamaError(Exception):
    """Raised when Ollama is unavailable or returns invalid data."""


class OllamaModel(BaseModel):
    name: str
    model: str | None = None


class OllamaTagsResponse(BaseModel):
    models: list[OllamaModel] = Field(default_factory=list)


class OllamaStatus(BaseModel):
    status: str
    url: str
    configured_model: str
    model_available: bool
    available_models: list[str]


class OllamaClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = str(settings.ollama_url).rstrip("/")
        self.model = settings.ollama_model
        self.context_window = settings.ollama_context_window
        self.max_output_tokens = settings.ollama_max_output_tokens
        self.temperature = settings.ollama_temperature
        self._client = httpx.AsyncClient(
            base_url=self.url,
            timeout=settings.ollama_timeout,
            transport=transport,
        )

    async def __aenter__(self) -> "OllamaClient":
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
        recovery_instruction_required = False
        for attempt in range(OLLAMA_CHAT_ATTEMPTS):
            request_messages = [_ollama_message(message) for message in messages]
            if recovery_instruction_required:
                request_messages = _add_recovery_instruction(
                    request_messages,
                    OLLAMA_RECOVERY_INSTRUCTION,
                )
            payload = {
                "model": self.model,
                "messages": request_messages,
                "tools": tools,
                "stream": False,
                "think": recovery_instruction_required,
                "options": {
                    "num_ctx": self.context_window,
                    "num_predict": self.max_output_tokens,
                    "temperature": self.temperature,
                },
            }
            try:
                response = await self._client.post("/api/chat", json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if _is_retryable_status(exc.response.status_code) and await self._retry(
                    attempt,
                    reason=f"HTTP {exc.response.status_code}",
                ):
                    continue
                raise OllamaError("Ollama chat request failed") from exc
            except httpx.RequestError as exc:
                if await self._retry(attempt, reason=type(exc).__name__):
                    continue
                raise OllamaError("Ollama chat request failed") from exc

            try:
                response_payload = response.json()
                message = response_payload["message"]
                if not isinstance(message, dict):
                    raise ValueError("message is not an object")
            except (KeyError, TypeError, ValueError) as exc:
                raise OllamaError("Ollama chat returned invalid data") from exc

            content = message.get("content")
            tool_calls = message.get("tool_calls")
            if (isinstance(content, str) and content.strip()) or (
                isinstance(tool_calls, list) and tool_calls
            ):
                sanitized_message = dict(message)
                sanitized_message.pop("thinking", None)
                return sanitized_message

            done_reason = response_payload.get("done_reason")
            prompt_tokens = response_payload.get("prompt_eval_count")
            output_tokens = response_payload.get("eval_count")
            thinking = message.get("thinking")
            logger.warning(
                "Ollama returned no content or tool calls: attempt={}/{} "
                "done={} done_reason={} prompt_tokens={} output_tokens={} "
                "thinking_present={}",
                attempt + 1,
                OLLAMA_CHAT_ATTEMPTS,
                response_payload.get("done"),
                done_reason,
                prompt_tokens,
                output_tokens,
                isinstance(thinking, str) and bool(thinking.strip()),
            )
            if done_reason == "length":
                raise OllamaError(
                    "Ollama exhausted the configured context window before "
                    "returning a response"
                )

            recovery_instruction_required = True
            if attempt < OLLAMA_CHAT_ATTEMPTS - 1:
                logger.warning(
                    "Ollama returned an empty response; retrying with recovery "
                    "instruction ({}/{})",
                    attempt + 1,
                    OLLAMA_CHAT_ATTEMPTS - 1,
                )

        raise OllamaError(
            "Ollama chat returned an empty response after "
            f"{OLLAMA_CHAT_ATTEMPTS} attempts"
        )

    async def _retry(self, attempt: int, *, reason: str) -> bool:
        if attempt >= OLLAMA_CHAT_ATTEMPTS - 1:
            return False
        delay = OLLAMA_RETRY_DELAYS[attempt + 1]
        logger.warning(
            "Transient Ollama chat failure; retrying in {} seconds: {}",
            delay,
            reason,
        )
        await asyncio.sleep(delay)
        return True

    async def status(self) -> OllamaStatus:
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            payload = OllamaTagsResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError("Ollama is unreachable or returned invalid data") from exc

        models = sorted(item.name for item in payload.models)
        return OllamaStatus(
            status="ok",
            url=self.url,
            configured_model=self.model,
            model_available=self.model in models,
            available_models=models,
        )


def _is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 429} or status_code >= 500


def _add_recovery_instruction(
    messages: list[dict[str, object]],
    instruction: str,
) -> list[dict[str, object]]:
    recovered = list(messages)
    insert_at = 0
    while insert_at < len(recovered) and recovered[insert_at].get("role") == "system":
        insert_at += 1
    recovered.insert(insert_at, {"role": "system", "content": instruction})
    return recovered


def _ollama_message(message: dict[str, object]) -> dict[str, object]:
    cleaned = {key: value for key, value in message.items() if value is not None}
    cleaned.pop("tool_call_id", None)
    return cleaned
