"""Tests for version parsing and comparison."""

import pytest

from custom_components.inkop.domain import is_version_at_least, parse_version


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("v0.10.0", (0, 10, 0)),
        ("0.10.0", (0, 10, 0)),
        ("V1.2.3", (1, 2, 3)),
        ("0.10", (0, 10, 0)),
        ("2", (2, 0, 0)),
        ("1.2.3-beta.1", (1, 2, 3)),
        ("  v1.0.0 ", (1, 0, 0)),
    ],
)
def test_parse_version(text: str, expected: tuple[int, int, int]) -> None:
    assert parse_version(text) == expected


@pytest.mark.parametrize("text", [None, "", "abc", "v", "latest"])
def test_unparseable_version_is_none(text: str | None) -> None:
    assert parse_version(text) is None


@pytest.mark.parametrize(
    ("version", "result"),
    [
        ("v0.10.0", True),
        ("0.10.0", True),
        ("v0.10.1", True),
        ("v0.11.0", True),
        ("v1.0.0", True),
        ("v0.9.0", False),
        ("v0.9.99", False),
        ("v0.2.0", False),  # numeric, not string, comparison
        ("garbage", False),
        (None, False),
    ],
)
def test_is_version_at_least(version: str | None, result: bool) -> None:
    assert is_version_at_least(version, "0.10.0") is result


def test_invalid_minimum_raises() -> None:
    with pytest.raises(ValueError, match="Invalid minimum"):
        is_version_at_least("1.0.0", "x")
