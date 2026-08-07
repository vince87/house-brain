"""Built-in language packs for deterministic server responses."""

from importlib import import_module
from types import ModuleType

SUPPORTED_LANGUAGES = (
    "ar",
    "de",
    "en",
    "es",
    "fr",
    "it",
    "ja",
    "ko",
    "pt",
    "zh",
)


def language_family(language: str) -> str:
    """Return a supported primary subtag or English as the safe fallback."""
    family = language.partition("-")[0].casefold()
    return family if family in SUPPORTED_LANGUAGES else "en"


def _pack(language: str) -> ModuleType:
    return import_module(f"{__name__}.{language_family(language)}")


def localized_message(key: str, language: str) -> str:
    """Translate a server-owned message without involving the model."""
    return str(_pack(language).MESSAGES[key])


def localized_rejection(reason: str, language: str) -> str:
    """Translate a deterministic action rejection."""
    pack = _pack(language)
    return (
        str(pack.REJECTION_PREFIX)
        + str(pack.REJECTION_REASONS[reason])
        + str(pack.REJECTION_SUFFIX)
    )


def response_language_instruction(language: str) -> str:
    """Require the model to translate every user-facing answer."""
    return (
        "\nMANDATORY OUTPUT LANGUAGE: translate every user-facing statement "
        f"and fixed explanatory phrase into BCP 47 language {language!r}. "
        "Never translate Home Assistant entity IDs, domain or service names, "
        "tool names, JSON keys, or machine-readable values."
    )
