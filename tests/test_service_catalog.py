import asyncio

import httpx
import pytest

from house_brain.config import Settings
from house_brain.home_assistant import HomeAssistantClient
from house_brain.service_catalog import ServiceCatalogError

SERVICES = [
    {
        "domain": "climate",
        "services": {
            "set_hvac_mode": {
                "fields": {
                    "hvac_mode": {
                        "required": True,
                        "selector": {"select": {"options": ["off", "heat"]}},
                    }
                }
            },
            "set_temperature": {
                "fields": {
                    "temperature": {"selector": {"number": {"min": 10, "max": 30}}}
                }
            },
        },
    }
]


def _settings() -> Settings:
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
    )


def test_service_catalog_is_cached_and_exposes_constraints() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        assert request.url.path == "/api/services"
        calls += 1
        return httpx.Response(200, json=SERVICES)

    async def read() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        async with HomeAssistantClient(
            _settings(), transport=httpx.MockTransport(handler)
        ) as client:
            return await client.list_services("climate"), await client.list_services(
                "climate"
            )

    first, second = asyncio.run(read())
    assert first == second
    assert calls == 1
    assert first[0]["domain"] == "climate"


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("set_hvac_mode", {}),
        ("set_hvac_mode", {"hvac_mode": "cool"}),
        ("set_temperature", {"temperature": 31}),
        ("set_temperature", {"unexpected": 20}),
        ("missing", {}),
    ],
)
def test_service_catalog_rejects_invalid_calls(
    service: str,
    data: dict[str, object],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=SERVICES)

    async def validate() -> None:
        async with HomeAssistantClient(
            _settings(), transport=httpx.MockTransport(handler)
        ) as client:
            await client.validate_service_call("climate", service, data)

    with pytest.raises(ServiceCatalogError):
        asyncio.run(validate())


def test_service_catalog_accepts_valid_call() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=SERVICES)

    async def validate() -> None:
        async with HomeAssistantClient(
            _settings(), transport=httpx.MockTransport(handler)
        ) as client:
            await client.validate_service_call(
                "climate", "set_hvac_mode", {"hvac_mode": "heat"}
            )

    asyncio.run(validate())
