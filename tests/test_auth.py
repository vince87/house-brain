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
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_protected_endpoint_rejects_incorrect_api_key() -> None:
    response = TestClient(app).get(
        "/openapi.json",
        headers={"X-API-Key": "incorrect-api-key"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_protected_endpoint_accepts_valid_api_key() -> None:
    response = TestClient(app).get(
        "/openapi.json",
        headers={"X-API-Key": API_KEY},
    )

    assert response.status_code == 200


def test_healthcheck_remains_public() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
