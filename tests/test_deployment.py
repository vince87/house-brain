from pathlib import Path

import yaml



RUNTIME_ENVIRONMENT = {
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


def test_release_compose_uses_versioned_public_image_without_env_file() -> None:
    raw = Path("docker-compose.yml").read_text()
    compose = yaml.safe_load(raw)
    service = compose["services"]["house-brain"]

    assert service["image"] == "ghcr.io/vince87/house-brain:0.1.0"
    assert "build" not in service
    assert "env_file" not in service
    assert "${" not in raw
    assert set(service["environment"]) == RUNTIME_ENVIRONMENT
    assert service["volumes"] == ["./config:/config:rw"]
    assert service["read_only"] is True


def test_development_compose_builds_locally_and_declares_environment() -> None:
    compose = yaml.safe_load(Path("docker-compose.dev.yml").read_text())
    service = compose["services"]["house-brain"]

    assert service["build"] == {"context": ".", "dockerfile": "Dockerfile"}
    assert service["image"] == "house-brain:local"
    assert "env_file" not in service
    assert set(service["environment"]) == RUNTIME_ENVIRONMENT
    assert service["volumes"] == ["./config:/config:rw"]


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
    checklist = Path("docs/release-v0.1.0.md").read_text()

    assert "PRAGMA integrity_check" in operations
    assert "config.before-restore-" in operations
    assert "named volume" in operations
    assert "non deve essere eliminato" in operations
    assert "memorie e" in operations
    assert "conversazioni" in operations
    assert "audit" in operations
    assert "consenso esplicito" in checklist
