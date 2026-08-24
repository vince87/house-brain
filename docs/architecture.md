# Architettura

## Flusso

1. Un utente usa `POST /agent/chat`, oppure Home Assistant invia
   `POST /agent/events` direttamente o tramite le entità native Conversation e
   AI Task.
2. House Brain avvia un agent loop limitato.
3. Il provider LLM selezionato può richiedere strumenti per leggere entità,
   cronologia, memoria o ricerca web.
4. Il server precarica i servizi Home Assistant del dominio risolto e li filtra
   tramite le capacità dichiarate dalla specifica entità.
5. Ogni piano viene validato interamente prima della prima chiamata a Home Assistant.
6. `simulate` valida e registra senza eseguire; `execute` richiede policy e kill switch.
7. Eventi e tracce vengono salvati in SQLite.

## Risoluzione delle entità

Per un singolo dispositivo l'agente usa un risolutore deterministico prima di
leggere o comandare l'entità. Il server normalizza maiuscole, accenti, spazi e
underscore, quindi applica questo ordine:

1. entity ID esatto;
2. friendly name esatto;
3. object ID esatto;
4. tutte le parole presenti nel friendly name;
5. tutte le parole presenti tra object ID e friendly name.

Il risultato è `resolved`, `ambiguous`, `not_found` oppure
`not_controllable`. Un risultato ambiguo non autorizza il modello a scegliere:
in chat deve chiedere quale candidato usare; negli eventi deve evitare l'azione.
Per i comandi, i candidati vengono limitati alle entità controllabili della
policy. Il catalogo non restituisce più dispositivi soltanto perché appartengono
a un dominio preferito: almeno una parola deve coincidere.

## Contesto relazionale

Per richieste che riguardano stanze, aree o dispositivi collegati, il server
legge i registri Home Assistant di aree, dispositivi ed entità e costruisce una
vista relazionale limitata. La vista viene filtrata dalla policy default-deny
prima di essere esposta al modello. Area e dispositivo spiegano la selezione ma
non autorizzano mai una lettura o un'azione.

Il tool `get_home_context` e l'endpoint `GET /context` usano lo stesso motore,
la stessa paginazione e gli stessi nomi autorevoli configurati in Autonomy.
Una vista troncata non costituisce prova dell'assenza di un'entità.

## Componenti

| Modulo | Responsabilità |
|---|---|
| `main.py` | API FastAPI, autenticazione e mapping errori |
| `agent.py` | prompt, strumenti, agent loop, piani atomici e traccia |
| `actions.py` | validazione strutturale generica e coerenza dominio-entità |
| `autonomy.py` | policy YAML fail-fast |
| `home_assistant.py` | stati, catalogo, Recorder, servizi e visibilità |
| `home_context.py` | relazioni area-dispositivo-entità e contesto limitato |
| `ollama.py` | tool-calling e disponibilità modello |
| `openai.py` | adattatore Chat Completions per OpenAI e server compatibili |
| `llm.py` | selezione indipendente del provider |
| `memory.py` | memorie e cestino recuperabile |
| `conversations.py` | sessioni chat |
| `events.py` | eventi e audit persistente |
| `web_search.py` | ricerca SearXNG limitata |
| `web_chat.py` | client web locale |
| `runtime_logs.py` | buffer limitato e oscuramento dei log applicativi |
| `web_theme.py` | navigazione e tema condiviso delle interfacce |
| `custom_components/house_brain` | ponte nativo Home Assistant per Assist e AI Task |

La chat presenta le azioni con entità, servizio, esito e motivo reale del
rifiuto. La `tool_trace` resta la fonte autorevole e i codici non sono inclusi
né nella traccia né nella cronologia della conversazione.

Il database predefinito è `/config/house_brain.db`. Contiene memorie,
conversazioni ed eventi. Policy, database e backup persistono tutti tramite
l'unico bind mount `./config:/config`.

## Limiti intenzionali

- 10 iterazioni massime dell'agent loop;
- 20 azioni massime per piano;
- budget globale massimo di 10 azioni per richiesta agente;
- 8 domini e 100 entità massime per snapshot;
- 8 aree e 100 entità massime per pagina di contesto;
- Recorder recente fino a 7 giorni;
- state-before fino a 30 giorni;
- ricerca web disponibile solo nelle chat, non negli eventi.
