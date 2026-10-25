"""The gate, as a cover."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GRemoteConfigEntry, GRemoteCoordinator
from .entity import GRemoteEntity

PARALLEL_UPDATES = 1

MOVING = ("opening", "closing", "running")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GRemoteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the gate if the module has an output to run it."""
    coordinator = entry.runtime_data
    if coordinator.data.status.gate_io:
        async_add_entities([GRemoteGate(coordinator)])


class GRemoteGate(GRemoteEntity, CoverEntity):
    """The gate.

    The module has one output that pulses the motor, like a remote's button:
    each pulse moves the gate the other way, or stops it mid-travel. Open and
    close therefore only pulse when that gets the gate where it was asked to go.
    """

    _attr_device_class = CoverDeviceClass.GATE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None

    def __init__(self, coordinator: GRemoteCoordinator) -> None:
        super().__init__(coordinator, "gate")

    @property
    def _state(self) -> str | None:
        return self.coordinator.data.gate_state

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.online

    @property
    def assumed_state(self) -> bool:
        """Without status feedback both buttons stay usable."""
        return self.coordinator.data.status.feedback_io is None

    @property
    def is_closed(self) -> bool | None:
        state = self._state
        return None if state in (None, "running") else state == "closed"

    @property
    def is_opening(self) -> bool:
        return self._state == "opening"

    @property
    def is_closing(self) -> bool:
        return self._state == "closing"

    async def _pulse_unless(self, done: tuple[str, ...]) -> None:
        state = self._state
        if state in done:
            return
        if state in MOVING:
            # A pulse now would stop the gate rather than send it the right way
            raise HomeAssistantError("The gate is moving; try again once it stops")
        gate_io = self.coordinator.data.status.gate_io
        assert gate_io is not None
        await self._trigger(gate_io.number)

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._pulse_unless(("open", "opening"))

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._pulse_unless(("closed", "closing"))
