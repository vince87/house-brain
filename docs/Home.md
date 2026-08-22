# Documentazione House Brain

House Brain è un middleware locale tra Home Assistant e Ollama oppure un
provider OpenAI-compatible. Il modello non accede direttamente alla casa: legge
dati e propone azioni attraverso strumenti controllati dal server.

## Da dove iniziare

Per installazione, primo accesso, configurazione, collaudo e uso quotidiano
segui il [Manuale utente completo](user-manual.md). Le pagine seguenti sono
approfondimenti tecnici e operativi.

## Guide

- [Manuale utente completo](user-manual.md)
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

Una sola policy globale parte da nessuna entità visibile e distingue entità
in sola lettura (`visible`) e controllabili (`include`); tutte le altre sono invisibili. Chat, eventi e API applicano le stesse regole
e gli stessi codici per dispositivo.
