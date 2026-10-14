"""Tests for add_item, tick_item, remove_item and clear_ticked."""

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.inkop.const import DOMAIN
from tests.conftest import FakeIca, FakeTodo, IcaConfigure, setup_inkop


@pytest.fixture
async def milk_list(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
) -> str:
    """A set-up Inköp with one active list; returns that list's entity id."""
    ica_dependency()
    entity_id = fake_ica.add_list("Veckan", "L-1", items=0)
    await setup_inkop(hass)
    return entity_id


async def _call(hass: HomeAssistant, service: str, **data: Any) -> dict[str, Any]:
    result = await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )
    assert result is not None
    return dict(result)


# --- add_item -----------------------------------------------------------------


async def test_add_item_to_the_active_list(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    result = await _call(hass, "add_item", item="2 st gurka")

    assert result["added"] is True
    assert result["duplicate"] is False
    assert result["item"] == "2 st gurka"
    assert result["entity_id"] == milk_list
    assert result["list_title"] == "Veckan"
    assert fake_todo.summaries(milk_list) == ["2 st gurka"]


async def test_add_item_normalises_the_text(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    await _call(hass, "add_item", item="  2   KG  Potatis ")
    await _call(hass, "add_item", item="1.5 l mjölk")

    assert fake_todo.summaries(milk_list) == ["2 kg Potatis", "1,5 l mjölk"]


async def test_add_item_to_an_explicit_list(
    hass: HomeAssistant, milk_list: str, fake_ica: FakeIca, fake_todo: FakeTodo
) -> None:
    other = fake_ica.add_list("Annan", "L-2")
    await hass.async_block_till_done()

    await _call(hass, "add_item", item="ägg", entity_id=other)

    assert fake_todo.summaries(other) == ["ägg"]
    assert fake_todo.summaries(milk_list) == []


async def test_duplicate_is_not_added_without_confirmation(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    uid = fake_todo.seed(milk_list, "1 l Mjölk")

    result = await _call(hass, "add_item", item="mjölk")

    assert result["added"] is False
    assert result["duplicate"] is True
    assert result["duplicates"] == [{"uid": uid, "summary": "1 l Mjölk"}]
    assert fake_todo.summaries(milk_list) == ["1 l Mjölk"]
    assert not fake_todo.calls_to("add_item")


async def test_duplicate_is_added_when_confirmed(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    fake_todo.seed(milk_list, "mjölk")

    result = await _call(hass, "add_item", item="MJÖLK", confirm_duplicate=True)

    assert result["added"] is True
    assert result["duplicate"] is True
    assert fake_todo.summaries(milk_list) == ["mjölk", "MJÖLK"]


async def test_ticked_item_is_not_a_duplicate(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    fake_todo.seed(milk_list, "mjölk", completed=True)

    result = await _call(hass, "add_item", item="mjölk")

    assert result["added"] is True
    assert result["duplicate"] is False


@pytest.mark.parametrize("text", ["", "   "])
async def test_empty_item_is_refused(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo, text: str
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "add_item", item=text)

    assert err.value.translation_key == "empty_item"
    assert not fake_todo.calls


async def test_add_without_any_list_is_refused(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
) -> None:
    ica_dependency()
    await setup_inkop(hass)

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "add_item", item="mjölk")

    assert err.value.translation_key == "no_list"


async def test_add_to_unknown_list_is_refused(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "add_item", item="mjölk", entity_id="todo.nope")

    assert err.value.translation_key == "unknown_list"


async def test_add_while_the_list_is_unavailable(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    hass.states.async_set(milk_list, "unavailable")
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "add_item", item="mjölk")

    assert err.value.translation_key == "list_unavailable"
    assert not fake_todo.calls


async def test_add_wraps_failures_from_the_todo_service(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    async def boom(call: Any) -> None:
        raise HomeAssistantError("ICA down")

    hass.services.async_remove("todo", "add_item")
    hass.services.async_register("todo", "add_item", boom)

    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, "add_item", item="mjölk")

    assert err.value.translation_key == "todo_failed"
    assert "ICA down" in err.value.translation_placeholders["error"]  # type: ignore[index]


# --- tick_item ----------------------------------------------------------------


async def test_tick_by_uid(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    uid = fake_todo.seed(milk_list, "mjölk")

    result = await _call(hass, "tick_item", item=uid)

    assert result["ticked"] is True
    assert result["changed"] is True
    assert fake_todo.status_of(milk_list, uid) == "completed"
    assert fake_todo.calls_to("update_item")[0]["item"] == uid


async def test_tick_by_text_and_untick(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    uid = fake_todo.seed(milk_list, "1 l mjölk")

    await _call(hass, "tick_item", item="Mjölk")
    assert fake_todo.status_of(milk_list, uid) == "completed"

    result = await _call(hass, "tick_item", item="mjölk", ticked=False)
    assert result["changed"] is True
    assert fake_todo.status_of(milk_list, uid) == "needs_action"


async def test_ticking_prefers_the_open_item(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    done = fake_todo.seed(milk_list, "mjölk", completed=True)
    open_ = fake_todo.seed(milk_list, "1 l mjölk")

    await _call(hass, "tick_item", item="mjölk")

    assert fake_todo.status_of(milk_list, open_) == "completed"
    assert fake_todo.status_of(milk_list, done) == "completed"


async def test_ticking_a_ticked_item_changes_nothing(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    fake_todo.seed(milk_list, "mjölk", completed=True)

    result = await _call(hass, "tick_item", item="mjölk")

    assert result["changed"] is False
    assert not fake_todo.calls_to("update_item")


async def test_tick_unknown_item(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "tick_item", item="smör")

    assert err.value.translation_key == "item_not_found"
    assert err.value.translation_placeholders == {"item": "smör"}


async def test_tick_ambiguous_item_lists_the_choices(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    fake_todo.seed(milk_list, "1 l mjölk")
    fake_todo.seed(milk_list, "2 st mjölk")

    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "tick_item", item="mjölk")

    assert err.value.translation_key == "item_ambiguous"
    assert err.value.translation_placeholders == {
        "item": "mjölk",
        "matches": "1 l mjölk, 2 st mjölk",
    }


async def test_identical_entries_are_interchangeable(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    first = fake_todo.seed(milk_list, "mjölk")
    fake_todo.seed(milk_list, "mjölk")

    result = await _call(hass, "tick_item", item="mjölk")

    assert result["uid"] == first


# --- remove_item --------------------------------------------------------------


async def test_remove_by_uid_and_by_text(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    uid = fake_todo.seed(milk_list, "mjölk")
    fake_todo.seed(milk_list, "2 st ägg")

    result = await _call(hass, "remove_item", item=uid)
    assert result["item"] == "mjölk"
    await _call(hass, "remove_item", item="ägg")

    assert fake_todo.summaries(milk_list) == []
    assert fake_todo.calls_to("remove_item")[0]["item"] == [uid]


async def test_remove_unknown_item(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "remove_item", item="smör")

    assert err.value.translation_key == "item_not_found"


# --- clear_ticked -------------------------------------------------------------


async def test_clear_ticked_removes_only_ticked_items(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    fake_todo.seed(milk_list, "mjölk", completed=True)
    fake_todo.seed(milk_list, "ägg")
    fake_todo.seed(milk_list, "smör", completed=True)

    result = await _call(hass, "clear_ticked")

    assert result["removed"] == 2
    assert result["items"] == ["mjölk", "smör"]
    assert fake_todo.summaries(milk_list) == ["ägg"]


async def test_clear_ticked_with_nothing_ticked(
    hass: HomeAssistant, milk_list: str, fake_todo: FakeTodo
) -> None:
    fake_todo.seed(milk_list, "ägg")

    result = await _call(hass, "clear_ticked")

    assert result["removed"] == 0
    assert not fake_todo.calls_to("remove_completed_items")


async def test_clear_ticked_on_an_explicit_list(
    hass: HomeAssistant, milk_list: str, fake_ica: FakeIca, fake_todo: FakeTodo
) -> None:
    other = fake_ica.add_list("Annan", "L-2")
    await hass.async_block_till_done()
    fake_todo.seed(milk_list, "mjölk", completed=True)
    fake_todo.seed(other, "ägg", completed=True)

    await _call(hass, "clear_ticked", entity_id=other)

    assert fake_todo.summaries(other) == []
    assert fake_todo.summaries(milk_list) == ["mjölk"]
