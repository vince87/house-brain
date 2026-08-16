"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": (
        "Le plan a été refusé car le "
        "code d’autorisation est abse"
        "nt, mal formé ou incorrect ;"
        " aucune action n’a été simul"
        "ée ni exécutée."
    ),
    "web_search_unavailable": (
        "La recherche web n’est pas configurée sur cette instance de House Brain."
    ),
    "entity_ambiguous": (
        "Le nom demandé n’identifie p"
        "as une entité contrôlable un"
        "ique. Indiquez le nom exact "
        "de l’appareil."
    ),
    "entity_not_found": (
        "Je n’ai trouvé aucune entité"
        " correspondant au nom demand"
        "é. Vérifiez le nom de l’appa"
        "reil."
    ),
    "entity_not_controllable": (
        "L’entité demandée existe, ma"
        "is elle ne fait pas partie d"
        "es entités contrôlables."
    ),
    "authorization_not_validated": (
        "Le plan a été refusé car le "
        "code fourni n’a pas été vali"
        "dé par un outil d’action ; a"
        "ucune action n’a été simulée"
        " ni exécutée."
    ),
    "action_not_validated": (
        "Je n’ai pas pu exécuter la c"
        "ommande car aucun outil d’ac"
        "tion ne l’a validée ; aucune"
        " action n’a été simulée ni e"
        "xécutée."
    ),
}

REJECTION_REASONS = {
    "device_code": ("l’appareil exige son code Home Assistant"),
    "service": ("le service généré n’existe pas dans Home Assistant"),
    "authorization_code": ("le code est absent, mal formé ou incorrect"),
    "kill_switch": ("l’exécution réelle est désactivée par l’interrupteur de sécurité"),
    "mode": ("le mode demandé n’est pas autorisé"),
    "explicit_entity": ("l’entité proposée ne correspond pas à l’identifiant demandé"),
    "unresolved": ("le nom de l’appareil n’a pas été résolu par le serveur"),
    "no_target": ("la recherche n’a pas identifié une entité contrôlable unique"),
    "resolved_entity": (
        "l’entité proposée ne correspond pas à la résolution du serveur"
    ),
    "not_included": ("l’identifiant demandé n’est pas contrôlable"),
    "action": ("l’action demandée n’est pas autorisée par la politique"),
    "value": ("une valeur demandée n’est pas autorisée par la politique"),
    "parameter": ("un paramètre demandé n’est pas autorisé par la politique"),
    "invalid": ("la commande générée n’est pas valide"),
    "policy": ("la politique du serveur a refusé le plan"),
}

REJECTION_PREFIX = "Le plan a été refusé car "
REJECTION_SUFFIX = " ; aucune action n’a été simulée ni exécutée."
