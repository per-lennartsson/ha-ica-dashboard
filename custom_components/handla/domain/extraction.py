"""Turning pasted text into shopping list suggestions with AI (pure logic).

The prompt and the output structure live here, in version control. The structure
asks for one list of plain texts ("<quantity> <unit> <name>") because that is what
ha-ica-todo parses; the model's answer is cleaned and merged again here, since a
model may ignore any part of the instructions.
"""

import re
from collections.abc import Iterable
from typing import Any

from .duplicates import normalize_name
from .items import ParsedItem, parse_item_text
from .todo_items import TodoItem, duplicate_items

# Longest pasted text accepted; keeps cost and the answer's size in check
MAX_TEXT_LENGTH = 20000
# Longest list read from an answer; anything beyond is ignored
MAX_SUGGESTIONS = 100
MAX_NAME_LENGTH = 60

TASK_NAME = "Handla: extract shopping items"
ITEMS_KEY = "items"

# Always at home: never suggested, even if the model includes them
STAPLES = frozenset(
    {"salt", "peppar", "svartpeppar", "svart peppar", "vatten", "kranvatten"}
)

# Structure for ai_task.generate_data: one field holding a list of texts
STRUCTURE: dict[str, Any] = {
    ITEMS_KEY: {
        "description": "The shopping items, one text per item.",
        "required": True,
        "selector": {"text": {"multiple": True}},
    }
}

INSTRUCTIONS = """\
Du hjälper till att göra en inköpslista på svenska.
Läs texten nedan (ett recept, en matsedel, ett meddelande eller något liknande) och \
lista allt som behöver köpas.

Regler:
- Ett föremål per rad i listan, utan punkter, numrering eller förklaringar.
- Skriv mängden först, sedan enhet (om det behövs), sedan namnet: "2 st gurka", \
"500 g nötfärs", "1 l mjölk". Ingen mängd om den är okänd eller självklar.
- Tillåtna enheter: st, förp, kg, hg, g, l, dl, cl, ml, msk, tsk, krm.
- Korta namn i grundform och med liten bokstav, utan beskrivningar ("lök", inte \
"hackad gul lök till sås").
- Slå ihop samma vara som förekommer flera gånger till en rad med summerad mängd.
- Hoppa över det som alltid finns hemma: salt, peppar och vatten.
- Hoppa över sådant i texten som inte är något att köpa.
- Hitta inte på varor som inte nämns eller följer av texten.
- Är texten inte på svenska, översätt varornas namn till svenska.

Texten:
\"\"\"
{text}
\"\"\"
"""

_BULLET_RE = re.compile(r"^\s*(?:[-*•–·]|\d+[.)])\s+")
_SPACES_RE = re.compile(r"\s+")


def build_instructions(text: str) -> str:
    """The prompt for one pasted text."""
    return INSTRUCTIONS.replace("{text}", text.strip())


def _clean_line(line: str) -> str:
    return _SPACES_RE.sub(" ", _BULLET_RE.sub("", line)).strip()


def _raw_lines(raw: Any) -> list[str]:
    """The answer as lines: a list of texts, or one text with a line per item."""
    if isinstance(raw, str):
        return raw.splitlines()
    if isinstance(raw, list | tuple):
        return [
            line
            for entry in raw
            if isinstance(entry, str)
            for line in entry.splitlines()
        ]
    return []


def _merge(first: ParsedItem, other: ParsedItem) -> ParsedItem:
    """Two entries for one item: add the quantities if they are comparable."""
    if (
        first.quantity is not None
        and other.quantity is not None
        and first.unit == other.unit
    ):
        return ParsedItem(first.name, first.quantity + other.quantity, first.unit)
    return first


def clean_suggestions(raw: Any) -> list[ParsedItem]:
    """Items from a model's answer: tidy, no staples, same names merged, in order.

    Anything that is not text is ignored, so a malformed answer gives an empty list
    rather than an error here (the caller decides what an empty answer means).
    """
    merged: dict[str, ParsedItem] = {}
    for line in _raw_lines(raw)[: MAX_SUGGESTIONS * 2]:
        parsed = parse_item_text(_clean_line(line))
        key = normalize_name(parsed.name)
        if not key or len(parsed.name) > MAX_NAME_LENGTH or key in STAPLES:
            continue
        merged[key] = _merge(merged[key], parsed) if key in merged else parsed
    return list(merged.values())[:MAX_SUGGESTIONS]


def suggestions_payload(
    suggestions: Iterable[ParsedItem], on_list: Iterable[TodoItem]
) -> list[dict[str, Any]]:
    """Suggestions for the review step; items already on the list start unticked."""
    open_items = list(on_list)
    payload: list[dict[str, Any]] = []
    for suggestion in suggestions:
        existing = duplicate_items(suggestion.summary, open_items)
        payload.append(
            {
                "item": suggestion.summary,
                "name": suggestion.name,
                "quantity": suggestion.quantity,
                "unit": suggestion.unit,
                "on_list": bool(existing),
                "existing": existing[0].summary if existing else None,
                "selected": not existing,
            }
        )
    return payload
