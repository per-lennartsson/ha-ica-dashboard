"""Translated message templates for notifications (the I/O side of the domain)."""

from collections.abc import Iterable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_get_translations

from .const import DOMAIN, NOTIFY_LANGUAGE_AUTO

CATEGORY = "exceptions"


async def async_get_templates(
    hass: HomeAssistant, keys: Iterable[str], language: str = NOTIFY_LANGUAGE_AUTO
) -> dict[str, str]:
    """The message templates `keys` in `language` ("auto" is Home Assistant's own).

    Languages without a translation fall back to English, which Home Assistant
    merges in. A key missing from every language raises KeyError (a packaging bug).
    """
    chosen = hass.config.language if language == NOTIFY_LANGUAGE_AUTO else language
    strings = await async_get_translations(hass, chosen, CATEGORY, [DOMAIN])
    return {
        key: strings[f"component.{DOMAIN}.{CATEGORY}.{key}.message"] for key in keys
    }
