"""Parsing and formatting of shopping list item text, e.g. "2 st Gurka".

Mirrors how ha-ica-todo parses and displays items (see docs/ica-contract.md), so
text typed in Handla round-trips through the ICA integration unchanged.
"""

import re
from dataclasses import dataclass

UNITS = ("st", "förp", "kg", "hg", "g", "l", "dl", "cl", "ml", "msk", "tsk", "krm")

_NUMBER = r"\d+(?:[.,]\d+)?"
# Unlike ha-ica-todo, the quantity may not be split mid-number ("12" is not 1 + "2").
_ITEM_RE = re.compile(
    rf"^(?:(?P<min_quantity>{_NUMBER})\s*[-–]\s*)?"
    rf"(?P<quantity>{_NUMBER})(?!\d|[.,]\d)\s*"
    rf"(?:(?P<unit>{'|'.join(UNITS)})(?=\s|$))?\s*"
    r"(?P<name>.*\S)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedItem:
    """An item split into optional quantity, optional unit and a name."""

    name: str
    quantity: float | None = None
    unit: str | None = None

    @property
    def summary(self) -> str:
        """The text as shown in Home Assistant: "<quantity> <unit> <name>"."""
        parts: list[str] = []
        if self.quantity is not None:
            parts.append(format_quantity(self.quantity))
            if self.unit:
                parts.append(self.unit)
        parts.append(self.name)
        return " ".join(parts)


def format_quantity(quantity: float) -> str:
    """Format a quantity the Swedish way: 2 -> "2", 1.5 -> "1,5"."""
    text = f"{quantity:.4f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def parse_item_text(text: str) -> ParsedItem:
    """Split free text into quantity, unit and name.

    - A unit only counts as a whole word ("1 gurka" is not "1 g" + "urka").
    - Comma or dot decimals are accepted; a range like "2–3" keeps the higher number.
    - Text without a leading positive number is kept as the name.
    """
    text = text.strip()
    match = _ITEM_RE.match(text)
    if match:
        quantity = float(match["quantity"].replace(",", "."))
        if quantity > 0:
            unit = match["unit"].lower() if match["unit"] else None
            return ParsedItem(name=match["name"], quantity=quantity, unit=unit)
    return ParsedItem(name=text)
