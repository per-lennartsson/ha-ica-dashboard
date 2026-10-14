"""Tests for the AI switch: options flow, status sensor, nothing runs when off."""

from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.handla.ai import get_ai_config
from custom_components.handla.const import (
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    DOMAIN,
)
from tests.conftest import (
    AI_ENTITY,
    FakeAiProvider,
    FakeIca,
    IcaConfigure,
    setup_handla,
)


def _ai_state(hass: HomeAssistant, entry: MockConfigEntry) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_ai"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def _open_ai(hass: HomeAssistant, entry: MockConfigEntry) -> FlowResult:
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    assert menu["type"] is FlowResultType.MENU
    assert menu["menu_options"] == ["notifications", "ai"]
    return await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "ai"}
    )


async def _submit(
    hass: HomeAssistant, result: FlowResult, data: dict[str, Any]
) -> FlowResult:
    return await hass.config_entries.options.async_configure(result["flow_id"], data)


async def _entry(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    ica_dependency()
    return await setup_handla(hass, options)


async def test_ai_is_off_by_default_and_registers_nothing(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    entry = await _entry(hass, ica_dependency, fake_ica)

    assert get_ai_config(entry) == (False, None)
    assert _ai_state(hass, entry).state == "off"
    assert not [s for s in hass.services.async_services_for_domain(DOMAIN) if "ai" in s]


async def test_form_defaults_to_off(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    entry = await _entry(hass, ica_dependency, fake_ica)
    result = await _open_ai(hass, entry)

    assert result["step_id"] == "ai"
    assert result["data_schema"]({}) == {CONF_AI_ENABLED: False}


async def test_turn_on_with_a_provider(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
) -> None:
    entry = await _entry(hass, ica_dependency, fake_ica, {"something": 1})
    result = await _submit(
        hass,
        await _open_ai(hass, entry),
        {CONF_AI_ENABLED: True, CONF_AI_ENTITY: AI_ENTITY},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_AI_ENABLED] is True
    assert entry.options[CONF_AI_ENTITY] == AI_ENTITY
    assert entry.options["something"] == 1  # other options are kept
    assert entry.state is ConfigEntryState.LOADED
    state = _ai_state(hass, entry)
    assert state.state == "ready"
    assert state.attributes["provider"] == AI_ENTITY


async def test_on_without_an_entity_is_refused(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    entry = await _entry(hass, ica_dependency, fake_ica)
    result = await _submit(hass, await _open_ai(hass, entry), {CONF_AI_ENABLED: True})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "ai_entity_required"}
    assert CONF_AI_ENABLED not in entry.options


async def test_unknown_entity_is_refused(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    entry = await _entry(hass, ica_dependency, fake_ica)
    result = await _submit(
        hass,
        await _open_ai(hass, entry),
        {CONF_AI_ENABLED: True, CONF_AI_ENTITY: "ai_task.nothing"},
    )

    assert result["errors"] == {"base": "ai_entity_unknown"}
    assert result["data_schema"]({CONF_AI_ENABLED: True}) == {
        CONF_AI_ENABLED: True,
        CONF_AI_ENTITY: "ai_task.nothing",
    }  # the typed choice is kept in the form
    assert CONF_AI_ENABLED not in entry.options


async def test_turning_off_always_works(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
) -> None:
    entry = await _entry(
        hass,
        ica_dependency,
        fake_ica,
        {CONF_AI_ENABLED: True, CONF_AI_ENTITY: AI_ENTITY},
    )
    assert _ai_state(hass, entry).state == "ready"
    fake_ai.remove()

    result = await _open_ai(hass, entry)
    assert result["data_schema"]({}) == {
        CONF_AI_ENABLED: True,
        CONF_AI_ENTITY: AI_ENTITY,
    }
    result = await _submit(hass, result, {CONF_AI_ENABLED: False})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_AI_ENABLED] is False
    assert _ai_state(hass, entry).state == "off"
    assert "provider" not in _ai_state(hass, entry).attributes


async def test_status_follows_the_provider(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
) -> None:
    entry = await _entry(
        hass,
        ica_dependency,
        fake_ica,
        {CONF_AI_ENABLED: True, CONF_AI_ENTITY: AI_ENTITY},
    )
    assert _ai_state(hass, entry).state == "ready"

    fake_ai.set_state("unavailable")
    await hass.async_block_till_done()
    assert _ai_state(hass, entry).state == "unavailable"

    fake_ai.set_state("2026-10-14T13:00:00+00:00")
    await hass.async_block_till_done()
    assert _ai_state(hass, entry).state == "ready"

    fake_ai.remove()
    await hass.async_block_till_done()
    assert _ai_state(hass, entry).state == "unavailable"


async def test_other_entities_do_not_touch_the_status(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
) -> None:
    entry = await _entry(
        hass,
        ica_dependency,
        fake_ica,
        {CONF_AI_ENABLED: True, CONF_AI_ENTITY: AI_ENTITY},
    )
    before = _ai_state(hass, entry).last_updated

    hass.states.async_set("ai_task.other", "x")
    await hass.async_block_till_done()

    assert _ai_state(hass, entry).last_updated == before


async def test_malformed_options_mean_off(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    entry = await _entry(
        hass, ica_dependency, fake_ica, {CONF_AI_ENABLED: "yes", CONF_AI_ENTITY: 5}
    )

    assert get_ai_config(entry) == (False, None)
    assert _ai_state(hass, entry).state == "off"
