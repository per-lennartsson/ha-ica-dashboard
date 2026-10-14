"""Tell the other users when someone adds items (batched, never the adder)."""

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later

from .const import CONF_RECIPIENTS, NOTIFY_DELAY
from .domain import build_message, merge_items, recipients_to_notify

_LOGGER = logging.getLogger(__name__)

# (list entity id, list title, user id of the adder)
type _Key = tuple[str, str, str | None]


def get_recipients(entry: ConfigEntry) -> dict[str, str]:
    """The configured {user_id: notify service}; malformed options are ignored."""
    raw = entry.options.get(CONF_RECIPIENTS)
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(user_id): service
        for user_id, service in raw.items()
        if isinstance(service, str) and service
    }


class AddNotifier:
    """Collects adds for a short while, then sends one message per adder and list."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._pending: dict[_Key, list[str]] = {}
        self._cancel: CALLBACK_TYPE | None = None

    def item_added(
        self, list_entity_id: str, list_title: str, adder_id: str | None, item: str
    ) -> None:
        """Remember an added item; nothing is sent if nobody is configured."""
        if not get_recipients(self._entry):
            return
        key = (list_entity_id, list_title, adder_id)
        self._pending[key] = merge_items(self._pending.get(key, []), [item])
        if self._cancel is None:
            self._cancel = async_call_later(self._hass, NOTIFY_DELAY, self._on_timer)

    async def _on_timer(self, _now: datetime) -> None:
        self._cancel = None
        await self.async_flush()

    async def async_flush(self) -> None:
        """Send everything that is waiting, now."""
        if self._cancel is not None:
            self._cancel()
            self._cancel = None
        pending, self._pending = self._pending, {}
        for (_entity_id, list_title, adder_id), items in pending.items():
            await self._send(list_title, adder_id, items)

    async def _send(
        self, list_title: str, adder_id: str | None, items: list[str]
    ) -> None:
        adder_name = await self._user_name(adder_id)
        title, message = build_message(
            self._hass.config.language, adder_name, list_title, items
        )
        targets = recipients_to_notify(get_recipients(self._entry), adder_id)
        for user_id, service in targets.items():
            try:
                await self._hass.services.async_call(
                    "notify",
                    service,
                    {"title": title, "message": message, "data": {"tag": "handla"}},
                    blocking=True,
                )
            except HomeAssistantError as err:
                # One broken phone must not stop the others (or the add itself)
                _LOGGER.warning(
                    "Could not notify user %s through notify.%s: %s",
                    user_id,
                    service,
                    err,
                )

    async def _user_name(self, user_id: str | None) -> str | None:
        if user_id is None:
            return None
        user = await self._hass.auth.async_get_user(user_id)
        return user.name if user else None


def event_data(
    list_entity_id: str,
    list_title: str,
    item: str,
    user_id: str | None,
    user_name: str | None,
) -> dict[str, Any]:
    """Payload of the `handla_item_added` event."""
    return {
        "entity_id": list_entity_id,
        "list_title": list_title,
        "item": item,
        "user_id": user_id,
        "user_name": user_name,
    }
