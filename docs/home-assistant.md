# Integrazione Home Assistant

Home Assistant invia il trigger e il contesto utile; House Brain legge gli stati correnti e decide entro i limiti della policy.

```yaml
rest_command:
  house_brain_event:
    url: !secret house_brain_events_url
    method: POST
    headers:
      X-API-Key: !secret house_brain_api_key
    content_type: application/json
    timeout: 150
    payload: >-
      {
        "event_type": {{ event_type | tojson }},
        "source": "home_assistant",
        "mode": {{ event_mode | default("simulate") | tojson }},
        "instruction": {{ instruction | tojson }},
        "context": {{ event_context | default({}) | tojson }}
      }
```

```yaml
house_brain_events_url: "http://IP_SERVER_IOT:8090/agent/events"
house_brain_api_key: "valore-della-chiave"
```

Da Home Assistant, `localhost` indica Home Assistant stesso: usa l'indirizzo del server House Brain.

## Regole pratiche

- usa un `event_type` stabile e presente nella policy;
- usa `simulate` durante il collaudo;
- passa nel contesto il valore che ha causato il trigger;
- scrivi un'istruzione orientata all'obiettivo;
- non duplicare nell'automazione tutta la decisione;
- autorizza solo le entità necessarie.

Esempio di istruzione:

```text
Valuta sole, ora, presenza e stato corrente della casa. Sistema i dispositivi
pertinenti secondo le preferenze memorizzate, senza azioni non necessarie.
```

## Collaudo

1. prova `observe`;
2. passa a `simulate` e controlla la `tool_trace`;
3. restringi la policy;
4. abilita temporaneamente il kill switch;
5. prova `execute` su un'azione reversibile;
6. disabilita il kill switch finché il comportamento non è stabile.

Se il testo del modello contraddice la `tool_trace`, considera vera la traccia.

L'esempio completo della ventola garage è in `examples/home_assistant/`.
