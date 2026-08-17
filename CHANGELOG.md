# Changelog

## Unreleased

Questa sezione descrive la candidata al primo tag stabile. La data sarà aggiunta
soltanto dopo il collaudo reale e il consenso esplicito al rilascio.

### Added

- integrazione controllata con Home Assistant, chat, memoria e audit persistenti;
- eventi observe, simulate ed execute con tool trace autorevole;
- catalogo dinamico e validazione generica dei servizi Home Assistant;
- configuratore web della policy e server MCP autenticato;
- procedura verificabile di backup e ripristino dell'intera directory config;
- immagine container versionata per amd64 e arm64 pubblicata tramite GHCR;
- Compose autonomo per utenti finali, senza dipendenza da `.env`;
- percorsi di policy e backup affidati ai default applicativi fissi in `/config`.

### Changed

- le risposte con azioni usano un riepilogo localizzato costruito dalla `tool_trace`,
  impedendo al testo del modello di confondere simulazioni ed esecuzioni reali;
- tutta la persistenza usa il solo bind mount `./config:/config:rw`;
- database e backup policy usano `/config/house_brain.db` e
  `/config/autonomy-backups`;
- il deployment Docker dichiara esplicitamente le variabili runtime.

### Security

- entità con `hidden_by` nel registro Home Assistant completamente invisibili
  e non azionabili in API, chat, eventi, configuratore e MCP;
- autorizzazioni globali per entità con precedenza delle esclusioni;
- validazione di servizio, parametri, capacità, codici e kill switch;
- codici rimossi dal testo inviato al modello e dalla tool trace;
- file reali, database, sidecar SQLite e backup esclusi da Git.
