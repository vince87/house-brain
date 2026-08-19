# Policy di autonomia

La policy versione 2 è unica per chat, eventi e API. La configurazione stabilisce
quali entità House Brain può leggere, quali può controllare e quali non deve vedere. Non contiene
elenchi di domini o servizi: il motore rappresenta genericamente i servizi Home
Assistant e la policy decide quali dispositivi sono controllabili.

La policy è fail-fast: versione errata, campi sconosciuti, entity ID non validi e
la presenza della stessa entità in `visible` e `include` impediscono l'avvio.

## Configurazione minima

```yaml
version: 2

entities:
  visible:
    - sensor.example_temperature
    - sun.sun

  include:
    - light.example_living_room
    - media_player.example_display
    - entity_id: lock.example_front_door
      code: "2468"

  exclude:
    - light.example_group
    - cover.example_group
    - sensor.*_diagnostic
```

## Significato delle liste

| Posizione | Visibile | Leggibile | Controllabile |
|---|:---:|:---:|:---:|
| `entities.visible` | sì | sì | no |
| `entities.include` | sì | sì | sì |
| `entities.exclude` | no | no | no |
| non elencata | no | no | no |

La visibilità è **default-deny**: all'avvio House Brain non espone alcuna entità
che non sia stata scelta esplicitamente. In `visible` e `include` sono ammessi
solo entity ID esatti. In `exclude` sono ammessi entity ID esatti e pattern
shell, per esempio `sensor.*_diagnostic`.

La stessa entità non può comparire sia in `visible` sia in `include`, perché
le due scelte hanno permessi diversi. `exclude` è invece un blocco assoluto e
prevale sempre, anche su una voce presente nelle altre liste.

Le esclusioni e il default-deny si applicano anche a catalogo, ricerca,
cronologia, lettura diretta, `state-before`, riferimenti contenuti negli
attributi dei gruppi, chat, eventi, MCP e simulazioni. Il configuratore
autenticato continua a interrogare il catalogo Home Assistant completo
(escluse le entità nascoste nel registro HA) per consentire la scelta iniziale.

## Come vengono autorizzate le azioni

Per un'entità inclusa il motore può usare qualunque servizio Home Assistant
coerente con il dominio dell'entità:

- `light.example_living_room` può usare `light.turn_on`;
- `media_player.example_display` può usare `media_player.turn_off`;
- un servizio `switch.*` non può essere applicato a un'entità `light.*`.

Non serve aggiungere ogni dominio nel codice. Anche `lock`, `button`,
`select`, `script`, `automation` o uno `switch` che aziona un accesso
restano inutilizzabili finché la relativa entità non compare in `include`.

Identificatori non validi, domini incoerenti, dati annidati e numeri non finiti
vengono respinti. Negli eventi automatici `toggle` resta vietato perché il suo
risultato dipende dallo stato iniziale.

### Richieste con entity ID esplicito

Se la richiesta contiene un entity ID, l'azione deve usare esattamente quello:

```text
Simula lo spegnimento di media_player.example_display
```

Se l'entità non esiste o non è inclusa, il comando viene respinto. Il modello non
può sostituirla con un'altra entità inclusa dal nome simile.

### Richieste con nome descrittivo

Se l'utente scrive un nome, l'agente può cercarlo nel catalogo:

```text
Simula lo spegnimento del display in cucina
```

L'entità trovata deve comunque essere in `include`. Una ricerca riuscita non
concede il permesso di controllarla.

## Codice facoltativo per entità

Il codice si dichiara accanto a qualsiasi entità, indipendentemente dal dominio:

```yaml
entities:
  include:
    - entity_id: switch.example_gate_relay
      code: "2468"
    - entity_id: lock.example_front_door
      code: "garage-A7"
```

Se un'entità ha `code`, ogni servizio su quell'entità richiede quel codice di
policy. Senza `code`, House Brain non aggiunge una protezione propria. Questo è
distinto dall'eventuale codice richiesto dal dispositivo Home Assistant: in quel
caso il server legge i metadati dell'entità e lo richiede soltanto per i servizi
interessati. Per esempio, `code_arm_required: false` non impone un codice per
inserire un allarme, mentre `code_format` può ancora indicarlo per disinserirlo.
House Brain non prova comunque a dedurre la pericolosità dal dominio: uno switch
può aprire un cancello e solo chi configura l'impianto conosce il significato
reale del dispositivo.

In chat e nelle istruzioni evento il codice può essere scritto esplicitamente:

```text
Sblocca la porta di esempio, codice: garage-A7
```

Un codice numerico di almeno quattro cifre può anche essere scritto naturalmente
alla fine del comando:

```text
Simula lo sblocco della porta di esempio 2468
```

Per `POST /actions` si usa invece l'header `X-Authorization-Code`. I codici
accettano da 4 a 64 lettere, numeri, trattini e underscore.

Il codice del dispositivo Home Assistant usa invece
`X-Home-Assistant-Code`; i due controlli possono coesistere e restano separati.

Il server rimuove il codice prima di inviare la richiesta a Ollama e non lo salva
nelle conversazioni, negli eventi, nei log o nella `tool_trace`. Un codice
mancante o errato respinge l'azione con un motivo esplicito.

## Modalità operative

| Modalità | Letture | Azioni |
|---|---|---|
| `observe` | consentite | non disponibili |
| `simulate` | consentite | validate ma non inviate a Home Assistant |
| `execute` | consentite | reali, se il kill switch globale è attivo |

L'esecuzione reale richiede:

```dotenv
AUTONOMOUS_EXECUTION_ENABLED=true
```

La modalità non modifica la policy: anche in simulazione un'entità non inclusa,
esclusa o protetta da un codice errato viene respinta.

## Ricaricare la policy

Il configuratore è disponibile su:

```text
http://SERVER:8090/autonomy
```

Usa la stessa API key della chat. Mostra tutte le entità di Home Assistant e
permette di impostare `visible`, `include`, `exclude`, pattern e un codice opzionale per
qualunque entità. I codici esistenti non vengono mai restituiti al browser:
lasciando vuoto il campo si conserva quello attuale.

Ogni salvataggio:

- valida completamente la nuova policy prima di modificare il file;
- conserva fino a 10 backup protetti in `AUTONOMY_BACKUP_PATH`;
- applica subito la nuova configurazione senza riavviare il container.

Per consentire il salvataggio atomico, `config/` è la sola directory di
configurazione montata in scrittura. Il resto del filesystem del container
rimane read-only. Il processo usa UID e GID `10001`: sul server assegna
directory e file al tuo utente e al gruppo numerico del container, senza
renderli accessibili agli altri utenti:

```bash
sudo chown "$(id -u):10001" config config/autonomy.yaml
chmod 770 config
chmod 660 config/autonomy.yaml
```

Questa operazione è necessaria una sola volta e non espone gli eventuali codici
contenuti nella policy.

Se modifichi invece `config/autonomy.yaml` manualmente, ricrea il container:

```bash
set -a
source .env
set +a

docker compose config --quiet
docker compose up -d --force-recreate
docker compose ps
```

`config/autonomy.yaml` e i suoi backup possono contenere codici reali: non
commetterli e limita i permessi sul server.

## Verifica rapida

Ricarica le variabili del terminale e imposta quelle usate dai test:

```bash
set -a
source .env
set +a
export AUTONOMY_POLICY_PATH="$PWD/config/autonomy.yaml"
export UV_LINK_MODE=copy
```

Verifica prima un'entità dichiarata in `entities.visible`:

```bash
curl -sS http://localhost:8090/entities/sensor.example_temperature \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" |
  python3 -m json.tool
```

Poi simula un'azione, sostituendo l'entity ID con uno realmente presente in
`entities.include`:

```bash
curl -sS http://localhost:8090/actions \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "light",
    "service": "turn_off",
    "entity_id": "light.example_living_room",
    "dry_run": true
  }' |
  python3 -m json.tool
```

Se l'entità ha un codice, aggiungi
`-H "X-Authorization-Code: CODICE"`. Controlla sempre `tool_trace`: è la
fonte autorevole sull'esito delle azioni.
