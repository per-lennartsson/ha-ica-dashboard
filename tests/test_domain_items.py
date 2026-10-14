"""Tests for item text parsing and formatting."""

import pytest

from custom_components.handla.domain import (
    UNITS,
    ParsedItem,
    format_quantity,
    parse_item_text,
)


@pytest.mark.parametrize(
    ("text", "name", "quantity", "unit"),
    [
        ("2 gula lökar", "gula lökar", 2.0, None),
        ("500 g nötfärs", "nötfärs", 500.0, "g"),
        ("500g nötfärs", "nötfärs", 500.0, "g"),
        ("1,5 l mjölk", "mjölk", 1.5, "l"),
        ("1.5 kg lax", "lax", 1.5, "kg"),
        ("3 förp pasta", "pasta", 3.0, "förp"),
        ("2 KG Potatis", "Potatis", 2.0, "kg"),
        ("  3   st   ägg  ", "ägg", 3.0, "st"),
        ("007 mjölk", "mjölk", 7.0, None),
    ],
)
def test_parse_quantity_unit_name(
    text: str, name: str, quantity: float, unit: str | None
) -> None:
    assert parse_item_text(text) == ParsedItem(name, quantity, unit)


@pytest.mark.parametrize("unit", UNITS)
def test_every_supported_unit_is_recognised(unit: str) -> None:
    assert parse_item_text(f"2 {unit} något") == ParsedItem("något", 2.0, unit)


@pytest.mark.parametrize(
    "text",
    ["2–3 st banan", "2-3 st banan", "2 - 3 st banan", "2 – 3 st banan"],
)
def test_range_keeps_the_higher_number(text: str) -> None:
    assert parse_item_text(text) == ParsedItem("banan", 3.0, "st")


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("1 gurka", "gurka"),  # "g" is not a unit inside a word
        ("1gurka", "gurka"),
        ("2 stora äpplen", "stora äpplen"),  # "st" is not a unit inside a word
        ("4 lök", "lök"),  # "l" is not a unit inside a word
        ("2 dlx saft", "dlx saft"),
    ],
)
def test_units_only_count_as_whole_words(text: str, name: str) -> None:
    assert parse_item_text(text).unit is None
    assert parse_item_text(text).name == name


@pytest.mark.parametrize(
    "text",
    ["mjölk", "Mjölk 2 l", "0 mjölk", "0,0 kg ris", "12", "1,5", "2", "-2 mjölk"],
)
def test_text_without_usable_leading_number_is_kept_as_name(text: str) -> None:
    assert parse_item_text(text) == ParsedItem(text.strip())


def test_unit_without_name_is_the_name() -> None:
    assert parse_item_text("2 st") == ParsedItem("st", 2.0)


def test_empty_text() -> None:
    assert parse_item_text("   ") == ParsedItem("")


@pytest.mark.parametrize(
    ("quantity", "text"),
    [(2.0, "2"), (1.5, "1,5"), (0.25, "0,25"), (500.0, "500"), (1234567.0, "1234567")],
)
def test_format_quantity_uses_decimal_comma(quantity: float, text: str) -> None:
    assert format_quantity(quantity) == text


@pytest.mark.parametrize(
    ("item", "summary"),
    [
        (ParsedItem("Gurka", 2.0, "st"), "2 st Gurka"),
        (ParsedItem("mjölk", 1.5, "l"), "1,5 l mjölk"),
        (ParsedItem("gula lökar", 2.0), "2 gula lökar"),
        (ParsedItem("mjölk"), "mjölk"),
        (ParsedItem("mjölk", None, "l"), "mjölk"),  # a unit needs a quantity
    ],
)
def test_summary(item: ParsedItem, summary: str) -> None:
    assert item.summary == summary


@pytest.mark.parametrize(
    "text", ["2 st Gurka", "1,5 l mjölk", "gula lökar", "2 gula lökar", "500 g ost"]
)
def test_summary_round_trips(text: str) -> None:
    assert parse_item_text(parse_item_text(text).summary) == parse_item_text(text)
