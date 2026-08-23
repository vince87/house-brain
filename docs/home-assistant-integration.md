# Integrazione nativa Home Assistant

House Brain può essere installato come custom integration locale e crea due
entità native:

- `conversation.*`, selezionabile come agente nelle pipeline Assist;
- `ai_task.*`, utilizzabile con l'azione `ai_task.generate_data`.

L'integrazione richiede Home Assistant 2026.8.0 o successivo. House Brain resta
un servizio separato: la custom integration inoltra richieste autenticate e non
duplica la policy, i codici, la validazione dei servizi o il kill switch.

## Installazione manuale

1. Copia la directory `custom_components/house_brain` del repository in:

   ```text
   /config/custom_components/house_brain
   ```

2. Riavvia Home Assistant.
3. Apri **Impostazioni > Dispositivi e servizi > Aggiungi integrazione**.
4. Cerca **House Brain**.
5. Inserisci l'URL raggiungibile da Home Assistant e la chiave API.

Da Home Assistant, `localhost` identifica Home Assistant stesso. Se House Brain
si trova su un altro server, usa il suo indirizzo IP o nome DNS, per esempio
`http://192.168.1.20:8090`.

L'installazione tramite repository personalizzato HACS sarà supportata dalla
release che include questa directory. La copia manuale resta sempre valida.

## Pannello nella barra laterale

Dopo aver aggiunto l'integrazione, Home Assistant registra automaticamente la
voce **House Brain** nella barra laterale per gli amministratori. Il pannello
riunisce in un'unica schermata:

- Chat;
- Memorie;
- Audit;
- Autonomia;
- Log;
- Diagnostica.

Le schede usano l'aspetto chiaro o scuro del browser e le variabili visive di
Home Assistant. Le pagine restano servite direttamente da House Brain: il
pannello non duplica API, policy o dati.

La chiave API configurata nell'integrazione non viene inserita nel pannello.
Al primo accesso a una pagina protetta, House Brain richiede la chiave e la
conserva soltanto nel `sessionStorage` della scheda del browser. La voce
laterale è riservata agli amministratori perché include configurazione, audit e
log operativi.

Per impedire che le interfacce siano incorporate da siti arbitrari, House Brain
autorizza come origine del pannello soltanto l'origine configurata in
`HOME_ASSISTANT_URL` (schema, host e porta). L'indirizzo usato dal browser per
aprire Home Assistant deve quindi coincidere con tale origine. In caso
contrario, usa **Apri in una nuova scheda** oppure allinea l'URL configurato.

La voce viene rimossa automaticamente se l'integrazione viene scaricata o
eliminata.

## Modalità dell'agente

Il configuratore richiede la modalità condivisa dalle entità `conversation.*` e
`ai_task.*`:

| Modalità | Comportamento |
|---|---|
| `observe` | legge e risponde, senza azioni |
| `simulate` | valida e simula tramite lo stesso motore di execute |
| `execute` | può eseguire soltanto azioni approvate dal server |

`execute` non abilita autonomamente le azioni. Restano obbligatori
`AUTONOMOUS_EXECUTION_ENABLED`, entità controllabile in `autonomy.yaml`, servizio
Home Assistant valido, parametri corretti ed eventuali codici. Un codice scritto
nella richiesta viene estratto e oscurato dal server come negli altri canali.

L'entità `conversation.*` dichiara a Home Assistant la capacità di controllo
soltanto quando è configurata in `execute`. Anche `ai_task.*` usa la stessa
modalità: una task avviata da un'automazione può quindi leggere, simulare o
eseguire secondo la configurazione corrente.

## Configurare Assist

Dopo l'installazione:

1. apri le impostazioni degli assistenti vocali;
2. crea o modifica una pipeline Assist;
3. seleziona l'entità House Brain come agente di conversazione;
4. prova prima una lettura e poi, se previsto, una simulazione.

La risposta usa la lingua configurata dal server con `HOUSE_BRAIN_LANGUAGE`.
House Brain mantiene la conversazione nella propria base SQLite usando
l'identificatore restituito a Home Assistant.

## Usare AI Task

`ai_task.*` usa la modalità configurata per l'integrazione:

- in `observe` può leggere entità visibili, usare memorie e generare dati;
- in `simulate` valida e simula le azioni richieste;
- in `execute` può eseguire azioni reali, sempre attraverso policy, codici,
  catalogo dei servizi e kill switch di House Brain.

Esempio di automazione da avviare manualmente con **Esegui azioni**:

```yaml
alias: "Test House Brain - controllo generale"
description: "Esegue un controllo generale tramite AI Task"
triggers:
  - trigger: event
    event_type: house_brain_ai_task_test
conditions: []
actions:
  - action: ai_task.generate_data
    data:
      entity_id: ai_task.house_brain
      task_name: "Controllo generale della casa"
      instructions: >-
        Controlla lo stato generale della casa, inclusi presenza, sole,
        temperature, clima, tapparelle, luci, TV e altri dispositivi pertinenti.
        Considera l'ora, la stagione e le preferenze memorizzate. Prima di
        pianificare eventuali interventi, recupera le memorie pertinenti e
        verifica gli stati attuali in Home Assistant. Esegui soltanto azioni
        necessarie, motivate dai dati letti e coerenti con le preferenze
        memorizzate. Non modificare dispositivi già nello stato desiderato e non
        contraddire una preferenza applicabile. Genera un resoconto basato
        esclusivamente sulle letture e sui risultati confermati dagli strumenti.
    response_variable: house_brain_result

  - action: persistent_notification.create
    data:
      title: "House Brain - controllo generale"
      message: "{{ house_brain_result.data }}"
      notification_id: house_brain_ai_task_test
mode: single
```

L'entity ID definitivo dipende dal nome assegnato da Home Assistant: selezionalo
dall'interfaccia invece di copiarlo dall'esempio. Il trigger evento evita
esecuzioni automatiche durante il collaudo; il pulsante **Esegui azioni** ignora
il trigger e avvia immediatamente la sequenza.

Una struttura opzionale viene convertita in schema, inviata come vincolo e
validata nuovamente dentro Home Assistant. Una risposta non JSON o non conforme
fa fallire l'azione invece di restituire dati inventati.

Gli allegati e la generazione di immagini non sono dichiarati come supportati in
questa prima versione.

## Diagnostica e sicurezza

La voce **Scarica diagnostica** dell'integrazione include soltanto:

- URL configurato;
- modalità della conversazione;
- raggiungibilità;
- versione remota.

La chiave API non viene inclusa. Una risposta `401` avvia la riconfigurazione
della chiave; errori di rete mantengono l'integrazione in attesa senza perdere
la configurazione.

Per il collaudo controlla anche `/audit` su House Brain. Le richieste AI Task compaiono come `home_assistant_ai_task` nella modalità
configurata e includono la `tool_trace` autorevole.

## Aggiornamento e rimozione

Per aggiornare manualmente, sostituisci soltanto la directory
`custom_components/house_brain` e riavvia Home Assistant. La rimozione della
config entry elimina le entità Home Assistant ma non cancella conversazioni,
memorie o audit conservati da House Brain.

Il precedente `rest_command` resta disponibile come ponte essenziale e come
fallback, ma non è necessario per `conversation.*` o `ai_task.*`.
