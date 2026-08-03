# House Brain

House Brain is an intelligent middleware between Large Language Models and
Home Assistant.

The LLM never talks directly to Home Assistant:

```text
LLM -> House Brain -> Home Assistant
```

## Current status

Bootstrap API with a health endpoint.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)

## Development

Install the project and development dependencies:

```bash
uv sync --extra dev
```

Start the API:

```bash
uv run uvicorn house_brain.main:app --host 0.0.0.0 --port 8090 --reload
```

Verify the service:

```bash
curl http://localhost:8090/health
```

Expected response:

```json
{"status":"ok","service":"house-brain","version":"0.1.0"}
```

Run the checks:

```bash
uv run pytest
uv run ruff check .
```
