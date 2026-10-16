"""Tests for usage statistics in the integration: counting, storage, sensor, service."""

from typing import Any

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.handla.const import DOMAIN
from custom_components.handla.domain import DEFAULT_QUICK_ITEMS
from custom_components.handla.schema import vol
from tests.conftest import FakeIca, FakeTodo, IcaConfigure, setup_handla

STORE_KEY = f"{DOMAIN}.usage"


@pytest.fixture
async def active_list(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
) -> str:
    ica_dependency()
    return fake_ica.add_list("Veckan", "L-1")


async def _add(hass: HomeAssistant, item: str, **data: Any) -> dict[str, Any]:
    result = await hass.services.async_call(
        DOMAIN,
        "add_item",
        {"item": item, **data},
        blocking=True,
        return_response=True,
    )
    assert result is not None
    return dict(result)


async def _top(hass: HomeAssistant, **data: Any) -> list[dict[str, Any]]:
    result = await hass.services.async_call(
        DOMAIN, "get_top_items", data, blocking=True, return_response=True
    )
    assert result is not None
    return list(result["items"])


def _sensor(hass: HomeAssistant, entry_id: str) -> State:
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry_id}_frequent_items"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def test_adds_are_counted_by_name(hass: HomeAssistant, active_list: str) -> None:
    await setup_handla(hass)

    await _add(hass, "2 st gurka")
    await _add(hass, "Gurka", confirm_duplicate=True)
    await _add(hass, "1 l mjölk")

    assert await _top(hass) == [
        {"name": "Gurka", "count": 2, "icon": "mdi:leaf", "pinned": False},
        {"name": "mjölk", "count": 1, "icon": "mdi:cow", "pinned": False},
    ]


async def test_an_unconfirmed_duplicate_is_not_counted(
    hass: HomeAssistant, active_list: str, fake_todo: FakeTodo
) -> None:
    await setup_handla(hass)
    fake_todo.seed(active_list, "mjölk")

    result = await _add(hass, "mjölk")

    assert result["added"] is False
    assert await _top(hass) == []


async def test_failed_adds_are_not_counted(
    hass: HomeAssistant, active_list: str
) -> None:
    await setup_handla(hass)
    hass.states.async_set(active_list, "unavailable")
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as err:
        await _add(hass, "mjölk")
    assert err.value.translation_key == "list_unavailable"

    assert await _top(hass) == []


async def test_ticking_and_removing_do_not_count(
    hass: HomeAssistant, active_list: str, fake_todo: FakeTodo
) -> None:
    await setup_handla(hass)
    fake_todo.seed(active_list, "mjölk")

    await hass.services.async_call(
        DOMAIN, "tick_item", {"item": "mjölk"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "remove_item", {"item": "mjölk"}, blocking=True
    )

    assert await _top(hass) == []


async def test_top_items_limit(hass: HomeAssistant, active_list: str) -> None:
    await setup_handla(hass)
    for name in ("a", "b", "c"):
        await _add(hass, name)

    assert len(await _top(hass, limit=2)) == 2
    assert len(await _top(hass)) == 3


async def test_top_items_rejects_a_bad_limit(
    hass: HomeAssistant, active_list: str
) -> None:
    await setup_handla(hass)

    with pytest.raises(vol.Invalid):
        await _top(hass, limit=0)


async def test_sensor_follows_the_counts(hass: HomeAssistant, active_list: str) -> None:
    entry = await setup_handla(hass)
    assert _sensor(hass, entry.entry_id).state == "0"
    # No history yet: staples with count 0 so the card has buttons from day one
    staples = _sensor(hass, entry.entry_id).attributes["items"]
    assert [i["name"] for i in staples] == list(DEFAULT_QUICK_ITEMS)
    assert {i["count"] for i in staples} == {0}

    await _add(hass, "kaffe")
    await _add(hass, "kaffe", confirm_duplicate=True)
    await _add(hass, "ananas")
    await hass.async_block_till_done()

    state = _sensor(hass, entry.entry_id)
    assert state.state == "2"  # only real items are counted
    items = state.attributes["items"]
    assert [(i["name"], i["count"]) for i in items[:2]] == [("kaffe", 2), ("ananas", 1)]
    assert len(items) == 8
    assert [i["name"] for i in items].count(
        "kaffe"
    ) == 1  # staples never repeat a real item


async def test_sensor_limits_to_the_quick_add_count(
    hass: HomeAssistant, active_list: str
) -> None:
    entry = await setup_handla(hass)
    for number in range(15):
        await _add(hass, f"vara {number}")
    await hass.async_block_till_done()

    state = _sensor(hass, entry.entry_id)
    assert state.state == "15"
    assert len(state.attributes["items"]) == 12


async def test_counts_are_saved_when_unloading_and_restored(
    hass: HomeAssistant, active_list: str, hass_storage: dict[str, Any]
) -> None:
    entry = await setup_handla(hass)
    await _add(hass, "mjölk")
    await _add(hass, "mjölk", confirm_duplicate=True)

    assert await hass.config_entries.async_unload(entry.entry_id)
    saved = hass_storage[STORE_KEY]["data"]["entries"]
    assert saved["mjölk"]["count"] == 2
    assert saved["mjölk"]["name"] == "mjölk"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await _top(hass) == [
        {"name": "mjölk", "count": 2, "icon": "mdi:cow", "pinned": False}
    ]


async def test_counts_are_restored_from_storage(
    hass: HomeAssistant, active_list: str, hass_storage: dict[str, Any]
) -> None:
    hass_storage[STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {
            "entries": {
                "ost": {"name": "Ost", "count": 7, "last_used": "2026-10-01T00:00:00"}
            }
        },
    }
    await setup_handla(hass)

    assert await _top(hass) == [
        {"name": "Ost", "count": 7, "icon": "mdi:cheese", "pinned": False}
    ]


async def test_corrupt_storage_starts_empty(
    hass: HomeAssistant, active_list: str, hass_storage: dict[str, Any]
) -> None:
    hass_storage[STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {"entries": {"x": {"nope": 1}, "y": "bad"}},
    }
    await setup_handla(hass)

    assert await _top(hass) == []


async def test_get_top_items_needs_a_set_up_integration(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as err:
        await _top(hass)

    assert err.value.translation_key == "not_set_up"


# --- managing the quick-add items ---


async def _manage(hass: HomeAssistant, service: str, **data: Any) -> None:
    await hass.services.async_call(DOMAIN, service, data, blocking=True)


async def test_remove_quick_item_updates_service_and_sensor(
    hass: HomeAssistant, active_list: str
) -> None:
    entry = await setup_handla(hass)
    await _add(hass, "Gurka")
    await _manage(hass, "remove_quick_item", item="gurka")

    assert await _top(hass) == []
    assert _sensor(hass, entry.entry_id).state == "0"


async def test_merge_quick_items_sums_and_keeps_counting_the_target(
    hass: HomeAssistant, active_list: str
) -> None:
    await setup_handla(hass)
    await _add(hass, "tomat")
    await _add(hass, "tomater")
    await _add(hass, "tomater", confirm_duplicate=True)
    await _manage(
        hass, "merge_quick_items", sources=["tomat", "tomater"], target="Tomater"
    )

    top = await _top(hass)
    assert [(i["name"], i["count"]) for i in top] == [("Tomater", 3)]

    await _add(hass, "Tomat", confirm_duplicate=True)
    top = await _top(hass)
    assert [(i["name"], i["count"]) for i in top] == [("Tomater", 4)]


async def test_add_quick_item_is_pinned_first(
    hass: HomeAssistant, active_list: str
) -> None:
    await setup_handla(hass)
    await _add(hass, "mjölk")
    await _add(hass, "mjölk", confirm_duplicate=True)
    await _manage(hass, "add_quick_item", item="Toalettpapper")

    top = await _top(hass)
    assert [(i["name"], i["pinned"]) for i in top] == [
        ("Toalettpapper", True),
        ("mjölk", False),
    ]


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("remove_quick_item", {"item": "smör"}),
        ("merge_quick_items", {"sources": ["smör"], "target": "Smör"}),
        ("merge_quick_items", {"sources": ["smör"], "target": " "}),
        ("add_quick_item", {"item": "  "}),
    ],
)
async def test_invalid_manage_calls_raise_a_readable_error(
    hass: HomeAssistant, active_list: str, service: str, data: dict[str, Any]
) -> None:
    await setup_handla(hass)
    with pytest.raises(ServiceValidationError):
        await _manage(hass, service, **data)


async def test_manage_changes_and_aliases_are_saved(
    hass: HomeAssistant, active_list: str, hass_storage: dict[str, Any]
) -> None:
    entry = await setup_handla(hass)
    await _add(hass, "tomat")
    await _add(hass, "tomater")
    await _manage(
        hass, "merge_quick_items", sources=["tomat", "tomater"], target="Tomater"
    )
    await _manage(hass, "add_quick_item", item="Disktrasa")

    assert await hass.config_entries.async_unload(entry.entry_id)
    data = hass_storage[STORE_KEY]["data"]
    assert data["aliases"] == {"tomat": "tomater"}
    assert data["entries"]["disktrasa"]["pinned"] is True

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert [i["name"] for i in await _top(hass)] == ["Disktrasa", "Tomater"]
