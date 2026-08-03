# Home Assistant event bridge

This example connects Home Assistant to the authenticated House Brain event API.
The first rollout is intentionally limited to garage fan simulations.

## 1. House Brain configuration

Keep execution disabled. Add the garage events to the local
`autonomy.yaml`; each remains simulation-only:

```yaml
version: 1

events:
  garage_humidity_high:
    modes: [simulate]
    max_actions: 1
    actions:
      switch.turn_on:
        entities: [switch.ventola]

  garage_humidity_low:
    modes: [simulate]
    max_actions: 1
    actions:
      switch.turn_off:
        entities: [switch.ventola]

  garage_night_window_ended:
    modes: [simulate]
    max_actions: 1
    actions:
      switch.turn_off:
        entities: [switch.ventola]
```

Retain any other event blocks already present in the file. Keep the global
kill switch in `.env`:

```dotenv
AUTONOMY_POLICY_PATH=/app/autonomy.yaml
AUTONOMOUS_EXECUTION_ENABLED=false
```

Restart House Brain after changing the YAML file:

```bash
docker compose config --quiet
docker compose up -d --force-recreate
```

## 2. Home Assistant secrets

Copy the two entries from `secrets.yaml.example` into the real Home Assistant
`secrets.yaml`.

`house_brain_events_url` must use the IP address or hostname of the server
running House Brain. Do not use `localhost`: from Home Assistant that points
back to Home Assistant itself.

Never commit or paste either real secret.

## 3. Install the package

Copy `packages/house_brain_garage_fan.yaml` to:

```text
/config/packages/house_brain_garage_fan.yaml
```

If packages are not already enabled, merge this into the existing
`homeassistant:` section of `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Do not create a second `homeassistant:` key.

Check the Home Assistant configuration and restart Home Assistant. The package
creates:

- `rest_command.house_brain_event`
- automation `House Brain - Ventola garage in simulazione`

The REST timeout is 150 seconds because the local Ollama request can take longer
than Home Assistant's default 10 seconds.

## 4. Behavior

The automation sends only `mode: simulate`:

- above 80% humidity between 20:00 and 06:00: consider fan start
- below 60% humidity: consider fan stop
- at 06:00: consider fan stop at the end of the night window

House Brain still reads the physical entity `switch.ventola`; it does not use
the state of the old Home Assistant automation as the fan state.

## 5. Manual bridge test

From Home Assistant Developer Tools, call
`rest_command.house_brain_event` with:

```yaml
event_type: garage_humidity_high
event_mode: simulate
instruction: >-
  Controlla la ventola del garage. Se è spenta, simula l'accensione.
event_context:
  test: true
  humidity: 85
```

Then inspect the House Brain audit log:

```bash
curl -sS http://localhost:8090/events \
  -H "X-API-Key: $HOUSE_BRAIN_API_KEY" | python3 -m json.tool
```

Do not switch this package to `execute` during the first observation period.
