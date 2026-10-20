"""Tests for the pure AI failure-notification rules."""

from datetime import UTC, datetime, timedelta

from custom_components.handla.domain import (
    RENOTIFY_AFTER,
    AiHealth,
    build_failure_message,
    record_failure,
    record_success,
)

T0 = datetime(2026, 10, 15, 8, 0, tzinfo=UTC)

TEMPLATES = {
    "ai_failure_title": "AI down",
    "ai_failure_message": "Error: {error} Fix it.",
}


def test_the_first_failure_notifies() -> None:
    health, notify = record_failure(AiHealth(), T0)

    assert notify is True
    assert health == AiHealth(failing_since=T0, last_notified=T0)


def test_further_failures_stay_quiet() -> None:
    first, _ = record_failure(AiHealth(), T0)

    later, notify = record_failure(first, T0 + timedelta(hours=1))

    assert notify is False
    assert later.failing_since == T0
    assert later.last_notified == T0


def test_a_long_outage_reminds_once_a_day() -> None:
    first, _ = record_failure(AiHealth(), T0)

    just_before, quiet = record_failure(
        first, T0 + RENOTIFY_AFTER - timedelta(seconds=1)
    )
    again, notify = record_failure(just_before, T0 + RENOTIFY_AFTER)

    assert quiet is False
    assert notify is True
    assert again.failing_since == T0
    assert again.last_notified == T0 + RENOTIFY_AFTER


def test_success_resets_so_the_next_failure_notifies() -> None:
    failing, _ = record_failure(AiHealth(), T0)

    healthy = record_success(failing)
    _, notify = record_failure(healthy, T0 + timedelta(minutes=5))

    assert healthy == AiHealth()
    assert notify is True


def test_message_uses_the_templates() -> None:
    title, text = build_failure_message(TEMPLATES, "credit balance is too low")
    assert title == "AI down"
    assert text == "Error: credit balance is too low Fix it."


def test_long_and_messy_errors_are_tidied() -> None:
    _, text = build_failure_message(TEMPLATES, "line one\n\n  line   two " + "x" * 500)

    assert "line one line two" in text
    assert "\n" not in text
    assert len(text) < 320
    assert "…" in text
