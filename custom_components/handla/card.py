"""Serve the Lovelace card to Home Assistant's frontend."""

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url

# Home Assistant's documented import; it re-exports the class without declaring it
from homeassistant.components.http import StaticPathConfig  # type: ignore[attr-defined]
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .domain.resources import find_resources, plan_resource

_LOGGER = logging.getLogger(__name__)

CARD_URL = "/handla/handla-card.js"
CARD_FILE = Path(__file__).parent / "www" / "handla-card.js"
_REGISTERED = "card_registered"


def _storage_resources(hass: HomeAssistant) -> ResourceStorageCollection | None:
    """The dashboard resources when they are editable (storage mode), else None."""
    resources = getattr(hass.data.get("lovelace"), "resources", None)
    return resources if isinstance(resources, ResourceStorageCollection) else None


async def _async_load_resources(
    resources: ResourceStorageCollection,
) -> list[dict[str, Any]]:
    """The stored resources (this loads them from storage on first use)."""
    await resources.async_get_info()
    return list(resources.async_items())


async def _async_register_resource(hass: HomeAssistant, url: str) -> bool:
    """Add or refresh the card as a dashboard resource; False if that is not possible.

    Home Assistant loads dashboard resources before it draws a dashboard, which a
    script added with add_extra_js_url does not get, so the card could be missing.
    """
    resources = _storage_resources(hass)
    if resources is None:
        return False
    action = plan_resource(await _async_load_resources(resources), CARD_URL, url)
    try:
        if action.kind == "create":
            await resources.async_create_item({"res_type": "module", "url": url})
        elif action.kind == "update" and action.item_id is not None:
            await resources.async_update_item(action.item_id, {"url": url})
    except HomeAssistantError as err:
        _LOGGER.warning("Could not register the Handla card as a resource: %s", err)
        return False
    return True


async def async_unregister_resource(hass: HomeAssistant) -> None:
    """Remove the card's dashboard resource, if Handla added one."""
    resources = _storage_resources(hass)
    if resources is None:
        return
    for item in find_resources(await _async_load_resources(resources), CARD_URL):
        try:
            await resources.async_delete_item(str(item["id"]))
        except HomeAssistantError as err:
            _LOGGER.warning("Could not remove the Handla card resource: %s", err)


async def async_register_card(hass: HomeAssistant, version: str) -> bool:
    """Make the built card available at CARD_URL and load it in every dashboard.

    Dashboards in storage mode get it as a resource; in YAML mode it is added as an
    extra script instead (add `/handla/handla-card.js` to your resources there).

    Returns False (and only logs) when the card has not been built or the web server
    is missing: the rest of Handla works without it.
    """
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(_REGISTERED):
        return True
    if not await hass.async_add_executor_job(CARD_FILE.is_file):
        _LOGGER.warning(
            "The Handla card file %s is missing; build the card (see docs/dev.md)",
            CARD_FILE,
        )
        return False
    if getattr(hass, "http", None) is None:
        _LOGGER.warning("The web server is not running; the Handla card is not served")
        return False
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_FILE), cache_headers=False)]
    )
    # The version in the URL makes browsers fetch a new build after an update
    url = f"{CARD_URL}?v={version}"
    if not await _async_register_resource(hass, url):
        add_extra_js_url(hass, url)
    data[_REGISTERED] = True
    return True
