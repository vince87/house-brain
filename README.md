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
- `POST /actions` for policy-controlled Home Assistant service calls
- `POST /agent/chat` for natural-language commands with persistent sessions
- `GET /conversations/{session_id}` to inspect recent conversation context
- `DELETE /conversations/{session_id}` to reset one conversation

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

## Docker deployment

Validate the Compose file without printing resolved environment secrets:

```bash
docker compose config --quiet
```

Never paste the output of `docker compose config`: without `--quiet`, Docker
prints values loaded from `.env`, including the Home Assistant token.

Build and start the production service:

```bash
docker compose up -d --build
```

Check container and application health:

```bash
docker compose ps
curl http://localhost:8090/health
```

Follow the application logs:

```bash
docker compose logs -f --tail=100 house-brain
```

Update after pulling a new version:

```bash
git pull
docker compose up -d --build
```

The container runs as an unprivileged user, drops Linux capabilities, uses a
read-only filesystem and rotates Docker logs at 10 MB with three retained
files.

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

## Controlled actions

Every action defaults to `dry_run: true`. This validates and logs the request
without calling Home Assistant.

Simulate lowering a cover:

```bash
curl -s http://localhost:8090/actions \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "cover",
    "service": "set_cover_position",
    "entity_id": "cover.tapparella_cucina_uno",
    "data": {"position": 0}
  }'
```

Execute a harmless stop command:

```bash
curl -s http://localhost:8090/actions \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "cover",
    "service": "stop_cover",
    "entity_id": "cover.tapparella_cucina_uno",
    "dry_run": false
  }'
```

Allowed domains:

- `light`
- `switch`
- `cover`
- `climate`

Blocked until a separate human-confirmation mechanism exists:

- `alarm_control_panel`
- `automation`
- `button`
- `lock`
- `scene`
- `script`

Run the checks:

```bash
uv run pytest
uv run ruff check .
```


## Conversation sessions

Agent requests use the `default` session unless a `session_id` is provided.
Each request loads at most the latest 12 messages, keeping Ollama context bounded.
Conversation history is separate from long-term memories.

Continue one conversation:

```bash
curl -sS http://localhost:8090/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "vincenzo",
    "message": "Qual è lo stato della ventola del garage?"
  }'

curl -sS http://localhost:8090/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "vincenzo",
    "message": "E quella della cucina?"
  }'
```

Inspect or reset that session:

```bash
curl -sS http://localhost:8090/conversations/vincenzo
curl -sS -X DELETE http://localhost:8090/conversations/vincenzo
```
