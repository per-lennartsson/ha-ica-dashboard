"""Watches the AI provider: tells people when it fails, with an optional daily test."""

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .ai import get_ai_config, get_health_check
from .const import AI_HEALTH_INTERVAL, AI_TASK_DOMAIN
from .domain import AiHealth, build_failure_message, record_failure, record_success
from .notify import async_notify_users, get_recipients

_LOGGER = logging.getLogger(__name__)

HEALTH_TASK_NAME = "Handla: health check"
HEALTH_INSTRUCTIONS = "Svara med ordet OK."


class AiMonitor:
    """Failure notifications (once per outage) and the daily health check."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._health = AiHealth()
        self._cancel: CALLBACK_TYPE | None = None

    @property
    def failing(self) -> bool:
        """The provider's last call failed."""
        return self._health.failing_since is not None

    @callback
    def async_sync(self) -> None:
        """Follow the options: start, stop or keep the daily health check."""
        self.async_stop()
        enabled, entity_id = get_ai_config(self._entry)
        if not enabled:
            self._health = AiHealth()
            return
        if entity_id is not None and get_health_check(self._entry):
            self._cancel = async_track_time_interval(
                self._hass, self._on_timer, AI_HEALTH_INTERVAL
            )

    @callback
    def async_stop(self) -> None:
        """Stop the daily health check."""
        if self._cancel is not None:
            self._cancel()
            self._cancel = None

    def record_success(self) -> None:
        """A provider call worked."""
        self._health = record_success(self._health)

    async def async_record_failure(self, error: str) -> None:
        """A provider call failed: tell the configured users, once per outage."""
        self._health, notify = record_failure(self._health, dt_util.utcnow())
        if not notify:
            return
        recipients = get_recipients(self._entry)
        if not recipients:
            _LOGGER.warning("The AI provider failed (nobody to notify): %s", error)
            return
        title, message = build_failure_message(self._hass.config.language, error)
        await async_notify_users(self._hass, recipients, title, message)

    async def async_health_check(self) -> bool:
        """One tiny provider call; records the outcome. True when it worked."""
        _enabled, entity_id = get_ai_config(self._entry)
        if entity_id is None:
            return False
        try:
            await self._hass.services.async_call(
                AI_TASK_DOMAIN,
                "generate_data",
                {
                    "entity_id": entity_id,
                    "task_name": HEALTH_TASK_NAME,
                    "instructions": HEALTH_INSTRUCTIONS,
                },
                blocking=True,
                return_response=True,
            )
        except HomeAssistantError as err:
            await self.async_record_failure(str(err))
            return False
        self.record_success()
        return True

    async def _on_timer(self, _now: datetime) -> None:
        await self.async_health_check()
