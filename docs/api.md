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
| MCP | `/mcp/` | strumenti Home Assistant in sola lettura |

## MCP

Il server MCP usa Streamable HTTP su `/mcp/` e accetta la stessa chiave API
come Bearer token:

```text
Authorization: Bearer HOUSE_BRAIN_API_KEY
```

Espone esclusivamente `get_entity`, `search_entities`, `list_entities` e
`get_history`. Non espone azioni. Tutte le letture attraversano la policy di
visibilità: le entità escluse restano invisibili anche ai client MCP.

`/actions` usa la stessa lista `entities.include` degli agenti. Se l'entità ha un codice, passalo nell'header `X-Authorization-Code`.

Il payload minimo di `POST /agent/events` contiene `mode` e `instruction`.
`event_type`, `source` e `context` sono facoltativi e ricevono valori
predefiniti. I campi tecnici servono all'audit o a integrazioni avanzate, non
concedono autorizzazioni.

`/entity-catalog` è una ricerca, non un dump. `query` è obbligatorio:

```bash
curl -sG http://localhost:8090/entity-catalog \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" \
  --data-urlencode "query=dispositivo di esempio" \
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
