"""Services: lists, items, quick-add items and the optional AI helper."""

from collections.abc import Callable, Coroutine, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from . import ai, shopping
from .const import (
    DOMAIN,
    MAX_COMMENT_LENGTH,
    MAX_ITEM_LENGTH,
    MAX_LIST_TITLE_LENGTH,
    QUICK_ADD_LIMIT,
)
from .coordinator import HandlaCoordinator
from .domain import MAX_TRACKED, ListInfo, UsageError
from .schema import vol
from .usage import UsageTracker

ITEM_TEXT = vol.All(cv.string, vol.Length(max=MAX_ITEM_LENGTH))

SET_ACTIVE_LIST_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.entity_id})
CREATE_LIST_SCHEMA = vol.Schema(
    {
        vol.Optional("title"): vol.All(
            cv.string, vol.Length(max=MAX_LIST_TITLE_LENGTH)
        ),
        vol.Optional("comment", default=""): vol.All(
            cv.string, vol.Length(max=MAX_COMMENT_LENGTH)
        ),
        vol.Optional("set_active", default=True): cv.boolean,
    }
)
DELETE_LIST_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.entity_id})
ADD_ITEM_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id"): cv.entity_id,
        vol.Required("item"): ITEM_TEXT,
        vol.Optional("confirm_duplicate", default=False): cv.boolean,
    }
)
TICK_ITEM_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id"): cv.entity_id,
        vol.Required("item"): ITEM_TEXT,
        vol.Optional("ticked", default=True): cv.boolean,
    }
)
REMOVE_ITEM_SCHEMA = vol.Schema(
    {vol.Optional("entity_id"): cv.entity_id, vol.Required("item"): ITEM_TEXT}
)
CLEAR_TICKED_SCHEMA = vol.Schema({vol.Optional("entity_id"): cv.entity_id})
AI_EXTRACT_ITEMS_SCHEMA = vol.Schema(
    {vol.Optional("entity_id"): cv.entity_id, vol.Required("text"): cv.string}
)
GET_TOP_ITEMS_SCHEMA = vol.Schema(
    {
        vol.Optional("limit", default=QUICK_ADD_LIMIT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_TRACKED)
        )
    }
)
REMOVE_QUICK_ITEM_SCHEMA = vol.Schema({vol.Required("item"): ITEM_TEXT})
ADD_QUICK_ITEM_SCHEMA = vol.Schema({vol.Required("item"): ITEM_TEXT})
MERGE_QUICK_ITEMS_SCHEMA = vol.Schema(
    {
        vol.Required("sources"): vol.All(
            cv.ensure_list, [ITEM_TEXT], vol.Length(min=1, max=MAX_TRACKED)
        ),
        vol.Required("target"): ITEM_TEXT,
    }
)


type Handler = Callable[[ServiceCall], Coroutine[Any, Any, Any]]


@dataclass(frozen=True)
class ServiceSpec:
    """One service: its name, handler, input schema and kind of response."""

    name: str
    handler: Handler
    schema: Any
    response: SupportsResponse = SupportsResponse.NONE


def _coordinator(hass: HomeAssistant) -> HandlaCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_set_up"
        )
    coordinator: HandlaCoordinator = entries[0].runtime_data
    return coordinator


def _target_list(call: ServiceCall) -> ListInfo:
    """The list a call refers to: its `entity_id`, else the active list."""
    return _coordinator(call.hass).resolve_list(call.data.get("entity_id"))


@contextmanager
def _quick_items(hass: HomeAssistant) -> Iterator[UsageTracker]:
    """Change the quick-add items; a rejected change becomes a readable error."""
    coordinator = _coordinator(hass)
    try:
        yield coordinator.usage
    except UsageError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key=err.key
        ) from err
    coordinator.async_update_listeners()


# --- lists ---------------------------------------------------------------------


async def _set_active_list(call: ServiceCall) -> None:
    await _coordinator(call.hass).async_set_active(call.data["entity_id"])


async def _create_list(call: ServiceCall) -> dict[str, Any]:
    return await _coordinator(call.hass).async_create_list(
        call.data.get("title"), call.data["comment"], call.data["set_active"]
    )


async def _delete_list(call: ServiceCall) -> dict[str, Any]:
    return await _coordinator(call.hass).async_delete_list(call.data["entity_id"])


async def _suggest_list_name(call: ServiceCall) -> dict[str, Any]:
    return {"name": _coordinator(call.hass).suggest_list_name()}


# --- items ---------------------------------------------------------------------


async def _add_item(call: ServiceCall) -> dict[str, Any]:
    return await _coordinator(call.hass).async_add_item(
        call.data.get("entity_id"),
        call.data["item"],
        call.data["confirm_duplicate"],
        call.context,
    )


async def _tick_item(call: ServiceCall) -> dict[str, Any]:
    return await shopping.async_tick_item(
        call.hass, _target_list(call), call.data["item"], call.data["ticked"]
    )


async def _remove_item(call: ServiceCall) -> dict[str, Any]:
    return await shopping.async_remove_item(
        call.hass, _target_list(call), call.data["item"]
    )


async def _clear_ticked(call: ServiceCall) -> dict[str, Any]:
    return await shopping.async_clear_ticked(call.hass, _target_list(call))


# --- quick-add items -----------------------------------------------------------


async def _get_top_items(call: ServiceCall) -> dict[str, Any]:
    return {"items": _coordinator(call.hass).usage.top(call.data["limit"])}


async def _remove_quick_item(call: ServiceCall) -> None:
    with _quick_items(call.hass) as usage:
        usage.remove(call.data["item"])


async def _add_quick_item(call: ServiceCall) -> None:
    with _quick_items(call.hass) as usage:
        usage.pin(call.data["item"])


async def _merge_quick_items(call: ServiceCall) -> None:
    with _quick_items(call.hass) as usage:
        usage.merge(call.data["sources"], call.data["target"])


# --- ai ------------------------------------------------------------------------


async def _ai_extract_items(call: ServiceCall) -> dict[str, Any]:
    coordinator = _coordinator(call.hass)
    return await ai.async_extract_items(
        call.hass,
        coordinator.config_entry,
        coordinator.ai_monitor,
        _target_list(call),
        call.data["text"],
        call.context,
    )


_OPTIONAL = SupportsResponse.OPTIONAL
_ONLY = SupportsResponse.ONLY

SERVICES = (
    ServiceSpec("set_active_list", _set_active_list, SET_ACTIVE_LIST_SCHEMA),
    ServiceSpec("create_list", _create_list, CREATE_LIST_SCHEMA, _OPTIONAL),
    ServiceSpec("delete_list", _delete_list, DELETE_LIST_SCHEMA, _OPTIONAL),
    ServiceSpec("suggest_list_name", _suggest_list_name, vol.Schema({}), _ONLY),
    ServiceSpec("add_item", _add_item, ADD_ITEM_SCHEMA, _OPTIONAL),
    ServiceSpec("tick_item", _tick_item, TICK_ITEM_SCHEMA, _OPTIONAL),
    ServiceSpec("remove_item", _remove_item, REMOVE_ITEM_SCHEMA, _OPTIONAL),
    ServiceSpec("clear_ticked", _clear_ticked, CLEAR_TICKED_SCHEMA, _OPTIONAL),
    ServiceSpec("get_top_items", _get_top_items, GET_TOP_ITEMS_SCHEMA, _ONLY),
    ServiceSpec("remove_quick_item", _remove_quick_item, REMOVE_QUICK_ITEM_SCHEMA),
    ServiceSpec("add_quick_item", _add_quick_item, ADD_QUICK_ITEM_SCHEMA),
    ServiceSpec("merge_quick_items", _merge_quick_items, MERGE_QUICK_ITEMS_SCHEMA),
)
AI_SERVICES = (
    ServiceSpec("ai_extract_items", _ai_extract_items, AI_EXTRACT_ITEMS_SCHEMA, _ONLY),
)


def _register(hass: HomeAssistant, spec: ServiceSpec) -> None:
    hass.services.async_register(
        DOMAIN,
        spec.name,
        spec.handler,
        schema=spec.schema,
        supports_response=spec.response,
    )


def async_register_services(hass: HomeAssistant) -> None:
    """Register the Handla services (available once an entry is loaded)."""
    for spec in SERVICES:
        _register(hass, spec)


def async_sync_ai_services(hass: HomeAssistant, enabled: bool) -> None:
    """Register the AI services while the AI module is on, remove them when off."""
    for spec in AI_SERVICES:
        if not enabled:
            hass.services.async_remove(DOMAIN, spec.name)
        elif not hass.services.has_service(DOMAIN, spec.name):
            _register(hass, spec)
