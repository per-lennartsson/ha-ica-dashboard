"""Usage statistics: how often each item name has been added.

Pure functions over plain data. Names are compared case-insensitively and without
quantity or unit, so "2 st Gurka" and "gurka" count as the same item.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
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
    pinned: bool = False


class UsageError(ValueError):
    """A manage operation that cannot be done. `key` is the translation key."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def record_use(
    entries: Mapping[str, UsageEntry],
    name: str,
    when: str,
    aliases: Mapping[str, str] | None = None,
) -> dict[str, UsageEntry]:
    """Return a copy of `entries` with one more use of `name`.

    A merged-away name (an alias) counts toward the item it was merged into and does
    not change that item's name. Otherwise the latest spelling of the name is kept. A
    blank name changes nothing. When more than MAX_TRACKED names are tracked, the least
    used (oldest first) are dropped; pinned items are dropped last.
    """
    key = normalize_name(name)
    updated = dict(entries)
    if not key:
        return updated
    target = (aliases or {}).get(key, key)
    previous = updated.get(target)
    keep_name = previous is not None and target != key
    updated[target] = UsageEntry(
        name=previous.name if keep_name and previous else " ".join(name.split()),
        count=(previous.count if previous else 0) + 1,
        last_used=when,
        pinned=previous.pinned if previous else False,
    )
    if len(updated) > MAX_TRACKED:
        keep = sorted(updated.items(), key=lambda kv: _rank(kv[1]), reverse=True)
        updated = dict(keep[:MAX_TRACKED])
    return updated


def _rank(entry: UsageEntry) -> tuple[bool, int, str, str]:
    return entry.pinned, entry.count, entry.last_used, entry.name.casefold()


def top_items(entries: Mapping[str, UsageEntry], limit: int) -> list[UsageEntry]:
    """The `limit` first items: pinned first, then highest count, then most recent."""
    if limit <= 0:
        return []
    ranked = sorted(entries.values(), key=lambda e: e.name.casefold())
    ranked.sort(key=lambda e: e.last_used, reverse=True)  # stable: ties keep the order
    ranked.sort(key=lambda e: e.count, reverse=True)
    ranked.sort(key=lambda e: e.pinned, reverse=True)
    return ranked[:limit]


def top_payload(entries: Mapping[str, UsageEntry], limit: int) -> list[dict[str, Any]]:
    """Top items as plain dicts for sensors and services."""
    return [
        {
            "name": e.name,
            "count": e.count,
            "icon": icon_for(e.name),
            "pinned": e.pinned,
        }
        for e in top_items(entries, limit)
    ]


def remove_entry(
    entries: Mapping[str, UsageEntry], aliases: Mapping[str, str], name: str
) -> tuple[dict[str, UsageEntry], dict[str, str]]:
    """Forget an item (and the names that were merged into it).

    Raises UsageError("quick_item_unknown") when the item is not tracked.
    """
    key = _resolve(entries, aliases, name)
    remaining = {k: v for k, v in entries.items() if k != key}
    kept = {a: t for a, t in aliases.items() if t != key and a != key}
    return remaining, kept


def merge_entries(
    entries: Mapping[str, UsageEntry],
    aliases: Mapping[str, str],
    sources: list[str],
    target: str,
) -> tuple[dict[str, UsageEntry], dict[str, str]]:
    """Merge `sources` into one item called `target`.

    Counts are summed (an existing item named `target` is included), the newest
    `last_used` wins and the item is pinned if any part was. The merged-away names
    become aliases, so adding them later keeps counting toward `target`.

    Raises UsageError: "quick_item_blank" (empty target or no sources) or
    "quick_item_unknown" (a source is not tracked).
    """
    name = " ".join(target.split())
    target_key = normalize_name(name)
    if not target_key or not sources:
        raise UsageError("quick_item_blank")
    source_keys = {_resolve(entries, aliases, source) for source in sources}
    parts = [entries[k] for k in source_keys]
    existing = entries.get(target_key)
    if existing is not None and target_key not in source_keys:
        parts.append(existing)
        source_keys.add(target_key)
    merged = UsageEntry(
        name=name,
        count=sum(part.count for part in parts),
        last_used=max(part.last_used for part in parts),
        pinned=any(part.pinned for part in parts),
    )
    result = {k: v for k, v in entries.items() if k not in source_keys}
    result[target_key] = merged
    new_aliases = {
        alias: target_key if dest in source_keys else dest
        for alias, dest in aliases.items()
    }
    for key in source_keys - {target_key}:
        new_aliases[key] = target_key
    new_aliases.pop(target_key, None)
    return result, new_aliases


def add_entry(
    entries: Mapping[str, UsageEntry],
    aliases: Mapping[str, str],
    name: str,
    when: str,
) -> tuple[dict[str, UsageEntry], dict[str, str]]:
    """Pin an item to the quick-add buttons, creating it (count 1) when new.

    A merged-away name pins the item it was merged into.

    Raises UsageError("quick_item_blank") for a blank name.
    """
    clean = " ".join(name.split())
    key = normalize_name(clean)
    if not key:
        raise UsageError("quick_item_blank")
    target = aliases.get(key, key)
    updated = dict(entries)
    current = updated.get(target)
    updated[target] = (
        replace(current, pinned=True)
        if current
        else UsageEntry(clean, 1, when, pinned=True)
    )
    return updated, dict(aliases)


def _resolve(
    entries: Mapping[str, UsageEntry], aliases: Mapping[str, str], name: str
) -> str:
    key = normalize_name(name)
    key = aliases.get(key, key)
    if key not in entries:
        raise UsageError("quick_item_unknown")
    return key


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
            items.append(
                {"name": name, "count": 0, "icon": icon_for(name), "pinned": False}
            )
    return items


def entries_to_json(entries: Mapping[str, UsageEntry]) -> dict[str, dict[str, Any]]:
    """Serialise for storage."""
    return {
        key: {"name": e.name, "count": e.count, "last_used": e.last_used}
        | ({"pinned": True} if e.pinned else {})
        for key, e in entries.items()
    }


def aliases_to_json(aliases: Mapping[str, str]) -> dict[str, str]:
    """Serialise merged-away names for storage."""
    return dict(aliases)


def aliases_from_json(data: Any) -> dict[str, str]:
    """Read stored aliases; anything malformed is skipped."""
    if not isinstance(data, Mapping):
        return {}
    return {
        a: t
        for a, t in data.items()
        if isinstance(a, str) and isinstance(t, str) and a and t and a != t
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
            result[key] = UsageEntry(name, count, last_used, raw.get("pinned") is True)
    return result
