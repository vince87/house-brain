import httpx
from pydantic import BaseModel, Field

from house_brain.config import Settings


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
        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": tools,
                    "stream": False,
                    "think": False,
                },
            )
            response.raise_for_status()
            message = response.json()["message"]
            if not isinstance(message, dict):
                raise ValueError("message is not an object")
            return message
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise OllamaError("Ollama chat returned invalid data") from exc

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
