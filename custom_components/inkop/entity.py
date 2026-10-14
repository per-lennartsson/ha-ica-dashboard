"""Shared base for Inköp entities."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InkopCoordinator


class InkopEntity(CoordinatorEntity[InkopCoordinator]):
    """Entity attached to the single Inköp device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: InkopCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Inköp",
            entry_type=DeviceEntryType.SERVICE,
        )
