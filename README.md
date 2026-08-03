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
- `GET /chat` for the browser chat client
- `POST /agent/chat` for natural-language commands with persistent sessions
- optional bounded SearXNG search for authenticated chats
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
AUTONOMY_POLICY_PATH=/app/autonomy.yaml
AUTONOMOUS_EXECUTION_ENABLED=false
SEARXNG_URL=http://host.docker.internal:8081
WEB_SEARCH_TIMEOUT=10
WEB_SEARCH_MAX_RESULTS=10
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

## Web chat

Open the browser client on the House Brain server:

```text
http://server-iot:8090/chat
```

The page itself is a public static shell and contains no house data or embedded
credentials. Enter `HOUSE_BRAIN_API_KEY` in its login form. The client verifies
it through the protected `GET /auth/check` endpoint and sends it in the
`X-API-Key` header for chat, history, and conversation deletion requests.

The key is kept only in browser `sessionStorage`: it is never placed in the
URL, persisted by House Brain, or stored in `localStorage`, and disappears
when the tab is closed. Use **Nuova chat** for a separate persistent
`session_id`, **Cancella** to permanently delete the current conversation, and
**Esci** to remove the key from the current browser session.

The address must be the IP or hostname of the machine running House Brain.
Home Assistant's IP works only if it is the same machine or a reverse proxy
forwards port 8090 to House Brain.

## Docker deployment

Validate the Compose file without printing resolved environment secrets:

```bash
docker compose config --quiet
```

Never paste the output of `docker compose config`: without `--quiet`, Docker
prints values loaded from `.env`, including the Home Assistant token.

Create the local autonomy policy before the first start:

```bash
cp autonomy.yaml.example autonomy.yaml
```

The local `autonomy.yaml` is ignored by Git and mounted read-only in the
container. Build and start the production service:

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
git pull --ff-only
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

For host-side commands, override the container-only policy path without
changing `.env`:

```bash
export AUTONOMY_POLICY_PATH="$PWD/autonomy.yaml"
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
curl http://localhost:8090/entities/sun.sun \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY"
```

Read the last 60 minutes of history:

```bash
curl -sG http://localhost:8090/history \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" \
  --data-urlencode "entity_id=cover.tapparella_cucina_uno" \
  --data-urlencode "minutes=60"
```

Read the last state strictly before a timezone-aware timestamp:

```bash
curl -sG http://localhost:8090/state-before \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" \
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
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" \
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
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" \
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
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "vincenzo",
    "message": "Qual è lo stato della ventola del garage?"
  }'

curl -sS http://localhost:8090/agent/chat \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "vincenzo",
    "message": "E quella della cucina?"
  }'
```

Inspect or reset that session:

```bash
curl -sS http://localhost:8090/conversations/vincenzo \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY"

curl -sS -X DELETE http://localhost:8090/conversations/vincenzo \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY"
```


## Web search

House Brain can expose a bounded `search_web` tool to authenticated chat
sessions. Configure the SearXNG address reachable from the container:

```dotenv
SEARXNG_URL=http://host.docker.internal:8081
WEB_SEARCH_TIMEOUT=10
WEB_SEARCH_MAX_RESULTS=10
```

Restart the container after changing `.env`. If `SEARXNG_URL` is absent or
empty, the tool is not advertised to Ollama. Search is deliberately unavailable
to `/agent/events`, including `observe`, `simulate`, and `execute`.

The tool calls only SearXNG's fixed `/search?format=json` endpoint. The model
cannot choose another server or fetch arbitrary result pages. Queries are
limited to 300 characters and each search returns at most 10 compact results.
Fresh-data verification uses two searches, providing up to 20 results without
filling the model context with 30 full excerpts. Returned fields are limited to a bounded title, HTTP(S) URL, excerpt,
engine list, and publication date. Duplicate or non-HTTP(S) URLs are
discarded. The prompt includes the current server date. Time-sensitive claims
must compare at least two searches, consider result dates, prefer official or primary
sources, and explicitly admit when the available results are inconclusive.
Final answers use plain text and identify relevant sources with titles and full
URLs; the web chat renders those URLs as safe external links.

Test SearXNG from the Docker host:

```bash
curl -sS "http://localhost:8081/search?q=Home+Assistant&format=json" |
  python3 -m json.tool | head -n 30
```

Then ask the web chat for current information and confirm that `search_web`
appears in the displayed tool list.

## Autonomous events

Home Assistant sends authenticated structured events to `POST /agent/events`.
All permissions for an event live together in the local `autonomy.yaml` file.
The file is validated completely at application startup; an unreadable or
inconsistent policy prevents House Brain from starting.

Copy the versioned example once:

```bash
cp autonomy.yaml.example autonomy.yaml
```

The top-level policy format is:

```yaml
version: 1

events:
  sun_context_changed:
    modes:
      - observe
      - simulate
    max_actions: 1
    actions:
      cover.set_cover_position:
        entities:
          - cover.tapparella_cucina_due
        parameters:
          position:
            allowed:
              - 0
              - 20
              - 100
```

Each exact event type declares:

- `modes`: any combination of `observe`, `simulate`, and `execute`
- `max_actions`: cumulative real-action budget from 1 to 20
- `actions`: exact services, entities, and optional parameter constraints

An event absent from the file is denied. A mode absent from that event is also
denied. Seeing an entity never grants permission to control it. Wildcards,
cross-domain service/entity pairs, unknown fields, invalid parameter
constraints, and action budgets outside the accepted range are rejected while
loading the file.

Actions without data need no parameter block. Every data field sent by an
autonomous action must have a matching constraint. Use `allowed` for discrete
values or `min` and `max` for numeric ranges:

```yaml
actions:
  climate.set_temperature:
    entities:
      - climate.sala
    parameters:
      temperature:
        min: 18
        max: 26
```

The endpoint modes remain:

- `observe`: read state and return a decision without actions
- `simulate`: plan actions but force every action to dry-run
- `execute`: execute only actions permitted by that event policy

Real execution also requires the independent global kill switch:

```dotenv
AUTONOMY_POLICY_PATH=/app/autonomy.yaml
AUTONOMOUS_EXECUTION_ENABLED=false
```

The kill switch is deliberately outside YAML so real execution can be disabled
without editing permissions. When it is `false`, every `execute` request is
rejected even if the event declares that mode. The model cannot override the
switch, event mode, actions, entities, constraints, or budget.

The old `AUTONOMOUS_EVENT_ALLOWLIST`,
`AUTONOMOUS_EXECUTE_EVENT_ALLOWLIST`,
`AUTONOMOUS_ACTION_ALLOWLIST`, `AUTONOMOUS_ACTION_CONSTRAINTS`, and
`AUTONOMOUS_EXECUTE_MAX_ACTIONS` variables are deprecated and prevent startup.
Remove them from `.env` after migrating their permissions into YAML.

Inspect the audit log:

```bash
curl -sS http://localhost:8090/events \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" | python3 -m json.tool
```

## Generic event planning

Home Assistant should send the trigger and useful context, not reproduce the
whole decision tree. House Brain can inspect a bounded snapshot across multiple
domains, recall stable preferences, calculate a plan, and submit several
actions together. Before the first real service call, the server validates the
entire plan against both the fixed action policy and the exact policy block
for that event. If one action is denied, none are executed.

For example, a Home Assistant sun trigger can send an instruction such as:

```text
Valuta sole, ora, presenza e stato attuale della casa. Sistema i dispositivi
pertinenti secondo le preferenze memorizzate, senza azioni non necessarie.
```

The prompt is intentionally generic: covers, lights, switches, climate,
sensors, and cameras can be discovered and read as context. Real commands
remain limited to the explicitly supported action domains and exact entities.
Seeing an entity never grants permission to control it. Use `simulate` while
teaching House Brain house layout and preferences, then add only reviewed
services and entities to that event's `actions` block in `autonomy.yaml`.

## First execute canary

The example policy contains a reversible light canary. Its complete permission
block is local to `canary_light_control`:

```yaml
canary_light_control:
  modes:
    - simulate
    - execute
  max_actions: 1
  actions:
    light.turn_on:
      entities:
        - light.sala_uno
    light.turn_off:
      entities:
        - light.sala_uno
```

Keep `AUTONOMOUS_EXECUTION_ENABLED=false` during simulation. Enable it only
for a deliberate real test, use a second event to restore the original state,
then disable it again.

## Home Assistant integration example

A deny-by-default garage fan rollout is available in
[`examples/home_assistant/`](examples/home_assistant/README.md). It includes a
reusable authenticated `rest_command`, secrets placeholders, and a simulation-only
automation package.
