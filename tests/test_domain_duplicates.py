"""Tests for duplicate detection."""

from custom_components.handla.domain import find_duplicates, normalize_name


def test_normalize_name_ignores_case_and_whitespace() -> None:
    assert normalize_name("  Gula   LÖKAR ") == "gula lökar"


def test_finds_case_insensitive_duplicate() -> None:
    assert find_duplicates("mjölk", ["Mjölk", "Ägg"]) == ["Mjölk"]


def test_quantity_and_unit_are_ignored() -> None:
    assert find_duplicates("2 mjölk", ["1 l Mjölk"]) == ["1 l Mjölk"]
    assert find_duplicates("1 l mjölk", ["mjölk"]) == ["mjölk"]


def test_returns_every_match() -> None:
    existing = ["1 l mjölk", "ägg", "MJÖLK"]
    assert find_duplicates("Mjölk", existing) == ["1 l mjölk", "MJÖLK"]


def test_different_names_are_not_duplicates() -> None:
    assert find_duplicates("mjölk", ["havremjölk", "mjölkchoklad"]) == []


def test_no_match_on_empty_list() -> None:
    assert find_duplicates("mjölk", []) == []


def test_blank_candidate_never_matches() -> None:
    assert find_duplicates("  ", ["", "mjölk"]) == []


def test_accepts_any_iterable() -> None:
    assert find_duplicates("ägg", (t for t in ["Ägg"])) == ["Ägg"]
