"""Tests for handla.ai_suggest_categories with a mocked ai_task provider."""

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.handla import ai
from custom_components.handla.const import CONF_AI_ENABLED, CONF_AI_ENTITY, DOMAIN
from custom_components.handla.domain import MAX_CATEGORIZE_ITEMS
from custom_components.handla.schema import vol
from tests.conftest import (
    AI_ENTITY,
    FakeAiProvider,
    FakeIca,
    FakeTodo,
    IcaConfigure,
    setup_handla,
)

ON = {CONF_AI_ENABLED: True, CONF_AI_ENTITY: AI_ENTITY}


@pytest.fixture
async def veckan(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
) -> str:
    """AI on; one list with an unplaced item, a placed one and a ticked one."""
    ica_dependency()
    entity_id = fake_ica.add_list("Veckan", "L-1")
    fake_ica.set_rows(
        entity_id,
        [
            ("a", "havremjölk", 12, False),
            ("b", "gurka", 4, False),
            ("c", "ost", 12, True),
        ],
    )
    await setup_handla(hass, ON)
    return entity_id


async def _suggest(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    result = await hass.services.async_call(
        DOMAIN, "ai_suggest_categories", data, blocking=True, return_response=True
    )
    assert result is not None
    return dict(result)


async def test_suggests_groups_for_unplaced_items_only_by_default(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    fake_ai.answer = {"items": [{"uid": "a", "group_id": 10}]}

    result = await _suggest(hass)

    assert result["entity_id"] == veckan
    assert result["items"] == [
        {"uid": "a", "name": "havremjölk", "current": 12, "suggested": 10}
    ]
    assert (result["count"], result["asked"], result["truncated"]) == (1, 1, False)
    (call,) = fake_ai.calls
    assert call["entity_id"] == AI_ENTITY
    assert "a | havremjölk" in call["instructions"]
    assert "gurka" not in call["instructions"]  # already placed
    assert "| ost" not in call["instructions"]  # ticked
    assert call["structure"]["items"]["selector"]["object"]["multiple"] is True


async def test_scope_all_asks_about_every_open_item(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    fake_ai.answer = {"items": [{"uid": "b", "group_id": 6}]}

    result = await _suggest(hass, scope="all")

    assert result["asked"] == 2
    assert [s["uid"] for s in result["items"]] == ["b"]
    assert "gurka" in fake_ai.calls[0]["instructions"]


async def test_nothing_to_ask_means_no_provider_call(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca, fake_ai: FakeAiProvider
) -> None:
    fake_ica.set_rows(veckan, [("b", "gurka", 4, False)])

    result = await _suggest(hass)

    assert (result["items"], result["asked"]) == ([], 0)
    assert fake_ai.calls == []


async def test_a_long_list_is_cut_and_says_so(
    hass: HomeAssistant, veckan: str, fake_ica: FakeIca, fake_ai: FakeAiProvider
) -> None:
    fake_ica.set_rows(
        veckan,
        [(f"u{n}", f"vara {n}", 12, False) for n in range(MAX_CATEGORIZE_ITEMS + 3)],
    )

    result = await _suggest(hass)

    assert (result["asked"], result["truncated"]) == (MAX_CATEGORIZE_ITEMS, True)


async def test_a_bad_answer_is_an_error(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    fake_ai.answer = {"oops": []}

    with pytest.raises(HomeAssistantError) as exc:
        await _suggest(hass)

    assert exc.value.translation_key == "ai_bad_answer"


async def test_a_provider_failure_is_reported_as_one(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    fake_ai.error = HomeAssistantError("credits used up")

    with pytest.raises(HomeAssistantError) as exc:
        await _suggest(hass)

    assert exc.value.translation_key == "ai_failed"
    assert "credits used up" in str(exc.value)


async def test_the_provider_being_unavailable_is_refused(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    fake_ai.set_state("unavailable")

    with pytest.raises(ServiceValidationError) as exc:
        await _suggest(hass)

    assert exc.value.translation_key == "ai_not_ready"
    assert fake_ai.calls == []


async def test_an_unknown_scope_is_refused(hass: HomeAssistant, veckan: str) -> None:
    with pytest.raises(vol.Invalid):
        await _suggest(hass, scope="everything")


async def test_the_service_exists_only_while_ai_is_on(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_dependency()
    fake_ica.add_list("Veckan", "L-1")
    await setup_handla(hass)

    assert not hass.services.has_service(DOMAIN, "ai_suggest_categories")
    assert hass.services.has_service(DOMAIN, "get_categories")


async def test_the_function_refuses_an_unknown_scope_itself(
    hass: HomeAssistant, veckan: str
) -> None:
    """The service schema catches this first; the function must not rely on it."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data

    with pytest.raises(ServiceValidationError) as exc:
        await ai.async_suggest_categories(
            hass,
            entry,
            coordinator.ai_monitor,
            coordinator.resolve_list(None),
            "everything",
        )

    assert exc.value.translation_key == "ai_bad_scope"
