"""``install()``, ``upgrade()``, ``uninstall()``, ``pin()`` and their steps (design 12 V1, V3, V4, V12).

On a real store in the test's folder, with small real jars, the real client and ``fetch_build``, and
``responses`` serving the ``releases`` recording (01 T4). Each test asserts state: the builds, the pin, the
report's fields and the number of requests and downloads, never wording (T12 rule 4).

Inventory rows: T2 (the first build is pinned; later installs never move a pin), T3 (a missing pin, or one
naming a gone folder, is nothing pinned), T4's ``install`` half (an empty pin file is nothing pinned), T40
(upgrade replaces the old build and moves the pin) and T41 (upgrade with nothing pinned is an error).
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import os
from typing import TYPE_CHECKING

import pytest

from tests.unit.versioning.conftest import SOURCE, commit, make_build, manifest, tmp_entries, with_jar
from tlaup.errors import (
    AmbiguousVersion,
    CannotAsk,
    DownloadVerificationError,
    FileOperationError,
    NetworkError,
    NoPinnedBuild,
    NoToolsInstalled,
    PinnedBuildMissing,
    UsageError,
    VersionNotFound,
)
from tlaup.ui import Ui
from tlaup.versioning.install import (
    Uninstall,
    choose_build,
    install,
    pin,
    same_as_published,
    uninstall,
    upgrade,
)
from tlaup.versioning.remote import Asset, Release
from tlaup.versioning.spec import parse_version_spec
from tlaup.versioning.store import ToolStore

if TYPE_CHECKING:
    from tests.clock import FakeClock
    from tests.conftest import Isolated
    from tests.unit.versioning.conftest import Downloads, Upstream
    from tlaup.versioning.install import InstallReport, UpgradeReport
    from tlaup.versioning.store import Build

ROLLING_CALVER = "2026.11.15.002146"  # the build time of the recorded rolling and v1.8.0 jars
ROLLING_COMMIT = "bc1b506"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(store: ToolStore, upstream: Upstream, text: str, *, force: bool = False) -> InstallReport:
    return install(store, upstream.remote, upstream.client, parse_version_spec(text), force=force)


def pin_text(isolated: Isolated) -> str | None:
    try:
        return isolated.paths.pin.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None


def unpin(store: ToolStore) -> None:
    with store.locked(timeout=0):
        store.unpin()


def truncate(build: Build) -> None:
    build.jar.write_bytes(build.jar.read_bytes()[:100])


# ---------------------------------------------------------------------- same_as_published


def release_with(digest: str | None, *, size: int = 10, updated_at: str = "2026-11-15T00:30:00Z") -> Release:
    asset = Asset(id=1, size=size, digest=digest, updated_at=updated_at, download_url="https://example.invalid/jar")
    return Release("rolling", prerelease=True, draft=False, created_at=updated_at, published_at=None, asset=asset)


BUILD = make_build("rolling", sha256="ab" * 32, size=10, source=SOURCE)  # SOURCE was uploaded 2026-11-15T00:30:00Z


def test_same_as_published_with_a_matching_digest() -> None:
    assert same_as_published(BUILD, release_with("sha256:" + "ab" * 32, size=99, updated_at="2020-01-01T00:00:00Z"))


def test_same_as_published_with_another_digest_is_false_even_with_equal_size_and_date() -> None:
    assert not same_as_published(BUILD, release_with("sha256:" + "cd" * 32))


def test_same_as_published_without_a_digest_compares_size_and_upload_time() -> None:
    assert same_as_published(BUILD, release_with(None))
    assert not same_as_published(BUILD, release_with(None, size=11))
    assert not same_as_published(BUILD, release_with(None, updated_at="2026-11-16T00:30:00Z"))


def test_same_as_published_reads_a_digest_in_upper_case() -> None:
    assert same_as_published(BUILD, release_with("SHA256:" + "AB" * 32, size=99))


def test_same_as_published_treats_a_digest_with_another_prefix_as_none() -> None:
    assert same_as_published(BUILD, release_with("sha512:" + "ef" * 64))
    assert not same_as_published(BUILD, release_with("sha512:" + "ab" * 32, size=11))


def test_same_as_published_is_false_for_a_release_without_the_jar() -> None:
    assert not same_as_published(BUILD, dataclasses.replace(release_with(None), asset=None))


# ---------------------------------------------------------------------- install, by row of V12's table


def test_not_installed_downloads_adds_and_pins(store: ToolStore, upstream: Upstream, isolated: Isolated) -> None:
    report = run(store, upstream, "rolling")
    assert report.downloaded
    assert not report.already_installed
    assert report.pinned
    assert report.could_not_check is None
    assert report.matches == ()
    assert [build.id for build in store.builds()] == [report.build.id]
    assert report.build.name == "rolling"
    assert report.build.sha256 == sha256(upstream.fake.jar("rolling").read_bytes())
    assert report.build.source.digest_checked
    assert pin_text(isolated) == report.build.id
    assert (upstream.tag_requests, upstream.downloads) == (1, 1)
    assert tmp_entries(store) == []


def test_installed_and_published_makes_one_request_and_no_download(store: ToolStore, upstream: Upstream) -> None:
    first = run(store, upstream, "rolling")
    upstream.fake.clear()
    report = run(store, upstream, "rolling")
    assert not report.downloaded
    assert report.already_installed
    assert not report.pinned
    assert report.build == first.build
    assert (upstream.api_requests, upstream.downloads) == (1, 0)


def test_installed_and_published_writes_a_changed_prerelease_flag(store: ToolStore, upstream: Upstream) -> None:
    first = run(store, upstream, "rolling")
    assert first.build.prerelease
    upstream.publish({**upstream.release("rolling"), "prerelease": False})
    report = run(store, upstream, "rolling")
    assert not report.downloaded
    assert not report.build.prerelease
    assert [(build.id, build.prerelease) for build in store.builds()] == [(first.build.id, False)]


def test_a_moving_tag_adds_a_second_build_and_leaves_the_pin(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    first = run(store, upstream, "rolling")
    upstream.publish_jar("rolling", upstream.jar("newer", commit=commit("1a2b3c4")))
    report = run(store, upstream, "rolling")
    assert report.downloaded
    assert not report.already_installed
    assert not report.pinned
    assert report.build.id != first.build.id
    assert {build.id for build in store.builds()} == {first.build.id, report.build.id}
    assert pin_text(isolated) == first.build.id


def test_no_digest_same_bytes_new_upload_time_downloads_once_and_updates_the_source(
    store: ToolStore, upstream: Upstream
) -> None:
    first = run(store, upstream, "v1.7.4")
    assert first.build.source.digest_checked is False
    uploaded = "2026-11-20T12:00:00Z"
    upstream.publish(with_jar(upstream.release("v1.7.4"), updated_at=uploaded), times=2)
    report = run(store, upstream, "v1.7.4")
    assert report.downloaded
    assert report.already_installed
    assert report.build.id == first.build.id
    assert report.build.source.asset_updated_at == uploaded
    assert [build.source.asset_updated_at for build in store.builds()] == [uploaded]
    assert upstream.downloads == 1
    upstream.fake.clear()
    again = run(store, upstream, "v1.7.4")
    assert not again.downloaded
    assert (upstream.api_requests, upstream.downloads) == (1, 0)
    assert tmp_entries(store) == []


def test_force_with_the_same_bytes_repairs_a_truncated_jar_in_place(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    first = run(store, upstream, "rolling")
    truncate(first.build)
    report = run(store, upstream, "rolling", force=True)
    assert report.downloaded
    assert report.already_installed
    assert report.build.id == first.build.id
    assert sha256(first.build.jar.read_bytes()) == first.build.sha256
    assert [build.id for build in store.builds()] == [first.build.id]
    assert pin_text(isolated) == first.build.id
    assert tmp_entries(store) == []


def test_force_with_other_bytes_adds_a_second_build(store: ToolStore, upstream: Upstream, isolated: Isolated) -> None:
    first = run(store, upstream, "rolling")
    upstream.publish_jar("rolling", upstream.jar("newer", commit=commit("1a2b3c4")))
    report = run(store, upstream, "rolling", force=True)
    assert report.downloaded
    assert not report.already_installed
    assert {build.id for build in store.builds()} == {first.build.id, report.build.id}
    assert pin_text(isolated) == first.build.id


def test_name_at_commit_installed_makes_no_request(store: ToolStore, upstream: Upstream) -> None:
    first = run(store, upstream, "rolling")
    upstream.fake.clear()
    report = run(store, upstream, f"rolling@{ROLLING_COMMIT}")
    assert report.build == first.build
    assert report.already_installed
    assert not report.downloaded
    assert report.matches == ()
    assert upstream.fake.requests == []


def two_rolling_builds_of_one_commit(store: ToolStore, upstream: Upstream) -> tuple[Build, Build]:
    first = run(store, upstream, "rolling").build
    assert first.commit is not None
    rebuilt = upstream.jar("rebuilt", commit=first.commit, built_at="2026-11-16T00:00:00Z")
    upstream.publish_jar("rolling", rebuilt)
    second = run(store, upstream, "rolling").build
    upstream.fake.clear()
    return first, second


def test_name_at_commit_matching_two_builds_names_both_and_pins_nothing(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    first, second = two_rolling_builds_of_one_commit(store, upstream)
    unpin(store)
    report = run(store, upstream, f"rolling@{ROLLING_COMMIT}")
    assert {build.id for build in report.matches} == {first.id, second.id}
    assert report.build == report.matches[0]
    assert report.already_installed
    assert not report.pinned
    assert pin_text(isolated) is None
    assert upstream.fake.requests == []


def test_name_at_commit_matching_two_builds_with_force_is_a_usage_error(store: ToolStore, upstream: Upstream) -> None:
    two_rolling_builds_of_one_commit(store, upstream)
    before = store.builds()
    with pytest.raises(UsageError):
        run(store, upstream, f"rolling@{ROLLING_COMMIT}", force=True)
    assert upstream.fake.requests == []
    assert store.builds() == before


def test_force_name_at_commit_installed_and_published_repairs_it(store: ToolStore, upstream: Upstream) -> None:
    first = run(store, upstream, "rolling")
    truncate(first.build)
    report = run(store, upstream, f"rolling@{ROLLING_COMMIT}", force=True)
    assert report.build.id == first.build.id
    assert report.downloaded
    assert sha256(first.build.jar.read_bytes()) == first.build.sha256
    assert [build.id for build in store.builds()] == [first.build.id]


def test_force_name_at_commit_with_another_build_published_changes_nothing(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    first = run(store, upstream, "rolling")
    truncate(first.build)
    damaged = first.build.jar.read_bytes()
    upstream.publish_jar("rolling", upstream.jar("newer", commit=commit("1a2b3c4")))
    before = store.builds()
    with pytest.raises(VersionNotFound):
        run(store, upstream, f"rolling@{ROLLING_COMMIT}", force=True)
    assert upstream.downloads == 1
    assert store.builds() == before
    assert first.build.jar.read_bytes() == damaged
    assert pin_text(isolated) == first.build.id
    assert tmp_entries(store) == []


def test_name_at_commit_not_installed_installs_what_upstream_publishes_when_it_matches(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    report = run(store, upstream, f"rolling@{ROLLING_COMMIT}")
    assert report.downloaded
    assert report.build.name == "rolling"
    assert report.build.commit is not None
    assert report.build.commit.startswith(ROLLING_COMMIT)
    assert pin_text(isolated) == report.build.id


def test_name_at_calver_not_installed_installs_what_upstream_publishes_when_it_matches(
    store: ToolStore, upstream: Upstream
) -> None:
    report = run(store, upstream, f"rolling@{ROLLING_CALVER}")
    assert report.downloaded
    assert report.build.calver == ROLLING_CALVER


@pytest.mark.parametrize("build", ["abcdef0", "2026.11.14.000000"])
def test_name_at_build_not_installed_and_upstream_publishes_another_installs_nothing(
    store: ToolStore, upstream: Upstream, isolated: Isolated, build: str
) -> None:
    with pytest.raises(VersionNotFound):
        run(store, upstream, f"rolling@{build}")
    assert upstream.downloads == 1
    assert store.builds() == []
    assert pin_text(isolated) is None
    assert tmp_entries(store) == []


@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("build", ["abcdef0", "2026.11.14.000000"])
def test_name_at_build_not_installed_with_another_build_of_the_name_installed_is_version_not_found(
    store: ToolStore, upstream: Upstream, isolated: Isolated, build: str, force: bool
) -> None:
    """V12, "NAME@COMMIT or NAME@CALVER, not installed": the installed build upstream publishes is not it."""
    installed = run(store, upstream, "rolling").build
    before = store.builds()
    upstream.fake.clear()
    with pytest.raises(VersionNotFound):
        run(store, upstream, f"rolling@{build}", force=force)
    assert store.builds() == before
    assert pin_text(isolated) == installed.id
    assert upstream.downloads == 0
    assert tmp_entries(store) == []


def test_name_at_sha256_not_installed_is_version_not_found_with_no_request(
    store: ToolStore, upstream: Upstream
) -> None:
    with pytest.raises(VersionNotFound):
        run(store, upstream, "rolling@sha256:0123456789ab")
    assert upstream.fake.requests == []


def test_name_at_sha256_installed_makes_no_request(store: ToolStore, upstream: Upstream) -> None:
    first = run(store, upstream, "rolling")
    upstream.fake.clear()
    report = run(store, upstream, f"rolling@sha256:{first.build.sha256[:12]}")
    assert report.build == first.build
    assert upstream.fake.requests == []


def test_a_bare_calver_installed_under_two_names_names_both(store: ToolStore, upstream: Upstream) -> None:
    rolling = run(store, upstream, "rolling").build
    v180 = run(store, upstream, "v1.8.0").build
    assert rolling.sha256 == v180.sha256  # the recording holds one jar under both names, as upstream does
    upstream.fake.clear()
    report = run(store, upstream, ROLLING_CALVER)
    assert {build.id for build in report.matches} == {rolling.id, v180.id}
    assert report.already_installed
    assert not report.pinned
    assert upstream.fake.requests == []


def test_a_bare_calver_not_installed_is_version_not_found_with_no_request(store: ToolStore, upstream: Upstream) -> None:
    with pytest.raises(VersionNotFound):
        run(store, upstream, ROLLING_CALVER)
    assert upstream.fake.requests == []


def test_a_bare_calver_with_force_is_a_usage_error(store: ToolStore, upstream: Upstream) -> None:
    run(store, upstream, "rolling")
    upstream.fake.clear()
    with pytest.raises(UsageError):
        run(store, upstream, ROLLING_CALVER, force=True)
    assert upstream.fake.requests == []


def test_stable_is_resolved_through_a_fresh_list(store: ToolStore, upstream: Upstream) -> None:
    upstream.remote.releases()  # a cache file just written: stable does not read it
    upstream.fake.clear()
    report = run(store, upstream, "stable")
    assert report.build.name == "v1.7.4"
    assert upstream.list_requests == 1
    assert report.downloaded


def test_a_version_without_v_installs_the_tag_and_records_its_name(store: ToolStore, upstream: Upstream) -> None:
    upstream.fake.answer(404, "/releases/tags/1.7.4")
    report = run(store, upstream, "1.7.4")
    assert report.build.name == "v1.7.4"
    assert [build.name for build in store.builds()] == ["v1.7.4"]


def test_github_failing_with_a_build_installed_returns_it(store: ToolStore, upstream: Upstream) -> None:
    first = run(store, upstream, "v1.7.4")
    unpin(store)
    upstream.fake.unreachable()
    report = run(store, upstream, "v1.7.4")
    assert report.build == first.build
    assert report.could_not_check is not None
    assert not report.downloaded
    assert report.pinned  # the same pin rule as any path that returns one build


def test_github_failing_with_nothing_installed_is_the_network_error(store: ToolStore, upstream: Upstream) -> None:
    upstream.fake.unreachable()
    with pytest.raises(NetworkError):
        run(store, upstream, "v1.7.4")
    assert store.builds() == []


def test_github_failing_with_force_is_the_network_error(store: ToolStore, upstream: Upstream) -> None:
    first = run(store, upstream, "v1.7.4")
    upstream.fake.unreachable()
    with pytest.raises(NetworkError):
        run(store, upstream, "v1.7.4", force=True)
    assert store.builds() == [first.build]


# ---------------------------------------------------------------------- install and the pin (rows T2, T3, T4)


def test_the_first_install_pins_and_the_second_does_not_row_t2(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    first = run(store, upstream, "rolling")
    second = run(store, upstream, "v1.7.4")
    assert first.pinned
    assert not second.pinned
    assert pin_text(isolated) == first.build.id


def test_force_never_moves_the_pin_row_t2(store: ToolStore, upstream: Upstream, isolated: Isolated) -> None:
    pinned = run(store, upstream, "rolling").build
    other = run(store, upstream, "v1.7.4", force=True)
    assert not other.pinned
    again = run(store, upstream, "rolling", force=True)
    assert not again.pinned
    upstream.publish_jar("rolling", upstream.jar("newer", commit=commit("1a2b3c4")))
    newer = run(store, upstream, "rolling", force=True)
    assert newer.build.id != pinned.id
    assert pin_text(isolated) == pinned.id


def test_with_no_pin_file_an_install_pins_row_t3(store: ToolStore, upstream: Upstream, isolated: Isolated) -> None:
    run(store, upstream, "v1.7.4")
    unpin(store)
    assert not isolated.paths.pin.exists()
    report = run(store, upstream, "rolling")
    assert report.pinned
    assert pin_text(isolated) == report.build.id


def test_a_pin_naming_a_missing_build_is_nothing_pinned_row_t3(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    isolated.paths.pin.parent.mkdir(parents=True, exist_ok=True)
    isolated.paths.pin.write_text("rolling-000000000000\n", encoding="utf-8")
    report = run(store, upstream, "rolling")
    assert report.pinned
    assert pin_text(isolated) == report.build.id


def test_a_pin_naming_a_removed_build_is_nothing_pinned_row_t3(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    gone = run(store, upstream, "v1.7.4").build
    with store.locked(timeout=0):
        store.remove(gone)  # the state a killed uninstall leaves (D50)
    assert pin_text(isolated) == gone.id
    report = run(store, upstream, "rolling")
    assert report.pinned
    assert pin_text(isolated) == report.build.id


@pytest.mark.parametrize("text", ["", "\n"])
def test_an_empty_pin_file_is_nothing_pinned_and_install_pins_over_it_row_t4(
    store: ToolStore, upstream: Upstream, isolated: Isolated, text: str
) -> None:
    isolated.paths.pin.parent.mkdir(parents=True, exist_ok=True)
    isolated.paths.pin.write_text(text, encoding="utf-8")
    report = run(store, upstream, "rolling")
    assert report.pinned
    assert pin_text(isolated) == report.build.id


def test_an_installed_build_found_with_no_request_is_pinned_when_nothing_is(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    first = run(store, upstream, "rolling")
    unpin(store)
    report = run(store, upstream, f"rolling@{ROLLING_COMMIT}")
    assert report.pinned
    assert pin_text(isolated) == first.build.id


# ---------------------------------------------------------------------- the Uninstall steps under the lock (V3)


@pytest.fixture
def other(isolated: Isolated, clock: FakeClock) -> ToolStore:
    """A second store object on the same folder: another tlaup."""
    return ToolStore(isolated.paths, now=clock.now)


def removed_by(store: ToolStore, *builds: Build) -> None:
    with store.locked(timeout=0):
        for build in builds:
            store.remove(build)


def run_uninstall(step: Uninstall) -> None:
    step.take_store_lock(timeout=0)
    try:
        step.clean_tmp()
        step.move_out()
        step.delete_out()
        step.clear_pin()
    finally:
        step.release_store_lock()


def test_two_builds_named_and_the_second_gone_meanwhile_removes_nothing(
    store: ToolStore, other: ToolStore, downloads: Downloads
) -> None:
    first = downloads.add(manifest(commit("a1")), name="v1.8.0")
    second = downloads.add(manifest(commit("b2")), name="v1.7.4")
    step = Uninstall(store, [first, second], groups=[[first], [second]])
    removed_by(other, second)
    run_uninstall(step)
    assert step.removed == []
    assert step.missing == [second]
    assert step.failed == []
    assert [build.id for build in store.builds()] == [first.id]


def test_one_of_two_rolling_builds_gone_meanwhile_removes_the_other(
    store: ToolStore, other: ToolStore, downloads: Downloads
) -> None:
    older = downloads.add(manifest(commit("a1"), "2026-11-14T00:00:00Z"))
    newer = downloads.add(manifest(commit("b2"), "2026-11-15T00:00:00Z"))
    step = Uninstall(store, [newer, older], groups=[[newer, older]])
    removed_by(other, older)
    run_uninstall(step)
    assert step.missing == []
    assert step.removed == [newer]
    assert store.builds() == []


def test_one_group_of_every_build_all_gone_meanwhile_moves_nothing(
    store: ToolStore, other: ToolStore, downloads: Downloads
) -> None:
    every = [downloads.add(manifest(commit("a1"))), downloads.add(manifest(commit("b2")), name="v1.7.4")]
    step = Uninstall(store, every, groups=[every])
    removed_by(other, *every)
    downloads.release()  # the lock files of the folders the builds were added from
    run_uninstall(step)
    assert step.removed == []
    assert {build.id for build in step.missing} == {build.id for build in every}
    assert tmp_entries(store) == []


def test_uninstall_clears_a_pin_on_a_build_it_removed_and_never_moves_it(
    store: ToolStore, downloads: Downloads, isolated: Isolated
) -> None:
    kept = downloads.add(manifest(commit("a1")), name="v1.7.4")
    pinned = downloads.add(manifest(commit("b2")))
    with store.locked(timeout=0):
        store.pin(pinned)
    step = Uninstall(store, [pinned])
    run_uninstall(step)
    assert step.removed == [pinned]
    assert step.unpinned == pinned
    assert pin_text(isolated) is None
    assert store.builds() == [kept]


def test_uninstall_leaves_a_pin_on_a_build_a_killed_uninstall_removed(
    store: ToolStore, downloads: Downloads, isolated: Isolated
) -> None:
    gone = downloads.add(manifest(commit("a1")), name="v1.7.4")
    other_build = downloads.add(manifest(commit("b2")))
    with store.locked(timeout=0):
        store.pin(gone)
        store.remove(gone)  # killed before it cleared the pin (D50)
    step = Uninstall(store, [other_build])
    run_uninstall(step)
    assert step.removed == [other_build]
    assert step.unpinned is None
    assert pin_text(isolated) == gone.id


# ---------------------------------------------------------------------- the build found has gone (K2-5)


class RemovedBeforeTheLock(ToolStore):
    """A store whose first ``acquire`` finds the build of ``name`` removed by another tlaup just before."""

    def __init__(self, isolated: Isolated, clock: FakeClock, name: str) -> None:
        super().__init__(isolated.paths, now=clock.now)
        self._other: ToolStore | None = ToolStore(isolated.paths, now=clock.now)
        self._name = name

    def acquire(self, timeout: float = 60.0) -> None:
        if self._other is not None:
            other, self._other = self._other, None
            removed_by(other, *[build for build in other.builds() if build.name == self._name])
        super().acquire(timeout)


@pytest.mark.parametrize("text", ["rolling", f"rolling@{ROLLING_COMMIT}"])
def test_install_starts_again_when_the_build_it_found_has_gone(
    store: ToolStore, upstream: Upstream, isolated: Isolated, clock: FakeClock, text: str
) -> None:
    run(store, upstream, "rolling")
    unpin(store)
    upstream.fake.clear()
    racing = RemovedBeforeTheLock(isolated, clock, "rolling")
    report = run(racing, upstream, text)
    assert report.downloaded
    assert report.pinned
    assert [build.id for build in store.builds()] == [report.build.id]
    assert pin_text(isolated) == report.build.id
    assert upstream.downloads == 1
    assert upstream.tag_requests == (2 if text == "rolling" else 1)  # the lookup again, never the first answer


# ---------------------------------------------------------------------- upgrade (V4; rows T40 and T41)


def run_upgrade(store: ToolStore, upstream: Upstream, text: str | None, *, keep_old: bool = False) -> UpgradeReport:
    spec = None if text is None else parse_version_spec(text)
    return upgrade(store, upstream.remote, upstream.client, spec, keep_old=keep_old)


def publish_rolling(upstream: Upstream, label: str, prefix: str, built_at: str) -> None:
    """A new rolling build upstream, with a later build time than the recorded one."""
    upstream.publish_jar("rolling", upstream.jar(label, commit=commit(prefix), built_at=built_at))


def test_upgrade_up_to_date_downloads_nothing_and_asks_github_once(
    store: ToolStore, upstream: Upstream, clock: FakeClock
) -> None:
    first = run(store, upstream, "rolling").build
    upstream.remote.releases()  # the lookup cache, written now
    clock.advance(60)  # one minute old: upgrade does not read it
    upstream.fake.clear()
    report = run_upgrade(store, upstream, "rolling")
    assert report.up_to_date
    assert (report.name, report.build, report.old) == ("rolling", first, first)
    assert (report.installed, report.pin_moved, report.removed, report.remaining) == (None, False, None, ())
    assert (upstream.api_requests, upstream.tag_requests, upstream.downloads) == (1, 1, 0)
    assert store.builds() == [first]


def test_upgrade_up_to_date_writes_a_changed_prerelease_flag(store: ToolStore, upstream: Upstream) -> None:
    first = run(store, upstream, "rolling").build
    upstream.publish({**upstream.release("rolling"), "prerelease": False})
    report = run_upgrade(store, upstream, "rolling")
    assert report.up_to_date
    assert not report.build.prerelease
    assert [(build.id, build.prerelease) for build in store.builds()] == [(first.id, False)]
    assert upstream.downloads == 0


def test_upgrade_with_another_digest_replaces_the_old_build_and_moves_the_pin_row_t40(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    old = run(store, upstream, "rolling").build
    publish_rolling(upstream, "newer", "1a2b3c4", "2026-11-16T00:00:00Z")
    report = run_upgrade(store, upstream, "rolling")
    assert not report.up_to_date
    assert report.old == old
    assert report.removed == old
    assert report.pin_moved
    assert report.build.commit == commit("1a2b3c4")
    assert store.builds() == [report.build]
    assert pin_text(isolated) == report.build.id
    assert report.remaining == ()
    assert (upstream.tag_requests, upstream.downloads) == (1, 1)
    assert tmp_entries(store) == []


def two_rolling_builds(store: ToolStore, upstream: Upstream) -> tuple[Build, Build]:
    """The recorded rolling build (pinned) and a newer one; upstream then publishes a third."""
    older = run(store, upstream, "rolling").build
    publish_rolling(upstream, "middle", "1a2b3c4", "2026-11-16T00:00:00Z")
    newer = run(store, upstream, "rolling").build
    assert store.builds() == [newer, older]
    publish_rolling(upstream, "newest", "2b3c4d5", "2026-11-17T00:00:00Z")
    return older, newer


def test_upgrade_compares_with_the_newest_build_of_the_name_and_leaves_the_older(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    older, newer = two_rolling_builds(store, upstream)
    with store.locked(timeout=0):
        store.pin(newer)
    report = run_upgrade(store, upstream, "rolling")
    assert report.old == newer
    assert report.removed == newer
    assert report.pin_moved
    assert report.remaining == (older,)
    assert store.builds() == [report.build, older]
    assert pin_text(isolated) == report.build.id


def test_upgrade_leaves_a_pin_on_an_older_build_of_the_name(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    older, newer = two_rolling_builds(store, upstream)
    report = run_upgrade(store, upstream, "rolling")
    assert report.removed == newer
    assert not report.pin_moved
    assert pin_text(isolated) == older.id
    assert report.remaining == (older,)


def test_upgrade_with_keep_old_keeps_the_old_build(store: ToolStore, upstream: Upstream, isolated: Isolated) -> None:
    old = run(store, upstream, "rolling").build
    publish_rolling(upstream, "newer", "1a2b3c4", "2026-11-16T00:00:00Z")
    report = run_upgrade(store, upstream, "rolling", keep_old=True)
    assert report.removed is None
    assert report.pin_moved
    assert store.builds() == [report.build, old]
    assert report.remaining == (old,)
    assert pin_text(isolated) == report.build.id


def test_upgrade_of_a_name_not_installed_installs_it(store: ToolStore, upstream: Upstream, isolated: Isolated) -> None:
    report = run_upgrade(store, upstream, "v1.7.4")
    assert report.installed is not None
    assert report.installed.downloaded
    assert report.installed.pinned
    assert (report.name, report.old, report.up_to_date) == ("v1.7.4", None, False)
    assert store.builds() == [report.build]
    assert pin_text(isolated) == report.build.id


def test_upgrade_of_a_tag_typed_without_v_upgrades_the_installed_tag(store: ToolStore, upstream: Upstream) -> None:
    first = run(store, upstream, "v1.7.4").build
    upstream.fake.clear()
    report = run_upgrade(store, upstream, "1.7.4")
    assert report.up_to_date
    assert (report.name, report.build) == ("v1.7.4", first)
    assert upstream.api_requests == 1


def test_upgrade_with_no_spec_upgrades_the_pinned_name(store: ToolStore, upstream: Upstream) -> None:
    run(store, upstream, "v1.7.4")
    old = run(store, upstream, "rolling").build
    with store.locked(timeout=0):
        store.pin(old)
    publish_rolling(upstream, "newer", "1a2b3c4", "2026-11-16T00:00:00Z")
    report = run_upgrade(store, upstream, None)
    assert (report.name, report.removed, report.pin_moved) == ("rolling", old, True)


def test_upgrade_with_no_spec_and_nothing_pinned_is_no_pinned_build_row_t41(
    store: ToolStore, upstream: Upstream
) -> None:
    run(store, upstream, "rolling")
    unpin(store)
    before = store.builds()
    upstream.fake.clear()
    with pytest.raises(NoPinnedBuild):
        run_upgrade(store, upstream, None)
    assert upstream.fake.requests == []
    assert store.builds() == before


def test_upgrade_with_no_spec_and_nothing_installed_is_no_tools_installed_row_t41(
    store: ToolStore, upstream: Upstream
) -> None:
    with pytest.raises(NoToolsInstalled):
        run_upgrade(store, upstream, None)
    assert upstream.fake.requests == []


def test_upgrade_with_no_spec_and_a_pin_naming_a_missing_build_is_pinned_build_missing(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    isolated.paths.pin.parent.mkdir(parents=True, exist_ok=True)
    isolated.paths.pin.write_text("rolling-000000000000\n", encoding="utf-8")
    with pytest.raises(PinnedBuildMissing):
        run_upgrade(store, upstream, None)
    assert upstream.fake.requests == []


@pytest.mark.parametrize("text", [ROLLING_CALVER, f"rolling@{ROLLING_COMMIT}", "rolling@sha256:0123456789ab"])
def test_upgrade_of_a_build_spec_is_a_usage_error_with_no_request(
    store: ToolStore, upstream: Upstream, text: str
) -> None:
    run(store, upstream, "rolling")
    before = store.builds()
    upstream.fake.clear()
    with pytest.raises(UsageError):
        run_upgrade(store, upstream, text)
    assert upstream.fake.requests == []
    assert store.builds() == before


def test_upgrade_of_stable_installs_a_newer_stable_tag_beside_the_old_and_moves_the_pin(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    v174 = run(store, upstream, "v1.7.4").build
    releases = [{**r, "prerelease": False} if r["tag_name"] == "v1.8.0" else r for r in upstream.releases()]
    upstream.publish_list(releases)
    upstream.fake.clear()
    report = run_upgrade(store, upstream, "stable")
    assert report.name == "v1.8.0"
    assert report.build.name == "v1.8.0"
    assert not report.build.prerelease
    assert report.old == v174
    assert report.pin_moved
    assert report.removed is None
    assert report.remaining == (v174,)
    assert {build.name for build in store.builds()} == {"v1.8.0", "v1.7.4"}
    assert pin_text(isolated) == report.build.id
    assert (upstream.list_requests, upstream.tag_requests, upstream.downloads) == (1, 0, 1)


def test_upgrade_of_stable_with_its_tag_installed_compares_like_a_name(store: ToolStore, upstream: Upstream) -> None:
    v174 = run(store, upstream, "v1.7.4").build
    upstream.fake.clear()
    report = run_upgrade(store, upstream, "stable")
    assert report.up_to_date
    assert (report.name, report.build) == ("v1.7.4", v174)
    assert (upstream.list_requests, upstream.tag_requests, upstream.downloads) == (1, 0, 0)


def test_upgrade_of_stable_with_no_stable_build_installed_is_install(store: ToolStore, upstream: Upstream) -> None:
    run(store, upstream, "rolling")
    report = run_upgrade(store, upstream, "stable")
    assert report.installed is not None
    assert (report.name, report.old, report.pin_moved) == ("v1.7.4", None, False)
    assert {build.name for build in store.builds()} == {"rolling", "v1.7.4"}


def test_upgrade_whose_download_fails_leaves_the_store_as_it_was(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    old = run(store, upstream, "rolling").build
    body = upstream.jar("newer", commit=commit("1a2b3c4"), built_at="2026-11-16T00:00:00Z")
    published = upstream.publish_jar("rolling", body, times=2)  # the retry looks the release up again
    url = next(a["browser_download_url"] for a in published["assets"] if a["name"] == "tla2tools.jar")
    upstream.serve(url, body[:100], times=2)  # cut short, and again on the one retry
    with pytest.raises(DownloadVerificationError):
        run_upgrade(store, upstream, "rolling")
    assert store.builds() == [old]
    assert pin_text(isolated) == old.id
    assert tmp_entries(store) == []


def test_upgrade_starts_again_when_the_build_it_compared_has_gone(
    store: ToolStore, upstream: Upstream, isolated: Isolated, clock: FakeClock
) -> None:
    run(store, upstream, "rolling")
    unpin(store)
    racing = RemovedBeforeTheLock(isolated, clock, "rolling")
    report = run_upgrade(racing, upstream, "rolling")
    assert report.installed is not None  # no build of the name was left, so upgrade was install
    assert store.builds() == [report.build]
    assert pin_text(isolated) == report.build.id


# ---------------------------------------------------------------------- uninstall (V3)


def test_uninstall_reports_a_failure_goes_on_and_leaves_the_pin_on_the_build_that_failed(
    store: ToolStore, downloads: Downloads, isolated: Isolated
) -> None:
    if getattr(os, "geteuid", lambda: -1)() == 0:
        pytest.skip("root can rename a read-only folder, so the failure cannot be made")
    stuck = downloads.add(manifest(commit("a1")), name="v1.7.4")
    gone = downloads.add(manifest(commit("b2")))
    with store.locked(timeout=0):
        store.pin(stuck)
    stuck.path.chmod(0o555)  # its own folder read-only: it cannot be moved out; the tool folder stays writable
    try:
        report = uninstall(store, [stuck, gone])
    finally:
        stuck.path.chmod(0o755)
    assert [build for build, _ in report.failed] == [stuck]
    assert isinstance(report.failed[0][1], FileOperationError)
    assert report.removed == (gone,)
    assert report.missing == ()
    assert report.unpinned is None
    assert store.builds() == [stuck]
    assert sha256(stuck.jar.read_bytes()) == stuck.sha256
    assert pin_text(isolated) == stuck.id


def test_uninstall_of_the_pinned_build_clears_the_pin_and_does_not_move_it(
    store: ToolStore, downloads: Downloads, isolated: Isolated
) -> None:
    kept = downloads.add(manifest(commit("a1")), name="v1.7.4")
    pinned = downloads.add(manifest(commit("b2")))
    with store.locked(timeout=0):
        store.pin(pinned)
    report = uninstall(store, [pinned])
    assert report.removed == (pinned,)
    assert report.unpinned == pinned
    assert pin_text(isolated) is None
    assert store.builds() == [kept]


def test_uninstall_of_three_builds_with_the_middle_one_pinned_removes_all(
    store: ToolStore, downloads: Downloads, isolated: Isolated
) -> None:
    every = [
        downloads.add(manifest(commit("a1"))),
        downloads.add(manifest(commit("b2")), name="v1.8.0"),
        downloads.add(manifest(commit("c3")), name="v1.7.4"),
    ]
    with store.locked(timeout=0):
        store.pin(every[1])
    report = uninstall(store, every, groups=[every])
    assert report.removed == tuple(every)
    assert report.unpinned == every[1]
    assert store.builds() == []
    assert pin_text(isolated) is None
    downloads.release()
    assert tmp_entries(store) == []


def test_uninstall_of_a_group_with_nothing_left_removes_nothing(
    store: ToolStore, downloads: Downloads, isolated: Isolated
) -> None:
    kept = downloads.add(manifest(commit("a1")), name="v1.7.4")
    gone = downloads.add(manifest(commit("b2")))
    with store.locked(timeout=0):
        store.pin(kept)
        store.remove(gone)
    report = uninstall(store, [kept, gone], groups=[[kept], [gone]])
    assert (report.removed, report.missing, report.failed, report.unpinned) == ((), (gone,), (), None)
    assert store.builds() == [kept]
    assert pin_text(isolated) == kept.id


# ---------------------------------------------------------------------- pin and the which-build question (V3, V4)


class Answers(io.StringIO):
    """Stdin with the answers typed, counting how often a line was read: once per question asked."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.asked = 0

    def readline(self, size: int | None = -1) -> str:
        self.asked += 1
        return super().readline(size)


def make_ui(answers: str = "", *, interactive: bool = True) -> tuple[Ui, Answers]:
    stdin = Answers(answers)
    return Ui(io.StringIO(), io.StringIO(), stdin, color=False, env={}, interactive=interactive), stdin


def two_rolling(downloads: Downloads) -> tuple[Build, Build]:
    """Two rolling builds, newest first, as ``find`` lists them."""
    older = downloads.add(manifest(commit("a1"), "2026-11-14T00:00:00Z"))
    newer = downloads.add(manifest(commit("b2"), "2026-11-15T00:00:00Z"))
    return newer, older


def test_pin_by_spec_writes_the_pin(store: ToolStore, downloads: Downloads, isolated: Isolated) -> None:
    downloads.add(manifest(commit("a1")))
    wanted = downloads.add(manifest(commit("b2")), name="v1.7.4")
    ui, stdin = make_ui()
    assert pin(store, parse_version_spec("1.7.4"), ui) == wanted
    assert pin_text(isolated) == wanted.id
    assert stdin.asked == 0


def test_pin_of_a_spec_that_matches_nothing_is_version_not_found(
    store: ToolStore, downloads: Downloads, isolated: Isolated
) -> None:
    downloads.add(manifest(commit("a1")))
    with pytest.raises(VersionNotFound):
        pin(store, parse_version_spec("v1.7.4"), make_ui()[0])
    assert pin_text(isolated) is None


def test_pin_of_several_matches_on_a_terminal_pins_the_answer(
    store: ToolStore, downloads: Downloads, isolated: Isolated
) -> None:
    _, older = two_rolling(downloads)
    ui, stdin = make_ui("2\n")
    assert pin(store, parse_version_spec("rolling"), ui) == older
    assert pin_text(isolated) == older.id
    assert stdin.asked == 1


def test_pin_asks_again_for_an_answer_out_of_range(store: ToolStore, downloads: Downloads, isolated: Isolated) -> None:
    _, older = two_rolling(downloads)
    ui, stdin = make_ui("-1\n7\n2\n")
    assert pin(store, parse_version_spec("rolling"), ui) == older
    assert stdin.asked == 3
    assert pin_text(isolated) == older.id


def test_pin_of_several_matches_without_a_terminal_is_ambiguous_and_writes_nothing(
    store: ToolStore, downloads: Downloads, isolated: Isolated
) -> None:
    two_rolling(downloads)
    ui, stdin = make_ui("1\n", interactive=False)
    with pytest.raises(AmbiguousVersion):
        pin(store, parse_version_spec("rolling"), ui)
    assert stdin.asked == 0
    assert pin_text(isolated) is None


def test_pin_of_a_build_removed_before_the_lock_is_version_not_found(
    isolated: Isolated, clock: FakeClock, downloads: Downloads
) -> None:
    kept = downloads.add(manifest(commit("a1")), name="v1.7.4")
    downloads.add(manifest(commit("b2")))
    with downloads.store.locked(timeout=0):
        downloads.store.pin(kept)
    racing = RemovedBeforeTheLock(isolated, clock, "rolling")
    with pytest.raises(VersionNotFound):
        pin(racing, parse_version_spec("rolling"), make_ui()[0])
    assert pin_text(isolated) == kept.id


def test_choose_build_takes_all_when_allowed_and_asks_again_on_an_empty_line(downloads: Downloads) -> None:
    builds = list(two_rolling(downloads))
    ui, stdin = make_ui("\nall\n")
    assert choose_build(ui, "Which build should be removed?", builds, allow_all=True) == builds
    assert stdin.asked == 2


def test_choose_build_refuses_all_when_not_allowed(downloads: Downloads) -> None:
    builds = list(two_rolling(downloads))
    ui, stdin = make_ui("all\n0\n")
    with pytest.raises(CannotAsk):  # the input ended with no answer in range
        choose_build(ui, "Which build should be pinned?", builds, allow_all=False)
    assert stdin.asked == 3
