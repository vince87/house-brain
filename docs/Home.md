# House Brain Wiki

House Brain è un middleware locale tra Ollama e Home Assistant. Il modello non accede direttamente alla casa: legge dati e propone azioni attraverso strumenti controllati da House Brain.

## Guide

- [Architettura](architecture.md)
- [Installazione e configurazione](installation.md)
- [API](api.md)
- [Policy di autonomia](autonomy-policy.md)
- [Home Assistant](home-assistant.md)
- [Gestione, sicurezza e sviluppo](operations.md)

## Stato attuale

Sono disponibili lettura di stato e Recorder, catalogo entità, chat e memoria persistenti, eventi `observe`/`simulate`/`execute`, visibilità globale, policy per evento, audit con `tool_trace`, ricerca web SearXNG opzionale e una chat web autenticata.

Il motore delle azioni supporta attualmente `light`, `switch`, `fan`, `cover` e `climate`. La generalizzazione a qualunque `domain.service` esplicitamente autorizzato dalla policy è il prossimo intervento previsto.
