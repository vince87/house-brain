"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": "Il piano è stato respinto perché il codice è mancante, malformato o errato; nessuna azione è stata simulata o eseguita.",
    "web_search_unavailable": "La ricerca web non è configurata in questa istanza di House Brain.",
    "entity_ambiguous": "Il nome richiesto non identifica un'unica entità controllabile. Specifica il nome esatto del dispositivo.",
    "entity_not_found": "Non ho trovato alcuna entità corrispondente al nome richiesto. Verifica il nome del dispositivo.",
    "entity_not_controllable": "L'entità richiesta esiste, ma non è inclusa tra quelle controllabili.",
    "authorization_not_validated": "Il piano è stato respinto perché il codice fornito non è stato validato da uno strumento di azione; nessuna azione è stata simulata o eseguita.",
    "action_not_validated": "Non ho potuto completare il comando perché nessuno strumento di azione lo ha validato; nessuna azione è stata simulata o eseguita.",
}

REJECTION_REASONS = {
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

REJECTION_PREFIX = "Il piano è stato respinto perché "
REJECTION_SUFFIX = "; nessuna azione è stata simulata o eseguita."
