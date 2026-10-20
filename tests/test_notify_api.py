"""Tests for the notify wrapper."""

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.handla.notify_api import async_notify_users


async def test_each_user_gets_the_message_and_a_failure_stops_no_one(
    hass: HomeAssistant, caplog: Any
) -> None:
    sent: list[tuple[str, dict[str, Any]]] = []

    def register(service: str, fail: bool = False) -> None:
        async def handler(call: ServiceCall) -> None:
            if fail:
                raise HomeAssistantError("phone off")
            sent.append((service, dict(call.data)))

        hass.services.async_register("notify", service, handler)

    register("mobile_app_a", fail=True)
    register("mobile_app_b")

    await async_notify_users(
        hass, {"u1": "mobile_app_a", "u2": "mobile_app_b"}, "Titel", "Text"
    )

    assert sent == [
        (
            "mobile_app_b",
            {"title": "Titel", "message": "Text", "data": {"tag": "handla"}},
        )
    ]
    assert "Could not notify user u1 through notify.mobile_app_a" in caplog.text
