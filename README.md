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
- ricerca web opzionale tramite SearXNG;
- client web locale autenticato.

Chat, eventi e `/actions` usano la stessa policy. Le entità incluse sono
controllabili tramite servizi coerenti con il loro dominio; quelle escluse sono
completamente invisibili. Le entità non elencate restano visibili in sola lettura.

## Avvio rapido

```bash
cp .env.example .env
cp autonomy.yaml.example autonomy.yaml

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

Non commettere `.env`, `autonomy.yaml`, token, chiavi o database.

Le istruzioni interne dell'agente e gli schemi dei tool sono in inglese. La
variabile `HOUSE_BRAIN_LANGUAGE` obbliga il modello a tradurre tutte le risposte
per l'utente e seleziona anche i messaggi di sicurezza generati direttamente
dal server. Sono inclusi i pacchetti `ar`, `de`, `en`, `es`, `fr`, `it`, `ja`,
`ko`, `pt` e `zh`; sono accettati anche tag regionali come `it-IT` e `pt-BR`.

## Accesso

- API: `http://SERVER:8090`
- chat: `http://SERVER:8090/chat`
- Swagger: `http://SERVER:8090/docs`

Gli endpoint operativi richiedono `X-API-Key`. La chat conserva la chiave soltanto nel `sessionStorage` della scheda.

## Documentazione

La documentazione completa è in [`docs/Home.md`](docs/Home.md):

- [architettura](docs/architecture.md);
- [installazione e configurazione](docs/installation.md);
- [API](docs/api.md);
- [policy di autonomia](docs/autonomy-policy.md);
- [integrazione Home Assistant](docs/home-assistant.md);
- [gestione, sicurezza e sviluppo](docs/operations.md).

Queste pagine sono versionate insieme al codice e costituiscono la base della futura Wiki GitHub.

## Sviluppo

```bash
uv sync --extra dev
export AUTONOMY_POLICY_PATH="$PWD/autonomy.yaml"
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
