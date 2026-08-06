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

## Azioni attuali

Il motore oggi consente:

- `light`: `turn_on`, `turn_off`, `toggle`;
- `switch`: `turn_on`, `turn_off`, `toggle`;
- `fan`: `turn_on`, `turn_off`, `toggle`, `set_percentage`;
- `cover`: `open_cover`, `close_cover`, `stop_cover`, `set_cover_position`;
- `climate`: `turn_on`, `turn_off`, `set_temperature`, `set_hvac_mode`.

`alarm_control_panel`, `automation`, `button`, `lock`, `scene` e `script` sono ancora bloccati dal codice anche se inseriti nella policy.

Ogni campo `data` deve avere un vincolo. Usa `allowed` per valori discreti oppure `min`/`max` per numeri. Il dominio dell'entità deve coincidere con quello del servizio.

Il futuro motore generico eliminerà l'elenco rigido dei domini, ma continuerà a negare qualunque azione non esplicitamente autorizzata dalla policy.
