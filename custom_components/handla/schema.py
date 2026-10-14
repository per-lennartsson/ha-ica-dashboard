"""Schema library used by Home Assistant: probatio (2026.10+), else voluptuous."""

try:
    import probatio as vol
except ImportError:  # pragma: no cover - older Home Assistant
    import voluptuous as vol  # type: ignore[no-redef]

__all__ = ["vol"]
