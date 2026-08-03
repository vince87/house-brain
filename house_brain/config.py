import os
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr

from house_brain.autonomy import parse_allowlist


class Settings(BaseModel):
    """Runtime configuration loaded from environment variables."""

    model_config = ConfigDict(frozen=True)

    home_assistant_url: HttpUrl
    home_assistant_token: SecretStr
    home_assistant_timeout: float = Field(default=10.0, gt=0)
    api_key: SecretStr | None = None
    ollama_url: HttpUrl = HttpUrl("http://host.docker.internal:11434")
    ollama_model: str = "gemma4:12b"
    ollama_timeout: float = Field(default=120.0, gt=0)
    memory_database_path: str = "/data/house_brain.db"
    autonomous_event_allowlist: frozenset[str] = frozenset()
    autonomous_action_allowlist: frozenset[str] = frozenset()

    @classmethod
    def from_env(cls) -> "Settings":
        values = {
            "home_assistant_url": os.getenv("HOME_ASSISTANT_URL"),
            "home_assistant_token": os.getenv("HOME_ASSISTANT_TOKEN"),
            "home_assistant_timeout": os.getenv("HOME_ASSISTANT_TIMEOUT", "10"),
            "api_key": os.getenv("HOUSE_BRAIN_API_KEY"),
            "ollama_url": os.getenv(
                "OLLAMA_URL", "http://host.docker.internal:11434"
            ),
            "ollama_model": os.getenv("OLLAMA_MODEL", "gemma4:12b"),
            "ollama_timeout": os.getenv("OLLAMA_TIMEOUT", "120"),
            "memory_database_path": os.getenv(
                "MEMORY_DATABASE_PATH", "/data/house_brain.db"
            ),
            "autonomous_event_allowlist": parse_allowlist(
                os.getenv("AUTONOMOUS_EVENT_ALLOWLIST")
            ),
            "autonomous_action_allowlist": parse_allowlist(
                os.getenv("AUTONOMOUS_ACTION_ALLOWLIST")
            ),
        }
        required = {
            "home_assistant_url": "HOME_ASSISTANT_URL",
            "home_assistant_token": "HOME_ASSISTANT_TOKEN",
            "api_key": "HOUSE_BRAIN_API_KEY",
        }
        missing = [
            environment_name
            for field_name, environment_name in required.items()
            if not values[field_name]
        ]
        if missing:
            variables = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {variables}")

        return cls.model_validate(values)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
