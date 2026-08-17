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
- policy YAML semplice con entità controllabili e invisibili;
- autorizzazione per entità condivisa da chat, eventi e API;
- piani di azione atomici, budget e audit con `tool_trace`;
- selezione dei servizi validata sul catalogo dinamico di Home Assistant;
- ricerca web opzionale tramite SearXNG;
- client web locale autenticato;
- server MCP autenticato con letture Home Assistant e memoria persistente.

Chat, eventi e `/actions` usano la stessa policy. Le entità incluse sono
controllabili tramite servizi coerenti con il loro dominio; quelle escluse sono
completamente invisibili. Le entità non elencate restano visibili in sola lettura.

## Avvio rapido

```bash
cp .env.example .env
mkdir -p config
cp config/autonomy.yaml.example config/autonomy.yaml
sudo chown "$(id -u):10001" config config/autonomy.yaml
chmod 770 config
chmod 660 config/autonomy.yaml

docker compose config --quiet
docker compose up -d --build
docker compose ps

curl -sS http://localhost:8090/health
```

Configura in `.env` almeno:

- `HOME_ASSISTANT_URL`;
- `HOME_ASSISTANT_TOKEN`;
- `HOUSE_BRAIN_API_KEY`;
- indirizzo e modello Ollama;
- `HOUSE_BRAIN_LANGUAGE` con la lingua delle risposte (predefinita `it`).
- `HOME_ASSISTANT_SERVICE_CACHE_TTL` per la cache dei servizi Home Assistant
  (predefinita `300` secondi).

Non commettere `.env`, `config/autonomy.yaml`, token, chiavi o database.

Compose legge `.env` per l'interpolazione, ma dichiara esplicitamente ogni
variabile passata al container. La directory locale `config/` è l'unico mount
di configurazione scrivibile; i dati persistenti restano nel volume `/data`.

Le istruzioni interne dell'agente e gli schemi dei tool sono in inglese. La
variabile `HOUSE_BRAIN_LANGUAGE` obbliga il modello a tradurre tutte le risposte
per l'utente e seleziona anche i messaggi di sicurezza generati direttamente
dal server. Sono inclusi i pacchetti `ar`, `de`, `en`, `es`, `fr`, `it`, `ja`,
`ko`, `pt` e `zh`; sono accettati anche tag regionali come `it-IT` e `pt-BR`.

## Accesso

- API: `http://SERVER:8090`
- chat: `http://SERVER:8090/chat`
- configuratore autonomia: `http://SERVER:8090/autonomy`
- Swagger: `http://SERVER:8090/docs`
- MCP Streamable HTTP: `http://SERVER:8090/mcp/`

Gli endpoint operativi richiedono `X-API-Key`. Il server MCP accetta anche lo standard `Authorization: Bearer HOUSE_BRAIN_API_KEY`. La chat conserva la chiave soltanto nel `sessionStorage` della scheda.

Il configuratore permette di selezionare entità controllabili, entità nascoste
e codici opzionali senza esporre i codici già salvati. Ogni modifica crea un
backup protetto nel volume dati e viene applicata subito al processo.

## Documentazione

La documentazione completa è in [`docs/Home.md`](docs/Home.md):

- [architettura](docs/architecture.md);
- [installazione e configurazione](docs/installation.md);
- [API](docs/api.md);
- [policy di autonomia](docs/autonomy-policy.md);
- [integrazione Home Assistant](docs/home-assistant.md);
- [gestione, sicurezza e sviluppo](docs/operations.md).
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

Durante sviluppo e collaudo mantienilo su `false`. Se la risposta testuale del modello contraddice la `tool_trace`, considera vera la traccia.

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
