"""Sensors: open items on the active list, and what Handla is doing."""

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .ai import current_ai_status, get_ai_config
from .const import QUICK_ADD_LIMIT
from .coordinator import HandlaConfigEntry, HandlaCoordinator, Status
from .domain import AiStatus, lists_payload, quick_add_payload
from .entity import HandlaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HandlaConfigEntry,
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
            AiStatusSensor(coordinator),
        ]
    )


class ItemCountSensor(SensorEntity, HandlaEntity):
    """Number of items still to buy on the active list."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cart-outline"  # also used when shown as a dashboard badge

    def __init__(self, coordinator: HandlaCoordinator) -> None:
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


class StatusSensor(SensorEntity, HandlaEntity):
    """idle / creating / deleting / error, so the UI can show progress."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [status.value for status in Status]

    def __init__(self, coordinator: HandlaCoordinator) -> None:
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


class FrequentItemsSensor(SensorEntity, HandlaEntity):
    """The most often added items, for quick-add buttons in the card."""

    _unrecorded_attributes = frozenset({"items"})

    def __init__(self, coordinator: HandlaCoordinator) -> None:
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


class ListsSensor(SensorEntity, HandlaEntity):
    """All ICA lists with item counts, for the card's list picker."""

    _unrecorded_attributes = frozenset({"lists", "active_offline_id"})

    def __init__(self, coordinator: HandlaCoordinator) -> None:
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


class AiStatusSensor(SensorEntity, HandlaEntity):
    """off / ready / unavailable: the card shows AI UI only when this is `ready`."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [status.value for status in AiStatus]

    def __init__(self, coordinator: HandlaCoordinator) -> None:
        super().__init__(coordinator, "ai")

    async def async_added_to_hass(self) -> None:
        """Follow option changes and the chosen provider's state."""
        await super().async_added_to_hass()
        entry = self.coordinator.config_entry
        self.async_on_remove(entry.add_update_listener(self._on_options_changed))
        self.async_on_remove(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                self._on_state_changed,
                event_filter=self._is_provider_event,
            )
        )

    async def _on_options_changed(
        self, hass: HomeAssistant, entry: HandlaConfigEntry
    ) -> None:
        self.async_write_ha_state()

    @callback
    def _is_provider_event(self, event_data: EventStateChangedData) -> bool:
        _enabled, entity_id = get_ai_config(self.coordinator.config_entry)
        return entity_id is not None and event_data["entity_id"] == entity_id

    @callback
    def _on_state_changed(self, event: Event[EventStateChangedData]) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        """Current AI status."""
        return current_ai_status(self.hass, self.coordinator.config_entry).value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """The chosen provider, when AI is on."""
        enabled, entity_id = get_ai_config(self.coordinator.config_entry)
        return {"provider": entity_id} if enabled and entity_id else {}
