"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": (
        "El plan fue rechazado porque"
        " el código de autorización f"
        "alta, tiene un formato incor"
        "recto o es erróneo; no se si"
        "muló ni ejecutó ninguna acci"
        "ón."
    ),
    "web_search_unavailable": (
        "La búsqueda web no está conf"
        "igurada en esta instancia de"
        " House Brain."
    ),
    "entity_ambiguous": (
        "El nombre solicitado no iden"
        "tifica una única entidad con"
        "trolable. Especifica el nomb"
        "re exacto del dispositivo."
    ),
    "entity_not_found": (
        "No encontré ninguna entidad "
        "que coincida con el nombre s"
        "olicitado. Comprueba el nomb"
        "re del dispositivo."
    ),
    "entity_not_controllable": (
        "La entidad solicitada existe"
        ", pero no está incluida entr"
        "e las entidades controlables"
        "."
    ),
    "authorization_not_validated": (
        "El plan fue rechazado porque"
        " el código proporcionado no "
        "fue validado por una herrami"
        "enta de acción; no se simuló"
        " ni ejecutó ninguna acción."
    ),
    "action_not_validated": (
        "No pude completar el comando"
        " porque ninguna herramienta "
        "de acción lo validó; no se s"
        "imuló ni ejecutó ninguna acc"
        "ión."
    ),
    "action_results_authoritative": (
        "Resultados de acciones confirmados por el servidor:"
    ),
    "action_status_executed": "ejecutada",
    "action_status_simulated": "simulada",
    "action_status_rejected": "rechazada",
}

REJECTION_REASONS = {
    "device_code": ("el dispositivo requiere su código de Home Assistant"),
    "service": ("el servicio generado no existe en Home Assistant"),
    "authorization_code": (
        "el código falta, tiene un fo"
        "rmato incorrecto o es erróne"
        "o"
    ),
    "kill_switch": (
        "la ejecución real está desha"
        "bilitada por el interruptor "
        "de seguridad"
    ),
    "mode": (
        "el modo solicitado no está a"
        "utorizado"
    ),
    "explicit_entity": (
        "la entidad propuesta no coin"
        "cide con el ID de entidad so"
        "licitado"
    ),
    "unresolved": (
        "el servidor no resolvió el n"
        "ombre del dispositivo"
    ),
    "no_target": (
        "la búsqueda no identificó un"
        "a única entidad controlable"
    ),
    "resolved_entity": (
        "la entidad propuesta no coin"
        "cide con la resolución del s"
        "ervidor"
    ),
    "not_included": (
        "el ID de entidad solicitado "
        "no es controlable"
    ),
    "action": (
        "la acción solicitada no está"
        " autorizada por la política"
    ),
    "value": (
        "un valor solicitado no está "
        "autorizado por la política"
    ),
    "parameter": (
        "un parámetro solicitado no e"
        "stá autorizado por la políti"
        "ca"
    ),
    "invalid": (
        "el comando generado no es vá"
        "lido"
    ),
    "policy": (
        "la política del servidor rec"
        "hazó el plan"
    ),
}

REJECTION_PREFIX = "El plan fue rechazado porque "
REJECTION_SUFFIX = "; no se simuló ni ejecutó ninguna acción."

