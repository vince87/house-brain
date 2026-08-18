# Changelog

## Unreleased

Questa sezione resta disponibile per modifiche successive alla candidata 0.1.1.

## 0.1.1 - 2026-08-18

La data sarà aggiunta soltanto dopo il collaudo della branch release e il consenso
esplicito alla pubblicazione.

### Added

- gestione web autenticata delle memorie con ricerca, modifica, cestino e
  ripristino;
- interfaccia web autenticata dell'audit con filtri e tool trace completa;
- endpoint autenticato `/diagnostics` per verificare in modo sicuro Home
  Assistant, Ollama e il modello configurato;
- esclusione automatica delle entità con `hidden_by` nel registro Home
  Assistant da API, chat, eventi, configuratore e MCP;
- procedura eseguibile di collaudo beta per observe, simulate, execute,
  persistenza, backup/ripristino e MCP;
- riepiloghi localizzati delle azioni costruiti dal server a partire dalla
  `tool_trace`.

### Changed

- i percorsi di policy e backup nel Compose pubblico usano direttamente i
  default applicativi fissi in `/config`;
- le risposte con azioni non dipendono più dal testo libero del modello per
  distinguere simulazioni ed esecuzioni reali;
- Chat, Autonomy, Memories e Audit condividono la stessa palette visiva;
- le tracce delle azioni registrano la modalità simulate/execute imposta dal
  server.

### Fixed

- lettura di registri entità Home Assistant superiori al limite WebSocket
  predefinito di 1 MiB;
- possibile contraddizione tra il risultato autorevole degli strumenti e il
  riepilogo finale del modello;
- riepiloghi execute troppo verbosi che mostravano tentativi rifiutati, duplicati
  e target incompleti prima dell'ultimo piano riuscito;
- ricomparsa nel configuratore di entità nascoste ma presenti nella policy;
- risposte vuote intermittenti di Ollama tramite tentativi configurabili e
  fallback autorevole quando gli strumenti hanno già prodotto un risultato;
- descrizioni dello stato in modalità observe prive di una lettura Home
  Assistant riuscita.

### Security

- le entità nascoste da Home Assistant sono trattate come inesistenti e non
  azionabili;
- i riferimenti a entità nascoste vengono rimossi anche dagli attributi di
  entità visibili;
- il registro entità resta fail-closed e usa un limite esplicito di 16 MiB;
- MCP continua a non esporre strumenti per eseguire azioni Home Assistant;
- codici e segreti restano esclusi da tool trace, cronologia e diagnostica.

## 0.1.0 - 2026-08-17

### Added

- integrazione controllata con Home Assistant, chat, memoria e audit persistenti;
- eventi observe, simulate ed execute con tool trace autorevole;
- catalogo dinamico e validazione generica dei servizi Home Assistant;
- configuratore web della policy e server MCP autenticato;
- procedura verificabile di backup e ripristino dell'intera directory config;
- immagine container versionata per amd64 e arm64 pubblicata tramite GHCR;
- Compose autonomo per utenti finali, senza dipendenza da `.env`.

### Changed

- tutta la persistenza usa il solo bind mount `./config:/config:rw`;
- database e backup policy usano `/config/house_brain.db` e
  `/config/autonomy-backups`;
- il deployment Docker dichiara esplicitamente le variabili runtime.

### Security

- autorizzazioni globali per entità con precedenza delle esclusioni;
- validazione di servizio, parametri, capacità, codici e kill switch;
- codici rimossi dal testo inviato al modello e dalla tool trace;
- file reali, database, sidecar SQLite e backup esclusi da Git.
