"""Tests for serving the Lovelace card."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.handla.card import CARD_URL, async_register_card
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
