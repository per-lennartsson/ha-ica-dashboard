"""Tests for the 'someone added items' events and notifications."""

import asyncio
import logging
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.auth.models import User
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.handla.const import CONF_RECIPIENTS, DOMAIN, EVENT_ITEM_ADDED
from tests.conftest import FakeIca, FakeTodo, IcaConfigure, setup_handla


@pytest.fixture(autouse=True)
def short_window() -> Iterator[None]:
    with patch("custom_components.handla.notify.NOTIFY_DELAY", 0.02):
        yield


@pytest.fixture
async def per(hass: HomeAssistant) -> User:
    return await hass.auth.async_create_user("Per")


@pytest.fixture
async def embla(hass: HomeAssistant) -> User:
    return await hass.auth.async_create_user("Embla")


class Phones:
    """Records notify.* calls."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.failing: set[str] = set()
        for service in ("mobile_app_per", "mobile_app_embla"):
            hass.services.async_register("notify", service, self._make(service))

    def _make(self, service: str) -> Any:
        async def handler(call: ServiceCall) -> None:
            if service in self.failing:
                raise HomeAssistantError("phone offline")
            self.calls.append((service, dict(call.data)))

        return handler

    def messages(self, service: str) -> list[str]:
        return [data["message"] for name, data in self.calls if name == service]


@pytest.fixture
def phones(hass: HomeAssistant) -> Phones:
    return Phones(hass)


@pytest.fixture
async def household(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    phones: Phones,
    per: User,
    embla: User,
) -> str:
    """Handla set up with Per and Embla as recipients; returns the list entity id."""
    hass.config.language = "sv"
    ica_dependency()
    entity_id = fake_ica.add_list("Veckan", "L-1")
    await setup_handla(
        hass,
        {CONF_RECIPIENTS: {per.id: "mobile_app_per", embla.id: "mobile_app_embla"}},
    )
    return entity_id


async def _add(
    hass: HomeAssistant, item: str, user: User | None, **data: Any
) -> dict[str, Any]:
    result = await hass.services.async_call(
        DOMAIN,
        "add_item",
        {"item": item, **data},
        blocking=True,
        return_response=True,
        context=Context(user_id=user.id) if user else Context(),
    )
    assert result is not None
    return dict(result)


async def _settle(hass: HomeAssistant) -> None:
    await asyncio.sleep(0.1)
    await hass.async_block_till_done()


async def test_the_other_user_is_told_and_the_adder_is_not(
    hass: HomeAssistant, household: str, phones: Phones, per: User
) -> None:
    await _add(hass, "2 st gurka", per)
    await _settle(hass)

    assert phones.messages("mobile_app_embla") == ["Per lade till 2 st gurka i Veckan"]
    assert phones.messages("mobile_app_per") == []
    data = phones.calls[0][1]
    assert data["title"] == "Handla"
    assert data["data"] == {"tag": "handla"}


async def test_quick_adds_are_combined_into_one_message(
    hass: HomeAssistant, household: str, phones: Phones, per: User
) -> None:
    await _add(hass, "mjölk", per)
    await _add(hass, "ägg", per)
    await _add(hass, "MJÖLK", per, confirm_duplicate=True)
    await _settle(hass)

    assert phones.messages("mobile_app_embla") == ["Per lade till mjölk, ägg i Veckan"]


async def test_each_adder_gets_a_message_of_their_own(
    hass: HomeAssistant, household: str, phones: Phones, per: User, embla: User
) -> None:
    await _add(hass, "mjölk", per)
    await _add(hass, "ägg", embla)
    await _settle(hass)

    assert phones.messages("mobile_app_embla") == ["Per lade till mjölk i Veckan"]
    assert phones.messages("mobile_app_per") == ["Embla lade till ägg i Veckan"]


async def test_a_later_add_starts_a_new_message(
    hass: HomeAssistant, household: str, phones: Phones, per: User
) -> None:
    await _add(hass, "mjölk", per)
    await _settle(hass)
    await _add(hass, "ägg", per)
    await _settle(hass)

    assert phones.messages("mobile_app_embla") == [
        "Per lade till mjölk i Veckan",
        "Per lade till ägg i Veckan",
    ]


async def test_an_add_without_a_user_tells_everyone(
    hass: HomeAssistant, household: str, phones: Phones
) -> None:
    await _add(hass, "mjölk", None)
    await _settle(hass)

    assert phones.messages("mobile_app_per") == ["Nytt på Veckan: mjölk"]
    assert phones.messages("mobile_app_embla") == ["Nytt på Veckan: mjölk"]


async def test_an_unknown_user_id_is_treated_as_no_name(
    hass: HomeAssistant, household: str, phones: Phones
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "add_item",
        {"item": "mjölk"},
        blocking=True,
        context=Context(user_id="deleted-user"),
    )
    await _settle(hass)

    assert phones.messages("mobile_app_embla") == ["Nytt på Veckan: mjölk"]


async def test_english_when_home_assistant_is_english(
    hass: HomeAssistant, household: str, phones: Phones, per: User
) -> None:
    hass.config.language = "en"
    await _add(hass, "milk", per)
    await _settle(hass)

    assert phones.messages("mobile_app_embla") == ["Per added milk to Veckan"]


async def test_a_failing_phone_does_not_block_the_others_or_the_add(
    hass: HomeAssistant,
    household: str,
    phones: Phones,
    per: User,
    embla: User,
    caplog: pytest.LogCaptureFixture,
    fake_todo: FakeTodo,
) -> None:
    phones.failing.add("mobile_app_embla")
    caplog.set_level(logging.WARNING)

    result = await _add(hass, "mjölk", None)
    await _settle(hass)

    assert result["added"] is True
    assert fake_todo.summaries(household) == ["mjölk"]
    assert phones.messages("mobile_app_per") == ["Nytt på Veckan: mjölk"]
    assert "Could not notify user" in caplog.text
    assert "mobile_app_embla" in caplog.text


async def test_nothing_is_sent_for_a_duplicate_that_was_not_added(
    hass: HomeAssistant,
    household: str,
    phones: Phones,
    per: User,
    fake_todo: FakeTodo,
) -> None:
    fake_todo.seed(household, "mjölk")
    events = async_capture_events(hass, EVENT_ITEM_ADDED)

    result = await _add(hass, "mjölk", per)
    await _settle(hass)

    assert result["added"] is False
    assert not phones.calls
    assert not events


async def test_nothing_is_sent_without_recipients(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    phones: Phones,
    per: User,
) -> None:
    ica_dependency()
    fake_ica.add_list("Veckan", "L-1")
    await setup_handla(hass)

    await _add(hass, "mjölk", per)
    await _settle(hass)

    assert not phones.calls


@pytest.mark.parametrize(
    "options", [{CONF_RECIPIENTS: "nonsense"}, {CONF_RECIPIENTS: {"u": 5}}]
)
async def test_malformed_options_are_ignored(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    phones: Phones,
    options: dict[str, Any],
) -> None:
    ica_dependency()
    fake_ica.add_list("Veckan", "L-1")
    await setup_handla(hass, options)

    await _add(hass, "mjölk", None)
    await _settle(hass)

    assert not phones.calls


async def test_the_added_event_names_the_user(
    hass: HomeAssistant, household: str, per: User
) -> None:
    events = async_capture_events(hass, EVENT_ITEM_ADDED)

    await _add(hass, "2 st gurka", per)
    await hass.async_block_till_done()

    (event,) = events
    assert event.data == {
        "entity_id": household,
        "list_title": "Veckan",
        "item": "2 st gurka",
        "user_id": per.id,
        "user_name": "Per",
    }
    assert event.context.user_id == per.id


async def test_the_added_event_without_a_user(
    hass: HomeAssistant, household: str
) -> None:
    events = async_capture_events(hass, EVENT_ITEM_ADDED)

    await _add(hass, "mjölk", None)
    await hass.async_block_till_done()

    assert events[0].data["user_id"] is None
    assert events[0].data["user_name"] is None


async def test_long_batches_are_cut_off(
    hass: HomeAssistant, household: str, phones: Phones, per: User
) -> None:
    for number in range(7):
        await _add(hass, f"vara {number}", per)
    await _settle(hass)

    (message,) = phones.messages("mobile_app_embla")
    assert (
        message
        == "Per lade till vara 0, vara 1, vara 2, vara 3, vara 4 +2 till i Veckan"
    )


async def test_pending_messages_are_sent_when_the_integration_unloads(
    hass: HomeAssistant, household: str, phones: Phones, per: User
) -> None:
    with patch("custom_components.handla.notify.NOTIFY_DELAY", 60):
        await _add(hass, "mjölk", per)
        assert not phones.calls

        (entry,) = hass.config_entries.async_entries(DOMAIN)
        assert await hass.config_entries.async_unload(entry.entry_id)

    assert phones.messages("mobile_app_embla") == ["Per lade till mjölk i Veckan"]


async def test_one_timer_serves_a_whole_batch(
    hass: HomeAssistant, household: str, phones: Phones, per: User
) -> None:
    with patch(
        "custom_components.handla.notify.async_call_later",
        wraps=async_call_later,
    ) as timer:
        await _add(hass, "mjölk", per)
        await _add(hass, "ägg", per)
        await _add(hass, "smör", per)
        await _settle(hass)

    assert timer.call_count == 1
    assert len(phones.messages("mobile_app_embla")) == 1
