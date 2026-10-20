"""Tests for ListsChangedWaiter: events before, during and after the wait."""

import asyncio
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.handla.const import ICA_LISTS_CHANGED
from custom_components.handla.events import ListsChangedWaiter


def _is(offline_id: str) -> Any:
    return lambda event: offline_id in event.get("created", [])


async def test_event_fired_before_wait_is_not_missed(hass: HomeAssistant) -> None:
    async with ListsChangedWaiter(hass) as waiter:
        hass.bus.async_fire(ICA_LISTS_CHANGED, {"created": ["A"]})
        await hass.async_block_till_done()
        event = await waiter.wait_for(_is("A"), 1)
    assert event is not None
    assert event["created"] == ["A"]


async def test_event_fired_during_wait_wakes_it(hass: HomeAssistant) -> None:
    async with ListsChangedWaiter(hass) as waiter:
        task = asyncio.create_task(waiter.wait_for(_is("B"), 5))
        await asyncio.sleep(0)
        hass.bus.async_fire(ICA_LISTS_CHANGED, {"created": ["B"]})
        event = await task
    assert event is not None
    assert event["created"] == ["B"]


async def test_non_matching_events_are_skipped(hass: HomeAssistant) -> None:
    async with ListsChangedWaiter(hass) as waiter:
        hass.bus.async_fire(ICA_LISTS_CHANGED, {"created": ["OTHER"]})
        hass.bus.async_fire(ICA_LISTS_CHANGED, {"created": ["WANTED"]})
        await hass.async_block_till_done()
        event = await waiter.wait_for(_is("WANTED"), 1)
    assert event is not None
    assert event["created"] == ["WANTED"]


async def test_timeout_returns_none(hass: HomeAssistant) -> None:
    async with ListsChangedWaiter(hass) as waiter:
        hass.bus.async_fire(ICA_LISTS_CHANGED, {"created": ["OTHER"]})
        assert await waiter.wait_for(_is("NEVER"), 0.05) is None


async def test_stops_listening_on_exit(hass: HomeAssistant) -> None:
    async with ListsChangedWaiter(hass) as waiter:
        pass
    hass.bus.async_fire(ICA_LISTS_CHANGED, {"created": ["LATE"]})
    await hass.async_block_till_done()
    assert await waiter.wait_for(_is("LATE"), 0.05) is None
