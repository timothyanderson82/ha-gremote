"""Connectivity, and whether each output is currently on."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import IO, output_is_on
from .coordinator import GRemoteConfigEntry, GRemoteCoordinator
from .entity import GRemoteEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GRemoteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [GRemoteOnline(coordinator)]
    entities += (
        GRemoteOutput(coordinator, io) for io in coordinator.data.status.ios if io.is_output
    )
    async_add_entities(entities)


class GRemoteOnline(GRemoteEntity, BinarySensorEntity):
    """Whether the module is connected to G-Web."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GRemoteCoordinator) -> None:
        super().__init__(coordinator, "online")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.online


class GRemoteOutput(GRemoteEntity, BinarySensorEntity):
    """An output's relay state, e.g. whether Keep Open is holding the gate."""

    _attr_translation_key = "output"

    def __init__(self, coordinator: GRemoteCoordinator, io: IO) -> None:
        super().__init__(coordinator, f"output_{io.number}_state")
        self._io = io
        self._attr_translation_placeholders = {"name": io.name}

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.online

    @property
    def is_on(self) -> bool | None:
        return output_is_on(self.coordinator.data.states, self._io)
