"""Services: set_active_list, create_list, delete_list."""

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from . import shopping
from .const import DOMAIN
from .coordinator import InkopCoordinator

try:  # Home Assistant 2026.10+ validates with probatio
    import probatio as vol
except ImportError:  # pragma: no cover - older Home Assistant
    import voluptuous as vol  # type: ignore[no-redef]

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


def _coordinator(hass: HomeAssistant) -> InkopCoordinator:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="not_set_up"
        )
    coordinator: InkopCoordinator = entries[0].runtime_data
    return coordinator


def async_register_services(hass: HomeAssistant) -> None:
    """Register the Inköp services (available once an entry is loaded)."""

    async def set_active_list(call: ServiceCall) -> None:
        await _coordinator(hass).async_set_active(call.data["entity_id"])

    async def create_list(call: ServiceCall) -> dict[str, Any]:
        return await _coordinator(hass).async_create_list(
            call.data.get("title"), call.data["comment"], call.data["set_active"]
        )

    async def delete_list(call: ServiceCall) -> dict[str, Any]:
        return await _coordinator(hass).async_delete_list(call.data["entity_id"])

    async def add_item(call: ServiceCall) -> dict[str, Any]:
        target = _coordinator(hass).resolve_list(call.data.get("entity_id"))
        return await shopping.async_add_item(
            hass, target, call.data["item"], call.data["confirm_duplicate"]
        )

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
