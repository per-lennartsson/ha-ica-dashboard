"""ICA article groups (categories): parsing ha-ica-todo's answers and their order.

ICA gives every item an article group. Group 12 means "not specified". The order
below follows a typical walk through a store, so a list read top to bottom matches
the shop. Handla only reads and changes groups; matching items to groups is done by
ha-ica-todo.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

UNSPECIFIED_GROUP = 12

# A typical walk through the store; unknown ids go just before UNSPECIFIED_GROUP
STORE_ORDER = (4, 3, 6, 10, 5, 9, 7, 11, 8, UNSPECIFIED_GROUP)


@dataclass(frozen=True)
class ArticleGroup:
    """One ICA article group."""

    id: int
    name: str


@dataclass(frozen=True)
class CategorizedItem:
    """An item on a list with its article group."""

    uid: str
    name: str
    group_id: int
    completed: bool = False


def _group_id(raw: Any) -> int | None:
    """An integer id from a number or numeric text (booleans are not ids)."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    return None


def parse_group_id(raw: Any) -> int | None:
    """A valid group id from model or service data, or None."""
    return _group_id(raw)


def parse_groups(raw: Any) -> list[ArticleGroup]:
    """Groups from `ica.get_article_groups`; malformed entries are skipped."""
    entries = raw.get("article_groups") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return []
    groups: dict[int, ArticleGroup] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        group_id = _group_id(entry.get("id"))
        name = entry.get("name")
        if group_id is None or not isinstance(name, str) or not name.strip():
            continue
        groups.setdefault(group_id, ArticleGroup(group_id, name.strip()))
    return list(groups.values())


def parse_categorized_items(raw: Any) -> list[CategorizedItem]:
    """Items from `ica.get_shopping_list_items` for one entity.

    An item with no or an unreadable group is placed in UNSPECIFIED_GROUP.
    """
    entries = raw.get("items") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return []
    items: list[CategorizedItem] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        uid, name = entry.get("uid"), entry.get("product_name")
        if not uid or not isinstance(name, str) or not name.strip():
            continue
        group = entry.get("article_group")
        group_id = _group_id(group.get("id")) if isinstance(group, dict) else None
        items.append(
            CategorizedItem(
                uid=str(uid),
                name=name.strip(),
                group_id=UNSPECIFIED_GROUP if group_id is None else group_id,
                completed=entry.get("completed") is True,
            )
        )
    return items


def _order_key(group_id: int) -> tuple[int, int]:
    if group_id in STORE_ORDER:
        return (STORE_ORDER.index(group_id), 0)
    return (STORE_ORDER.index(UNSPECIFIED_GROUP) - 1, group_id)


def order_groups(groups: Iterable[ArticleGroup]) -> list[ArticleGroup]:
    """Groups in store order; unknown ids sit just before the unspecified group."""
    return sorted(groups, key=lambda group: _order_key(group.id))


def groups_payload(groups: Iterable[ArticleGroup]) -> list[dict[str, Any]]:
    """The groups in store order, for the card."""
    return [{"id": group.id, "name": group.name} for group in order_groups(groups)]


def items_payload(items: Iterable[CategorizedItem]) -> dict[str, int]:
    """uid to group id, for the card."""
    return {item.uid: item.group_id for item in items}
