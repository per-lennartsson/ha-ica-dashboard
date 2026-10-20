"""Translated message templates for notifications (the I/O side of the domain)."""

from collections.abc import Iterable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN

CATEGORY = "exceptions"


async def async_get_templates(
    hass: HomeAssistant, keys: Iterable[str]
) -> dict[str, str]:
    """The message templates `keys` in Home Assistant's language.

    Languages without a translation fall back to English, which Home Assistant
    merges in. A key missing from every language raises KeyError (a packaging bug).
    """
    strings = await async_get_translations(
        hass, hass.config.language, CATEGORY, [DOMAIN]
    )
    return {
        key: strings[f"component.{DOMAIN}.{CATEGORY}.{key}.message"] for key in keys
    }
