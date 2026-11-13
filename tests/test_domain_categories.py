"""Tests for the pure category logic: parsing ha-ica-todo's answers and the order."""

from typing import Any

import pytest

from custom_components.handla.domain import (
    ArticleGroup,
    CategorizedItem,
    groups_payload,
    items_payload,
    order_groups,
    parse_categorized_items,
    parse_group_id,
    parse_groups,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(10, 10), (10.0, 10), ("10", 10), (" 7 ", 7), (10.5, None), (True, None)]
    + [("x", None), (None, None), ([], None)],
)
def test_group_ids(raw: Any, expected: int | None) -> None:
    assert parse_group_id(raw) == expected


def test_groups_are_parsed_and_malformed_entries_skipped() -> None:
    raw = {
        "article_groups": [
            {"id": 10, "name": " Mejeri "},
            {"id": 10, "name": "Again"},  # repeated id: the first one wins
            {"id": "x", "name": "Bad id"},
            {"id": 4, "name": ""},
            {"id": 5},
            "not a dict",
            {"id": 12, "name": "Ospecificerad"},
        ]
    }
    assert parse_groups(raw) == [
        ArticleGroup(10, "Mejeri"),
        ArticleGroup(12, "Ospecificerad"),
    ]


@pytest.mark.parametrize("raw", [None, {}, {"article_groups": "x"}, [], "x"])
def test_groups_from_a_bad_answer_are_empty(raw: Any) -> None:
    assert parse_groups(raw) == []


def test_items_are_parsed_with_a_group_defaulting_to_unspecified() -> None:
    raw = {
        "items": [
            {"uid": "a", "product_name": "Mjölk", "article_group": {"id": 10}},
            {"uid": "b", "product_name": " Gurka ", "completed": True},
            {"uid": "c", "product_name": "Okänt", "article_group": {"id": "?"}},
            {"uid": "d", "product_name": "Bananer", "article_group": "oops"},
            {"uid": "", "product_name": "No uid"},
            {"uid": "e", "product_name": " "},
            {"uid": "f", "product_name": 3},
            "x",
        ]
    }
    assert parse_categorized_items(raw) == [
        CategorizedItem("a", "Mjölk", 10),
        CategorizedItem("b", "Gurka", 12, completed=True),
        CategorizedItem("c", "Okänt", 12),
        CategorizedItem("d", "Bananer", 12),
    ]


@pytest.mark.parametrize("raw", [None, {}, {"items": 3}, "x"])
def test_items_from_a_bad_answer_are_empty(raw: Any) -> None:
    assert parse_categorized_items(raw) == []


def test_groups_follow_the_walk_through_the_store() -> None:
    groups = [
        ArticleGroup(i, f"g{i}") for i in (12, 8, 99, 10, 4, 3, 98, 6, 5, 9, 7, 11)
    ]
    assert [g.id for g in order_groups(groups)] == [
        4, 3, 6, 10, 5, 9, 7, 11, 8, 98, 99, 12,
    ]  # fmt: skip


def test_payloads() -> None:
    assert groups_payload([ArticleGroup(12, "O"), ArticleGroup(4, "F")]) == [
        {"id": 4, "name": "F"},
        {"id": 12, "name": "O"},
    ]
    items = [CategorizedItem("a", "x", 4), CategorizedItem("b", "y", 12, True)]
    assert items_payload(items) == {"a": 4, "b": 12}
