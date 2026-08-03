from datetime import UTC, datetime

from fastapi.testclient import TestClient

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
        attributes={"friendly_name": "Luce sala", "brightness": 180},
        last_changed=timestamp,
        last_updated=timestamp,
        context={"id": "test-context"},
    )


class StubHomeAssistantClient:
    async def get_entity(self, entity_id: str) -> HomeAssistantEntity:
        if entity_id == "light.unknown":
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
        if entity_id == "light.unknown":
            raise HistoryNotFoundError(entity_id)
        return make_entity(entity_id, state="off", hour=7)


async def override_home_assistant_client() -> StubHomeAssistantClient:
    return StubHomeAssistantClient()


app.dependency_overrides[get_home_assistant_client] = (
    override_home_assistant_client
)
client = TestClient(app)


def test_get_entity() -> None:
    response = client.get("/entities/light.sala")

    assert response.status_code == 200
    assert response.json()["entity_id"] == "light.sala"
    assert response.json()["state"] == "on"
    assert response.json()["attributes"]["brightness"] == 180


def test_get_unknown_entity() -> None:
    response = client.get("/entities/light.unknown")

    assert response.status_code == 404
    assert response.json() == {"detail": "Entity not found: light.unknown"}


def test_get_history() -> None:
    response = client.get(
        "/history",
        params={"entity_id": "light.sala", "minutes": 120},
    )

    assert response.status_code == 200
    assert [item["state"] for item in response.json()] == ["off", "on"]


def test_get_state_before() -> None:
    response = client.get(
        "/state-before",
        params={
            "entity_id": "light.sala",
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
            "entity_id": "light.sala",
            "before": "2026-08-03T08:00:00",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "before must include a timezone offset"
    }
