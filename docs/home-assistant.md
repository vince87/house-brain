# Integrazione Home Assistant

Home Assistant deve normalmente inviare soltanto la modalità e l'istruzione.
House Brain aggiunge automaticamente l'origine, assegna un tipo generico
all'evento e legge gli stati correnti tramite i propri strumenti.

## REST command essenziale

Il blocco `rest_command:` va inserito nel file `configuration.yaml` di Home
Assistant. Se usi i package, può invece essere inserito in un file package già
incluso da `configuration.yaml`.


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
        "mode": {{ event_mode | default("simulate") | tojson }},
        "instruction": {{ instruction | tojson }}
      }
```

In `secrets.yaml`:

```yaml
house_brain_events_url: "http://IP_SERVER_IOT:8090/agent/events"
house_brain_api_key: "valore-della-chiave"
```

Da Home Assistant, `localhost` indica Home Assistant stesso: usa l'indirizzo
del server House Brain.

Dopo aver aggiunto o modificato il blocco, controlla la configurazione e riavvia
Home Assistant. Ricreare il container House Brain non ricarica il
`rest_command` di Home Assistant.

## Chiamare il REST command

```yaml
- action: rest_command.house_brain_event
  data:
    event_mode: simulate
    instruction: >-
      Controlla switch.example_fan_relay. Se è acceso, simula lo spegnimento.
```

Questi sono gli unici due valori necessari:

- `event_mode`: `observe`, `simulate` oppure `execute`;
- `instruction`: l'obiettivo in linguaggio naturale.

Se `event_mode` viene omesso, il template usa `simulate`.

## Campi avanzati dell'API

L'endpoint accetta ancora tre campi facoltativi per integrazioni che ne hanno
davvero bisogno:

| Campo | Predefinito | Uso |
|---|---|---|
| `event_type` | `home_assistant_event` | etichetta tecnica nell'audit |
| `source` | `home_assistant` | origine tecnica nell'audit |
| `context` | `{}` | dati strutturati aggiuntivi per il modello |

Non servono nel normale `rest_command` e non concedono autorizzazioni. La
policy dipende sempre dalle entità visibili o controllabili e dagli eventuali
codici.

Se un'integrazione deve inviare un contesto strutturato, può chiamare
direttamente l'API con un payload esteso:

```json
{
  "mode": "simulate",
  "instruction": "Valuta se attivare la ventilazione.",
  "context": {
    "humidity": 84,
    "threshold": 80
  }
}
```

Nelle automazioni normali è preferibile lasciare che House Brain legga lo stato
corrente da Home Assistant, invece di duplicarlo nel payload.

## Entità nascoste

House Brain legge il registro entità tramite l'API WebSocket ufficiale di Home
Assistant. Se un'entità ha il campo `hidden_by` valorizzato, viene trattata
come inesistente: non compare nelle ricerche, nella chat, nel configuratore o
nelle letture MCP e non può essere usata da `/actions` o dagli eventi. Questo
controllo si aggiunge alla policy default-deny: un'entità nascosta resta
inaccessibile anche se compare accidentalmente in `visible` o `include`.

La cache usa lo stesso intervallo configurato per il catalogo servizi. Se il
registro non è raggiungibile, House Brain rifiuta l'operazione invece di rendere
accidentalmente visibili le entità nascoste.

## Regole pratiche

- usa `simulate` durante il collaudo;
- scrivi un'istruzione orientata all'obiettivo;
- indica l'entity ID quando vuoi un bersaglio esatto;
- non duplicare nell'automazione tutta la decisione;
- autorizza solo le entità necessarie in `autonomy.yaml`;
- controlla sempre la `tool_trace`.

## Collaudo

1. prova `observe`;
2. passa a `simulate` e controlla la `tool_trace`;
3. restringi la policy;
4. abilita temporaneamente il kill switch;
5. prova `execute` su un'azione reversibile;
6. disabilita il kill switch finché il comportamento non è stabile.

Se il testo del modello contraddice la `tool_trace`, considera vera la traccia.

L'esempio completo è in `examples/home_assistant/`.
