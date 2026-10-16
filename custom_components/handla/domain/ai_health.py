"""Pure rules for telling people the AI provider is failing, without nagging."""

from dataclasses import dataclass
from datetime import datetime, timedelta

# While the provider keeps failing, remind at most this often
RENOTIFY_AFTER = timedelta(hours=24)
MAX_ERROR_LENGTH = 200


@dataclass(frozen=True)
class AiHealth:
    """When the provider started failing and when people were last told."""

    failing_since: datetime | None = None
    last_notified: datetime | None = None


def record_failure(health: AiHealth, now: datetime) -> tuple[AiHealth, bool]:
    """The new state, and whether to notify now.

    The first failure notifies. Further failures stay quiet until the provider has
    worked again, or until RENOTIFY_AFTER has passed.
    """
    due = health.last_notified is None or now - health.last_notified >= RENOTIFY_AFTER
    return (
        AiHealth(
            failing_since=health.failing_since or now,
            last_notified=now if due else health.last_notified,
        ),
        due,
    )


def record_success(health: AiHealth) -> AiHealth:
    """A call worked: forget the failure, so the next one notifies again."""
    return AiHealth()


def build_failure_message(language: str, error: str) -> tuple[str, str]:
    """Title and text of the "AI provider failed" notification."""
    detail = " ".join(error.split())
    if len(detail) > MAX_ERROR_LENGTH:
        detail = detail[: MAX_ERROR_LENGTH - 1].rstrip() + "…"
    if language.casefold().startswith("sv"):
        return (
            "Handla: AI fungerar inte",
            f"AI-leverantören svarar med fel: {detail} "
            "Lägg till från text är inte tillgängligt förrän det är löst.",
        )
    return (
        "Handla: AI is not working",
        f"The AI provider reports an error: {detail} "
        "Add from text is not available until it is fixed.",
    )
