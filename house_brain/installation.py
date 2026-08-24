"""Safe backup, restore and installation lifecycle primitives."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import stat
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from house_brain.autonomy import load_autonomy_policy
from house_brain.config import Settings
from house_brain.context_views import load_context_views
from house_brain.version import APP_VERSION

ARCHIVE_FORMAT_VERSION = 1
INSTALLATION_SCHEMA_VERSION = 1
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 4096
MAX_MEMBER_BYTES = 128 * 1024 * 1024
RESTORE_TOKEN_TTL = timedelta(minutes=10)
LIFECYCLE_BACKUP_DIRECTORY = "system-backups"
_SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


class InstallationLifecycleError(RuntimeError):
    """Raised when a lifecycle operation cannot be completed safely."""


@dataclass(frozen=True)
class StagedRestore:
    token: str
    directory: Path
    created_at: datetime
    expires_at: datetime
    manifest: dict[str, Any]
    files: tuple[dict[str, Any], ...]


class RestoreStagingStore:
    """Hold validated restore uploads for a short, process-local window."""

    def __init__(self) -> None:
        self._items: dict[str, StagedRestore] = {}
        self._lock = threading.RLock()

    def add(
        self,
        directory: Path,
        manifest: dict[str, Any],
        files: tuple[dict[str, Any], ...],
    ) -> StagedRestore:
        now = datetime.now(UTC)
        staged = StagedRestore(
            token=secrets.token_urlsafe(32),
            directory=directory,
            created_at=now,
            expires_at=now + RESTORE_TOKEN_TTL,
            manifest=manifest,
            files=files,
        )
        with self._lock:
            self._cleanup_locked(now)
            self._items[staged.token] = staged
        return staged

    def consume(self, token: str) -> StagedRestore:
        now = datetime.now(UTC)
        with self._lock:
            self._cleanup_locked(now)
            staged = self._items.pop(token, None)
        if staged is None:
            raise InstallationLifecycleError(
                "Restore inspection token is invalid or expired"
            )
        return staged

    def discard(self, staged: StagedRestore) -> None:
        shutil.rmtree(staged.directory, ignore_errors=True)

    def _cleanup_locked(self, now: datetime) -> None:
        expired = [
            token for token, item in self._items.items() if item.expires_at <= now
        ]
        for token in expired:
            item = self._items.pop(token)
            shutil.rmtree(item.directory, ignore_errors=True)


restore_staging_store = RestoreStagingStore()


def installation_config_root(settings: Settings) -> Path:
    """Resolve the one persistent root and reject split-path configuration."""
    database = Path(settings.memory_database_path).expanduser().resolve()
    policy = Path(settings.autonomy_policy_path).expanduser().resolve()
    backups = Path(settings.autonomy_backup_path).expanduser().resolve()
    context_views = Path(settings.context_views_path).expanduser().resolve()
    root = database.parent
    if (
        policy.parent != root
        or backups.parent != root
        or context_views.parent != root
    ):
        raise InstallationLifecycleError(
            "Persistent database, policy, context views and backups "
            "must share one directory"
        )
    return root


def sqlite_integrity(path: Path) -> str:
    """Return SQLite integrity status without creating a missing database."""
    if not path.is_file():
        return "missing"
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as exc:
        raise InstallationLifecycleError(
            "SQLite integrity check could not be completed"
        ) from exc
    if rows == [("ok",)]:
        return "ok"
    raise InstallationLifecycleError("SQLite integrity check failed")


def _sqlite_backup(source: Path, destination: Path) -> None:
    if sqlite_integrity(source) != "ok":
        raise InstallationLifecycleError("SQLite database is not available")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with (
            sqlite3.connect(source) as source_connection,
            sqlite3.connect(destination) as destination_connection,
        ):
            source_connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
            source_connection.backup(destination_connection)
    except sqlite3.Error as exc:
        raise InstallationLifecycleError(
            "SQLite backup could not be completed"
        ) from exc
    sqlite_integrity(destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_payload_path(root: Path, path: Path) -> str:
    return (PurePosixPath("config") / path.relative_to(root).as_posix()).as_posix()


def _is_sqlite_sidecar(path: Path, database: Path) -> bool:
    return path.parent == database.parent and any(
        path.name == database.name + suffix for suffix in _SQLITE_SIDECAR_SUFFIXES
    )


def _is_excluded_source(root: Path, path: Path, database: Path) -> bool:
    if path == database:
        return True
    if _is_sqlite_sidecar(path, database):
        return True
    relative = path.relative_to(root)
    return bool(relative.parts and relative.parts[0] == LIFECYCLE_BACKUP_DIRECTORY)


def create_installation_backup(settings: Settings, destination: Path) -> dict[str, Any]:
    """Create a coherent, checksummed archive of managed persistent state."""
    root = installation_config_root(settings)
    database = Path(settings.memory_database_path).expanduser().resolve()
    policy = Path(settings.autonomy_policy_path).expanduser().resolve()
    policy_backups = Path(settings.autonomy_backup_path).expanduser().resolve()
    if not root.is_dir():
        raise InstallationLifecycleError(
            "Persistent configuration directory is missing"
        )
    if not policy.is_file():
        raise InstallationLifecycleError("Autonomy policy is missing")
    load_autonomy_policy(policy)
    context_views = Path(settings.context_views_path).expanduser().resolve()
    if context_views.is_file():
        load_context_views(context_views)
    sqlite_integrity(database)

    work_directory = Path(tempfile.mkdtemp(prefix="house-brain-backup-"))
    payload_root = work_directory / "config"
    payload_root.mkdir()
    temporary_archive = destination.with_name(destination.name + ".tmp")
    try:
        staged_database = payload_root / database.relative_to(root)
        _sqlite_backup(database, staged_database)
        for suffix in _SQLITE_SIDECAR_SUFFIXES:
            staged_database.with_name(staged_database.name + suffix).unlink(
                missing_ok=True
            )

        for source in sorted(root.rglob("*")):
            if source.is_symlink():
                raise InstallationLifecycleError(
                    "Persistent configuration contains a symbolic link"
                )
            if not source.is_file() or _is_excluded_source(root, source, database):
                continue
            target = payload_root / source.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

        entries: list[dict[str, Any]] = []
        for payload in sorted(payload_root.rglob("*")):
            if not payload.is_file() or _is_sqlite_sidecar(
                payload,
                staged_database,
            ):
                continue
            entries.append(
                {
                    "path": _relative_payload_path(payload_root, payload),
                    "size": payload.stat().st_size,
                    "sha256": _sha256(payload),
                }
            )
        database_member = _relative_payload_path(root, database)
        policy_member = _relative_payload_path(root, policy)
        if database_member not in {entry["path"] for entry in entries}:
            raise InstallationLifecycleError("Backup database payload is missing")
        if policy_member not in {entry["path"] for entry in entries}:
            raise InstallationLifecycleError("Backup policy payload is missing")

        manifest: dict[str, Any] = {
            "format": "house-brain-config-backup",
            "format_version": ARCHIVE_FORMAT_VERSION,
            "house_brain_version": APP_VERSION,
            "installation_schema_version": INSTALLATION_SCHEMA_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "database": database_member,
            "policy": policy_member,
            "policy_backups": (
                _relative_payload_path(root, policy_backups) + "/"
            ),
            "files": entries,
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_archive.unlink(missing_ok=True)
        with zipfile.ZipFile(
            temporary_archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for entry in entries:
                source = work_directory / entry["path"]
                archive.write(source, entry["path"])
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )
        if temporary_archive.stat().st_size > MAX_ARCHIVE_BYTES:
            raise InstallationLifecycleError("Backup archive exceeds the size limit")
        os.replace(temporary_archive, destination)
        return manifest
    finally:
        temporary_archive.unlink(missing_ok=True)
        shutil.rmtree(work_directory, ignore_errors=True)


def _validated_member_path(name: str) -> PurePosixPath:
    if "\\" in name:
        raise InstallationLifecycleError("Archive contains an invalid path")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise InstallationLifecycleError("Archive contains an unsafe path")
    if name != path.as_posix():
        raise InstallationLifecycleError("Archive path is not normalized")
    return path


def _member_is_regular(member: zipfile.ZipInfo) -> bool:
    mode = (member.external_attr >> 16) & 0o170000
    return mode in {0, stat.S_IFREG}


def inspect_installation_backup(
    archive_path: Path,
    settings: Settings,
    *,
    staging_store: RestoreStagingStore = restore_staging_store,
) -> StagedRestore:
    """Validate and stage an uploaded archive without changing persistence."""
    if not archive_path.is_file() or archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise InstallationLifecycleError("Restore archive is missing or too large")
    staging_directory = Path(tempfile.mkdtemp(prefix="house-brain-restore-"))
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_ENTRIES:
                raise InstallationLifecycleError("Restore archive has too many entries")
            names: set[str] = set()
            total_size = 0
            for member in members:
                path = _validated_member_path(member.filename)
                if member.filename in names:
                    raise InstallationLifecycleError(
                        "Restore archive contains duplicate paths"
                    )
                names.add(member.filename)
                if member.is_dir():
                    continue
                if not _member_is_regular(member):
                    raise InstallationLifecycleError(
                        "Restore archive contains a non-regular file"
                    )
                if member.file_size > MAX_MEMBER_BYTES:
                    raise InstallationLifecycleError(
                        "Restore archive member exceeds the size limit"
                    )
                total_size += member.file_size
                if total_size > MAX_ARCHIVE_BYTES:
                    raise InstallationLifecycleError(
                        "Restore archive expands beyond the size limit"
                    )
                if path != PurePosixPath("manifest.json") and (
                    not path.parts or path.parts[0] != "config"
                ):
                    raise InstallationLifecycleError(
                        "Restore archive contains an unmanaged path"
                    )

            if "manifest.json" not in names:
                raise InstallationLifecycleError("Restore manifest is missing")
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
                raise InstallationLifecycleError(
                    "Restore manifest is invalid"
                ) from exc
            if (
                not isinstance(manifest, dict)
                or manifest.get("format") != "house-brain-config-backup"
                or manifest.get("format_version") != ARCHIVE_FORMAT_VERSION
                or not isinstance(manifest.get("files"), list)
            ):
                raise InstallationLifecycleError(
                    "Restore archive format is not supported"
                )

            declared: dict[str, dict[str, Any]] = {}
            for raw_entry in manifest["files"]:
                if not isinstance(raw_entry, dict):
                    raise InstallationLifecycleError(
                        "Restore manifest entry is invalid"
                    )
                path = _validated_member_path(str(raw_entry.get("path", "")))
                name = path.as_posix()
                if path.parts[0] != "config" or name in declared:
                    raise InstallationLifecycleError("Restore manifest path is invalid")
                size = raw_entry.get("size")
                checksum = raw_entry.get("sha256")
                if (
                    not isinstance(size, int)
                    or size < 0
                    or not isinstance(checksum, str)
                    or re.fullmatch(r"[0-9a-f]{64}", checksum) is None
                ):
                    raise InstallationLifecycleError(
                        "Restore manifest metadata is invalid"
                    )
                declared[name] = {
                    "path": name,
                    "size": size,
                    "sha256": checksum,
                }
            payload_names = {
                member.filename
                for member in members
                if not member.is_dir() and member.filename != "manifest.json"
            }
            if payload_names != set(declared):
                raise InstallationLifecycleError(
                    "Restore payload does not match its manifest"
                )

            for name, entry in declared.items():
                target = staging_directory / name
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                written = 0
                with archive.open(name) as source, target.open("wb") as output:
                    while block := source.read(1024 * 1024):
                        written += len(block)
                        if written > entry["size"]:
                            raise InstallationLifecycleError(
                                "Restore member size does not match its manifest"
                            )
                        digest.update(block)
                        output.write(block)
                if written != entry["size"] or digest.hexdigest() != entry["sha256"]:
                    raise InstallationLifecycleError(
                        "Restore member checksum validation failed"
                    )

        database_member = str(manifest.get("database", ""))
        policy_member = str(manifest.get("policy", ""))
        if database_member not in declared or policy_member not in declared:
            raise InstallationLifecycleError(
                "Restore manifest does not identify database and policy"
            )
        sqlite_integrity(staging_directory / database_member)
        load_autonomy_policy(staging_directory / policy_member)
        context_member = str(
            PurePosixPath(policy_member).with_name("context-views.yaml")
        )
        if context_member in declared:
            load_context_views(staging_directory / context_member)
        files = tuple(declared[name] for name in sorted(declared))
        return staging_store.add(staging_directory, manifest, files)
    except zipfile.BadZipFile as exc:
        shutil.rmtree(staging_directory, ignore_errors=True)
        raise InstallationLifecycleError("Restore archive is not a valid ZIP") from exc
    except Exception:
        shutil.rmtree(staging_directory, ignore_errors=True)
        raise


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _apply_staged_files(staged: StagedRestore, settings: Settings) -> None:
    root = installation_config_root(settings)
    database = Path(settings.memory_database_path).expanduser().resolve()
    database_member = str(staged.manifest["database"])
    policy_member = str(staged.manifest["policy"])
    staged_database = staged.directory / database_member
    staged_policy = staged.directory / policy_member

    load_autonomy_policy(staged_policy)
    context_member = str(
        PurePosixPath(policy_member).with_name("context-views.yaml")
    )
    if context_member in {str(entry["path"]) for entry in staged.files}:
        load_context_views(staged.directory / context_member)
    sqlite_integrity(staged_database)
    for entry in staged.files:
        member = str(entry["path"])
        relative = PurePosixPath(member).relative_to("config")
        destination = root.joinpath(*relative.parts).resolve()
        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise InstallationLifecycleError(
                "Restore destination escaped the persistent directory"
            ) from exc
        source = staged.directory / member
        if member == database_member:
            _sqlite_backup(source, database)
        else:
            _atomic_copy(source, destination)
    load_autonomy_policy(Path(settings.autonomy_policy_path))
    context_views = Path(settings.context_views_path)
    if context_views.is_file():
        load_context_views(context_views)
    sqlite_integrity(database)


def apply_installation_restore(
    token: str,
    settings: Settings,
    *,
    staging_store: RestoreStagingStore = restore_staging_store,
) -> dict[str, Any]:
    """Apply a staged restore with a pre-restore snapshot and rollback."""
    staged = staging_store.consume(token)
    root = installation_config_root(settings)
    backup_directory = root / LIFECYCLE_BACKUP_DIRECTORY
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    pre_restore = backup_directory / f"config.before-restore-{timestamp}.zip"
    try:
        create_installation_backup(settings, pre_restore)
        try:
            _apply_staged_files(staged, settings)
        except Exception as apply_error:
            rollback_descriptor, rollback_name = tempfile.mkstemp(suffix=".zip")
            os.close(rollback_descriptor)
            rollback_archive = Path(rollback_name)
            rollback_directory: Path | None = None
            try:
                shutil.copyfile(pre_restore, rollback_archive)
                rollback = inspect_installation_backup(
                    rollback_archive,
                    settings,
                    staging_store=RestoreStagingStore(),
                )
                rollback_directory = rollback.directory
                _apply_staged_files(rollback, settings)
            except Exception as rollback_error:
                raise InstallationLifecycleError(
                    "Restore failed and automatic rollback also failed"
                ) from rollback_error
            finally:
                rollback_archive.unlink(missing_ok=True)
                if rollback_directory is not None:
                    shutil.rmtree(rollback_directory, ignore_errors=True)
            raise InstallationLifecycleError(
                "Restore failed; the pre-restore snapshot was reapplied"
            ) from apply_error
        return {
            "status": "restored",
            "files_restored": len(staged.files),
            "pre_restore_backup": pre_restore.name,
            "restart_recommended": True,
        }
    finally:
        staging_store.discard(staged)


def installation_status(settings: Settings) -> dict[str, Any]:
    """Return local lifecycle readiness without exposing secrets."""
    root = installation_config_root(settings)
    database = Path(settings.memory_database_path).expanduser().resolve()
    policy = Path(settings.autonomy_policy_path).expanduser().resolve()
    policy_backups = Path(settings.autonomy_backup_path).expanduser().resolve()
    context_views = Path(settings.context_views_path).expanduser().resolve()
    backup_directory = root / LIFECYCLE_BACKUP_DIRECTORY

    def persistent_path(path: Path) -> str:
        return str(PurePosixPath("/config") / path.relative_to(root).as_posix())
    policy_status = "missing"
    if policy.is_file():
        try:
            load_autonomy_policy(policy)
            policy_status = "ok"
        except Exception:
            policy_status = "invalid"
    database_status = "missing"
    if database.is_file():
        try:
            database_status = sqlite_integrity(database)
        except InstallationLifecycleError:
            database_status = "invalid"
    writable = root.is_dir() and os.access(root, os.R_OK | os.W_OK | os.X_OK)
    ready = writable and policy_status == "ok" and database_status == "ok"
    readiness = {
        "runtime_configuration": "ok",
        "persistent_root": "ok" if writable else "attention_required",
        "policy": policy_status,
        "database": database_status,
        "api_authentication": "configured" if settings.api_key else "missing",
        "home_assistant": "configured",
        "llm_provider": settings.llm_provider,
    }
    return {
        "status": "ready" if ready else "attention_required",
        "version": APP_VERSION,
        "first_run": {
            "ready": ready,
            "checks": readiness,
            "execution_enabled": settings.autonomous_execution_enabled,
        },
        "migration": {
            "schema_version": INSTALLATION_SCHEMA_VERSION,
            "status": "current",
            "pending": [],
            "automatic_rollback_snapshot": True,
        },
        "updates": {
            "strategy": "container_image",
            "automatic": False,
            "status": "manual",
            "restart_managed_by_house_brain": False,
        },
        "installation_schema_version": INSTALLATION_SCHEMA_VERSION,
        "persistent_root": "/config",
        "persistent_paths": {
            "root": "/config",
            "database": persistent_path(database),
            "policy": persistent_path(policy),
            "policy_backups": persistent_path(policy_backups),
            "context_views": persistent_path(context_views),
            "lifecycle_backups": persistent_path(backup_directory),
        },
        "persistent_root_access": "read_write" if writable else "unavailable",
        "policy": policy_status,
        "database": database_status,
        "pre_restore_backups": (
            len(list(backup_directory.glob("config.before-restore-*.zip")))
            if backup_directory.is_dir()
            else 0
        ),
        "automatic_updates": False,
        "container_restart_control": False,
    }
