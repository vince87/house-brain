# Gestione, sicurezza e sviluppo

## Operazioni

```bash
docker compose ps
curl -sS http://localhost:8090/health
docker compose logs --tail=100 house-brain
```

Dopo una modifica a `config/autonomy.yaml`:

```bash
docker compose config --quiet
docker compose up -d --force-recreate
docker compose ps
```

La modifica manuale richiede la ricreazione. Il configuratore web `/autonomy`
invece valida, salva e ricarica la policy nel processo senza riavvio.

Per interrogare l'audit:

```bash
curl -sS http://localhost:8090/events \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" |
  python3 -m json.tool
```

La `tool_trace` è autorevole per strumenti, argomenti, esiti e azioni
simulate o eseguite. Se la risposta del modello la contraddice, considera vera
la traccia.

## Diagnosi

| Sintomo | Controllo |
|---|---|
| 401 | `X-API-Key` mancante o errata |
| 403 | entità non inclusa, codice, modalità o kill switch |
| 404 su entità esistente in HA | entità o pattern presente in `exclude` |
| azione su dispositivo diverso | verifica l'entity ID nella richiesta e nella `tool_trace` |
| modifica alla policy ignorata | ricrea il container |
| codice sempre rifiutato | verifica entità, codice configurato e canale usato |
| 502 su HA | URL, token e rete |
| 502 su chat | Ollama, modello e timeout |
| avvio fallito | versione e struttura della policy YAML |
| agente fermato per iterazioni | controlla sequenza e errori degli strumenti |

Un'entità trovata dal catalogo non è automaticamente controllabile: deve
comparire in `entities.include`. Se la richiesta contiene un entity ID
esplicito, House Brain vieta al modello di sostituirlo con un'altra entità.

Per `POST /actions` il codice va nell'header `X-Authorization-Code`. In chat
e negli eventi va scritto nel testo della richiesta. Non inserirlo nel campo
`data` dell'azione.

## Sicurezza

Le barriere sono indipendenti: autenticazione, esclusioni di visibilità,
inclusione esplicita per il controllo, coerenza dominio-entità, eventuale codice
per dispositivo, piano atomico, kill switch e audit.

Il container usa utente non privilegiato, filesystem read-only, capability
eliminate, `no-new-privileges`, tmpfs limitato e rotazione log.

Non stampare `docker compose config` senza `--quiet`: può mostrare i segreti
risolti.

Ferma House Brain prima di copiare direttamente `config/house_brain.db`, oppure
usa l'API backup di SQLite. Conserva insieme la directory `config/` e `.env` in
un backup protetto. Se la policy contiene codici, trattala come un file di
segreti e limita i permessi sul filesystem.

Per dispositivi ad alto rischio usa entity ID esatti, configura un codice,
collauda a lungo in simulazione e valuta un secondo interlock fisico o Home
Assistant. Il dominio non misura il rischio reale: anche uno `switch` può
azionare un accesso.

## Aggiornamento del server

```bash
set -a
source .env
set +a
git switch main
git pull --ff-only
docker compose up -d --build
docker compose ps
```

Per usare subito le variabili nel terminale:

```bash
set -a
source .env
set +a
```

## Sviluppo

```bash
uv sync --extra dev
export AUTONOMY_POLICY_PATH="$PWD/config/autonomy.yaml"
export UV_LINK_MODE=copy
uv run pytest
uv run ruff check .
```

Lavora su branch dedicate, aggiungi test, apri PR in bozza e fai squash merge
solo dopo il collaudo sul server.
