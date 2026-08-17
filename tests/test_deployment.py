from pathlib import Path

import yaml


def test_compose_mounts_explicit_writable_config_directory() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    service = compose["services"]["house-brain"]

    assert service["read_only"] is True
    assert service["volumes"] == ["./config:/config:rw"]
    assert "volumes" not in compose
    assert "env_file" not in service


def test_compose_declares_every_runtime_environment_variable() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    environment = compose["services"]["house-brain"]["environment"]

    assert set(environment) == {
        "AUTONOMOUS_EXECUTION_ENABLED",
        "AUTONOMY_BACKUP_PATH",
        "AUTONOMY_POLICY_PATH",
        "HOME_ASSISTANT_SERVICE_CACHE_TTL",
        "HOME_ASSISTANT_TIMEOUT",
        "HOME_ASSISTANT_TOKEN",
        "HOME_ASSISTANT_URL",
        "HOUSE_BRAIN_API_KEY",
        "HOUSE_BRAIN_LANGUAGE",
        "MEMORY_DATABASE_PATH",
        "OLLAMA_MODEL",
        "OLLAMA_TIMEOUT",
        "OLLAMA_URL",
        "SEARXNG_URL",
        "TZ",
        "WEB_SEARCH_MAX_RESULTS",
        "WEB_SEARCH_TIMEOUT",
    }


def test_example_environment_uses_persistent_policy_backup_directory() -> None:
    environment = Path(".env.example").read_text()

    assert "AUTONOMY_POLICY_PATH=/config/autonomy.yaml" in environment
    assert "AUTONOMY_BACKUP_PATH=/config/autonomy-backups" in environment
    assert "MEMORY_DATABASE_PATH=/config/house_brain.db" in environment


def test_config_example_is_kept_outside_repository_root() -> None:
    assert Path("config/autonomy.yaml.example").is_file()
    assert not Path("autonomy.yaml.example").exists()


def test_persistent_runtime_paths_are_confined_to_config() -> None:
    combined = "\n".join(
        Path(path).read_text()
        for path in (".env.example", "docker-compose.yml", "house_brain/config.py")
    )

    assert "/data" not in combined
    assert "house_brain_data" not in combined
    assert "/config/autonomy.yaml" in combined
    assert "/config/autonomy-backups" in combined
    assert "/config/house_brain.db" in combined


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
    checklist = Path("docs/release-v0.1.0.md").read_text()

    assert "PRAGMA integrity_check" in operations
    assert "config.before-restore-" in operations
    assert "vecchio named volume" in operations
    assert "memorie e" in operations
    assert "conversazioni" in operations
    assert "audit" in operations
    assert "consenso esplicito" in checklist
