"""Tests for serving the Lovelace card."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.handla.card import (
    CARD_URL,
    async_register_card,
    async_unregister_resource,
)
from custom_components.handla.const import DOMAIN
from tests.conftest import IcaConfigure, setup_handla


@pytest.fixture
def card_file(tmp_path: Path) -> Path:
    file = tmp_path / "handla-card.js"
    file.write_text("// built card")
    return file


@pytest.fixture
def web_server(hass: HomeAssistant) -> MagicMock:
    hass.http = MagicMock()  # type: ignore[assignment]
    hass.http.async_register_static_paths = AsyncMock()
    return hass.http  # type: ignore[return-value]


@pytest.fixture
def extra_js() -> MagicMock:
    with patch("custom_components.handla.card.add_extra_js_url") as add:
        yield add


async def test_card_is_served_and_loaded_in_every_dashboard(
    hass: HomeAssistant, card_file: Path, web_server: MagicMock, extra_js: MagicMock
) -> None:
    with patch("custom_components.handla.card.CARD_FILE", card_file):
        assert await async_register_card(hass, "0.1.0")

    (configs,) = web_server.async_register_static_paths.call_args.args
    (config,) = configs
    assert config.url_path == CARD_URL
    assert config.path == str(card_file)
    assert config.cache_headers is False
    extra_js.assert_called_once_with(hass, f"{CARD_URL}?v=0.1.0")


async def test_registering_twice_does_nothing_the_second_time(
    hass: HomeAssistant, card_file: Path, web_server: MagicMock, extra_js: MagicMock
) -> None:
    with patch("custom_components.handla.card.CARD_FILE", card_file):
        assert await async_register_card(hass, "0.1.0")
        assert await async_register_card(hass, "0.1.0")

    assert web_server.async_register_static_paths.await_count == 1
    assert extra_js.call_count == 1


async def test_a_missing_build_is_reported_not_fatal(
    hass: HomeAssistant,
    tmp_path: Path,
    web_server: MagicMock,
    extra_js: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch("custom_components.handla.card.CARD_FILE", tmp_path / "nope.js"):
        assert not await async_register_card(hass, "0.1.0")

    assert "card file" in caplog.text
    web_server.async_register_static_paths.assert_not_awaited()
    extra_js.assert_not_called()


async def test_no_web_server(
    hass: HomeAssistant,
    card_file: Path,
    extra_js: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    hass.http = None  # type: ignore[assignment]
    with patch("custom_components.handla.card.CARD_FILE", card_file):
        assert not await async_register_card(hass, "0.1.0")

    assert "web server" in caplog.text
    extra_js.assert_not_called()


async def test_setup_registers_the_card_once_even_after_a_reload(
    hass: HomeAssistant,
    ica_dependency: IcaConfigure,
    card_file: Path,
    web_server: MagicMock,
    extra_js: MagicMock,
) -> None:
    ica_dependency()
    with patch("custom_components.handla.card.CARD_FILE", card_file):
        entry = await setup_handla(hass)
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert web_server.async_register_static_paths.await_count == 1
    (call,) = extra_js.call_args_list
    assert call.args[1].startswith(f"{CARD_URL}?v=")
    assert DOMAIN in hass.data


async def test_setup_works_without_a_built_card(
    hass: HomeAssistant, ica_dependency: IcaConfigure, tmp_path: Path
) -> None:
    ica_dependency()
    with patch("custom_components.handla.card.CARD_FILE", tmp_path / "nope.js"):
        entry = await setup_handla(hass)

    assert entry.state.value == "loaded"


@pytest.fixture
async def lovelace(hass: HomeAssistant) -> ResourceStorageCollection:
    assert await async_setup_component(hass, "lovelace", {})
    # Setting up lovelace brings the real web server; the card tests use a stub
    hass.http = MagicMock()  # type: ignore[assignment]
    hass.http.async_register_static_paths = AsyncMock()
    resources = hass.data["lovelace"].resources
    assert isinstance(resources, ResourceStorageCollection)
    return resources


async def _register(hass: HomeAssistant, card_file: Path, version: str) -> bool:
    hass.data.pop(DOMAIN, None)
    with patch("custom_components.handla.card.CARD_FILE", card_file):
        return await async_register_card(hass, version)


async def test_card_becomes_a_dashboard_resource(
    hass: HomeAssistant,
    card_file: Path,
    web_server: MagicMock,
    extra_js: MagicMock,
    lovelace: ResourceStorageCollection,
) -> None:
    assert await _register(hass, card_file, "0.1.0")

    (item,) = lovelace.async_items()
    assert item["url"] == f"{CARD_URL}?v=0.1.0"
    assert item["type"] == "module"
    extra_js.assert_not_called()


async def test_a_new_version_updates_the_resource_instead_of_adding_one(
    hass: HomeAssistant,
    card_file: Path,
    web_server: MagicMock,
    extra_js: MagicMock,
    lovelace: ResourceStorageCollection,
) -> None:
    await _register(hass, card_file, "0.1.0")
    await _register(hass, card_file, "0.2.0")

    (item,) = lovelace.async_items()
    assert item["url"] == f"{CARD_URL}?v=0.2.0"


async def test_a_resource_added_by_hand_is_not_duplicated(
    hass: HomeAssistant,
    card_file: Path,
    web_server: MagicMock,
    extra_js: MagicMock,
    lovelace: ResourceStorageCollection,
) -> None:
    await lovelace.async_create_item({"res_type": "module", "url": CARD_URL})

    assert await _register(hass, card_file, "0.1.0")

    (item,) = lovelace.async_items()
    assert item["url"] == CARD_URL


async def test_a_failing_resource_write_falls_back_to_the_extra_script(
    hass: HomeAssistant,
    card_file: Path,
    web_server: MagicMock,
    extra_js: MagicMock,
    lovelace: ResourceStorageCollection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch.object(
        lovelace, "async_create_item", side_effect=HomeAssistantError("disk full")
    ):
        assert await _register(hass, card_file, "0.1.0")

    assert "disk full" in caplog.text
    extra_js.assert_called_once_with(hass, f"{CARD_URL}?v=0.1.0")


async def test_removing_the_integration_removes_the_resource(
    hass: HomeAssistant,
    card_file: Path,
    web_server: MagicMock,
    extra_js: MagicMock,
    lovelace: ResourceStorageCollection,
) -> None:
    await _register(hass, card_file, "0.1.0")

    await async_unregister_resource(hass)

    assert lovelace.async_items() == []


async def test_removing_does_nothing_without_storage_resources(
    hass: HomeAssistant,
) -> None:
    await async_unregister_resource(hass)


async def test_a_failing_resource_delete_is_logged(
    hass: HomeAssistant,
    card_file: Path,
    web_server: MagicMock,
    extra_js: MagicMock,
    lovelace: ResourceStorageCollection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _register(hass, card_file, "0.1.0")
    with patch.object(
        lovelace, "async_delete_item", side_effect=HomeAssistantError("locked")
    ):
        await async_unregister_resource(hass)

    assert "locked" in caplog.text
