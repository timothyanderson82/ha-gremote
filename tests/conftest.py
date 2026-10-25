"""Fixtures for G-Remote tests. G-Web is never contacted: the client is patched."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gremote.api import encode_data, parse_status
from custom_components.gremote.const import CONF_DEVICE_ID, CONF_TOKEN, DOMAIN

DEVICE_ID = 12345
# Encodes to base64 with "+" and "=", which must survive the round trip
TOKEN = "0123456789abcdef0123456789abcdef|c2Vj>>>?~~~"
URL = f"https://www.gweb.co.za/api/MCRStatus?data={encode_data(DEVICE_ID, TOKEN, 1)}"

# Shaped like a real G-ULTRA 3G reply (values made up)
STATUS_BODY = {
    "Voltage": "27,4",
    "Signal": "2",
    "Firmware": "3.2.4",
    "Antenna": "0",
    "OnlineStatus": "Active",
    "Airtime": "Tokens Remaining Call: 40 SMS: 0",
    "AirtimeLastUpdated": "2026/10/23 06:32:03",
    "IOstates": "Open:Off,Pedestrian:Off,Keep Open:Off,Gate Status:Closed,NA:NA,NA:NA",
    "IODirections": "Output, Output, Output, Input, NA,NA",
    "Number": "27000000000",
    "ConnectionType": "3G",
    "LastSynced": "2026/10/23 06:32:03",
}
CLOSED = [89, 91, 93, 51, 48, 48]
OPEN = [89, 91, 93, 49, 48, 48]
OPENING = [88, 91, 93, 48, 48, 48]
KEEP_OPEN = [89, 91, 92, 49, 48, 48]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading custom_components/."""


@pytest.fixture
def client() -> Generator[AsyncMock]:
    """Patch the G-Web client everywhere it is used."""
    mock = AsyncMock()
    mock.status.return_value = parse_status(STATUS_BODY)
    mock.io_states.return_value = list(CLOSED)
    with (
        patch("custom_components.gremote.api.GRemoteClient.status", mock.status),
        patch("custom_components.gremote.api.GRemoteClient.io_states", mock.io_states),
        patch("custom_components.gremote.api.GRemoteClient.trigger", mock.trigger),
    ):
        yield mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Gate",
        unique_id=str(DEVICE_ID),
        data={CONF_DEVICE_ID: DEVICE_ID, CONF_TOKEN: TOKEN},
    )


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: AsyncMock
) -> MockConfigEntry:
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
