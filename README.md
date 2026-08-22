# House Brain

House Brain è un middleware locale tra modelli LLM e Home Assistant. Il modello non accede direttamente a Home Assistant: ogni lettura e azione passa attraverso strumenti, policy e controlli del server.

```text
Utente / automazione HA -> House Brain -> Ollama
                              |
                              +-> Home Assistant
                              +-> SQLite
                              +-> SearXNG (opzionale)
```

## Funzionalità

- lettura di stato, catalogo e cronologia Recorder;
- chat persistente con Ollama e strumenti;
- memoria persistente con cestino recuperabile;
- eventi autonomi in modalità `observe`, `simulate` ed `execute`;
- policy YAML default-deny con entità in sola lettura, controllabili e invisibili;
- esclusione automatica delle entità nascoste nel registro di Home Assistant;
- autorizzazione per entità condivisa da chat, eventi e API;
- piani di azione atomici, budget e audit con `tool_trace`;
- selezione dei servizi validata sul catalogo dinamico di Home Assistant;
- ricerca web opzionale tramite SearXNG;
- client web locale autenticato;
- server MCP autenticato con letture Home Assistant e memoria persistente.

Chat, eventi e `/actions` usano la stessa policy. Le entità in `visible` sono
leggibili ma non controllabili; quelle in `include` sono leggibili e
controllabili. Ogni entità non elencata è automaticamente invisibile.

## Avvio rapido con immagine precompilata

Non serve clonare il codice né creare un file `.env`. Scarica
`docker-compose.yml` e `config/autonomy.yaml.example`, rinomina il secondo
file in `config/autonomy.yaml`, quindi modifica direttamente nel Compose:

- `HOME_ASSISTANT_URL`;
- `HOME_ASSISTANT_TOKEN`;
- `HOUSE_BRAIN_API_KEY`;
- indirizzo e modello Ollama;
- lingua e altre opzioni desiderate.
- `PUID` e `PGID` dell'utente che deve possedere i file in `config/`.

Il Compose usa l'immagine versionata
`ghcr.io/vince87/house-brain:0.1.3`. Proteggi il file perché contiene token e
chiavi.

```bash
mkdir -p config
cp config/autonomy.yaml.example config/autonomy.yaml
sudo chown -R "$(id -u):$(id -g)" config
chmod 770 config
chmod 660 config/autonomy.yaml

docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
curl -sS http://localhost:8090/health
```

La directory locale `config/` è l'unico mount persistente e contiene policy,
database SQLite e backup della policy. Per lo sviluppo locale usa
`docker-compose.dev.yml`, che costruisce il codice e legge `.env`.
Il container assegna soltanto `/config` a `PUID:PGID` e poi esegue
l'applicazione senza privilegi; non richiede permessi `777`.

## Accesso

- API: `http://SERVER:8090`
- chat: `http://SERVER:8090/chat`
- configuratore autonomia: `http://SERVER:8090/autonomy`
- gestione memorie: `http://SERVER:8090/memories`
- Swagger: `http://SERVER:8090/docs`
- MCP Streamable HTTP: `http://SERVER:8090/mcp/`

Gli endpoint operativi richiedono `X-API-Key`. Il server MCP accetta anche lo standard `Authorization: Bearer HOUSE_BRAIN_API_KEY`. La chat conserva la chiave soltanto nel `sessionStorage` della scheda.

La pagina delle memorie permette di cercare, aggiungere, modificare, spostare nel cestino e ripristinare le memorie persistenti.

Il configuratore permette di selezionare entità in sola lettura o
controllabili; la scelta “Non visibile” rimuove l'entità dalla policy e codici opzionali senza esporre i codici già salvati. Ogni modifica crea un
backup protetto in `config/autonomy-backups/` e viene applicata subito al
processo.

## Documentazione

La documentazione completa è in [`docs/Home.md`](docs/Home.md):

- [manuale utente completo](docs/user-manual.md);
- [architettura](docs/architecture.md);
- [installazione e configurazione](docs/installation.md);
- [API](docs/api.md);
- [policy di autonomia](docs/autonomy-policy.md);
- [integrazione Home Assistant](docs/home-assistant.md);
- [gestione, sicurezza e sviluppo](docs/operations.md);
- [backup e ripristino guidato](docs/backup-restore.md);
- [checklist di collaudo beta](docs/beta-testing.md);
- [procedura di collaudo beta eseguibile](docs/beta-validation-runbook.md);
- [roadmap](docs/roadmap.md).

Queste pagine sono versionate insieme al codice e costituiscono la base della futura Wiki GitHub.

## Sviluppo

```bash
uv sync --extra dev
export AUTONOMY_POLICY_PATH="$PWD/config/autonomy.yaml"
export UV_LINK_MODE=copy

uv run pytest
uv run ruff check .
```

Per avviare l'API fuori da Docker:

```bash
uv run uvicorn house_brain.main:app \
  --host 0.0.0.0 \
  --port 8090 \
  --reload \
  --env-file .env
```

## Sicurezza operativa

L'esecuzione reale richiede che l'entità sia inclusa in `autonomy.yaml` e che sia attivo:

```dotenv
AUTONOMOUS_EXECUTION_ENABLED=true
```

Durante sviluppo e collaudo mantienilo su `false`. Quando viene richiesta un'azione, il riepilogo finale è costruito direttamente dalla `tool_trace`: il modello non può descrivere come simulata un'azione eseguita, o viceversa.

## Codici per entità sensibili

Un elemento di `entities.include` può avere un codice. Lo stesso codice viene
verificato da chat, eventi e `/actions`; non viene inviato a Ollama, salvato o
mostrato nella `tool_trace`. Vedi [Policy di autonomia](docs/autonomy-policy.md).

Questo codice protegge House Brain ed è distinto dall'eventuale codice richiesto
dal dispositivo Home Assistant. Il codice dispositivo viene fornito insieme al
comando, resta sul server ed è iniettato nella chiamata Home Assistant soltanto
dopo la scelta e la validazione del servizio. Per `/actions` usa
`X-Home-Assistant-Code`; il valore non compare nella risposta.

Il catalogo dei servizi è filtrato anche tramite i `supported_features` della
singola entità. Per gli allarmi, `code_arm_required` viene applicato solo ai
servizi di inserimento: un pannello può quindi richiedere il proprio codice per
il disinserimento ma non per l'inserimento.
