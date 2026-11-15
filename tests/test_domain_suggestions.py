"""Tests for parsing ha-ica-todo's item suggestions (pure logic)."""

from typing import Any

import pytest

from custom_components.handla.domain import (
    ItemSuggestion,
    item_suggestions_payload,
    parse_suggestions,
)


def _entry(name: Any, group: Any = 10, **extra: Any) -> dict[str, Any]:
    return {"name": name, "article_group": {"id": group, "name": "x"}, **extra}


def test_parses_names_groups_sources_and_counts_in_order() -> None:
    raw = {
        "items": [
            _entry("Mjölk", 10, source="history", count=7),
            _entry("Toalettpapper", 9, source="article"),
        ]
    }
    assert parse_suggestions(raw) == [
        ItemSuggestion("Mjölk", 10, "history", 7),
        ItemSuggestion("Toalettpapper", 9, "article", 0),
    ]


@pytest.mark.parametrize("raw", [None, [], "x", {}, {"items": "x"}, {"items": None}])
def test_unusable_answers_give_no_suggestions(raw: Any) -> None:
    assert parse_suggestions(raw) == []


def test_entries_without_a_name_are_skipped() -> None:
    raw = {
        "items": [
            "text",
            None,
            {"source": "history"},
            _entry(""),
            _entry("   "),
            _entry(5),
            _entry("Ost"),
        ]
    }
    assert [s.name for s in parse_suggestions(raw)] == ["Ost"]


@pytest.mark.parametrize(
    "group", [None, "x", {"id": None}, {"id": "abc"}, {"id": True}, {}]
)
def test_missing_or_unknown_group_becomes_12(group: Any) -> None:
    raw = {"items": [{"name": "Ost", "article_group": group}]}
    assert parse_suggestions(raw)[0].group_id == 12


def test_group_without_article_group_key_becomes_12() -> None:
    assert parse_suggestions({"items": [{"name": "Ost"}]})[0].group_id == 12


@pytest.mark.parametrize("count", [None, "3", True, -2, 1.5])
def test_a_bad_count_becomes_zero(count: Any) -> None:
    assert parse_suggestions({"items": [_entry("Ost", count=count)]})[0].count == 0


def test_payload_is_plain_data() -> None:
    assert item_suggestions_payload([ItemSuggestion("Ost", 10, "history", 2)]) == [
        {"name": "Ost", "group_id": 10, "source": "history", "count": 2}
    ]
