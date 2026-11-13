"""Tests for handla.get_categories and handla.set_category (mocked ha-ica-todo)."""

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.handla.const import DOMAIN, EVENT_ITEM_ADDED
from custom_components.handla.schema import vol
from tests.conftest import FakeIca, FakeTodo, IcaConfigure, setup_handla


@pytest.fixture
async def veckan(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
) -> str:
    """Handla with one active list that has three categorised rows."""
    ica_dependency()
    entity_id = fake_ica.add_list("Veckan", "L-1")
    fake_ica.set_rows(
        entity_id,
        [("a", "mjölk", 10, False), ("b", "gurka", 12, False), ("c", "ost", 10, True)],
    )
    await setup_handla(hass)
    return entity_id


async def _call(hass: HomeAssistant, service: str, **data: Any) -> dict[str, Any]:
    result = await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )
    return dict(result or {})


async def test_get_categories_returns_ordered_groups_and_item_groups(
    hass: HomeAssistant, veckan: str
) -> None:
    result = await _call(hass, "get_categories")

    assert result["entity_id"] == veckan
    assert [g["id"] for g in result["groups"]] == [4, 3, 6, 10, 5, 9, 7, 11, 8, 12]
    assert result["groups"][0] == {"id": 4, "name": "Frukt & Grönt"}
    assert result["items"] == {"a": 10, "b": 12, "c": 10}


async def test_get_categories_for_an_explicit_list(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    other = fake_ica.add_list("Helgen", "L-2")
    fake_ica.set_rows(other, [("z", "bröd", 3, False)])

    result = await _call(hass, "get_categories", entity_id=other)

    assert result["items"] == {"z": 3}


async def test_get_categories_reports_a_failure(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    async def boom(_data: dict[str, Any]) -> Any:
        raise HomeAssistantError("ICA is down")

    fake_ica.handlers["get_shopping_list_items"] = boom

    with pytest.raises(HomeAssistantError, match="ICA is down"):
        await _call(hass, "get_categories")


async def test_get_categories_reports_a_failure_to_read_the_groups(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    async def boom(_data: dict[str, Any]) -> Any:
        raise HomeAssistantError("no groups")

    fake_ica.handlers["get_article_groups"] = boom

    with pytest.raises(HomeAssistantError, match="no groups"):
        await _call(hass, "get_categories")


async def test_set_category_changes_groups_and_asks_ica_to_remember(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    result = await _call(
        hass,
        "set_category",
        items=[{"uid": "b", "group_id": 4}, {"uid": "gone", "group_id": 4}],
    )

    assert result == {"entity_id": veckan, "updated": ["b"], "not_found": ["gone"]}
    (call,) = fake_ica.calls_to("set_item_article_group")
    assert call == {
        "entity_id": veckan,
        "items": [
            {"uid": "b", "article_group_id": 4},
            {"uid": "gone", "article_group_id": 4},
        ],
        "remember": True,
    }
    assert (await _call(hass, "get_categories"))["items"]["b"] == 4


async def test_set_category_refuses_an_unknown_group(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    with pytest.raises(ServiceValidationError) as exc:
        await _call(hass, "set_category", items=[{"uid": "a", "group_id": 99}])

    assert exc.value.translation_key == "unknown_category"
    assert fake_ica.calls_to("set_item_article_group") == []


@pytest.mark.parametrize(
    "items",
    [[], [{"uid": "a"}], [{"uid": "", "group_id": 4}], [{"uid": "a", "group_id": -1}]],
)
async def test_set_category_validates_its_input(
    hass: HomeAssistant, veckan: str, items: list[dict[str, Any]]
) -> None:
    with pytest.raises(vol.Invalid):
        await _call(hass, "set_category", items=items)


async def test_set_category_reports_a_failure(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    async def boom(_data: dict[str, Any]) -> Any:
        raise HomeAssistantError("write failed")

    fake_ica.handlers["set_item_article_group"] = boom

    with pytest.raises(HomeAssistantError, match="write failed"):
        await _call(hass, "set_category", items=[{"uid": "a", "group_id": 4}])


async def test_a_malformed_ica_answer_means_nothing_was_updated(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    async def odd(_data: dict[str, Any]) -> Any:
        return {"something": "else"}

    fake_ica.handlers["set_item_article_group"] = odd

    result = await _call(hass, "set_category", items=[{"uid": "a", "group_id": 4}])

    assert result == {"entity_id": veckan, "updated": [], "not_found": []}


async def test_changing_a_category_is_not_an_add(
    hass: HomeAssistant, veckan: str
) -> None:
    """No "someone added items" event, so nobody is notified about a category change."""
    added = async_capture_events(hass, EVENT_ITEM_ADDED)

    await _call(hass, "set_category", items=[{"uid": "a", "group_id": 4}])
    await hass.async_block_till_done()

    assert added == []
