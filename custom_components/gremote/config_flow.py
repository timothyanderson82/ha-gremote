"""Config flow for G-Remote.

The module is identified by the ``data`` parameter the apps send, so the user
pastes a G-Web URL captured from the app (or from an existing Node-RED flow)
rather than typing the device ID and token separately.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    DeviceOfflineError,
    GRemoteClient,
    GRemoteError,
    InvalidCredentialsError,
    parse_url,
)
from .const import CONF_DEVICE_ID, CONF_TOKEN, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCHEMA = vol.Schema(
    {vol.Required(CONF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
)


class GRemoteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a gate module."""

    VERSION = 1

    async def _check(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        """Return the entry data for a pasted URL, or form errors."""
        try:
            device_id, token = parse_url(user_input[CONF_URL])
        except ValueError:
            return None, {CONF_URL: "invalid_url"}
        client = GRemoteClient(async_get_clientsession(self.hass), device_id, token)
        try:
            status = await client.status()
            if status.online:
                await client.io_states()
        except InvalidCredentialsError:
            return None, {"base": "invalid_auth"}
        except DeviceOfflineError:
            pass  # still a valid module; it can come back online later
        except GRemoteError:
            _LOGGER.debug("G-Web check failed", exc_info=True)
            return None, {"base": "cannot_connect"}
        if not status.ios:
            return None, {"base": "invalid_auth"}
        return {CONF_DEVICE_ID: device_id, CONF_TOKEN: token}, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._check(user_input)
            if data:
                await self.async_set_unique_id(str(data[CONF_DEVICE_ID]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Gate", data=data)
        return self.async_show_form(step_id="user", data_schema=SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._check(user_input)
            if data:
                await self.async_set_unique_id(str(data[CONF_DEVICE_ID]))
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        return self.async_show_form(step_id="reauth_confirm", data_schema=SCHEMA, errors=errors)
