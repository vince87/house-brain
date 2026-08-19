# Installazione e configurazione

## Installazione con immagine precompilata

Richiede soltanto Docker Compose, Home Assistant e Ollama raggiungibile dal
container. Non richiede Git, Python, `uv` o un file `.env`.

Scarica il pacchetto di distribuzione della release, modifica direttamente
`docker-compose.yml` e sostituisci almeno:

- `HOME_ASSISTANT_URL`;
- `HOME_ASSISTANT_TOKEN`;
- `HOUSE_BRAIN_API_KEY`;
- `OLLAMA_URL` e `OLLAMA_MODEL`.
- `PUID` e `PGID` con gli identificatori dell'utente proprietario di `config/`.

Il Compose contiene dati sensibili: limita i permessi e non pubblicarlo.

```bash
mkdir -p config
cp config/autonomy.yaml.example config/autonomy.yaml
sudo chown -R "$(id -u):$(id -g)" config
chmod 600 docker-compose.yml
chmod 770 config
chmod 660 config/autonomy.yaml

docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
curl -sS http://localhost:8090/health
```

Per aggiornare, modifica soltanto il tag immagine nel Compose dopo aver letto il
changelog, quindi usa `docker compose pull` e `docker compose up -d`. Non
usare tag mobili in ambienti domestici: il file distribuito resta fissato alla
versione collaudata.

### Proprietà dei file persistenti

Il container usa `PUID` e `PGID` dichiarati nel Compose (predefiniti a
`1000:1000`). All'avvio assegna esclusivamente il contenuto di `/config` a
questi identificatori e avvia immediatamente House Brain senza privilegi di
root. Database SQLite, relativi sidecar, policy e backup rimangono quindi di
proprietà dell'utente scelto sul server. Non sono necessari permessi `777`.

Trova gli identificatori corretti con `id -u` e `id -g`, quindi riportali nel
Compose. Se la directory è su NFS o su un filesystem che impedisce `chown`,
prepara la proprietà sul server prima dell'avvio. Non usare `PUID: 0` o
`PGID: 0`: il container li rifiuta intenzionalmente.

## Sviluppo dal repository

Copia `.env.example` in `.env` e usa il Compose di sviluppo:

```bash
set -a
source .env
set +a

docker compose -f docker-compose.dev.yml config --quiet
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml ps
```

`.env.example` è mantenuto esclusivamente per sviluppo e migrazione.
`docker-compose.yml` non usa interpolazione, `env_file` o variabili esterne.

## Variabili

| Variabile | Predefinito | Uso |
|---|---|---|
| `PUID` | `1000` | UID proprietario dei file persistenti |
| `PGID` | `1000` | GID proprietario dei file persistenti |
| `HOME_ASSISTANT_URL` | obbligatoria | API Home Assistant |
| `HOME_ASSISTANT_TOKEN` | obbligatoria | token HA |
| `HOUSE_BRAIN_API_KEY` | obbligatoria | autenticazione House Brain |
| `HOUSE_BRAIN_LANGUAGE` | `it` | lingua delle risposte dell'agente |
| `HOME_ASSISTANT_SERVICE_CACHE_TTL` | `300` | secondi di cache del catalogo servizi HA |
| `AUTONOMY_POLICY_PATH` | `/config/autonomy.yaml` | policy YAML |
| `AUTONOMY_BACKUP_PATH` | `/config/autonomy-backups` | backup protetti della policy |
| `AUTONOMOUS_EXECUTION_ENABLED` | `false` | kill switch reale |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | API Ollama |
| `OLLAMA_MODEL` | `gemma4:12b` | modello |
| `OLLAMA_TIMEOUT` | `120` | timeout modello |
| `SEARXNG_URL` | vuota | abilita ricerca web in chat |
| `WEB_SEARCH_TIMEOUT` | `10` | timeout ricerca, max 30 |
| `WEB_SEARCH_MAX_RESULTS` | `10` | risultati, max 10 |
| `MEMORY_DATABASE_PATH` | `/config/house_brain.db` | SQLite |

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


### Migrazione dal volume Docker `/data`

Questa procedura va eseguita **prima** di aggiornare il Compose che rimuove il
volume `/data`. Il container viene fermato in modo pulito prima della copia,
così SQLite chiude e consolida anche le eventuali scritture presenti nel WAL.
Vengono migrati sia il database sia i backup della policy già esistenti.

```bash
set -a
source .env
set +a

test ! -e config/house_brain.db

docker compose stop house-brain
docker compose cp house-brain:/data/. ./config/

sudo chown -R "$(id -u):10001" config
chmod -R u+rwX,g+rwX,o-rwx config
ls -lh config/house_brain.db
```

Aggiorna quindi il repository e imposta in `.env`:

```dotenv
AUTONOMY_POLICY_PATH=/config/autonomy.yaml
AUTONOMY_BACKUP_PATH=/config/autonomy-backups
MEMORY_DATABASE_PATH=/config/house_brain.db
```

Ricarica `.env` e avvia il nuovo Compose:

```bash
set -a
source .env
set +a

docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 house-brain
```

Verifica memorie, conversazioni e audit prima di rimuovere manualmente il
vecchio volume. House Brain non lo elimina: rimane disponibile per il rollback.
Non usare `docker compose down -v` durante la migrazione.

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
