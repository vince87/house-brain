import json
import sqlite3
import stat
import zipfile
from pathlib import Path

import pytest

from house_brain.config import Settings
from house_brain.installation import (
    InstallationLifecycleError,
    RestoreStagingStore,
    apply_installation_restore,
    create_installation_backup,
    inspect_installation_backup,
    installation_status,
)


def _settings(root: Path) -> Settings:
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
        api_key="test-key",
        memory_database_path=str(root / "house_brain.db"),
        autonomy_policy_path=str(root / "autonomy.yaml"),
        autonomy_backup_path=str(root / "autonomy-backups"),
    )


def _write_policy(root: Path, name: str = "Example Room") -> None:
    (root / "autonomy.yaml").write_text(
        (
            "version: 2\n"
            "entities:\n"
            "  visible:\n"
            "    - entity_id: sensor.example_temperature\n"
            "      name: Example Temperature\n"
            "  include:\n"
            "    - entity_id: light.example_room\n"
            f"      name: {name}\n"
        )
    )
    (root / "autonomy-backups").mkdir(exist_ok=True)


def _write_database(root: Path, value: str) -> None:
    with sqlite3.connect(root / "house_brain.db") as connection:
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker VALUES (?)", (value,))


def _read_marker(root: Path) -> str:
    with sqlite3.connect(root / "house_brain.db") as connection:
        return str(connection.execute("SELECT value FROM marker").fetchone()[0])


def _configured_root(tmp_path: Path, name: str, marker: str) -> Path:
    root = tmp_path / name
    root.mkdir()
    _write_policy(root, name=f"{name} room")
    _write_database(root, marker)
    return root


def test_backup_uses_sqlite_snapshot_manifest_and_checksums(tmp_path: Path) -> None:
    root = _configured_root(tmp_path, "source", "coherent")
    (root / "autonomy-backups" / "autonomy.yaml.backup-example").write_text(
        "version: 2\nentities:\n  include: []\n"
    )
    (root / "house_brain.db-wal").write_bytes(b"not-a-real-sidecar")
    lifecycle = root / "system-backups"
    lifecycle.mkdir()
    (lifecycle / "older.zip").write_bytes(b"not-recursive")
    archive = tmp_path / "backup.zip"

    manifest = create_installation_backup(_settings(root), archive)

    assert manifest["format_version"] == 1
    assert manifest["database"] == "config/house_brain.db"
    assert manifest["policy"] == "config/autonomy.yaml"
    paths = {item["path"] for item in manifest["files"]}
    assert "config/house_brain.db" in paths
    assert "config/autonomy.yaml" in paths
    assert "config/autonomy-backups/autonomy.yaml.backup-example" in paths
    assert "config/house_brain.db-wal" not in paths
    assert not any("system-backups" in path for path in paths)
    with zipfile.ZipFile(archive) as backup:
        archived_manifest = json.loads(backup.read("manifest.json"))
        assert archived_manifest == manifest
        archived_database = tmp_path / "archived-house-brain.db"
        archived_database.write_bytes(backup.read("config/house_brain.db"))
        with sqlite3.connect(archived_database) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"


def test_backup_and_inspection_round_trip(tmp_path: Path) -> None:
    root = _configured_root(tmp_path, "source", "round-trip")
    archive = tmp_path / "backup.zip"
    create_installation_backup(_settings(root), archive)
    store = RestoreStagingStore()

    staged = inspect_installation_backup(
        archive,
        _settings(root),
        staging_store=store,
    )

    assert staged.manifest["database"] == "config/house_brain.db"
    assert staged.expires_at > staged.created_at
    assert {item["path"] for item in staged.files} >= {
        "config/autonomy.yaml",
        "config/house_brain.db",
    }
    store.discard(store.consume(staged.token))


def test_restore_rejects_invalid_zip(tmp_path: Path) -> None:
    root = _configured_root(tmp_path, "target", "original")
    archive = tmp_path / "invalid.zip"
    archive.write_bytes(b"not a zip archive")

    with pytest.raises(InstallationLifecycleError, match="valid ZIP"):
        inspect_installation_backup(
            archive,
            _settings(root),
            staging_store=RestoreStagingStore(),
        )


def test_restore_rejects_parent_traversal(tmp_path: Path) -> None:
    root = _configured_root(tmp_path, "target", "original")
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside", b"unsafe")
        output.writestr("manifest.json", "{}")

    with pytest.raises(InstallationLifecycleError, match="unsafe path"):
        inspect_installation_backup(
            archive,
            _settings(root),
            staging_store=RestoreStagingStore(),
        )


def test_restore_rejects_symbolic_links(tmp_path: Path) -> None:
    root = _configured_root(tmp_path, "target", "original")
    archive = tmp_path / "link.zip"
    link = zipfile.ZipInfo("config/autonomy.yaml")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(link, "outside")
        output.writestr("manifest.json", "{}")

    with pytest.raises(InstallationLifecycleError, match="non-regular"):
        inspect_installation_backup(
            archive,
            _settings(root),
            staging_store=RestoreStagingStore(),
        )


def test_restore_rejects_checksum_mismatch(tmp_path: Path) -> None:
    root = _configured_root(tmp_path, "target", "original")
    archive = tmp_path / "bad-checksum.zip"
    payload = b"version: 2\nentities:\n  include: []\n"
    manifest = {
        "format": "house-brain-config-backup",
        "format_version": 1,
        "database": "config/autonomy.yaml",
        "policy": "config/autonomy.yaml",
        "files": [
            {
                "path": "config/autonomy.yaml",
                "size": len(payload),
                "sha256": "0" * 64,
            }
        ],
    }
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("config/autonomy.yaml", payload)
        output.writestr("manifest.json", json.dumps(manifest))

    with pytest.raises(InstallationLifecycleError, match="checksum"):
        inspect_installation_backup(
            archive,
            _settings(root),
            staging_store=RestoreStagingStore(),
        )


def test_apply_restore_replaces_managed_state_and_keeps_snapshot(
    tmp_path: Path,
) -> None:
    source = _configured_root(tmp_path, "source", "restored")
    target = _configured_root(tmp_path, "target", "original")
    archive = tmp_path / "backup.zip"
    create_installation_backup(_settings(source), archive)
    store = RestoreStagingStore()
    staged = inspect_installation_backup(
        archive,
        _settings(target),
        staging_store=store,
    )

    result = apply_installation_restore(
        staged.token,
        _settings(target),
        staging_store=store,
    )

    assert result["status"] == "restored"
    assert result["restart_recommended"] is True
    assert _read_marker(target) == "restored"
    assert "source room" in (target / "autonomy.yaml").read_text()
    snapshots = list(
        (target / "system-backups").glob("config.before-restore-*.zip")
    )
    assert len(snapshots) == 1


def test_installation_status_is_secret_free_and_reports_readiness(
    tmp_path: Path,
) -> None:
    root = _configured_root(tmp_path, "target", "ready")

    result = installation_status(_settings(root))

    assert result["status"] == "ready"
    assert result["persistent_root"] == "/config"
    assert result["policy"] == "ok"
    assert result["database"] == "ok"
    assert result["automatic_updates"] is False
    assert result["first_run"]["ready"] is True
    assert result["migration"]["status"] == "current"
    assert result["updates"]["strategy"] == "container_image"
    assert "secret" not in json.dumps(result)
