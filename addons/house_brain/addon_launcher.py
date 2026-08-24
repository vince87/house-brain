#!/usr/bin/env python3
"""Translate Supervisor add-on options into House Brain runtime settings."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

OPTIONS_PATH = Path("/data/options.json")
ALLOWED_OPTIONS = {
    "api_key": "HOUSE_BRAIN_API_KEY",
    "language": "HOUSE_BRAIN_LANGUAGE",
    "llm_provider": "LLM_PROVIDER",
    "ollama_url": "OLLAMA_URL",
    "ollama_model": "OLLAMA_MODEL",
    "openai_base_url": "OPENAI_BASE_URL",
    "openai_api_key": "OPENAI_API_KEY",
    "openai_model": "OPENAI_MODEL",
    "autonomous_execution_enabled": "AUTONOMOUS_EXECUTION_ENABLED",
}


def main() -> None:
    """Load bounded scalar options, add Supervisor credentials, then start."""
    try:
        options = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Cannot read add-on options: {exc}") from exc
    if not isinstance(options, dict):
        raise SystemExit("Add-on options must be an object")

    for option, environment in ALLOWED_OPTIONS.items():
        value = options.get(option)
        if value is None or value == "":
            continue
        if not isinstance(value, (str, bool, int, float)):
            raise SystemExit(f"Invalid scalar option: {option}")
        os.environ[environment] = (
            "true" if value is True else "false" if value is False else str(value)
        )

    api_key = os.environ.get("HOUSE_BRAIN_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set a non-empty api_key in the add-on configuration")
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if not supervisor_token:
        raise SystemExit("Supervisor did not provide a Home Assistant API token")

    os.environ["HOME_ASSISTANT_URL"] = "http://supervisor/core"
    os.environ["HOME_ASSISTANT_TOKEN"] = supervisor_token
    os.environ["PUID"] = "1000"
    os.environ["PGID"] = "1000"
    os.execv(
        "/usr/local/bin/house-brain-entrypoint",
        ["house-brain-entrypoint", *sys.argv[1:]],
    )


if __name__ == "__main__":
    main()
