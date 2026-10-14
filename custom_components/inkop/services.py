"""Services: set_active_list, create_list, delete_list."""

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

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
