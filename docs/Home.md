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

Gli eventi autonomi possono rappresentare qualunque `domain.service`, ma la
policy dell'evento deve autorizzare esattamente servizio, entità e parametri.
L'API diretta e la chat normale conservano il perimetro storico dei domini
supportati.
