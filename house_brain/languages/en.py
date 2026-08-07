"""Server-owned messages for this language."""

MESSAGES = {
    "authorization_invalid": "The plan was rejected because the authorization code is missing, malformed, or incorrect; no action was simulated or executed.",
    "web_search_unavailable": "Web search is not configured on this House Brain instance.",
    "entity_ambiguous": "The requested name does not identify one controllable entity. Specify the device's exact name.",
    "entity_not_found": "I could not find an entity matching the requested name. Check the device name.",
    "entity_not_controllable": "The requested entity exists, but it is not included among the controllable entities.",
    "authorization_not_validated": "The plan was rejected because the supplied code was not validated by an action tool; no action was simulated or executed.",
    "action_not_validated": "I could not complete the command because no action tool validated it; no action was simulated or executed.",
}

REJECTION_REASONS = {
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

REJECTION_PREFIX = "The plan was rejected because "
REJECTION_SUFFIX = "; no action was simulated or executed."
