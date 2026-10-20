"""Tests for the todo.* wrappers: parsing of answers and error mapping."""

from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from custom_components.handla import todo_api

ENTITY = "todo.ica_test"


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
        "todo", service, handler, supports_response=SupportsResponse.OPTIONAL
    )
    return calls


async def test_get_items_parses_and_skips_malformed(hass: HomeAssistant) -> None:
    _register(
        hass,
        "get_items",
        {
            ENTITY: {
                "items": [
                    {"uid": "1", "summary": "Mjölk", "status": "needs_action"},
                    {"uid": "2", "summary": "Bröd", "status": "completed"},
                    {"summary": "no uid"},
                    {"uid": "3"},
                ]
            }
        },
    )
    items = await todo_api.async_get_items(hass, ENTITY)
    assert [(i.uid, i.summary, i.completed) for i in items] == [
        ("1", "Mjölk", False),
        ("2", "Bröd", True),
    ]


@pytest.mark.parametrize("response", [{}, {ENTITY: {}}, {ENTITY: {"items": None}}])
async def test_get_items_handles_empty_answers(
    hass: HomeAssistant, response: Any
) -> None:
    _register(hass, "get_items", response)
    assert await todo_api.async_get_items(hass, ENTITY) == []


async def test_set_completed_sends_status(hass: HomeAssistant) -> None:
    calls = _register(hass, "update_item")
    await todo_api.async_set_completed(hass, ENTITY, "1", True)
    await todo_api.async_set_completed(hass, ENTITY, "1", False)
    assert [c["status"] for c in calls] == ["completed", "needs_action"]
    assert calls[0]["item"] == "1"


async def test_errors_are_mapped_to_todo_failed(hass: HomeAssistant) -> None:
    _register(hass, "add_item", fail=True)
    with pytest.raises(HomeAssistantError) as exc:
        await todo_api.async_add(hass, ENTITY, "Mjölk")
    assert exc.value.translation_key == "todo_failed"
    assert exc.value.translation_placeholders == {
        "entity_id": ENTITY,
        "error": "boom",
    }
