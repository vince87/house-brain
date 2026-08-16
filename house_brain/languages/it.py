"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": (
        "Il piano è stato respinto pe"
        "rché il codice è mancante, m"
        "alformato o errato; nessuna "
        "azione è stata simulata o es"
        "eguita."
    ),
    "web_search_unavailable": (
        "La ricerca web non è configurata in questa istanza di House Brain."
    ),
    "entity_ambiguous": (
        "Il nome richiesto non identi"
        "fica un'unica entità control"
        "labile. Specifica il nome es"
        "atto del dispositivo."
    ),
    "entity_not_found": (
        "Non ho trovato alcuna entità"
        " corrispondente al nome rich"
        "iesto. Verifica il nome del "
        "dispositivo."
    ),
    "entity_not_controllable": (
        "L'entità richiesta esiste, ma non è inclusa tra quelle controllabili."
    ),
    "authorization_not_validated": (
        "Il piano è stato respinto pe"
        "rché il codice fornito non è"
        " stato validato da uno strum"
        "ento di azione; nessuna azio"
        "ne è stata simulata o esegui"
        "ta."
    ),
    "action_not_validated": (
        "Non ho potuto completare il "
        "comando perché nessuno strum"
        "ento di azione lo ha validat"
        "o; nessuna azione è stata si"
        "mulata o eseguita."
    ),
}

REJECTION_REASONS = {
    "device_code": ("il dispositivo richiede il proprio codice Home Assistant"),
    "service": ("il servizio generato non esiste in Home Assistant"),
    "authorization_code": ("il codice è mancante, malformato o errato"),
    "kill_switch": ("l'esecuzione reale è disabilitata dal kill switch"),
    "mode": ("la modalità richiesta non è autorizzata"),
    "explicit_entity": ("l'entità proposta non corrisponde all'entity_id richiesto"),
    "unresolved": ("il nome del dispositivo non è stato risolto dal server"),
    "no_target": ("la ricerca non ha individuato un'unica entità controllabile"),
    "resolved_entity": (
        "l'entità proposta non corrisponde a quella risolta dal server"
    ),
    "not_included": ("l'entity_id richiesto non è incluso tra quelli controllabili"),
    "action": ("l'azione richiesta non è autorizzata dalla policy"),
    "value": ("un valore richiesto non è autorizzato dalla policy"),
    "parameter": ("un parametro richiesto non è autorizzato dalla policy"),
    "invalid": ("il comando generato non è valido"),
    "policy": ("la policy del server ha rifiutato il piano"),
}

REJECTION_PREFIX = "Il piano è stato respinto perché "
REJECTION_SUFFIX = "; nessuna azione è stata simulata o eseguita."
