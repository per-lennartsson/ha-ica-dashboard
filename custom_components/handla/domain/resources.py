"""Deciding what to do with the card's Lovelace resource (no Home Assistant imports)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ResourceAction:
    """What to do with the stored resources: nothing, create one, or update one."""

    kind: Literal["none", "create", "update"]
    item_id: str | None = None


def _path(url: str) -> str:
    return url.split("?", 1)[0]


def find_resources(
    items: Iterable[Mapping[str, Any]], path: str
) -> list[Mapping[str, Any]]:
    """The stored resources that point at `path`, whatever their query string."""
    return [item for item in items if _path(str(item.get("url", ""))) == path]


def plan_resource(
    items: Iterable[Mapping[str, Any]], path: str, url: str
) -> ResourceAction:
    """Decide how to make `url` (path plus ?v=version) a stored resource.

    An entry added by hand without a query string is left alone; one carrying a
    different version is updated so browsers fetch the new build.
    """
    found = find_resources(items, path)
    if not found:
        return ResourceAction("create")
    current = str(found[0].get("url", ""))
    if "?" in current and current != url:
        return ResourceAction("update", str(found[0].get("id")))
    return ResourceAction("none")
