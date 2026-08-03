from secrets import compare_digest

from pydantic import SecretStr

API_KEY_HEADER = "X-API-Key"


def api_key_is_valid(provided: str | None, expected: SecretStr | None) -> bool:
    """Compare an API key without leaking timing information."""
    if provided is None or expected is None:
        return False
    return compare_digest(
        provided.encode("utf-8"),
        expected.get_secret_value().encode("utf-8"),
    )
