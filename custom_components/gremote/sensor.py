"""Diagnostics from the module: supply voltage, signal and airtime."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfElectricPotential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Status
from .coordinator import GRemoteConfigEntry, GRemoteCoordinator
from .entity import GRemoteEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GRemoteSensorDescription(SensorEntityDescription):
    value: Callable[[Status], float | int | str | datetime | None]


SENSORS = (
    GRemoteSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.voltage,
    ),
    GRemoteSensorDescription(
        key="signal",
        translation_key="signal",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.signal,
    ),
    GRemoteSensorDescription(
        key="calls_remaining",
        translation_key="calls_remaining",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.calls_remaining,
    ),
    GRemoteSensorDescription(
        key="sms_remaining",
        translation_key="sms_remaining",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.sms_remaining,
    ),
    GRemoteSensorDescription(
        key="connection_type",
        translation_key="connection_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.connection_type,
    ),
    GRemoteSensorDescription(
        key="last_synced",
        translation_key="last_synced",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda s: s.last_synced,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GRemoteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(GRemoteSensor(coordinator, d) for d in SENSORS)


class GRemoteSensor(GRemoteEntity, SensorEntity):
    entity_description: GRemoteSensorDescription

    def __init__(
        self, coordinator: GRemoteCoordinator, description: GRemoteSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | datetime | None:
        return self.entity_description.value(self.coordinator.data.status)
