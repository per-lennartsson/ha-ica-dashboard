"""Adding, ticking, removing and clearing items on an ICA shopping list."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import todo_api
from .const import DOMAIN
from .domain import (
    ListInfo,
    TodoItem,
    duplicate_items,
    normalize_name,
    parse_item_text,
    resolve_items,
)


def _ensure_available(hass: HomeAssistant, target: ListInfo) -> None:
    state = hass.states.get(target.entity_id)
    if state is None or state.state == "unavailable":
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="list_unavailable",
            translation_placeholders={"list": target.title},
        )


def _single(query: str, matches: list[TodoItem]) -> TodoItem:
    """The one item meant by `query`, or a clear error."""
    if not matches:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="item_not_found",
            translation_placeholders={"item": query},
        )
    # Several identical entries are interchangeable: take the first
    if len({normalize_name(m.summary) for m in matches}) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="item_ambiguous",
            translation_placeholders={
                "item": query,
                "matches": ", ".join(m.summary for m in matches),
            },
        )
    return matches[0]


def _context(target: ListInfo) -> dict[str, Any]:
    return {"entity_id": target.entity_id, "list_title": target.title}


async def async_add_item(
    hass: HomeAssistant, target: ListInfo, text: str, confirm_duplicate: bool
) -> dict[str, Any]:
    """Add an item, unless an open item with the same name exists and is unconfirmed."""
    parsed = parse_item_text(text)
    if not parsed.name:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="empty_item"
        )
    summary = parsed.summary
    _ensure_available(hass, target)
    duplicates = duplicate_items(
        summary, await todo_api.async_get_items(hass, target.entity_id)
    )
    base = {
        **_context(target),
        "item": summary,
        "duplicate": bool(duplicates),
        "duplicates": [{"uid": d.uid, "summary": d.summary} for d in duplicates],
    }
    if duplicates and not confirm_duplicate:
        return {**base, "added": False}
    await todo_api.async_add(hass, target.entity_id, summary)
    return {**base, "added": True}


async def async_tick_item(
    hass: HomeAssistant, target: ListInfo, query: str, ticked: bool
) -> dict[str, Any]:
    """Tick (or untick) the item meant by `query`."""
    _ensure_available(hass, target)
    items = await todo_api.async_get_items(hass, target.entity_id)
    item = _single(query, resolve_items(query, items, completed=not ticked))
    changed = item.completed != ticked
    if changed:
        await todo_api.async_set_completed(hass, target.entity_id, item.uid, ticked)
    return {
        **_context(target),
        "item": item.summary,
        "uid": item.uid,
        "ticked": ticked,
        "changed": changed,
    }


async def async_remove_item(
    hass: HomeAssistant, target: ListInfo, query: str
) -> dict[str, Any]:
    """Remove the item meant by `query`."""
    _ensure_available(hass, target)
    items = await todo_api.async_get_items(hass, target.entity_id)
    item = _single(query, resolve_items(query, items))
    await todo_api.async_remove(hass, target.entity_id, [item.uid])
    return {**_context(target), "item": item.summary, "uid": item.uid}


async def async_clear_ticked(hass: HomeAssistant, target: ListInfo) -> dict[str, Any]:
    """Remove all ticked items from the list."""
    _ensure_available(hass, target)
    items = await todo_api.async_get_items(hass, target.entity_id)
    ticked = [i for i in items if i.completed]
    if ticked:
        await todo_api.async_remove_completed(hass, target.entity_id)
    return {
        **_context(target),
        "removed": len(ticked),
        "items": [i.summary for i in ticked],
    }
