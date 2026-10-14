"""Tests for the ha-ica-todo dependency check."""

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.inkop.const import DOMAIN, MIN_ICA_VERSION
from custom_components.inkop.dependency import (
    ISSUE_ID,
    IcaProblem,
    IcaStatus,
    async_check_ica,
    create_dependency_issue,
    delete_dependency_issue,
)
from tests.conftest import IcaConfigure


async def test_ok(hass: HomeAssistant, ica_dependency: IcaConfigure) -> None:
    ica_dependency()
    status = await async_check_ica(hass)
    assert status == IcaStatus(None, "v0.10.0")
    assert status.translation_key is None


async def test_missing(hass: HomeAssistant, ica_dependency: IcaConfigure) -> None:
    ica_dependency(installed=False)
    assert (await async_check_ica(hass)).problem is IcaProblem.MISSING


@pytest.mark.parametrize("version", ["v0.9.0", "0.1.0", "garbage", None])
async def test_too_old(
    hass: HomeAssistant, ica_dependency: IcaConfigure, version: str | None
) -> None:
    ica_dependency(version=version)
    status = await async_check_ica(hass)
    assert status.problem is IcaProblem.TOO_OLD
    assert status.version == version


async def test_not_configured(
    hass: HomeAssistant, ica_dependency: IcaConfigure
) -> None:
    ica_dependency(entry_state=None)
    assert (await async_check_ica(hass)).problem is IcaProblem.NOT_CONFIGURED


@pytest.mark.parametrize(
    "state",
    [
        ConfigEntryState.NOT_LOADED,
        ConfigEntryState.SETUP_ERROR,
        ConfigEntryState.SETUP_RETRY,
    ],
)
async def test_not_loaded(
    hass: HomeAssistant, ica_dependency: IcaConfigure, state: ConfigEntryState
) -> None:
    ica_dependency(entry_state=state)
    assert (await async_check_ica(hass)).problem is IcaProblem.NOT_LOADED


async def test_too_old_is_reported_before_not_configured(
    hass: HomeAssistant, ica_dependency: IcaConfigure
) -> None:
    ica_dependency(version="v0.9.0", entry_state=None)
    assert (await async_check_ica(hass)).problem is IcaProblem.TOO_OLD


def test_translation_key_and_placeholders() -> None:
    status = IcaStatus(IcaProblem.TOO_OLD, "v0.9.0")
    assert status.translation_key == "ica_too_old"
    assert status.placeholders == {"version": "v0.9.0", "minimum": MIN_ICA_VERSION}
    assert IcaStatus(IcaProblem.MISSING).placeholders["version"] == "?"


async def test_issue_create_update_delete(hass: HomeAssistant) -> None:
    registry = ir.async_get(hass)

    create_dependency_issue(hass, IcaStatus(IcaProblem.MISSING))
    issue = registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "ica_missing"
    assert issue.severity is ir.IssueSeverity.ERROR
    assert not issue.is_fixable

    create_dependency_issue(hass, IcaStatus(IcaProblem.TOO_OLD, "v0.9.0"))
    issue = registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.translation_key == "ica_too_old"

    delete_dependency_issue(hass)
    assert registry.async_get_issue(DOMAIN, ISSUE_ID) is None


def test_no_issue_for_ok_status(hass: HomeAssistant) -> None:
    create_dependency_issue(hass, IcaStatus(None))
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID) is None
