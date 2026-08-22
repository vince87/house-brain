# Checklist di rilascio v0.1.4

Hotfix per i bind mount già accessibili a PUID/PGID ma incompatibili con un
`chown` eseguito dal container.

## Verifica

- [x] versione applicativa, lockfile e Compose impostati a `0.1.4`;
- [x] PUID/PGID reali possono leggere e scrivere `/config`;
- [x] l'entrypoint salta il `chown` quando l'accesso è già sufficiente;
- [x] policy, database e backup restano invariati;
- [x] test di deployment e Ruff completati;
- [x] collaudo reale della branch con bind mount `1000:1000` completato;
- [ ] GitHub Actions completato sul commit finale;
- [ ] immagine multiarch `ghcr.io/vince87/house-brain:0.1.4` pubblicata;
- [ ] health check dell'immagine restituisce `0.1.4`.

## Collaudo host-side

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

La pubblicazione richiede consenso esplicito e deve usare squash merge.
