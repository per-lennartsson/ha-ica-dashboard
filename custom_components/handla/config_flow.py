"""Config and options flow for Handla.

Setup refuses to start without a usable ha-ica-todo. The options choose which users
are told when someone adds items, and through which notify service.
"""

from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .ai import get_ai_config, get_health_check
from .const import (
    AI_TASK_DOMAIN,
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    CONF_AI_HEALTH_CHECK,
    CONF_RECIPIENTS,
    DOMAIN,
)
from .dependency import async_check_ica
from .domain import ai_choice_error, choose_notify_services
from .notify import get_recipients
from .schema import vol


class HandlaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-step flow that creates the one allowed config entry."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HandlaOptionsFlow:
        """Options: who gets notified, and the optional AI module."""
        return HandlaOptionsFlow()

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
            return self.async_create_entry(title="Handla", data={})
        return self.async_show_form(step_id="user")


class HandlaOptionsFlow(OptionsFlow):
    """A menu: notifications (users, then a notify service each) and the AI module."""

    def __init__(self) -> None:
        self._queue: list[str] = []
        self._names: dict[str, str] = {}
        self._chosen: dict[str, str] = {}

    async def _load_users(self) -> None:
        users = await self.hass.auth.async_get_users()
        self._names = {
            user.id: user.name or user.id
            for user in users
            if user.is_active and not user.system_generated
        }

    def _finish(self) -> ConfigFlowResult:
        options = {**self.config_entry.options, CONF_RECIPIENTS: self._chosen}
        return self.async_create_entry(data=options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """What to configure."""
        return self.async_show_menu(
            step_id="init", menu_options=["notifications", "ai"]
        )

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose which users are told about new items."""
        await self._load_users()
        if not self._names:
            return self.async_abort(reason="no_users")
        if user_input is not None:
            self._queue = [uid for uid in user_input["users"] if uid in self._names]
            self._chosen = {}
            if not self._queue:
                return self._finish()
            return await self.async_step_recipient()
        current = [
            uid for uid in get_recipients(self.config_entry) if uid in self._names
        ]
        options = [
            SelectOptionDict(value=uid, label=name)
            for uid, name in sorted(
                self._names.items(), key=lambda kv: kv[1].casefold()
            )
        ]
        schema = vol.Schema(
            {
                vol.Optional("users", default=current): SelectSelector(
                    SelectSelectorConfig(options=options, multiple=True)
                )
            }
        )
        return self.async_show_form(step_id="notifications", data_schema=schema)

    async def async_step_recipient(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the notify service for the next user in the queue."""
        services = choose_notify_services(
            self.hass.services.async_services_for_domain("notify")
        )
        if not services:
            return self.async_abort(reason="no_notify_services")
        user_id = self._queue[0]
        if user_input is not None:
            self._chosen[user_id] = user_input["service"]
            self._queue.pop(0)
            if not self._queue:
                return self._finish()
            user_id = self._queue[0]
            user_input = None
        saved = get_recipients(self.config_entry).get(user_id)
        schema = vol.Schema(
            {
                vol.Required(
                    "service", default=saved if saved in services else services[0]
                ): SelectSelector(SelectSelectorConfig(options=services))
            }
        )
        return self.async_show_form(
            step_id="recipient",
            data_schema=schema,
            description_placeholders={"name": self._names.get(user_id, user_id)},
        )

    async def async_step_ai(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Turn the optional AI module on or off and choose its ai_task entity."""
        enabled, saved = get_ai_config(self.config_entry)
        health_check = get_health_check(self.config_entry)
        errors: dict[str, str] = {}
        if user_input is not None:
            enabled = bool(user_input.get(CONF_AI_ENABLED))
            chosen = user_input.get(CONF_AI_ENTITY) or None
            health_check = bool(user_input.get(CONF_AI_HEALTH_CHECK))
            exists = chosen is not None and self.hass.states.get(chosen) is not None
            error = ai_choice_error(enabled, chosen, exists)
            if error is None:
                options = {
                    **self.config_entry.options,
                    CONF_AI_ENABLED: enabled,
                    CONF_AI_ENTITY: chosen,
                    CONF_AI_HEALTH_CHECK: health_check,
                }
                return self.async_create_entry(data=options)
            errors["base"] = error
            saved = chosen
        entity_key = (
            vol.Optional(CONF_AI_ENTITY, default=saved)
            if saved
            else vol.Optional(CONF_AI_ENTITY)
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_AI_ENABLED, default=enabled): BooleanSelector(),
                entity_key: EntitySelector(EntitySelectorConfig(domain=AI_TASK_DOMAIN)),
                vol.Required(
                    CONF_AI_HEALTH_CHECK, default=health_check
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="ai", data_schema=schema, errors=errors)
