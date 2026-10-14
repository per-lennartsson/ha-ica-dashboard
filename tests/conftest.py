"""Shared fixtures: a fake ICA integration (todo entities + ica services)."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
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
    """Fakes ha-ica-todo: list entities, ica.* services and the lists-changed event."""

    hass: HomeAssistant
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    responses: dict[str, Any] = field(default_factory=dict)
    handlers: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = field(
        default_factory=dict
    )

    def add_list(
        self,
        title: str,
        offline_id: str,
        items: int = 0,
        comment: str | None = None,
    ) -> str:
        """Register a fake ICA list entity (as v0.10.0 exposes it)."""
        registry = er.async_get(self.hass)
        entry = registry.async_get_or_create(
            "todo",
            ICA_DOMAIN,
            unique_id=f"{ICA_ENTRY_ID}-{offline_id}",
            suggested_object_id=f"ica_{title.lower().replace(' ', '_')}",
            original_name=f"ICA {title}",
        )
        self.hass.states.async_set(
            entry.entity_id,
            str(items),
            {
                "friendly_name": f"ICA {title}",
                "offline_id": offline_id,
                "config_entry_id": ICA_ENTRY_ID,
                "comment": comment,
            },
        )
        return entry.entity_id

    def remove_list(self, entity_id: str) -> None:
        """Remove a fake list entity completely."""
        er.async_get(self.hass).async_remove(entity_id)
        self.hass.states.async_remove(entity_id)

    def fire_lists_changed(
        self,
        created: list[str] | None = None,
        deleted: list[str] | None = None,
        entities: dict[str, str] | None = None,
    ) -> None:
        """Fire ica_lists_changed like ha-ica-todo v0.10.0 does after a reload."""
        self.hass.bus.async_fire(
            "ica_lists_changed",
            {
                "config_entry_id": ICA_ENTRY_ID,
                "created": created or [],
                "deleted": deleted or [],
                "entities": entities or {},
            },
        )

    def install_create(
        self,
        offline_id: str = "NEW-1",
        *,
        fire: bool = True,
        include_entity: bool = True,
        early: bool = False,
        gate: asyncio.Event | None = None,
    ) -> None:
        """Make ica.create_shopping_list add a list and (optionally) fire the event.

        `early` fires before the service returns; otherwise right after, like the
        real background reload. `gate` blocks the service until it is set.
        """

        async def handler(data: dict[str, Any]) -> dict[str, Any]:
            if gate is not None:
                await gate.wait()
            entity_id = self.add_list(data["title"], offline_id)
            payload = {offline_id: entity_id} if include_entity else {}

            async def later() -> None:
                await asyncio.sleep(0)
                self.fire_lists_changed(created=[offline_id], entities=payload)

            if fire and early:
                self.fire_lists_changed(created=[offline_id], entities=payload)
            elif fire:
                self.hass.async_create_task(later())
            return {
                "success": True,
                "offline_id": offline_id,
                "title": data["title"],
                "tracked": True,
            }

        self.handlers["create_shopping_list"] = handler

    def install_delete(self, *, fire: bool = True) -> None:
        """Make ica.delete_shopping_list remove the list and (optionally) fire."""

        async def handler(data: dict[str, Any]) -> dict[str, Any]:
            entity_id = data["entity_id"]
            state = self.hass.states.get(entity_id)
            offline_id = state.attributes["offline_id"] if state else "?"
            self.remove_list(entity_id)

            async def later() -> None:
                await asyncio.sleep(0)
                self.fire_lists_changed(deleted=[offline_id])

            if fire:
                self.hass.async_create_task(later())
            return {"success": True, "entity_id": entity_id, "offline_id": offline_id}

        self.handlers["delete_shopping_list"] = handler

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
            if name in fake.handlers:
                return await fake.handlers[name](dict(call.data))
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


IcaConfigure = Callable[..., MockConfigEntry | None]


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
        ) -> MockConfigEntry | None:
            nonlocal configured
            assert not configured, "configure the ICA dependency only once per test"
            configured = True
            if installed:
                manifest = {"version": version} if version is not None else {}
                find = AsyncMock(return_value=SimpleNamespace(manifest=manifest))
            else:
                find = AsyncMock(side_effect=IntegrationNotFound("ica"))
            stack.enter_context(
                patch("custom_components.handla.dependency.async_get_integration", find)
            )
            if entry_state is None:
                return None
            entry = MockConfigEntry(
                domain=ICA_DOMAIN, state=entry_state, entry_id=ICA_ENTRY_ID
            )
            entry.add_to_hass(hass)
            return entry

        yield configure


@pytest.fixture(autouse=True)
def mock_storage(hass_storage: dict[str, Any]) -> dict[str, Any]:
    """Keep Store writes in memory for every test."""
    return hass_storage


async def setup_handla(
    hass: HomeAssistant, options: dict[str, Any] | None = None
) -> MockConfigEntry:
    """Add and set up an Handla config entry (ICA must be faked first)."""
    entry = MockConfigEntry(domain="handla", options=options or {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


class FakeTodo:
    """In-memory stand-in for Home Assistant's todo.* entity services.

    Mirrors the real shapes: get_items answers {entity_id: {"items": [...]}} and
    update_item / remove_item accept an item uid or its exact summary.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.lists: dict[str, list[dict[str, str]]] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._next = 0
        for name in (
            "get_items",
            "add_item",
            "update_item",
            "remove_item",
            "remove_completed_items",
        ):
            hass.services.async_register(
                "todo",
                name,
                self._make(name),
                supports_response=(
                    SupportsResponse.ONLY
                    if name == "get_items"
                    else SupportsResponse.NONE
                ),
            )

    def seed(self, entity_id: str, summary: str, *, completed: bool = False) -> str:
        """Put an item on a list and return its uid."""
        self._next += 1
        uid = f"uid-{self._next}"
        self.lists.setdefault(entity_id, []).append(
            {
                "uid": uid,
                "summary": summary,
                "status": "completed" if completed else "needs_action",
            }
        )
        return uid

    def summaries(self, entity_id: str) -> list[str]:
        """Summaries on a list, in order."""
        return [i["summary"] for i in self.lists.get(entity_id, [])]

    def status_of(self, entity_id: str, uid: str) -> str:
        """Status of one item."""
        return next(i["status"] for i in self.lists[entity_id] if i["uid"] == uid)

    def _find(self, entity_id: str, key: str) -> dict[str, str]:
        for item in self.lists.get(entity_id, []):
            if key in (item["uid"], item["summary"]):
                return item
        raise ServiceValidationError(f"Unable to find to-do list item: {key}")

    def _make(self, name: str) -> Callable[[ServiceCall], Any]:
        async def handler(call: ServiceCall) -> Any:
            data = dict(call.data)
            self.calls.append((name, data))
            entity_id = data["entity_id"]
            if isinstance(entity_id, list):
                entity_id = entity_id[0]
            items = self.lists.setdefault(entity_id, [])
            if name == "get_items":
                return {entity_id: {"items": [dict(i) for i in items]}}
            if name == "add_item":
                self.seed(entity_id, data["item"])
            elif name == "update_item":
                item = self._find(entity_id, data["item"])
                if "status" in data:
                    item["status"] = data["status"]
                if "rename" in data:
                    item["summary"] = data["rename"]
            elif name == "remove_item":
                for key in data["item"]:
                    items.remove(self._find(entity_id, key))
            elif name == "remove_completed_items":
                items[:] = [i for i in items if i["status"] != "completed"]
            return None

        return handler

    def calls_to(self, service: str) -> list[dict[str, Any]]:
        """Data of every call to todo.<service>."""
        return [data for name, data in self.calls if name == service]


@pytest.fixture
def fake_todo(hass: HomeAssistant) -> FakeTodo:
    """Fake todo.* services (the real todo integration is not set up in tests)."""
    return FakeTodo(hass)
