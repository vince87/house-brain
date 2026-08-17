# Installazione e configurazione

## Requisiti

Docker Compose, Home Assistant con token a lunga durata, Ollama raggiungibile dal container e Python 3.12 con `uv` per lo sviluppo.

## Prima installazione

```bash
cp .env.example .env
mkdir -p config
cp config/autonomy.yaml.example config/autonomy.yaml
sudo chown "$(id -u):10001" config config/autonomy.yaml
chmod 770 config
chmod 660 config/autonomy.yaml
openssl rand -hex 32
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl -sS http://localhost:8090/health
```

Non commettere `.env`, `config/autonomy.yaml`, token o chiavi reali.

Docker Compose usa automaticamente `.env` per sostituire i valori dichiarati
nella sezione `environment`. Non viene usato `env_file`: il contratto delle
variabili disponibili nel container rimane interamente visibile nel Compose.
La directory `./config` viene montata in `/config`; il database e i backup
persistenti rimangono separati nel volume `/data`.

## Variabili

| Variabile | Predefinito | Uso |
|---|---|---|
| `HOME_ASSISTANT_URL` | obbligatoria | API Home Assistant |
| `HOME_ASSISTANT_TOKEN` | obbligatoria | token HA |
| `HOUSE_BRAIN_API_KEY` | obbligatoria | autenticazione House Brain |
| `HOUSE_BRAIN_LANGUAGE` | `it` | lingua delle risposte dell'agente |
| `HOME_ASSISTANT_SERVICE_CACHE_TTL` | `300` | secondi di cache del catalogo servizi HA |
| `AUTONOMY_POLICY_PATH` | `/config/autonomy.yaml` | policy YAML |
| `AUTONOMY_BACKUP_PATH` | `/data/autonomy-backups` | backup protetti della policy |
| `AUTONOMOUS_EXECUTION_ENABLED` | `false` | kill switch reale |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | API Ollama |
| `OLLAMA_MODEL` | `gemma4:12b` | modello |
| `OLLAMA_TIMEOUT` | `120` | timeout modello |
| `SEARXNG_URL` | vuota | abilita ricerca web in chat |
| `WEB_SEARCH_TIMEOUT` | `10` | timeout ricerca, max 30 |
| `WEB_SEARCH_MAX_RESULTS` | `10` | risultati, max 10 |
| `MEMORY_DATABASE_PATH` | `/data/house_brain.db` | SQLite |

`HOUSE_BRAIN_LANGUAGE` accetta `ar`, `de`, `en`, `es`, `fr`, `it`, `ja`, `ko`,
`pt` e `zh`, anche con una variante regionale come `pt-BR`. Prompt, istruzioni
e descrizioni dei tool restano in inglese; il modello deve tradurre le risposte
nella lingua configurata. I messaggi di sicurezza prodotti senza Ollama usano
lo stesso pacchetto lingua.

Le vecchie variabili `AUTONOMOUS_*_ALLOWLIST`, `AUTONOMOUS_ACTION_CONSTRAINTS` e `AUTONOMOUS_EXECUTE_MAX_ACTIONS` sono rifiutate all'avvio.

## Aggiornamento

```bash
git switch main
git pull --ff-only
docker compose up -d --build
docker compose ps
```

### Migrazione dal precedente mount singolo

Prima di avviare il nuovo Compose, conserva la policy esistente spostandola
nella directory di configurazione. Il volume Docker contenente il database non
viene modificato:

```bash
mkdir -p config
cp -p autonomy.yaml config/autonomy.yaml
sudo chown "$(id -u):10001" config config/autonomy.yaml
chmod 770 config
chmod 660 config/autonomy.yaml
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Non cancellare il vecchio `autonomy.yaml` finché il container non risulta
healthy e `/autonomy` mostra la policy corretta.

## Test host-side

```bash
set -a
source .env
set +a
export AUTONOMY_POLICY_PATH="$PWD/config/autonomy.yaml"
export UV_LINK_MODE=copy
uv run pytest
uv run ruff check .
```
