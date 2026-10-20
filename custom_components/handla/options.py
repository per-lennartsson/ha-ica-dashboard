"""Reading Handla's options from the config entry (AI module and notifications)."""

from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    CONF_AI_HEALTH_CHECK,
    CONF_RECIPIENTS,
)


def get_ai_config(entry: ConfigEntry) -> tuple[bool, str | None]:
    """(enabled, ai_task entity id). Off unless explicitly on; bad data is off."""
    enabled = entry.options.get(CONF_AI_ENABLED) is True
    entity_id = entry.options.get(CONF_AI_ENTITY)
    if not isinstance(entity_id, str) or not entity_id:
        return enabled, None
    return enabled, entity_id


def get_health_check(entry: ConfigEntry) -> bool:
    """Whether the daily health check is on (off unless explicitly on)."""
    return entry.options.get(CONF_AI_HEALTH_CHECK) is True


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
