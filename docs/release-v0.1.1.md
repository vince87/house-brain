# Checklist di rilascio v0.1.1

Questa checklist non autorizza il tag. Il tag `v0.1.1` e la release GitHub
richiedono il collaudo sul server e il consenso esplicito.

## Preparazione

- [ ] versione applicativa, pacchetto e lockfile impostati a `0.1.1`;
- [ ] Compose pubblico impostato su `ghcr.io/vince87/house-brain:0.1.1`;
- [ ] `docker compose config --quiet`, pytest e Ruff completati;
- [ ] workflow GitHub Actions completato sul commit approvato;
- [ ] nessun file reale di configurazione o database incluso nel repository.

## Collaudo reale

- [ ] health check restituisce la versione `0.1.1`;
- [ ] entità con `hidden_by` assenti da ricerca, configuratore, API e MCP;
- [ ] registro entità Home Assistant superiore a 1 MiB letto senza errore 1009;
- [ ] modalità `simulate` riporta soltanto azioni simulate;
- [ ] modalità `execute` riporta soltanto azioni realmente eseguite;
- [ ] riepilogo finale coerente con la `tool_trace`;
- [ ] memorie, cestino, chat e audit persistono dopo il riavvio;
- [ ] configuratore autonomia, gestione memorie e audit funzionanti;
- [ ] diagnostica autenticata non espone segreti;
- [ ] observe non descrive stati senza una lettura Home Assistant riuscita;
- [ ] MCP non espone strumenti di azione Home Assistant.

## Persistenza e sicurezza

- [ ] unico mount persistente `./config:/config:rw`;
- [ ] policy in `/config/autonomy.yaml`;
- [ ] database in `/config/house_brain.db`;
- [ ] backup policy in `/config/autonomy-backups`;
- [ ] `PRAGMA integrity_check` restituisce `ok`;
- [ ] vecchio named volume lasciato intatto e non eliminato;
- [ ] backup verificato prima di qualunque ripristino.

## Test host-side

```bash
set -a
source .env
set +a

export AUTONOMY_POLICY_PATH="$PWD/config/autonomy.yaml"
export MEMORY_DATABASE_PATH="/tmp/house-brain-tests.db"
export AUTONOMY_BACKUP_PATH="/tmp/house-brain-autonomy-backups"
export UV_LINK_MODE=copy
export AUTONOMOUS_EXECUTION_ENABLED=false

uv run pytest
uv run ruff check .
```

Prima di Docker Compose:

```bash
set -a
source .env
set +a
```

## Pubblicazione, solo dopo consenso esplicito

- [ ] squash merge autorizzato;
- [ ] tag `v0.1.1` creato sul commit approvato;
- [ ] workflow multiarch completato;
- [ ] immagini GHCR `0.1.1`, `0.1` e `latest` disponibili;
- [ ] release GitHub pubblicata con le note del changelog;
- [ ] installazione pulita verificata con l'immagine `0.1.1`.
