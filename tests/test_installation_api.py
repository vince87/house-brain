import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from house_brain import main as main_module
from house_brain.config import get_settings
from house_brain.main import app

API_KEY = "test-installation-key"


@pytest.fixture
def installation_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[TestClient, Path]:
    root = tmp_path / "config"
    root.mkdir()
    (root / "autonomy-backups").mkdir()
    (root / "autonomy.yaml").write_text(
        (
            "version: 2\n"
            "entities:\n"
            "  visible:\n"
            "    - sensor.example_temperature\n"
            "  include:\n"
            "    - light.example_room\n"
        )
    )
    with sqlite3.connect(root / "house_brain.db") as connection:
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker VALUES ('original')")

    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://homeassistant.test:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "secret-token")
    monkeypatch.setenv("HOUSE_BRAIN_API_KEY", API_KEY)
    monkeypatch.setenv("MEMORY_DATABASE_PATH", str(root / "house_brain.db"))
    monkeypatch.setenv("AUTONOMY_POLICY_PATH", str(root / "autonomy.yaml"))
    monkeypatch.setenv(
        "AUTONOMY_BACKUP_PATH",
        str(root / "autonomy-backups"),
    )
    get_settings.cache_clear()
    main_module.INSTALLATION_RESTORE_ACTIVE = False
    with TestClient(app) as client:
        yield client, root
    main_module.INSTALLATION_RESTORE_ACTIVE = False
    get_settings.cache_clear()


def _headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


def test_installation_shell_is_public_but_api_is_protected(
    installation_client: tuple[TestClient, Path],
) -> None:
    client, _ = installation_client

    shell = client.get("/installation")
    protected = client.get("/admin/installation")

    assert shell.status_code == 200
    assert "Gestione installazione" in shell.text
    assert 'id="authForm"' in shell.text
    assert protected.status_code == 401


def test_installation_status_is_authenticated_and_secret_free(
    installation_client: tuple[TestClient, Path],
) -> None:
    client, _ = installation_client

    response = client.get("/admin/installation", headers=_headers())

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["persistent_root"] == "/config"
    assert API_KEY not in response.text
    assert "secret-token" not in response.text


def test_backup_download_is_a_valid_archive_without_credentials(
    installation_client: tuple[TestClient, Path],
) -> None:
    client, _ = installation_client

    response = client.post(
        "/admin/installation/backups",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format"] == "house-brain-config-backup"
        assert "config/house_brain.db" in archive.namelist()
        assert "config/autonomy.yaml" in archive.namelist()
        joined = b"".join(
            archive.read(name)
            for name in archive.namelist()
            if not name.endswith("/")
        )
    assert API_KEY.encode() not in joined
    assert b"secret-token" not in joined


def test_inspect_and_apply_require_explicit_confirmation(
    installation_client: tuple[TestClient, Path],
) -> None:
    client, root = installation_client
    backup = client.post(
        "/admin/installation/backups",
        headers=_headers(),
    )
    with sqlite3.connect(root / "house_brain.db") as connection:
        connection.execute("UPDATE marker SET value = 'changed'")

    inspected = client.post(
        "/admin/installation/restores/inspect",
        headers={**_headers(), "Content-Type": "application/zip"},
        content=backup.content,
    )

    assert inspected.status_code == 200
    body = inspected.json()
    assert body["status"] == "validated"
    assert body["files"]
    rejected = client.post(
        "/admin/installation/restores/apply",
        headers=_headers(),
        json={
            "restore_token": body["restore_token"],
            "confirmation": "NO",
        },
    )
    assert rejected.status_code == 422

    applied = client.post(
        "/admin/installation/restores/apply",
        headers=_headers(),
        json={
            "restore_token": body["restore_token"],
            "confirmation": "RESTORE",
        },
    )

    assert applied.status_code == 200
    assert applied.json()["status"] == "restored"
    assert applied.json()["restart_recommended"] is True
    with sqlite3.connect(root / "house_brain.db") as connection:
        value = connection.execute("SELECT value FROM marker").fetchone()[0]
        event_types = {
            row[0]
            for row in connection.execute(
                "SELECT event_type FROM agent_events"
            ).fetchall()
        }
    assert value == "original"
    assert "installation.restore" in event_types
    assert list(
        (root / "system-backups").glob("config.before-restore-*.zip")
    )


def test_restore_maintenance_mode_rejects_other_operations(
    installation_client: tuple[TestClient, Path],
) -> None:
    client, _ = installation_client
    main_module.INSTALLATION_RESTORE_ACTIVE = True

    blocked = client.get("/admin/installation", headers=_headers())
    health = client.get("/health")

    assert blocked.status_code == 503
    assert blocked.headers["retry-after"] == "5"
    assert health.status_code == 200
