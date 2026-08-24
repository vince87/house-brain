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

_MODEL_TOOL_NOTICES = {
    "ar": (
        "النموذج المضبوط لا يدعم الأدوات. لم يقرأ House Brain بيانات Home "
        "Assistant ولم يسترجع الذكريات ولم يحاكِ أو ينفذ أي إجراء."
    ),
    "de": (
        "Das konfigurierte Modell unterstützt keine Tools. House Brain hat "
        "Home Assistant nicht gelesen, keine Erinnerungen abgerufen und keine "
        "Aktionen simuliert oder ausgeführt."
    ),
    "en": (
        "The configured model does not support tools. House Brain did not read "
        "Home Assistant, retrieve memories, or simulate or execute actions."
    ),
    "es": (
        "El modelo configurado no admite herramientas. House Brain no leyó "
        "Home Assistant, no recuperó memorias ni simuló o ejecutó acciones."
    ),
    "fr": (
        "Le modèle configuré ne prend pas en charge les outils. House Brain "
        "n'a pas consulté Home Assistant, récupéré de mémoires, simulé ou "
        "exécuté d'actions."
    ),
    "it": (
        "Il modello configurato non supporta i tool. House Brain non ha letto "
        "Home Assistant, recuperato memorie, simulato o eseguito azioni."
    ),
    "ja": (
        "設定されたモデルはツールに対応していません。House Brain は Home "
        "Assistant の状態を読み取らず、メモリの取得や操作のシミュレーション、"
        "実行も行っていません。"
    ),
    "ko": (
        "설정된 모델은 도구를 지원하지 않습니다. House Brain은 Home "
        "Assistant를 읽거나 메모리를 조회하지 않았으며 작업을 시뮬레이션하거나 "
        "실행하지 않았습니다."
    ),
    "pt": (
        "O modelo configurado não oferece suporte a ferramentas. O House Brain "
        "não consultou o Home Assistant, não recuperou memórias e não simulou "
        "ou executou ações."
    ),
    "zh": (
        "当前配置的模型不支持工具。House Brain 未读取 Home Assistant、检索记忆，"
        "也未模拟或执行任何操作。"
    ),
}


def language_family(language: str) -> str:
    """Return a supported primary subtag or English as the safe fallback."""
    family = language.partition("-")[0].casefold()
    return family if family in SUPPORTED_LANGUAGES else "en"


def _pack(language: str) -> ModuleType:
    return import_module(f"{__name__}.{language_family(language)}")


def localized_message(key: str, language: str) -> str:
    """Translate a server-owned message without involving the model."""
    return str(_pack(language).MESSAGES[key])


def localized_model_tool_notice(language: str) -> str:
    """Explain the deterministic limitations of response-only mode."""
    return _MODEL_TOOL_NOTICES[language_family(language)]


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


def localized_ui_messages(language: str) -> dict[str, str]:
    """Return fixed browser UI text for the configured language."""
    from house_brain.languages.ui import UI_MESSAGES

    return UI_MESSAGES[language_family(language)]


def localized_autonomy_ui_messages(language: str) -> dict[str, str]:
    """Return fixed autonomy configurator text for the selected language."""
    from house_brain.languages.admin_ui import AUTONOMY_UI_MESSAGES

    return AUTONOMY_UI_MESSAGES[language_family(language)]
