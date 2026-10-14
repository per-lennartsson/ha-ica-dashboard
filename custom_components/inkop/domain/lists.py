"""Pure logic for shopping lists: titles, labels, active list and ICA events."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_ICA_PREFIX = "ICA "


@dataclass(frozen=True)
class ListInfo:
    """One ICA shopping list as seen through its Home Assistant todo entity."""

    entity_id: str
    offline_id: str
    title: str
    item_count: int | None = None
    comment: str | None = None


def lists_payload(lists: Sequence[ListInfo]) -> list[dict[str, Any]]:
    """Lists as plain dicts for the sensor the card reads."""
    return [
        {
            "entity_id": item.entity_id,
            "offline_id": item.offline_id,
            "title": item.title,
            "item_count": item.item_count,
        }
        for item in lists
    ]


def same_id(a: str | None, b: str | None) -> bool:
    """Compare ICA list IDs case-insensitively (ICA returns them in upper case)."""
    return a is not None and b is not None and a.casefold() == b.casefold()


def title_from_name(name: str | None, fallback: str) -> str:
    """Strip the "ICA " prefix ha-ica-todo puts in front of list titles."""
    if not name:
        return fallback
    stripped = name[len(_ICA_PREFIX) :] if name.startswith(_ICA_PREFIX) else name
    return stripped.strip() or fallback


def unique_labels(titles: Sequence[str]) -> list[str]:
    """Make titles unique for a select: a repeated title gets " (2)", " (3)"..."""
    seen: dict[str, int] = {}
    labels: list[str] = []
    for title in titles:
        key = title.casefold()
        seen[key] = seen.get(key, 0) + 1
        labels.append(title if seen[key] == 1 else f"{title} ({seen[key]})")
    return labels


def pick_active(
    lists: Sequence[ListInfo],
    preferred: str | None,
    current: str | None = None,
) -> str | None:
    """Choose the active list's offline ID.

    The preferred ID wins if that list exists, then the current one, then the first
    list by title. None when there are no lists.
    """
    for wanted in (preferred, current):
        for item in lists:
            if same_id(item.offline_id, wanted):
                return item.offline_id
    if not lists:
        return None
    return min(lists, key=lambda item: item.title.casefold()).offline_id


def event_mentions(event: Mapping[str, Any], key: str, offline_id: str) -> bool:
    """True if an `ica_lists_changed` payload lists `offline_id` under `key`."""
    ids: Iterable[str] = event.get(key) or []
    return any(same_id(item, offline_id) for item in ids)


def entity_for(event: Mapping[str, Any], offline_id: str) -> str | None:
    """Entity ID for `offline_id` from an `ica_lists_changed` payload, if any."""
    entities: Mapping[str, str] = event.get("entities") or {}
    for key, entity_id in entities.items():
        if same_id(key, offline_id):
            return entity_id
    return None
