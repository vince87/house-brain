# Checklist di rilascio v0.1.6

La release consolida Context Orchestrator, backup e ripristino guidati e la
distribuzione Home Assistant introdotti dopo v0.1.5.

## Contenuto

- [x] versione applicativa, lockfile, manifest, Compose e add-on allineati a
  `0.1.6`;
- [x] changelog e roadmap aggiornati;
- [x] un solo mount persistente `config/`;
- [x] path runtime fisse sotto `/config`;
- [x] nessuna modifica automatica a policy, database, backup o vecchi volumi.

## Verifiche automatiche

- [x] suite Python 3.12;
- [x] Ruff;
- [x] sintassi JavaScript;
- [x] hassfest e HACS;
- [x] build multiarch del container;
- [x] build multiarch dell'add-on sperimentale.

## Collaudi reali già completati sulla branch funzionale

- [x] viste contestuali con limite e selezione default-deny;
- [x] uso della vista tramite agente in modalità `simulate`;
- [x] pannello Home Assistant e GUI diretta;
- [x] backup, ispezione e ripristino completo;
- [x] persistenza di database, policy, memorie, conversazioni e audit.

Il collaudo runtime dell'add-on resta non applicabile all'ambiente Home
Assistant Core disponibile. L'add-on rimane sperimentale.

## Dopo il tag

- [ ] workflow del tag `v0.1.6` completato;
- [ ] immagini GHCR `0.1.6` e `latest` pubblicate per amd64 e arm64;
- [ ] health check dell'immagine pubblicata restituisce `0.1.6`;
- [ ] aggiornamento della custom integration dalla release verificato;
- [ ] database, policy, memorie, conversazioni e audit presenti dopo
  l'aggiornamento.

La creazione del tag e il merge richiedono consenso esplicito. Il vecchio named
volume Docker e i backup non devono essere eliminati.
