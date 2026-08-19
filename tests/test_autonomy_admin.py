from pathlib import Path
from stat import S_IMODE

import pytest

import house_brain.autonomy_admin as admin_module
from house_brain.autonomy import AutonomyPolicyError, load_autonomy_policy
from house_brain.autonomy_admin import (
    AutonomyConfigurationInput,
    AutonomyPolicyWriteError,
    build_policy_yaml,
    public_configuration,
    save_policy_with_backup,
)


def _policy(path: Path):
    path.write_text(
        """
version: 2
entities:
  visible:
    - entity_id: sensor.example_temperature
      name: Example Temperature
  include:
    - light.example_room
    - entity_id: lock.example_door
      code: "2468"
  exclude:
    - sensor.*_diagnostic
""".lstrip()
    )
    return load_autonomy_policy(path)


def test_public_configuration_never_exposes_codes(tmp_path: Path) -> None:
    policy = _policy(tmp_path / "autonomy.yaml")

    result = public_configuration(policy)

    assert "2468" not in str(result)
    assert result["visible"] == [
        {
            "entity_id": "sensor.example_temperature",
            "name": "Example Temperature",
        }
    ]
    assert result["include"] == [
        {"entity_id": "light.example_room", "name": None, "code_required": False},
        {"entity_id": "lock.example_door", "name": None, "code_required": True},
    ]


def test_blank_code_preserves_existing_secret(tmp_path: Path) -> None:
    policy = _policy(tmp_path / "autonomy.yaml")
    request = AutonomyConfigurationInput.model_validate(
        {
            "include": [
                {
                    "entity_id": "lock.example_door",
                    "code_required": True,
                    "code": None,
                }
            ],
            "exclude": [],
        }
    )

    generated = build_policy_yaml(request, policy)
    saved = tmp_path / "generated.yaml"
    saved.write_text(generated)

    assert load_autonomy_policy(saved).entity_codes == {"lock.example_door": "2468"}


def test_new_protected_entity_requires_new_code(tmp_path: Path) -> None:
    policy = _policy(tmp_path / "autonomy.yaml")
    request = AutonomyConfigurationInput.model_validate(
        {
            "include": [
                {
                    "entity_id": "switch.example_relay",
                    "code_required": True,
                }
            ],
            "exclude": [],
        }
    )

    with pytest.raises(AutonomyPolicyError, match="new authorization code"):
        build_policy_yaml(request, policy)


def test_save_is_validated_and_creates_backup(tmp_path: Path) -> None:
    path = tmp_path / "autonomy.yaml"
    current = _policy(path)
    request = AutonomyConfigurationInput.model_validate(
        {
            "include": [
                {
                    "entity_id": "switch.example_relay",
                    "code_required": False,
                }
            ],
            "exclude": ["sensor.*_diagnostic"],
        }
    )
    generated = build_policy_yaml(request, current)

    backup = save_policy_with_backup(path, generated)

    assert backup.is_file()
    assert "lock.example_door" in backup.read_text()
    updated = load_autonomy_policy(path)
    assert updated.included_entities == frozenset({"switch.example_relay"})


def test_generated_policy_keeps_exclude_as_absolute_override(
    tmp_path: Path,
) -> None:
    policy = _policy(tmp_path / "autonomy.yaml")
    request = AutonomyConfigurationInput.model_validate(
        {
            "visible": ["sensor.example_temperature"],
            "include": [
                {
                    "entity_id": "light.example_room",
                    "code_required": False,
                }
            ],
            "exclude": ["light.*"],
        }
    )

    generated = build_policy_yaml(request, policy)
    saved = tmp_path / "generated.yaml"
    saved.write_text(generated)
    updated = load_autonomy_policy(saved)

    assert updated.visibility.is_hidden("light.example_room")
    assert not updated.visibility.is_hidden("sensor.example_temperature")

def test_duplicate_included_entity_is_rejected(tmp_path: Path) -> None:
    policy = _policy(tmp_path / "autonomy.yaml")
    request = AutonomyConfigurationInput.model_validate(
        {
            "include": [
                {"entity_id": "light.example_room"},
                {"entity_id": "light.example_room"},
            ],
            "exclude": [],
        }
    )

    with pytest.raises(AutonomyPolicyError, match="Duplicate included"):
        build_policy_yaml(request, policy)


def test_policy_backups_are_bounded(tmp_path: Path) -> None:
    path = tmp_path / "autonomy.yaml"
    _policy(path)
    content = path.read_text()

    for _ in range(12):
        save_policy_with_backup(path, content)

    assert len(list(tmp_path.glob("autonomy.yaml.backup-*"))) == 10


def test_missing_policy_cannot_be_created_by_admin(tmp_path: Path) -> None:
    missing = tmp_path / "autonomy.yaml"
    content = "version: 2\nentities:\n  include: []\n  exclude: []\n"

    with pytest.raises(AutonomyPolicyWriteError, match="Cannot update"):
        save_policy_with_backup(missing, content)


def test_bind_mount_fallback_writes_file_and_keeps_backup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "autonomy.yaml"
    current = _policy(path)
    request = AutonomyConfigurationInput.model_validate(
        {
            "include": [{"entity_id": "switch.example_relay"}],
            "exclude": [],
        }
    )
    content = build_policy_yaml(request, current)
    backup_directory = tmp_path / "backups"

    def fail_atomic(_path: Path, _content: str) -> None:
        raise OSError("simulated bind mount")

    monkeypatch.setattr(admin_module, "_atomic_replace", fail_atomic)

    backup = save_policy_with_backup(path, content, backup_directory)

    assert backup.parent == backup_directory
    assert S_IMODE(backup.stat().st_mode) == 0o600
    assert load_autonomy_policy(path).included_entities == frozenset(
        {"switch.example_relay"}
    )
    assert "lock.example_door" in backup.read_text()
