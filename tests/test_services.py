"""Tests for create_list / delete_list, including the reload wait and failures."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from custom_components.inkop.const import DOMAIN
from custom_components.inkop.coordinator import InkopCoordinator, Status
from tests.conftest import ICA_ENTRY_ID, FakeIca, IcaConfigure, setup_inkop


@pytest.fixture(autouse=True)
def fixed_today() -> Iterator[None]:
    with patch(
        "custom_components.inkop.coordinator.dt_util.now",
        return_value=datetime(2026, 10, 14, 12, 0, tzinfo=UTC),
    ):
        yield


@pytest.fixture
def short_timeout() -> Iterator[None]:
    with patch("custom_components.inkop.coordinator.LISTS_CHANGED_TIMEOUT", 0.05):
        yield


async def _create(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    result = await hass.services.async_call(
        DOMAIN, "create_list", data, blocking=True, return_response=True
    )
    assert result is not None
    return dict(result)


async def _setup(hass: HomeAssistant, ica_dependency: IcaConfigure) -> InkopCoordinator:
    ica_dependency()
    entry = await setup_inkop(hass)
    coordinator: InkopCoordinator = entry.runtime_data
    return coordinator


# --- create ---------------------------------------------------------------


async def test_create_list_waits_for_reload_and_makes_it_active(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    coordinator = await _setup(hass, ica_dependency)
    fake_ica.install_create("NEW-1")

    result = await _create(hass, title="Fredagsmat")

    assert result["title"] == "Fredagsmat"
    assert result["offline_id"] == "NEW-1"
    assert result["entity_id"].startswith("todo.ica_")
    assert coordinator.data.active_offline_id == "NEW-1"
    assert coordinator.status is Status.IDLE
    (call,) = fake_ica.calls_to("create_shopping_list")
    assert call == {
        "integration": [ICA_ENTRY_ID],
        "title": "Fredagsmat",
        "comment": "",
        "track": True,
    }


async def test_default_title_uses_the_date(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    await _setup(hass, ica_dependency)
    fake_ica.install_create("NEW-1")

    result = await _create(hass)

    assert result["title"] == "Att handla 14 oktober"


async def test_default_title_is_numbered_when_taken(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    await _setup(hass, ica_dependency)
    fake_ica.add_list("Att handla 14 oktober", "OLD-1")
    fake_ica.install_create("NEW-1")

    result = await _create(hass)

    assert result["title"] == "Att handla 14 oktober (2)"


async def test_create_without_making_it_active(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    coordinator = await _setup(hass, ica_dependency)
    fake_ica.add_list("Aaa", "OLD-1")
    await hass.async_block_till_done()
    fake_ica.install_create("NEW-1")

    await _create(hass, title="Zzz", set_active=False)

    assert coordinator.data.active_offline_id == "OLD-1"


async def test_event_that_arrives_before_the_service_returns_is_not_missed(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    await _setup(hass, ica_dependency)
    fake_ica.install_create("NEW-1", early=True)

    result = await _create(hass, title="Snabb")

    assert result["offline_id"] == "NEW-1"


async def test_event_with_lower_case_id_matches(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    """ICA stores ids in upper case; the event may differ in case from the response."""
    await _setup(hass, ica_dependency)

    async def handler(data: dict[str, Any]) -> dict[str, Any]:
        entity_id = fake_ica.add_list(data["title"], "ABC-1")
        hass.async_create_task(_fire_later(entity_id))
        return {"success": True, "offline_id": "abc-1"}

    async def _fire_later(entity_id: str) -> None:
        await asyncio.sleep(0)
        fake_ica.fire_lists_changed(created=["ABC-1"], entities={"ABC-1": entity_id})

    fake_ica.handlers["create_shopping_list"] = handler

    result = await _create(hass, title="Versaler")

    assert result["offline_id"] == "ABC-1"


async def test_create_times_out_when_no_event_arrives(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    short_timeout: None,
) -> None:
    coordinator = await _setup(hass, ica_dependency)
    fake_ica.install_create("NEW-1", fire=False)

    with pytest.raises(HomeAssistantError) as err:
        await _create(hass, title="Hängande")

    assert err.value.translation_key == "create_timeout"
    assert coordinator.status is Status.ERROR
    assert coordinator.status_detail


async def test_create_fails_when_event_has_no_entity(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    """The event also fires when the reload failed, then without the entity."""
    coordinator = await _setup(hass, ica_dependency)
    fake_ica.install_create("NEW-1", include_entity=False)

    with pytest.raises(HomeAssistantError) as err:
        await _create(hass, title="Trasig")

    assert err.value.translation_key == "create_failed"
    assert coordinator.status is Status.ERROR


async def test_create_fails_when_ica_service_fails(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    coordinator = await _setup(hass, ica_dependency)

    async def boom(data: dict[str, Any]) -> dict[str, Any]:
        raise HomeAssistantError("ICA said no")

    fake_ica.handlers["create_shopping_list"] = boom

    with pytest.raises(HomeAssistantError) as err:
        await _create(hass, title="Nej")

    assert err.value.translation_key == "create_failed"
    assert "ICA said no" in err.value.translation_placeholders["error"]  # type: ignore[index]
    assert coordinator.status is Status.ERROR


async def test_create_fails_when_ica_returns_no_id(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    await _setup(hass, ica_dependency)
    fake_ica.responses["create_shopping_list"] = {"success": True}

    with pytest.raises(HomeAssistantError) as err:
        await _create(hass, title="Utan id")

    assert err.value.translation_key == "create_failed"


async def test_error_status_is_cleared_by_the_next_operation(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    short_timeout: None,
) -> None:
    coordinator = await _setup(hass, ica_dependency)
    fake_ica.install_create("NEW-1", fire=False)
    with pytest.raises(HomeAssistantError):
        await _create(hass, title="Först")
    assert coordinator.status is Status.ERROR

    fake_ica.install_create("NEW-2")
    await _create(hass, title="Sedan")

    assert coordinator.status is Status.IDLE
    assert coordinator.status_detail is None


async def test_create_fails_when_ica_is_not_loaded(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    ica_entry = ica_dependency()
    assert ica_entry is not None
    entry = await setup_inkop(hass)
    ica_entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    with pytest.raises(HomeAssistantError) as err:
        await _create(hass, title="Ingen ICA")

    assert err.value.translation_key == "ica_unavailable"
    assert entry.runtime_data.status is Status.ERROR
    assert not fake_ica.calls


async def test_second_operation_is_refused_while_busy(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    coordinator = await _setup(hass, ica_dependency)
    gate = asyncio.Event()
    fake_ica.install_create("NEW-1", gate=gate)

    first = hass.async_create_task(_create(hass, title="Först"))
    await asyncio.sleep(0.01)
    assert coordinator.status is Status.CREATING

    with pytest.raises(ServiceValidationError) as err:
        await _create(hass, title="Andra")
    assert err.value.translation_key == "busy"

    gate.set()
    result = await first
    assert result["title"] == "Först"
    assert coordinator.status is Status.IDLE
    assert len(fake_ica.calls_to("create_shopping_list")) == 1


async def test_services_refuse_when_not_set_up(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as err:
        await _create(hass, title="Ingen")

    assert err.value.translation_key == "not_set_up"


# --- delete ---------------------------------------------------------------


async def test_delete_list_waits_for_reload_and_moves_active(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    coordinator = await _setup(hass, ica_dependency)
    bread = fake_ica.add_list("Bröd", "B-2")
    fake_ica.add_list("Mjölk", "M-1")
    await hass.async_block_till_done()
    assert coordinator.data.active_offline_id == "B-2"
    fake_ica.install_delete()

    result = await hass.services.async_call(
        DOMAIN,
        "delete_list",
        {"entity_id": bread},
        blocking=True,
        return_response=True,
    )

    assert result == {"entity_id": bread, "offline_id": "B-2"}
    assert [i.offline_id for i in coordinator.data.lists] == ["M-1"]
    assert coordinator.data.active_offline_id == "M-1"
    assert coordinator.status is Status.IDLE
    assert fake_ica.calls_to("delete_shopping_list") == [{"entity_id": bread}]


async def test_delete_unknown_list_is_refused_without_calling_ica(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    coordinator = await _setup(hass, ica_dependency)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, "delete_list", {"entity_id": "todo.nope"}, blocking=True
        )

    assert err.value.translation_key == "unknown_list"
    assert not fake_ica.calls
    assert coordinator.status is Status.IDLE


async def test_delete_fails_when_ica_service_fails(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    coordinator = await _setup(hass, ica_dependency)
    milk = fake_ica.add_list("Mjölk", "M-1")

    async def boom(data: dict[str, Any]) -> dict[str, Any]:
        raise HomeAssistantError("nope")

    fake_ica.handlers["delete_shopping_list"] = boom

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, "delete_list", {"entity_id": milk}, blocking=True
        )

    assert err.value.translation_key == "delete_failed"
    assert coordinator.status is Status.ERROR
    assert [i.offline_id for i in coordinator.data.lists] == ["M-1"]


async def test_delete_times_out_when_no_event_arrives(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    fake_ica: FakeIca,
    short_timeout: None,
) -> None:
    coordinator = await _setup(hass, ica_dependency)
    milk = fake_ica.add_list("Mjölk", "M-1")
    fake_ica.install_delete(fire=False)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, "delete_list", {"entity_id": milk}, blocking=True
        )

    assert err.value.translation_key == "delete_timeout"
    assert coordinator.status is Status.ERROR


# --- suggest_list_name ------------------------------------------------------


async def _suggest(hass: HomeAssistant) -> str:
    result = await hass.services.async_call(
        DOMAIN, "suggest_list_name", {}, blocking=True, return_response=True
    )
    assert result is not None
    return str(result["name"])


async def test_suggest_list_name_uses_the_date(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    await _setup(hass, ica_dependency)

    assert await _suggest(hass) == "Att handla 14 oktober"


async def test_suggest_list_name_numbers_a_taken_name(
    hass: HomeAssistant, ica_dependency: IcaConfigure, fake_ica: FakeIca
) -> None:
    await _setup(hass, ica_dependency)
    fake_ica.add_list("Att handla 14 oktober", "OLD-1")
    fake_ica.add_list("Att handla 14 oktober (2)", "OLD-2")
    await hass.async_block_till_done()

    assert await _suggest(hass) == "Att handla 14 oktober (3)"


async def test_suggest_list_name_needs_a_set_up_integration(
    hass: HomeAssistant,
) -> None:
    assert await async_setup_component(hass, DOMAIN, {})

    with pytest.raises(ServiceValidationError) as err:
        await _suggest(hass)

    assert err.value.translation_key == "not_set_up"
