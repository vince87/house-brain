# Checklist di rilascio v0.1.0

Questa checklist non autorizza il tag. Il tag `v0.1.0` e la release GitHub
richiedono collaudo sul server e consenso esplicito.

## Preparazione

- [ ] nessun percorso runtime `/data` o riferimento a `house_brain_data`;
- [ ] unico mount persistente `./config:/config:rw`;
- [ ] `.env`, policy, database, sidecar e backup ignorati da Git;
- [ ] `docker compose config --quiet`, pytest e Ruff completati.

## Collaudo reale

- [ ] health check versione `0.1.0`;
- [ ] observe, simulate ed execute verificati;
- [ ] kill switch, codici policy e codici Home Assistant verificati;
- [ ] entità escluse e target ambigui rifiutati correttamente;
- [ ] tool trace autorevole rispetto alla risposta del modello;
- [ ] configuratore web e MCP verificati.

## Persistenza

- [ ] House Brain fermato prima della copia dell'intera directory `config/`;
- [ ] archivio e checksum conservati fuori dal repository;
- [ ] `PRAGMA integrity_check` restituisce `ok`;
- [ ] ripristino conserva memorie, cestino, chat, audit e policy;
- [ ] health check, riavvio e rebuild riescono dopo il ripristino;
- [ ] directory precedente e vecchio volume Docker restano intatti.

## Test host-side

```bash
set -a
source .env
set +a

export AUTONOMY_POLICY_PATH="$PWD/config/autonomy.yaml"
export MEMORY_DATABASE_PATH="/tmp/house-brain-tests.db"
export AUTONOMY_BACKUP_PATH="/tmp/house-brain-autonomy-backups"
export UV_LINK_MODE=copy

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
- [ ] changelog finalizzato con data;
- [ ] tag annotato `v0.1.0` creato sul commit approvato;
- [ ] release GitHub verificata senza eliminare dati, branch o volumi.
