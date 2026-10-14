"""Config flow for Inköp: refuses to start without a usable ha-ica-todo."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN
from .dependency import async_check_ica


class InkopConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-step flow that creates the one allowed config entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check the ICA dependency, ask for confirmation, then create the entry."""
        status = await async_check_ica(self.hass)
        if status.translation_key:
            return self.async_abort(
                reason=status.translation_key,
                description_placeholders=status.placeholders,
            )
        if user_input is not None:
            return self.async_create_entry(title="Inköp", data={})
        return self.async_show_form(step_id="user")
