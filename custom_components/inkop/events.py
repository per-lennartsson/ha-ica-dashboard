"""Collect `ica_lists_changed` events so a fast event is never missed."""

import asyncio
from collections.abc import Callable, Mapping
from types import TracebackType
from typing import Any, Self

from homeassistant.core import Event, HomeAssistant, callback

from .const import ICA_LISTS_CHANGED


class ListsChangedWaiter:
    """Async context manager that records events from the moment it is entered.

    Enter it *before* calling ica.create_shopping_list / ica.delete_shopping_list:
    ha-ica-todo reloads in the background and the event can arrive at any time.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._events: list[Mapping[str, Any]] = []
        self._wake = asyncio.Event()
        self._unsubscribe: Callable[[], None] | None = None

    async def __aenter__(self) -> Self:
        self._unsubscribe = self._hass.bus.async_listen(
            ICA_LISTS_CHANGED, self._on_event
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    @callback
    def _on_event(self, event: Event) -> None:
        self._events.append(dict(event.data))
        self._wake.set()

    async def wait_for(
        self, predicate: Callable[[Mapping[str, Any]], bool], wait_seconds: float
    ) -> Mapping[str, Any] | None:
        """Return the first recorded or new matching event, or None on timeout."""
        try:
            async with asyncio.timeout(wait_seconds):
                while True:
                    for event in self._events:
                        if predicate(event):
                            return event
                    self._wake.clear()
                    await self._wake.wait()
        except TimeoutError:
            return None
