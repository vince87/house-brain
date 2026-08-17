# Roadmap

## Deployment dichiarativo — completato

Il deployment espone un'unica directory persistente facile da copiare:

- policy, database e backup raccolti in `config/` e montati esplicitamente nel
  container;
- variabili di ambiente dichiarate nel `docker-compose.yml` con valori letti
  da `.env`;
- migrazione documentata dall'installazione attuale senza perdere policy,
  database o backup;
- verifica preventiva con `docker compose config`.

## Prima versione stabile

Dopo un periodo di utilizzo reale:

- collaudo finale `observe`, `simulate` ed `execute`;
- verifica dei codici, delle esclusioni e del configuratore;
- backup del database e della policy;
- tag `v0.1.0` e changelog.
