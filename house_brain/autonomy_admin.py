from __future__ import annotations

import os
import shutil
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from house_brain.autonomy import (
    AUTHORIZATION_CODE_PATTERN,
    ENTITY_ID_PATTERN,
    AutonomyPolicyCatalog,
    AutonomyPolicyError,
    parse_autonomy_policy,
)

MAX_POLICY_BACKUPS = 10


class AutonomyPolicyWriteError(RuntimeError):
    """Raised when a validated policy cannot be persisted safely."""


class ControlledEntityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    code_required: bool = False
    code: str | None = Field(default=None, max_length=64, repr=False)

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not ENTITY_ID_PATTERN.fullmatch(normalized):
            raise ValueError("invalid entity_id")
        return normalized

    @model_validator(mode="after")
    def validate_code(self) -> ControlledEntityInput:
        if self.code is not None:
            self.code = self.code.strip() or None
        if self.code is not None and not AUTHORIZATION_CODE_PATTERN.fullmatch(
            self.code
        ):
            raise ValueError("authorization code must be 4 to 64 safe characters")
        if not self.code_required and self.code is not None:
            raise ValueError("code requires code_required=true")
        return self


class AutonomyConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible: list[str] = Field(default_factory=list, max_length=5000)
    include: list[ControlledEntityInput] = Field(max_length=5000)
    exclude: list[str] = Field(max_length=5000)

    @field_validator("visible", "exclude")
    @classmethod
    def normalize_exclusions(cls, values: list[str]) -> list[str]:
        return [value.strip().lower() for value in values]


def public_configuration(policy: AutonomyPolicyCatalog) -> dict[str, object]:
    """Expose configuration state without returning authorization codes."""
    return {
        "version": 2,
        "visible": sorted(policy.visible_entities),
        "include": [
            {
                "entity_id": entity_id,
                "code_required": entity_id in policy.entity_codes,
            }
            for entity_id in sorted(policy.included_entities)
        ],
        "exclude": [
            *sorted(policy.visibility.exclude_entities),
            *policy.visibility.exclude_patterns,
        ],
    }


def build_policy_yaml(
    request: AutonomyConfigurationInput,
    current: AutonomyPolicyCatalog,
) -> str:
    """Build validated YAML while preserving protected codes left blank."""
    include: list[object] = []
    seen: set[str] = set()
    for item in request.include:
        if item.entity_id in seen:
            raise AutonomyPolicyError(f"Duplicate included entity_id: {item.entity_id}")
        seen.add(item.entity_id)
        if not item.code_required:
            include.append(item.entity_id)
            continue
        code = item.code or current.entity_codes.get(item.entity_id)
        if code is None:
            raise AutonomyPolicyError(
                f"A new authorization code is required for entity: {item.entity_id}"
            )
        include.append({"entity_id": item.entity_id, "code": code})

    payload = {
        "version": 2,
        "entities": {
            "visible": list(dict.fromkeys(request.visible)),
            "include": include,
            "exclude": list(dict.fromkeys(request.exclude)),
        },
    }
    content = yaml.safe_dump(
        payload,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    parse_autonomy_policy(content, source="generated autonomy policy")
    return content


def save_policy_with_backup(
    path: str | Path,
    content: str,
    backup_directory: str | Path | None = None,
) -> Path:
    """Atomically replace the policy after creating a timestamped backup."""
    policy_path = Path(path)
    parse_autonomy_policy(content, source="generated autonomy policy")
    if not policy_path.is_file():
        raise AutonomyPolicyWriteError(f"Cannot update autonomy policy: {policy_path}")

    backup_path = (
        Path(backup_directory) if backup_directory is not None else policy_path.parent
    )
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_path / f"{policy_path.name}.backup-{timestamp}"
    temporary_path: Path | None = None
    try:
        backup_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(policy_path, backup)
        os.chmod(backup, 0o600)
        try:
            temporary_path = _atomic_replace(policy_path, content)
        except OSError:
            _replace_bind_mounted_file(policy_path, content, backup)
        try:
            _prune_backups(policy_path, backup_path)
        except OSError:
            pass
        return backup
    except OSError as exc:
        raise AutonomyPolicyWriteError(
            f"Cannot update autonomy policy: {policy_path}"
        ) from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def _atomic_replace(policy_path: Path, content: str) -> Path | None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{policy_path.name}.",
        suffix=".tmp",
        dir=policy_path.parent,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, stat.S_IMODE(policy_path.stat().st_mode))
        os.replace(temporary_path, policy_path)
        return None
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _replace_bind_mounted_file(
    policy_path: Path,
    content: str,
    backup: Path,
) -> None:
    try:
        with policy_path.open("w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        shutil.copyfile(backup, policy_path)
        raise


def _prune_backups(policy_path: Path, backup_path: Path) -> None:
    backups = sorted(
        backup_path.glob(f"{policy_path.name}.backup-*"),
        key=lambda item: item.name,
        reverse=True,
    )
    for stale in backups[MAX_POLICY_BACKUPS:]:
        stale.unlink(missing_ok=True)
