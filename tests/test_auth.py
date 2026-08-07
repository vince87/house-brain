from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from house_brain.autonomy import AutonomyPolicyError
from house_brain.config import DEPRECATED_AUTONOMY_VARIABLES, get_settings
from house_brain.main import app

API_KEY = "test-house-brain-api-key"


@pytest.fixture(autouse=True)
def configured_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    for name in DEPRECATED_AUTONOMY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    policy_path = tmp_path / "autonomy.yaml"
    policy_path.write_text(
        "version: 2\nentities:\n  include: [light.example_living_room]\n"
        "  exclude: []\n"
    )
    monkeypatch.setenv("AUTONOMY_POLICY_PATH", str(policy_path))
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


def test_protected_endpoint_accepts_bearer_api_key() -> None:
    response = TestClient(app).get(
        "/auth/check",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_mcp_endpoint_rejects_missing_api_key() -> None:
    response = TestClient(app).post("/mcp/")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


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


def test_execute_event_requires_global_kill_switch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("MEMORY_DATABASE_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setenv("AUTONOMOUS_EXECUTION_ENABLED", "false")
    get_settings.cache_clear()

    response = TestClient(app).post(
        "/agent/events",
        headers={"X-API-Key": API_KEY},
        json={
            "event_type": "canary_light_control",
            "source": "manual_test",
            "mode": "execute",
            "instruction": "Accendi Example Living Room.",
            "context": {"canary": True},
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Autonomous execution is disabled"
    }


def test_invalid_policy_prevents_application_startup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    policy_path = tmp_path / "invalid.yaml"
    policy_path.write_text("version: 1\nevents: {}\n")
    monkeypatch.setenv("AUTONOMY_POLICY_PATH", str(policy_path))
    get_settings.cache_clear()

    with pytest.raises(
        AutonomyPolicyError,
        match="version must be 2",
    ):
        with TestClient(app):
            pass
