import os
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr


class Settings(BaseModel):
    """Runtime configuration loaded from environment variables."""

    model_config = ConfigDict(frozen=True)

    home_assistant_url: HttpUrl
    home_assistant_token: SecretStr
    home_assistant_timeout: float = Field(default=10.0, gt=0)
    ollama_url: HttpUrl = HttpUrl("http://host.docker.internal:11434")
    ollama_model: str = "gemma4:12b"
    ollama_timeout: float = Field(default=120.0, gt=0)

    @classmethod
    def from_env(cls) -> "Settings":
        values = {
            "home_assistant_url": os.getenv("HOME_ASSISTANT_URL"),
            "home_assistant_token": os.getenv("HOME_ASSISTANT_TOKEN"),
            "home_assistant_timeout": os.getenv("HOME_ASSISTANT_TIMEOUT", "10"),
            "ollama_url": os.getenv(
                "OLLAMA_URL", "http://host.docker.internal:11434"
            ),
            "ollama_model": os.getenv("OLLAMA_MODEL", "gemma4:12b"),
            "ollama_timeout": os.getenv("OLLAMA_TIMEOUT", "120"),
        }
        missing = [
            name
            for name in ("home_assistant_url", "home_assistant_token")
            if not values[name]
        ]
        if missing:
            variables = ", ".join(name.upper() for name in missing)
            raise RuntimeError(f"Missing required environment variables: {variables}")

        return cls.model_validate(values)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
