"""Building Handla's translated errors."""

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def failure(key: str, **placeholders: str) -> HomeAssistantError:
    """A HomeAssistantError whose message is the translation `key`."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders,
    )
