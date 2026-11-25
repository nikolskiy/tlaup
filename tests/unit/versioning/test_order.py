"""The order of builds and the lookup among installed builds (design 12 V2, 02 X3, X4). No file times anywhere."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest

from tests.unit.versioning.conftest import commit, make_build, manifest
from tlaup.versioning.order import name_key, sort_key, version_key
from tlaup.versioning.spec import VersionSpec, parse_version_spec

if TYPE_CHECKING:
    from tests.clock import FakeClock
    from tests.unit.versioning.conftest import Downloads
    from tlaup.versioning.store import Build, ToolStore

ROLLING = commit("bc1b506")
OTHER = commit("bc1b507")
V174 = commit("5a47802")


# ---------------------------------------------------------------------- names


@pytest.mark.parametrize(
    ("tag", "key"),
    [
        ("v1.7.4", ((1, 7, 4), 1, "")),
        ("1.7.4", ((1, 7, 4), 1, "")),
        ("v1.5.0rc1", ((1, 5, 0), 0, "rc1")),
        ("v1.10", ((1, 10), 1, "")),
        ("rolling", None),
        ("release/1.9", None),
        ("", None),
    ],
)
def test_version_key(tag: str, key: object) -> None:
    assert version_key(tag) == key


def test_names_sort_rolling_then_numbers_highest_first_then_other_names() -> None:
    expected = ["rolling", "v1.10.0", "v1.8.0", "v1.7.4", "v1.5.0", "v1.5.0rc2", "v1.5.0rc1", "alpha", "nightly"]
    for seed in range(20):
        shuffled = expected[:]
        random.Random(seed).shuffle(shuffled)
        assert sorted(shuffled, key=name_key) == expected


def test_rolling_sorts_above_every_numbered_name() -> None:
    assert sorted(["v99.0.0", "rolling"], key=name_key) == ["rolling", "v99.0.0"]


# ---------------------------------------------------------------------- builds


def test_builds_of_one_name_by_build_time_then_install_time() -> None:
    newest = make_build("rolling", "a", calver="2026.11.16.090000", installed_at="2026-11-01T00:00:00Z")
    older = make_build("rolling", "b", calver="2026.11.15.002146", installed_at="2026-11-20T00:00:00Z")
    no_time_late = make_build("rolling", "c", installed_at="2026-11-19T00:00:00Z")
    no_time_early = make_build("rolling", "d", installed_at="2026-11-18T00:00:00Z")
    expected = [newest, older, no_time_late, no_time_early]
    for seed in range(20):
        shuffled = expected[:]
        random.Random(seed).shuffle(shuffled)
        assert sorted(shuffled, key=sort_key) == expected


def test_builds_sort_by_name_first() -> None:
    other = make_build("nightly", "n", calver="2027.01.01.000000")
    old = make_build("v1.7.4", "o")
    rolling = make_build("rolling", "r", calver="2020.01.01.000000")
    v180 = make_build("v1.8.0", "v", calver="2026.11.15.002146")
    assert sorted([other, old, v180, rolling], key=sort_key) == [rolling, v180, old, other]


def test_the_store_lists_builds_in_this_order(downloads: Downloads, store: ToolStore, clock: FakeClock) -> None:
    v174 = downloads.add(manifest(V174), "v1.7.4", prerelease=False)
    clock.advance(1)
    v174_again = downloads.add(manifest(V174, extra="later"), "v1.7.4", prerelease=False)
    old = downloads.add(manifest(ROLLING, "2026-11-15T00:21:46Z"), "rolling")
    new = downloads.add(manifest(OTHER, "2026-11-16T00:00:00Z"), "rolling")
    assert store.builds() == [new, old, v174_again, v174]


# ---------------------------------------------------------------------- find


@pytest.fixture
def installed(downloads: Downloads) -> dict[str, Build]:
    """Two rolling builds of one commit, a v1.8.0 of the same jar, two releases and a build with no commit."""
    return {
        "rolling-new": downloads.add(manifest(ROLLING, "2026-11-16T00:00:00Z"), "rolling"),
        "rolling-old": downloads.add(manifest(ROLLING, "2026-11-15T00:21:46Z"), "rolling"),
        "v1.8.0": downloads.add(manifest(ROLLING, "2026-11-16T00:00:00Z"), "v1.8.0", prerelease=True),
        "v1.7.4": downloads.add(manifest(V174), "v1.7.4", prerelease=False),
        "v1.6.0": downloads.add(manifest(commit("1234567")), "v1.6.0", prerelease=False),
        "nocommit": downloads.add(manifest(None), "v1.5.0", prerelease=False),
    }


def find(store: ToolStore, text: str) -> list[Build]:
    return list(store.find(parse_version_spec(text)))


def test_a_tag_as_typed_and_with_v(store: ToolStore, installed: dict[str, Build]) -> None:
    assert find(store, "v1.7.4") == [installed["v1.7.4"]]
    assert find(store, "1.7.4") == [installed["v1.7.4"]]


def test_a_tag_as_typed_comes_before_the_v_form(store: ToolStore, downloads: Downloads) -> None:
    bare = downloads.add(manifest(V174), "1.7.4")
    with_v = downloads.add(manifest(V174), "v1.7.4")
    assert find(store, "1.7.4") == [bare]
    assert find(store, "v1.7.4") == [with_v]


def test_stable_is_the_highest_numbered_name_that_is_not_a_prerelease(
    store: ToolStore, installed: dict[str, Build]
) -> None:
    assert find(store, "stable") == [installed["v1.7.4"]]
    assert find(store, "stable@5a47802") == [installed["v1.7.4"]]
    assert find(store, "stable@1234567") == []


def test_stable_is_empty_when_every_build_is_a_prerelease(store: ToolStore, downloads: Downloads) -> None:
    downloads.add(manifest(ROLLING), "v1.8.0", prerelease=True)
    downloads.add(manifest(ROLLING), "rolling", prerelease=True)
    assert find(store, "stable") == []


def test_stable_never_names_rolling_or_another_word(store: ToolStore, downloads: Downloads) -> None:
    downloads.add(manifest(ROLLING), "rolling", prerelease=False)
    downloads.add(manifest(ROLLING), "nightly", prerelease=False)
    assert find(store, "stable") == []


def test_rolling(store: ToolStore, installed: dict[str, Build]) -> None:
    assert find(store, "rolling") == [installed["rolling-new"], installed["rolling-old"]]


def test_a_commit_prefix_narrows(store: ToolStore, installed: dict[str, Build]) -> None:
    assert find(store, "rolling@bc1b506") == [installed["rolling-new"], installed["rolling-old"]]
    assert find(store, "v1.8.0@BC1B506") == [installed["v1.8.0"]]
    assert find(store, f"rolling@{ROLLING}") == [installed["rolling-new"], installed["rolling-old"]]
    assert find(store, "rolling@bc1b507") == []


def test_a_calver_narrows(store: ToolStore, installed: dict[str, Build]) -> None:
    assert find(store, "rolling@2026.11.15.002146") == [installed["rolling-old"]]


def test_a_sha256_prefix_narrows(store: ToolStore, installed: dict[str, Build]) -> None:
    old = installed["rolling-old"]
    assert find(store, f"rolling@sha256:{old.sha256[:12]}") == [old]
    assert find(store, f"v1.8.0@sha256:{old.sha256[:12]}") == []


def test_a_bare_calver_matches_across_names(store: ToolStore, installed: dict[str, Build]) -> None:
    assert find(store, "2026.11.16.000000") == [installed["rolling-new"], installed["v1.8.0"]]


def test_a_build_without_a_commit_matches_its_name_and_never_a_commit(
    store: ToolStore, installed: dict[str, Build]
) -> None:
    assert find(store, "v1.5.0") == [installed["nocommit"]]
    assert find(store, "v1.5.0@0000000") == []
    assert store.find(VersionSpec("v1.5.0", "", None, None)) == []


def test_nothing_matching_is_an_empty_list(store: ToolStore, installed: dict[str, Build]) -> None:
    assert find(store, "v9.9.9") == []
    assert find(store, "2020.01.01.000000") == []


def test_find_on_an_empty_store(store: ToolStore) -> None:
    assert find(store, "stable") == []
    assert find(store, "rolling") == []
