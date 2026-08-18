# House Brain Wiki

House Brain è un middleware locale tra Ollama e Home Assistant. Il modello non accede direttamente alla casa: legge dati e propone azioni attraverso strumenti controllati da House Brain.

## Guide

- [Architettura](architecture.md)
- [Installazione e configurazione](installation.md)
- [API](api.md)
- [Policy di autonomia](autonomy-policy.md)
- [Home Assistant](home-assistant.md)
- [Gestione, sicurezza e sviluppo](operations.md)
- [Backup e ripristino guidato](backup-restore.md)
- [Checklist di collaudo beta](beta-testing.md)
- [Procedura di collaudo beta eseguibile](beta-validation-runbook.md)
- [Roadmap](roadmap.md)

## Stato attuale

Sono disponibili lettura di stato e Recorder, catalogo entità, chat e memoria
persistenti, eventi `observe`/`simulate`/`execute`, audit con `tool_trace`,
ricerca web SearXNG opzionale, chat web autenticata e configuratore della
policy di autonomia. La chat mostra inoltre schede di audit per le azioni con
target, servizio, esito e motivo dell'eventuale rifiuto.

Una sola policy globale distingue entità controllabili, entità invisibili ed
entità visibili in sola lettura. Chat, eventi e API applicano le stesse regole
e gli stessi codici per dispositivo.
