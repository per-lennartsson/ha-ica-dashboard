"""Persistent usage statistics (the Home Assistant side of domain/usage.py)."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_VERSION, USAGE_SAVE_DELAY
from .domain import (
    UsageEntry,
    add_entry,
    aliases_from_json,
    aliases_to_json,
    entries_from_json,
    entries_to_json,
    merge_entries,
    record_use,
    remove_entry,
    top_payload,
)


class UsageTracker:
    """Counts added items and keeps the counts in a Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.usage"
        )
        self.entries: dict[str, UsageEntry] = {}
        self.aliases: dict[str, str] = {}

    async def async_load(self) -> None:
        """Read the saved counts; unreadable data starts empty."""
        stored = await self._store.async_load()
        self.entries = entries_from_json((stored or {}).get("entries"))
        self.aliases = aliases_from_json((stored or {}).get("aliases"))

    def record(self, name: str) -> None:
        """Count one more use of `name` and schedule a save."""
        self.entries = record_use(
            self.entries, name, dt_util.utcnow().isoformat(), self.aliases
        )
        self._store.async_delay_save(self._data, USAGE_SAVE_DELAY)

    def remove(self, name: str) -> None:
        """Forget an item. Raises UsageError when it is not tracked."""
        self.entries, self.aliases = remove_entry(self.entries, self.aliases, name)
        self._store.async_delay_save(self._data, USAGE_SAVE_DELAY)

    def merge(self, sources: list[str], target: str) -> None:
        """Merge items into one called `target`. Raises UsageError on bad input."""
        self.entries, self.aliases = merge_entries(
            self.entries, self.aliases, sources, target
        )
        self._store.async_delay_save(self._data, USAGE_SAVE_DELAY)

    def pin(self, name: str) -> None:
        """Pin an item to the quick-add buttons. Raises UsageError if blank."""
        self.entries, self.aliases = add_entry(
            self.entries, self.aliases, name, dt_util.utcnow().isoformat()
        )
        self._store.async_delay_save(self._data, USAGE_SAVE_DELAY)

    async def async_flush(self) -> None:
        """Write the counts now (used when the integration unloads)."""
        await self._store.async_save(self._data())

    def top(self, limit: int) -> list[dict[str, Any]]:
        """The most added items as dicts with name, count and icon."""
        return top_payload(self.entries, limit)

    def _data(self) -> dict[str, Any]:
        return {
            "entries": entries_to_json(self.entries),
            "aliases": aliases_to_json(self.aliases),
        }
