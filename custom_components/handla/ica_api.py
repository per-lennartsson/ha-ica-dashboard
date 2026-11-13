"""Thin wrappers around ha-ica-todo's services (the I/O layer for ICA)."""

from collections.abc import Mapping

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import ICA_DOMAIN
from .domain import ArticleGroup, CategorizedItem, parse_categorized_items, parse_groups
from .errors import failure


def loaded_entry_id(hass: HomeAssistant) -> str:
    """The config entry of the loaded ha-ica-todo; an error if there is none."""
    for entry in hass.config_entries.async_entries(ICA_DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.entry_id
    raise failure("ica_unavailable")


async def async_create_list(
    hass: HomeAssistant, entry_id: str, name: str, comment: str
) -> str:
    """Create a tracked ICA list and return its ICA ID.

    ha-ica-todo reloads in the background, so the entity does not exist yet.
    """
    try:
        response = await hass.services.async_call(
            ICA_DOMAIN,
            "create_shopping_list",
            {
                "integration": [entry_id],
                "title": name,
                "comment": comment,
                "track": True,
            },
            blocking=True,
            return_response=True,
        )
    except HomeAssistantError as err:
        raise failure("create_failed", name=name, error=str(err)) from err
    offline_id = (response or {}).get("offline_id")
    if not offline_id:
        raise failure("create_failed", name=name, error="no list id returned")
    return str(offline_id)


async def async_delete_list(hass: HomeAssistant, entity_id: str, name: str) -> None:
    """Delete an ICA list; ha-ica-todo reloads in the background afterwards."""
    try:
        await hass.services.async_call(
            ICA_DOMAIN,
            "delete_shopping_list",
            {"entity_id": entity_id},
            blocking=True,
        )
    except HomeAssistantError as err:
        raise failure("delete_failed", name=name, error=str(err)) from err


def _uids(raw: object) -> list[str]:
    return [str(uid) for uid in raw] if isinstance(raw, list) else []


async def async_get_article_groups(hass: HomeAssistant) -> list[ArticleGroup]:
    """ICA's article groups (categories); ha-ica-todo falls back to a built-in list."""
    try:
        response = await hass.services.async_call(
            ICA_DOMAIN,
            "get_article_groups",
            {},
            blocking=True,
            return_response=True,
        )
    except HomeAssistantError as err:
        raise failure("categories_failed", error=str(err)) from err
    return parse_groups(response)


async def async_get_list_items(
    hass: HomeAssistant, entity_id: str
) -> list[CategorizedItem]:
    """The items on a list with their article group (read from ha-ica-todo's cache)."""
    try:
        response = await hass.services.async_call(
            ICA_DOMAIN,
            "get_shopping_list_items",
            {"entity_id": entity_id},
            blocking=True,
            return_response=True,
        )
    except HomeAssistantError as err:
        raise failure("categories_failed", error=str(err)) from err
    return parse_categorized_items((response or {}).get(entity_id))


async def async_set_article_groups(
    hass: HomeAssistant,
    entity_id: str,
    assignments: Mapping[str, int],
    *,
    remember: bool = True,
) -> dict[str, list[str]]:
    """Give items a new group in ICA. Returns the uids `updated` and `not_found`.

    With `remember`, ha-ica-todo gives later items with the same name that group.
    """
    try:
        response = await hass.services.async_call(
            ICA_DOMAIN,
            "set_item_article_group",
            {
                "entity_id": entity_id,
                "items": [
                    {"uid": uid, "article_group_id": group_id}
                    for uid, group_id in assignments.items()
                ],
                "remember": remember,
            },
            blocking=True,
            return_response=True,
        )
    except HomeAssistantError as err:
        raise failure("set_category_failed", error=str(err)) from err
    answer = (response or {}).get(entity_id)
    result = answer if isinstance(answer, dict) else {}
    return {key: _uids(result.get(key)) for key in ("updated", "not_found")}
