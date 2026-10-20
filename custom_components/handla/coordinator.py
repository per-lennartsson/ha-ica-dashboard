"""Event-driven coordinator: ICA lists, the active list and create/delete flows."""

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import (
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import shopping
from .ai_monitor import AiMonitor
from .const import (
    DOMAIN,
    ICA_DOMAIN,
    ICA_LISTS_CHANGED,
)
from .domain import (
    ListInfo,
    pick_active,
    same_id,
)
from .item_announcer import ItemAnnouncer
from .list_operations import ListOperations, Status
from .lists_registry import ActiveListStore, HandlaData, read_lists
from .notify import AddNotifier
from .usage import UsageTracker

_LOGGER = logging.getLogger(__name__)

type HandlaConfigEntry = ConfigEntry[HandlaCoordinator]


class HandlaCoordinator(DataUpdateCoordinator[HandlaData]):
    """Derives ICA lists from Home Assistant state and runs list operations.

    Push-based: no polling. It recomputes when ICA todo entities change.
    """

    config_entry: HandlaConfigEntry

    def __init__(self, hass: HomeAssistant, entry: HandlaConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=None
        )
        self._active = ActiveListStore(hass)
        self.usage = UsageTracker(hass)
        self.notifier = AddNotifier(hass, entry)
        self.ai_monitor = AiMonitor(hass, entry)
        self._announcer = ItemAnnouncer(
            hass, self.usage, self.notifier, self.async_update_listeners
        )
        self._operations = ListOperations(self)

    async def async_start(self) -> None:
        """Load the saved active list, compute data and start listening."""
        await self._active.async_load()
        await self.usage.async_load()
        self.data = self._compute()
        entry = self.config_entry
        entry.async_on_unload(self.usage.async_flush)
        entry.async_on_unload(self.notifier.async_flush)
        entry.async_on_unload(self.ai_monitor.async_stop)
        self.ai_monitor.async_sync()
        entry.async_on_unload(
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._on_registry_event
            )
        )
        entry.async_on_unload(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                self._on_state_event,
                event_filter=self._is_todo_event,
            )
        )
        entry.async_on_unload(
            self.hass.bus.async_listen(ICA_LISTS_CHANGED, self._on_lists_changed)
        )

    async def _async_update_data(self) -> HandlaData:
        return self._compute()

    # --- deriving data -------------------------------------------------------

    def _compute(self) -> HandlaData:
        lists = read_lists(self.hass)
        active = pick_active(
            lists,
            self._active.preferred,
            self.data.active_offline_id if self.data else None,
        )
        return HandlaData(tuple(lists), active)

    @callback
    def recompute(self) -> None:
        data = self._compute()
        if data != self.data:
            self.async_set_updated_data(data)

    @callback
    def _on_registry_event(self, event: Event[Any]) -> None:
        if str(event.data.get("entity_id", "")).startswith("todo."):
            self.recompute()

    @staticmethod
    @callback
    def _is_todo_event(event_data: EventStateChangedData) -> bool:
        """Only todo entities matter; this keeps other state changes out of the loop."""
        return event_data["entity_id"].startswith("todo.")

    @callback
    def _on_state_event(self, event: Event[EventStateChangedData]) -> None:
        entry = er.async_get(self.hass).async_get(event.data["entity_id"])
        if entry is not None and entry.platform == ICA_DOMAIN:
            self.recompute()

    @callback
    def _on_lists_changed(self, event: Event) -> None:
        self.recompute()

    # --- items ---------------------------------------------------------------

    async def async_add_item(
        self,
        entity_id: str | None,
        text: str,
        confirm_duplicate: bool,
        context: Context,
    ) -> dict[str, Any]:
        """Add an item to a list (the active one by default) and announce it."""
        target = self.resolve_list(entity_id)
        result = await shopping.async_add_item(
            self.hass, target, text, confirm_duplicate
        )
        if result["added"]:
            await self._announcer.async_added(result, context.user_id, context)
        return result

    # --- active list ---------------------------------------------------------

    async def async_set_active(self, entity_id: str) -> None:
        """Make the list behind `entity_id` the household's active list."""
        target = self.list_by_entity(entity_id)
        await self.async_set_preferred(target.offline_id)

    async def async_set_active_by_offline_id(self, offline_id: str) -> None:
        """Make the list with this ICA ID the active list (must exist)."""
        if not any(same_id(item.offline_id, offline_id) for item in self.data.lists):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_list",
                translation_placeholders={"entity_id": offline_id},
            )
        await self.async_set_preferred(offline_id)

    async def async_set_preferred(self, offline_id: str) -> None:
        await self._active.async_save(offline_id)
        self.recompute()

    def resolve_list(self, entity_id: str | None) -> ListInfo:
        """The list a service call refers to: the given one, else the active one."""
        if entity_id:
            return self.list_by_entity(entity_id)
        active = self.data.active
        if active is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_list"
            )
        return active

    def list_by_entity(self, entity_id: str) -> ListInfo:
        for item in self.data.lists:
            if item.entity_id == entity_id:
                return item
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_list",
            translation_placeholders={"entity_id": entity_id},
        )

    # --- create / delete -----------------------------------------------------

    @property
    def status(self) -> Status:
        """What list operations are doing right now."""
        return self._operations.status

    @property
    def status_detail(self) -> str | None:
        """The error of the last failed operation, if any."""
        return self._operations.detail

    def suggest_list_name(self) -> str:
        """ "Att handla <dag> <månad>", numbered if a list with that name exists."""
        return self._operations.suggest_list_name()

    async def async_create_list(
        self, title: str | None, comment: str, set_active: bool
    ) -> dict[str, str]:
        """Create an ICA list, wait for it to appear, optionally make it active."""
        return await self._operations.async_create(title, comment, set_active)

    async def async_delete_list(self, entity_id: str) -> dict[str, str]:
        """Delete an ICA list and wait until ha-ica-todo has reloaded."""
        return await self._operations.async_delete(entity_id)
