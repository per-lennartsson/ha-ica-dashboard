"""The optional AI module's switch and provider, read from the config entry."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import ai_api, ica_api, todo_api
from .ai_monitor import AiMonitor
from .const import DOMAIN
from .domain import (
    MAX_TEXT_LENGTH,
    SCOPES,
    AiStatus,
    ListInfo,
    ai_status,
    build_categorize_instructions,
    build_instructions,
    category_suggestions_payload,
    choose_items,
    clean_category_suggestions,
    clean_suggestions,
    extraction,
    suggestions_payload,
)
from .domain import categorize as categorize_rules
from .domain.categories import UNSPECIFIED_GROUP
from .domain.extraction import ITEMS_KEY
from .options import get_ai_config


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
    task_name: str,
    instructions: str,
    structure: dict[str, Any],
    context: Context | None,
) -> Any:
    try:
        result = await ai_api.async_generate_data(
            hass,
            entity_id,
            task_name,
            instructions,
            structure=structure,
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

    result = await _ask_provider(
        hass,
        monitor,
        entity_id,
        extraction.TASK_NAME,
        build_instructions(text),
        extraction.STRUCTURE,
        context,
    )
    suggestions = clean_suggestions(_answer_items(result))
    on_list = await todo_api.async_get_items(hass, target.entity_id)
    items = suggestions_payload(suggestions, on_list)
    return {
        "entity_id": target.entity_id,
        "list_title": target.title,
        "items": items,
        "count": len(items),
    }


async def async_suggest_categories(
    hass: HomeAssistant,
    entry: ConfigEntry,
    monitor: AiMonitor,
    target: ListInfo,
    scope: str,
    context: Context | None = None,
) -> dict[str, Any]:
    """Suggest article groups for open items; nothing is changed on the list.

    Scope `unspecified` asks only about items without a group, `all` about every
    open item. Only item ids and names are sent to the provider.
    """
    if scope not in SCOPES:
        raise _invalid("ai_bad_scope")
    _enabled, entity_id = get_ai_config(entry)
    if entity_id is None or current_ai_status(hass, entry) is not AiStatus.READY:
        raise _invalid("ai_not_ready")

    groups = await ica_api.async_get_article_groups(hass)
    on_list = await ica_api.async_get_list_items(hass, target.entity_id)
    asked, truncated = choose_items(on_list, scope, UNSPECIFIED_GROUP)
    suggestions = []
    if asked:
        result = await _ask_provider(
            hass,
            monitor,
            entity_id,
            categorize_rules.TASK_NAME,
            build_categorize_instructions(asked, groups, UNSPECIFIED_GROUP),
            categorize_rules.STRUCTURE,
            context,
        )
        suggestions = clean_category_suggestions(_answer_items(result), asked, groups)
    items = category_suggestions_payload(suggestions)
    return {
        "entity_id": target.entity_id,
        "list_title": target.title,
        "items": items,
        "count": len(items),
        "asked": len(asked),
        "truncated": truncated,
    }
