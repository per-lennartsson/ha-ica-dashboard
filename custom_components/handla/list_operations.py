"""Creating and deleting ICA lists, with a status the UI can show."""

from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Protocol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from . import ica_api
from .const import DOMAIN, LISTS_CHANGED_TIMEOUT
from .domain import ListInfo, default_list_name, entity_for, event_mentions
from .errors import failure
from .events import ListsChangedWaiter
from .lists_registry import HandlaData


class Status(StrEnum):
    """What the integration is doing; shown by the status sensor."""

    IDLE = "idle"
    CREATING = "creating"
    DELETING = "deleting"
    ERROR = "error"


class ListsHost(Protocol):
    """What list operations need from the coordinator that owns them."""

    hass: HomeAssistant

    @property
    def data(self) -> HandlaData:
        """The current lists."""

    def recompute(self) -> None:
        """Re-read the lists from Home Assistant."""

    def list_by_entity(self, entity_id: str) -> ListInfo:
        """The list behind `entity_id`; an error if it is not known."""

    async def async_set_preferred(self, offline_id: str) -> None:
        """Make this list the active one."""

    def async_update_listeners(self) -> None:
        """Tell the entities that something changed."""


class ListOperations:
    """Runs create and delete one at a time and reports progress through `status`."""

    def __init__(self, host: ListsHost) -> None:
        self._host = host
        self.status = Status.IDLE
        self.detail: str | None = None

    def suggest_list_name(self) -> str:
        """ "Att handla <dag> <månad>", numbered if a list with that name exists."""
        return default_list_name(
            dt_util.now().date(), [item.title for item in self._host.data.lists]
        )

    async def async_create(
        self, title: str | None, comment: str, set_active: bool
    ) -> dict[str, str]:
        """Create an ICA list, wait for it to appear, optionally make it active."""
        return await self._run(
            Status.CREATING, lambda: self._create(title, comment, set_active)
        )

    async def async_delete(self, entity_id: str) -> dict[str, str]:
        """Delete an ICA list and wait until ha-ica-todo has reloaded."""
        target = self._host.list_by_entity(entity_id)
        return await self._run(Status.DELETING, lambda: self._delete(target))

    async def _create(
        self, title: str | None, comment: str, set_active: bool
    ) -> dict[str, str]:
        host = self._host
        ica_entry_id = ica_api.loaded_entry_id(host.hass)
        name = (title or "").strip() or self.suggest_list_name()
        async with ListsChangedWaiter(host.hass) as waiter:
            offline_id = await ica_api.async_create_list(
                host.hass, ica_entry_id, name, comment
            )
            event = await waiter.wait_for(
                lambda e: event_mentions(e, "created", offline_id),
                LISTS_CHANGED_TIMEOUT,
            )
        if event is None:
            raise failure("create_timeout", name=name)
        entity_id = entity_for(event, offline_id)
        if entity_id is None:
            raise failure("create_failed", name=name, error="list did not appear")
        host.recompute()
        created = host.list_by_entity(entity_id)
        if set_active:
            await host.async_set_preferred(created.offline_id)
        return {
            "entity_id": created.entity_id,
            "offline_id": created.offline_id,
            "title": created.title,
        }

    async def _delete(self, target: ListInfo) -> dict[str, str]:
        host = self._host
        async with ListsChangedWaiter(host.hass) as waiter:
            await ica_api.async_delete_list(host.hass, target.entity_id, target.title)
            event = await waiter.wait_for(
                lambda e: event_mentions(e, "deleted", target.offline_id),
                LISTS_CHANGED_TIMEOUT,
            )
        if event is None:
            raise failure("delete_timeout", name=target.title)
        host.recompute()
        return {"entity_id": target.entity_id, "offline_id": target.offline_id}

    async def _run[T](self, status: Status, operation: Callable[[], Awaitable[T]]) -> T:
        """Run `operation` as the only one in progress, keeping `status` up to date."""
        self._begin(status)
        try:
            result = await operation()
        except HomeAssistantError as err:
            self._set_status(Status.ERROR, str(err))
            raise
        self._set_status(Status.IDLE)
        return result

    def _begin(self, status: Status) -> None:
        """Mark busy, or refuse so nobody can start two operations at once."""
        if self.status in (Status.CREATING, Status.DELETING):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="busy"
            )
        self._set_status(status)

    def _set_status(self, status: Status, detail: str | None = None) -> None:
        self.status = status
        self.detail = detail
        self._host.async_update_listeners()
