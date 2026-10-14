"""Tests for entry setup, the repair issue and recovery."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.inkop.const import DOMAIN
from custom_components.inkop.dependency import ISSUE_ID
from tests.conftest import ICA_DOMAIN, IcaConfigure


def _issue(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID)


async def test_entry_sets_up_and_unloads(
    hass: HomeAssistant, ica_dependency: IcaConfigure
) -> None:
    ica_dependency()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert _issue(hass) is None

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("configure", "key"),
    [
        ({"installed": False}, "ica_missing"),
        ({"version": "v0.9.0"}, "ica_too_old"),
        ({"entry_state": None}, "ica_not_configured"),
        ({"entry_state": ConfigEntryState.NOT_LOADED}, "ica_not_loaded"),
    ],
)
async def test_setup_retries_and_raises_issue_when_ica_is_unusable(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    configure: dict[str, object],
    key: str,
) -> None:
    ica_dependency(**configure)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    issue = _issue(hass)
    assert issue is not None
    assert issue.translation_key == key


async def test_issue_is_cleared_when_ica_recovers(hass: HomeAssistant) -> None:
    # First attempt: ICA missing (nothing patched, no ica integration exists in tests)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert _issue(hass) is not None

    # ICA becomes usable, then the retry succeeds and clears the issue
    ica_entry = MockConfigEntry(domain=ICA_DOMAIN, state=ConfigEntryState.LOADED)
    ica_entry.add_to_hass(hass)
    found = AsyncMock(return_value=SimpleNamespace(manifest={"version": "v0.10.0"}))
    with patch("custom_components.inkop.dependency.async_get_integration", found):
        await hass.config_entries.async_reload(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert _issue(hass) is None


async def test_removing_the_entry_clears_the_issue(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert _issue(hass) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    assert _issue(hass) is None
