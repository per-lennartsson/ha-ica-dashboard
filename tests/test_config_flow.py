"""Tests for the config flow, including the ICA dependency check."""

import pytest
from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.handla.const import DOMAIN
from tests.conftest import IcaConfigure


async def _start_flow(hass: HomeAssistant) -> ConfigFlowResult:
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def test_user_flow_creates_entry(
    hass: HomeAssistant, ica_dependency: IcaConfigure
) -> None:
    ica_dependency()
    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Handla"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize(
    ("configure", "reason"),
    [
        ({"installed": False}, "ica_missing"),
        ({"version": "v0.9.0"}, "ica_too_old"),
        ({"entry_state": None}, "ica_not_configured"),
        ({"entry_state": ConfigEntryState.NOT_LOADED}, "ica_not_loaded"),
    ],
)
async def test_flow_aborts_when_ica_is_unusable(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    configure: dict[str, object],
    reason: str,
) -> None:
    ica_dependency(**configure)

    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert result["description_placeholders"]["minimum"] == "0.10.0"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_too_old_abort_shows_the_installed_version(
    hass: HomeAssistant, ica_dependency: IcaConfigure
) -> None:
    ica_dependency(version="v0.9.0")
    result = await _start_flow(hass)
    assert result["description_placeholders"]["version"] == "v0.9.0"


async def test_only_one_instance_allowed(
    hass: HomeAssistant, ica_dependency: IcaConfigure
) -> None:
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await _start_flow(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
