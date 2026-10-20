"""Event-driven coordinator: ICA lists, the active list and create/delete flows."""

import logging
from enum import StrEnum
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import ica_api, shopping
from .ai_monitor import AiMonitor
from .const import (
    DOMAIN,
    ICA_DOMAIN,
    ICA_LISTS_CHANGED,
    LISTS_CHANGED_TIMEOUT,
)
from .domain import (
    ListInfo,
    default_list_name,
    entity_for,
    event_mentions,
    pick_active,
    same_id,
)
from .errors import failure
from .events import ListsChangedWaiter
from .item_announcer import ItemAnnouncer
from .lists_registry import ActiveListStore, HandlaData, read_lists
from .notify import AddNotifier
from .usage import UsageTracker

_LOGGER = logging.getLogger(__name__)

type HandlaConfigEntry = ConfigEntry[HandlaCoordinator]


class Status(StrEnum):
    """What the integration is doing; shown by the status sensor."""

    IDLE = "idle"
    CREATING = "creating"
    DELETING = "deleting"
    ERROR = "error"


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
        self.status = Status.IDLE
        self.status_detail: str | None = None

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
            self.hass.bus.async_listen("state_changed", self._on_state_event)
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
    def _recompute(self) -> None:
        data = self._compute()
        if data != self.data:
            self.async_set_updated_data(data)

    @callback
    def _on_registry_event(self, event: Event[Any]) -> None:
        if str(event.data.get("entity_id", "")).startswith("todo."):
            self._recompute()

    @callback
    def _on_state_event(self, event: Event) -> None:
        entity_id: str = event.data["entity_id"]
        if not entity_id.startswith("todo."):
            return
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is not None and entry.platform == ICA_DOMAIN:
            self._recompute()

    @callback
    def _on_lists_changed(self, event: Event) -> None:
        self._recompute()

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
        target = self._list_by_entity(entity_id)
        await self._set_preferred(target.offline_id)

    async def async_set_active_by_offline_id(self, offline_id: str) -> None:
        """Make the list with this ICA ID the active list (must exist)."""
        if not any(same_id(item.offline_id, offline_id) for item in self.data.lists):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_list",
                translation_placeholders={"entity_id": offline_id},
            )
        await self._set_preferred(offline_id)

    async def _set_preferred(self, offline_id: str) -> None:
        await self._active.async_save(offline_id)
        self._recompute()

    def resolve_list(self, entity_id: str | None) -> ListInfo:
        """The list a service call refers to: the given one, else the active one."""
        if entity_id:
            return self._list_by_entity(entity_id)
        active = self.data.active
        if active is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_list"
            )
        return active

    def _list_by_entity(self, entity_id: str) -> ListInfo:
        for item in self.data.lists:
            if item.entity_id == entity_id:
                return item
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_list",
            translation_placeholders={"entity_id": entity_id},
        )

    # --- create / delete -----------------------------------------------------

    def _begin(self, status: Status) -> None:
        """Mark busy, or refuse so nobody can start two operations at once."""
        if self.status in (Status.CREATING, Status.DELETING):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="busy"
            )
        self._set_status(status)

    def _set_status(self, status: Status, detail: str | None = None) -> None:
        self.status = status
        self.status_detail = detail
        self.async_update_listeners()

    def suggest_list_name(self) -> str:
        """ "Att handla <dag> <månad>", numbered if a list with that name exists."""
        return default_list_name(
            dt_util.now().date(), [item.title for item in self.data.lists]
        )

    async def async_create_list(
        self, title: str | None, comment: str, set_active: bool
    ) -> dict[str, str]:
        """Create an ICA list, wait for it to appear, optionally make it active."""
        self._begin(Status.CREATING)
        try:
            ica_entry_id = ica_api.loaded_entry_id(self.hass)
            name = (title or "").strip() or self.suggest_list_name()
            async with ListsChangedWaiter(self.hass) as waiter:
                offline_id = await ica_api.async_create_list(
                    self.hass, ica_entry_id, name, comment
                )
                event = await waiter.wait_for(
                    lambda e: event_mentions(e, "created", offline_id),
                    LISTS_CHANGED_TIMEOUT,
                )
            entity_id = entity_for(event, offline_id) if event else None
            if event is None:
                raise failure("create_timeout", name=name)
            if entity_id is None:
                raise failure("create_failed", name=name, error="list did not appear")
            self._recompute()
            created = self._list_by_entity(entity_id)
            if set_active:
                await self._set_preferred(created.offline_id)
        except HomeAssistantError as err:
            self._set_status(Status.ERROR, str(err))
            raise
        self._set_status(Status.IDLE)
        return {
            "entity_id": created.entity_id,
            "offline_id": created.offline_id,
            "title": created.title,
        }

    async def async_delete_list(self, entity_id: str) -> dict[str, str]:
        """Delete an ICA list and wait until ha-ica-todo has reloaded."""
        target = self._list_by_entity(entity_id)
        self._begin(Status.DELETING)
        try:
            async with ListsChangedWaiter(self.hass) as waiter:
                await ica_api.async_delete_list(self.hass, entity_id, target.title)
                event = await waiter.wait_for(
                    lambda e: event_mentions(e, "deleted", target.offline_id),
                    LISTS_CHANGED_TIMEOUT,
                )
            if event is None:
                raise failure("delete_timeout", name=target.title)
            self._recompute()
        except HomeAssistantError as err:
            self._set_status(Status.ERROR, str(err))
            raise
        self._set_status(Status.IDLE)
        return {"entity_id": entity_id, "offline_id": target.offline_id}
