import re

_CODE_MARKER = re.compile(
    r"\bcodice\s*:\s*(?P<code>\S+)",
    flags=re.IGNORECASE,
)
_VALID_CODE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")


def extract_authorization_codes(message: str) -> tuple[str, tuple[str, ...]]:
    """Remove explicit authorization codes before persistence or LLM use."""
    codes: list[str] = []

    def redact(match: re.Match[str]) -> str:
        candidate = match.group("code")
        if _VALID_CODE.fullmatch(candidate):
            codes.append(candidate)
        return "codice: [fornito]"

    sanitized = _CODE_MARKER.sub(redact, message)
    return sanitized, tuple(dict.fromkeys(codes))
