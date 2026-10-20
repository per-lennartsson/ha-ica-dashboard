"""Thin wrapper around Home Assistant's `ai_task.generate_data` (the AI I/O layer)."""

from typing import Any

from homeassistant.core import Context, HomeAssistant

from .const import AI_TASK_DOMAIN


async def async_generate_data(
    hass: HomeAssistant,
    entity_id: str,
    task_name: str,
    instructions: str,
    *,
    structure: Any = None,
    context: Context | None = None,
) -> Any:
    """Ask the AI Task entity and return the service response.

    Raises HomeAssistantError when the provider fails; callers decide what that means.
    """
    data: dict[str, Any] = {
        "entity_id": entity_id,
        "task_name": task_name,
        "instructions": instructions,
    }
    if structure is not None:
        data["structure"] = structure
    return await hass.services.async_call(
        AI_TASK_DOMAIN,
        "generate_data",
        data,
        blocking=True,
        return_response=True,
        context=context,
    )
