"""Tests for usage statistics and icons."""

import pytest

from custom_components.handla.domain import (
    DEFAULT_ICON,
    DEFAULT_QUICK_ITEMS,
    MAX_TRACKED,
    MIN_QUICK_ITEMS,
    UsageEntry,
    UsageError,
    add_entry,
    aliases_from_json,
    aliases_to_json,
    entries_from_json,
    entries_to_json,
    icon_for,
    merge_entries,
    quick_add_payload,
    record_use,
    remove_entry,
    top_items,
    top_payload,
)


def test_first_use_creates_an_entry() -> None:
    result = record_use({}, "Mjölk", "2026-10-14T10:00:00")
    assert result == {"mjölk": UsageEntry("Mjölk", 1, "2026-10-14T10:00:00")}


def test_repeated_use_counts_case_insensitively_and_keeps_latest_spelling() -> None:
    entries = record_use({}, "Mjölk", "2026-10-14T10:00:00")
    entries = record_use(entries, "  mjölk ", "2026-10-15T10:00:00")
    entries = record_use(entries, "MJÖLK", "2026-10-16T10:00:00")
    assert entries == {"mjölk": UsageEntry("MJÖLK", 3, "2026-10-16T10:00:00")}


def test_inner_whitespace_is_collapsed() -> None:
    assert record_use({}, "gula   lökar", "t")["gula lökar"].name == "gula lökar"


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_names_are_ignored(name: str) -> None:
    assert record_use({}, name, "t") == {}


def test_record_use_does_not_modify_its_input() -> None:
    original: dict[str, UsageEntry] = {}
    record_use(original, "mjölk", "t")
    assert original == {}


def test_least_used_entries_are_dropped_over_the_limit() -> None:
    entries: dict[str, UsageEntry] = {}
    for number in range(MAX_TRACKED):
        entries = record_use(entries, f"vara {number:03}", f"2026-01-01T00:{number:04}")
    entries = record_use(entries, "mjölk", "2026-12-01T00:00:00")  # 1 use, newest
    entries = record_use(entries, "vara 007", "2026-12-02T00:00:00")  # now 2 uses
    assert len(entries) == MAX_TRACKED
    assert "vara 007" in entries
    assert "mjölk" in entries  # newest among the 1-use entries
    assert "vara 000" not in entries  # oldest of the 1-use entries


def test_top_items_by_count_then_recency_then_name() -> None:
    entries = {
        "a": UsageEntry("a", 3, "2026-01-01"),
        "b": UsageEntry("b", 5, "2026-01-01"),
        "c": UsageEntry("c", 3, "2026-02-01"),  # same count as a, more recent
        "d": UsageEntry("Å", 1, "2026-03-01"),
        "e": UsageEntry("B", 1, "2026-03-01"),  # same count and time as d: by name
    }
    assert [e.name for e in top_items(entries, 10)] == ["b", "c", "a", "B", "Å"]


def test_top_items_limit() -> None:
    entries = record_use(record_use({}, "a", "1"), "b", "2")
    assert len(top_items(entries, 1)) == 1
    assert top_items(entries, 0) == []
    assert top_items(entries, -3) == []
    assert top_items({}, 5) == []


def test_top_payload_has_name_count_and_icon() -> None:
    entries = record_use({}, "Mjölk", "t")
    assert top_payload(entries, 5) == [
        {"name": "Mjölk", "count": 1, "icon": "mdi:cow", "pinned": False}
    ]


def test_json_round_trip() -> None:
    entries = record_use(record_use({}, "Mjölk", "t1"), "ägg", "t2")
    assert entries_from_json(entries_to_json(entries)) == entries


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "x",
        {"a": "x"},
        {"a": {"name": "", "count": 1, "last_used": "t"}},
        {"a": {"name": "x", "count": 0, "last_used": "t"}},
        {"a": {"name": "x", "count": True, "last_used": "t"}},
        {"a": {"name": "x", "count": "2", "last_used": "t"}},
        {"a": {"name": "x", "count": 1}},
        {1: {"name": "x", "count": 1, "last_used": "t"}},
    ],
)
def test_malformed_stored_data_is_skipped(data: object) -> None:
    assert entries_from_json(data) == {}


def test_valid_entries_survive_next_to_broken_ones() -> None:
    data = {
        "ok": {"name": "ok", "count": 2, "last_used": "t"},
        "bad": {"name": "x"},
    }
    assert entries_from_json(data) == {"ok": UsageEntry("ok", 2, "t")}


@pytest.mark.parametrize(
    ("name", "icon"),
    [
        ("Mjölk", "mdi:cow"),
        ("havremjölk", "mdi:cow"),  # compound words match on their parts
        ("ägg", "mdi:egg"),
        ("Ost", "mdi:cheese"),
        ("Hushållspapper", "mdi:paper-roll"),
        ("nötfärs", "mdi:food-steak"),
        ("Lax", "mdi:fish"),
        ("kaffe", "mdi:coffee"),
        ("spaghetti", "mdi:pasta"),
        ("Äpplen", "mdi:food-apple"),
    ],
)
def test_icons_for_common_groceries(name: str, icon: str) -> None:
    assert icon_for(name) == icon


def test_unknown_items_get_the_default_icon() -> None:
    assert icon_for("xyzzy") == DEFAULT_ICON
    assert icon_for("") == DEFAULT_ICON


def test_quick_add_without_history_is_the_staples() -> None:
    items = quick_add_payload({}, 12)
    assert [i["name"] for i in items] == list(DEFAULT_QUICK_ITEMS)
    assert all(i["count"] == 0 for i in items)
    assert items[0] == {"name": "mjölk", "count": 0, "icon": "mdi:cow", "pinned": False}
    assert len(items) == MIN_QUICK_ITEMS


def test_quick_add_puts_real_items_first_and_fills_up_with_staples() -> None:
    entries = record_use(record_use({}, "ananas", "1"), "ananas", "2")
    items = quick_add_payload(entries, 12)
    assert items[0] == {
        "name": "ananas",
        "count": 2,
        "icon": DEFAULT_ICON,
        "pinned": False,
    }
    assert [i["name"] for i in items[1:]] == list(
        DEFAULT_QUICK_ITEMS[: MIN_QUICK_ITEMS - 1]
    )
    assert len(items) == MIN_QUICK_ITEMS


def test_quick_add_never_repeats_a_real_item_among_the_staples() -> None:
    entries = record_use({}, "MJÖLK", "1")
    names = [i["name"] for i in quick_add_payload(entries, 12)]
    assert names.count("MJÖLK") == 1
    assert "mjölk" not in names
    assert len(names) == MIN_QUICK_ITEMS


def test_quick_add_needs_no_staples_with_enough_history() -> None:
    entries: dict[str, UsageEntry] = {}
    for number in range(MIN_QUICK_ITEMS):
        entries = record_use(entries, f"vara {number}", f"2026-01-0{number + 1}")
    items = quick_add_payload(entries, 12)
    assert len(items) == MIN_QUICK_ITEMS
    assert all(i["count"] == 1 for i in items)


def test_quick_add_respects_the_limit() -> None:
    assert len(quick_add_payload({}, 3)) == 3
    assert quick_add_payload({}, 0) == []


def test_quick_add_with_a_higher_minimum() -> None:
    assert len(quick_add_payload({}, 12, minimum=3)) == 3


# --- managing the items: remove, merge, add (pinned) ---------------------------------


def _sample() -> dict[str, UsageEntry]:
    return {
        "tomat": UsageEntry("Tomat", 2, "2026-01-02"),
        "tomater": UsageEntry("Tomater", 5, "2026-01-01"),
        "mjölk": UsageEntry("Mjölk", 9, "2026-01-03"),
    }


def test_remove_forgets_the_item_and_aliases_pointing_to_it() -> None:
    entries, aliases = remove_entry(
        _sample(), {"tomatt": "tomater", "x": "mjölk"}, "TOMATER"
    )
    assert set(entries) == {"tomat", "mjölk"}
    assert aliases == {"x": "mjölk"}


def test_remove_through_an_alias_removes_the_target() -> None:
    entries, aliases = remove_entry(_sample(), {"tomatt": "tomater"}, "tomatt")
    assert "tomater" not in entries
    assert aliases == {}


def test_remove_unknown_item_fails() -> None:
    with pytest.raises(UsageError) as err:
        remove_entry(_sample(), {}, "smör")
    assert err.value.key == "quick_item_unknown"


def test_merge_sums_counts_and_keeps_chosen_name() -> None:
    sample = _sample()
    entries, aliases = merge_entries(sample, {}, ["Tomat", "tomater"], "Tomater")
    assert entries["tomater"] == UsageEntry("Tomater", 7, "2026-01-02")
    assert "tomat" not in entries
    assert aliases == {"tomat": "tomater"}
    assert "tomat" in sample  # input untouched


def test_merge_into_a_new_name() -> None:
    entries, aliases = merge_entries(
        _sample(), {}, ["tomat", "tomater"], "Tomater (burk)"
    )
    assert entries["tomater (burk)"].count == 7
    assert aliases == {"tomat": "tomater (burk)", "tomater": "tomater (burk)"}


def test_merge_includes_an_existing_item_with_the_target_name() -> None:
    entries, aliases = merge_entries(_sample(), {}, ["tomat"], "Tomater")
    assert entries["tomater"].count == 7
    assert aliases == {"tomat": "tomater"}


def test_merge_retargets_older_aliases_and_keeps_pins() -> None:
    sample = _sample()
    sample["tomat"] = UsageEntry("Tomat", 2, "2026-01-02", pinned=True)
    entries, aliases = merge_entries(
        sample, {"tomatt": "tomat"}, ["tomat", "tomater"], "Tomater"
    )
    assert entries["tomater"].pinned is True
    assert aliases == {"tomatt": "tomater", "tomat": "tomater"}


def test_merge_validates() -> None:
    with pytest.raises(UsageError) as blank:
        merge_entries(_sample(), {}, ["tomat"], "  ")
    assert blank.value.key == "quick_item_blank"
    with pytest.raises(UsageError) as empty:
        merge_entries(_sample(), {}, [], "Tomater")
    assert empty.value.key == "quick_item_blank"
    with pytest.raises(UsageError) as unknown:
        merge_entries(_sample(), {}, ["tomat", "smör"], "Tomater")
    assert unknown.value.key == "quick_item_unknown"


def test_record_use_through_an_alias_counts_the_target_and_keeps_its_name() -> None:
    entries = record_use(_sample(), "TOMAT", "2026-02-01", {"tomat": "tomater"})
    assert entries["tomater"] == UsageEntry("Tomater", 6, "2026-02-01")
    assert entries["tomat"].count == 2  # untouched here: the alias is only a pointer


def test_add_creates_a_pinned_item() -> None:
    entries, aliases = add_entry({}, {}, " Toalettpapper ", "t")
    assert entries == {
        "toalettpapper": UsageEntry("Toalettpapper", 1, "t", pinned=True)
    }
    assert aliases == {}


def test_add_pins_an_existing_or_aliased_item() -> None:
    entries, _ = add_entry(_sample(), {}, "mjölk", "t")
    assert entries["mjölk"] == UsageEntry("Mjölk", 9, "2026-01-03", pinned=True)
    entries, _ = add_entry(_sample(), {"tomatt": "tomater"}, "Tomatt", "t")
    assert entries["tomater"].pinned is True
    assert "tomatt" not in entries


def test_add_blank_fails() -> None:
    with pytest.raises(UsageError):
        add_entry({}, {}, "  ", "t")


def test_pinned_items_come_first_and_survive_trimming() -> None:
    entries = {
        "a": UsageEntry("a", 9, "2026-01-01"),
        "b": UsageEntry("b", 1, "2026-01-01", pinned=True),
    }
    assert [e.name for e in top_items(entries, 5)] == ["b", "a"]
    assert top_payload(entries, 1)[0]["pinned"] is True
    many: dict[str, UsageEntry] = {"pin": UsageEntry("pin", 1, "0", pinned=True)}
    for number in range(MAX_TRACKED):
        many = record_use(many, f"vara {number:03}", f"2026-01-01T00:{number:04}")
    assert "pin" in many
    assert len(many) == MAX_TRACKED


def test_pinned_and_aliases_round_trip_through_json() -> None:
    entries = {"a": UsageEntry("A", 2, "t", pinned=True), "b": UsageEntry("B", 1, "t")}
    stored = entries_to_json(entries)
    assert "pinned" not in stored["b"]
    assert entries_from_json(stored) == entries
    assert aliases_from_json(aliases_to_json({"x": "a"})) == {"x": "a"}
    assert aliases_from_json({"x": "x", "": "a", "y": 3, 4: "a"}) == {}
    assert aliases_from_json(None) == {}
