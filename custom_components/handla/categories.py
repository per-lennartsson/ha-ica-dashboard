"""Reading and changing the article groups (categories) of items on a list."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import ica_api
from .const import DOMAIN
from .domain import ListInfo, groups_payload, items_payload


async def async_get_categories(hass: HomeAssistant, target: ListInfo) -> dict[str, Any]:
    """The groups in store order and each item's group, for the card."""
    groups = await ica_api.async_get_article_groups(hass)
    items = await ica_api.async_get_list_items(hass, target.entity_id)
    return {
        "entity_id": target.entity_id,
        "groups": groups_payload(groups),
        "items": items_payload(items),
    }


async def async_set_categories(
    hass: HomeAssistant, target: ListInfo, assignments: dict[str, int]
) -> dict[str, Any]:
    """Give items a new group; ha-ica-todo remembers the choice for later items."""
    known = {group.id for group in await ica_api.async_get_article_groups(hass)}
    unknown = sorted({group for group in assignments.values() if group not in known})
    if unknown:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_category",
            translation_placeholders={"group": ", ".join(map(str, unknown))},
        )
    result = await ica_api.async_set_article_groups(hass, target.entity_id, assignments)
    return {"entity_id": target.entity_id, **result}
