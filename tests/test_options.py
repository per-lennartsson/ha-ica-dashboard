"""Tests for reading options from the config entry."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.handla.const import (
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    CONF_AI_HEALTH_CHECK,
    CONF_NOTIFY_LANGUAGE,
    CONF_RECIPIENTS,
    DOMAIN,
)
from custom_components.handla.domain import event_data
from custom_components.handla.options import (
    get_ai_config,
    get_health_check,
    get_notification_language,
    get_recipients,
)


def _entry(options: dict[str, Any]) -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, options=options)


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, (False, None)),
        ({CONF_AI_ENABLED: True}, (True, None)),
        ({CONF_AI_ENABLED: "yes"}, (False, None)),
        ({CONF_AI_ENABLED: True, CONF_AI_ENTITY: "ai_task.x"}, (True, "ai_task.x")),
        ({CONF_AI_ENABLED: True, CONF_AI_ENTITY: ""}, (True, None)),
        ({CONF_AI_ENABLED: True, CONF_AI_ENTITY: 5}, (True, None)),
    ],
)
def test_get_ai_config(
    options: dict[str, Any], expected: tuple[bool, str | None]
) -> None:
    assert get_ai_config(_entry(options)) == expected


def test_health_check_is_off_unless_explicitly_on() -> None:
    assert get_health_check(_entry({})) is False
    assert get_health_check(_entry({CONF_AI_HEALTH_CHECK: "true"})) is False
    assert get_health_check(_entry({CONF_AI_HEALTH_CHECK: True})) is True


def test_get_recipients_ignores_malformed_options() -> None:
    assert get_recipients(_entry({})) == {}
    assert get_recipients(_entry({CONF_RECIPIENTS: ["a"]})) == {}
    options = {CONF_RECIPIENTS: {"u1": "mobile_app_a", "u2": "", "u3": 4}}
    assert get_recipients(_entry(options)) == {"u1": "mobile_app_a"}


def test_event_data_payload() -> None:
    assert event_data("todo.x", "Veckan", "2 st mjölk", "u1", "Per") == {
        "entity_id": "todo.x",
        "list_title": "Veckan",
        "item": "2 st mjölk",
        "user_id": "u1",
        "user_name": "Per",
    }


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, "auto"),
        ({CONF_NOTIFY_LANGUAGE: "sv"}, "sv"),
        ({CONF_NOTIFY_LANGUAGE: "en"}, "en"),
        ({CONF_NOTIFY_LANGUAGE: "auto"}, "auto"),
        ({CONF_NOTIFY_LANGUAGE: "de"}, "auto"),
        ({CONF_NOTIFY_LANGUAGE: 5}, "auto"),
    ],
)
def test_notification_language_defaults_to_auto(
    options: dict[str, Any], expected: str
) -> None:
    assert get_notification_language(_entry(options)) == expected
