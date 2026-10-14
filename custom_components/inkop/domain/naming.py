"""Default names for new shopping lists."""

from collections.abc import Iterable
from datetime import date

SWEDISH_MONTHS = (
    "januari",
    "februari",
    "mars",
    "april",
    "maj",
    "juni",
    "juli",
    "augusti",
    "september",
    "oktober",
    "november",
    "december",
)

_PREFIX = "Att handla"


def default_list_name(today: date, existing_titles: Iterable[str]) -> str:
    """Return "Att handla <dag> <månad>", numbered "(2)", "(3)" if taken.

    Existing titles are compared case-insensitively.
    """
    base = f"{_PREFIX} {today.day} {SWEDISH_MONTHS[today.month - 1]}"
    taken = {title.strip().casefold() for title in existing_titles}
    if base.casefold() not in taken:
        return base
    number = 2
    while f"{base} ({number})".casefold() in taken:
        number += 1
    return f"{base} ({number})"
