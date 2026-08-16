import re

_CODE_MARKER = re.compile(
    r"(?P<label>\b[^\W\d_][\w-]*)\s*:\s*(?P<code>\S+)",
    flags=re.IGNORECASE,
)
_VALID_CODE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
_NATURAL_CODE = re.compile(
    r"(?P<prefix>^.*?\s)(?P<code>\d{4,64})(?P<suffix>\s*[.!]?\s*)$",
    flags=re.DOTALL,
)


def extract_authorization_codes(message: str) -> tuple[str, tuple[str, ...]]:
    """Remove explicit authorization codes before persistence or LLM use."""
    codes: list[str] = []

    def redact(match: re.Match[str]) -> str:
        raw_candidate = match.group("code")
        candidate = raw_candidate.rstrip(".,;:!?)]}")
        suffix = raw_candidate[len(candidate) :]
        if _VALID_CODE.fullmatch(candidate):
            codes.append(candidate)
        return f"{match.group('label')}: [authorization provided]{suffix}"

    sanitized = _CODE_MARKER.sub(redact, message)

    def redact_natural(match: re.Match[str]) -> str:
        codes.append(match.group("code"))
        return f"{match.group('prefix')}[authorization provided]{match.group('suffix')}"

    sanitized = _NATURAL_CODE.sub(redact_natural, sanitized)
    return sanitized, tuple(dict.fromkeys(codes))
