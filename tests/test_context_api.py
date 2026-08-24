import pytest
from fastapi.testclient import TestClient

from house_brain.config import get_settings
from house_brain.home_context import HomeContextItem, HomeContextPage
from house_brain.main import app, get_home_assistant_client


class StubContextClient:
    async def get_home_context(self, **kwargs: object) -> HomeContextPage:
        assert kwargs == {
            "domains": {"light"},
            "areas": {"Example Kitchen"},
            "query": "ceiling",
            "controllable_only": True,
            "limit": 10,
            "offset": 0,
        }
        return HomeContextPage(
            items=[
                HomeContextItem(
                    entity_id="light.example_kitchen",
                    domain="light",
                    name="Example Kitchen Light",
                    state="off",
                    effective_state="off",
                    last_changed="2026-08-24T08:00:00+00:00",
                    area_id="example_kitchen",
                    area_name="Example Kitchen",
                    device_id="device-1",
                    device_name="Example Ceiling Device",
                    controllable=True,
                    selection_reasons=[
                        "policy_visible",
                        "policy_controllable",
                        "area_match",
                    ],
                )
            ],
            offset=0,
            returned=1,
            total=1,
            truncated=False,
            requested_areas=["Example Kitchen"],
            requested_domains=["light"],
            query="ceiling",
        )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://homeassistant.test:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "secret")
    monkeypatch.setenv("HOUSE_BRAIN_API_KEY", "context-api-key")
    get_settings.cache_clear()

    async def override() -> StubContextClient:
        return StubContextClient()

    previous = app.dependency_overrides.get(get_home_assistant_client)
    app.dependency_overrides[get_home_assistant_client] = override
    try:
        yield TestClient(app, headers={"X-API-Key": "context-api-key"})
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_home_assistant_client, None)
        else:
            app.dependency_overrides[get_home_assistant_client] = previous
        get_settings.cache_clear()


def test_context_endpoint_exposes_bounded_relationship_view(
    client: TestClient,
) -> None:
    response = client.get(
        "/context",
        params=[
            ("domains", "light"),
            ("areas", "Example Kitchen"),
            ("query", "ceiling"),
            ("controllable_only", "true"),
            ("limit", "10"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["entity_id"] == "light.example_kitchen"
    assert payload["items"][0]["area_name"] == "Example Kitchen"
    assert payload["items"][0]["selection_reasons"] == [
        "policy_visible",
        "policy_controllable",
        "area_match",
    ]


def test_context_endpoint_rejects_invalid_domains(client: TestClient) -> None:
    response = client.get("/context", params={"domains": "light.example"})

    assert response.status_code == 422
    assert response.json() == {
        "detail": "domains must contain at most 8 valid domains"
    }

