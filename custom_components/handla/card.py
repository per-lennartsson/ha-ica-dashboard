"""Serve the Lovelace card to Home Assistant's frontend."""

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url

# Home Assistant's documented import; it re-exports the class without declaring it
from homeassistant.components.http import StaticPathConfig  # type: ignore[attr-defined]
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_URL = "/handla/handla-card.js"
CARD_FILE = Path(__file__).parent / "www" / "handla-card.js"
_REGISTERED = "card_registered"


async def async_register_card(hass: HomeAssistant, version: str) -> bool:
    """Make the built card available at CARD_URL and load it in every dashboard.

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
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")
    data[_REGISTERED] = True
    return True
