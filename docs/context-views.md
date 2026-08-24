# Viste contestuali

Le viste contestuali riducono in modo deterministico il gruppo di entità
presentato al modello. Non sono una seconda policy: una vista può soltanto
selezionare un sottoinsieme delle entità già rese leggibili o controllabili da
Autonomia.

## Configurazione

La pagina `/context-views` e la scheda **Contesto** del pannello Home Assistant
permettono di configurare:

- un identificatore stabile e un nome descrittivo;
- aree, domini ed entity ID espliciti;
- il numero massimo di entità;
- l'inclusione delle memorie collegate;
- abilitazione e vista predefinita.

Aree, domini ed entity ID sono combinati come alternative: un'entità viene
selezionata se corrisponde ad almeno uno dei selettori. Successivamente House
Brain applica sempre la policy default-deny e l'esclusione delle entità nascoste
in Home Assistant. Il limite viene applicato dopo un ordinamento stabile.

La configurazione runtime è `/config/context-views.yaml`. Il file reale e i
relativi backup sono ignorati da Git; l'esempio versionato è
`config/context-views.yaml.example`. Ogni salvataggio è atomico e crea un
backup nella directory già usata per i backup della policy.

## Uso da API e agente

`GET /context?view_id=example_daytime` restituisce la selezione effettiva,
l'origine della selezione e quante entità sono state omesse dal limite. Il tool
`list_context_views` espone al modello solo identificatori, nomi e limiti: non
rivela automaticamente gli entity ID della configurazione.

Il modello deve scegliere una vista usando il suo identificatore esatto. House
Brain non interpreta parole chiave del prompt per indovinare una vista. Una
vista sconosciuta o disabilitata viene rifiutata esplicitamente.
