from typing import Protocol

from house_brain.config import Settings
from house_brain.ollama import OllamaClient
from house_brain.openai import OpenAIClient


class ChatClient(Protocol):
    model: str

    async def __aenter__(self) -> "ChatClient": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None: ...

    async def chat(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> dict[str, object]: ...


def create_chat_client(settings: Settings) -> ChatClient:
    if settings.llm_provider == "openai":
        return OpenAIClient(settings)
    return OllamaClient(settings)
