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
- `POST /agent/events` to evaluate Home Assistant events safely
- `GET /events` to inspect the persistent event audit log
- `GET /events/{event_id}` to inspect one sanitized decision trace

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
HOUSE_BRAIN_API_KEY=replace-with-a-random-secret
AUTONOMOUS_EVENT_ALLOWLIST=
AUTONOMOUS_ACTION_ALLOWLIST=
AUTONOMOUS_ACTION_CONSTRAINTS={}
AUTONOMOUS_EXECUTION_ENABLED=false
```

The real `.env` file is ignored by Git and must never be committed.

Generate a strong House Brain API key and store it only in `.env`:

```bash
openssl rand -hex 32
```

## API authentication

`GET /health`, `/docs`, `/redoc`, and `/openapi.json` are public. Every
operational endpoint requires the House Brain key in the `X-API-Key` header.
Missing and incorrect keys both return `401` with the same response. The server
compares keys with a constant-time comparison. Swagger exposes an `Authorize`
button that sends the key only as this header.

For shell tests, load the value without printing it:

```bash
set -a
source .env
set +a

curl -sS http://localhost:8090/entities/sun.sun \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY"
```

Do not put the key in URLs, logs, Home Assistant automation names, or the
repository.

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


## Autonomous events

Home Assistant can send authenticated structured events to House Brain. Both
event types and requested actions are denied unless they exactly match the
server-side allowlists.

The values are comma-separated. Event entries are exact `event_type` values.
Action entries use `domain.service:entity_id`; wildcards are rejected.

For example, to allow one exit event to request only turning off the garage
fan:

```dotenv
AUTONOMOUS_EVENT_ALLOWLIST=person_left_home
AUTONOMOUS_ACTION_ALLOWLIST=switch.turn_off:switch.ventola
```

Autonomous `toggle` is always rejected because its final state depends on the
current state. Actions without data need no parameter constraint. Every data
field used by an autonomous action is denied unless it has an explicit
constraint in `AUTONOMOUS_ACTION_CONSTRAINTS`.

The value is a JSON object keyed by the exact action rule. Use `allowed` for
discrete values or `min` and `max` for numeric ranges:

```dotenv
AUTONOMOUS_ACTION_CONSTRAINTS={"cover.set_cover_position:cover.tapparella_cucina_due":{"position":{"allowed":[0,20,100]}},"climate.set_temperature:climate.sala":{"temperature":{"min":18,"max":26}},"light.turn_on:light.sala":{"brightness_pct":{"min":0,"max":70}}}
```

A constraint whose action is absent from `AUTONOMOUS_ACTION_ALLOWLIST` makes
the configuration invalid. A batch is validated completely before its first
Home Assistant call, so one forbidden value rejects the whole plan.

Restart House Brain after changing `.env`. An event not in the event allowlist
returns `403` before Ollama is called. An action outside the action allowlist
is returned to the model as a rejected tool result and is never sent to Home
Assistant.

The event endpoint supports:

- `observe`: read state and return a decision without actions
- `simulate`: allow action planning, but force every action to dry-run
- `execute`: execute only actions that pass every server-side policy

Execution has an independent kill switch and is disabled by default:

```dotenv
AUTONOMOUS_EXECUTION_ENABLED=false
```

Setting it to `true` does not bypass authentication or either allowlist. In
`execute` mode the server, not the model, forces an authorized action to
`dry_run: false`. Keep the switch disabled except while deliberately enabling
autonomous execution.

Simulate an exit check:

```bash
curl -sS http://localhost:8090/agent/events \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "person_left_home",
    "source": "home_assistant",
    "mode": "simulate",
    "instruction": "Controlla la ventola del garage e simula lo spegnimento se è accesa",
    "context": {
      "person": "Vincenzo"
    }
  }'
```

Inspect the audit log:

```bash
curl -sS http://localhost:8090/events \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" | python3 -m json.tool
```

Inspect every tool attempt for one event:

```bash
curl -sS http://localhost:8090/events/replace-with-event-id \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" | python3 -m json.tool
```

Each `tool_trace` item records its sequence, tool name, sanitized arguments,
completion or failure status, outcome, and bounded error text. Action targets
and validated action data are retained so rejected plans can be diagnosed.
Permanent-memory values and memory search text are redacted. API keys and Home
Assistant tokens are never tool arguments and are not stored in this trace.
Existing databases gain the audit column automatically at startup.


## Generic event planning

Home Assistant should send the trigger and useful context, not reproduce the
whole decision tree. House Brain can inspect a bounded snapshot across multiple
domains, recall stable preferences, calculate a plan, and submit several
actions together. Before the first real service call, the server validates the
entire plan against both the fixed action policy and the exact autonomous
action allowlist. If one action is denied, none are executed.

For example, a Home Assistant sun trigger can send an instruction such as:

```text
Valuta sole, ora, presenza e stato attuale della casa. Sistema i dispositivi
pertinenti secondo le preferenze memorizzate, senza azioni non necessarie.
```

The prompt is intentionally generic: covers, lights, switches, climate,
sensors, and cameras can be discovered and read as context. Real commands
remain limited to the explicitly supported action domains and exact entities.
Seeing an entity never grants permission to control it. Use `simulate` while
teaching House Brain house layout and preferences, then add only the reviewed
action targets to `AUTONOMOUS_ACTION_ALLOWLIST`.

## Home Assistant integration example

A deny-by-default garage fan rollout is available in
[`examples/home_assistant/`](examples/home_assistant/README.md). It includes a
reusable authenticated `rest_command`, secrets placeholders, and a simulation-only
automation package.
