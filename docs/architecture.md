# Architettura

## Flusso

1. Un utente usa `POST /agent/chat`, oppure Home Assistant invia `POST /agent/events`.
2. House Brain avvia un agent loop limitato.
3. Ollama può richiedere strumenti per leggere entità, cronologia, memoria o ricerca web.
4. Ogni piano viene validato interamente prima della prima chiamata a Home Assistant.
5. `simulate` valida e registra senza eseguire; `execute` richiede policy e kill switch.
6. Eventi e tracce vengono salvati in SQLite.

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

- 8 iterazioni massime dell'agent loop;
- 20 azioni massime per piano;
- budget globale massimo di 10 azioni per richiesta agente;
- 8 domini e 100 entità massime per snapshot;
- Recorder recente fino a 7 giorni;
- state-before fino a 30 giorni;
- ricerca web disponibile solo nelle chat, non negli eventi.
