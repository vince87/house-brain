# Add-on Home Assistant sperimentale

Il repository contiene un prototipo di add-on nella directory
`addons/house_brain`. Il container standalone resta pienamente supportato.

## Perimetro di sicurezza

L'add-on:

- usa la directory Supervisor dedicata all'add-on come `/config`;
- riceve l'accesso alle API Home Assistant tramite il token Supervisor;
- non monta la configurazione generale di Home Assistant;
- non usa rete host, modalità privilegiata o socket Docker;
- non importa, sposta o elimina automaticamente dati di una precedente
  installazione standalone;
- parte con l'esecuzione autonoma disabilitata salvo scelta esplicita.

Il pannello nativo dell'integrazione resta l'interfaccia raccomandata. L'add-on
espone la porta 8090 per configurazione, diagnostica e collegamento
dell'integrazione.

## Percorsi persistenti

Supervisor assegna all'add-on una directory dedicata sotto
`/addon_configs/<repository>_house_brain` e la monta esplicitamente come
`/config` nel container. House Brain usa esclusivamente:

- `/config/house_brain.db`;
- `/config/autonomy.yaml`;
- `/config/autonomy-backups`;
- `/config/context-views.yaml`;
- `/config/system-backups`.

Le opzioni dell'add-on sono conservate separatamente da Supervisor in
`/data/options.json`. La pagina di configurazione non espone override per i
percorsi persistenti.

## Compatibilità

L'add-on richiede Home Assistant OS o Supervised. Con Home Assistant Core o
Container usa il container standalone e la custom integration; non tentare di
copiare manualmente i dati nella directory di Home Assistant.

## Installazione di prova

1. In Home Assistant apri **Impostazioni → Componenti aggiuntivi → Store**.
2. Aggiungi `https://github.com/vince87/house-brain` come repository.
3. Installa **House Brain**, indicato come sperimentale.
4. Configura una chiave API robusta, lingua, provider, URL e modello.
5. Mantieni `autonomous_execution_enabled: false` durante il primo collaudo.
6. Avvia l'add-on e verifica health, diagnostica e persistenza.
7. Installa/configura l'integrazione House Brain con l'indirizzo dell'add-on e
   la stessa chiave API.

## Migrazione prudente

Non collegare add-on e container standalone alla stessa directory. Scarica un
backup verificato dalla vecchia installazione, arrestala, conserva intatti
directory e volumi originali, quindi usa l'ispezione e il ripristino esplicito
nella nuova installazione. Verifica memorie, conversazioni, audit, policy,
viste contestuali e backup prima di considerare completata la migrazione.

Il prototipo non viene dichiarato stabile fino a un collaudo reale su Home
Assistant OS/Supervised e a una release autorizzata.
