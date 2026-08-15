import os
import re
from functools import lru_cache

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    SecretStr,
    field_validator,
)

from house_brain.autonomy import (
    AutonomyPolicyCatalog,
    load_autonomy_policy,
)
from house_brain.languages import SUPPORTED_LANGUAGES

DEPRECATED_AUTONOMY_VARIABLES = (
    "AUTONOMOUS_EVENT_ALLOWLIST",
    "AUTONOMOUS_EXECUTE_EVENT_ALLOWLIST",
    "AUTONOMOUS_ACTION_ALLOWLIST",
    "AUTONOMOUS_ACTION_CONSTRAINTS",
    "AUTONOMOUS_EXECUTE_MAX_ACTIONS",
)


class Settings(BaseModel):
    """Runtime configuration loaded from environment variables."""

    model_config = ConfigDict(frozen=True)

    home_assistant_url: HttpUrl
    home_assistant_token: SecretStr
    home_assistant_timeout: float = Field(default=10.0, gt=0)
    home_assistant_service_cache_ttl: float = Field(default=300.0, ge=5, le=3600)
    api_key: SecretStr | None = None
    ollama_url: HttpUrl = HttpUrl("http://host.docker.internal:11434")
    ollama_model: str = "gemma4:12b"
    ollama_timeout: float = Field(default=120.0, gt=0)
    house_brain_language: str = "it"
    searxng_url: HttpUrl | None = None
    web_search_timeout: float = Field(default=10.0, gt=0, le=30)
    web_search_max_results: int = Field(default=10, ge=1, le=10)
    memory_database_path: str = "/data/house_brain.db"
    autonomy_policy_path: str = "/app/autonomy.yaml"
    autonomy_policy: AutonomyPolicyCatalog = Field(
        default_factory=AutonomyPolicyCatalog.empty
    )
    autonomous_execution_enabled: bool = False

    @field_validator("house_brain_language", mode="before")
    @classmethod
    def validate_house_brain_language(cls, value: object) -> str:
        language = str(value).strip().replace("_", "-").lower()
        if not re.fullmatch(
            r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*",
            language,
        ):
            raise ValueError("HOUSE_BRAIN_LANGUAGE must be a valid BCP 47 language tag")
        if language.partition("-")[0] not in SUPPORTED_LANGUAGES:
            supported = ", ".join(SUPPORTED_LANGUAGES)
            raise ValueError(
                "HOUSE_BRAIN_LANGUAGE is not installed; "
                f"supported languages: {supported}"
            )
        return language

    @classmethod
    def from_env(cls) -> "Settings":
        deprecated = [
            name
            for name in DEPRECATED_AUTONOMY_VARIABLES
            if os.getenv(name) is not None
        ]
        if deprecated:
            names = ", ".join(deprecated)
            raise RuntimeError(
                f"Remove deprecated autonomy environment variables: {names}"
            )

        values = {
            "home_assistant_url": os.getenv("HOME_ASSISTANT_URL"),
            "home_assistant_token": os.getenv("HOME_ASSISTANT_TOKEN"),
            "home_assistant_timeout": os.getenv("HOME_ASSISTANT_TIMEOUT", "10"),
            "home_assistant_service_cache_ttl": os.getenv(
                "HOME_ASSISTANT_SERVICE_CACHE_TTL", "300"
            ),
            "api_key": os.getenv("HOUSE_BRAIN_API_KEY"),
            "ollama_url": os.getenv("OLLAMA_URL", "http://host.docker.internal:11434"),
            "ollama_model": os.getenv("OLLAMA_MODEL", "gemma4:12b"),
            "ollama_timeout": os.getenv("OLLAMA_TIMEOUT", "120"),
            "house_brain_language": os.getenv("HOUSE_BRAIN_LANGUAGE", "it"),
            "searxng_url": os.getenv("SEARXNG_URL") or None,
            "web_search_timeout": os.getenv("WEB_SEARCH_TIMEOUT", "10"),
            "web_search_max_results": os.getenv("WEB_SEARCH_MAX_RESULTS", "10"),
            "memory_database_path": os.getenv(
                "MEMORY_DATABASE_PATH", "/data/house_brain.db"
            ),
            "autonomy_policy_path": os.getenv(
                "AUTONOMY_POLICY_PATH", "/app/autonomy.yaml"
            ),
            "autonomous_execution_enabled": os.getenv(
                "AUTONOMOUS_EXECUTION_ENABLED", "false"
            ),
        }
        values["autonomy_policy"] = load_autonomy_policy(values["autonomy_policy_path"])

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
