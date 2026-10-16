"""Tests for AI provider monitoring: failure notifications and the daily check."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.handla.const import (
    AI_HEALTH_INTERVAL,
    CONF_AI_ENABLED,
    CONF_AI_ENTITY,
    CONF_AI_HEALTH_CHECK,
    CONF_RECIPIENTS,
    DOMAIN,
)
from custom_components.handla.coordinator import HandlaCoordinator
from tests.conftest import (
    AI_ENTITY,
    FakeAiProvider,
    FakeIca,
    FakeTodo,
    IcaConfigure,
    setup_handla,
)

OPTIONS = {
    CONF_AI_ENABLED: True,
    CONF_AI_ENTITY: AI_ENTITY,
    CONF_RECIPIENTS: {"user-1": "mobile_app_per", "user-2": "mobile_app_embla"},
}


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

    def sent_to(self, service: str) -> list[dict[str, Any]]:
        return [data for name, data in self.calls if name == service]


@pytest.fixture
def phones(hass: HomeAssistant) -> Phones:
    return Phones(hass)


async def _setup(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    options: dict[str, Any] | None = None,
) -> MockConfigEntry:
    ica_dependency()
    fake_ica.add_list("Veckan", "L-1")
    return await setup_handla(hass, OPTIONS if options is None else options)


async def _extract(hass: HomeAssistant, text: str = "Pannkakor") -> None:
    await hass.services.async_call(
        DOMAIN,
        "ai_extract_items",
        {"text": text},
        blocking=True,
        return_response=True,
    )


def _monitor(entry: MockConfigEntry) -> Any:
    coordinator: HandlaCoordinator = entry.runtime_data
    return coordinator.ai_monitor


async def _fire(hass: HomeAssistant, days: float = 1) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(days=days, seconds=1))
    await hass.async_block_till_done()


# --- failure notifications ----------------------------------------------------------


async def test_a_provider_failure_notifies_the_chosen_users(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    await _setup(hass, ica_dependency, fake_ica)
    fake_ai.error = HomeAssistantError("credit balance is too low")

    with pytest.raises(HomeAssistantError):
        await _extract(hass)

    for service in ("mobile_app_per", "mobile_app_embla"):
        (sent,) = phones.sent_to(service)
        assert "credit balance is too low" in sent["message"]
        assert sent["title"]


async def test_the_same_outage_notifies_only_once(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    await _setup(hass, ica_dependency, fake_ica)
    fake_ai.error = HomeAssistantError("credit balance is too low")

    for _ in range(3):
        with pytest.raises(HomeAssistantError):
            await _extract(hass)

    assert len(phones.sent_to("mobile_app_per")) == 1


async def test_a_new_outage_after_recovery_notifies_again(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    entry = await _setup(hass, ica_dependency, fake_ica)
    fake_ai.error = HomeAssistantError("credit balance is too low")
    with pytest.raises(HomeAssistantError):
        await _extract(hass)
    assert _monitor(entry).failing is True

    fake_ai.error = None
    await _extract(hass)
    assert _monitor(entry).failing is False

    fake_ai.error = HomeAssistantError("rate limited")
    with pytest.raises(HomeAssistantError):
        await _extract(hass)

    messages = [d["message"] for d in phones.sent_to("mobile_app_per")]
    assert len(messages) == 2
    assert "rate limited" in messages[1]


async def test_a_long_outage_reminds_after_a_day(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    await _setup(hass, ica_dependency, fake_ica)
    fake_ai.error = HomeAssistantError("credit balance is too low")
    with pytest.raises(HomeAssistantError):
        await _extract(hass)

    later = dt_util.utcnow() + timedelta(days=1, minutes=1)
    with (
        patch("custom_components.handla.ai_monitor.dt_util.utcnow", return_value=later),
        pytest.raises(HomeAssistantError),
    ):
        await _extract(hass)

    assert len(phones.sent_to("mobile_app_per")) == 2


async def test_nobody_is_notified_without_recipients(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
    phones: Phones,
    caplog: pytest.LogCaptureFixture,
) -> None:
    options = {CONF_AI_ENABLED: True, CONF_AI_ENTITY: AI_ENTITY}
    await _setup(hass, ica_dependency, fake_ica, options)
    fake_ai.error = HomeAssistantError("credit balance is too low")

    with pytest.raises(HomeAssistantError):
        await _extract(hass)

    assert phones.calls == []
    assert "nobody to notify" in caplog.text
    assert "credit balance is too low" in caplog.text


async def test_a_broken_phone_does_not_hide_the_failure_from_the_others(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    await _setup(hass, ica_dependency, fake_ica)
    phones.failing.add("mobile_app_per")
    fake_ai.error = HomeAssistantError("credit balance is too low")

    with pytest.raises(HomeAssistantError) as err:
        await _extract(hass)

    assert err.value.translation_key == "ai_failed"  # the caller still gets the error
    assert len(phones.sent_to("mobile_app_embla")) == 1


async def test_input_mistakes_and_bad_answers_are_not_provider_failures(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    await _setup(hass, ica_dependency, fake_ica)

    with pytest.raises(HomeAssistantError):
        await _extract(hass, "   ")
    fake_ai.answer = "not what was asked for"
    with pytest.raises(HomeAssistantError):
        await _extract(hass)

    assert phones.calls == []


# --- daily health check -------------------------------------------------------------


async def test_the_health_check_is_off_by_default(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    await _setup(hass, ica_dependency, fake_ica)

    await _fire(hass, days=3)

    assert fake_ai.calls == []


async def test_the_daily_check_calls_the_provider_with_a_tiny_request(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    await _setup(
        hass, ica_dependency, fake_ica, {**OPTIONS, CONF_AI_HEALTH_CHECK: True}
    )

    await _fire(hass)

    (call,) = fake_ai.calls
    assert call["entity_id"] == AI_ENTITY
    assert len(call["instructions"]) < 40
    assert "structure" not in call
    assert phones.calls == []


async def test_a_failing_daily_check_notifies_once_and_recovers(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    entry = await _setup(
        hass, ica_dependency, fake_ica, {**OPTIONS, CONF_AI_HEALTH_CHECK: True}
    )
    fake_ai.error = HomeAssistantError("invalid x-api-key")

    await _fire(hass, days=1)
    await _fire(hass, days=1.5)  # a second failing day, still inside the quiet period
    assert len(phones.sent_to("mobile_app_per")) == 1
    assert _monitor(entry).failing is True

    fake_ai.error = None
    await _fire(hass, days=2)
    assert _monitor(entry).failing is False


async def test_health_check_on_demand_reports_the_outcome(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    entry = await _setup(hass, ica_dependency, fake_ica)
    monitor = _monitor(entry)

    assert await monitor.async_health_check() is True
    fake_ai.error = HomeAssistantError("down")
    assert await monitor.async_health_check() is False
    assert len(phones.sent_to("mobile_app_per")) == 1


async def test_health_check_without_a_provider_is_false(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
) -> None:
    entry = await _setup(hass, ica_dependency, fake_ica, {})

    assert await _monitor(entry).async_health_check() is False
    assert fake_ai.calls == []


async def test_the_check_follows_the_options_and_unload(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    entry = await _setup(hass, ica_dependency, fake_ica, OPTIONS)
    await _fire(hass)
    assert fake_ai.calls == []

    hass.config_entries.async_update_entry(
        entry, options={**OPTIONS, CONF_AI_HEALTH_CHECK: True}
    )
    await hass.async_block_till_done()
    await _fire(hass)
    assert len(fake_ai.calls) == 1

    hass.config_entries.async_update_entry(
        entry, options={**OPTIONS, CONF_AI_HEALTH_CHECK: True, CONF_AI_ENABLED: False}
    )
    await hass.async_block_till_done()
    await _fire(hass, days=3)
    assert len(fake_ai.calls) == 1  # AI off: no more checks

    hass.config_entries.async_update_entry(
        entry, options={**OPTIONS, CONF_AI_HEALTH_CHECK: True}
    )
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)
    await _fire(hass, days=5)
    assert len(fake_ai.calls) == 1  # unloaded: no more checks


async def test_turning_ai_off_forgets_an_outage(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    fake_todo: FakeTodo,
    fake_ai: FakeAiProvider,
    phones: Phones,
) -> None:
    entry = await _setup(hass, ica_dependency, fake_ica)
    fake_ai.error = HomeAssistantError("down")
    with pytest.raises(HomeAssistantError):
        await _extract(hass)
    assert _monitor(entry).failing is True

    hass.config_entries.async_update_entry(entry, options={})
    await hass.async_block_till_done()

    assert _monitor(entry).failing is False


def test_the_interval_is_a_day() -> None:
    assert timedelta(days=1) == AI_HEALTH_INTERVAL
