# Roadmap

Questa pagina raccoglie le priorità ufficiali di House Brain. Non è una
promessa di date: ogni elemento entra in una release solo dopo test automatici,
collaudo reale e approvazione esplicita.

Ultimo aggiornamento: 24 agosto 2026.

## Principi invarianti

Ogni sviluppo deve preservare questi vincoli:

- nessuna entità è visibile per impostazione predefinita;
- `entities.visible` abilita soltanto la lettura e `entities.include` abilita
  lettura e controllo;
- policy, API, chat, eventi e MCP applicano le stesse regole globali;
- servizi, campi e capacità provengono dinamicamente da Home Assistant;
- nessun dominio, dispositivo, nome o lingua viene trattato con eccezioni
  hardcoded;
- `simulate` valida come `execute`, mentre `execute` richiede anche il kill
  switch globale;
- una risposta del modello non può prevalere sui risultati degli strumenti;
- codici, token e ragionamento interno non entrano in risposte, audit o
  cronologia;
- ogni release mantiene un solo mount persistente, `config/`, e deve essere
  ripristinabile da backup.

## Stato pubblicato

Le versioni da `v0.1.0` a `v0.1.4` sono state pubblicate. Sono disponibili il
motore di azioni generico, la visibilità default-deny, la memoria persistente,
l'audit autorevole, le interfacce web, MCP in sola lettura per Home Assistant,
il provider Ollama e il provider OpenAI-compatible.

## Prossima release beta

La prossima release prevista è `v0.1.5`. Prima del tag devono essere completati
e documentati i seguenti controlli:

- [ ] collaudo prolungato di chat ed eventi con più chiamate consecutive agli
  strumenti;
- [ ] collaudo finale di `observe`, `simulate` ed `execute` controllato;
- [ ] verifica di codici policy, codici richiesti da Home Assistant, kill
  switch e rifiuti obbligatori;
- [ ] verifica della visibilità default-deny da API, chat, eventi e MCP;
- [ ] verifica prolungata del recupero delle risposte vuote di Ollama, senza
  esposizione del ragionamento interno;
- [ ] collaudo del provider OpenAI-compatible ufficiale e locale, inclusi URL
  personalizzato, modello assente e modello non caricato;
- [ ] verifica responsive e autenticazione di Chat, Autonomy, Memories, Audit
  e Log;
- [ ] collaudo dell'immagine GHCR con `PUID`/`PGID`, riavvio, rebuild e
  filesystem persistente;
- [ ] backup e ripristino completo di policy, database, conversazioni,
  memorie, audit e backup policy;
- [x] passaggio delle action di checkout, Python e uv a versioni basate su
  Node.js 24;
- [ ] verifica delle action Docker su un build multiarch senza pubblicazione;
- [ ] collaudo reale della custom integration con Assist, AI Task, observe,
  simulate, execute negato e riconfigurazione della chiave;
- [ ] aggiornamento di manuale, changelog e checklist della release;
- [ ] creazione del tag e della release soltanto dopo approvazione esplicita.

## Blocchi di lavoro in corso

La branch `feature/home-assistant-context-engine` introduce la prima versione
del contesto relazionale:

- [x] lettura autenticata dei registri di aree, dispositivi ed entità;
- [x] vista paginata filtrata dalla policy default-deny;
- [x] selezione per area, dominio e ricerca normalizzata;
- [x] nomi Autonomy autorevoli e motivi di selezione espliciti;
- [x] tool agente e API autenticata basati sullo stesso motore;
- [x] area e dispositivo visibili nelle interfacce Autonomy.

La branch successiva `feature/action-plan-approval` sarà impilata sulla prima
e realizzerà anteprima, approvazione, scadenza e rivalidazione dei piani.

## Priorità successive

### 1. Diagnostica guidata — prima versione completata

- [x] pagina di stato unica per Home Assistant, provider LLM, database, policy,
  backup e capacità del modello;
- [x] errori operativi con causa, componente coinvolto e controllo suggerito;
- [x] esportazione di un rapporto diagnostico già oscurato dai segreti.

### 2. Anteprima e approvazione delle azioni — prima versione implementata

- [x] mostrare prima dell'esecuzione entità, stato letto, servizio, parametri e
  motivazione;
- [x] consentire l'approvazione esplicita di un piano senza aggirare policy, codici
  o kill switch;
- [x] invalidare l'approvazione se lo stato di partenza cambia;
- [x] non introdurre scorciatoie basate su domini ritenuti arbitrariamente sicuri.

### 3. Backup e ripristino dalla GUI

- creare e scaricare un backup coerente dell'intera directory persistente;
- verificare l'integrità SQLite prima del download e dopo il ripristino;
- mostrare chiaramente cosa verrà sostituito e conservare un backup
  pre-ripristino recuperabile;
- non eliminare automaticamente volumi o backup storici.

### 4. Memoria più controllabile — ciclo di vita completato

- [x] provenienza e data dell'ultima conferma di ogni memoria;
- [x] scadenza opzionale per informazioni temporanee;
- [x] collegamenti visibili alle entità citate e verifica del loro stato corrente;
- [x] importazione ed esportazione senza includere memorie eliminate per errore.

### 5. Modelli senza tool nativi

- [x] rilevare esplicitamente le capacità del modello configurato;
- [x] offrire una modalità conversazionale in sola risposta quando i tool non sono
  supportati;
- valutare un protocollo strutturato server-side soltanto se può essere
  validato con la stessa sicurezza dei tool nativi;
- non consentire azioni reali interpretando testo libero o parole chiave.

### 6. Contesto Home Assistant più selettivo — prima versione implementata

- [x] usare aree, dispositivi e relazioni del registro Home Assistant per
  ridurre il numero di entità presentate al modello;
- [ ] permettere viste o gruppi logici configurabili senza duplicare la policy
  di autorizzazione;
- [x] mantenere autorevoli entity ID, nomi configurati e risoluzione
  server-side;
- [x] esporre paginazione, controllabilità e motivi di selezione senza
  trasformare le relazioni in autorizzazioni.

### 7. Audit operativo

- [x] filtri combinabili ed esportazione JSON;
- [x] indicatori riassuntivi;
- [x] confronto chiaro fra azione richiesta, validazione, chiamata Home Assistant
  ed esito;
- nessuna funzione di “ripeti azione” che salti una nuova validazione completa.

### 8. Distribuzione più semplice

- procedura guidata di prima configurazione senza memorizzare segreti nel
  browser oltre la sessione necessaria;
- valutazione di un add-on Home Assistant mantenendo disponibile il container
  Docker generico;
- controllo aggiornamenti e migrazioni con backup preventivo e rollback
  documentato.

### 9. Integrazione nativa Home Assistant — prima versione implementata

- [x] config flow autenticato con verifica URL, chiave e duplicati;
- [x] entità `conversation.*` con modalità observe, simulate o execute;
- [x] entità `ai_task.*` con modalità observe, simulate o execute e gli stessi
  controlli server-side;
- [x] diagnostica priva della chiave e flussi di reautenticazione e
  riconfigurazione;
- [x] pacchetti lingua e installazione manuale documentata;
- [ ] collaudo su Home Assistant reale e installazione HACS dalla release;
- [ ] valutazione allegati soltanto dopo un trasporto sicuro e limitato.

## Idee da valutare dopo la stabilizzazione

- notifiche tramite servizi disponibili nel catalogo Home Assistant;
- metriche locali su latenza, uso degli strumenti e tasso di recupero dei
  provider, senza registrare prompt o segreti;
- importazione della documentazione versionata nella GitHub Wiki;
- azioni MCP soltanto con un modello di autorizzazione esplicito e almeno
  equivalente a quello di chat, eventi e API;
- ulteriori provider LLM dietro un'interfaccia comune e test di conformità.

## Fuori ambito finché non esiste una garanzia equivalente

- accesso indiscriminato a tutte le entità Home Assistant;
- esecuzione di azioni dedotte da testo libero per modelli senza tool;
- liste hardcoded di domini o dispositivi “sicuri” o “sensibili”;
- esposizione del socket Docker all'applicazione web;
- eliminazione automatica di configurazioni, backup o vecchi volumi;
- dichiarazioni di successo non confermate da un risultato positivo dello
  strumento autorevole.

## Come aggiornare questa roadmap

Ogni modifica deve essere proposta con una PR circoscritta. Quando un elemento
è completato, la stessa PR che lo consegna aggiorna la relativa voce e il
changelog. Una funzione non viene considerata completata soltanto perché il
codice esiste: servono test, documentazione e collaudo reale quando applicabile.

