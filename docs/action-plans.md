# Piani d'azione con approvazione

I piani d'azione separano la decisione dall'esecuzione reale. House Brain può
analizzare una richiesta in linguaggio naturale e usare i normali strumenti in
modalità `simulate`; soltanto le azioni simulate con successo e presenti nella
`tool_trace` autorevole diventano una proposta persistente.

## Flusso

1. La richiesta viene ripulita da eventuali codici prima di raggiungere il
   modello.
2. L'agente opera in `simulate`, con la stessa policy e lo stesso catalogo dei
   servizi usati da `execute`.
3. Il server salva entity ID, servizio, parametri oscurati, motivazione, stato
   iniziale e impronta degli attributi correnti.
4. Il piano resta `proposed` per un intervallo limitato, predefinito a cinque
   minuti.
5. Al momento dell'approvazione il server acquisisce il piano in modo atomico,
   controlla il kill switch, rilegge ogni entità e ripete tutte le validazioni.
6. Se uno stato o un attributo iniziale è cambiato, il piano diventa
   `invalidated` e nessuna azione viene chiamata.
7. Un piano può essere eseguito una sola volta. Un secondo tentativo riceve un
   conflitto e non ripete le chiamate Home Assistant.

Gli stati finali possibili sono `executed`, `rejected`, `expired`,
`invalidated` e `failed`. Se un piano con più azioni si interrompe dopo una
chiamata riuscita, i risultati parziali confermati restano registrati.

## Interfacce

La pagina `/plans` permette di creare, esaminare, approvare o rifiutare una
proposta. La stessa sezione è disponibile nel pannello amministrativo nativo di
Home Assistant. I codici policy e Home Assistant sono campi password effimeri:
vengono inoltrati come header e non sono salvati nel piano o nel browser.

Le API autenticate disponibili sono:

- `POST /action-plans/from-request` per una proposta da linguaggio naturale;
- `POST /action-plans` per una proposta strutturata;
- `GET /action-plans` e `GET /action-plans/{plan_id}` per la consultazione;
- `POST /action-plans/{plan_id}/approve` per la nuova validazione e
  l'esecuzione;
- `POST /action-plans/{plan_id}/reject` per il rifiuto esplicito.

## Garanzie e limiti

- il testo finale del modello non viene interpretato come azione;
- aree, dispositivi e nomi aiutano la selezione ma non concedono permessi;
- i codici non compaiono nel database dei piani, nelle risposte o nella trace;
- `AUTONOMOUS_EXECUTION_ENABLED=true` è necessario soltanto all'approvazione;
- un piano scaduto o modificato non può essere riattivato: va simulato di
  nuovo;
- il piano non sostituisce la normale modalità `execute`, ma offre un percorso
  esplicito per le richieste che richiedono revisione umana.

