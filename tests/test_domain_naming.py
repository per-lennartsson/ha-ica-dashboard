"""Tests for default list names."""

from datetime import date

import pytest

from custom_components.inkop.domain import SWEDISH_MONTHS, default_list_name


def test_all_twelve_months() -> None:
    assert len(SWEDISH_MONTHS) == 12
    for month, name in enumerate(SWEDISH_MONTHS, start=1):
        assert default_list_name(date(2026, month, 5), []) == f"Att handla 5 {name}"


def test_plain_name_when_free() -> None:
    assert default_list_name(date(2026, 10, 14), ["Annan lista"]) == (
        "Att handla 14 oktober"
    )


def test_second_list_gets_number_two() -> None:
    assert default_list_name(date(2026, 10, 14), ["Att handla 14 oktober"]) == (
        "Att handla 14 oktober (2)"
    )


def test_third_list_gets_number_three() -> None:
    taken = ["Att handla 14 oktober", "Att handla 14 oktober (2)"]
    assert default_list_name(date(2026, 10, 14), taken) == "Att handla 14 oktober (3)"


def test_collision_check_ignores_case_and_surrounding_space() -> None:
    taken = [" att handla 14 OKTOBER ", "ATT HANDLA 14 oktober (2)"]
    assert default_list_name(date(2026, 10, 14), taken) == "Att handla 14 oktober (3)"


def test_gap_is_filled_with_lowest_free_number() -> None:
    taken = ["Att handla 14 oktober", "Att handla 14 oktober (3)"]
    assert default_list_name(date(2026, 10, 14), taken) == "Att handla 14 oktober (2)"


def test_other_dates_do_not_collide() -> None:
    assert default_list_name(date(2026, 10, 14), ["Att handla 13 oktober"]) == (
        "Att handla 14 oktober"
    )


@pytest.mark.parametrize("day", [1, 9, 31])
def test_day_is_not_zero_padded(day: int) -> None:
    assert default_list_name(date(2026, 12, day), []) == f"Att handla {day} december"
