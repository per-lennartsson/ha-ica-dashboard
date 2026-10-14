"""Tests for the card resource decisions."""

from custom_components.handla.domain.resources import (
    ResourceAction,
    find_resources,
    plan_resource,
)

PATH = "/handla/handla-card.js"
URL = f"{PATH}?v=0.2.0"


def test_no_resources_means_create() -> None:
    assert plan_resource([], PATH, URL) == ResourceAction("create")


def test_other_resources_are_ignored() -> None:
    items = [{"id": "a", "url": "/hacsfiles/other-card.js", "type": "module"}]
    assert plan_resource(items, PATH, URL) == ResourceAction("create")


def test_same_url_is_left_alone() -> None:
    assert plan_resource([{"id": "a", "url": URL}], PATH, URL) == ResourceAction("none")


def test_an_entry_added_by_hand_without_query_is_left_alone() -> None:
    assert plan_resource([{"id": "a", "url": PATH}], PATH, URL) == ResourceAction(
        "none"
    )


def test_an_older_version_is_updated() -> None:
    items = [{"id": "a", "url": f"{PATH}?v=0.1.0"}]
    assert plan_resource(items, PATH, URL) == ResourceAction("update", "a")


def test_find_resources_ignores_the_query_string() -> None:
    items = [
        {"id": "a", "url": f"{PATH}?v=1"},
        {"id": "b", "url": PATH},
        {"id": "c", "url": "/other.js"},
        {"id": "d"},
    ]
    assert [item["id"] for item in find_resources(items, PATH)] == ["a", "b"]
