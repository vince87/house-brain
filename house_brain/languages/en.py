"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": (
        "The plan was rejected becaus"
        "e the authorization code is "
        "missing, malformed, or incor"
        "rect; no action was simulate"
        "d or executed."
    ),
    "web_search_unavailable": (
        "Web search is not configured"
        " on this House Brain instanc"
        "e."
    ),
    "entity_ambiguous": (
        "The requested name does not "
        "identify one controllable en"
        "tity. Specify the device's e"
        "xact name."
    ),
    "entity_not_found": (
        "I could not find an entity m"
        "atching the requested name. "
        "Check the device name."
    ),
    "entity_not_controllable": (
        "The requested entity exists,"
        " but it is not included amon"
        "g the controllable entities."
    ),
    "authorization_not_validated": (
        "The plan was rejected becaus"
        "e the supplied code was not "
        "validated by an action tool;"
        " no action was simulated or "
        "executed."
    ),
    "action_not_validated": (
        "I could not complete the com"
        "mand because no action tool "
        "validated it; no action was "
        "simulated or executed."
    ),
}

REJECTION_REASONS = {
    "authorization_code": (
        "the code is missing, malform"
        "ed, or incorrect"
    ),
    "kill_switch": (
        "real execution is disabled b"
        "y the kill switch"
    ),
    "mode": (
        "the requested mode is not au"
        "thorized"
    ),
    "explicit_entity": (
        "the proposed entity does not"
        " match the requested entity "
        "ID"
    ),
    "unresolved": (
        "the device name was not reso"
        "lved by the server"
    ),
    "no_target": (
        "the search did not identify "
        "one controllable entity"
    ),
    "resolved_entity": (
        "the proposed entity does not"
        " match the server resolution"
    ),
    "not_included": (
        "the requested entity ID is n"
        "ot controllable"
    ),
    "action": (
        "the requested action is not "
        "authorized by policy"
    ),
    "value": (
        "a requested value is not aut"
        "horized by policy"
    ),
    "parameter": (
        "a requested parameter is not"
        " authorized by policy"
    ),
    "invalid": (
        "the generated command is inv"
        "alid"
    ),
    "policy": (
        "server policy rejected the p"
        "lan"
    ),
}

REJECTION_PREFIX = "The plan was rejected because "
REJECTION_SUFFIX = "; no action was simulated or executed."
