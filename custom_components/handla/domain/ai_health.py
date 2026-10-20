"""Pure rules for telling people the AI provider is failing, without nagging."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

# While the provider keeps failing, remind at most this often
RENOTIFY_AFTER = timedelta(hours=24)
MAX_ERROR_LENGTH = 200

# Translation keys (under `exceptions` in strings.json) of the message templates
AI_FAILURE_TITLE = "ai_failure_title"
AI_FAILURE_MESSAGE = "ai_failure_message"
AI_FAILURE_KEYS = (AI_FAILURE_TITLE, AI_FAILURE_MESSAGE)


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


def build_failure_message(templates: Mapping[str, str], error: str) -> tuple[str, str]:
    """Title and text of the "AI provider failed" notification.

    The text template uses {error}; see AI_FAILURE_KEYS.
    """
    detail = " ".join(error.split())
    if len(detail) > MAX_ERROR_LENGTH:
        detail = detail[: MAX_ERROR_LENGTH - 1].rstrip() + "…"
    return (
        templates[AI_FAILURE_TITLE],
        templates[AI_FAILURE_MESSAGE].format(error=detail),
    )
