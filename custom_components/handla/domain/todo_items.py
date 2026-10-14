"""Pure logic for items on a shopping list: duplicates and finding an item."""

from collections.abc import Iterable
from dataclasses import dataclass

from .duplicates import normalize_name
from .items import parse_item_text


@dataclass(frozen=True)
class TodoItem:
    """An item on a list as returned by Home Assistant's todo.get_items."""

    uid: str
    summary: str
    completed: bool = False


def _name(text: str) -> str:
    return normalize_name(parse_item_text(text).name)


def duplicate_items(candidate: str, items: Iterable[TodoItem]) -> list[TodoItem]:
    """Open items with the same name as `candidate` (quantity and unit ignored).

    Ticked items do not count: something already bought may be wanted again.
    """
    wanted = _name(candidate)
    if not wanted:
        return []
    return [i for i in items if not i.completed and _name(i.summary) == wanted]


def resolve_items(
    query: str, items: Iterable[TodoItem], completed: bool | None = None
) -> list[TodoItem]:
    """Find the items a user means by `query`, best match first.

    Order of matching: exact uid, same text (case and spaces ignored), same name.
    With `completed` set, an item in that state is preferred over a better text
    match in the other state, e.g. ticking "mjölk" picks the open one.
    """
    items = list(items)
    wanted_text = normalize_name(query)
    wanted_name = _name(query)
    by_uid = [i for i in items if i.uid == query.strip()]
    if by_uid:
        return by_uid
    tiers = (
        [i for i in items if normalize_name(i.summary) == wanted_text],
        [i for i in items if wanted_name and _name(i.summary) == wanted_name],
    )
    fallback: list[TodoItem] = []
    for tier in tiers:
        if not tier:
            continue
        if completed is None:
            return tier
        preferred = [i for i in tier if i.completed is completed]
        if preferred:
            return preferred
        fallback = fallback or tier
    return fallback
