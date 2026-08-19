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
    name: str | None = Field(default=None, max_length=100)
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
        if self.name is not None:
            self.name = " ".join(self.name.split()) or None
        if self.code is not None:
            self.code = self.code.strip() or None
        if self.code is not None and not AUTHORIZATION_CODE_PATTERN.fullmatch(
            self.code
        ):
            raise ValueError("authorization code must be 4 to 64 safe characters")
        if not self.code_required and self.code is not None:
            raise ValueError("code requires code_required=true")
        return self


class VisibleEntityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    name: str | None = Field(default=None, max_length=100)

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not ENTITY_ID_PATTERN.fullmatch(normalized):
            raise ValueError("invalid entity_id")
        return normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return " ".join(value.split()) or None if value is not None else None


class AutonomyConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible: list[VisibleEntityInput | str] = Field(
        default_factory=list,
        max_length=5000,
    )
    include: list[ControlledEntityInput] = Field(max_length=5000)
    exclude: list[str] = Field(default_factory=list, max_length=5000)

    @field_validator("exclude")
    @classmethod
    def normalize_exclusions(cls, values: list[str]) -> list[str]:
        return [value.strip().lower() for value in values]


def public_configuration(policy: AutonomyPolicyCatalog) -> dict[str, object]:
    """Expose configuration state without returning authorization codes."""
    return {
        "version": 2,
        "visible": [
            {
                "entity_id": entity_id,
                "name": policy.entity_names.get(entity_id),
            }
            for entity_id in sorted(policy.visible_entities)
            if not policy.visibility.is_hidden(entity_id)
        ],
        "include": [
            {
                "entity_id": entity_id,
                "name": policy.entity_names.get(entity_id),
                "code_required": entity_id in policy.entity_codes,
            }
            for entity_id in sorted(policy.included_entities)
            if not policy.visibility.is_hidden(entity_id)
        ],
    }


def build_policy_yaml(
    request: AutonomyConfigurationInput,
    current: AutonomyPolicyCatalog,
) -> str:
    """Build validated YAML while preserving protected codes left blank."""
    visible: list[object] = []
    visible_seen: set[str] = set()
    for item in request.visible:
        if isinstance(item, str):
            entity_id = item.strip().lower()
            name = None
            if not ENTITY_ID_PATTERN.fullmatch(entity_id):
                raise AutonomyPolicyError(f"Invalid visible entity_id: {entity_id}")
        else:
            entity_id = item.entity_id
            name = item.name
        if entity_id in visible_seen:
            raise AutonomyPolicyError(f"Duplicate visible entity_id: {entity_id}")
        visible_seen.add(entity_id)
        visible.append(
            {"entity_id": entity_id, "name": name}
            if name is not None
            else entity_id
        )

    include: list[object] = []
    seen: set[str] = set()
    for item in request.include:
        if item.entity_id in seen:
            raise AutonomyPolicyError(f"Duplicate included entity_id: {item.entity_id}")
        seen.add(item.entity_id)
        code = item.code or current.entity_codes.get(item.entity_id)
        if item.code_required and code is None:
            raise AutonomyPolicyError(
                f"A new authorization code is required for entity: {item.entity_id}"
            )
        if item.name is None and not item.code_required:
            include.append(item.entity_id)
            continue
        definition = {"entity_id": item.entity_id}
        if item.name is not None:
            definition["name"] = item.name
        if item.code_required:
            definition["code"] = code
        include.append(definition)

    payload = {
        "version": 2,
        "entities": {
            "visible": visible,
            "include": include,
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
