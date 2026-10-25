"""G-Remote: Centurion G-ULTRA / G-SPEAK gate modules via the G-Web cloud."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GRemoteClient
from .const import CONF_DEVICE_ID, CONF_TOKEN
from .coordinator import GRemoteConfigEntry, GRemoteCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.COVER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GRemoteConfigEntry) -> bool:
    """Set up a gate module from a config entry."""
    client = GRemoteClient(
        async_get_clientsession(hass),
        entry.data[CONF_DEVICE_ID],
        entry.data[CONF_TOKEN],
    )
    coordinator = GRemoteCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GRemoteConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
