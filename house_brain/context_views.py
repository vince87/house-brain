import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from house_brain.autonomy import ENTITY_ID_PATTERN

VIEW_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")
DOMAIN_PATTERN = re.compile(r"^[a-z0-9_]+$")
MAX_VIEWS = 50
MAX_SELECTORS = 100
MIN_ENTITY_LIMIT = 1
MAX_ENTITY_LIMIT = 100


class ContextViewError(ValueError):
    """Raised when context view configuration is invalid."""


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: yaml.SafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ContextViewError(f"Duplicate context view key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


class ContextView(BaseModel):
    """A policy-narrowing logical view of Home Assistant entities."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    enabled: bool = True
    areas: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    max_entities: int = Field(default=50, ge=MIN_ENTITY_LIMIT, le=MAX_ENTITY_LIMIT)
    include_linked_memories: bool = True

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not VIEW_ID_PATTERN.fullmatch(normalized):
            raise ValueError("view id must use lowercase letters, numbers, _ or -")
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized or len(normalized) > 100:
            raise ValueError("view name must contain 1 to 100 characters")
        if any(ord(character) < 32 for character in normalized):
            raise ValueError("view name contains control characters")
        return normalized

    @field_validator("areas")
    @classmethod
    def validate_areas(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _normalized_selectors(values, label="area")

    @field_validator("domains")
    @classmethod
    def validate_domains(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = _normalized_selectors(values, label="domain", lowercase=True)
        if any(not DOMAIN_PATTERN.fullmatch(value) for value in normalized):
            raise ValueError("view domains must be valid Home Assistant domains")
        return normalized

    @field_validator("entities")
    @classmethod
    def validate_entities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = _normalized_selectors(values, label="entity", lowercase=True)
        if any(not ENTITY_ID_PATTERN.fullmatch(value) for value in normalized):
            raise ValueError("view entities must be valid entity IDs")
        return normalized

    @model_validator(mode="after")
    def require_selectors(self) -> "ContextView":
        if not self.areas and not self.domains and not self.entities:
            raise ValueError("context view must define at least one selector")
        return self


class ContextViewCatalog(BaseModel):
    """Validated context views indexed by stable identifier."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    default_view: str | None = None
    views: tuple[ContextView, ...] = ()

    @model_validator(mode="after")
    def validate_catalog(self) -> "ContextViewCatalog":
        if self.version != 1:
            raise ValueError("context view version must be 1")
        if len(self.views) > MAX_VIEWS:
            raise ValueError(f"context views must contain at most {MAX_VIEWS} items")
        identifiers = [view.id for view in self.views]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("context view IDs must be unique")
        if self.default_view is not None:
            normalized = self.default_view.strip().lower()
            enabled = {view.id for view in self.views if view.enabled}
            if normalized not in enabled:
                raise ValueError("default_view must reference an enabled view")
            self.default_view = normalized
        return self

    @classmethod
    def empty(cls) -> "ContextViewCatalog":
        return cls()

    def get(self, view_id: str, *, include_disabled: bool = False) -> ContextView:
        normalized = view_id.strip().lower()
        for view in self.views:
            if view.id == normalized and (include_disabled or view.enabled):
                return view
        raise ContextViewError(f"Unknown or disabled context view: {normalized}")

    def enabled_views(self) -> tuple[ContextView, ...]:
        return tuple(view for view in self.views if view.enabled)


def parse_context_views(
    content: str,
    *,
    source: str = "context views",
) -> ContextViewCatalog:
    """Parse a context view document with strict keys and duplicate detection."""
    try:
        raw = yaml.load(content, Loader=_UniqueKeyLoader)
    except (yaml.YAMLError, ContextViewError) as exc:
        raise ContextViewError(f"Invalid context view YAML: {source}") from exc
    if raw is None:
        return ContextViewCatalog.empty()
    if not isinstance(raw, dict):
        raise ContextViewError("Context views must be a YAML object")
    unexpected = set(raw) - {"version", "default_view", "views"}
    if unexpected:
        raise ContextViewError(f"Unexpected context view keys: {sorted(unexpected)}")
    raw_views = raw.get("views", [])
    if not isinstance(raw_views, list):
        raise ContextViewError("context views must be a list")
    allowed_view_keys = {
        "id",
        "name",
        "enabled",
        "areas",
        "domains",
        "entities",
        "max_entities",
        "include_linked_memories",
    }
    for index, raw_view in enumerate(raw_views):
        if not isinstance(raw_view, dict):
            raise ContextViewError(f"context view {index} must be an object")
        extra = set(raw_view) - allowed_view_keys
        if extra:
            raise ContextViewError(
                f"Unexpected keys in context view {index}: {sorted(extra)}"
            )
    try:
        return ContextViewCatalog.model_validate(raw)
    except ValidationError as exc:
        raise ContextViewError(f"Invalid context views: {source}") from exc


def load_context_views(path: str | Path) -> ContextViewCatalog:
    """Load optional context views; a missing file preserves current behaviour."""
    view_path = Path(path)
    if not view_path.exists():
        return ContextViewCatalog.empty()
    try:
        content = view_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContextViewError(f"Cannot read context views: {view_path}") from exc
    return parse_context_views(content, source=str(view_path))


def dump_context_views(catalog: ContextViewCatalog) -> str:
    """Serialize a validated catalog to stable, human-readable YAML."""
    payload = catalog.model_dump(mode="json")
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)


def save_context_views(path: str | Path, catalog: ContextViewCatalog) -> None:
    """Atomically replace context view configuration."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(dump_context_views(catalog))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise




def save_context_views_with_backup(
    path: str | Path,
    catalog: ContextViewCatalog,
    backup_directory: str | Path,
) -> Path | None:
    """Save views and retain a recoverable copy of the previous configuration."""
    target = Path(path)
    backup_root = Path(backup_directory)
    backup: Path | None = None
    try:
        backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if target.is_file():
            timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            backup = backup_root / f"{target.name}.backup-{timestamp}"
            shutil.copy2(target, backup)
            os.chmod(backup, 0o600)
        save_context_views(target, catalog)
        backups = sorted(
            backup_root.glob(f"{target.name}.backup-*"),
            key=lambda item: item.name,
            reverse=True,
        )
        for stale in backups[10:]:
            stale.unlink(missing_ok=True)
        return backup
    except OSError as exc:
        raise ContextViewError(f"Cannot update context views: {target}") from exc


def _normalized_selectors(
    values: tuple[str, ...],
    *,
    label: str,
    lowercase: bool = False,
) -> tuple[str, ...]:
    if len(values) > MAX_SELECTORS:
        raise ValueError(
            f"view {label} selectors must contain at most {MAX_SELECTORS} items"
        )
    normalized = tuple(
        (str(value).strip().lower() if lowercase else str(value).strip())
        for value in values
    )
    if any(not value or len(value) > 100 for value in normalized):
        raise ValueError(
            f"view {label} selectors must contain 1 to 100 characters"
        )
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"view {label} selectors must be unique")
    return normalized
