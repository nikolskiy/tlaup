"""``format_build``, one test per row of the printing table (design 02 X3)."""

from __future__ import annotations

from tests.unit.versioning.conftest import commit, make_build
from tlaup.versioning.spec import format_build

CALVER = "2026.11.15.002146"
DIGEST = "7e53aa636dac" + "1" * 52


def test_a_commit_no_other_build_of_the_name_has() -> None:
    build = make_build("rolling", "a", commit=commit("bc1b506"), calver=CALVER)
    other = make_build("rolling", "b", commit=commit("5a47802"))
    assert format_build(build) == "rolling@bc1b506"
    assert format_build(build, [build, other]) == "rolling@bc1b506"


def test_two_commits_that_share_seven_digits_grow_the_prefix() -> None:
    build = make_build("rolling", "a", commit=commit("bc1b506a"))
    other = make_build("rolling", "b", commit=commit("bc1b506b"))
    assert format_build(build, [build, other]) == "rolling@bc1b506a"
    assert format_build(other, [build, other]) == "rolling@bc1b506b"


def test_commits_that_differ_only_in_the_last_digit_print_in_full() -> None:
    build = make_build("rolling", "a", commit="a" * 39 + "1")
    other = make_build("rolling", "b", commit="a" * 39 + "2")
    assert format_build(build, [build, other]) == "rolling@" + "a" * 39 + "1"


def test_only_builds_of_the_same_name_are_looked_at() -> None:
    build = make_build("rolling", "a", commit=commit("bc1b506a"))
    other = make_build("v1.8.0", "b", commit=commit("bc1b506a"))
    assert format_build(build, [build, other]) == "rolling@bc1b506"


def test_two_builds_of_one_commit_print_their_build_time() -> None:
    build = make_build("rolling", "a", commit=commit("bc1b506"), calver=CALVER)
    other = make_build("rolling", "b", commit=commit("bc1b506"), calver="2026.11.16.090000")
    assert format_build(build, [build, other]) == f"rolling@{CALVER}"


def test_a_build_with_no_commit_and_a_build_time_beside_another() -> None:
    build = make_build("rolling", "a", calver=CALVER)
    other = make_build("rolling", "b", commit=commit("bc1b506"))
    assert format_build(build, [build, other]) == f"rolling@{CALVER}"
    assert format_build(other, [build, other]) == "rolling@bc1b506"


def test_the_only_build_of_its_name_with_neither_is_the_bare_name() -> None:
    build = make_build("v1.6.0", "a")
    other = make_build("rolling", "b")
    assert format_build(build) == "v1.6.0"
    assert format_build(build, [build, other]) == "v1.6.0"


def test_two_builds_of_one_name_and_commit_with_no_build_time_print_the_digest() -> None:
    build = make_build("v1.6.0", "a", commit=commit("1234567"), sha256=DIGEST)
    other = make_build("v1.6.0", "b", commit=commit("1234567"), sha256="2" * 64)
    assert format_build(build, [build, other]) == "v1.6.0@sha256:7e53aa636dac"


def test_two_digests_that_share_twelve_digits_grow_the_prefix() -> None:
    build = make_build("v1.6.0", "a", sha256="7e53aa636dac" + "1" * 52)
    other = make_build("v1.6.0", "b", sha256="7e53aa636dac" + "2" * 52)
    assert format_build(build, [build, other]) == "v1.6.0@sha256:7e53aa636dac1"


def test_a_build_with_no_commit_beside_another_build_of_its_name() -> None:
    build = make_build("v1.6.0", "a", sha256=DIGEST)
    other = make_build("v1.6.0", "b", commit=commit("1234567"), sha256="2" * 64)
    assert format_build(build, [build, other]) == "v1.6.0@sha256:7e53aa636dac"
    assert format_build(other, [build, other]) == "v1.6.0@1234567"
