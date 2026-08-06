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
- policy YAML deny-by-default per eventi, servizi, entità e parametri;
- visibilità globale delle entità;
- piani di azione atomici, budget e audit con `tool_trace`;
- ricerca web opzionale tramite SearXNG;
- client web locale autenticato.

Negli eventi autonomi il motore può rappresentare qualunque `domain.service`, ma
esegue soltanto combinazioni di servizio, entità e parametri autorizzate
esplicitamente dalla policy dell'evento. L'endpoint diretto `/actions` e la chat
normale conservano per ora il perimetro storico `light`, `switch`, `fan`,
`cover` e `climate`.

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
- indirizzo e modello Ollama.

Non commettere `.env`, `autonomy.yaml`, token, chiavi o database.

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

L'esecuzione reale richiede sia l'autorizzazione dell'evento in `autonomy.yaml` sia:

```dotenv
AUTONOMOUS_EXECUTION_ENABLED=true
```

Durante sviluppo e collaudo mantienilo su `false`. Se la risposta testuale del modello contraddice la `tool_trace`, considera vera la traccia.

## Comandi sensibili dalla chat

Il blocco riservato `events.chat_command` può autorizzare azioni generiche dalla
chat. Una singola combinazione servizio-entità può richiedere un codice locale
dichiarato in `autonomy.yaml`. Scrivilo nel messaggio con il formato
`codice: VALORE`: House Brain lo rimuove prima di Ollama e non lo salva nella
conversazione o nella `tool_trace`.

Vedi [Policy di autonomia](docs/autonomy-policy.md#codici-per-azioni-dalla-chat).
