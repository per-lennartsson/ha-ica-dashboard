"""Smoke tests: the fake ICA fixture works."""

from homeassistant.core import HomeAssistant

from tests.conftest import FakeIca


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
