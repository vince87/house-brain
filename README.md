# House Brain

House Brain is an intelligent middleware between Large Language Models and
Home Assistant.

The LLM never talks directly to Home Assistant:

```text
LLM -> House Brain -> Home Assistant
```

## Current status

House Brain exposes:

- `GET /health`
- `GET /entities/{entity_id}` for generic, read-only Home Assistant state access

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- a Home Assistant long-lived access token

## Configuration

Create the local environment file:

```bash
cp .env.example .env
```

Set your Home Assistant URL and token in `.env`:

```dotenv
HOME_ASSISTANT_URL=http://192.168.10.250:8123
HOME_ASSISTANT_TOKEN=replace-with-your-token
HOME_ASSISTANT_TIMEOUT=10
```

The real `.env` file is ignored by Git and must never be committed.

## Development

Install the project and development dependencies:

```bash
uv sync --extra dev
```

Start the API:

```bash
uv run uvicorn house_brain.main:app \
  --host 0.0.0.0 \
  --port 8090 \
  --reload \
  --env-file .env
```

Verify House Brain:

```bash
curl http://localhost:8090/health
curl http://localhost:8090/entities/sun.sun
```

Run the checks:

```bash
uv run pytest
uv run ruff check .
```
