import pytest
from fastapi.testclient import TestClient

from house_brain.config import get_settings
from house_brain.main import app

API_KEY = "test-house-brain-api-key"


@pytest.fixture(autouse=True)
def configured_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://homeassistant.test:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "test-home-assistant-token")
    monkeypatch.setenv("HOUSE_BRAIN_API_KEY", API_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_protected_endpoint_rejects_missing_api_key() -> None:
    response = TestClient(app).get("/actions")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_protected_endpoint_rejects_incorrect_api_key() -> None:
    response = TestClient(app).get(
        "/actions",
        headers={"X-API-Key": "incorrect-api-key"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_protected_endpoint_accepts_valid_api_key() -> None:
    response = TestClient(app).get(
        "/actions",
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 405


def test_api_documentation_is_public_and_declares_api_key() -> None:
    client = TestClient(app)

    docs = client.get("/docs")
    schema = client.get("/openapi.json")

    assert docs.status_code == 200
    assert schema.status_code == 200
    assert schema.json()["components"]["securitySchemes"] == {
        "HouseBrainApiKey": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    assert schema.json()["security"] == [{"HouseBrainApiKey": []}]
    assert schema.json()["paths"]["/health"]["get"]["security"] == []


def test_healthcheck_remains_public() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_event_detail_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv(
        "MEMORY_DATABASE_PATH",
        str(tmp_path / "memory.db"),
    )
    get_settings.cache_clear()

    response = TestClient(app).get(
        "/events/missing-event",
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Event not found: missing-event"
    }


def test_execute_event_requires_dedicated_event_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MEMORY_DATABASE_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv(
        "AUTONOMOUS_EVENT_ALLOWLIST",
        "canary_light_control",
    )
    monkeypatch.setenv(
        "AUTONOMOUS_ACTION_ALLOWLIST",
        "light.turn_on:light.sala_uno",
    )
    monkeypatch.setenv("AUTONOMOUS_EXECUTION_ENABLED", "true")
    monkeypatch.delenv(
        "AUTONOMOUS_EXECUTE_EVENT_ALLOWLIST",
        raising=False,
    )
    get_settings.cache_clear()

    response = TestClient(app).post(
        "/agent/events",
        headers={"X-API-Key": API_KEY},
        json={
            "event_type": "canary_light_control",
            "source": "manual_test",
            "mode": "execute",
            "instruction": "Accendi Sala Uno.",
            "context": {"canary": True},
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Autonomous execute event is not allowlisted: "
            "canary_light_control"
        )
    }
