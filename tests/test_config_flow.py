"""The config flow."""

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gremote.api import (
    DeviceOfflineError,
    GRemoteError,
    InvalidCredentialsError,
    encode_data,
)
from custom_components.gremote.const import CONF_DEVICE_ID, CONF_TOKEN, CONF_URL, DOMAIN

from .conftest import DEVICE_ID, TOKEN, URL


async def _submit(hass: HomeAssistant, url: str):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: url})


async def test_create_entry(hass: HomeAssistant, client: AsyncMock) -> None:
    result = await _submit(hass, URL)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gate"
    assert result["data"] == {CONF_DEVICE_ID: DEVICE_ID, CONF_TOKEN: TOKEN}
    assert result["result"].unique_id == str(DEVICE_ID)


async def test_offline_module_can_be_added(hass: HomeAssistant, client: AsyncMock) -> None:
    client.io_states.side_effect = DeviceOfflineError("Device is Offline")
    result = await _submit(hass, URL)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("url", "side_effect", "errors"),
    [
        ("https://www.gweb.co.za/api/MCRStatus", None, {CONF_URL: "invalid_url"}),
        (URL, InvalidCredentialsError("x"), {"base": "invalid_auth"}),
        (URL, GRemoteError("x"), {"base": "cannot_connect"}),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    client: AsyncMock,
    url: str,
    side_effect: Exception | None,
    errors: dict[str, str],
) -> None:
    client.status.side_effect = side_effect
    result = await _submit(hass, url)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors


async def test_already_configured(
    hass: HomeAssistant, client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await _submit(hass, URL)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant, client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    new_token = TOKEN.replace("0123", "9999")
    other = f"https://www.gweb.co.za/api/MCRStatus?data={encode_data(1, new_token, 1)}"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: other})
    assert result["reason"] == "wrong_device"

    result = await config_entry.start_reauth_flow(hass)
    same = f"https://www.gweb.co.za/api/MCRStatus?data={encode_data(DEVICE_ID, new_token, 1)}"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: same})
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_TOKEN] == new_token
