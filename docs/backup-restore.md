# Backup e ripristino guidato

Questa procedura protegge l'intera configurazione persistente di House Brain.
La directory `config/` contiene policy, database SQLite, conversazioni, memorie,
audit e backup della policy. Il vecchio named volume non viene usato e non deve
essere eliminato.

> Il ripristino non è esposto come pulsante web: sostituire il database mentre
> House Brain è attivo può danneggiarlo. La procedura arresta il servizio e
> conserva sempre la configurazione precedente.

## 1. Creare il backup

Esegui i comandi dalla directory del progetto:

```bash
set -a
source .env
set +a

backup_root="/docker/appdata/house-brain-backups"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${backup_root}/house-brain-config-${stamp}.tar.gz"

mkdir -p "${backup_root}"
chmod 700 "${backup_root}"
docker compose stop house-brain
tar -C "$PWD" -czf "${backup_file}" config
sha256sum "${backup_file}" > "${backup_file}.sha256"
```

Con il servizio ancora fermo, verifica il database:

```bash
python3 - <<'PY'
import sqlite3
with sqlite3.connect("file:config/house_brain.db?mode=ro", uri=True) as db:
    result = db.execute("PRAGMA integrity_check").fetchone()[0]
if result != "ok":
    raise SystemExit(f"SQLite integrity check failed: {result}")
print("SQLite integrity check: ok")
PY
```

Riavvia House Brain:

```bash
set -a
source .env
set +a

docker compose up -d
docker compose ps
curl -sS http://localhost:8090/health
```

Il backup è completo soltanto se il checksum è stato creato e
`PRAGMA integrity_check` restituisce `ok`.

## 2. Verificare l'archivio prima del ripristino

Sostituisci il nome di esempio con il backup scelto:

```bash
set -a
source .env
set +a

backup_file="/docker/appdata/house-brain-backups/house-brain-config-YYYYMMDDTHHMMSSZ.tar.gz"

sha256sum -c "${backup_file}.sha256"
tar -tzf "${backup_file}"
```

L'archivio deve contenere una sola directory radice `config/`. Non procedere
se il checksum fallisce o se compaiono percorsi esterni a `config/`.

## 3. Ripristinare conservando lo stato precedente

```bash
set -a
source .env
set +a

backup_file="/docker/appdata/house-brain-backups/house-brain-config-YYYYMMDDTHHMMSSZ.tar.gz"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

docker compose stop house-brain
mv -- config "config.before-restore-${stamp}"
tar -C "$PWD" -xzf "${backup_file}"
sudo chown -R "$(id -u):10001" config
chmod -R u+rwX,g+rwX,o-rwx config
```

La directory `config.before-restore-...` è il ritorno immediato allo stato
precedente. Non eliminarla durante il collaudo.

## 4. Verificare e riavviare

Ripeti il controllo SQLite della sezione 1, quindi:

```bash
set -a
source .env
set +a

docker compose config --quiet
docker compose up -d
docker compose ps
curl -sS http://localhost:8090/health
```

Apri poi:

- `/diagnostics` con la chiave API e verifica Home Assistant e Ollama;
- `/memories` e verifica memorie attive e cestino;
- `/chat` e verifica una conversazione esistente;
- `/audit` e verifica eventi completati e rifiutati;
- `/autonomy` e verifica policy e backup;
- il client MCP e verifica almeno una lettura.

Conserva `config.before-restore-...` finché tutti i controlli sono conclusi.
Per tornare indietro, arresta nuovamente il servizio, sposta la `config/`
ripristinata con un nome distinto e rimetti al suo posto
`config.before-restore-...`.
