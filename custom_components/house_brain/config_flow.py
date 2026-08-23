"""Configuration flow for the House Brain integration."""

from __future__ import annotations

from typing import Any, override
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    HouseBrainAuthenticationError,
    HouseBrainClient,
    HouseBrainConnectionError,
    HouseBrainResponseError,
    normalize_base_url,
)
from .const import (
    CONF_BASE_URL,
    CONF_CONVERSATION_MODE,
    CONVERSATION_MODES,
    DEFAULT_BASE_URL,
    DEFAULT_CONVERSATION_MODE,
    DOMAIN,
)


async def _async_validate_input(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> None:
    """Validate credentials against the configured local server."""
    client = HouseBrainClient(
        async_get_clientsession(hass),
        data[CONF_BASE_URL],
        data[CONF_API_KEY],
    )
    await client.async_validate()


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the connection form with safe suggested values."""
    values = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_BASE_URL,
                default=values.get(CONF_BASE_URL, DEFAULT_BASE_URL),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
            ),
            vol.Required(CONF_API_KEY): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_CONVERSATION_MODE,
                default=values.get(
                    CONF_CONVERSATION_MODE,
                    DEFAULT_CONVERSATION_MODE,
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(CONVERSATION_MODES),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_CONVERSATION_MODE,
                )
            ),
        }
    )


def _normalize_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize form data before validation and storage."""
    return {
        CONF_BASE_URL: normalize_base_url(user_input[CONF_BASE_URL]),
        CONF_API_KEY: str(user_input[CONF_API_KEY]).strip(),
        CONF_CONVERSATION_MODE: user_input[CONF_CONVERSATION_MODE],
    }


class HouseBrainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one or more local House Brain servers."""

    VERSION = 1

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Create an integration entry after a live authentication check."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = _normalize_input(user_input)
                await _async_validate_input(self.hass, data)
            except ValueError:
                errors[CONF_BASE_URL] = "invalid_url"
            except HouseBrainAuthenticationError:
                errors["base"] = "invalid_auth"
            except HouseBrainConnectionError:
                errors["base"] = "cannot_connect"
            except HouseBrainResponseError:
                errors["base"] = "invalid_response"
            else:
                await self.async_set_unique_id(data[CONF_BASE_URL].casefold())
                self._abort_if_unique_id_configured()
                host = urlsplit(data[CONF_BASE_URL]).hostname or "House Brain"
                return self.async_create_entry(
                    title=f"House Brain ({host})",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    @override
    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Start a flow after the configured API key is rejected."""
        del entry_data
        return await self.async_step_reauth_confirm()

    @override
    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Validate and store a replacement API key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {
                **entry.data,
                CONF_API_KEY: str(user_input[CONF_API_KEY]).strip(),
            }
            try:
                await _async_validate_input(self.hass, data)
            except HouseBrainAuthenticationError:
                errors["base"] = "invalid_auth"
            except HouseBrainConnectionError:
                errors["base"] = "cannot_connect"
            except HouseBrainResponseError:
                errors["base"] = "invalid_response"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data=data,
                    reason="reauth_successful",
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Change the server URL, API key, or conversation safety mode."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = _normalize_input(user_input)
                await _async_validate_input(self.hass, data)
            except ValueError:
                errors[CONF_BASE_URL] = "invalid_url"
            except HouseBrainAuthenticationError:
                errors["base"] = "invalid_auth"
            except HouseBrainConnectionError:
                errors["base"] = "cannot_connect"
            except HouseBrainResponseError:
                errors["base"] = "invalid_response"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data=data,
                    unique_id=data[CONF_BASE_URL].casefold(),
                    reason="reconfigure_successful",
                )

        defaults = dict(entry.data)
        if user_input is not None:
            defaults.update(user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(defaults),
            errors=errors,
        )
