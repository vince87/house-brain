# Collaudo del ciclo di vita dell'installazione

Questa procedura verifica la PR senza eliminare dati, volumi o backup. Il
ripristino viene applicato soltanto nell'ultima fase e richiede conferma
esplicita nella GUI.

## 1. Preparare la branch

```bash
cd /docker/appdata/house-brain/house-brain

git fetch origin
git switch feature/installation-lifecycle-management
git pull --ff-only origin feature/installation-lifecycle-management

set -a
source .env
set +a

docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml ps
curl -fsS http://localhost:8090/health | python3 -m json.tool
```

## 2. Verificare stato e autenticazione

```bash
set -a
source .env
set +a

curl -sS -w '\nHTTP %{http_code}\n' \
  http://localhost:8090/admin/installation

curl -fsS \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  http://localhost:8090/admin/installation |
  python3 -m json.tool
```

Il primo comando deve restituire HTTP 401. Il secondo deve mostrare
`status: ready`, policy e database `ok`, root persistente `/config` e
nessun token o codice.

## 3. Scaricare e controllare il backup

```bash
set -a
source .env
set +a

backup="/tmp/house-brain-config-validation.zip"

curl -fsS -X POST \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  http://localhost:8090/admin/installation/backups \
  -o "${backup}"

unzip -t "${backup}"
unzip -p "${backup}" manifest.json | python3 -m json.tool
```

Il manifest deve elencare `config/house_brain.db`,
`config/autonomy.yaml` e i backup policy, ma non i sidecar SQLite, i backup
di sistema, `.env` o credenziali runtime.

## 4. Ispezionare senza applicare

```bash
set -a
source .env
set +a

curl -fsS -X POST \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  -H "Content-Type: application/zip" \
  --data-binary @/tmp/house-brain-config-validation.zip \
  http://localhost:8090/admin/installation/restores/inspect |
  tee /tmp/house-brain-restore-inspection.json |
  python3 -m json.tool
```

La risposta deve essere `validated` e deve soltanto creare una fase
temporanea. Nessun file in `config/` deve cambiare.

## 5. Collaudare dalla GUI

Apri `http://localhost:8090/installation`, inserisci la chiave API e verifica:

1. stato di prima configurazione, migrazioni e aggiornamenti;
2. download del backup;
3. selezione e ispezione dell'archivio;
4. elenco completo dei file da ripristinare;
5. richiesta della parola esatta `RESTORE`.

Nel pannello nativo Home Assistant, visibile soltanto agli amministratori,
verifica anche la nuova scheda **Installazione** e lo stesso stato privo di
segreti.

## 6. Ripristino controllato opzionale

Esegui questa fase soltanto dopo avere conservato fuori dal server il backup
scaricato. Applicare il backup appena creato non dovrebbe cambiare i dati, ma
deve creare uno snapshot `config.before-restore-*.zip`.

Usa la GUI, inserisci `RESTORE` e poi ricarica l'ambiente prima dei controlli:

```bash
set -a
source .env
set +a

docker compose -f docker-compose.dev.yml restart house-brain
docker compose -f docker-compose.dev.yml ps
curl -fsS http://localhost:8090/health | python3 -m json.tool
```

Verifica infine Memorie, Chat, Audit, Autonomia, Piani e Diagnostica. Nell'audit
devono comparire eventi `installation.backup`,
`installation.restore_inspect` e, se applicato, `installation.restore`.

## 7. Controlli host-side

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

Prima di tornare a Docker Compose ricarica nuovamente `.env`, così i percorsi
del container tornano a `/config/...`.

Non eseguire `docker compose config` senza `--quiet`.
