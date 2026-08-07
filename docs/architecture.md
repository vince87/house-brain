# Architettura

## Flusso

1. Un utente usa `POST /agent/chat`, oppure Home Assistant invia `POST /agent/events`.
2. House Brain avvia un agent loop limitato.
3. Ollama può richiedere strumenti per leggere entità, cronologia, memoria o ricerca web.
4. Ogni piano viene validato interamente prima della prima chiamata a Home Assistant.
5. `simulate` valida e registra senza eseguire; `execute` richiede policy e kill switch.
6. Eventi e tracce vengono salvati in SQLite.

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

## Componenti

| Modulo | Responsabilità |
|---|---|
| `main.py` | API FastAPI, autenticazione e mapping errori |
| `agent.py` | prompt, strumenti, agent loop, piani atomici e traccia |
| `actions.py` | validazione strutturale generica e coerenza dominio-entità |
| `autonomy.py` | policy YAML fail-fast |
| `home_assistant.py` | stati, catalogo, Recorder, servizi e visibilità |
| `ollama.py` | tool-calling e disponibilità modello |
| `memory.py` | memorie e cestino recuperabile |
| `conversations.py` | sessioni chat |
| `events.py` | eventi e audit persistente |
| `web_search.py` | ricerca SearXNG limitata |
| `web_chat.py` | client web locale |

Il database predefinito è `/data/house_brain.db`. Contiene memorie, conversazioni ed eventi.

## Limiti intenzionali

- 10 iterazioni massime dell'agent loop;
- 20 azioni massime per piano;
- budget globale massimo di 10 azioni per richiesta agente;
- 8 domini e 100 entità massime per snapshot;
- Recorder recente fino a 7 giorni;
- state-before fino a 30 giorni;
- ricerca web disponibile solo nelle chat, non negli eventi.
