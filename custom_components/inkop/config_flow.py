"""Config flow for Inköp (minimal; dependency checks come in a later step)."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class InkopConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-step flow that creates the one allowed config entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for confirmation, then create the entry."""
        if user_input is not None:
            return self.async_create_entry(title="Inköp", data={})
        return self.async_show_form(step_id="user")
