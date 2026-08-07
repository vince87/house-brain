"""Localized deterministic messages for agent responses."""

_MESSAGES: dict[str, dict[str, str]] = {
    "authorization_invalid": {
        "it": (
            "Il piano è stato respinto perché il codice è mancante, "
            "malformato o errato; nessuna azione è stata simulata o eseguita."
        ),
        "en": (
            "The plan was rejected because the authorization code is missing, "
            "malformed, or incorrect; no action was simulated or executed."
        ),
    },
    "web_search_unavailable": {
        "it": "La ricerca web non è configurata in questa istanza di House Brain.",
        "en": "Web search is not configured on this House Brain instance.",
    },
    "entity_ambiguous": {
        "it": (
            "Il nome richiesto non identifica un'unica entità controllabile. "
            "Specifica il nome esatto del dispositivo."
        ),
        "en": (
            "The requested name does not identify one controllable entity. "
            "Specify the device's exact name."
        ),
    },
    "entity_not_found": {
        "it": (
            "Non ho trovato alcuna entità corrispondente al nome richiesto. "
            "Verifica il nome del dispositivo."
        ),
        "en": (
            "I could not find an entity matching the requested name. "
            "Check the device name."
        ),
    },
    "entity_not_controllable": {
        "it": (
            "L'entità richiesta esiste, ma non è inclusa tra quelle "
            "controllabili."
        ),
        "en": (
            "The requested entity exists, but it is not included among the "
            "controllable entities."
        ),
    },
    "authorization_not_validated": {
        "it": (
            "Il piano è stato respinto perché il codice fornito non è stato "
            "validato da uno strumento di azione; nessuna azione è stata "
            "simulata o eseguita."
        ),
        "en": (
            "The plan was rejected because the supplied code was not validated "
            "by an action tool; no action was simulated or executed."
        ),
    },
    "action_not_validated": {
        "it": (
            "Non ho potuto completare il comando perché nessuno strumento di "
            "azione lo ha validato; nessuna azione è stata simulata o eseguita."
        ),
        "en": (
            "I could not complete the command because no action tool validated "
            "it; no action was simulated or executed."
        ),
    },
}


def language_family(language: str) -> str:
    """Return the primary language subtag used by deterministic translations."""
    return language.partition("-")[0].casefold()


def localized_message(key: str, language: str) -> str:
    """Return a deterministic message, falling back to English."""
    translations = _MESSAGES[key]
    return translations.get(language_family(language), translations["en"])


def response_language_instruction(language: str) -> str:
    """Build a safe model instruction from a validated BCP 47 tag."""
    return (
        "\nWrite every user-facing answer in the language identified by "
        f"the BCP 47 tag {language!r}. Keep Home Assistant entity IDs, service "
        "names, tool names, and machine-readable values unchanged."
    )
