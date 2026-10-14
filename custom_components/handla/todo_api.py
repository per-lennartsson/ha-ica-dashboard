"""Thin wrappers around Home Assistant's todo.* services (the I/O layer)."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .domain import TodoItem

TODO_DOMAIN = "todo"
_COMPLETED = "completed"
_NEEDS_ACTION = "needs_action"


def _failed(entity_id: str, err: HomeAssistantError) -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="todo_failed",
        translation_placeholders={"entity_id": entity_id, "error": str(err)},
    )


async def _call(
    hass: HomeAssistant,
    service: str,
    entity_id: str,
    data: dict[str, Any] | None = None,
    *,
    response: bool = False,
) -> Any:
    try:
        return await hass.services.async_call(
            TODO_DOMAIN,
            service,
            {"entity_id": entity_id, **(data or {})},
            blocking=True,
            return_response=response,
        )
    except HomeAssistantError as err:
        raise _failed(entity_id, err) from err


async def async_get_items(hass: HomeAssistant, entity_id: str) -> list[TodoItem]:
    """All items on the list, open and ticked."""
    result = await _call(hass, "get_items", entity_id, response=True)
    raw = ((result or {}).get(entity_id) or {}).get("items") or []
    return [
        TodoItem(
            uid=str(item["uid"]),
            summary=str(item["summary"]),
            completed=item.get("status") == _COMPLETED,
        )
        for item in raw
        if item.get("uid") and item.get("summary")
    ]


async def async_add(hass: HomeAssistant, entity_id: str, summary: str) -> None:
    """Add an item."""
    await _call(hass, "add_item", entity_id, {"item": summary})


async def async_set_completed(
    hass: HomeAssistant, entity_id: str, uid: str, completed: bool
) -> None:
    """Tick or untick one item."""
    status = _COMPLETED if completed else _NEEDS_ACTION
    await _call(hass, "update_item", entity_id, {"item": uid, "status": status})


async def async_remove(hass: HomeAssistant, entity_id: str, uids: list[str]) -> None:
    """Remove items by uid."""
    await _call(hass, "remove_item", entity_id, {"item": uids})


async def async_remove_completed(hass: HomeAssistant, entity_id: str) -> None:
    """Remove every ticked item."""
    await _call(hass, "remove_completed_items", entity_id)
