import asyncio

import httpx
import pytest

from house_brain.config import Settings
from house_brain.home_assistant import HomeAssistantClient
from house_brain.service_catalog import ServiceCatalog, ServiceCatalogError

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


def test_missing_service_error_lists_real_domain_services() -> None:
    catalog = ServiceCatalog.from_home_assistant(SERVICES)

    with pytest.raises(ServiceCatalogError) as captured:
        catalog.validate("climate", "set_mode", {})

    error = str(captured.value)
    assert "climate.set_mode" in error
    assert "available services: set_hvac_mode, set_temperature" in error


def test_device_code_is_injected_only_into_prepared_service_data() -> None:
    catalog = ServiceCatalog.from_home_assistant(
        [
            {
                "domain": "alarm_control_panel",
                "services": {
                    "alarm_disarm": {
                        "fields": {"code": {"required": True}},
                    }
                },
            }
        ]
    )
    original: dict[str, object] = {}

    prepared = catalog.prepare(
        "alarm_control_panel",
        "alarm_disarm",
        original,
        supplied_codes=("2468",),
    )

    assert original == {}
    assert prepared == {"code": "2468"}


def test_required_home_assistant_device_code_is_not_optional() -> None:
    catalog = ServiceCatalog.from_home_assistant(
        [
            {
                "domain": "lock",
                "services": {
                    "unlock": {"fields": {"code": {"required": True}}},
                },
            }
        ]
    )

    with pytest.raises(
        ServiceCatalogError,
        match="service parameter is required: code",
    ):
        catalog.prepare("lock", "unlock", {}, supplied_codes=())


def test_entity_code_format_requires_code_for_target_specific_service() -> None:
    services = [
        {
            "domain": "alarm_control_panel",
            "services": {
                "alarm_disarm": {
                    "fields": {"code": {"required": False}},
                }
            },
        }
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/services":
            return httpx.Response(200, json=services)
        assert request.url.path == "/api/states/alarm_control_panel.example_home"
        return httpx.Response(
            200,
            json={
                "entity_id": "alarm_control_panel.example_home",
                "state": "armed_away",
                "attributes": {"code_format": "number"},
                "last_changed": "2026-08-16T12:00:00Z",
                "last_updated": "2026-08-16T12:00:00Z",
            },
        )

    async def prepare() -> None:
        async with HomeAssistantClient(
            _settings(), transport=httpx.MockTransport(handler)
        ) as client:
            await client.prepare_service_data(
                "alarm_control_panel",
                "alarm_disarm",
                "alarm_control_panel.example_home",
                {},
            )

    with pytest.raises(
        ServiceCatalogError,
        match="service parameter is required: code",
    ):
        asyncio.run(prepare())
