"""Tests for the pure AI switch rules."""

import pytest

from custom_components.handla.domain import AiStatus, ai_choice_error, ai_status


@pytest.mark.parametrize(
    ("enabled", "ready", "expected"),
    [
        (False, False, AiStatus.OFF),
        (False, True, AiStatus.OFF),
        (True, True, AiStatus.READY),
        (True, False, AiStatus.UNAVAILABLE),
    ],
)
def test_status(enabled: bool, ready: bool, expected: AiStatus) -> None:
    assert ai_status(enabled, ready) is expected


@pytest.mark.parametrize(
    ("enabled", "entity", "exists", "expected"),
    [
        (False, None, False, None),
        (False, "ai_task.gone", False, None),
        (True, None, False, "ai_entity_required"),
        (True, "", False, "ai_entity_required"),
        (True, "ai_task.gone", False, "ai_entity_unknown"),
        (True, "ai_task.x", True, None),
    ],
)
def test_choice_error(
    enabled: bool, entity: str | None, exists: bool, expected: str | None
) -> None:
    assert ai_choice_error(enabled, entity, exists) == expected
