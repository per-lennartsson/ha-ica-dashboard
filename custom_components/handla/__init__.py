"""The Handla integration: shopping lists on top of ha-ica-todo."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .card import async_register_card
from .const import DOMAIN
from .coordinator import HandlaConfigEntry, HandlaCoordinator
from .dependency import (
    async_check_ica,
    create_dependency_issue,
    delete_dependency_issue,
)
from .services import async_register_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SELECT, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services; they act on the loaded config entry."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HandlaConfigEntry) -> bool:
    """Set up Handla, or retry later (with a repair issue) if ICA is not usable.

    The dependency is only checked here, not while running: ha-ica-todo reloads
    whenever a list is created or deleted, which must not be reported as a problem.
    """
    status = await async_check_ica(hass)
    if status.problem is not None:
        create_dependency_issue(hass, status)
        raise ConfigEntryNotReady(
            f"ha-ica-todo is not usable ({status.problem}); version {status.version}"
        )
    delete_dependency_issue(hass)

    integration = await async_get_integration(hass, DOMAIN)
    await async_register_card(hass, str(integration.version))

    coordinator = HandlaCoordinator(hass, entry)
    await coordinator.async_start()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HandlaConfigEntry) -> bool:
    """Unload the platforms."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: HandlaConfigEntry) -> None:
    """Clean up the repair issue when the integration is removed."""
    delete_dependency_issue(hass)
