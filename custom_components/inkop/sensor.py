"""Sensors: open items on the active list, and what Inköp is doing."""

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import QUICK_ADD_LIMIT
from .coordinator import InkopConfigEntry, InkopCoordinator, Status
from .domain import lists_payload, quick_add_payload
from .entity import InkopEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InkopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the item count and status sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ItemCountSensor(coordinator),
            StatusSensor(coordinator),
            FrequentItemsSensor(coordinator),
            ListsSensor(coordinator),
        ]
    )


class ItemCountSensor(SensorEntity, InkopEntity):
    """Number of items still to buy on the active list."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cart-outline"  # also used when shown as a dashboard badge

    def __init__(self, coordinator: InkopCoordinator) -> None:
        super().__init__(coordinator, "items")

    @property
    def native_value(self) -> int | None:
        """Open items on the active list; None while it is unavailable."""
        active = self.coordinator.data.active
        return active.item_count if active else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Which list the count belongs to."""
        active = self.coordinator.data.active
        if active is None:
            return {}
        return {
            "list_entity_id": active.entity_id,
            "list_title": active.title,
            "list_offline_id": active.offline_id,
        }


class StatusSensor(SensorEntity, InkopEntity):
    """idle / creating / deleting / error, so the UI can show progress."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [status.value for status in Status]

    def __init__(self, coordinator: InkopCoordinator) -> None:
        super().__init__(coordinator, "status")

    @property
    def native_value(self) -> str:
        """Current status."""
        return self.coordinator.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Error details, if any."""
        detail = self.coordinator.status_detail
        return {"detail": detail} if detail else {}


class FrequentItemsSensor(SensorEntity, InkopEntity):
    """The most often added items, for quick-add buttons in the card."""

    _unrecorded_attributes = frozenset({"items"})

    def __init__(self, coordinator: InkopCoordinator) -> None:
        super().__init__(coordinator, "frequent_items")

    @property
    def native_value(self) -> int:
        """Number of different items counted so far."""
        return len(self.coordinator.usage.entries)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Quick-add buttons: most added first, topped up with staples (count 0)."""
        entries = self.coordinator.usage.entries
        return {"items": quick_add_payload(entries, QUICK_ADD_LIMIT)}


class ListsSensor(SensorEntity, InkopEntity):
    """All ICA lists with item counts, for the card's list picker."""

    _unrecorded_attributes = frozenset({"lists", "active_offline_id"})

    def __init__(self, coordinator: InkopCoordinator) -> None:
        super().__init__(coordinator, "lists")

    @property
    def native_value(self) -> int:
        """Number of lists."""
        return len(self.coordinator.data.lists)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The lists (entity id, ICA id, title, open items) and the active list."""
        data = self.coordinator.data
        return {
            "lists": lists_payload(data.lists),
            "active_offline_id": data.active_offline_id,
        }
