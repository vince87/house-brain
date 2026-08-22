# Changelog

## Unreleased

Questa sezione resta disponibile per modifiche successive alla release 0.1.3.

## 0.1.3 - 2026-08-22

### Added

- provider OpenAI Chat Completions con supporto sia all'API ufficiale sia a
  server locali OpenAI-compatible e URL configurabile;
- pagina web autenticata dei log applicativi recenti, con ricerca, filtri,
  aggiornamento automatico e oscuramento dei segreti;
- manuale utente completo per installazione, configurazione, interfacce,
  sicurezza, collaudo, backup, diagnosi e aggiornamento;
- configurazione PUID/PGID per mantenere i file persistenti di proprietà
  dell'utente scelto sul server.

### Changed

- Chat, Memories, Audit, Autonomy e Log condividono navigazione, tema responsive
  e componenti visivi coerenti;
- il container corregge soltanto la proprietà di `/config` e avvia House Brain
  senza privilegi tramite l'utente configurato;
- Ollama usa limiti espliciti di contesto, output e temperatura e registra
  diagnostica strutturata sulle risposte vuote senza esporre prompt;
- la diagnostica e la documentazione descrivono il provider LLM selezionato
  invece di presumere sempre Ollama.

### Fixed

- risposte Ollama vuote gestite con recupero più robusto e fallback autorevole
  quando gli strumenti hanno già prodotto risultati;
- disponibilità dei modelli su server OpenAI-compatible che espongono soltanto
  `GET /v1/models` o rispondono HTTP 200 agli endpoint sconosciuti;
- blocchi di ragionamento `<think>` rimossi dalle risposte mostrate all'utente;
- diagnostica chiara quando il modello OpenAI configurato non è disponibile o
  non è stato caricato;
- accesso alla pagina Log con codici policy rappresentati come stringhe.

### Security

- nessun accesso al socket Docker dalla pagina Log;
- token Home Assistant, chiavi House Brain/OpenAI e codici policy vengono
  oscurati prima dell'esposizione dei log;
- filesystem container read-only, capability ridotte e
  `no-new-privileges` restano attivi durante la gestione PUID/PGID;
- tool trace, cronologia e log continuano a non mostrare codici di
  autorizzazione.

## 0.1.2 - 2026-08-19

### Added

- visibilità delle entità default-deny con selezione esplicita in sola lettura
  tramite `entities.visible`;
- nomi autorevoli opzionali per le entità, inizializzati dal `friendly_name` di
  Home Assistant e modificabili dal configuratore;
- migrazione sicura delle precedenti esclusioni al nuovo modello con sole
  entità visibili o controllabili.

### Changed

- ogni entità non presente in `visible` o `include` è automaticamente
  invisibile ad API, chat, eventi e MCP;
- il configuratore usa “Non visibile” come stato della GUI senza scrivere
  entità o pattern ridondanti nella policy;
- risoluzione e risultati degli strumenti usano il nome configurato come
  riferimento autorevole;
- il motore delle azioni e la selezione delle entità restano generici e
  indipendenti da domini, servizi e lingua;
- gli store persistenti SQLite vengono riutilizzati per database invece di
  essere ricreati a ogni richiesta.

### Fixed

- filtraggio dei riferimenti a entità invisibili senza rimuovere normali
  stringhe dagli attributi Home Assistant;
- ricerche delle memorie che potevano restituire risultati non pertinenti;
- decodifica dell'audit in presenza di record JSON danneggiati;
- gestione concorrente di SQLite tramite WAL, busy timeout e configurazione
  condivisa;
- perdita o esposizione di dati sensibili in strutture annidate della tool
  trace;
- selezioni arbitrarie quando più entità hanno nomi simili o quando il target
  esplicito non è controllabile.

### Security

- nessuna entità è leggibile o comandabile senza una scelta esplicita nella
  policy;
- entità nascoste nel registro Home Assistant restano inaccessibili anche nel
  configuratore;
- le vecchie esclusioni restano fail-closed durante la migrazione e vengono
  rimosse soltanto al salvataggio della nuova policy;
- codici, token e segreti annidati restano esclusi da prompt, conversazioni,
  audit e tool trace.

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
