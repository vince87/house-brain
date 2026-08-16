from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ServiceCatalogError(ValueError):
    """Raised when a service call contradicts Home Assistant metadata."""


@dataclass(frozen=True)
class ServiceField:
    required: bool = False
    allowed: tuple[Any, ...] = ()
    minimum: float | None = None
    maximum: float | None = None

    def validate(self, key: str, value: Any) -> None:
        if self.allowed and value not in self.allowed:
            raise ServiceCatalogError(
                f"Home Assistant service parameter value is not allowed: {key}"
            )
        if self.minimum is not None or self.maximum is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ServiceCatalogError(
                    f"Home Assistant service parameter must be numeric: {key}"
                )
            if self.minimum is not None and value < self.minimum:
                raise ServiceCatalogError(
                    f"Home Assistant service parameter is below minimum: {key}"
                )
            if self.maximum is not None and value > self.maximum:
                raise ServiceCatalogError(
                    f"Home Assistant service parameter is above maximum: {key}"
                )


@dataclass(frozen=True)
class ServiceDefinition:
    domain: str
    service: str
    fields: dict[str, ServiceField]

    def validate(self, data: dict[str, Any]) -> None:
        unknown = sorted(set(data) - set(self.fields))
        if unknown:
            raise ServiceCatalogError(
                "Home Assistant service parameter is not supported: "
                + ", ".join(unknown)
            )
        missing = sorted(
            key
            for key, field in self.fields.items()
            if field.required and key not in data
        )
        if missing:
            raise ServiceCatalogError(
                "Home Assistant service parameter is required: " + ", ".join(missing)
            )
        for key, value in data.items():
            self.fields[key].validate(key, value)

    def compact(self) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        for key, field in sorted(self.fields.items()):
            description: dict[str, Any] = {"required": field.required}
            if field.allowed:
                description["allowed"] = list(field.allowed)
            if field.minimum is not None:
                description["min"] = field.minimum
            if field.maximum is not None:
                description["max"] = field.maximum
            fields[key] = description
        return {"domain": self.domain, "service": self.service, "fields": fields}


class ServiceCatalog:
    def __init__(self, definitions: dict[tuple[str, str], ServiceDefinition]) -> None:
        self._definitions = definitions

    @classmethod
    def from_home_assistant(cls, payload: object) -> ServiceCatalog:
        if not isinstance(payload, list):
            raise ServiceCatalogError("Invalid Home Assistant service catalog")
        definitions: dict[tuple[str, str], ServiceDefinition] = {}
        for raw_domain in payload:
            if not isinstance(raw_domain, dict):
                continue
            domain = raw_domain.get("domain")
            services = raw_domain.get("services")
            if not isinstance(domain, str) or not isinstance(services, dict):
                continue
            for service, raw_service in services.items():
                if not isinstance(service, str) or not isinstance(raw_service, dict):
                    continue
                raw_fields = raw_service.get("fields", {})
                fields = (
                    {
                        key: _parse_field(value)
                        for key, value in raw_fields.items()
                        if isinstance(key, str) and isinstance(value, dict)
                    }
                    if isinstance(raw_fields, dict)
                    else {}
                )
                definitions[(domain, service)] = ServiceDefinition(
                    domain=domain,
                    service=service,
                    fields=fields,
                )
        if not definitions:
            raise ServiceCatalogError("Home Assistant service catalog is empty")
        return cls(definitions)

    def validate(self, domain: str, service: str, data: dict[str, Any]) -> None:
        definition = self._definitions.get((domain, service))
        if definition is None:
            available = sorted(
                item_service
                for item_domain, item_service in self._definitions
                if item_domain == domain
            )
            detail = (
                "; available services: " + ", ".join(available[:30])
                if available
                else "; no services are exposed for this domain"
            )
            raise ServiceCatalogError(
                f"Home Assistant service does not exist: {domain}.{service}{detail}"
            )
        definition.validate(data)

    def prepare(
        self,
        domain: str,
        service: str,
        data: dict[str, Any],
        *,
        supplied_codes: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Inject a user-supplied device code without exposing it to the model."""
        definition = self._definitions.get((domain, service))
        if definition is None:
            self.validate(domain, service, data)
            raise AssertionError("service validation did not raise")

        prepared = dict(data)
        if "code" in definition.fields and "code" not in prepared and supplied_codes:
            prepared["code"] = supplied_codes[-1]
        definition.validate(prepared)
        return prepared

    def accepts_field(self, domain: str, service: str, field: str) -> bool:
        definition = self._definitions.get((domain, service))
        return definition is not None and field in definition.fields

    def list(self, domain: str | None = None) -> list[dict[str, Any]]:
        return [
            definition.compact()
            for (item_domain, _), definition in sorted(self._definitions.items())
            if domain is None or item_domain == domain
        ]


def _parse_field(raw: dict[str, Any]) -> ServiceField:
    selector = raw.get("selector")
    selector = selector if isinstance(selector, dict) else {}
    allowed: tuple[Any, ...] = ()
    select = selector.get("select")
    if isinstance(select, dict) and isinstance(select.get("options"), list):
        values = []
        for option in select["options"]:
            if isinstance(option, dict) and "value" in option:
                values.append(option["value"])
            elif isinstance(option, (str, int, float, bool)):
                values.append(option)
        allowed = tuple(values)
    number = selector.get("number")
    number = number if isinstance(number, dict) else {}
    minimum = number.get("min")
    maximum = number.get("max")
    return ServiceField(
        required=raw.get("required") is True,
        allowed=allowed,
        minimum=float(minimum) if isinstance(minimum, (int, float)) else None,
        maximum=float(maximum) if isinstance(maximum, (int, float)) else None,
    )
