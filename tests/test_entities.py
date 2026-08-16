import os
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from house_brain.config import get_settings
from house_brain.home_assistant import (
    EntityNotFoundError,
    HistoryNotFoundError,
    HomeAssistantEntity,
)
from house_brain.main import app, get_home_assistant_client


def make_entity(
    entity_id: str,
    *,
    state: str = "on",
    hour: int = 8,
) -> HomeAssistantEntity:
    timestamp = datetime(2026, 8, 3, hour, 0, tzinfo=UTC)
    return HomeAssistantEntity(
        entity_id=entity_id,
        state=state,
        attributes={"friendly_name": "Example room light", "brightness": 180},
        last_changed=timestamp,
        last_updated=timestamp,
        context={"id": "test-context"},
    )


class StubHomeAssistantClient:
    async def list_entities_for_configuration(self) -> list[dict[str, str]]:
        return [
            {
                "entity_id": "light.example_room",
                "domain": "light",
                "friendly_name": "Example room light",
                "state": "on",
            }
        ]

    async def get_entity(self, entity_id: str) -> HomeAssistantEntity:
        if entity_id == "light.example_unknown":
            raise EntityNotFoundError(entity_id)
        return make_entity(entity_id)

    async def get_history(
        self,
        entity_id: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[HomeAssistantEntity]:
        return [
            make_entity(entity_id, state="off", hour=7),
            make_entity(entity_id, state="on", hour=8),
        ]

    async def get_state_before(
        self,
        entity_id: str,
        *,
        before: datetime,
        search_start: datetime,
    ) -> HomeAssistantEntity:
        if entity_id == "light.example_unknown":
            raise HistoryNotFoundError(entity_id)
        return make_entity(entity_id, state="off", hour=7)

    async def call_service(
        self,
        domain: str,
        service: str,
        *,
        entity_id: str,
        data: dict[str, Any],
    ) -> dict[str, bool]:
        return {"called": True}


async def override_home_assistant_client() -> StubHomeAssistantClient:
    return StubHomeAssistantClient()


app.dependency_overrides[get_home_assistant_client] = override_home_assistant_client

TEST_API_KEY = "test-house-brain-api-key"
os.environ["HOME_ASSISTANT_URL"] = "http://homeassistant.test:8123"
os.environ["HOME_ASSISTANT_TOKEN"] = "test-home-assistant-token"
os.environ["HOUSE_BRAIN_API_KEY"] = TEST_API_KEY
os.environ["AUTONOMY_POLICY_PATH"] = "autonomy.yaml.example"
get_settings.cache_clear()

client = TestClient(app, headers={"X-API-Key": TEST_API_KEY})


def test_get_entity() -> None:
    response = client.get("/entities/light.example_room")

    assert response.status_code == 200
    assert response.json()["entity_id"] == "light.example_room"
    assert response.json()["state"] == "on"
    assert response.json()["attributes"]["brightness"] == 180


def test_get_unknown_entity() -> None:
    response = client.get("/entities/light.example_unknown")

    assert response.status_code == 404
    assert response.json() == {"detail": "Entity not found: light.example_unknown"}


def test_get_history() -> None:
    response = client.get(
        "/history",
        params={"entity_id": "light.example_room", "minutes": 120},
    )

    assert response.status_code == 200
    assert [item["state"] for item in response.json()] == ["off", "on"]


def test_get_state_before() -> None:
    response = client.get(
        "/state-before",
        params={
            "entity_id": "light.example_room",
            "before": "2026-08-03T08:00:00+02:00",
            "search_hours": 24,
        },
    )

    assert response.status_code == 200
    assert response.json()["state"] == "off"


def test_state_before_requires_timezone() -> None:
    response = client.get(
        "/state-before",
        params={
            "entity_id": "light.example_room",
            "before": "2026-08-03T08:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "before must include a timezone offset"}


def test_action_defaults_to_dry_run() -> None:
    response = client.post(
        "/actions",
        json={
            "domain": "cover",
            "service": "set_cover_position",
            "entity_id": "cover.example_kitchen_shade",
            "data": {"position": 0},
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "simulated"
    assert response.json()["home_assistant_response"] is None


def test_real_action_requires_global_kill_switch() -> None:
    response = client.post(
        "/actions",
        json={
            "domain": "switch",
            "service": "turn_on",
            "entity_id": "switch.example_fan_relay",
            "dry_run": False,
        },
    )

    assert response.status_code == 403
    assert "global kill switch" in response.json()["detail"]


def test_action_rejects_unincluded_entity() -> None:
    response = client.post(
        "/actions",
        json={
            "domain": "lock",
            "service": "unlock",
            "entity_id": "lock.example_door",
        },
    )

    assert response.status_code == 403
    assert "not included" in response.json()["detail"]


def test_action_rejects_invalid_position() -> None:
    response = client.post(
        "/actions",
        json={
            "domain": "cover",
            "service": "set_cover_position",
            "entity_id": "cover.example_kitchen_shade",
            "data": {"position": 101},
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "position must be between 0 and 100"


def test_action_rejects_mismatched_entity_domain() -> None:
    response = client.post(
        "/actions",
        json={
            "domain": "light",
            "service": "turn_on",
            "entity_id": "switch.example_fan_relay",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "entity_id domain must match the requested service domain"
    )
