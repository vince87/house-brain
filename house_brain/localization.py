"""Translate deterministic safety responses at the server boundary."""

_ENGLISH_MESSAGES: dict[str, str] = {
    "authorization_invalid": (
        "The plan was rejected because the authorization code is missing, "
        "malformed, or incorrect; no action was simulated or executed."
    ),
    "web_search_unavailable": (
        "Web search is not configured on this House Brain instance."
    ),
    "entity_ambiguous": (
        "The requested name does not identify one controllable entity. "
        "Specify the device's exact name."
    ),
    "entity_not_found": (
        "I could not find an entity matching the requested name. "
        "Check the device name."
    ),
    "entity_not_controllable": (
        "The requested entity exists, but it is not included among the "
        "controllable entities."
    ),
    "authorization_not_validated": (
        "The plan was rejected because the supplied code was not validated by "
        "an action tool; no action was simulated or executed."
    ),
    "action_not_validated": (
        "I could not complete the command because no action tool validated it; "
        "no action was simulated or executed."
    ),
}

_ITALIAN_MESSAGES: dict[str, str] = {
    "authorization_invalid": (
        "Il piano è stato respinto perché il codice è mancante, malformato o "
        "errato; nessuna azione è stata simulata o eseguita."
    ),
    "web_search_unavailable": (
        "La ricerca web non è configurata in questa istanza di House Brain."
    ),
    "entity_ambiguous": (
        "Il nome richiesto non identifica un'unica entità controllabile. "
        "Specifica il nome esatto del dispositivo."
    ),
    "entity_not_found": (
        "Non ho trovato alcuna entità corrispondente al nome richiesto. "
        "Verifica il nome del dispositivo."
    ),
    "entity_not_controllable": (
        "L'entità richiesta esiste, ma non è inclusa tra quelle controllabili."
    ),
    "authorization_not_validated": (
        "Il piano è stato respinto perché il codice fornito non è stato "
        "validato da uno strumento di azione; nessuna azione è stata simulata "
        "o eseguita."
    ),
    "action_not_validated": (
        "Non ho potuto completare il comando perché nessuno strumento di "
        "azione lo ha validato; nessuna azione è stata simulata o eseguita."
    ),
}

_ENGLISH_REJECTION_REASONS: dict[str, str] = {
    "authorization_code": "the code is missing, malformed, or incorrect",
    "kill_switch": "real execution is disabled by the kill switch",
    "mode": "the requested mode is not authorized",
    "explicit_entity": "the proposed entity does not match the requested entity ID",
    "unresolved": "the device name was not resolved by the server",
    "no_target": "the search did not identify one controllable entity",
    "resolved_entity": "the proposed entity does not match the server resolution",
    "not_included": "the requested entity ID is not controllable",
    "action": "the requested action is not authorized by policy",
    "value": "a requested value is not authorized by policy",
    "parameter": "a requested parameter is not authorized by policy",
    "invalid": "the generated command is invalid",
    "policy": "server policy rejected the plan",
}

_ITALIAN_REJECTION_REASONS: dict[str, str] = {
    "authorization_code": "il codice è mancante, malformato o errato",
    "kill_switch": "l'esecuzione reale è disabilitata dal kill switch",
    "mode": "la modalità richiesta non è autorizzata",
    "explicit_entity": "l'entità proposta non corrisponde all'entity_id richiesto",
    "unresolved": "il nome del dispositivo non è stato risolto dal server",
    "no_target": "la ricerca non ha individuato un'unica entità controllabile",
    "resolved_entity": "l'entità proposta non corrisponde a quella risolta dal server",
    "not_included": "l'entity_id richiesto non è incluso tra quelli controllabili",
    "action": "l'azione richiesta non è autorizzata dalla policy",
    "value": "un valore richiesto non è autorizzato dalla policy",
    "parameter": "un parametro richiesto non è autorizzato dalla policy",
    "invalid": "il comando generato non è valido",
    "policy": "la policy del server ha rifiutato il piano",
}


def language_family(language: str) -> str:
    """Return the primary language subtag."""
    return language.partition("-")[0].casefold()


def localized_message(key: str, language: str) -> str:
    """Translate a server-owned message without involving the model."""
    if language_family(language) == "it":
        return _ITALIAN_MESSAGES[key]
    return _ENGLISH_MESSAGES[key]


def localized_rejection(reason: str, language: str) -> str:
    """Translate a deterministic action rejection."""
    if language_family(language) == "it":
        detail = _ITALIAN_REJECTION_REASONS[reason]
        return (
            f"Il piano è stato respinto perché {detail}; nessuna azione è "
            "stata simulata o eseguita."
        )
    detail = _ENGLISH_REJECTION_REASONS[reason]
    return (
        f"The plan was rejected because {detail}; no action was simulated "
        "or executed."
    )


def response_language_instruction(language: str) -> str:
    """Require the model to translate every user-facing answer."""
    return (
        "\nMANDATORY OUTPUT LANGUAGE: translate every user-facing statement "
        f"and fixed explanatory phrase into BCP 47 language {language!r}. "
        "Never translate Home Assistant entity IDs, domain or service names, "
        "tool names, JSON keys, or machine-readable values."
    )
