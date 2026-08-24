# Motore di contesto Home Assistant

House Brain può usare le relazioni native di Home Assistant per selezionare un
insieme piccolo e verificabile di entità. Il motore legge tramite WebSocket i
registri delle aree, dei dispositivi e delle entità e li unisce agli stati
correnti.

## Sicurezza e autorevolezza

Il contesto non modifica la policy e non concede autorizzazioni:

- vengono restituite soltanto entità presenti in `entities.visible` o
  `entities.include`;
- le entità nascoste nel registro Home Assistant restano invisibili;
- `controllable: true` significa soltanto che l'entità è inclusa nella policy;
- ogni azione deve ancora superare validazione, catalogo servizi, codici,
  modalità e kill switch;
- il nome configurato in Autonomy sostituisce il `friendly_name` di Home
  Assistant;
- area e dispositivo sono metadati di selezione, non regole di autorizzazione.

## Strumento agente

Lo strumento `get_home_context` accetta filtri opzionali:

- `domains`: massimo otto domini;
- `areas`: massimo otto ID, nomi o alias di aree Home Assistant;
- `query`: ricerca normalizzata su entity ID, nome autorevole, area e
  dispositivo;
- `controllable_only`: limita il risultato alle entità incluse per il
  controllo;
- `limit` e `offset`: paginazione deterministica.

Ogni elemento include stato corrente, area, dispositivo, controllabilità e
`selection_reasons`. Se il risultato è troncato, l'agente deve leggere la
pagina successiva o restringere i filtri prima di dichiarare che un'entità è
assente.

## API

L'endpoint autenticato `GET /context` espone lo stesso risultato del motore.
I parametri `domains` e `areas` possono essere ripetuti.

```bash
set -a
source .env
set +a

curl -fsS \
  -H "X-API-Key: ${HOUSE_BRAIN_API_KEY}" \
  --get "http://localhost:8090/context" \
  --data-urlencode "areas=Example Kitchen" \
  --data-urlencode "domains=light" \
  --data-urlencode "limit=20" |
  python3 -m json.tool
```

Usare nomi e ID realmente configurati nel proprio Home Assistant. Gli esempi
del repository sono intenzionalmente generici.

## Interfaccia Autonomy

Le interfacce diretta e nativa mostrano area e dispositivo quando disponibili.
La ricerca considera anche questi metadati. Un errore temporaneo dei registri
non impedisce di aprire il configuratore: in quel caso le relazioni vengono
omesse e la policy rimane modificabile.

## Cache e aggiornamenti

I registri condividono la durata della cache dei servizi Home Assistant. Gli
stati vengono comunque letti al momento della richiesta. Il riavvio del
processo svuota la cache senza modificare alcuna configurazione persistente.
