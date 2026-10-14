"""Tests for duplicate detection and item lookup on a list."""

from custom_components.inkop.domain import TodoItem, duplicate_items, resolve_items


def _items(*specs: tuple[str, str, bool]) -> list[TodoItem]:
    return [TodoItem(uid, summary, done) for uid, summary, done in specs]


def test_duplicate_is_found_case_insensitively() -> None:
    items = _items(("1", "Mjölk", False), ("2", "ägg", False))
    assert duplicate_items("mjölk", items) == [items[0]]


def test_duplicate_ignores_quantity_and_unit() -> None:
    items = _items(("1", "1 l mjölk", False))
    assert duplicate_items("2 st Mjölk", items) == items


def test_ticked_items_are_not_duplicates() -> None:
    items = _items(("1", "mjölk", True), ("2", "ägg", False))
    assert duplicate_items("mjölk", items) == []


def test_every_open_duplicate_is_returned() -> None:
    items = _items(("1", "mjölk", False), ("2", "1 l MJÖLK", False))
    assert duplicate_items("mjölk", items) == items


def test_blank_candidate_has_no_duplicates() -> None:
    assert duplicate_items("  ", _items(("1", "", False))) == []


def test_no_duplicate_for_similar_names() -> None:
    assert duplicate_items("mjölk", _items(("1", "havremjölk", False))) == []


def test_resolve_by_uid_wins_over_text() -> None:
    items = _items(("abc", "mjölk", False), ("mjölk", "ägg", False))
    assert resolve_items("abc", items) == [items[0]]
    assert resolve_items("mjölk", items) == [items[1]]  # "mjölk" is a uid here too


def test_resolve_by_uid_ignores_state_preference() -> None:
    items = _items(("u1", "mjölk", True))
    assert resolve_items("u1", items, completed=False) == items


def test_resolve_by_exact_text_before_name() -> None:
    items = _items(("1", "1 l mjölk", False), ("2", "mjölk", False))
    assert resolve_items("Mjölk", items) == [items[1]]


def test_resolve_by_name_when_no_exact_text() -> None:
    items = _items(("1", "1 l mjölk", False))
    assert resolve_items("mjölk", items) == items
    assert resolve_items("2 st mjölk", items) == items


def test_resolve_finds_nothing() -> None:
    assert resolve_items("smör", _items(("1", "mjölk", False))) == []
    assert resolve_items("smör", []) == []


def test_resolve_prefers_requested_state() -> None:
    items = _items(("1", "mjölk", True), ("2", "1 l mjölk", False))
    # Ticking "mjölk": the open "1 l mjölk" beats the already ticked exact match
    assert resolve_items("mjölk", items, completed=False) == [items[1]]
    # Unticking "mjölk": the ticked one
    assert resolve_items("mjölk", items, completed=True) == [items[0]]


def test_resolve_falls_back_when_no_item_has_the_preferred_state() -> None:
    items = _items(("1", "mjölk", True))
    assert resolve_items("mjölk", items, completed=False) == items
