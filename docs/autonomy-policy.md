# Policy di autonomia

La policy versione 2 è unica per chat, eventi e API. È fail-fast: errori,
campi sconosciuti e conflitti impediscono l'avvio.

```yaml
version: 2

entities:
  include:
    - light.sala_uno
    - media_player.tablet_p1
    - entity_id: lock.aqara_smart_lock_u200_lite
      code: "1234"

  exclude:
    - light.luci
    - cover.tapparelle
    - sensor.*_diagnostic
```

## Regole

- `include`: entità visibile e controllabile da ogni canale autenticato;
- `exclude`: entità invisibile, illeggibile e non controllabile;
- non elencata: visibile ma in sola lettura.

In `exclude` sono ammessi entity ID esatti e pattern shell. In `include` sono
ammessi solo entity ID esatti. La stessa entità non può comparire in entrambe
le liste.

Non esistono più policy separate per evento, `chat_command`, elenchi di servizi,
`modes`, `max_actions`, parametri o blocchi `authorization`.

## Azioni

Per un'entità inclusa il motore può rappresentare genericamente i servizi Home
Assistant del dominio corrispondente. Per esempio una entità `media_player.*`
può ricevere un servizio `media_player.*`, ma non un servizio `switch.*`.
Identificatori non validi, domini incoerenti, dati annidati e valori numerici
non finiti vengono respinti. Negli eventi automatici `toggle` resta vietato.

`observe` non esegue azioni, `simulate` non chiama Home Assistant ed `execute`
richiede sempre `AUTONOMOUS_EXECUTION_ENABLED=true`.

## Codice per entità

Il codice è facoltativo e si dichiara direttamente accanto all'entità:

```yaml
- entity_id: lock.aqara_smart_lock_u200_lite
  code: "1234"
```

Se configurato, viene richiesto per ogni azione su quell'entità, qualunque sia
il canale. In chat e nelle istruzioni evento usa:

```text
Sblocca Portoncino Casa, codice: 1234
```

Per `POST /actions` usa l'header `X-Authorization-Code`. Il server rimuove il
codice prima di Ollama, conversazioni, eventi persistenti, log e `tool_trace`.
I codici accettano da 4 a 64 lettere, numeri, trattini e underscore.

House Brain non classifica i servizi come sensibili: uno `switch` potrebbe
aprire un cancello e il server non può dedurlo dal dominio. La decisione è
sempre dell'utente: se una entità ha `code`, ogni suo servizio richiede quel
codice; senza `code`, nessun suo servizio lo richiede.

`autonomy.yaml` contiene segreti locali: non commetterlo e limita i permessi
sul filesystem.
