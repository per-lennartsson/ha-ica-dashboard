"""Persistent usage statistics (the Home Assistant side of domain/usage.py)."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_VERSION, USAGE_SAVE_DELAY
from .domain import (
    UsageEntry,
    entries_from_json,
    entries_to_json,
    record_use,
    top_payload,
)


class UsageTracker:
    """Counts added items and keeps the counts in a Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.usage"
        )
        self.entries: dict[str, UsageEntry] = {}

    async def async_load(self) -> None:
        """Read the saved counts; unreadable data starts empty."""
        stored = await self._store.async_load()
        self.entries = entries_from_json((stored or {}).get("entries"))

    def record(self, name: str) -> None:
        """Count one more use of `name` and schedule a save."""
        self.entries = record_use(self.entries, name, dt_util.utcnow().isoformat())
        self._store.async_delay_save(self._data, USAGE_SAVE_DELAY)

    async def async_flush(self) -> None:
        """Write the counts now (used when the integration unloads)."""
        await self._store.async_save(self._data())

    def top(self, limit: int) -> list[dict[str, Any]]:
        """The most added items as dicts with name, count and icon."""
        return top_payload(self.entries, limit)

    def _data(self) -> dict[str, Any]:
        return {"entries": entries_to_json(self.entries)}
