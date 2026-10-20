"""Thin wrapper around Home Assistant's notify services (the notification I/O layer)."""

import logging
from collections.abc import Mapping

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


async def async_notify_users(
    hass: HomeAssistant, targets: Mapping[str, str], title: str, message: str
) -> None:
    """Send one message through each user's notify service; one failure stops no one."""
    for user_id, service in targets.items():
        try:
            await hass.services.async_call(
                "notify",
                service,
                {"title": title, "message": message, "data": {"tag": "handla"}},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Could not notify user %s through notify.%s: %s", user_id, service, err
            )
