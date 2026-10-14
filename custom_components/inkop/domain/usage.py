"""Usage statistics: how often each item name has been added.

Pure functions over plain data. Names are compared case-insensitively and without
quantity or unit, so "2 st Gurka" and "gurka" count as the same item.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .duplicates import normalize_name
from .icons import icon_for

MAX_TRACKED = 500

# Shown as quick-add buttons until real history takes over (Swedish staples)
DEFAULT_QUICK_ITEMS = (
    "mjölk",
    "bröd",
    "ägg",
    "smör",
    "ost",
    "kaffe",
    "bananer",
    "tomater",
)
MIN_QUICK_ITEMS = 8


@dataclass(frozen=True)
class UsageEntry:
    """How often an item was added, and when it was last added (ISO 8601)."""

    name: str
    count: int
    last_used: str


def record_use(
    entries: Mapping[str, UsageEntry], name: str, when: str
) -> dict[str, UsageEntry]:
    """Return a copy of `entries` with one more use of `name`.

    The latest spelling of the name is kept. A blank name changes nothing. When more
    than MAX_TRACKED names are tracked, the least used (oldest first) are dropped.
    """
    key = normalize_name(name)
    updated = dict(entries)
    if not key:
        return updated
    previous = updated.get(key)
    updated[key] = UsageEntry(
        name=" ".join(name.split()),
        count=(previous.count if previous else 0) + 1,
        last_used=when,
    )
    if len(updated) > MAX_TRACKED:
        keep = sorted(updated.items(), key=lambda kv: _rank(kv[1]), reverse=True)
        updated = dict(keep[:MAX_TRACKED])
    return updated


def _rank(entry: UsageEntry) -> tuple[int, str, str]:
    return entry.count, entry.last_used, entry.name.casefold()


def top_items(entries: Mapping[str, UsageEntry], limit: int) -> list[UsageEntry]:
    """The `limit` most added items: highest count first, then most recent."""
    if limit <= 0:
        return []
    ranked = sorted(entries.values(), key=lambda e: e.name.casefold())
    ranked.sort(key=lambda e: e.last_used, reverse=True)  # stable: ties keep the order
    ranked.sort(key=lambda e: e.count, reverse=True)
    return ranked[:limit]


def top_payload(entries: Mapping[str, UsageEntry], limit: int) -> list[dict[str, Any]]:
    """Top items as plain dicts for sensors and services."""
    return [
        {"name": e.name, "count": e.count, "icon": icon_for(e.name)}
        for e in top_items(entries, limit)
    ]


def quick_add_payload(
    entries: Mapping[str, UsageEntry],
    limit: int,
    minimum: int = MIN_QUICK_ITEMS,
) -> list[dict[str, Any]]:
    """Buttons for quick-add: the most added items, topped up with staples.

    Real items always come first. Staples (count 0) only fill the remaining places up
    to `minimum` buttons (never more than `limit`) and never repeat a real item.
    """
    items = top_payload(entries, limit)
    shown = {normalize_name(item["name"]) for item in items}
    for name in DEFAULT_QUICK_ITEMS:
        if len(items) >= min(minimum, limit):
            break
        if normalize_name(name) not in shown:
            shown.add(normalize_name(name))
            items.append({"name": name, "count": 0, "icon": icon_for(name)})
    return items


def entries_to_json(entries: Mapping[str, UsageEntry]) -> dict[str, dict[str, Any]]:
    """Serialise for storage."""
    return {
        key: {"name": e.name, "count": e.count, "last_used": e.last_used}
        for key, e in entries.items()
    }


def entries_from_json(data: Any) -> dict[str, UsageEntry]:
    """Read stored data; anything malformed is skipped instead of failing."""
    if not isinstance(data, Mapping):
        return {}
    result: dict[str, UsageEntry] = {}
    for key, raw in data.items():
        if not isinstance(key, str) or not isinstance(raw, Mapping):
            continue
        name, count, last_used = raw.get("name"), raw.get("count"), raw.get("last_used")
        if (
            isinstance(name, str)
            and name.strip()
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count > 0
            and isinstance(last_used, str)
        ):
            result[key] = UsageEntry(name, count, last_used)
    return result
