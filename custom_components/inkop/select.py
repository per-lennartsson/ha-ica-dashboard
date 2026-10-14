"""Select entity: the household's active shopping list."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import InkopConfigEntry, InkopCoordinator
from .domain import ListInfo, unique_labels
from .entity import InkopEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InkopConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the active-list select."""
    async_add_entities([ActiveListSelect(entry.runtime_data)])


class ActiveListSelect(InkopEntity, SelectEntity):
    """Choose which ICA list is the active one (shared by all users)."""

    def __init__(self, coordinator: InkopCoordinator) -> None:
        super().__init__(coordinator, "active_list")

    def _labelled(self) -> list[tuple[str, ListInfo]]:
        lists = self.coordinator.data.lists
        return list(
            zip(unique_labels([item.title for item in lists]), lists, strict=True)
        )

    @property
    def options(self) -> list[str]:
        """Titles of all ICA lists (repeated titles get a number)."""
        return [label for label, _ in self._labelled()]

    @property
    def current_option(self) -> str | None:
        """Title of the active list."""
        active = self.coordinator.data.active
        for label, item in self._labelled():
            if active is not None and item.offline_id == active.offline_id:
                return label
        return None

    async def async_select_option(self, option: str) -> None:
        """Make the chosen list the active one."""
        for label, item in self._labelled():
            if label == option:
                await self.coordinator.async_set_active_by_offline_id(item.offline_id)
                return
