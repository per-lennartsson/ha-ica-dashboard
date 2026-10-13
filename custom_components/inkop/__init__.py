"""The Inköp integration: shopping lists on top of ha-ica-todo."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Inköp integration (skeleton; services come in later steps)."""
    hass.data.setdefault(DOMAIN, {})
    return True
