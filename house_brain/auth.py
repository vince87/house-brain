from secrets import compare_digest

from pydantic import SecretStr

API_KEY_HEADER = "X-API-Key"
AUTHORIZATION_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "


def api_key_is_valid(provided: str | None, expected: SecretStr | None) -> bool:
    """Compare an API key without leaking timing information."""
    if provided is None or expected is None:
        return False
    return compare_digest(
        provided.encode("utf-8"),
        expected.get_secret_value().encode("utf-8"),
    )


def api_key_from_headers(
    api_key: str | None,
    authorization: str | None,
) -> str | None:
    """Read the API key from REST or standard Bearer authentication."""
    if api_key:
        return api_key
    if authorization and authorization.startswith(BEARER_PREFIX):
        token = authorization[len(BEARER_PREFIX) :].strip()
        return token or None
    return None
