# Installazione e configurazione

## Requisiti

Docker Compose, Home Assistant con token a lunga durata, Ollama raggiungibile dal container e Python 3.12 con `uv` per lo sviluppo.

## Prima installazione

```bash
cp .env.example .env
cp autonomy.yaml.example autonomy.yaml
openssl rand -hex 32
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl -sS http://localhost:8090/health
```

Non commettere `.env`, `autonomy.yaml`, token o chiavi reali.

## Variabili

| Variabile | Predefinito | Uso |
|---|---|---|
| `HOME_ASSISTANT_URL` | obbligatoria | API Home Assistant |
| `HOME_ASSISTANT_TOKEN` | obbligatoria | token HA |
| `HOUSE_BRAIN_API_KEY` | obbligatoria | autenticazione House Brain |
| `AUTONOMY_POLICY_PATH` | `/app/autonomy.yaml` | policy YAML |
| `AUTONOMOUS_EXECUTION_ENABLED` | `false` | kill switch reale |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | API Ollama |
| `OLLAMA_MODEL` | `gemma4:12b` | modello |
| `OLLAMA_TIMEOUT` | `120` | timeout modello |
| `SEARXNG_URL` | vuota | abilita ricerca web in chat |
| `WEB_SEARCH_TIMEOUT` | `10` | timeout ricerca, max 30 |
| `WEB_SEARCH_MAX_RESULTS` | `10` | risultati, max 10 |
| `MEMORY_DATABASE_PATH` | `/data/house_brain.db` | SQLite |

Le vecchie variabili `AUTONOMOUS_*_ALLOWLIST`, `AUTONOMOUS_ACTION_CONSTRAINTS` e `AUTONOMOUS_EXECUTE_MAX_ACTIONS` sono rifiutate all'avvio.

## Aggiornamento

```bash
git switch main
git pull --ff-only
docker compose up -d --build
docker compose ps
```

## Test host-side

```bash
export AUTONOMY_POLICY_PATH="$PWD/autonomy.yaml"
export UV_LINK_MODE=copy
uv run pytest
uv run ruff check .
```
