"""Item name suggestions: parsing ha-ica-todo's answer from `ica.get_item_suggestions`.

ha-ica-todo holds the item history and decides each name's category. Handla only
reads the answer defensively and passes it on.
"""

from dataclasses import dataclass
from typing import Any

from .categories import UNSPECIFIED_GROUP, parse_group_id


@dataclass(frozen=True)
class ItemSuggestion:
    """A name to pick while typing, with the group an item of that name gets."""

    name: str
    group_id: int
    source: str
    count: int


def _count(raw: Any) -> int:
    """A non-negative count from a number; anything else is 0."""
    if isinstance(raw, bool) or not isinstance(raw, int):
        return 0
    return max(raw, 0)


def _group(raw: Any) -> int:
    """The group id of an `article_group` entry; unknown or missing is 12."""
    group_id = parse_group_id(raw.get("id")) if isinstance(raw, dict) else None
    return UNSPECIFIED_GROUP if group_id is None else group_id


def parse_suggestions(raw: Any) -> list[ItemSuggestion]:
    """Suggestions from the `items` of an answer; malformed entries are skipped.

    The order of ha-ica-todo (most used first) is kept.
    """
    entries = raw.get("items") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return []
    suggestions: list[ItemSuggestion] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        source = entry.get("source")
        suggestions.append(
            ItemSuggestion(
                name=name.strip(),
                group_id=_group(entry.get("article_group")),
                source=source if isinstance(source, str) else "",
                count=_count(entry.get("count")),
            )
        )
    return suggestions


def suggestions_payload(suggestions: list[ItemSuggestion]) -> list[dict[str, Any]]:
    """The suggestions as plain data for the card."""
    return [
        {
            "name": item.name,
            "group_id": item.group_id,
            "source": item.source,
            "count": item.count,
        }
        for item in suggestions
    ]
