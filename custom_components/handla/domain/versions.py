"""Version parsing and comparison (no external dependencies)."""

import re

_VERSION_RE = re.compile(r"^\s*[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    """Parse "v0.10.0", "0.10" or "1.2.3-beta" into (major, minor, patch).

    A leading "v" is ignored, missing parts count as 0 and any suffix is dropped.
    Returns None when the text does not start with a number.
    """
    if not text:
        return None
    match = _VERSION_RE.match(text)
    if not match:
        return None
    major, minor, patch = (int(part) if part else 0 for part in match.groups())
    return major, minor, patch


def is_version_at_least(version: str | None, minimum: str) -> bool:
    """True if `version` is parseable and not older than `minimum`."""
    parsed = parse_version(version)
    wanted = parse_version(minimum)
    if wanted is None:
        raise ValueError(f"Invalid minimum version: {minimum!r}")
    return parsed is not None and parsed >= wanted
