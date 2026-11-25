"""The order of builds and of names (design 12 V2, 02 X4). Nothing sorts by GitHub's order or by file times."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tlaup.versioning.store import Build

ROLLING = "rolling"

_NUMBER = re.compile(r"v?([0-9]+(?:\.[0-9]+)*)(.*)", re.DOTALL)

VersionKey = tuple[tuple[int, ...], int, str]


def version_key(tag: str) -> VersionKey | None:
    """``((1, 7, 4), suffix_rank, suffix)``, or None if the tag is not a number.

    The number is read as integers with an optional suffix; a tag without a suffix ranks above
    the same number with one, so ``v1.5.0rc1`` sorts below ``v1.5.0``.
    """
    match = _NUMBER.fullmatch(tag)
    if match is None:
        return None
    numbers = tuple(int(part) for part in match.group(1).split("."))
    suffix = match.group(2)
    return numbers, 0 if suffix else 1, suffix


@total_ordering
@dataclass(frozen=True)
class _Descending:
    """Wraps a value so that an ascending sort puts the highest first."""

    value: VersionKey | str

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, _Descending):
            return NotImplemented
        return bool(self.value > other.value)  # type: ignore[operator]


def name_key(tag: str) -> tuple[object, ...]:
    """The order of names, ascending: ``rolling``, then numbers highest first, then other names by name.

    A function of the tag alone, so that releases (package 25) sort by the same rule as builds.
    """
    if tag == ROLLING:
        return (0, tag)
    key = version_key(tag)
    if key is not None:
        return (1, _Descending(key), tag)
    return (2, tag)


def sort_key(build: Build) -> tuple[object, ...]:
    """Rolling first, then version number descending, then build time newest first.

    A build with no build time sorts after those of its name that have one, then by install
    time, newest first. The id only makes the order total.
    """
    return (
        name_key(build.name),
        0 if build.calver is not None else 1,
        _Descending(build.calver or ""),
        _Descending(build.installed_at),
        build.id,
    )
