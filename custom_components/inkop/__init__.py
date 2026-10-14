"""The Inköp integration: shopping lists on top of ha-ica-todo."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .dependency import (
    async_check_ica,
    create_dependency_issue,
    delete_dependency_issue,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Inköp, or retry later (with a repair issue) if ICA is not usable.

    Only checked here, not while running: ha-ica-todo reloads whenever a list is
    created or deleted, which must not be reported as a problem.
    """
    status = await async_check_ica(hass)
    if status.problem is not None:
        create_dependency_issue(hass, status)
        raise ConfigEntryNotReady(
            f"ha-ica-todo is not usable ({status.problem}); version {status.version}"
        )
    delete_dependency_issue(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up the repair issue when the integration is removed."""
    delete_dependency_issue(hass)
