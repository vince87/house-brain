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

## Modalità della conversazione

Il configuratore richiede la modalità massima dell'entità `conversation.*`:

| Modalità | Comportamento |
|---|---|
| `observe` | legge e risponde, senza azioni |
| `simulate` | valida e simula tramite lo stesso motore di execute |
| `execute` | può eseguire soltanto azioni approvate dal server |

`execute` non abilita autonomamente le azioni. Restano obbligatori
`AUTONOMOUS_EXECUTION_ENABLED`, entità controllabile in `autonomy.yaml`, servizio
Home Assistant valido, parametri corretti ed eventuali codici. Un codice scritto
nella richiesta viene estratto e oscurato dal server come negli altri canali.

L'entità dichiara a Home Assistant la capacità di controllo soltanto quando è
configurata in `execute`.

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

`ai_task.*` è intenzionalmente bloccata in `observe`: può leggere le entità
visibili, usare memorie e generare dati, ma non controlla dispositivi, anche se
la conversazione è configurata in `execute`.

Esempio di automazione con risposta testuale:

```yaml
actions:
  - action: ai_task.generate_data
    data:
      entity_id: ai_task.house_brain
      task_name: "Riepilogo giornaliero"
      instructions: >-
        Controlla le entità pertinenti e genera un breve riepilogo della casa.
    response_variable: house_brain_result

  - action: notify.persistent_notification
    data:
      message: "{{ house_brain_result.data }}"
```

L'entity ID definitivo dipende dal nome assegnato da Home Assistant: selezionalo
dall'interfaccia invece di copiarlo dall'esempio.

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

Per il collaudo controlla anche `/audit` su House Brain. Le richieste AI Task
compaiono come `home_assistant_ai_task` in modalità `observe`.

## Aggiornamento e rimozione

Per aggiornare manualmente, sostituisci soltanto la directory
`custom_components/house_brain` e riavvia Home Assistant. La rimozione della
config entry elimina le entità Home Assistant ma non cancella conversazioni,
memorie o audit conservati da House Brain.

Il precedente `rest_command` resta disponibile come ponte essenziale e come
fallback, ma non è necessario per `conversation.*` o `ai_task.*`.
