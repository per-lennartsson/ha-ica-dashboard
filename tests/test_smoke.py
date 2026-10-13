"""Smoke tests: the integration loads and the fake ICA fixture works."""

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.inkop.const import DOMAIN
from tests.conftest import FakeIca


async def test_integration_sets_up(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    assert DOMAIN in hass.data


async def test_fake_ica_records_calls(hass: HomeAssistant, fake_ica: FakeIca) -> None:
    entity_id = fake_ica.add_list("Att handla fredag", "ABC-123", items=2)
    assert hass.states.get(entity_id) is not None

    result = await hass.services.async_call(
        "ica",
        "create_shopping_list",
        {"title": "x"},
        blocking=True,
        return_response=True,
    )
    assert result == {"success": True}
    assert fake_ica.calls_to("create_shopping_list") == [{"title": "x"}]
