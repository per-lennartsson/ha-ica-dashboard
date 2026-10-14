"""Tests for the notification options flow."""

from typing import Any

import pytest
from homeassistant.auth.models import User
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.handla.const import CONF_RECIPIENTS
from tests.conftest import FakeIca, IcaConfigure, setup_handla


def _register_phones(hass: HomeAssistant, *names: str) -> None:
    async def noop(call: ServiceCall) -> None:
        return None

    for name in names:
        hass.services.async_register("notify", name, noop)


@pytest.fixture
async def per(hass: HomeAssistant) -> User:
    return await hass.auth.async_create_user("Per")


@pytest.fixture
async def embla(hass: HomeAssistant) -> User:
    return await hass.auth.async_create_user("Embla")


async def _entry(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    ica_dependency()
    return await setup_handla(hass, options)


async def _init(hass: HomeAssistant, entry: MockConfigEntry) -> FlowResult:
    return await hass.config_entries.options.async_init(entry.entry_id)


def _user_choices(result: FlowResult) -> list[str]:
    selector = next(iter(result["data_schema"].schema.values()))
    return [option["label"] for option in selector.config["options"]]


async def test_choose_users_and_a_service_for_each(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    per: User,
    embla: User,
) -> None:
    _register_phones(hass, "mobile_app_per", "mobile_app_embla", "smtp")
    entry = await _entry(hass, ica_dependency, fake_ica)

    result = await _init(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert _user_choices(result) == ["Embla", "Per"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"users": [per.id, embla.id]}
    )
    assert result["step_id"] == "recipient"
    assert result["description_placeholders"] == {"name": "Per"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"service": "mobile_app_per"}
    )
    assert result["step_id"] == "recipient"
    assert result["description_placeholders"] == {"name": "Embla"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"service": "mobile_app_embla"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RECIPIENTS] == {
        per.id: "mobile_app_per",
        embla.id: "mobile_app_embla",
    }


async def test_only_companion_app_services_are_offered(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    per: User,
) -> None:
    _register_phones(hass, "mobile_app_per", "smtp")
    entry = await _entry(hass, ica_dependency, fake_ica)
    result = await _init(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"users": [per.id]}
    )

    selector = next(iter(result["data_schema"].schema.values()))
    assert selector.config["options"] == ["mobile_app_per"]


async def test_choosing_nobody_turns_notifications_off(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    per: User,
) -> None:
    _register_phones(hass, "mobile_app_per")
    entry = await _entry(
        hass, ica_dependency, fake_ica, {CONF_RECIPIENTS: {per.id: "mobile_app_per"}}
    )

    result = await _init(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"users": []}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RECIPIENTS] == {}


async def test_existing_choices_are_the_defaults(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    per: User,
    embla: User,
) -> None:
    _register_phones(hass, "mobile_app_per", "mobile_app_embla")
    entry = await _entry(
        hass,
        ica_dependency,
        fake_ica,
        {CONF_RECIPIENTS: {embla.id: "mobile_app_embla", "gone": "x"}},
    )

    result = await _init(hass, entry)
    assert result["data_schema"]({}) == {
        "users": [embla.id]
    }  # users that are gone drop out

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"users": [embla.id]}
    )
    assert result["data_schema"]({}) == {"service": "mobile_app_embla"}


async def test_other_options_are_kept(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    per: User,
) -> None:
    _register_phones(hass, "mobile_app_per")
    entry = await _entry(hass, ica_dependency, fake_ica, {"something": 1})
    result = await _init(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"users": []}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["something"] == 1


async def test_aborts_without_users(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    entry = await _entry(hass, ica_dependency, fake_ica)

    result = await _init(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_users"


async def test_system_and_inactive_users_are_not_offered(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    per: User,
) -> None:
    await hass.auth.async_create_system_user("Robot")
    away = await hass.auth.async_create_user("Away")
    await hass.auth.async_update_user(away, is_active=False)
    entry = await _entry(hass, ica_dependency, fake_ica)

    result = await _init(hass, entry)

    assert _user_choices(result) == ["Per"]


async def test_aborts_without_notify_services(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    per: User,
) -> None:
    entry = await _entry(hass, ica_dependency, fake_ica)
    result = await _init(hass, entry)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"users": [per.id]}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_notify_services"
