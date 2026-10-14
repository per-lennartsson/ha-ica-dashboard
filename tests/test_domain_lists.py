"""Tests for pure list logic."""

import pytest

from custom_components.handla.domain import (
    ListInfo,
    entity_for,
    event_mentions,
    lists_payload,
    pick_active,
    same_id,
    title_from_name,
    unique_labels,
)


def _list(title: str, offline_id: str) -> ListInfo:
    return ListInfo(f"todo.{offline_id.lower()}", offline_id, title)


@pytest.mark.parametrize(
    ("a", "b", "result"),
    [
        ("ABC", "abc", True),
        ("ABC", "ABD", False),
        (None, "a", False),
        ("a", None, False),
    ],
)
def test_same_id(a: str | None, b: str | None, result: bool) -> None:
    assert same_id(a, b) is result


@pytest.mark.parametrize(
    ("name", "title"),
    [
        ("ICA Att handla fredag", "Att handla fredag"),
        ("Att handla fredag", "Att handla fredag"),
        ("ICA  Mjölk ", "Mjölk"),
        ("ICAmjölk", "ICAmjölk"),  # only the "ICA " prefix is removed
        (None, "todo.x"),
        ("", "todo.x"),
        ("ICA ", "todo.x"),
    ],
)
def test_title_from_name(name: str | None, title: str) -> None:
    assert title_from_name(name, "todo.x") == title


def test_unique_labels() -> None:
    assert unique_labels(["A", "B", "a", "A"]) == ["A", "B", "a (2)", "A (3)"]
    assert unique_labels([]) == []


def test_pick_active_prefers_preferred_then_current_then_first() -> None:
    lists = [_list("Bröd", "B-1"), _list("ägg", "A-2"), _list("Mjölk", "M-3")]
    assert pick_active(lists, "m-3", "B-1") == "M-3"  # case-insensitive
    assert pick_active(lists, "gone", "B-1") == "B-1"
    assert pick_active(lists, None, None) == "B-1"  # first by title, "Bröd" < "ägg"
    assert pick_active(lists, "gone", "also-gone") == "B-1"


def test_pick_active_without_lists() -> None:
    assert pick_active([], "x", "y") is None


def test_event_mentions_and_entity_for() -> None:
    event = {"created": ["ABC-1"], "deleted": [], "entities": {"ABC-1": "todo.x"}}
    assert event_mentions(event, "created", "abc-1")
    assert not event_mentions(event, "deleted", "abc-1")
    assert not event_mentions({}, "created", "abc-1")
    assert entity_for(event, "abc-1") == "todo.x"
    assert entity_for(event, "other") is None
    assert entity_for({}, "abc-1") is None


def test_lists_payload() -> None:
    lists = [
        ListInfo("todo.a", "A-1", "Bröd", 2, "kommentar"),
        ListInfo("todo.b", "B-2", "Mjölk"),
    ]
    assert lists_payload(lists) == [
        {"entity_id": "todo.a", "offline_id": "A-1", "title": "Bröd", "item_count": 2},
        {
            "entity_id": "todo.b",
            "offline_id": "B-2",
            "title": "Mjölk",
            "item_count": None,
        },
    ]
    assert lists_payload([]) == []
