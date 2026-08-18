"""Server-owned messages for this language."""

MESSAGES = {
    "observe_not_grounded": (
        "Ich konnte den aktuellen Hauszustand nicht prüfen, da keine Home-Assistant-Statusabfrage erfolgreich abgeschlossen wurde."
    ),
    "authorization_invalid": (
        "Der Plan wurde abgelehnt, we"
        "il der Autorisierungscode fe"
        "hlt, ungültig formatiert ode"
        "r falsch ist; es wurde keine"
        " Aktion simuliert oder ausge"
        "führt."
    ),
    "web_search_unavailable": (
        "Die Websuche ist auf dieser "
        "House-Brain-Instanz nicht ko"
        "nfiguriert."
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
    "action_results_authoritative": "Vom Server bestätigte Aktionsergebnisse:",
    "action_status_executed": "ausgeführt",
    "action_status_simulated": "simuliert",
    "action_status_rejected": "abgelehnt",
}

REJECTION_REASONS = {
    "device_code": ("das Gerät seinen Home-Assistant-Code benötigt"),
    "service": ("der erzeugte Dienst in Home Assistant nicht existiert"),
    "authorization_code": (
        "der Code fehlt, ungültig for"
        "matiert oder falsch ist"
    ),
    "kill_switch": (
        "die reale Ausführung durch d"
        "en Sicherheitsschalter deakt"
        "iviert ist"
    ),
    "mode": (
        "der angeforderte Modus nicht"
        " autorisiert ist"
    ),
    "explicit_entity": (
        "die vorgeschlagene Entität n"
        "icht der angeforderten Entit"
        "äts-ID entspricht"
    ),
    "unresolved": (
        "der Gerätename vom Server ni"
        "cht aufgelöst wurde"
    ),
    "no_target": (
        "die Suche keine eindeutig st"
        "euerbare Entität ermittelt h"
        "at"
    ),
    "resolved_entity": (
        "die vorgeschlagene Entität n"
        "icht der Serverauflösung ent"
        "spricht"
    ),
    "not_included": (
        "die angeforderte Entitäts-ID"
        " nicht steuerbar ist"
    ),
    "action": (
        "die angeforderte Aktion nich"
        "t durch die Richtlinie autor"
        "isiert ist"
    ),
    "value": (
        "ein angeforderter Wert nicht"
        " durch die Richtlinie autori"
        "siert ist"
    ),
    "parameter": (
        "ein angeforderter Parameter "
        "nicht durch die Richtlinie a"
        "utorisiert ist"
    ),
    "invalid": (
        "der erzeugte Befehl ungültig"
        " ist"
    ),
    "policy": (
        "die Serverrichtlinie den Pla"
        "n abgelehnt hat"
    ),
}

REJECTION_PREFIX = "Der Plan wurde abgelehnt, weil "
REJECTION_SUFFIX = "; es wurde keine Aktion simuliert oder ausgeführt."

