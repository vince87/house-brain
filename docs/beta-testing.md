# Checklist di collaudo beta

Questa checklist serve prima di promuovere una beta a release stabile. Usa
soltanto entità di prova scelte dall'utente e nomi generici nella
documentazione dei risultati. I comandi, gli esiti attesi e l'ordine sicuro
sono nella [procedura di collaudo beta eseguibile](beta-validation-runbook.md).

## Preparazione

- [ ] È disponibile un backup verificato dell'intera directory `config/`.
- [ ] Il database supera `PRAGMA integrity_check`.
- [ ] `AUTONOMOUS_EXECUTION_ENABLED` è `false` all'inizio.
- [ ] Le entità di prova sono elencate esplicitamente in `entities.include`.
- [ ] Almeno un'entità è esclusa e almeno una è nascosta nel registro HA.
- [ ] La pagina `/diagnostics` riporta Home Assistant e Ollama disponibili.

## Observe

- [ ] L'evento legge stati e cronologia senza chiamare servizi.
- [ ] Nessuna risposta afferma che sia stata eseguita un'azione.
- [ ] L'audit mostra modalità, istruzione, risposta e strumenti usati.
- [ ] Entità escluse o nascoste non compaiono nei risultati.

## Simulate

Per ogni dominio realmente disponibile nel sistema, prova un servizio
supportato. Esempi possibili: `light`, `switch`, `cover`, `lock`,
`alarm_control_panel`, `siren`, `valve`, `button`, `script`,
`automation`, `media_player` e `select`.

- [ ] Il servizio proviene dal catalogo dinamico di Home Assistant.
- [ ] Dominio del servizio ed entità coincidono.
- [ ] I campi richiesti e i valori ammessi vengono validati.
- [ ] Un servizio inesistente viene rifiutato.
- [ ] Un parametro richiesto mancante viene rifiutato.
- [ ] Un entity ID inesistente non viene sostituito.
- [ ] Un nome ambiguo richiede chiarimento in chat e viene rifiutato negli eventi.
- [ ] Un'entità non inclusa non è comandabile.
- [ ] Un'entità esclusa o nascosta è invisibile e non comandabile.
- [ ] Un codice di policy mancante o errato viene rifiutato senza essere rivelato.
- [ ] Un codice richiesto da HA viene inoltrato ma non appare nella tool trace.
- [ ] Nessuno stato reale del dispositivo cambia.

## Execute controllato

Abilita il kill switch soltanto durante questa sezione e usa dispositivi per i
quali un comando reale sia sicuro.

- [ ] `AUTONOMOUS_EXECUTION_ENABLED` è stato impostato a `true` e il container ricreato.
- [ ] Una singola azione sicura viene eseguita e confermata da Home Assistant.
- [ ] La risposta finale dice `eseguita`, non `simulata`.
- [ ] La risposta deriva soltanto dall'ultimo piano concluso con successo.
- [ ] Tentativi rifiutati o incompleti non vengono presentati come azioni riuscite.
- [ ] In caso di risposta finale vuota di Ollama, resta disponibile il riepilogo autorevole delle azioni già riuscite.
- [ ] Un errore di Home Assistant rimane un errore e non viene trasformato in successo.
- [ ] Il kill switch viene riportato a `false` dopo la prova e il container ricreato.

## Persistenza e interfacce

- [ ] Memorie, cestino, conversazioni e audit sopravvivono al riavvio.
- [ ] Memorie possono essere aggiunte, modificate, eliminate e ripristinate dalla GUI.
- [ ] Il configuratore salva la policy e crea un backup.
- [ ] La GUI audit filtra observe, simulate ed execute e mostra la tool trace completa.
- [ ] MCP può leggere entità e gestire memorie entro le capacità previste.
- [ ] Un rebuild Docker mantiene tutti i dati della directory `config/`.
- [ ] Un ripristino di prova supera tutti i controlli della guida backup.

## Esito

Annota versione dell'immagine o commit, data, domini provati e anomalie senza
registrare token, chiavi, codici o nomi reali dei dispositivi. La pubblicazione
e il tag richiedono sempre consenso esplicito dopo il collaudo.
