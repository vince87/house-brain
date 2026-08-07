# Gestione, sicurezza e sviluppo

## Operazioni

```bash
docker compose ps
curl -sS http://localhost:8090/health
docker compose logs --tail=100 house-brain
```

Dopo una modifica a `autonomy.yaml`:

```bash
docker compose config --quiet
docker compose up -d --force-recreate
```

Audit:

```bash
curl -sS http://localhost:8090/events \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" |
  python3 -m json.tool
```

La `tool_trace` è autorevole per strumenti, esiti e azioni simulate/eseguite.

## Diagnosi

| Sintomo | Controllo |
|---|---|
| 401 | API key |
| 403 | modalità, policy e kill switch |
| 404 su entità esistente | visibilità |
| 502 su HA | URL, token e rete |
| 502 su chat | Ollama, modello e timeout |
| avvio fallito | policy YAML e conflitti |

## Sicurezza

Le barriere sono indipendenti: autenticazione, esclusioni di visibilità, inclusione esplicita per il controllo, coerenza dominio-entità, codici per operazioni sensibili, piano atomico, kill switch e audit.

Il container usa utente non privilegiato, filesystem read-only, capability eliminate, `no-new-privileges`, tmpfs limitato e rotazione log.

Non stampare `docker compose config` senza `--quiet`: può mostrare i segreti risolti.

Esegui backup coerenti del volume contenente `/data/house_brain.db` e conserva
separatamente `.env` e `autonomy.yaml`. Se la policy contiene codici per
azioni sensibili, trattala come un file di segreti e limita i permessi sul
filesystem.

## Sviluppo

```bash
uv sync --extra dev
export AUTONOMY_POLICY_PATH="$PWD/autonomy.yaml"
export UV_LINK_MODE=copy
uv run pytest
uv run ruff check .
```

Lavora su branch dedicate, aggiungi test, apri PR in bozza e fai squash merge solo dopo il collaudo sul server.

Per domini ad alto rischio usa entità esatte, configura un codice, collauda a lungo in simulazione e valuta un secondo interlock fisico o Home Assistant.
