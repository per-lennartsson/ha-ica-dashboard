"""Services: set_active_list, create_list, delete_list."""

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from . import shopping
from .const import DOMAIN, QUICK_ADD_LIMIT
from .coordinator import HandlaCoordinator
from .schema import vol

SET_ACTIVE_LIST_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.entity_id})
CREATE_LIST_SCHEMA = vol.Schema(
    {
        vol.Optional("title"): cv.string,
        vol.Optional("comment", default=""): cv.string,
        vol.Optional("set_active", default=True): cv.boolean,
    }
)
DELETE_LIST_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.entity_id})
ADD_ITEM_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id"): cv.entity_id,
        vol.Required("item"): cv.string,
        vol.Optional("confirm_duplicate", default=False): cv.boolean,
    }
)
TICK_ITEM_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id"): cv.entity_id,
        vol.Required("item"): cv.string,
        vol.Optional("ticked", default=True): cv.boolean,
    }
)
REMOVE_ITEM_SCHEMA = vol.Schema(
    {vol.Optional("entity_id"): cv.entity_id, vol.Required("item"): cv.string}
)
CLEAR_TICKED_SCHEMA = vol.Schema({vol.Optional("entity_id"): cv.entity_id})
GET_TOP_ITEMS_SCHEMA = vol.Schema(
    {
        vol.Optional("limit", default=QUICK_ADD_LIMIT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=50)
        )
    }
)


def _coordinator(hass: HomeAssistant) -> HandlaCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_set_up"
        )
    coordinator: HandlaCoordinator = entries[0].runtime_data
    return coordinator


def async_register_services(hass: HomeAssistant) -> None:
    """Register the Handla services (available once an entry is loaded)."""

    async def set_active_list(call: ServiceCall) -> None:
        await _coordinator(hass).async_set_active(call.data["entity_id"])

    async def create_list(call: ServiceCall) -> dict[str, Any]:
        return await _coordinator(hass).async_create_list(
            call.data.get("title"), call.data["comment"], call.data["set_active"]
        )

    async def delete_list(call: ServiceCall) -> dict[str, Any]:
        return await _coordinator(hass).async_delete_list(call.data["entity_id"])

    async def add_item(call: ServiceCall) -> dict[str, Any]:
        coordinator = _coordinator(hass)
        target = coordinator.resolve_list(call.data.get("entity_id"))
        result = await shopping.async_add_item(
            hass, target, call.data["item"], call.data["confirm_duplicate"]
        )
        if result["added"]:
            await coordinator.async_item_added(
                result, call.context.user_id, call.context
            )
        return result

    async def suggest_list_name(call: ServiceCall) -> dict[str, Any]:
        return {"name": _coordinator(hass).suggest_list_name()}

    async def get_top_items(call: ServiceCall) -> dict[str, Any]:
        return {"items": _coordinator(hass).usage.top(call.data["limit"])}

    async def tick_item(call: ServiceCall) -> dict[str, Any]:
        target = _coordinator(hass).resolve_list(call.data.get("entity_id"))
        return await shopping.async_tick_item(
            hass, target, call.data["item"], call.data["ticked"]
        )

    async def remove_item(call: ServiceCall) -> dict[str, Any]:
        target = _coordinator(hass).resolve_list(call.data.get("entity_id"))
        return await shopping.async_remove_item(hass, target, call.data["item"])

    async def clear_ticked(call: ServiceCall) -> dict[str, Any]:
        target = _coordinator(hass).resolve_list(call.data.get("entity_id"))
        return await shopping.async_clear_ticked(hass, target)

    for name, handler, schema in (
        ("add_item", add_item, ADD_ITEM_SCHEMA),
        ("tick_item", tick_item, TICK_ITEM_SCHEMA),
        ("remove_item", remove_item, REMOVE_ITEM_SCHEMA),
        ("clear_ticked", clear_ticked, CLEAR_TICKED_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )

    hass.services.async_register(
        DOMAIN,
        "suggest_list_name",
        suggest_list_name,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_top_items",
        get_top_items,
        schema=GET_TOP_ITEMS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "set_active_list", set_active_list, schema=SET_ACTIVE_LIST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        "create_list",
        create_list,
        schema=CREATE_LIST_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "delete_list",
        delete_list,
        schema=DELETE_LIST_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
