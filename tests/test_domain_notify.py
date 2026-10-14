"""Tests for notification logic that needs no Home Assistant."""

import pytest

from custom_components.inkop.domain import (
    MAX_LISTED,
    build_message,
    choose_notify_services,
    merge_items,
    recipients_to_notify,
)

RECIPIENTS = {"u-per": "mobile_app_per", "u-embla": "mobile_app_embla"}


def test_the_adder_is_never_notified() -> None:
    assert recipients_to_notify(RECIPIENTS, "u-per") == {"u-embla": "mobile_app_embla"}


def test_everyone_is_notified_when_the_adder_is_unknown() -> None:
    assert recipients_to_notify(RECIPIENTS, None) == RECIPIENTS


def test_an_adder_who_is_not_a_recipient_notifies_everyone() -> None:
    assert recipients_to_notify(RECIPIENTS, "u-guest") == RECIPIENTS


def test_nobody_configured() -> None:
    assert recipients_to_notify({}, "u-per") == {}


def test_merge_keeps_order_and_skips_repeats() -> None:
    assert merge_items(["mjölk"], ["ägg", "MJÖLK", " ägg "]) == ["mjölk", "ägg"]


def test_merge_skips_blank_text() -> None:
    assert merge_items([], ["", "  ", "ost"]) == ["ost"]


def test_merge_does_not_change_its_input() -> None:
    existing = ["mjölk"]
    merge_items(existing, ["ägg"])
    assert existing == ["mjölk"]


@pytest.mark.parametrize(
    ("language", "name", "expected"),
    [
        ("sv", "Embla", "Embla lade till mjölk, ägg i Veckan"),
        ("sv-SE", "Embla", "Embla lade till mjölk, ägg i Veckan"),
        ("sv", None, "Nytt på Veckan: mjölk, ägg"),
        ("en", "Embla", "Embla added mjölk, ägg to Veckan"),
        ("en-GB", None, "New on Veckan: mjölk, ägg"),
        ("de", "Embla", "Embla added mjölk, ägg to Veckan"),
    ],
)
def test_message_language_and_adder(
    language: str, name: str | None, expected: str
) -> None:
    title, message = build_message(language, name, "Veckan", ["mjölk", "ägg"])
    assert title == "Inköp"
    assert message == expected


def test_long_lists_are_cut_off() -> None:
    items = [f"vara {n}" for n in range(MAX_LISTED + 3)]
    _, sv = build_message("sv", "A", "L", items)
    _, en = build_message("en", "A", "L", items)
    assert sv.endswith("vara 4 +3 till i L")
    assert en.endswith("vara 4 +3 more to L")
    assert "vara 5" not in sv


def test_exactly_the_limit_is_not_cut() -> None:
    items = [f"v{n}" for n in range(MAX_LISTED)]
    assert "+" not in build_message("sv", "A", "L", items)[1]


def test_companion_app_services_are_preferred() -> None:
    names = ["notify", "mobile_app_per", "send_message", "mobile_app_embla", "smtp"]
    assert choose_notify_services(names) == ["mobile_app_embla", "mobile_app_per"]


def test_other_notify_services_when_there_is_no_phone() -> None:
    assert choose_notify_services(["smtp", "send_message", "alert"]) == [
        "alert",
        "smtp",
    ]


def test_no_notify_services() -> None:
    assert choose_notify_services([]) == []
    assert choose_notify_services(["send_message"]) == []
