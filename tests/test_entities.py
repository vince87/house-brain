from datetime import UTC, datetime

from fastapi.testclient import TestClient

from house_brain.home_assistant import (
    EntityNotFoundError,
    HomeAssistantEntity,
)
from house_brain.main import app, get_home_assistant_client


class StubHomeAssistantClient:
    async def get_entity(self, entity_id: str) -> HomeAssistantEntity:
        if entity_id == "light.unknown":
            raise EntityNotFoundError(entity_id)

        timestamp = datetime(2026, 8, 3, 8, 0, tzinfo=UTC)
        return HomeAssistantEntity(
            entity_id=entity_id,
            state="on",
            attributes={"friendly_name": "Luce sala", "brightness": 180},
            last_changed=timestamp,
            last_updated=timestamp,
            context={"id": "test-context"},
        )


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
