# Manuale utente di House Brain

Questa guida accompagna dall'installazione al primo utilizzo sicuro. House Brain
è un intermediario tra Home Assistant e un modello linguistico: il modello non
accede direttamente alla casa, ma usa strumenti controllati dal server. Ogni
lettura rispetta la visibilità configurata e ogni azione viene validata prima di
raggiungere Home Assistant.

## 1. Come funziona la sicurezza

House Brain separa quattro decisioni:

1. **autenticazione**: chi può usare API e interfacce;
2. **visibilità**: quali entità il modello può conoscere e leggere;
3. **controllo**: quali entità possono ricevere azioni;
4. **esecuzione reale**: il kill switch globale abilita o blocca `execute`.

La configurazione è default-deny: un'entità non selezionata in Autonomy è
invisibile anche a chat, ricerche, cronologia e MCP.

| Modalità | Letture | Validazione azioni | Chiamate reali a HA |
|---|:---:|:---:|:---:|
| `observe` | sì | azioni vietate | no |
| `simulate` | sì | completa | no |
| `execute` | sì | completa | solo con kill switch attivo |

`simulate` applica gli stessi controlli di `execute`, fermandosi prima della
chiamata di servizio.

## 2. Requisiti

- Docker Engine con Docker Compose;
- Home Assistant raggiungibile dal container e relativo Long-Lived Access Token;
- Ollama oppure un provider OpenAI/OpenAI-compatible;
- una directory locale persistente `config/`.

Per l'uso normale è consigliata l'immagine GHCR. Git, Python e `uv` servono
soltanto per sviluppo.

## 3. Installazione con immagine precompilata

Scarica dalla release `docker-compose.yml` e
`config/autonomy.yaml.example`, quindi prepara:

```bash
mkdir -p config
cp config/autonomy.yaml.example config/autonomy.yaml
sudo chown -R "$(id -u):$(id -g)" config
chmod 770 config
chmod 660 config/autonomy.yaml
chmod 600 docker-compose.yml
```

Modifica direttamente `docker-compose.yml` e sostituisci almeno:

- `PUID` e `PGID` con il risultato di `id -u` e `id -g`;
- `HOME_ASSISTANT_URL` e `HOME_ASSISTANT_TOKEN`;
- `HOUSE_BRAIN_API_KEY` con un segreto lungo e casuale;
- provider, indirizzo e modello LLM;
- `AUTONOMOUS_EXECUTION_ENABLED`, inizialmente `false`.

Avvia:

```bash
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
curl -fsS http://localhost:8090/health | python3 -m json.tool
```

Non eseguire `docker compose config` senza `--quiet`: l'output può contenere i
segreti risolti. Il solo mount persistente è `./config:/config`; non montare il
socket Docker nel container.

## 4. Scegliere il modello

### Ollama

```yaml
LLM_PROVIDER: "ollama"
OLLAMA_URL: "http://host.docker.internal:11434"
OLLAMA_MODEL: "gemma4:12b"
OLLAMA_CONTEXT_WINDOW: "16384"
OLLAMA_MAX_OUTPUT_TOKENS: "4096"
OLLAMA_TEMPERATURE: "0.1"
```

Il modello deve supportare in modo affidabile il tool calling. House Brain
ritenta le risposte vuote e distingue l'esaurimento della finestra di contesto,
ma non può correggere un modello che non produce contenuto né strumenti.

### OpenAI ufficiale

```yaml
LLM_PROVIDER: "openai"
OPENAI_BASE_URL: "https://api.openai.com/v1"
OPENAI_MODEL: "gpt-5-mini"
OPENAI_API_KEY: "inserire-la-chiave"
OPENAI_MAX_OUTPUT_TOKENS: "4096"
```

Gli stati e i risultati necessari al ciclo agente vengono inviati al provider
configurato. Valuta questo aspetto prima di usare un servizio esterno.

### Server locale OpenAI-compatible

```yaml
LLM_PROVIDER: "openai"
OPENAI_BASE_URL: "http://server-locale:porta/v1"
OPENAI_MODEL: "identificatore-esatto-del-modello"
OPENAI_API_KEY: ""
```

La chiave è opzionale solo se il server locale non la richiede. Il modello deve
essere già caricato: lo standard OpenAI non definisce un'API universale per
caricare modelli. House Brain segnala separatamente un modello non disponibile.

## 5. Interfacce web

Apri `http://SERVER:8090/chat`. La navigazione collega:

| Pagina | Scopo |
|---|---|
| `/chat` | conversazioni persistenti e risultati delle azioni |
| `/memories` | aggiunta, modifica, ricerca, cestino e ripristino |
| `/audit` | eventi autonomi, esito e `tool_trace` completa |
| `/autonomy` | visibilità, controllo, nomi e codici delle entità |
| `/logs` | log applicativi recenti, filtrati e oscurati |
| `/docs` | API interattiva Swagger |

Le shell HTML sono pubbliche, ma nessun dato protetto viene restituito prima
dell'autenticazione. La chiave resta nel `sessionStorage` della singola scheda.

La pagina Log mostra un buffer limitato dei log applicativi. Non legge i log
Docker e non accede all'host. Token, chiavi e codici policy conosciuti vengono
oscurati.

### Lingua e ricerca web

`HOUSE_BRAIN_LANGUAGE` controlla la lingua delle risposte. Sono inclusi arabo,
cinese, inglese, francese, tedesco, italiano, giapponese, coreano, portoghese e
spagnolo; sono accettate anche varianti come `it-IT` e `pt-BR`.

La ricerca web è opzionale. Impostando `SEARXNG_URL`, la chat può usare un
server SearXNG; gli eventi automatici non ricevono questo strumento. Timeout e
numero massimo di risultati sono configurabili con `WEB_SEARCH_TIMEOUT` e
`WEB_SEARCH_MAX_RESULTS`.

## 6. Configurare Autonomy

Apri `/autonomy`, inserisci la chiave e aggiorna il catalogo. Per ogni entità:

- **Non visibile**: non viene scritta nella policy;
- **Solo visibile**: può essere letta, ma mai controllata;
- **Controllabile**: può essere letta e ricevere servizi validati;
- **Richiedi codice**: ogni azione sull'entità richiede il codice.

Quando abiliti un'entità, il nome iniziale proviene dal `friendly_name` di Home
Assistant. Puoi modificarlo: il nome configurato diventa autorevole per display
e risoluzione; l'entity ID esatto resta sempre valido.

```yaml
version: 2

entities:
  visible:
    - entity_id: sensor.example_temperature
      name: Temperatura di esempio

  include:
    - entity_id: light.example_room
      name: Luce di esempio
    - entity_id: lock.example_front_door
      name: Porta di esempio
      code: "2468"
```

Ogni salvataggio dalla GUI valida il file, crea un backup in
`/config/autonomy-backups` e applica subito la policy. Una modifica manuale
richiede invece la ricreazione del container.

Le entità nascoste nel registro Home Assistant sono sempre trattate come
inesistenti, anche se rimangono accidentalmente nel file YAML.

## 7. Chat e risoluzione delle entità

Inizia con una lettura esplicita:

```text
Leggi lo stato di light.example_room e non eseguire azioni.
```

Passa poi alla simulazione:

```text
Simula lo spegnimento di light.example_room.
```

Per nomi ambigui la chat deve chiedere quale dispositivo usare. Se indichi un
entity ID inesistente o non controllabile, il modello non può sostituirlo.

Il risultato autorevole è la scheda costruita dalla `tool_trace`, non una frase
libera del modello. Controlla entità, servizio, stato `simulated`, `executed` o
`rejected` e motivo dell'eventuale rifiuto.

## 8. Memorie

Una memoria contiene chiave, valore, categoria e importanza. Usala per
preferenze durevoli, non per duplicare gli stati correnti di Home Assistant. Se
cita entity ID visibili, House Brain ne verifica gli stati quando possibile.

Da `/memories` puoi creare, cercare e modificare una memoria, spostarla nel
cestino e ripristinarla. La rimozione è recuperabile. Memorie, cestino,
conversazioni e audit sono in `/config/house_brain.db`.

## 9. Eventi da Home Assistant

L'integrazione normale invia modalità e istruzione a `POST /agent/events`:

```yaml
rest_command:
  house_brain_event:
    url: !secret house_brain_events_url
    method: POST
    headers:
      X-API-Key: !secret house_brain_api_key
    content_type: application/json
    timeout: 150
    payload: >-
      {
        "mode": {{ event_mode | default("simulate") | tojson }},
        "instruction": {{ instruction | tojson }}
      }
```

Collauda prima `observe`, poi `simulate`. Gli eventi automatici non scelgono
arbitrariamente tra risultati ambigui: rifiutano l'azione.

## 10. Azioni reali e codici

`execute` richiede anche il kill switch globale:

```yaml
AUTONOMOUS_EXECUTION_ENABLED: "true"
```

Con `false`, una richiesta execute non può comandare Home Assistant. Attivalo
solo dopo un periodo di simulazione e inizia con un'azione reversibile.

Esistono due codici distinti:

- **codice policy House Brain**, configurato accanto all'entità;
- **codice Home Assistant**, richiesto dal servizio o dispositivo.

Per `/actions` usa rispettivamente `X-Authorization-Code` e
`X-Home-Assistant-Code`. In chat o eventi il server estrae il codice dal testo,
lo rimuove prima del modello e non lo inserisce in cronologia o `tool_trace`.

## 11. Diagnostica, audit e log

Ogni evento autonomo compare in `/audit` con modalità, stato, istruzione
sanificata, risposta, strumenti e traccia completa.

Per diagnosticare usa nell'ordine:

1. `/health` per il processo;
2. `/diagnostics` per Home Assistant e provider LLM;
3. `/logs` per gli eventi applicativi recenti;
4. `/audit` per la singola decisione;
5. `docker compose logs --tail=200 house-brain` se il container non parte.

## 12. MCP

Il server MCP Streamable HTTP è disponibile su `/mcp/` e usa:

```text
Authorization: Bearer HOUSE_BRAIN_API_KEY
```

Espone letture Home Assistant filtrate dalla policy e gestione delle memorie.
Non espone strumenti per comandare dispositivi: la limitazione è intenzionale.

## 13. Backup, aggiornamento e rollback

L'intera persistenza è nella directory `config/`:

```text
config/
├── autonomy.yaml
├── house_brain.db
└── autonomy-backups/
```

Ferma House Brain prima di archiviarla, crea un checksum e verifica
`PRAGMA integrity_check`. La procedura completa è in
[Backup e ripristino](backup-restore.md). Non usare `docker compose down -v` per
pulire dati e non eliminare vecchi volumi senza backup e autorizzazione.

Per aggiornare l'immagine: leggi il changelog, crea il backup, modifica il tag
nel Compose, esegui `docker compose pull` e `docker compose up -d`, quindi
verifica health, policy, memorie, chat e audit. Usa tag di versione per rendere
il rollback prevedibile.

## 14. Problemi comuni

| Sintomo | Controllo principale |
|---|---|
| `401` | chiave House Brain mancante o errata |
| `403` | entità, codice, modalità o kill switch |
| `404` su entità presente in HA | entità non visibile o nascosta in HA |
| `502` Home Assistant | URL, token, rete o API HA |
| risposta vuota Ollama | modello/tool template, contesto, versione Ollama |
| modello OpenAI non disponibile | ID errato o modello locale non caricato |
| policy ignorata | modifica manuale senza ricreazione |
| container in riavvio | log, permessi `config/`, PUID e PGID |
| testo contrario all'azione | considera autorevole la `tool_trace` |

## 15. Checklist del primo collaudo

- `/health` restituisce `status: ok`;
- `/diagnostics` vede Home Assistant e il modello;
- Autonomy contiene soltanto le entità necessarie;
- una lettura visibile riesce e una non selezionata restituisce 404;
- `observe` non esegue azioni;
- `simulate` valida senza eseguire;
- audit e tool trace riportano il risultato corretto;
- memoria, modifica, cestino e ripristino funzionano;
- backup e `PRAGMA integrity_check` riescono;
- soltanto dopo viene provato un `execute` reversibile.

Le altre guide in `docs/` approfondiscono API, architettura, policy, Home
Assistant, operazioni, backup e collaudo beta.
