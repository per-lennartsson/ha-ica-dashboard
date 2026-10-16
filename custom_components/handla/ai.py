"""The optional AI module's switch and provider, read from the config entry."""

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import todo_api
from .const import (
    AI_TASK_DOMAIN,
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    CONF_AI_HEALTH_CHECK,
    DOMAIN,
)
from .domain import (
    MAX_TEXT_LENGTH,
    AiStatus,
    ListInfo,
    ai_status,
    build_instructions,
    clean_suggestions,
    suggestions_payload,
)
from .domain.extraction import ITEMS_KEY, STRUCTURE, TASK_NAME

if TYPE_CHECKING:
    from .ai_monitor import AiMonitor


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


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def _answer_items(result: Any) -> Any:
    """The `items` field of ai_task's answer; a clear error if there is none."""
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, dict) or ITEMS_KEY not in data:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="ai_bad_answer"
        )
    return data[ITEMS_KEY]


async def _ask_provider(
    hass: HomeAssistant,
    monitor: AiMonitor,
    entity_id: str,
    text: str,
    context: Context | None,
) -> Any:
    try:
        result = await hass.services.async_call(
            AI_TASK_DOMAIN,
            "generate_data",
            {
                "entity_id": entity_id,
                "task_name": TASK_NAME,
                "instructions": build_instructions(text),
                "structure": STRUCTURE,
            },
            blocking=True,
            return_response=True,
            context=context,
        )
    except HomeAssistantError as err:
        await monitor.async_record_failure(str(err))
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="ai_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    monitor.record_success()
    return result


async def async_extract_items(
    hass: HomeAssistant,
    entry: ConfigEntry,
    monitor: AiMonitor,
    target: ListInfo,
    text: str,
    context: Context | None = None,
) -> dict[str, Any]:
    """Suggest shopping items from pasted text, marking those already on the list."""
    text = text.strip()
    if not text:
        raise _invalid("ai_text_empty")
    if len(text) > MAX_TEXT_LENGTH:
        raise _invalid("ai_text_too_long", max=str(MAX_TEXT_LENGTH))
    _enabled, entity_id = get_ai_config(entry)
    if entity_id is None or current_ai_status(hass, entry) is not AiStatus.READY:
        raise _invalid("ai_not_ready")

    result = await _ask_provider(hass, monitor, entity_id, text, context)
    suggestions = clean_suggestions(_answer_items(result))
    on_list = await todo_api.async_get_items(hass, target.entity_id)
    items = suggestions_payload(suggestions, on_list)
    return {
        "entity_id": target.entity_id,
        "list_title": target.title,
        "items": items,
        "count": len(items),
    }
