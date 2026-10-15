"""Tests for handla.ai_extract_items with a mocked ai_task provider."""

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.handla.const import CONF_AI_ENABLED, CONF_AI_ENTITY, DOMAIN
from custom_components.handla.domain import MAX_TEXT_LENGTH
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
    """Handla with AI on and one active list; returns that list's entity id."""
    ica_dependency()
    entity_id = fake_ica.add_list("Veckan", "L-1")
    await setup_handla(hass, ON)
    return entity_id


async def _extract(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    result = await hass.services.async_call(
        DOMAIN, "ai_extract_items", data, blocking=True, return_response=True
    )
    assert result is not None
    return dict(result)


async def test_extracts_cleans_and_marks_items(
    hass: HomeAssistant, veckan: str, fake_todo: FakeTodo, fake_ai: FakeAiProvider
) -> None:
    fake_todo.seed(veckan, "1 l Mjölk")
    fake_ai.answer = {"items": ["- 2 l mjölk", "salt", "4 st tomat", "2 st tomat"]}

    result = await _extract(hass, text="Pannkakor och tomatsås")

    assert result["entity_id"] == veckan
    assert result["list_title"] == "Veckan"
    assert result["count"] == 2
    milk, tomato = result["items"]
    assert (milk["item"], milk["on_list"], milk["selected"]) == (
        "2 l mjölk",
        True,
        False,
    )
    assert milk["existing"] == "1 l Mjölk"
    assert (tomato["item"], tomato["on_list"], tomato["selected"]) == (
        "6 st tomat",
        False,
        True,
    )
    assert fake_todo.summaries(veckan) == ["1 l Mjölk"]  # nothing was added


async def test_the_provider_gets_prompt_structure_and_the_chosen_entity(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    await _extract(hass, text="Pannkakor")

    (call,) = fake_ai.calls
    assert call["entity_id"] == AI_ENTITY
    assert "Pannkakor" in call["instructions"]
    assert call["structure"]["items"]["selector"] == {"text": {"multiple": True}}
    assert call["task_name"]


async def test_an_empty_answer_is_not_an_error(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    fake_ai.answer = {"items": []}

    result = await _extract(hass, text="Hej, hur mår du?")

    assert result["items"] == []
    assert result["count"] == 0


async def test_another_list_can_be_chosen(
    hass: HomeAssistant,
    veckan: str,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
) -> None:
    other = fake_ica.add_list("Fest", "L-2")
    await hass.async_block_till_done()
    fake_todo.seed(other, "ost")
    fake_ai.answer = {"items": ["ost"]}

    result = await _extract(hass, text="Ost", entity_id=other)

    assert result["list_title"] == "Fest"
    assert result["items"][0]["on_list"] is True


@pytest.mark.parametrize(
    "answer", [None, "text", {"other": []}, {"items": 5}, {"items": [1, {}]}]
)
async def test_unusable_answers(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider, answer: Any
) -> None:
    fake_ai.answer = answer
    if isinstance(answer, dict) and "items" in answer:
        assert (await _extract(hass, text="x"))["items"] == []  # nothing usable
        return
    with pytest.raises(HomeAssistantError) as err:
        await _extract(hass, text="x")
    assert err.value.translation_key == "ai_bad_answer"


async def test_provider_failure_is_reported(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    fake_ai.error = HomeAssistantError("credit balance is too low")

    with pytest.raises(HomeAssistantError) as err:
        await _extract(hass, text="Pannkakor")

    assert err.value.translation_key == "ai_failed"
    assert "credit balance is too low" in err.value.translation_placeholders["error"]


async def test_empty_and_too_long_text_never_reach_the_provider(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _extract(hass, text="   ")
    assert err.value.translation_key == "ai_text_empty"

    with pytest.raises(ServiceValidationError) as err:
        await _extract(hass, text="a" * (MAX_TEXT_LENGTH + 1))
    assert err.value.translation_key == "ai_text_too_long"
    assert fake_ai.calls == []


async def test_unavailable_provider_is_refused(
    hass: HomeAssistant, veckan: str, fake_ai: FakeAiProvider
) -> None:
    fake_ai.set_state("unavailable")
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await _extract(hass, text="Pannkakor")

    assert err.value.translation_key == "ai_not_ready"
    assert fake_ai.calls == []


# --- the service exists only while AI is on ---------------------------------------


async def test_no_ai_service_when_ai_is_off(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
) -> None:
    ica_dependency()
    await setup_handla(hass)

    assert not hass.services.has_service(DOMAIN, "ai_extract_items")


async def test_service_follows_the_options_switch(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
) -> None:
    ica_dependency()
    entry = await setup_handla(hass)

    hass.config_entries.async_update_entry(entry, options=ON)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "ai_extract_items")

    hass.config_entries.async_update_entry(
        entry, options={**ON, CONF_AI_ENABLED: False}
    )
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, "ai_extract_items")

    hass.config_entries.async_update_entry(entry, options=ON)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "ai_extract_items")

    await hass.config_entries.async_unload(entry.entry_id)
    assert not hass.services.has_service(DOMAIN, "ai_extract_items")
