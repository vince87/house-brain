# Checklist di rilascio v0.1.3

Il tag e la release richiedono test automatici superati e consenso esplicito.

## Preparazione

- [ ] pacchetto e lockfile impostati a `0.1.3`;
- [ ] Compose pubblico impostato su `ghcr.io/vince87/house-brain:0.1.3`;
- [ ] changelog e manuale aggiornati;
- [ ] `docker compose config --quiet`, pytest e Ruff completati;
- [ ] workflow GitHub Actions completato;
- [ ] nessun file reale di configurazione, database o segreto incluso.

## Collaudo applicativo

- [ ] health check restituisce `0.1.3`;
- [ ] Ollama completa chat, letture e tool call ripetute;
- [ ] provider OpenAI-compatible accetta URL e modello configurati;
- [ ] modello OpenAI non caricato produce un errore esplicito;
- [ ] `observe`, `simulate` ed `execute` rispettano policy e kill switch;
- [ ] riepilogo finale coerente con la `tool_trace`;
- [ ] memorie, cestino, conversazioni e audit persistono dopo il riavvio;
- [ ] MCP non espone azioni Home Assistant.

## Container e interfacce

- [ ] file in `config/` appartenenti a PUID/PGID dopo avvio e scritture;
- [ ] container esegue House Brain senza privilegi;
- [ ] Chat, Memories, Audit, Autonomy e Log funzionano da desktop e mobile;
- [ ] pagina Log richiede autenticazione per i dati;
- [ ] token, chiavi e codici non compaiono nei log esposti;
- [ ] nessun socket Docker montato;
- [ ] unico mount persistente `./config:/config:rw`.

## Persistenza

- [ ] backup completo di `config/` creato con House Brain fermo;
- [ ] checksum del backup valido;
- [ ] `PRAGMA integrity_check` restituisce `ok`;
- [ ] ripristino verificato senza perdere policy, memorie, chat o audit;
- [ ] vecchi volumi Docker non eliminati automaticamente.

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

## Pubblicazione

- [ ] squash merge autorizzato;
- [ ] tag `v0.1.3` creato sul merge commit;
- [ ] GitHub Release pubblicata dalle note del changelog;
- [ ] workflow multiarch completato;
- [ ] immagini GHCR `0.1.3`, `0.1` e `latest` disponibili;
- [ ] installazione pulita verificata con l'immagine `0.1.3`.
