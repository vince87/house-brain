# Policy di autonomia

La policy è fail-fast: errori di sintassi, campi sconosciuti o autorizzazioni incoerenti impediscono l'avvio.

```yaml
version: 1

visibility:
  exclude_entities:
    - light.luci
    - cover.tapparelle
  exclude_patterns:
    - sensor.*_diagnostic
    - sensor.*_last_seen

events:
  periodic_house_check:
    modes: [observe, simulate]
    max_actions: 10
    actions:
      cover.set_cover_position:
        entities:
          - cover.tapparella_cucina_due
        parameters:
          position:
            allowed: [0, 20, 100]
```

## Visibilità

Un'entità nascosta non compare in liste o ricerche, non è leggibile, non espone Recorder/state-before, viene rimossa dagli attributi annidati e non può essere comandata nemmeno in simulazione. Non può essere anche autorizzata da un evento.

Usa ID esatti per casi singoli e pattern shell solo per famiglie chiaramente tecniche.

## Modalità

- `observe`: lettura e decisione;
- `simulate`: piano validato senza chiamate reali;
- `execute`: azioni reali autorizzate anche dal kill switch.

`max_actions` è cumulativo e va da 1 a 20.

## Azioni generiche

Negli eventi autonomi qualunque `domain.service` sintatticamente valido è
rappresentabile. Questo include, per esempio, `media_player.turn_off`,
`button.press`, `select.select_option`, `lock.lock`,
`alarm_control_panel.alarm_arm_away`, `siren.turn_on`, `valve.close_valve`,
`script.turn_on` e `automation.trigger`.

La presenza nella policy è obbligatoria e deve indicare entità esatte. Il dominio
dell'entità deve coincidere con il dominio del servizio. `toggle` resta vietato
agli eventi autonomi perché non esprime uno stato finale deterministico.

```yaml
actions:
  media_player.turn_off:
    entities:
      - media_player.televisore_sala

  button.press:
    entities:
      - button.qualcosa

  select.select_option:
    entities:
      - select.modalita
    parameters:
      option:
        allowed:
          - Auto
          - Manuale
```

Ogni campo inviato in `data` deve avere un vincolo. Usa `allowed` per valori
discreti oppure `min`/`max` per numeri. I valori generici sono limitati a
scalari: stringhe, numeri e booleani. Strutture annidate non sono accettate.

L'endpoint diretto `/actions` e le azioni della chat non associate a un evento
mantengono intenzionalmente il perimetro storico di `light`, `switch`, `fan`,
`cover` e `climate`. Una sola API key non concede quindi accesso generico ai
servizi Home Assistant.

I domini ad alto rischio sono tecnicamente rappresentabili, ma restano
inutilizzabili finché non vengono autorizzati esplicitamente. Prima di abilitarli
in `execute` sono raccomandati eventi dedicati, budget minimo e interlock
aggiuntivi.
