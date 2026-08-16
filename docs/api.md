# API

Gli endpoint operativi richiedono `X-API-Key`. Sono pubblici `/health`, `/docs`,
`/redoc`, `/openapi.json` e le shell `/chat` e `/autonomy`; i dati e i
salvataggi del configuratore restano protetti.

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
| GET | `/services` | servizi e vincoli correnti di Home Assistant |
| GET | `/admin/autonomy` | entità HA e configurazione senza codici |
| PUT | `/admin/autonomy` | valida, archivia e salva la policy |
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

Per Home Assistant espone esclusivamente `get_entity`, `search_entities`,
`list_entities`, `list_services` e `get_history`: non espone azioni. Tutte le letture
attraversano la policy di visibilità, quindi le entità escluse restano
invisibili anche ai client MCP.

La memoria persistente è disponibile tramite `remember_memory`,
`search_memories`, `forget_memory` e `restore_memory`. La rimozione sposta
la memoria nel cestino recuperabile e non cancella definitivamente il record.

`/actions` usa la stessa lista `entities.include` degli agenti. Se l'entità ha
un codice nella policy, passalo nell'header `X-Authorization-Code`. Se invece è
il dispositivo Home Assistant a richiedere un PIN o codice, usa l'header
`X-Home-Assistant-Code`. Sono controlli distinti e nessuno dei due valori viene
restituito nel payload di risposta.

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

## Catalogo servizi

House Brain legge `GET /api/services` da Home Assistant e mantiene una cache
breve. Prima di simulare o eseguire valida che `domain.service` esista, che i
parametri siano dichiarati e che rispettino opzioni e limiti numerici esposti
da Home Assistant. La policy `entities.include` e gli eventuali codici restano
comunque la barriera autorizzativa principale.

Per un comando con un singolo target, il contratto del relativo dominio viene
caricato prima della pianificazione. Il modello non deve inventare servizi e,
quando più servizi rappresentano modalità differenti, deve chiedere quale usare.
I campi segreti come `code` vengono rimossi dal testo inviato al modello e
aggiunti soltanto dal server alla chiamata Home Assistant.
