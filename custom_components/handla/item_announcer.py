"""What happens after an item was added: count it, announce it, notify others."""

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import Context, HomeAssistant

from .const import EVENT_ITEM_ADDED
from .domain import event_data, parse_item_text
from .notify import AddNotifier
from .usage import UsageTracker

_LOGGER = logging.getLogger(__name__)


class ItemAnnouncer:
    """Records an added item in the statistics, fires the event and queues the push."""

    def __init__(
        self,
        hass: HomeAssistant,
        usage: UsageTracker,
        notifier: AddNotifier,
        on_counted: Callable[[], None],
    ) -> None:
        self._hass = hass
        self._usage = usage
        self._notifier = notifier
        self._on_counted = on_counted

    async def async_added(
        self, result: dict[str, Any], user_id: str | None, context: Context
    ) -> None:
        """An item was added through Handla; `result` is shopping.async_add_item's.

        The item is already on the list, so a failure here is logged and never
        raised: reporting it as a failed add would make people add the item twice.
        """
        try:
            await self._announce(result, user_id, context)
        except Exception:
            _LOGGER.exception(
                "The item %r was added, but counting or announcing it failed",
                result.get("item"),
            )

    async def _announce(
        self, result: dict[str, Any], user_id: str | None, context: Context
    ) -> None:
        item = result["item"]
        self._usage.record(parse_item_text(item).name)
        self._on_counted()
        user = await self._hass.auth.async_get_user(user_id) if user_id else None
        self._hass.bus.async_fire(
            EVENT_ITEM_ADDED,
            event_data(
                result["entity_id"],
                result["list_title"],
                item,
                user_id,
                user.name if user else None,
            ),
            context=context,
        )
        self._notifier.item_added(
            result["entity_id"], result["list_title"], user_id, item
        )
