"""Thin wrappers around ha-ica-todo's services (the I/O layer for ICA)."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import ICA_DOMAIN
from .errors import failure


def loaded_entry_id(hass: HomeAssistant) -> str:
    """The config entry of the loaded ha-ica-todo; an error if there is none."""
    for entry in hass.config_entries.async_entries(ICA_DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.entry_id
    raise failure("ica_unavailable")


async def async_create_list(
    hass: HomeAssistant, entry_id: str, name: str, comment: str
) -> str:
    """Create a tracked ICA list and return its ICA ID.

    ha-ica-todo reloads in the background, so the entity does not exist yet.
    """
    try:
        response = await hass.services.async_call(
            ICA_DOMAIN,
            "create_shopping_list",
            {
                "integration": [entry_id],
                "title": name,
                "comment": comment,
                "track": True,
            },
            blocking=True,
            return_response=True,
        )
    except HomeAssistantError as err:
        raise failure("create_failed", name=name, error=str(err)) from err
    offline_id = (response or {}).get("offline_id")
    if not offline_id:
        raise failure("create_failed", name=name, error="no list id returned")
    return str(offline_id)


async def async_delete_list(hass: HomeAssistant, entity_id: str, name: str) -> None:
    """Delete an ICA list; ha-ica-todo reloads in the background afterwards."""
    try:
        await hass.services.async_call(
            ICA_DOMAIN,
            "delete_shopping_list",
            {"entity_id": entity_id},
            blocking=True,
        )
    except HomeAssistantError as err:
        raise failure("delete_failed", name=name, error=str(err)) from err
