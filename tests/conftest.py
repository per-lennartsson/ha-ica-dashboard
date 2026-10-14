"""Shared fixtures: a fake ICA integration (todo entities + ica services)."""

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import IntegrationNotFound
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytest_plugins = "pytest_homeassistant_custom_component"

ICA_DOMAIN = "ica"
ICA_ENTRY_ID = "ica_entry_1"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow loading integrations from custom_components in every test."""


@dataclass
class FakeIca:
    """Records calls to mocked ica.* services and creates fake list entities."""

    hass: HomeAssistant
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    responses: dict[str, Any] = field(default_factory=dict)

    def add_list(self, title: str, offline_id: str, items: int = 0) -> str:
        """Register a fake ICA list entity and return its entity_id."""
        registry = er.async_get(self.hass)
        entry = registry.async_get_or_create(
            "todo",
            ICA_DOMAIN,
            unique_id=f"{ICA_ENTRY_ID}-{offline_id}",
            suggested_object_id=f"ica_{title.lower().replace(' ', '_')}",
        )
        self.hass.states.async_set(
            entry.entity_id, str(items), {"friendly_name": f"ICA {title}"}
        )
        return entry.entity_id

    def calls_to(self, service: str) -> list[dict[str, Any]]:
        """Return the data of every call made to ica.<service>."""
        return [data for name, data in self.calls if name == service]


@pytest.fixture
def fake_ica(hass: HomeAssistant) -> FakeIca:
    """Register mocked ica services; set fake.responses[service] to customise."""
    fake = FakeIca(hass)

    def make_handler(name: str) -> Callable[[ServiceCall], Any]:
        async def handler(call: ServiceCall) -> Any:
            fake.calls.append((name, dict(call.data)))
            return fake.responses.get(name, {"success": True})

        return handler

    for name in (
        "create_shopping_list",
        "delete_shopping_list",
        "refresh_all",
        "upsert_shopping_list",
        "add_offers_to_shopping_list",
        "get_baseitems",
        "add_baseitem",
        "lookup_product",
        "get_recipe",
    ):
        hass.services.async_register(
            ICA_DOMAIN,
            name,
            make_handler(name),
            supports_response=SupportsResponse.OPTIONAL,
        )
    return fake


IcaConfigure = Callable[..., None]


@pytest.fixture
def ica_dependency(hass: HomeAssistant) -> Iterator[IcaConfigure]:
    """Fake the ha-ica-todo dependency. Nothing is faked until the result is called.

    Call it exactly once per test. With no arguments ICA is ready (v0.10.0, loaded);
    otherwise e.g. `ica_dependency(version="v0.9.0")`, `ica_dependency(installed=False)`
    or `ica_dependency(entry_state=None)` for "installed but not set up".
    """
    with ExitStack() as stack:
        configured = False

        def configure(
            *,
            installed: bool = True,
            version: str | None = "v0.10.0",
            entry_state: ConfigEntryState | None = ConfigEntryState.LOADED,
        ) -> None:
            nonlocal configured
            assert not configured, "configure the ICA dependency only once per test"
            configured = True
            if installed:
                manifest = {"version": version} if version is not None else {}
                find = AsyncMock(return_value=SimpleNamespace(manifest=manifest))
            else:
                find = AsyncMock(side_effect=IntegrationNotFound("ica"))
            stack.enter_context(
                patch("custom_components.inkop.dependency.async_get_integration", find)
            )
            if entry_state is not None:
                MockConfigEntry(domain=ICA_DOMAIN, state=entry_state).add_to_hass(hass)

        yield configure
