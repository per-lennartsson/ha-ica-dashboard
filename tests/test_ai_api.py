"""Tests for the ai_task.generate_data wrapper."""

from typing import Any

import pytest
from homeassistant.core import Context, HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from custom_components.handla import ai_api


def _register(hass: HomeAssistant, fail: bool = False) -> list[ServiceCall]:
    calls: list[ServiceCall] = []

    async def handler(call: ServiceCall) -> Any:
        calls.append(call)
        if fail:
            raise HomeAssistantError("no credits")
        return {"data": {"ok": True}}

    hass.services.async_register(
        "ai_task",
        "generate_data",
        handler,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return calls


async def test_sends_the_structure_and_context_when_given(hass: HomeAssistant) -> None:
    calls = _register(hass)
    context = Context(user_id="u1")
    result = await ai_api.async_generate_data(
        hass, "ai_task.x", "Task", "Do it", structure={"a": 1}, context=context
    )
    assert result == {"data": {"ok": True}}
    assert dict(calls[0].data) == {
        "entity_id": "ai_task.x",
        "task_name": "Task",
        "instructions": "Do it",
        "structure": {"a": 1},
    }
    assert calls[0].context.user_id == "u1"


async def test_leaves_out_the_structure_when_there_is_none(hass: HomeAssistant) -> None:
    calls = _register(hass)
    await ai_api.async_generate_data(hass, "ai_task.x", "Task", "Do it")
    assert "structure" not in calls[0].data


async def test_provider_errors_propagate(hass: HomeAssistant) -> None:
    _register(hass, fail=True)
    with pytest.raises(HomeAssistantError, match="no credits"):
        await ai_api.async_generate_data(hass, "ai_task.x", "Task", "Do it")
