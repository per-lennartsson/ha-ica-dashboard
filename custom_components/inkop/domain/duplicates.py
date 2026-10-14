"""Case-insensitive duplicate detection for shopping list items."""

from collections.abc import Iterable

from .items import parse_item_text


def normalize_name(name: str) -> str:
    """Lower-case and collapse whitespace so names compare case-insensitively."""
    return " ".join(name.casefold().split())


def find_duplicates(candidate: str, existing: Iterable[str]) -> list[str]:
    """Return the existing item texts that have the same name as `candidate`.

    Quantity and unit are ignored: "2 mjölk" duplicates "1 l Mjölk".
    """
    wanted = normalize_name(parse_item_text(candidate).name)
    if not wanted:
        return []
    return [
        text
        for text in existing
        if normalize_name(parse_item_text(text).name) == wanted
    ]
