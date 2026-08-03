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
- `GET /entities/{entity_id}` for current Home Assistant state
- `GET /history` for recent Recorder history
- `GET /state-before` for the last state before a timestamp

All Home Assistant access is currently read-only.

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

Verify the current state:

```bash
curl http://localhost:8090/health
curl http://localhost:8090/entities/sun.sun
```

Read the last 60 minutes of history:

```bash
curl -sG http://localhost:8090/history \
  --data-urlencode "entity_id=cover.tapparella_cucina_uno" \
  --data-urlencode "minutes=60"
```

Read the last state strictly before a timezone-aware timestamp:

```bash
curl -sG http://localhost:8090/state-before \
  --data-urlencode "entity_id=cover.tapparella_cucina_uno" \
  --data-urlencode "before=2026-08-03T08:00:00+02:00" \
  --data-urlencode "search_hours=24"
```

Limits:

- `minutes`: from 1 to 10,080 (7 days)
- `search_hours`: from 1 to 720 (30 days)
- `before` must include a timezone, such as `+02:00` or `Z`

Run the checks:

```bash
uv run pytest
uv run ruff check .
```
