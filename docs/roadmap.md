# Roadmap

Le versioni `v0.1.0`, `v0.1.1` e `v0.1.2` sono state pubblicate. Il progetto è
in collaudo beta prolungato prima della successiva release.

## Deployment dichiarativo — completato

Il deployment espone un'unica directory persistente facile da copiare:

- policy, database e backup raccolti in `config/` e montati esplicitamente nel
  container;
- variabili dichiarate direttamente nel Compose di release; `.env` resta
  riservato al Compose di sviluppo;
- migrazione documentata dall'installazione attuale senza perdere policy,
  database o backup;
- verifica preventiva con `docker compose config`.

## Prossima release beta

Prima della prossima release:

- collaudo finale `observe`, `simulate` ed `execute`;
- verifica dei codici, della visibilità default-deny e del configuratore;
- backup del database e della policy;
- collaudo dei permessi Docker e delle interfacce unificate;
- verifica prolungata di Ollama e del provider OpenAI-compatible;
- revisione completa del manuale e delle procedure operative;
- changelog, checklist, tag e immagine GHCR versionata.
