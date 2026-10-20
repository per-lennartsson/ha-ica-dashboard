"""The ICA lists as Home Assistant knows them, and which one is the active list."""

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .const import DOMAIN, ICA_DOMAIN, STORAGE_VERSION
from .domain import ListInfo, same_id, title_from_name

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HandlaData:
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


def read_lists(hass: HomeAssistant) -> list[ListInfo]:
    """The tracked ICA lists (not the favourites), sorted by title."""
    registry = er.async_get(hass)
    found: list[ListInfo] = []
    for reg in registry.entities.values():
        if (
            reg.platform != ICA_DOMAIN
            or reg.domain != "todo"
            or reg.disabled
            or reg.unique_id.endswith("-baseitems")
        ):
            continue
        state = hass.states.get(reg.entity_id)
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


class ActiveListStore:
    """The household's chosen active list, kept across restarts."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, str | None]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.active_list"
        )
        self.preferred: str | None = None

    async def async_load(self) -> None:
        """Read the saved choice, if any."""
        stored = await self._store.async_load()
        self.preferred = stored.get("offline_id") if stored else None

    async def async_save(self, offline_id: str) -> None:
        """Use this list now; if it cannot be saved it is forgotten at a restart."""
        self.preferred = offline_id
        try:
            await self._store.async_save({"offline_id": offline_id})
        except OSError as err:
            _LOGGER.warning("Could not save the active list: %s", err)
