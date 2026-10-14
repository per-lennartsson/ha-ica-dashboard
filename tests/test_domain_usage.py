"""Tests for usage statistics and icons."""

import pytest

from custom_components.inkop.domain import (
    DEFAULT_ICON,
    MAX_TRACKED,
    UsageEntry,
    entries_from_json,
    entries_to_json,
    icon_for,
    record_use,
    top_items,
    top_payload,
)


def test_first_use_creates_an_entry() -> None:
    result = record_use({}, "Mjölk", "2026-10-14T10:00:00")
    assert result == {"mjölk": UsageEntry("Mjölk", 1, "2026-10-14T10:00:00")}


def test_repeated_use_counts_case_insensitively_and_keeps_latest_spelling() -> None:
    entries = record_use({}, "Mjölk", "2026-10-14T10:00:00")
    entries = record_use(entries, "  mjölk ", "2026-10-15T10:00:00")
    entries = record_use(entries, "MJÖLK", "2026-10-16T10:00:00")
    assert entries == {"mjölk": UsageEntry("MJÖLK", 3, "2026-10-16T10:00:00")}


def test_inner_whitespace_is_collapsed() -> None:
    assert record_use({}, "gula   lökar", "t")["gula lökar"].name == "gula lökar"


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_names_are_ignored(name: str) -> None:
    assert record_use({}, name, "t") == {}


def test_record_use_does_not_modify_its_input() -> None:
    original: dict[str, UsageEntry] = {}
    record_use(original, "mjölk", "t")
    assert original == {}


def test_least_used_entries_are_dropped_over_the_limit() -> None:
    entries: dict[str, UsageEntry] = {}
    for number in range(MAX_TRACKED):
        entries = record_use(entries, f"vara {number:03}", f"2026-01-01T00:{number:04}")
    entries = record_use(entries, "mjölk", "2026-12-01T00:00:00")  # 1 use, newest
    entries = record_use(entries, "vara 007", "2026-12-02T00:00:00")  # now 2 uses
    assert len(entries) == MAX_TRACKED
    assert "vara 007" in entries
    assert "mjölk" in entries  # newest among the 1-use entries
    assert "vara 000" not in entries  # oldest of the 1-use entries


def test_top_items_by_count_then_recency_then_name() -> None:
    entries = {
        "a": UsageEntry("a", 3, "2026-01-01"),
        "b": UsageEntry("b", 5, "2026-01-01"),
        "c": UsageEntry("c", 3, "2026-02-01"),  # same count as a, more recent
        "d": UsageEntry("Å", 1, "2026-03-01"),
        "e": UsageEntry("B", 1, "2026-03-01"),  # same count and time as d: by name
    }
    assert [e.name for e in top_items(entries, 10)] == ["b", "c", "a", "B", "Å"]


def test_top_items_limit() -> None:
    entries = record_use(record_use({}, "a", "1"), "b", "2")
    assert len(top_items(entries, 1)) == 1
    assert top_items(entries, 0) == []
    assert top_items(entries, -3) == []
    assert top_items({}, 5) == []


def test_top_payload_has_name_count_and_icon() -> None:
    entries = record_use({}, "Mjölk", "t")
    assert top_payload(entries, 5) == [{"name": "Mjölk", "count": 1, "icon": "mdi:cow"}]


def test_json_round_trip() -> None:
    entries = record_use(record_use({}, "Mjölk", "t1"), "ägg", "t2")
    assert entries_from_json(entries_to_json(entries)) == entries


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "x",
        {"a": "x"},
        {"a": {"name": "", "count": 1, "last_used": "t"}},
        {"a": {"name": "x", "count": 0, "last_used": "t"}},
        {"a": {"name": "x", "count": True, "last_used": "t"}},
        {"a": {"name": "x", "count": "2", "last_used": "t"}},
        {"a": {"name": "x", "count": 1}},
        {1: {"name": "x", "count": 1, "last_used": "t"}},
    ],
)
def test_malformed_stored_data_is_skipped(data: object) -> None:
    assert entries_from_json(data) == {}


def test_valid_entries_survive_next_to_broken_ones() -> None:
    data = {
        "ok": {"name": "ok", "count": 2, "last_used": "t"},
        "bad": {"name": "x"},
    }
    assert entries_from_json(data) == {"ok": UsageEntry("ok", 2, "t")}


@pytest.mark.parametrize(
    ("name", "icon"),
    [
        ("Mjölk", "mdi:cow"),
        ("havremjölk", "mdi:cow"),  # compound words match on their parts
        ("ägg", "mdi:egg"),
        ("Ost", "mdi:cheese"),
        ("Hushållspapper", "mdi:paper-roll"),
        ("nötfärs", "mdi:food-steak"),
        ("Lax", "mdi:fish"),
        ("kaffe", "mdi:coffee"),
        ("spaghetti", "mdi:pasta"),
        ("Äpplen", "mdi:food-apple"),
    ],
)
def test_icons_for_common_groceries(name: str, icon: str) -> None:
    assert icon_for(name) == icon


def test_unknown_items_get_the_default_icon() -> None:
    assert icon_for("xyzzy") == DEFAULT_ICON
    assert icon_for("") == DEFAULT_ICON
