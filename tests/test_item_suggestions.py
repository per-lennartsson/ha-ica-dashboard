"""Tests for handla.get_item_suggestions (mocked ha-ica-todo)."""

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.handla.const import DOMAIN
from custom_components.handla.schema import vol
from tests.conftest import FakeIca, IcaConfigure, setup_handla

ENTRIES = [
    {
        "name": "Mjölk",
        "source": "history",
        "count": 5,
        "article_group": {"id": 10, "name": "Mejeri"},
    },
    {"name": "Toalettpapper", "source": "article", "article_group": {"id": 9}},
    {"name": "Smör", "source": "favorite"},
]


@pytest.fixture
async def veckan(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> str:
    """Handla with one active list and some suggestions."""
    ica_dependency()
    entity_id = fake_ica.add_list("Veckan", "L-1")
    fake_ica.set_suggestions(ENTRIES)
    await setup_handla(hass)
    return entity_id


async def _call(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    result = await hass.services.async_call(
        DOMAIN, "get_item_suggestions", data, blocking=True, return_response=True
    )
    return dict(result or {})


async def test_returns_the_full_list_for_the_active_list(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    result = await _call(hass)

    assert result == {
        "items": [
            {"name": "Mjölk", "group_id": 10, "source": "history", "count": 5},
            {"name": "Toalettpapper", "group_id": 9, "source": "article", "count": 0},
            {"name": "Smör", "group_id": 12, "source": "favorite", "count": 0},
        ]
    }
    assert fake_ica.calls_to("get_item_suggestions") == [{"entity_id": veckan}]


async def test_passes_query_limit_and_list(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    other = fake_ica.add_list("Helgen", "L-2")

    result = await _call(hass, entity_id=other, query="mj", limit=5)

    assert [item["name"] for item in result["items"]] == ["Mjölk"]
    assert fake_ica.calls_to("get_item_suggestions") == [
        {"entity_id": other, "query": "mj", "limit": 5}
    ]


async def test_rejects_a_limit_out_of_range(hass: HomeAssistant, veckan: str) -> None:
    with pytest.raises(vol.Invalid):
        await _call(hass, limit=0)


async def test_reports_a_failure(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca
) -> None:
    async def boom(_data: dict[str, Any]) -> Any:
        raise HomeAssistantError("ICA is down")

    fake_ica.handlers["get_item_suggestions"] = boom

    with pytest.raises(HomeAssistantError) as exc:
        await _call(hass)
    assert exc.value.translation_key == "suggestions_failed"


async def test_an_older_ha_ica_todo_without_the_service_fails_clearly(
    hass: HomeAssistant, veckan: str
) -> None:
    hass.services.async_remove("ica", "get_item_suggestions")

    with pytest.raises(HomeAssistantError) as exc:
        await _call(hass)
    assert exc.value.translation_key == "suggestions_failed"
