# Checklist di rilascio v0.1.5

La release consolida integrazione nativa Home Assistant, contesto relazionale,
diagnostica dei provider e piani d'azione con approvazione esplicita.

## Contenuto

- [x] versione applicativa, lockfile, manifest e Compose impostati a `0.1.5`;
- [x] changelog e roadmap aggiornati;
- [x] custom integration installabile dalla struttura versionata della release;
- [x] action basate su Node.js 24;
- [x] build Docker multiarch senza pubblicazione nelle pull request;
- [x] un solo bind mount persistente `./config:/config:rw`;
- [x] nessuna modifica automatica a policy, database, backup o vecchi volumi.

## Verifiche automatiche

- [x] suite Python 3.12;
- [x] Ruff;
- [x] sintassi JavaScript del pannello Home Assistant;
- [x] hassfest;
- [x] coerenza della versione fra package, lockfile, Compose, health e manifest;
- [x] GitHub Actions sul commit finale della PR.

## Collaudi reali completati

- [x] contesto Home Assistant limitato alle entità visibili o controllabili;
- [x] entità non autorizzate e nascoste non accessibili;
- [x] nomi Autonomy autorevoli e metadati di dispositivo verificati;
- [x] piani creati, rifiutati, approvati e non riutilizzabili;
- [x] piani scaduti rifiutati con HTTP 409;
- [x] cambio di stato prima dell'approvazione rilevato e piano invalidato;
- [x] codici policy non persistiti nel piano;
- [x] Assist e AI Task nelle modalità configurate;
- [x] recupero delle risposte Ollama vuote durante sequenze con strumenti;
- [x] provider OpenAI-compatible locale con URL personalizzato;
- [x] persistenza di memorie, conversazioni e audit durante i collaudi.

## Collaudo host-side

Prima dei test caricare sempre `.env` e usare percorsi temporanei host-side:

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

Prima di tornare a Docker Compose, ricaricare `.env` affinché i percorsi del
container tornino ai valori `/config/...`:

```bash
set -a
source .env
set +a

docker compose -f docker-compose.dev.yml config --quiet
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml ps
curl -fsS http://localhost:8090/health | python3 -m json.tool
```

Per i comandi `docker compose exec` usare sempre `-T`.

## Dopo il tag

- [ ] workflow del tag `v0.1.5` completato;
- [ ] immagine `ghcr.io/vince87/house-brain:0.1.5` disponibile per amd64 e arm64;
- [ ] tag `latest` aggiornato dalla stessa build;
- [ ] health check dell'immagine pubblicata restituisce `0.1.5`;
- [ ] installazione o aggiornamento della custom integration dalla release
  verificato;
- [ ] database SQLite integro e policy, memorie, conversazioni e audit presenti
  dopo l'aggiornamento.

Il tag e la GitHub Release richiedono consenso esplicito. I vecchi volumi Docker
e i backup storici non devono essere eliminati automaticamente.
