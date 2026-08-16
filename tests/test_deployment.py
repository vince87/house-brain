from pathlib import Path

import yaml


def test_compose_keeps_container_read_only_but_allows_policy_updates() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    service = compose["services"]["house-brain"]

    assert service["read_only"] is True
    assert "./autonomy.yaml:/app/autonomy.yaml:rw" in service["volumes"]
    assert "house_brain_data:/data" in service["volumes"]


def test_example_environment_uses_persistent_policy_backup_directory() -> None:
    environment = Path(".env.example").read_text()

    assert "AUTONOMY_POLICY_PATH=/app/autonomy.yaml" in environment
    assert "AUTONOMY_BACKUP_PATH=/data/autonomy-backups" in environment
