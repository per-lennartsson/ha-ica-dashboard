"""The optional AI module's switch and provider, read from the config entry."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .const import CONF_AI_ENABLED, CONF_AI_ENTITY
from .domain import AiStatus, ai_status


def get_ai_config(entry: ConfigEntry) -> tuple[bool, str | None]:
    """(enabled, ai_task entity id). Off unless explicitly on; bad data is off."""
    enabled = entry.options.get(CONF_AI_ENABLED) is True
    entity_id = entry.options.get(CONF_AI_ENTITY)
    if not isinstance(entity_id, str) or not entity_id:
        return enabled, None
    return enabled, entity_id


def provider_ready(hass: HomeAssistant, entity_id: str | None) -> bool:
    """The chosen ai_task entity exists and is not unavailable."""
    if entity_id is None:
        return False
    state = hass.states.get(entity_id)
    return state is not None and state.state != STATE_UNAVAILABLE


def current_ai_status(hass: HomeAssistant, entry: ConfigEntry) -> AiStatus:
    """Whether AI features may run right now."""
    enabled, entity_id = get_ai_config(entry)
    return ai_status(enabled, provider_ready(hass, entity_id))
