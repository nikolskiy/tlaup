"""X3's round trip: every printed form finds exactly the build it was printed for (design 02 X3, T7).

The stores are made with ``ToolStore.add`` on a jar file and a ``JarInfo`` of the test's own,
so that commits, build times and digests come from small pools and collide often.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from hypothesis import event, given
from hypothesis import strategies as st

from tests.clock import FakeClock
from tests.unit.versioning.conftest import SOURCE
from tlaup.paths import AppPaths
from tlaup.versioning.jarinfo import JarInfo
from tlaup.versioning.spec import format_build, parse_version_spec
from tlaup.versioning.store import ToolStore

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_CALVER = re.compile(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]{6}")
_FIXED_NAMES = ["rolling", "v1.7.4", "1.7.4", "v1.8.0", "a-b", "a_b", "a/b", ".x", "v1.9+b", "release/1.9"]

names = st.one_of(
    st.sampled_from(_FIXED_NAMES[:2]),  # most builds share a name with another, so the rows meet
    st.sampled_from(_FIXED_NAMES),
    st.from_regex(r"[A-Za-z0-9._/+][A-Za-z0-9._/+-]{0,6}", fullmatch=True),
).filter(lambda name: name not in {"stable", "latest"} and not _CALVER.fullmatch(name))
commits = st.sampled_from(
    [None, "bc1b506" + "0" * 33, "bc1b506" + "1" * 33, "bc1b5061" + "2" * 32, "5a47802" + "3" * 33, "a" * 39 + "4"]
)
build_times = st.sampled_from([None, "2026.11.15.002146", "2026.11.16.090000", "2026.11.17.000001"])
digests = st.sampled_from(
    ["7e53aa636dac" + digit * 52 for digit in "0123"] + ["7e53aa636da" + digit * 53 for digit in "ef"] + ["f" * 64]
)
entry = st.tuples(names, commits, build_times, digests)
stores = st.lists(entry, max_size=8, unique_by=lambda item: (item[0], item[3]))


def make_store(root: Path, entries: list[tuple[str, str | None, str | None, str]]) -> ToolStore:
    store = ToolStore(AppPaths(config=root / "config", cache=root / "cache", data=root / "data"), now=FakeClock().now)
    with store.locked(timeout=0):
        for name, commit, calver, digest in entries:
            tmp = store.new_tmp()
            tmp.lock()
            tmp.make()
            jar = tmp.path / "tla2tools.jar"
            jar.write_bytes(digest.encode())
            built_at = None if calver is None else f"{calver} as written"
            info = JarInfo(digest, len(digest), commit, built_at, calver, frozenset())
            store.add(jar, info, name=name, prerelease=False, source=SOURCE)
            tmp.release()
    return store


@given(entries=stores)
def test_every_printed_form_finds_exactly_its_build(
    entries: list[tuple[str, str | None, str | None, str]], tmp_path_factory: pytest.TempPathFactory
) -> None:
    store = make_store(tmp_path_factory.mktemp("store"), entries)
    builds = store.builds()
    assert len(builds) == len(entries)
    for build in builds:
        printed = format_build(build, builds)
        event(_row(printed))
        assert store.find(parse_version_spec(printed)) == [build], printed


def _row(printed: str) -> str:
    _, at, after = printed.partition("@")
    if not at:
        return "bare name"
    if after.startswith("sha256:"):
        return "name@sha256:" + ("12 digits" if len(after) == 19 else "more than 12 digits")
    if _CALVER.fullmatch(after):
        return "name@calver"
    return "name@commit, " + ("7 digits" if len(after) == 7 else "more than 7 digits")
