"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": (
        "Der Plan wurde abgelehnt, we"
        "il der Autorisierungscode fe"
        "hlt, ungültig formatiert ode"
        "r falsch ist; es wurde keine"
        " Aktion simuliert oder ausge"
        "führt."
    ),
    "web_search_unavailable": (
        "Die Websuche ist auf dieser House-Brain-Instanz nicht konfiguriert."
    ),
    "entity_ambiguous": (
        "Der angeforderte Name bezeic"
        "hnet keine eindeutig steuerb"
        "are Entität. Gib den genauen"
        " Gerätenamen an."
    ),
    "entity_not_found": (
        "Ich habe keine Entität gefun"
        "den, die dem angeforderten N"
        "amen entspricht. Prüfe den G"
        "erätenamen."
    ),
    "entity_not_controllable": (
        "Die angeforderte Entität exi"
        "stiert, gehört aber nicht zu"
        " den steuerbaren Entitäten."
    ),
    "authorization_not_validated": (
        "Der Plan wurde abgelehnt, we"
        "il der angegebene Code nicht"
        " von einem Aktionswerkzeug g"
        "eprüft wurde; es wurde keine"
        " Aktion simuliert oder ausge"
        "führt."
    ),
    "action_not_validated": (
        "Der Befehl konnte nicht abge"
        "schlossen werden, weil ihn k"
        "ein Aktionswerkzeug geprüft "
        "hat; es wurde keine Aktion s"
        "imuliert oder ausgeführt."
    ),
}

REJECTION_REASONS = {
    "device_code": ("das Gerät seinen Home-Assistant-Code benötigt"),
    "service": ("der erzeugte Dienst in Home Assistant nicht existiert"),
    "authorization_code": ("der Code fehlt, ungültig formatiert oder falsch ist"),
    "kill_switch": (
        "die reale Ausführung durch den Sicherheitsschalter deaktiviert ist"
    ),
    "mode": ("der angeforderte Modus nicht autorisiert ist"),
    "explicit_entity": (
        "die vorgeschlagene Entität nicht der angeforderten Entitäts-ID entspricht"
    ),
    "unresolved": ("der Gerätename vom Server nicht aufgelöst wurde"),
    "no_target": ("die Suche keine eindeutig steuerbare Entität ermittelt hat"),
    "resolved_entity": (
        "die vorgeschlagene Entität nicht der Serverauflösung entspricht"
    ),
    "not_included": ("die angeforderte Entitäts-ID nicht steuerbar ist"),
    "action": ("die angeforderte Aktion nicht durch die Richtlinie autorisiert ist"),
    "value": ("ein angeforderter Wert nicht durch die Richtlinie autorisiert ist"),
    "parameter": (
        "ein angeforderter Parameter nicht durch die Richtlinie autorisiert ist"
    ),
    "invalid": ("der erzeugte Befehl ungültig ist"),
    "policy": ("die Serverrichtlinie den Plan abgelehnt hat"),
}

REJECTION_PREFIX = "Der Plan wurde abgelehnt, weil "
REJECTION_SUFFIX = "; es wurde keine Aktion simuliert oder ausgeführt."
