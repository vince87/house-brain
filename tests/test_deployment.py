from pathlib import Path

import yaml

DEVELOPMENT_RUNTIME_ENVIRONMENT = {
    "PGID",
    "PUID",
    "AUTONOMOUS_EXECUTION_ENABLED",
    "AUTONOMY_BACKUP_PATH",
    "AUTONOMY_POLICY_PATH",
    "HOME_ASSISTANT_SERVICE_CACHE_TTL",
    "HOME_ASSISTANT_TIMEOUT",
    "HOME_ASSISTANT_TOKEN",
    "HOME_ASSISTANT_URL",
    "HOUSE_BRAIN_API_KEY",
    "HOUSE_BRAIN_LANGUAGE",
    "LLM_PROVIDER",
    "MEMORY_DATABASE_PATH",
    "OLLAMA_MODEL",
    "OLLAMA_CONTEXT_WINDOW",
    "OLLAMA_MAX_OUTPUT_TOKENS",
    "OLLAMA_TIMEOUT",
    "OLLAMA_TEMPERATURE",
    "OLLAMA_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_MODEL",
    "OPENAI_TIMEOUT",
    "OPENAI_MAX_OUTPUT_TOKENS",
    "SEARXNG_URL",
    "TZ",
    "WEB_SEARCH_MAX_RESULTS",
    "WEB_SEARCH_TIMEOUT",
}


def test_release_compose_uses_versioned_public_image_without_env_file() -> None:
    raw = Path("docker-compose.yml").read_text()
    compose = yaml.safe_load(raw)
    service = compose["services"]["house-brain"]

    assert service["image"] == "ghcr.io/vince87/house-brain:0.1.2"
    assert "build" not in service
    assert "env_file" not in service
    assert "${" not in raw
    assert set(service["environment"]) == DEVELOPMENT_RUNTIME_ENVIRONMENT - {
        "AUTONOMY_BACKUP_PATH",
        "AUTONOMY_POLICY_PATH",
    }
    assert "AUTONOMY_BACKUP_PATH" not in service["environment"]
    assert "AUTONOMY_POLICY_PATH" not in service["environment"]
    assert service["volumes"] == ["./config:/config:rw"]
    assert service["read_only"] is True
    assert service["environment"]["PUID"] == "1000"
    assert service["environment"]["PGID"] == "1000"
    assert service["cap_drop"] == ["ALL"]
    assert service["cap_add"] == ["CHOWN", "DAC_OVERRIDE", "SETGID", "SETUID"]


def test_development_compose_builds_locally_and_declares_environment() -> None:
    compose = yaml.safe_load(Path("docker-compose.dev.yml").read_text())
    service = compose["services"]["house-brain"]

    assert service["build"] == {"context": ".", "dockerfile": "Dockerfile"}
    assert service["image"] == "house-brain:local"
    assert "env_file" not in service
    assert set(service["environment"]) == DEVELOPMENT_RUNTIME_ENVIRONMENT
    assert service["volumes"] == ["./config:/config:rw"]
    assert service["environment"]["PUID"] == "${PUID:-1000}"
    assert service["environment"]["PGID"] == "${PGID:-1000}"
    assert service["cap_drop"] == ["ALL"]
    assert service["cap_add"] == ["CHOWN", "DAC_OVERRIDE", "SETGID", "SETUID"]


def test_container_drops_privileges_after_scoped_config_ownership_fix() -> None:
    dockerfile = Path("Dockerfile").read_text()
    entrypoint = Path("docker-entrypoint.sh").read_text()

    assert "apt-get install --no-install-recommends --yes gosu" in dockerfile
    assert 'ENTRYPOINT ["house-brain-entrypoint"]' in dockerfile
    assert 'chown -R "$PUID:$PGID" /config' in entrypoint
    assert 'exec gosu "$PUID:$PGID" "$@"' in entrypoint
    assert "chmod 777" not in entrypoint
    assert 'if [ "$PUID" -eq 0 ]' in entrypoint


def test_example_environment_uses_persistent_config_paths() -> None:
    environment = Path(".env.example").read_text()

    assert "AUTONOMY_POLICY_PATH=/config/autonomy.yaml" in environment
    assert "AUTONOMY_BACKUP_PATH=/config/autonomy-backups" in environment
    assert "MEMORY_DATABASE_PATH=/config/house_brain.db" in environment


def test_config_example_is_kept_outside_repository_root() -> None:
    assert Path("config/autonomy.yaml.example").is_file()
    assert not Path("autonomy.yaml.example").exists()


def test_runtime_paths_are_confined_to_config() -> None:
    combined = "\n".join(
        Path(path).read_text()
        for path in (
            ".env.example",
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.dev.yml",
            "house_brain/config.py",
        )
    )

    assert "/data" not in combined
    assert "house_brain_data" not in combined
    assert "/config/autonomy.yaml" in combined
    assert "/config/autonomy-backups" in combined
    assert "/config/house_brain.db" in combined


def test_container_workflow_tests_and_publishes_version_tags() -> None:
    workflow = Path(".github/workflows/container.yml").read_text()

    assert "uv run pytest" in workflow
    assert "uv run ruff check ." in workflow
    assert "packages: write" in workflow
    assert "startsWith(github.ref, 'refs/tags/v')" in workflow
    assert "linux/amd64,linux/arm64" in workflow
    assert "ghcr.io/vince87/house-brain" in workflow


def test_runtime_data_and_sqlite_sidecars_are_ignored() -> None:
    ignored = Path(".gitignore").read_text().splitlines()

    assert ".env" in ignored
    assert "config/autonomy.yaml" in ignored
    assert "config/autonomy-backups/" in ignored
    assert "config/house_brain.db-*" in ignored
    assert "config/*.db-*" in ignored
    assert "config/*.sqlite-*" in ignored


def test_release_documents_cover_backup_integrity_and_approval() -> None:
    operations = Path("docs/operations.md").read_text()
    checklist = Path("docs/release-v0.1.2.md").read_text()

    assert "PRAGMA integrity_check" in operations
    assert "config.before-restore-" in operations
    assert "named volume" in operations
    assert "non deve essere eliminato" in operations
    assert "memorie e" in operations
    assert "conversazioni" in operations
    assert "audit" in operations
    assert "consenso esplicito" in checklist


def test_release_uses_fixed_application_policy_paths() -> None:
    release_environment = yaml.safe_load(
        Path("docker-compose.yml").read_text()
    )["services"]["house-brain"]["environment"]
    application = Path("house_brain/config.py").read_text()

    assert "AUTONOMY_POLICY_PATH" not in release_environment
    assert "AUTONOMY_BACKUP_PATH" not in release_environment
    assert 'autonomy_policy_path: str = "/config/autonomy.yaml"' in application
    assert 'autonomy_backup_path: str = "/config/autonomy-backups"' in application


def test_guided_backup_and_beta_documents_cover_safe_validation() -> None:
    backup = Path("docs/backup-restore.md").read_text()
    beta = Path("docs/beta-testing.md").read_text()
    home = Path("docs/Home.md").read_text()

    assert "docker compose config --quiet" in backup
    assert "PRAGMA integrity_check" in backup
    assert "config.before-restore-" in backup
    assert "non deve essere eliminato" in backup
    assert "/diagnostics" in backup
    assert "AUTONOMOUS_EXECUTION_ENABLED" in beta
    assert "Observe" in beta
    assert "Simulate" in beta
    assert "Execute controllato" in beta
    assert "consenso esplicito" in beta
    assert "backup-restore.md" in home
    assert "beta-testing.md" in home


def test_executable_beta_runbook_covers_all_operational_gates() -> None:
    runbook = Path("docs/beta-validation-runbook.md").read_text()
    checklist = Path("docs/beta-testing.md").read_text()
    home = Path("docs/Home.md").read_text()

    required_sections = (
        "Preflight del codice",
        "Avvio e diagnostica",
        "Interfacce web",
        "Catalogo, servizi e visibilità",
        "Memoria e persistenza",
        "Chat e conversazione persistente",
        "Evento observe",
        "Simulate",
        "Rifiuti obbligatori",
        "Execute controllato",
        "Codici",
        "Rebuild e persistenza completa",
        "Backup e ripristino",
        "MCP",
        "Resoconto finale",
    )
    assert all(section in runbook for section in required_sections)
    assert runbook.count("set -a\nsource .env\nset +a") >= 10
    assert "docker compose -f docker-compose.dev.yml config --quiet" in runbook
    assert "uv run pytest" in runbook
    assert "uv run ruff check ." in runbook
    assert "AUTONOMOUS_EXECUTION_ENABLED=true" in runbook
    assert "export AUTONOMOUS_EXECUTION_ENABLED=false" in runbook
    assert runbook.count('if curl -fsS "$HB_URL/health"') >= 3
    assert "REPLACE_ME" in runbook
    assert "Non continuare se il controllo stampa" in runbook
    assert "ogni stato descritto deriva da una lettura riuscita" in runbook
    assert "Non aggiungere `-v`" in runbook
    assert "Non eliminare il vecchio named volume" in runbook
    assert "consenso esplicito" in runbook
    assert "beta-validation-runbook.md" in checklist
    assert "beta-validation-runbook.md" in home


def test_release_version_is_consistent() -> None:
    assert 'version = "0.1.2"' in Path("pyproject.toml").read_text()
    assert 'name = "house-brain"\nversion = "0.1.2"' in Path(
        "uv.lock"
    ).read_text()
    version_module = Path("house_brain/version.py").read_text()
    main = Path("house_brain/main.py").read_text()
    mcp = Path("house_brain/mcp_server.py").read_text()
    assert 'APP_VERSION = version("house-brain")' in version_module
    assert "from house_brain.version import APP_VERSION" in main
    assert "from house_brain.version import APP_VERSION" in mcp
    assert "version=APP_VERSION" in mcp
    assert "ghcr.io/vince87/house-brain:0.1.2" in Path(
        "docker-compose.yml"
    ).read_text()
