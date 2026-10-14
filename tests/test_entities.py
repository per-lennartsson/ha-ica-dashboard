"""Tests for the select and sensor entities."""

import asyncio

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.inkop.const import DOMAIN
from tests.conftest import FakeIca, IcaConfigure, setup_inkop


def _state(hass: HomeAssistant, platform: str, key: str, entry_id: str) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{entry_id}_{key}"
    )
    assert entity_id is not None, f"{platform}.{key} is not registered"
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def test_select_lists_titles_and_current(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mjölk", "M-1")
    fake_ica.add_list("Bröd", "B-2")
    entry = await setup_inkop(hass)

    state = _state(hass, "select", "active_list", entry.entry_id)
    assert state.attributes["options"] == ["Bröd", "Mjölk"]
    assert state.state == "Bröd"


async def test_select_option_changes_the_active_list(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mjölk", "M-1")
    fake_ica.add_list("Bröd", "B-2")
    entry = await setup_inkop(hass)
    entity_id = _state(hass, "select", "active_list", entry.entry_id).entity_id

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": "Mjölk"},
        blocking=True,
    )

    assert entry.runtime_data.data.active_offline_id == "M-1"
    assert hass.states.get(entity_id).state == "Mjölk"  # type: ignore[union-attr]


async def test_select_numbers_repeated_titles(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mat", "A-1")
    fake_ica.add_list("Mat", "B-2")
    entry = await setup_inkop(hass)
    state = _state(hass, "select", "active_list", entry.entry_id)

    assert state.attributes["options"] == ["Mat", "Mat (2)"]

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": state.entity_id, "option": "Mat (2)"},
        blocking=True,
    )
    assert entry.runtime_data.data.active_offline_id in {"A-1", "B-2"}
    assert hass.states.get(state.entity_id).state == "Mat (2)"  # type: ignore[union-attr]


async def test_select_without_lists(
    hass: HomeAssistant, ica_dependency: IcaConfigure
) -> None:
    ica_dependency()
    entry = await setup_inkop(hass)

    state = _state(hass, "select", "active_list", entry.entry_id)
    assert state.attributes["options"] == []
    assert state.state == "unknown"


async def test_items_sensor_follows_the_active_list(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    milk = fake_ica.add_list("Mjölk", "M-1", items=3)
    entry = await setup_inkop(hass)

    state = _state(hass, "sensor", "items", entry.entry_id)
    assert state.state == "3"
    assert state.attributes["list_title"] == "Mjölk"
    assert state.attributes["list_offline_id"] == "M-1"
    assert state.attributes["list_entity_id"] == milk

    hass.states.async_set(milk, "7", hass.states.get(milk).attributes)  # type: ignore[union-attr]
    await hass.async_block_till_done()
    assert hass.states.get(state.entity_id).state == "7"  # type: ignore[union-attr]


async def test_items_sensor_is_unknown_without_an_active_list(
    hass: HomeAssistant, ica_dependency: IcaConfigure
) -> None:
    ica_dependency()
    entry = await setup_inkop(hass)

    state = _state(hass, "sensor", "items", entry.entry_id)
    assert state.state == "unknown"
    assert "list_title" not in state.attributes


async def test_status_sensor_shows_progress_and_errors(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    entry = await setup_inkop(hass)
    status = _state(hass, "sensor", "status", entry.entry_id)
    assert status.state == "idle"
    assert status.attributes["options"] == ["idle", "creating", "deleting", "error"]

    gate = asyncio.Event()
    fake_ica.install_create("NEW-1", gate=gate)
    task = hass.async_create_task(
        hass.services.async_call(
            DOMAIN, "create_list", {"title": "X"}, blocking=True, return_response=True
        )
    )
    await asyncio.sleep(0.01)
    assert hass.states.get(status.entity_id).state == "creating"  # type: ignore[union-attr]

    gate.set()
    await task
    await hass.async_block_till_done()
    assert hass.states.get(status.entity_id).state == "idle"  # type: ignore[union-attr]


async def test_status_sensor_exposes_error_detail(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    entry = await setup_inkop(hass)
    status = _state(hass, "sensor", "status", entry.entry_id)
    fake_ica.responses["create_shopping_list"] = {"success": True}  # no id returned

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "create_list", {"title": "X"}, blocking=True, return_response=True
        )
    await hass.async_block_till_done()

    state = hass.states.get(status.entity_id)
    assert state is not None
    assert state.state == "error"
    assert state.attributes["detail"]


async def test_unload_and_reload_keep_entities(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mjölk", "M-1", items=2)
    entry = await setup_inkop(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert _state(hass, "sensor", "items", entry.entry_id).state == "2"


async def test_lists_sensor_shows_every_list_and_the_active_one(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    bread = fake_ica.add_list("Bröd", "B-2", items=2)
    milk = fake_ica.add_list("Mjölk", "M-1", items=0)
    entry = await setup_inkop(hass)

    state = _state(hass, "sensor", "lists", entry.entry_id)
    assert state.state == "2"
    assert state.attributes["active_offline_id"] == "B-2"
    assert state.attributes["lists"] == [
        {"entity_id": bread, "offline_id": "B-2", "title": "Bröd", "item_count": 2},
        {"entity_id": milk, "offline_id": "M-1", "title": "Mjölk", "item_count": 0},
    ]


async def test_lists_sensor_follows_counts_and_new_lists(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    milk = fake_ica.add_list("Mjölk", "M-1", items=1)
    entry = await setup_inkop(hass)

    hass.states.async_set(milk, "4", hass.states.get(milk).attributes)  # type: ignore[union-attr]
    fake_ica.add_list("Ägg", "E-3")
    await hass.async_block_till_done()

    state = _state(hass, "sensor", "lists", entry.entry_id)
    assert state.state == "2"
    counts = {i["title"]: i["item_count"] for i in state.attributes["lists"]}
    assert counts == {"Mjölk": 4, "Ägg": 0}


async def test_lists_sensor_without_lists(
    hass: HomeAssistant, ica_dependency: IcaConfigure
) -> None:
    ica_dependency()
    entry = await setup_inkop(hass)

    state = _state(hass, "sensor", "lists", entry.entry_id)
    assert state.state == "0"
    assert state.attributes["lists"] == []
    assert state.attributes["active_offline_id"] is None


async def test_items_sensor_has_a_cart_icon_for_badges(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mjölk", "M-1", items=3)
    entry = await setup_inkop(hass)

    state = _state(hass, "sensor", "items", entry.entry_id)
    assert state.attributes["icon"] == "mdi:cart-outline"
