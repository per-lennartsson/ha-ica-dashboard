"""Event-driven coordinator: ICA lists, the active list and create/delete flows."""

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ICA_DOMAIN,
    ICA_LISTS_CHANGED,
    LISTS_CHANGED_TIMEOUT,
    STORAGE_VERSION,
)
from .domain import (
    ListInfo,
    default_list_name,
    entity_for,
    event_mentions,
    parse_item_text,
    pick_active,
    same_id,
    title_from_name,
)
from .events import ListsChangedWaiter
from .usage import UsageTracker

_LOGGER = logging.getLogger(__name__)

type InkopConfigEntry = ConfigEntry[InkopCoordinator]


class Status(StrEnum):
    """What the integration is doing; shown by the status sensor."""

    IDLE = "idle"
    CREATING = "creating"
    DELETING = "deleting"
    ERROR = "error"


@dataclass(frozen=True)
class InkopData:
    """Snapshot of the ICA lists and which one is active."""

    lists: tuple[ListInfo, ...]
    active_offline_id: str | None

    @property
    def active(self) -> ListInfo | None:
        """The active list, if any."""
        return next(
            (
                item
                for item in self.lists
                if same_id(item.offline_id, self.active_offline_id)
            ),
            None,
        )


class InkopCoordinator(DataUpdateCoordinator[InkopData]):
    """Derives ICA lists from Home Assistant state and runs list operations.

    Push-based: no polling. It recomputes when ICA todo entities change.
    """

    config_entry: InkopConfigEntry

    def __init__(self, hass: HomeAssistant, entry: InkopConfigEntry) -> None:
        super().__init__(
            hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=None
        )
        self._store: Store[dict[str, str | None]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.active_list"
        )
        self._preferred: str | None = None
        self.usage = UsageTracker(hass)
        self.status = Status.IDLE
        self.status_detail: str | None = None

    async def async_start(self) -> None:
        """Load the saved active list, compute data and start listening."""
        stored = await self._store.async_load()
        self._preferred = stored.get("offline_id") if stored else None
        await self.usage.async_load()
        self.data = self._compute()
        entry = self.config_entry
        entry.async_on_unload(self.usage.async_flush)
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

    async def _async_update_data(self) -> InkopData:
        return self._compute()

    # --- deriving data -------------------------------------------------------

    def _compute(self) -> InkopData:
        lists = self._read_lists()
        active = pick_active(
            lists, self._preferred, self.data.active_offline_id if self.data else None
        )
        return InkopData(tuple(lists), active)

    def _read_lists(self) -> list[ListInfo]:
        registry = er.async_get(self.hass)
        found: list[ListInfo] = []
        for reg in registry.entities.values():
            if (
                reg.platform != ICA_DOMAIN
                or reg.domain != "todo"
                or reg.disabled
                or reg.unique_id.endswith("-baseitems")
            ):
                continue
            state = self.hass.states.get(reg.entity_id)
            attrs: dict[str, Any] = dict(state.attributes) if state else {}
            offline_id = attrs.get("offline_id") or reg.unique_id.partition("-")[2]
            count = state.state if state else None
            found.append(
                ListInfo(
                    entity_id=reg.entity_id,
                    offline_id=str(offline_id),
                    title=title_from_name(
                        attrs.get("friendly_name") or reg.original_name or reg.name,
                        reg.entity_id,
                    ),
                    item_count=int(count) if count and count.isdigit() else None,
                    comment=attrs.get("comment"),
                )
            )
        return sorted(found, key=lambda item: item.title.casefold())

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

    # --- usage statistics ----------------------------------------------------

    def record_added(self, item_text: str) -> None:
        """Count an item that was added through Inköp (quantity and unit ignored)."""
        self.usage.record(parse_item_text(item_text).name)
        self.async_update_listeners()

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
        self._preferred = offline_id
        await self._store.async_save({"offline_id": offline_id})
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

    def _ica_entry_id(self) -> str:
        for entry in self.hass.config_entries.async_entries(ICA_DOMAIN):
            if entry.state is ConfigEntryState.LOADED:
                return entry.entry_id
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="ica_unavailable"
        )

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

    async def async_create_list(
        self, title: str | None, comment: str, set_active: bool
    ) -> dict[str, str]:
        """Create an ICA list, wait for it to appear, optionally make it active."""
        self._begin(Status.CREATING)
        try:
            ica_entry_id = self._ica_entry_id()
            name = (title or "").strip() or default_list_name(
                dt_util.now().date(), [item.title for item in self.data.lists]
            )
            async with ListsChangedWaiter(self.hass) as waiter:
                offline_id = await self._call_create(ica_entry_id, name, comment)
                event = await waiter.wait_for(
                    lambda e: event_mentions(e, "created", offline_id),
                    LISTS_CHANGED_TIMEOUT,
                )
            entity_id = entity_for(event, offline_id) if event else None
            if event is None:
                raise _failure("create_timeout", name=name)
            if entity_id is None:
                raise _failure("create_failed", name=name, error="list did not appear")
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

    async def _call_create(self, ica_entry_id: str, name: str, comment: str) -> str:
        try:
            response = await self.hass.services.async_call(
                ICA_DOMAIN,
                "create_shopping_list",
                {
                    "integration": [ica_entry_id],
                    "title": name,
                    "comment": comment,
                    "track": True,
                },
                blocking=True,
                return_response=True,
            )
        except HomeAssistantError as err:
            raise _failure("create_failed", name=name, error=str(err)) from err
        offline_id = (response or {}).get("offline_id")
        if not offline_id:
            raise _failure("create_failed", name=name, error="no list id returned")
        return str(offline_id)

    async def async_delete_list(self, entity_id: str) -> dict[str, str]:
        """Delete an ICA list and wait until ha-ica-todo has reloaded."""
        target = self._list_by_entity(entity_id)
        self._begin(Status.DELETING)
        try:
            async with ListsChangedWaiter(self.hass) as waiter:
                try:
                    await self.hass.services.async_call(
                        ICA_DOMAIN,
                        "delete_shopping_list",
                        {"entity_id": entity_id},
                        blocking=True,
                    )
                except HomeAssistantError as err:
                    raise _failure(
                        "delete_failed", name=target.title, error=str(err)
                    ) from err
                event = await waiter.wait_for(
                    lambda e: event_mentions(e, "deleted", target.offline_id),
                    LISTS_CHANGED_TIMEOUT,
                )
            if event is None:
                raise _failure("delete_timeout", name=target.title)
            self._recompute()
        except HomeAssistantError as err:
            self._set_status(Status.ERROR, str(err))
            raise
        self._set_status(Status.IDLE)
        return {"entity_id": entity_id, "offline_id": target.offline_id}


def _failure(key: str, **placeholders: str) -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders,
    )
