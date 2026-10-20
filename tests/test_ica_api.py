"""Tests for the ha-ica-todo wrappers: entry lookup, create and delete."""

from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.handla import ica_api


def _register(
    hass: HomeAssistant, service: str, response: Any = None, fail: bool = False
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def handler(call: ServiceCall) -> Any:
        calls.append(dict(call.data))
        if fail:
            raise HomeAssistantError("boom")
        return response

    hass.services.async_register(
        "ica", service, handler, supports_response=SupportsResponse.OPTIONAL
    )
    return calls


def test_loaded_entry_id_picks_the_loaded_entry(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain="ica", entry_id="off", state=ConfigEntryState.NOT_LOADED
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="ica", entry_id="on", state=ConfigEntryState.LOADED
    ).add_to_hass(hass)
    assert ica_api.loaded_entry_id(hass) == "on"


def test_loaded_entry_id_without_a_loaded_entry(hass: HomeAssistant) -> None:
    MockConfigEntry(domain="ica", state=ConfigEntryState.SETUP_RETRY).add_to_hass(hass)
    with pytest.raises(HomeAssistantError) as exc:
        ica_api.loaded_entry_id(hass)
    assert exc.value.translation_key == "ica_unavailable"


async def test_create_sends_a_tracked_list_and_returns_the_id(
    hass: HomeAssistant,
) -> None:
    calls = _register(hass, "create_shopping_list", {"offline_id": "L-9"})
    assert await ica_api.async_create_list(hass, "e1", "Veckan", "c") == "L-9"
    assert calls == [
        {"integration": ["e1"], "title": "Veckan", "comment": "c", "track": True}
    ]


@pytest.mark.parametrize("response", [{}, {"offline_id": ""}])
async def test_create_without_an_id_fails(hass: HomeAssistant, response: Any) -> None:
    _register(hass, "create_shopping_list", response)
    with pytest.raises(HomeAssistantError) as exc:
        await ica_api.async_create_list(hass, "e1", "Veckan", "")
    assert exc.value.translation_key == "create_failed"
    assert exc.value.translation_placeholders == {
        "name": "Veckan",
        "error": "no list id returned",
    }


async def test_create_error_is_mapped(hass: HomeAssistant) -> None:
    _register(hass, "create_shopping_list", fail=True)
    with pytest.raises(HomeAssistantError) as exc:
        await ica_api.async_create_list(hass, "e1", "Veckan", "")
    assert exc.value.translation_key == "create_failed"
    assert exc.value.translation_placeholders == {"name": "Veckan", "error": "boom"}


async def test_delete_sends_the_entity(hass: HomeAssistant) -> None:
    calls = _register(hass, "delete_shopping_list")
    await ica_api.async_delete_list(hass, "todo.ica_x", "X")
    assert calls == [{"entity_id": "todo.ica_x"}]


async def test_delete_error_is_mapped(hass: HomeAssistant) -> None:
    _register(hass, "delete_shopping_list", fail=True)
    with pytest.raises(HomeAssistantError) as exc:
        await ica_api.async_delete_list(hass, "todo.ica_x", "X")
    assert exc.value.translation_key == "delete_failed"
    assert exc.value.translation_placeholders == {"name": "X", "error": "boom"}
