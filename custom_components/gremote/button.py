"""A button for each of the module's other outputs, e.g. pedestrian."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import IO
from .coordinator import GRemoteConfigEntry, GRemoteCoordinator
from .entity import GRemoteEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GRemoteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a button per output, apart from the one the gate cover uses."""
    coordinator = entry.runtime_data
    status = coordinator.data.status
    async_add_entities(
        GRemoteButton(coordinator, io) for io in status.ios if io.is_output and io != status.gate_io
    )


class GRemoteButton(GRemoteEntity, ButtonEntity):
    """Pulses one output, like its button in the app."""

    def __init__(self, coordinator: GRemoteCoordinator, io: IO) -> None:
        super().__init__(coordinator, f"output_{io.number}")
        self._io = io
        self._attr_name = io.name

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.online

    async def async_press(self) -> None:
        await self._trigger(self._io.number)
