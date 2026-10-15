"""Rules for the optional AI module: is it usable, and is the choice valid."""

from enum import StrEnum


class AiStatus(StrEnum):
    """What the card needs to know: show AI UI only when ready."""

    OFF = "off"
    READY = "ready"
    UNAVAILABLE = "unavailable"


def ai_status(enabled: bool, provider_ready: bool) -> AiStatus:
    """Off when disabled; otherwise ready only while the chosen provider is usable."""
    if not enabled:
        return AiStatus.OFF
    return AiStatus.READY if provider_ready else AiStatus.UNAVAILABLE


def ai_choice_error(
    enabled: bool, entity_id: str | None, entity_exists: bool
) -> str | None:
    """Translation key of what is wrong with the options form, or None if it is fine.

    Turning AI off never fails, whatever entity is left in the form.
    """
    if not enabled:
        return None
    if not entity_id:
        return "ai_entity_required"
    if not entity_exists:
        return "ai_entity_unknown"
    return None
