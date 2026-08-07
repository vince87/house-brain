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
        "La ricerca web non è configu"
        "rata in questa istanza di Ho"
        "use Brain."
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
        "L'entità richiesta esiste, m"
        "a non è inclusa tra quelle c"
        "ontrollabili."
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
    "authorization_code": (
        "il codice è mancante, malfor"
        "mato o errato"
    ),
    "kill_switch": (
        "l'esecuzione reale è disabil"
        "itata dal kill switch"
    ),
    "mode": (
        "la modalità richiesta non è "
        "autorizzata"
    ),
    "explicit_entity": (
        "l'entità proposta non corris"
        "ponde all'entity_id richiest"
        "o"
    ),
    "unresolved": (
        "il nome del dispositivo non "
        "è stato risolto dal server"
    ),
    "no_target": (
        "la ricerca non ha individuat"
        "o un'unica entità controllab"
        "ile"
    ),
    "resolved_entity": (
        "l'entità proposta non corris"
        "ponde a quella risolta dal s"
        "erver"
    ),
    "not_included": (
        "l'entity_id richiesto non è "
        "incluso tra quelli controlla"
        "bili"
    ),
    "action": (
        "l'azione richiesta non è aut"
        "orizzata dalla policy"
    ),
    "value": (
        "un valore richiesto non è au"
        "torizzato dalla policy"
    ),
    "parameter": (
        "un parametro richiesto non è"
        " autorizzato dalla policy"
    ),
    "invalid": (
        "il comando generato non è va"
        "lido"
    ),
    "policy": (
        "la policy del server ha rifi"
        "utato il piano"
    ),
}

REJECTION_PREFIX = "Il piano è stato respinto perché "
REJECTION_SUFFIX = "; nessuna azione è stata simulata o eseguita."
