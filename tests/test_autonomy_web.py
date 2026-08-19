from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from house_brain.autonomy import load_autonomy_policy
from house_brain.config import get_settings
from house_brain.main import app, get_home_assistant_client

API_KEY = "test-autonomy-admin-key"


class StubHomeAssistantClient:
    async def hidden_entity_ids(self) -> frozenset[str]:
        return frozenset()

    async def list_entities_for_configuration(self) -> list[dict[str, str]]:
        return [
            {
                "entity_id": "light.example_room",
                "domain": "light",
                "friendly_name": "Example Room",
                "state": "on",
            },
        ]


async def override_home_assistant_client() -> StubHomeAssistantClient:
    return StubHomeAssistantClient()


@pytest.fixture
def configured_admin(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    policy_path = tmp_path / "autonomy.yaml"
    policy_path.write_text(
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
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://homeassistant.test:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "secret")
    monkeypatch.setenv("HOUSE_BRAIN_API_KEY", API_KEY)
    monkeypatch.setenv("AUTONOMY_POLICY_PATH", str(policy_path))
    monkeypatch.setenv("AUTONOMY_BACKUP_PATH", str(tmp_path / "backups"))
    monkeypatch.setenv("HOUSE_BRAIN_LANGUAGE", "en")
    get_settings.cache_clear()
    previous = app.dependency_overrides.get(get_home_assistant_client)
    app.dependency_overrides[get_home_assistant_client] = override_home_assistant_client
    yield policy_path
    if previous is None:
        app.dependency_overrides.pop(get_home_assistant_client, None)
    else:
        app.dependency_overrides[get_home_assistant_client] = previous
    get_settings.cache_clear()


def test_autonomy_shell_is_public_localized_and_contains_no_secret(
    configured_admin: Path,
) -> None:
    response = TestClient(app).get("/autonomy")

    assert response.status_code == 200
    assert '<html lang="en">' in response.text
    assert "Autonomy configuration" in response.text
    assert "2468" not in response.text
    assert "innerHTML" not in response.text


def test_autonomy_data_requires_authentication(configured_admin: Path) -> None:
    response = TestClient(app).get("/admin/autonomy")

    assert response.status_code == 401


def test_autonomy_data_never_returns_configured_code(
    configured_admin: Path,
) -> None:
    response = TestClient(app).get(
        "/admin/autonomy",
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 200
    assert "2468" not in response.text
    assert response.json()["configuration"]["visible"] == [
        {
            "entity_id": "sensor.example_temperature",
            "name": "Example Temperature",
        }
    ]
    assert response.json()["configuration"]["include"][1] == {
        "entity_id": "lock.example_door",
        "name": None,
        "code_required": True,
    }
    assert response.json()["entities"] == [
        {
            "entity_id": "light.example_room",
            "domain": "light",
            "friendly_name": "Example Room",
            "state": "on",
        },
        {
            "entity_id": "lock.example_door",
            "domain": "lock",
            "friendly_name": "lock.example_door",
            "state": "unavailable",
        },
        {
            "entity_id": "sensor.example_temperature",
            "domain": "sensor",
            "friendly_name": "sensor.example_temperature",
            "state": "unavailable",
        },
    ]


def test_autonomy_update_preserves_blank_existing_code_and_creates_backup(
    configured_admin: Path,
) -> None:
    response = TestClient(app).put(
        "/admin/autonomy",
        headers={"X-API-Key": API_KEY},
        json={
            "include": [
                {
                    "entity_id": "lock.example_door",
                    "code_required": True,
                    "code": None,
                }
            ],
            "exclude": ["sensor.*_diagnostic"],
        },
    )

    assert response.status_code == 200
    assert response.json()["backup_created"] is True
    assert load_autonomy_policy(configured_admin).entity_codes == {
        "lock.example_door": "2468"
    }
    assert list((configured_admin.parent / "backups").glob("autonomy.yaml.backup-*"))


def test_invalid_update_does_not_replace_policy(configured_admin: Path) -> None:
    original = configured_admin.read_text()

    response = TestClient(app).put(
        "/admin/autonomy",
        headers={"X-API-Key": API_KEY},
        json={
            "visible": ["light.example_room"],
            "include": [{"entity_id": "light.example_room"}],
            "exclude": [],
        },
    )

    assert response.status_code == 422
    assert configured_admin.read_text() == original
    assert not list(
        (configured_admin.parent / "backups").glob("autonomy.yaml.backup-*")
    )


def test_autonomy_data_does_not_reintroduce_hidden_configured_entity(
    configured_admin: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def hidden_entity_ids(
        self: StubHomeAssistantClient,
    ) -> frozenset[str]:
        return frozenset({"lock.example_door"})

    monkeypatch.setattr(
        StubHomeAssistantClient,
        "hidden_entity_ids",
        hidden_entity_ids,
    )
    response = TestClient(app).get(
        "/admin/autonomy",
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 200
    assert [item["entity_id"] for item in response.json()["entities"]] == [
        "light.example_room",
        "sensor.example_temperature",
    ]


def test_autonomy_uses_shared_blue_interface_theme(
    configured_admin: Path,
) -> None:
    response = TestClient(app).get("/autonomy")

    assert "--bg:#0b1020" in response.text
    assert "--panel:#151d33" in response.text
    assert "--accent:#75a7ff" in response.text
    assert "#62d99b" not in response.text
