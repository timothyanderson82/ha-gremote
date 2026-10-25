"""Polls G-Web for a module's live IO states and its diagnostics."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    DeviceOfflineError,
    GRemoteClient,
    GRemoteError,
    InvalidCredentialsError,
    Status,
    gate_state,
)
from .const import (
    DOMAIN,
    FAST_POLL_DURATION,
    FAST_POLL_INTERVAL,
    POLL_INTERVAL,
    STATUS_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type GRemoteConfigEntry = ConfigEntry[GRemoteCoordinator]


@dataclass
class GRemoteData:
    """What the entities read."""

    status: Status
    states: list[int]  # empty while the module is offline
    online: bool

    @property
    def gate_state(self) -> str | None:
        return gate_state(self.states, self.status.feedback_io)


class GRemoteCoordinator(DataUpdateCoordinator[GRemoteData]):
    """One coordinator per module."""

    config_entry: GRemoteConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: GRemoteConfigEntry, client: GRemoteClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=POLL_INTERVAL,
        )
        self.client = client
        self._status: Status | None = None
        self._status_at = dt_util.utcnow()
        self._fast_until = dt_util.utcnow()

    async def _fetch_status(self) -> Status:
        try:
            status = await self.client.status()
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        self._status, self._status_at = status, dt_util.utcnow()
        return status

    async def _async_update_data(self) -> GRemoteData:
        now = dt_util.utcnow()
        try:
            if self._status is None:
                status = await self._fetch_status()
            elif now - self._status_at >= STATUS_INTERVAL:
                try:
                    status = await self._fetch_status()
                except GRemoteError as err:
                    # Diagnostics can wait; keep the gate state live
                    _LOGGER.debug("Keeping old diagnostics: %s", err)
                    status = self._status
            else:
                status = self._status
            try:
                states, online = await self.client.io_states(), True
            except DeviceOfflineError:
                states, online = [], False
        except GRemoteError as err:
            raise UpdateFailed(str(err)) from err

        if now >= self._fast_until:
            self.update_interval = POLL_INTERVAL
        return GRemoteData(status=status, states=states, online=online)

    async def async_trigger(self, io_number: int) -> None:
        """Pulse an output, then watch closely while the gate moves."""
        await self.client.trigger(io_number)
        self._fast_until = dt_util.utcnow() + FAST_POLL_DURATION
        self.update_interval = FAST_POLL_INTERVAL
        await self.async_request_refresh()
