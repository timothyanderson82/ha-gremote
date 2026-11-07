"""Base entity for G-Remote."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import GRemoteError
from .const import DOMAIN, MANUFACTURER
from .coordinator import GRemoteCoordinator


class GRemoteEntity(CoordinatorEntity[GRemoteCoordinator]):
    """An entity of one gate module."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GRemoteCoordinator, key: str) -> None:
        super().__init__(coordinator)
        device_id = coordinator.client.device_id
        status = coordinator.data.status
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            manufacturer=MANUFACTURER,
            model=f"G-ULTRA ({status.connection_type})" if status.connection_type else "G-ULTRA",
            name="Gate",
            sw_version=status.firmware,
            serial_number=str(device_id),
        )

    async def _trigger(self, io_number: int) -> None:
        try:
            await self.coordinator.async_trigger(io_number)
        except GRemoteError as err:
            raise HomeAssistantError(f"Could not reach the gate: {err}") from err
