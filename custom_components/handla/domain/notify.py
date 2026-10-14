"""Pure logic for "someone added items" notifications."""

from collections.abc import Iterable, Mapping

from .duplicates import normalize_name

MAX_LISTED = 5


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


def _swedish(language: str) -> bool:
    return language.casefold().startswith("sv")


def build_message(
    language: str, adder_name: str | None, list_title: str, items: list[str]
) -> tuple[str, str]:
    """Title and text of the notification, in Swedish or English."""
    swedish = _swedish(language)
    listed = ", ".join(items[:MAX_LISTED])
    extra = len(items) - MAX_LISTED
    if extra > 0:
        listed += f" +{extra} till" if swedish else f" +{extra} more"
    if swedish:
        if adder_name:
            return "Handla", f"{adder_name} lade till {listed} i {list_title}"
        return "Handla", f"Nytt på {list_title}: {listed}"
    if adder_name:
        return "Handla", f"{adder_name} added {listed} to {list_title}"
    return "Handla", f"New on {list_title}: {listed}"


def choose_notify_services(names: Iterable[str]) -> list[str]:
    """Notify services worth offering: the companion apps' if there are any.

    Falls back to every notify service except the generic `send_message`.
    """
    candidates = sorted(name for name in names if name != "send_message")
    phones = [name for name in candidates if name.startswith("mobile_app_")]
    return phones or candidates
