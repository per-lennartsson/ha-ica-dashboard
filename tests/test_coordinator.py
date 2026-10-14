"""Tests for how the coordinator derives lists and keeps the active list."""

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.inkop.const import DOMAIN
from custom_components.inkop.coordinator import InkopCoordinator
from tests.conftest import (
    ICA_DOMAIN,
    ICA_ENTRY_ID,
    FakeIca,
    IcaConfigure,
    setup_inkop,
)


async def _coordinator(hass: HomeAssistant) -> InkopCoordinator:
    entry = await setup_inkop(hass)
    return entry.runtime_data  # type: ignore[no-any-return]


async def test_lists_are_read_from_ica_entities(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mjölk", "M-1", items=3, comment="snabbt")
    fake_ica.add_list("Bröd", "B-2", items=0)
    coordinator = await _coordinator(hass)

    assert [(i.title, i.offline_id, i.item_count) for i in coordinator.data.lists] == [
        ("Bröd", "B-2", 0),
        ("Mjölk", "M-1", 3),
    ]
    assert coordinator.data.lists[1].comment == "snabbt"


async def test_favourites_and_other_todo_entities_are_ignored(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "todo", ICA_DOMAIN, f"{ICA_ENTRY_ID}-baseitems", suggested_object_id="ica_fav"
    )
    registry.async_get_or_create(
        "todo", "local_todo", "something", suggested_object_id="other"
    )
    fake_ica.add_list("Mjölk", "M-1")
    coordinator = await _coordinator(hass)

    assert [i.title for i in coordinator.data.lists] == ["Mjölk"]


@pytest.mark.parametrize("state", ["unavailable", "unknown", ""])
async def test_item_count_is_none_when_state_is_not_a_number(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    state: str,
) -> None:
    ica_dependency()
    entity_id = fake_ica.add_list("Mjölk", "M-1", items=2)
    hass.states.async_set(entity_id, state, hass.states.get(entity_id).attributes)  # type: ignore[union-attr]
    coordinator = await _coordinator(hass)

    assert coordinator.data.lists[0].item_count is None


async def test_list_survives_a_reload_of_ica(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    """While ha-ica-todo reloads its entities have no state; the list must stay."""
    ica_dependency()
    entity_id = fake_ica.add_list("Mjölk", "M-1", items=2)
    coordinator = await _coordinator(hass)

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()

    (info,) = coordinator.data.lists
    assert (info.title, info.offline_id, info.item_count) == ("Mjölk", "M-1", None)


async def test_item_count_follows_state_changes(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    entity_id = fake_ica.add_list("Mjölk", "M-1", items=1)
    coordinator = await _coordinator(hass)

    hass.states.async_set(entity_id, "5", hass.states.get(entity_id).attributes)  # type: ignore[union-attr]
    await hass.async_block_till_done()

    assert coordinator.data.lists[0].item_count == 5


async def test_new_and_removed_lists_are_picked_up(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    coordinator = await _coordinator(hass)
    assert coordinator.data.lists == ()
    assert coordinator.data.active is None

    entity_id = fake_ica.add_list("Mjölk", "M-1")
    await hass.async_block_till_done()
    assert [i.title for i in coordinator.data.lists] == ["Mjölk"]
    assert coordinator.data.active_offline_id == "M-1"

    fake_ica.remove_list(entity_id)
    await hass.async_block_till_done()
    assert coordinator.data.lists == ()
    assert coordinator.data.active is None


async def test_first_list_by_title_is_active_by_default(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mjölk", "M-1")
    fake_ica.add_list("Bröd", "B-2")
    coordinator = await _coordinator(hass)

    assert coordinator.data.active_offline_id == "B-2"


async def test_set_active_list_service_and_persistence(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    hass_storage: dict[str, Any],
) -> None:
    ica_dependency()
    fake_ica.add_list("Bröd", "B-2")
    milk = fake_ica.add_list("Mjölk", "M-1")
    entry = await setup_inkop(hass)

    await hass.services.async_call(
        DOMAIN, "set_active_list", {"entity_id": milk}, blocking=True
    )

    assert entry.runtime_data.data.active_offline_id == "M-1"
    assert hass_storage[f"{DOMAIN}.active_list"]["data"] == {"offline_id": "M-1"}

    # After a restart the saved choice is restored
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.data.active_offline_id == "M-1"


async def test_saved_active_list_that_no_longer_exists_falls_back(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    hass_storage: dict[str, Any],
) -> None:
    ica_dependency()
    hass_storage[f"{DOMAIN}.active_list"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.active_list",
        "data": {"offline_id": "GONE"},
    }
    fake_ica.add_list("Mjölk", "M-1")
    coordinator = await _coordinator(hass)

    assert coordinator.data.active_offline_id == "M-1"


async def test_active_list_moves_when_it_disappears(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    bread = fake_ica.add_list("Bröd", "B-2")
    fake_ica.add_list("Mjölk", "M-1")
    coordinator = await _coordinator(hass)
    assert coordinator.data.active_offline_id == "B-2"

    fake_ica.remove_list(bread)
    await hass.async_block_till_done()

    assert coordinator.data.active_offline_id == "M-1"


async def test_set_active_list_rejects_unknown_entity(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mjölk", "M-1")
    await setup_inkop(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "set_active_list", {"entity_id": "todo.nope"}, blocking=True
        )


async def test_unrelated_state_changes_do_not_touch_the_lists(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mjölk", "M-1", items=1)
    coordinator = await _coordinator(hass)
    before = coordinator.data

    hass.states.async_set("sensor.unrelated", "1")
    hass.states.async_set("todo.not_ica", "9")
    await hass.async_block_till_done()

    assert coordinator.data is before


async def test_set_active_by_unknown_offline_id_is_refused(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Mjölk", "M-1")
    coordinator = await _coordinator(hass)

    with pytest.raises(ServiceValidationError):
        await coordinator.async_set_active_by_offline_id("nope")
    assert coordinator.data.active_offline_id == "M-1"


async def test_manual_refresh_recomputes(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    coordinator = await _coordinator(hass)
    fake_ica.add_list("Mjölk", "M-1")

    await coordinator.async_refresh()

    assert [i.offline_id for i in coordinator.data.lists] == ["M-1"]
