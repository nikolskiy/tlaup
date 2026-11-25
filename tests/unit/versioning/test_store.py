"""The tool store on real files and real locks (design 12 V1, V11).

Inventory rows owned here: T4, the store half (``test_an_empty_pin_file_is_no_pin_row_t4``),
T14 (``test_two_builds_of_one_commit_coexist_row_t14`` and
``test_two_jars_of_one_name_and_commit_without_build_time_coexist_row_t14``) and T30
(``test_a_pinned_folder_without_a_jar_is_pinned_build_missing_row_t30``).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.clock import FakeClock
from tests.unit.versioning.conftest import SOURCE, Downloads, commit, manifest
from tlaup.errors import FileOperationError, InternalError, PinnedBuildMissing, StoreLocked
from tlaup.versioning.store import Source, ToolStore, build_id

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.conftest import Isolated
    from tlaup.versioning.store import Build

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROLLING = commit("bc1b506")
STAMP = "2026-11-15T00:21:46Z"
LATER = "2026-11-16T09:00:00Z"


def build_folders(store: ToolStore, isolated: Isolated) -> list[str]:
    """What sits in the tool folder outside ``.tmp/``, apart from the lock and the pin."""
    return sorted(entry.name for entry in isolated.paths.tools.iterdir() if entry.name not in {".tmp", ".lock", "pin"})


# ---------------------------------------------------------------------- add and list


def test_add_then_list(store: ToolStore, downloads: Downloads, clock: FakeClock) -> None:
    build = downloads.add(manifest(ROLLING, STAMP), "rolling", prerelease=True)
    assert store.builds() == [build]
    assert build.name == "rolling"
    assert build.commit == ROLLING
    assert build.calver == "2026.11.15.002146"
    assert build.built_at == STAMP
    assert build.prerelease is True
    assert build.source == SOURCE
    assert build.installed_at == "2026-11-15T00:00:00Z"
    assert build.capabilities == {"calver", "overrides_property", "no_generate_spec_te"}
    assert build.jar == build.path / "tla2tools.jar"
    assert build.jar.is_file()
    assert build.size == build.jar.stat().st_size
    record = json.loads((build.path / "build.json").read_text(encoding="utf-8"))
    assert record["schema"] == 1
    assert "id" not in record
    assert "path" not in record
    assert record["source"]["digest_checked"] is True


def test_an_empty_store_has_no_builds_and_nothing_pinned(store: ToolStore, isolated: Isolated) -> None:
    assert store.builds() == []
    assert store.pinned() is None
    assert not isolated.paths.tools.exists(), "reading creates nothing"


def test_a_folder_without_build_json_is_not_a_build(store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(ROLLING))
    (build.path / "build.json").unlink()
    assert store.builds() == []


def test_a_build_json_with_an_unknown_schema_is_not_a_build(store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(ROLLING))
    record = build.path / "build.json"
    data = json.loads(record.read_text(encoding="utf-8"))
    record.write_text(json.dumps({**data, "schema": 99}), encoding="utf-8")
    assert store.builds() == []


@pytest.mark.parametrize(
    "damage",
    [
        "{not json",
        "[]",
        json.dumps({"schema": "1"}),
        json.dumps({"schema": True}),
    ],
)
def test_a_damaged_build_json_is_not_a_build(store: ToolStore, downloads: Downloads, damage: str) -> None:
    build = downloads.add(manifest(ROLLING))
    (build.path / "build.json").write_text(damage, encoding="utf-8")
    assert store.builds() == []


@pytest.mark.parametrize(("field", "value"), [("sha256", "abc"), ("size", "12"), ("prerelease", 1), ("source", None)])
def test_a_build_json_with_a_wrong_field_is_not_a_build(
    store: ToolStore, downloads: Downloads, field: str, value: object
) -> None:
    build = downloads.add(manifest(ROLLING))
    record = build.path / "build.json"
    data = json.loads(record.read_text(encoding="utf-8"))
    record.write_text(json.dumps({**data, field: value}), encoding="utf-8")
    assert store.builds() == []


def test_a_jar_without_metadata_is_not_a_build(store: ToolStore, isolated: Isolated, downloads: Downloads) -> None:
    jar, _ = downloads.jar(manifest(ROLLING))
    folder = isolated.paths.tools / "rolling-000000000000"
    shutil.copytree(jar.parent, folder)
    assert (folder / "tla2tools.jar").is_file()
    assert store.builds() == []


def test_a_build_json_without_a_jar_is_not_a_build(store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(ROLLING))
    build.jar.unlink()
    assert store.builds() == []


# ---------------------------------------------------------------------- the pin


def test_pin_and_unpin(store: ToolStore, downloads: Downloads, isolated: Isolated) -> None:
    first = downloads.add(manifest(ROLLING), "rolling")
    second = downloads.add(manifest(commit("5a47802")), "v1.7.4")
    with store.locked(timeout=0):
        store.pin(first)
    assert store.pinned() == first
    assert isolated.paths.pin.read_text(encoding="utf-8") == f"{first.id}\n"
    with store.locked(timeout=0):
        store.pin(second)
    assert store.pinned() == second
    with store.locked(timeout=0):
        store.unpin()
        store.unpin()  # nothing pinned: nothing to do
    assert store.pinned() is None
    assert not isolated.paths.pin.exists()


def test_pinned_raises_when_the_pinned_folder_is_removed(store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(ROLLING))
    with store.locked(timeout=0):
        store.pin(build)
    shutil.rmtree(build.path)
    with pytest.raises(PinnedBuildMissing) as caught:
        store.pinned()
    assert caught.value.exit_code == 3
    assert caught.value.hint is not None
    assert "tlaup tool install" in caught.value.hint


def test_a_pinned_folder_without_a_jar_is_pinned_build_missing_row_t30(store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(ROLLING))
    with store.locked(timeout=0):
        store.pin(build)
    build.jar.unlink()
    with pytest.raises(PinnedBuildMissing):
        store.pinned()


@pytest.mark.parametrize("text", ["", "\n", "  \n\n"])
def test_an_empty_pin_file_is_no_pin_row_t4(
    store: ToolStore, downloads: Downloads, isolated: Isolated, text: str
) -> None:
    build = downloads.add(manifest(ROLLING))
    isolated.paths.pin.write_text(text, encoding="utf-8")
    assert store.pinned() is None
    with store.locked(timeout=0):
        store.pin(build)
    assert isolated.paths.pin.read_text(encoding="utf-8") == f"{build.id}\n"
    assert store.pinned() == build


def test_the_pin_is_read_with_white_space_stripped(store: ToolStore, downloads: Downloads, isolated: Isolated) -> None:
    build = downloads.add(manifest(ROLLING))
    isolated.paths.pin.write_text(f"  {build.id}\r\n", encoding="utf-8")
    assert store.pinned() == build


def test_an_unreadable_pin_file_is_a_file_operation_error(store: ToolStore, isolated: Isolated) -> None:
    isolated.paths.pin.mkdir(parents=True)
    with pytest.raises(FileOperationError) as caught:
        store.pinned()
    assert caught.value.exit_code == 5
    assert str(isolated.paths.pin) in caught.value.message


# ---------------------------------------------------------------------- ids


@pytest.mark.parametrize(("name", "text"), [("v1.9-rc", "v1.9_rc"), ("release/1.9", "release_1.9"), ("a+b", "a_b")])
def test_ids_of_names_with_a_hyphen_or_a_slash(downloads: Downloads, name: str, text: str) -> None:
    build = downloads.add(manifest(ROLLING), name)
    assert build.id == f"{text}-{build.sha256[:12]}"
    assert re.fullmatch(r"[A-Za-z0-9._-]+", build.id)
    assert build.path.name == build.id
    assert build.name == name


def test_two_builds_of_one_commit_coexist_row_t14(store: ToolStore, downloads: Downloads) -> None:
    first = downloads.add(manifest(ROLLING, STAMP))
    second = downloads.add(manifest(ROLLING, LATER))
    assert first.id != second.id
    assert {build.calver for build in store.builds()} == {"2026.11.15.002146", "2026.11.16.090000"}


def test_two_jars_of_one_name_and_commit_without_build_time_coexist_row_t14(
    store: ToolStore, downloads: Downloads
) -> None:
    first = downloads.add(manifest(ROLLING, extra="1"), "v1.7.4")
    second = downloads.add(manifest(ROLLING, extra="2"), "v1.7.4")
    assert first.sha256 != second.sha256
    assert first.id != second.id
    assert sorted(build.id for build in store.builds()) == sorted([first.id, second.id])
    assert all(build.commit == ROLLING and build.calver is None for build in store.builds())


def test_a_jar_without_a_commit_is_stored_like_any_other(store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(None), "v1.7.4")
    assert build.commit is None
    assert build.id == f"v1.7.4-{build.sha256[:12]}"
    record = json.loads((build.path / "build.json").read_text(encoding="utf-8"))
    assert record["commit"] is None
    assert store.builds() == [build]


def test_one_jar_under_two_names_is_two_builds(store: ToolStore, downloads: Downloads) -> None:
    rolling = downloads.add(manifest(ROLLING, STAMP), "rolling")
    v180 = downloads.add(manifest(ROLLING, STAMP), "v1.8.0")
    assert rolling.sha256 == v180.sha256
    assert rolling.id != v180.id
    assert len(store.builds()) == 2


def test_one_jar_under_names_that_give_the_same_text_is_two_builds(store: ToolStore, downloads: Downloads) -> None:
    first = downloads.add(manifest(ROLLING), "a-b")
    second = downloads.add(manifest(ROLLING), "a_b")
    assert first.id == f"a_b-{first.sha256[:12]}"
    assert second.id == f"{first.id}-2"
    assert {build.name for build in store.builds()} == {"a-b", "a_b"}


@pytest.mark.parametrize("content", [None, "{not json", json.dumps({"schema": 99, "name": "rolling"})])
def test_add_leaves_a_folder_it_cannot_read_and_takes_the_next_id(
    store: ToolStore, downloads: Downloads, isolated: Isolated, content: str | None
) -> None:
    jar, info = downloads.jar(manifest(ROLLING))
    first = isolated.paths.tools / build_id("rolling", info.sha256)
    first.mkdir(parents=True)
    (first / "other").write_text("left by someone", encoding="utf-8")
    if content is not None:
        (first / "build.json").write_text(content, encoding="utf-8")
    before = sorted((path.name, path.read_bytes()) for path in first.iterdir())
    with store.locked(timeout=0):
        build = store.add(jar, info, name="rolling", prerelease=True, source=SOURCE)
    assert build.id == f"{first.name}-2"
    assert sorted((path.name, path.read_bytes()) for path in first.iterdir()) == before
    assert store.builds() == [build]


def test_two_jars_that_agree_in_the_id_digits_coexist(isolated: Isolated, clock: FakeClock) -> None:
    store = ToolStore(isolated.paths, now=clock.now, id_digits=1)
    downloads = Downloads(store)
    try:
        first = downloads.add(manifest(ROLLING, extra="0"))
        extra = 1
        while True:
            jar, info = downloads.jar(manifest(ROLLING, extra=str(extra)))
            if info.sha256[0] == first.sha256[0]:
                break
            extra += 1
        with store.locked(timeout=0):
            second = store.add(jar, info, name="rolling", prerelease=True, source=SOURCE)
    finally:
        downloads.release()
    assert first.sha256 != second.sha256
    assert first.id == f"rolling-{first.sha256[0]}"
    assert second.id == f"{first.id}-2"
    assert sorted(build.id for build in store.builds()) == sorted([first.id, second.id])


# ---------------------------------------------------------------------- already there


def test_the_same_name_and_bytes_twice_is_one_build(store: ToolStore, downloads: Downloads, isolated: Isolated) -> None:
    first = downloads.add(manifest(ROLLING))
    jar, info = downloads.jar(manifest(ROLLING))
    with store.locked(timeout=0):
        again = store.add(jar, info, name="rolling", prerelease=False, source=SOURCE)
    assert again == first
    assert build_folders(store, isolated) == [first.id]
    assert not jar.parent.exists(), "the temporary copy is discarded"


def test_repair_replaces_the_jar_on_disk(store: ToolStore, downloads: Downloads, clock: FakeClock) -> None:
    first = downloads.add(manifest(ROLLING))
    good = first.jar.read_bytes()
    first.jar.write_bytes(b"damaged")
    clock.advance(60)
    jar, info = downloads.jar(manifest(ROLLING))
    with store.locked(timeout=0):
        repaired = store.add(jar, info, name="rolling", prerelease=False, source=SOURCE, repair=True)
    assert repaired.id == first.id
    assert repaired.jar.read_bytes() == good
    assert repaired.prerelease is False
    assert repaired.installed_at == "2026-11-15T00:01:00Z"
    assert store.builds() == [repaired]
    assert not jar.parent.exists()


# ---------------------------------------------------------------------- mutations need the lock


def test_mutations_without_the_lock_fail(store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(ROLLING))
    jar, info = downloads.jar(manifest(ROLLING, extra="other"))
    calls = [
        lambda: store.add(jar, info, name="rolling", prerelease=True, source=SOURCE),
        lambda: store.update(build, prerelease=False, source=SOURCE),
        lambda: store.remove(build),
        lambda: store.pin(build),
        store.unpin,
        lambda: store.move_out(build),
        store.clean_tmp,
    ]
    for call in calls:
        with pytest.raises(InternalError):
            call()
    assert store.builds() == [build]
    assert store.pinned() is None


def test_another_store_objects_lock_does_not_count(isolated: Isolated, store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(ROLLING))
    other = ToolStore(isolated.paths, now=FakeClock().now)
    with store.locked(timeout=0), pytest.raises(InternalError):
        other.pin(build)


# ---------------------------------------------------------------------- update and remove


def test_update_rewrites_build_json_only(store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(ROLLING), prerelease=True)
    content = build.jar.read_bytes()
    source = Source("github-release", "https://example.invalid/other", 7, "2026-11-20T00:00:00Z", digest_checked=False)
    with store.locked(timeout=0):
        updated = store.update(build, prerelease=False, source=source)
    assert updated.id == build.id
    assert updated.prerelease is False
    assert updated.source == source
    assert updated.installed_at == build.installed_at
    assert store.builds() == [updated]
    assert updated.jar.read_bytes() == content


def test_remove_leaves_nothing_outside_tmp(store: ToolStore, downloads: Downloads, isolated: Isolated) -> None:
    keep = downloads.add(manifest(ROLLING), "v1.8.0")
    build = downloads.add(manifest(ROLLING), "rolling")
    with store.locked(timeout=0):
        store.remove(build)
    assert build_folders(store, isolated) == [keep.id]
    assert store.builds() == [keep]
    downloads.release()
    assert list((isolated.paths.tools / ".tmp").iterdir()) == []


@pytest.fixture
def read_only() -> Iterator[list[Path]]:
    folders: list[Path] = []
    yield folders
    for folder in folders:
        if folder.exists():
            folder.chmod(0o700)


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root deletes read-only folders")
@pytest.mark.skipif(sys.platform == "win32", reason="the read-only folder is a POSIX permission (D15)")
def test_remove_leaves_nothing_outside_tmp_when_the_delete_fails(
    store: ToolStore, downloads: Downloads, isolated: Isolated, read_only: list[Path]
) -> None:
    build = downloads.add(manifest(ROLLING))
    stuck = build.path / "stuck"
    stuck.mkdir()
    (stuck / "file").write_text("cannot be deleted", encoding="utf-8")
    stuck.chmod(0o500)  # its entries cannot be unlinked, so the delete step fails
    with store.locked(timeout=0):
        store.remove(build)
    downloads.release()
    leftovers = list((isolated.paths.tools / ".tmp").iterdir())
    read_only.extend(path / "stuck" for path in leftovers if path.is_dir())
    assert build_folders(store, isolated) == []
    assert store.builds() == []
    assert [path for path in leftovers if path.is_dir()], "what could not be deleted stays under .tmp/"
    assert not [path for path in leftovers if path.suffix == ".lock"], "its lock was released and its file removed"
    for folder in read_only:
        folder.chmod(0o700)
    with store.locked(timeout=0):
        store.clean_tmp()
    assert list((isolated.paths.tools / ".tmp").iterdir()) == []


def test_move_out_of_a_build_that_has_gone_is_none(store: ToolStore, downloads: Downloads, isolated: Isolated) -> None:
    build = downloads.add(manifest(ROLLING))
    with store.locked(timeout=0):
        out = store.move_out(build)
        assert out is not None
        assert not build.path.exists()
        assert out.path.is_dir()
        assert out.lock_file.is_file()
        assert store.move_out(build) is None
        store.delete_out(out)
    downloads.release()
    assert list((isolated.paths.tools / ".tmp").iterdir()) == []


def test_move_out_leaves_another_build_at_the_same_id(store: ToolStore, downloads: Downloads) -> None:
    build = downloads.add(manifest(ROLLING))
    with store.locked(timeout=0):
        store.remove(build)
    again = downloads.add(manifest(ROLLING))
    assert again.id == build.id
    stale = replace(build, sha256="0" * 64)
    with store.locked(timeout=0):
        assert store.move_out(stale) is None
    assert store.builds() == [again]


# ---------------------------------------------------------------------- complete after every write


def test_readers_never_see_a_build_without_both_files(isolated: Isolated, clock: FakeClock) -> None:
    reader = ToolStore(isolated.paths, now=clock.now)
    writer = ToolStore(isolated.paths, now=clock.now)
    downloads = Downloads(writer)

    def check() -> list[Build]:
        builds = reader.builds()
        tools = isolated.paths.tools
        for entry in tools.iterdir() if tools.exists() else []:
            if entry.is_dir() and entry.name != ".tmp":
                assert (entry / "tla2tools.jar").is_file(), entry.name
                assert (entry / "build.json").is_file(), entry.name
        pin = isolated.paths.pin
        if pin.exists():
            assert pin.read_text(encoding="utf-8").strip() in {build.id for build in builds}
        return builds

    try:
        jar, info = downloads.jar(manifest(ROLLING))
        assert check() == []
        writer.acquire(timeout=0)
        assert check() == []
        first = writer.add(jar, info, name="rolling", prerelease=True, source=SOURCE)
        assert check() == [first]
        writer.pin(first)
        assert reader.pinned() == first
        jar, info = downloads.jar(manifest(ROLLING, LATER))
        assert check() == [first]
        second = writer.add(jar, info, name="rolling", prerelease=True, source=SOURCE)
        assert {build.id for build in check()} == {first.id, second.id}
        writer.pin(second)
        assert reader.pinned() == second
        writer.update(second, prerelease=False, source=SOURCE)
        pinned = reader.pinned()
        assert pinned is not None
        assert pinned.prerelease is False
        writer.release()
    finally:
        downloads.release()
    temporary = [entry.name for entry in isolated.paths.tools.rglob(".*.tmp")]
    assert temporary == [], "no temporary file of a write is left"


# ---------------------------------------------------------------------- the store lock (V11)

HOLDER = """
import sys
import filelock
lock = filelock.FileLock(sys.argv[1])
lock.acquire(timeout=0)
print("held", flush=True)
sys.stdin.readline()
"""


@pytest.fixture
def hold_in_another_process() -> Iterator[Callable[[Path], None]]:
    children: list[subprocess.Popen[str]] = []

    def hold(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        child = subprocess.Popen(
            [sys.executable, "-c", HOLDER, str(path)],
            cwd=PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        children.append(child)
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "held"

    yield hold
    for child in children:
        child.communicate("\n", timeout=30)


def test_the_store_lock_held_by_another_process_is_store_locked(
    store: ToolStore, isolated: Isolated, hold_in_another_process: Callable[[Path], None]
) -> None:
    lock_file = isolated.paths.tools / ".lock"
    hold_in_another_process(lock_file)
    with pytest.raises(StoreLocked) as caught:
        store.acquire(timeout=0.1)
    assert caught.value.exit_code == 5
    assert str(lock_file) in caught.value.message
    with pytest.raises(StoreLocked):
        store.acquire(timeout=0)


def test_a_second_store_object_is_refused_and_refuses(isolated: Isolated, clock: FakeClock) -> None:
    first = ToolStore(isolated.paths, now=clock.now)
    second = ToolStore(isolated.paths, now=clock.now)
    with first.locked(timeout=0):
        with pytest.raises(StoreLocked):
            second.acquire(timeout=0.1)
        with pytest.raises(StoreLocked):
            second.acquire(timeout=0)
    with second.locked(timeout=0), pytest.raises(StoreLocked):
        first.acquire(timeout=0)
    first.acquire(timeout=0)
    first.release()


def test_locked_releases_on_an_error(isolated: Isolated, store: ToolStore, clock: FakeClock) -> None:
    with pytest.raises(ValueError, match="inside"), store.locked(timeout=0):
        raise ValueError("inside")
    ToolStore(isolated.paths, now=clock.now).acquire(timeout=0)


# ---------------------------------------------------------------------- temporary folders (V11)


def test_a_tmp_folder_is_locked_before_it_exists_and_released_without_a_trace(
    store: ToolStore, isolated: Isolated
) -> None:
    tmp = store.new_tmp()
    assert tmp.path.parent == isolated.paths.tools / ".tmp"
    tmp.lock()
    assert tmp.lock_file.is_file()
    assert not tmp.path.exists()
    tmp.make()
    assert tmp.path.is_dir()
    tmp.discard()
    assert not tmp.path.exists()
    tmp.release()
    assert list((isolated.paths.tools / ".tmp").iterdir()) == []


def test_clean_tmp_leaves_a_folder_whose_lock_another_process_holds(
    isolated: Isolated, hold_in_another_process: Callable[[Path], None]
) -> None:
    clock = FakeClock(datetime.now(UTC))
    store = ToolStore(isolated.paths, now=clock.now)
    folder = isolated.paths.tools / ".tmp" / "download"
    folder.mkdir(parents=True)
    (folder / "tla2tools.jar").write_bytes(b"part")
    old = (datetime.now(UTC) - timedelta(days=30)).timestamp()
    os.utime(folder, (old, old))
    hold_in_another_process(folder.with_name("download.lock"))
    clock.advance(timedelta(days=30).total_seconds())
    with store.locked(timeout=0):
        store.clean_tmp()
    assert (folder / "tla2tools.jar").is_file()
    assert folder.with_name("download.lock").is_file()


def test_clean_tmp_leaves_a_folder_whose_lock_another_store_holds(store: ToolStore, isolated: Isolated) -> None:
    other = ToolStore(isolated.paths, now=FakeClock().now)
    tmp = other.new_tmp()
    tmp.lock()
    tmp.make()
    with store.locked(timeout=0):
        store.clean_tmp()
    assert tmp.path.is_dir()
    tmp.discard()
    tmp.release()


@pytest.mark.parametrize("with_lock_file", [True, False])
def test_clean_tmp_removes_a_folder_whose_lock_is_free(
    store: ToolStore, isolated: Isolated, with_lock_file: bool
) -> None:
    folder = isolated.paths.tools / ".tmp" / "left"
    folder.mkdir(parents=True)
    (folder / "tla2tools.jar").write_bytes(b"part")
    if with_lock_file:
        folder.with_name("left.lock").touch()
    with store.locked(timeout=0):
        store.clean_tmp()
    assert list((isolated.paths.tools / ".tmp").iterdir()) == []


@pytest.mark.parametrize(("minutes", "kept"), [(59, True), (61, False)])
def test_a_lock_file_alone_is_removed_after_an_hour(isolated: Isolated, minutes: int, kept: bool) -> None:
    lock_file = isolated.paths.tools / ".tmp" / "orphan.lock"
    lock_file.parent.mkdir(parents=True)
    lock_file.touch()
    clock = FakeClock(datetime.fromtimestamp(lock_file.stat().st_mtime, UTC))
    clock.advance(minutes * 60)
    store = ToolStore(isolated.paths, now=clock.now)
    with store.locked(timeout=0):
        store.clean_tmp()
    assert lock_file.is_file() is kept


def test_a_lock_file_alone_that_another_process_holds_stays(
    isolated: Isolated, hold_in_another_process: Callable[[Path], None]
) -> None:
    lock_file = isolated.paths.tools / ".tmp" / "orphan.lock"
    hold_in_another_process(lock_file)
    clock = FakeClock(datetime.fromtimestamp(lock_file.stat().st_mtime, UTC))
    clock.advance(3 * 3600)
    store = ToolStore(isolated.paths, now=clock.now)
    with store.locked(timeout=0):
        store.clean_tmp()
    assert lock_file.is_file()


def test_add_requires_a_temporary_folder_of_the_store(store: ToolStore, tmp_path: Path, downloads: Downloads) -> None:
    _, info = downloads.jar(manifest(ROLLING))
    elsewhere = tmp_path / "elsewhere" / "tla2tools.jar"
    elsewhere.parent.mkdir()
    elsewhere.write_bytes(b"jar")
    with store.locked(timeout=0), pytest.raises(InternalError):
        store.add(elsewhere, info, name="rolling", prerelease=True, source=SOURCE)
