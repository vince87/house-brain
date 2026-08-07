"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": "El plan fue rechazado porque el código de autorización falta, tiene un formato incorrecto o es erróneo; no se simuló ni ejecutó ninguna acción.",
    "web_search_unavailable": "La búsqueda web no está configurada en esta instancia de House Brain.",
    "entity_ambiguous": "El nombre solicitado no identifica una única entidad controlable. Especifica el nombre exacto del dispositivo.",
    "entity_not_found": "No encontré ninguna entidad que coincida con el nombre solicitado. Comprueba el nombre del dispositivo.",
    "entity_not_controllable": "La entidad solicitada existe, pero no está incluida entre las entidades controlables.",
    "authorization_not_validated": "El plan fue rechazado porque el código proporcionado no fue validado por una herramienta de acción; no se simuló ni ejecutó ninguna acción.",
    "action_not_validated": "No pude completar el comando porque ninguna herramienta de acción lo validó; no se simuló ni ejecutó ninguna acción.",
}

REJECTION_REASONS = {
    "authorization_code": "el código falta, tiene un formato incorrecto o es erróneo",
    "kill_switch": "la ejecución real está deshabilitada por el interruptor de seguridad",
    "mode": "el modo solicitado no está autorizado",
    "explicit_entity": "la entidad propuesta no coincide con el ID de entidad solicitado",
    "unresolved": "el servidor no resolvió el nombre del dispositivo",
    "no_target": "la búsqueda no identificó una única entidad controlable",
    "resolved_entity": "la entidad propuesta no coincide con la resolución del servidor",
    "not_included": "el ID de entidad solicitado no es controlable",
    "action": "la acción solicitada no está autorizada por la política",
    "value": "un valor solicitado no está autorizado por la política",
    "parameter": "un parámetro solicitado no está autorizado por la política",
    "invalid": "el comando generado no es válido",
    "policy": "la política del servidor rechazó el plan",
}

REJECTION_PREFIX = "El plan fue rechazado porque "
REJECTION_SUFFIX = "; no se simuló ni ejecutó ninguna acción."
