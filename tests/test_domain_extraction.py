"""Tests for the pure AI extraction logic: prompt, cleaning, marking."""

import pytest

from custom_components.handla.domain import (
    MAX_TEXT_LENGTH,
    TodoItem,
    build_instructions,
    clean_suggestions,
    suggestions_payload,
)
from custom_components.handla.domain.extraction import STRUCTURE


def _summaries(raw: object) -> list[str]:
    return [item.summary for item in clean_suggestions(raw)]


def test_prompt_contains_the_text_and_the_rules() -> None:
    prompt = build_instructions("  Pasta med tomatsås  ")
    assert "Pasta med tomatsås" in prompt
    assert "{text}" not in prompt
    for rule in ("salt, peppar och vatten", "st, förp, kg", "Slå ihop"):
        assert rule in prompt


def test_text_with_braces_is_kept_as_is() -> None:
    assert "{x} {text}" in build_instructions("{x} {text}")


def test_structure_asks_for_one_list_of_texts() -> None:
    assert STRUCTURE["items"]["selector"] == {"text": {"multiple": True}}
    assert STRUCTURE["items"]["required"] is True


def test_cleans_bullets_numbers_and_spaces() -> None:
    raw = ["- 2 st  gurka", "1. 500 g nötfärs", "• mjölk", "  ", ""]
    assert _summaries(raw) == ["2 st gurka", "500 g nötfärs", "mjölk"]


def test_a_text_answer_is_read_line_by_line() -> None:
    assert _summaries("2 st gurka\n\n- mjölk\n") == ["2 st gurka", "mjölk"]


def test_staples_are_skipped_in_any_case() -> None:
    assert _summaries(["Salt", "1 tsk peppar", "vatten", "svart peppar", "ost"]) == [
        "ost"
    ]


def test_same_names_are_merged_and_quantities_added() -> None:
    raw = ["1 st lök", "2 st Lök", "lök"]
    assert _summaries(raw) == ["3 st lök"]


def test_different_units_keep_the_first() -> None:
    assert _summaries(["1 l mjölk", "2 dl mjölk"]) == ["1 l mjölk"]


def test_order_is_kept() -> None:
    assert _summaries(["b", "a", "c", "a"]) == ["b", "a", "c"]


def test_names_too_long_are_dropped() -> None:
    assert _summaries(["x" * 61, "ost"]) == ["ost"]


@pytest.mark.parametrize("raw", [None, 5, {"a": 1}, [1, None, {"a": 1}], ""])
def test_malformed_answers_give_nothing(raw: object) -> None:
    assert clean_suggestions(raw) == []


def test_only_the_first_hundred_are_used() -> None:
    raw = [f"vara {n}" for n in range(300)]
    assert len(clean_suggestions(raw)) == 100


def test_items_on_the_list_are_marked_and_unticked() -> None:
    on_list = [
        TodoItem("u1", "1 l Mjölk"),
        TodoItem("u2", "ost", completed=True),
    ]
    payload = suggestions_payload(
        clean_suggestions(["2 l mjölk", "ost", "ägg"]), on_list
    )

    assert [p["item"] for p in payload] == ["2 l mjölk", "ost", "ägg"]
    assert [p["on_list"] for p in payload] == [True, False, False]  # ticked: not on it
    assert [p["selected"] for p in payload] == [False, True, True]
    assert payload[0]["existing"] == "1 l Mjölk"
    assert payload[1]["existing"] is None
    assert payload[0]["quantity"] == 2
    assert payload[0]["unit"] == "l"


def test_limits_are_sane() -> None:
    assert MAX_TEXT_LENGTH >= 5000
