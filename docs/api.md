# API

Gli endpoint operativi richiedono `X-API-Key`. Sono pubblici `/health`, `/docs`, `/redoc`, `/openapi.json` e la shell `/chat`; le operazioni della chat restano protette.

| Metodo | Percorso | Funzione |
|---|---|---|
| GET | `/health` | stato servizio |
| GET | `/auth/check` | verifica chiave |
| GET | `/llm/status` | Ollama e modello |
| POST | `/agent/chat` | chat con strumenti |
| GET | `/entities/{entity_id}` | stato corrente |
| GET | `/history` | Recorder recente |
| GET | `/state-before` | stato prima di un istante |
| GET | `/entity-catalog` | ricerca catalogo |
| POST | `/actions` | singola azione controllata |
| POST/GET | `/memory` | scrittura e ricerca memorie |
| DELETE | `/memory/{key}` | cestino memoria |
| POST | `/memory/{key}/restore` | ripristino memoria |
| GET/DELETE | `/conversations/{session_id}` | sessione chat |
| POST | `/agent/events` | evento autonomo |
| GET | `/events` | audit eventi |
| GET | `/events/{event_id}` | evento e tool trace |

`/entity-catalog` è una ricerca, non un dump. `query` è obbligatorio:

```bash
curl -sG http://localhost:8090/entity-catalog \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" \
  --data-urlencode "query=ventola garage" \
  --data-urlencode "limit=20"
```

## Errori

| Codice | Significato |
|---:|---|
| 401 | chiave mancante o errata |
| 403 | policy, modalità o kill switch negano |
| 404 | entità nascosta/sconosciuta o record assente |
| 422 | richiesta non valida |
| 502 | dipendenza non raggiungibile o risposta non valida |

Gli schemi completi sono disponibili in Swagger su `/docs`.
