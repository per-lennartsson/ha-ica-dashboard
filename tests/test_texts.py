"""Tests for the translated notification templates (strings.json and translations)."""

import json
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant

from custom_components.handla.domain import (
    AI_FAILURE_KEYS,
    NOTIFY_KEYS,
    build_failure_message,
    build_message,
)
from custom_components.handla.texts import async_get_templates

HANDLA = Path(__file__).parent.parent / "custom_components" / "handla"
ALL_KEYS = (*NOTIFY_KEYS, *AI_FAILURE_KEYS)


@pytest.mark.parametrize(
    "file", ["strings.json", "translations/en.json", "translations/sv.json"]
)
def test_every_template_exists_in_every_file(file: str) -> None:
    exceptions = json.loads((HANDLA / file).read_text())["exceptions"]
    for key in ALL_KEYS:
        assert exceptions[key]["message"]


async def test_swedish_templates(hass: HomeAssistant) -> None:
    hass.config.language = "sv"
    templates = await async_get_templates(hass, NOTIFY_KEYS)
    _, text = build_message(templates, "Per", "Veckan", ["mjölk"])
    assert text == "Per lade till mjölk i Veckan"
    templates = await async_get_templates(hass, AI_FAILURE_KEYS)
    title, text = build_failure_message(templates, "credit balance is too low")
    assert title == "Handla: AI fungerar inte"
    assert "credit balance is too low" in text


@pytest.mark.parametrize("language", ["en", "en-GB", "de"])
async def test_english_templates_and_fallback(
    hass: HomeAssistant, language: str
) -> None:
    hass.config.language = language
    templates = await async_get_templates(hass, NOTIFY_KEYS)
    _, text = build_message(templates, None, "Veckan", ["milk"])
    assert text == "New on Veckan: milk"
    templates = await async_get_templates(hass, AI_FAILURE_KEYS)
    title, _ = build_failure_message(templates, "x")
    assert title == "Handla: AI is not working"


@pytest.mark.parametrize(
    ("ha_language", "chosen", "expected"),
    [
        ("en", "sv", "Per lade till mjölk i Veckan"),
        ("sv", "en", "Per added milk to Veckan"),
        ("sv", "auto", "Per lade till mjölk i Veckan"),
        ("en", "auto", "Per added milk to Veckan"),
    ],
)
async def test_chosen_language_beats_home_assistants(
    hass: HomeAssistant, ha_language: str, chosen: str, expected: str
) -> None:
    hass.config.language = ha_language
    templates = await async_get_templates(hass, NOTIFY_KEYS, chosen)
    _, text = build_message(
        templates, "Per", "Veckan", ["mjölk" if "lade" in expected else "milk"]
    )
    assert text == expected


async def test_unknown_key_raises(hass: HomeAssistant) -> None:
    with pytest.raises(KeyError):
        await async_get_templates(hass, ["no_such_template"])
