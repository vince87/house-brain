# Collaudo beta eseguibile

Questa guida trasforma la [checklist beta](beta-testing.md) in prove ripetibili.
Esegui una sezione alla volta e annota l'esito. Non inserire nel resoconto token,
chiavi, codici o nomi reali dei dispositivi.

I comandi sono pensati per il container di sviluppo nella directory:

```text
/docker/appdata/house-brain/house-brain
```

## Variabili di prova

Dopo avere scelto entità sicure nella propria installazione, imposta valori
temporanei nella shell. Gli esempi seguenti non devono essere copiati nella
policy reale:

```bash
cd /docker/appdata/house-brain/house-brain

set -a
source .env
set +a

export HB_URL="http://localhost:8090"
export HB_INCLUDED_ENTITY="light.example_room"
export HB_INCLUDED_DOMAIN="light"
export HB_SAFE_SERVICE="turn_off"
export HB_READ_ONLY_ENTITY="sensor.example_temperature"
export HB_EXCLUDED_ENTITY="sensor.example_diagnostic"
export HB_HIDDEN_ENTITY="sensor.example_hidden"
export HB_UNKNOWN_ENTITY="light.example_missing"
```

Sostituisci i valori con entità reali scelte da te, senza salvarli nel
repository. `HB_INCLUDED_ENTITY` deve essere in `entities.include` e
l'azione scelta deve essere innocua e reversibile.

## 1. Preflight del codice

```bash
cd /docker/appdata/house-brain/house-brain
git status --short
git branch --show-current
git log -1 --oneline

set -a
source .env
set +a

export AUTONOMY_POLICY_PATH="$PWD/config/autonomy.yaml"
export MEMORY_DATABASE_PATH="/tmp/house-brain-tests.db"
export AUTONOMY_BACKUP_PATH="/tmp/house-brain-autonomy-backups"
export UV_LINK_MODE=copy

uv run pytest
uv run ruff check .
```

Esito atteso:

- pytest termina senza errori;
- Ruff stampa `All checks passed!`;
- nessun file reale in `config/` viene sovrascritto.

Prima di tornare a Docker ricarica sempre i percorsi del container:

```bash
set -a
source .env
set +a
```

## 2. Avvio e diagnostica

```bash
set -a
source .env
set +a

docker compose -f docker-compose.dev.yml config --quiet
docker compose -f docker-compose.dev.yml up -d --build --force-recreate
docker compose -f docker-compose.dev.yml ps

curl -fsS "$HB_URL/health" | python3 -m json.tool
curl -fsS "$HB_URL/auth/check" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" |
  python3 -m json.tool
curl -fsS "$HB_URL/diagnostics" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" |
  python3 -m json.tool
```

Esito atteso:

- health: `status=ok`;
- autenticazione: `authenticated=true`;
- diagnostics: stato generale `ok`;
- Home Assistant riporta conteggi di entità visibili, nascoste e servizi;
- Ollama riporta il modello configurato come disponibile;
- nessun token o chiave compare nella risposta.

Prova negativa dell'autenticazione:

```bash
set -a
source .env
set +a

curl -sS -o /tmp/house-brain-auth-test.json -w '%{http_code}\n' \
  "$HB_URL/auth/check" -H "X-API-Key: chiave-errata"
python3 -m json.tool /tmp/house-brain-auth-test.json
```

Esito atteso: HTTP 401.

## 3. Interfacce web

Apri nel browser:

- `$HB_URL/chat`;
- `$HB_URL/autonomy`;
- `$HB_URL/memories`;
- `$HB_URL/audit`.

Verifica:

- [ ] tutte le pagine usano la stessa palette blu;
- [ ] la chiave errata viene rifiutata;
- [ ] la chiave corretta resta soltanto nella scheda corrente;
- [ ] il logout torna alla schermata di autenticazione;
- [ ] Chat mostra le schede delle azioni senza contraddire la tool trace;
- [ ] Autonomy non mostra i codici già configurati;
- [ ] Memories permette ricerca, modifica, cestino e ripristino;
- [ ] Audit filtra `observe`, `simulate` ed `execute` e apre la traccia completa.

## 4. Catalogo, servizi e visibilità

Ricarica prima ambiente e variabili della sezione iniziale.

```bash
set -a
source .env
set +a

curl -fsS "$HB_URL/services?domain=${HB_INCLUDED_DOMAIN}" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" |
  python3 -m json.tool

curl -fsS "$HB_URL/entities/${HB_READ_ONLY_ENTITY}" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" |
  python3 -m json.tool
```

Esito atteso: il catalogo proviene da Home Assistant e un'entità non esclusa
può essere letta anche se non è controllabile.

Prove negative:

```bash
set -a
source .env
set +a

for entity_id in "$HB_EXCLUDED_ENTITY" "$HB_HIDDEN_ENTITY" "$HB_UNKNOWN_ENTITY"; do
  curl -sS -o /tmp/house-brain-entity-test.json -w "$entity_id -> %{http_code}\n" \
    "$HB_URL/entities/$entity_id" \
    -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}"
done
```

Esito atteso: entità escluse, nascoste e inesistenti non sono esposte. Verifica
inoltre dalla ricerca in Chat e Autonomy che le entità nascoste non ricompaiano.

## 5. Memoria e persistenza

Questa prova crea una memoria chiaramente riconoscibile, la sposta nel cestino
e la ripristina. Alla fine puoi riutilizzare la GUI per modificarla o lasciarla
come evidenza del collaudo.

```bash
set -a
source .env
set +a

export HB_TEST_MEMORY="beta_validation_marker"

curl -fsS -X POST "$HB_URL/memory" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"key":"beta_validation_marker","value":"temporary beta validation","category":"test","importance":1}' |
  python3 -m json.tool

curl -fsSG "$HB_URL/memory" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  --data-urlencode "query=${HB_TEST_MEMORY}" |
  python3 -m json.tool

curl -fsS -X DELETE "$HB_URL/memory/${HB_TEST_MEMORY}" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" |
  python3 -m json.tool

curl -fsSG "$HB_URL/memory" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  --data-urlencode "query=${HB_TEST_MEMORY}" \
  --data-urlencode "deleted=true" |
  python3 -m json.tool

curl -fsS -X POST "$HB_URL/memory/${HB_TEST_MEMORY}/restore" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" |
  python3 -m json.tool
```

Riavvia e verifica nuovamente la memoria:

```bash
set -a
source .env
set +a

docker compose -f docker-compose.dev.yml restart house-brain

curl -fsSG "$HB_URL/memory" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  --data-urlencode "query=${HB_TEST_MEMORY}" |
  python3 -m json.tool
```

Esito atteso: la memoria sopravvive al riavvio e il cestino è recuperabile.

## 6. Chat e conversazione persistente

```bash
set -a
source .env
set +a

export HB_SESSION_ID="beta-validation-session"

curl -fsS -X POST "$HB_URL/agent/chat" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"beta-validation-session","message":"Rispondi soltanto confermando che la sessione di collaudo è attiva."}' |
  python3 -m json.tool

curl -fsS "$HB_URL/conversations/${HB_SESSION_ID}" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" |
  python3 -m json.tool
```

Dopo un riavvio, ripeti soltanto la seconda richiesta. Esito atteso: la
conversazione contiene ancora il messaggio dell'utente e la risposta.

## 7. Evento observe

```bash
set -a
source .env
set +a

curl -fsS -X POST "$HB_URL/agent/events" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type":"beta.observe",
    "source":"manual_beta_test",
    "mode":"observe",
    "instruction":"Osserva lo stato della casa senza proporre o eseguire azioni.",
    "context":{"validation":"beta"}
  }' |
  tee /tmp/house-brain-observe.json |
  python3 -m json.tool
```

Esito atteso:

- `mode=observe` e `status=completed`;
- nessuna chiamata di azione è eseguita;
- la risposta non dichiara azioni simulate o eseguite;
- l'evento compare nella GUI Audit.

## 8. Simulate

La simulazione deve usare esattamente le stesse validazioni di execute senza
modificare lo stato del dispositivo.

```bash
set -a
source .env
set +a

curl -fsS -X POST "$HB_URL/actions" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"domain\":\"${HB_INCLUDED_DOMAIN}\",
    \"service\":\"${HB_SAFE_SERVICE}\",
    \"entity_id\":\"${HB_INCLUDED_ENTITY}\",
    \"data\":{},
    \"dry_run\":true
  }" |
  python3 -m json.tool
```

Esito atteso: `status=simulated`; lo stato reale del dispositivo non cambia.

Ripeti da Chat e da `/agent/events` con `mode=simulate`. Controlla che:

- l'entità naturale venga risolta prima dell'azione;
- un nome ambiguo produca una richiesta di chiarimento in Chat;
- lo stesso nome ambiguo venga rifiutato negli eventi;
- il riepilogo dica `simulata`, mai `eseguita`;
- la tool trace contenga soltanto il piano finale pertinente.

## 9. Rifiuti obbligatori

Esegui una prova per ciascun caso:

- entity ID esplicito inesistente;
- entità leggibile ma non inclusa;
- entità esclusa;
- entità nascosta nel registro HA;
- dominio diverso da quello dell'entità;
- servizio inesistente;
- servizio non supportato dalle capacità dell'entità;
- parametro richiesto mancante;
- valore fuori dai limiti dichiarati da Home Assistant;
- codice di policy mancante;
- codice di policy errato;
- codice richiesto da HA mancante.

Per ogni caso verifica:

- [ ] nessuna azione reale;
- [ ] HTTP e messaggio indicano il motivo corretto;
- [ ] nessuna sostituzione con un'altra entità;
- [ ] nessun codice corretto viene rivelato;
- [ ] nessun codice compare in cronologia o tool trace;
- [ ] Audit registra il rifiuto senza semplificarne erroneamente la causa.

## 10. Execute controllato

Questa è l'unica sezione che comanda realmente Home Assistant. Prima crea un
backup, scegli un dispositivo sicuro e verifica direttamente in Home Assistant
lo stato iniziale.

Con kill switch disattivato, la stessa richiesta con `dry_run=false` deve
essere rifiutata. Solo dopo questo controllo modifica temporaneamente:

```dotenv
AUTONOMOUS_EXECUTION_ENABLED=true
```

Quindi ricrea il container:

```bash
set -a
source .env
set +a

docker compose -f docker-compose.dev.yml config --quiet
docker compose -f docker-compose.dev.yml up -d --force-recreate
docker compose -f docker-compose.dev.yml ps
```

Esegui una sola azione reversibile:

```bash
set -a
source .env
set +a

curl -fsS -X POST "$HB_URL/actions" \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"domain\":\"${HB_INCLUDED_DOMAIN}\",
    \"service\":\"${HB_SAFE_SERVICE}\",
    \"entity_id\":\"${HB_INCLUDED_ENTITY}\",
    \"data\":{},
    \"dry_run\":false
  }" |
  python3 -m json.tool
```

Esito atteso:

- `status=executed`;
- Home Assistant conferma il cambiamento;
- Chat e Audit dicono `eseguita`, non `simulata`;
- una risposta vuota finale di Ollama non perde l'esito autorevole del tool.

Subito dopo riporta il kill switch a `false` e ricrea nuovamente il container
con gli stessi comandi. Verifica che execute torni a essere rifiutato.

## 11. Codici

Per un'entità di prova con codice configurato in `autonomy.yaml`:

1. simula senza codice: rifiuto;
2. simula con codice errato: rifiuto;
3. simula con codice corretto: successo;
4. verifica che il codice non appaia nella risposta, Chat, conversazione o Audit;
5. ripeti execute soltanto se il dispositivo scelto è sicuro.

Per `POST /actions` passa il codice di policy con `X-Authorization-Code` e
l'eventuale codice richiesto dal dispositivo con `X-Home-Assistant-Code`.
Non scrivere mai i valori nei file del repository o nei resoconti.

## 12. Rebuild e persistenza completa

Annota un identificatore di memoria, sessione ed evento già creati, quindi:

```bash
set -a
source .env
set +a

docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml ps
curl -fsS "$HB_URL/health" | python3 -m json.tool
```

Verifica dopo il rebuild:

- memoria e cestino;
- conversazione;
- eventi e tool trace;
- policy e backup della policy;
- configurazione GUI;
- diagnostics;
- assenza di nuovi percorsi `/data`.

Non aggiungere `-v` a `docker compose down`: non bisogna rimuovere dati o
volumi.

## 13. Backup e ripristino

Segui integralmente [Backup e ripristino guidato](backup-restore.md). Dopo il
ripristino ripeti le sezioni 2, 3, 5, 6 e 12. Il database deve superare
`PRAGMA integrity_check` prima e dopo il ripristino.

Non eliminare il vecchio named volume e conserva
`config.before-restore-...` fino alla conclusione del collaudo.

## 14. MCP

Collega un client MCP usando:

```text
URL: http://SERVER:8090/mcp/
Authorization: Bearer HOUSE_BRAIN_API_KEY
```

Verifica:

- lettura di un'entità visibile;
- ricerca nel catalogo;
- elenco servizi;
- cronologia;
- rifiuto o assenza delle entità escluse/nascoste;
- creazione, ricerca, cestino e ripristino di una memoria di prova;
- assenza di strumenti MCP che eseguano azioni Home Assistant.

## 15. Resoconto finale

Registra soltanto:

```text
Commit collaudato:
Data:
Container dev / immagine:
Home Assistant raggiungibile: sì/no
Ollama e modello disponibili: sì/no
Observe: superato/fallito
Simulate: superato/fallito
Execute controllato: superato/fallito/non eseguito
Codice policy: superato/fallito/non applicabile
Codice Home Assistant: superato/fallito/non applicabile
Entità escluse: superato/fallito
Entità nascoste: superato/fallito
Memorie e cestino persistenti: superato/fallito
Conversazioni persistenti: superato/fallito
Audit persistente e autorevole: superato/fallito
Configuratore e backup policy: superato/fallito
Rebuild: superato/fallito
Backup/ripristino config: superato/fallito
MCP: superato/fallito
Anomalie:
```

Non creare tag o pubblicare una nuova immagine finché tutti i problemi rilevati
non sono stati valutati e il proprietario non ha dato consenso esplicito.
