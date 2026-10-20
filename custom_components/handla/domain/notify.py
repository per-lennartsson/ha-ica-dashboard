"""Pure logic for "someone added items" notifications."""

from collections.abc import Iterable, Mapping
from typing import Any

from .duplicates import normalize_name

MAX_LISTED = 5
NOTIFY_TITLE = "Handla"

# Translation keys (under `exceptions` in strings.json) of the message templates
NOTIFY_ADDED_BY = "notify_added_by"
NOTIFY_ADDED = "notify_added"
NOTIFY_MORE = "notify_more"
NOTIFY_KEYS = (NOTIFY_ADDED_BY, NOTIFY_ADDED, NOTIFY_MORE)


def recipients_to_notify(
    recipients: Mapping[str, str], adder_user_id: str | None
) -> dict[str, str]:
    """Everyone configured except the person who made the change.

    With no known adder (an automation, for example) everyone is notified.
    """
    return {
        user_id: service
        for user_id, service in recipients.items()
        if user_id != adder_user_id
    }


def merge_items(existing: Iterable[str], new: Iterable[str]) -> list[str]:
    """Append new item texts, skipping ones already listed (case-insensitive)."""
    merged = list(existing)
    seen = {normalize_name(text) for text in merged}
    for text in new:
        key = normalize_name(text)
        if key and key not in seen:
            seen.add(key)
            merged.append(" ".join(text.split()))
    return merged


def build_message(
    templates: Mapping[str, str],
    adder_name: str | None,
    list_title: str,
    items: list[str],
) -> tuple[str, str]:
    """Title and text of the notification, from translated `templates`.

    Templates use {name}, {items}, {list} and {count}; see NOTIFY_KEYS.
    """
    listed = ", ".join(items[:MAX_LISTED])
    extra = len(items) - MAX_LISTED
    if extra > 0:
        listed += " " + templates[NOTIFY_MORE].format(count=extra)
    key = NOTIFY_ADDED_BY if adder_name else NOTIFY_ADDED
    text = templates[key].format(name=adder_name, items=listed, list=list_title)
    return NOTIFY_TITLE, text


def choose_notify_services(names: Iterable[str]) -> list[str]:
    """Notify services worth offering: the companion apps' if there are any.

    Falls back to every notify service except the generic `send_message`.
    """
    candidates = sorted(name for name in names if name != "send_message")
    phones = [name for name in candidates if name.startswith("mobile_app_")]
    return phones or candidates


def event_data(
    list_entity_id: str,
    list_title: str,
    item: str,
    user_id: str | None,
    user_name: str | None,
) -> dict[str, Any]:
    """Payload of the `handla_item_added` event."""
    return {
        "entity_id": list_entity_id,
        "list_title": list_title,
        "item": item,
        "user_id": user_id,
        "user_name": user_name,
    }
