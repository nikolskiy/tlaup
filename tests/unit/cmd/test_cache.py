"""The `cache` commands and `clean_lock_files` (design 23 C1, 11 R6; package 45), on real folders."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import filelock
import pytest
from typer.testing import CliRunner

import tlaup.cli
from tests.clock import FakeClock
from tests.expected import assert_matches
from tlaup.cmd.cache import render_runs
from tlaup.tlc.rundirs import RunRecord, clean_lock_files, format_size

if TYPE_CHECKING:
    from tests.conftest import Isolated

EXPECTED = Path(__file__).parent / "expected"
HOUR = 3600

HOLDER = """
import sys, filelock
lock = filelock.FileLock(sys.argv[1])
lock.acquire()
print("held", flush=True)
sys.stdin.read()
"""


def run_folder(isolated: Isolated, run_id: str, *, record: dict[str, object] | None = None, size: int = 0) -> Path:
    folder = isolated.paths.runs / run_id
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(json.dumps(record if record is not None else {"keep": False}), encoding="utf-8")
    if size:
        (folder / "data.bin").write_bytes(b"x" * size)
    return folder


def lock_file(isolated: Isolated, run_id: str, *, age_seconds: float, now: datetime) -> Path:
    path = isolated.paths.runs / f"{run_id}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    stamp = now.timestamp() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def clean(*args: str) -> tuple[int, str]:
    result = CliRunner().invoke(tlaup.cli.app, ["cache", "clean", *args])
    return result.exit_code, result.stderr


# ---------------------------------------------------------------------- clean_lock_files


def test_a_lock_file_without_a_folder_goes_after_an_hour_and_not_before(isolated: Isolated) -> None:
    clock = FakeClock()
    young = lock_file(isolated, "young", age_seconds=59 * 60, now=clock.now())
    old = lock_file(isolated, "old", age_seconds=61 * 60, now=clock.now())
    assert clean_lock_files(isolated.paths, clock.now) == 1
    assert young.exists()
    assert not old.exists()


def test_a_lock_file_whose_folder_exists_is_not_visited(isolated: Isolated) -> None:
    clock = FakeClock()
    run_folder(isolated, "withfolder")
    path = lock_file(isolated, "withfolder", age_seconds=5 * HOUR, now=clock.now())
    assert clean_lock_files(isolated.paths, clock.now) == 0
    assert path.exists()


def test_a_held_lock_file_survives_at_any_age(isolated: Isolated) -> None:
    clock = FakeClock()
    path = lock_file(isolated, "held", age_seconds=100 * HOUR, now=clock.now())
    mine = filelock.FileLock(path)
    mine.acquire(timeout=0)
    try:
        assert clean_lock_files(isolated.paths, clock.now) == 0
        assert path.exists()
    finally:
        mine.release()
    assert clean_lock_files(isolated.paths, clock.now) == 1


@pytest.mark.skipif(os.name != "posix", reason="a second process holding a flock: Linux and macOS (D15)")
def test_a_lock_file_held_by_another_process_survives(isolated: Isolated) -> None:
    clock = FakeClock()
    path = lock_file(isolated, "elsewhere", age_seconds=100 * HOUR, now=clock.now())
    holder = subprocess.Popen(
        [sys.executable, "-I", "-c", HOLDER, str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"
        assert clean_lock_files(isolated.paths, clock.now) == 0
        assert path.exists()
    finally:
        assert holder.stdin is not None
        holder.stdin.close()
        holder.wait(timeout=10)
        assert holder.stdout is not None
        holder.stdout.close()


def test_no_runs_folder_is_no_lock_files(isolated: Isolated) -> None:
    assert clean_lock_files(isolated.paths, FakeClock().now) == 0


# ---------------------------------------------------------------------- cache clean


def test_clean_of_a_run_id_in_use_exits_5_and_keeps_the_folder(isolated: Isolated) -> None:
    folder = run_folder(isolated, "busy")
    holder = filelock.FileLock(isolated.paths.runs / "busy.lock")
    holder.acquire(timeout=0)
    try:
        code, stderr = clean("busy")
    finally:
        holder.release()
    assert code == 5
    assert "in use" in stderr
    assert folder.is_dir()


def test_clean_with_one_folder_in_use_and_one_removable_names_the_first(isolated: Isolated) -> None:
    busy = run_folder(isolated, "busy")
    free = run_folder(isolated, "free")
    holder = filelock.FileLock(isolated.paths.runs / "busy.lock")
    holder.acquire(timeout=0)
    try:
        code, stderr = clean()
        all_code, all_stderr = clean("--all")
    finally:
        holder.release()
    assert code == 0
    assert busy.is_dir()
    assert not free.exists()
    assert "left run folder busy: in use" in stderr
    assert all_code == 0
    assert "left run folder busy: in use" in all_stderr
    assert busy.is_dir()


def test_the_freed_total_is_the_sum_of_what_was_removed(isolated: Isolated) -> None:
    run_folder(isolated, "one", size=1500)
    run_folder(isolated, "two", size=2000)
    remote = isolated.paths.remote
    remote.mkdir(parents=True)
    (remote / "a.json").write_bytes(b"y" * 700)
    (remote / "b.json.tmp").write_bytes(b"y" * 300)
    isolated.paths.java_cache.write_bytes(b"z" * 40)
    code, stderr = clean("--all")
    assert code == 0
    run_json = len(json.dumps({"keep": False}))
    total = 1500 + 2000 + 2 * run_json + 700 + 300 + 40
    assert f"freed {format_size(total)}" in stderr
    assert remote.is_dir()
    assert list(remote.iterdir()) == []
    assert not isolated.paths.java_cache.exists()


def test_with_a_kind_named_the_java_check_stays(isolated: Isolated) -> None:
    isolated.paths.java_cache.parent.mkdir(parents=True)
    isolated.paths.java_cache.write_text("{}", encoding="utf-8")
    for args in (["--runs", "--all"], ["--remote", "--all"], ["--runs", "--remote", "--all"], []):
        assert clean(*args)[0] == 0
        assert isolated.paths.java_cache.exists()
    assert clean("--all")[0] == 0
    assert not isolated.paths.java_cache.exists()


def test_nothing_removed_says_so(isolated: Isolated) -> None:
    code, stderr = clean()
    assert code == 0
    assert stderr.strip() == "nothing was removed"


def test_a_run_id_with_an_option_is_refused_before_anything_is_looked_at(isolated: Isolated) -> None:
    folder = run_folder(isolated, "keepme")
    for option in ("--runs", "--remote", "--all"):
        code, stderr = clean("keepme", option)
        assert code == 2
        assert stderr.count("error:") == 1
    assert folder.is_dir()


# ---------------------------------------------------------------------- never out of the cache


@pytest.mark.skipif(os.name != "posix", reason="symbolic links need no privilege here only on Linux and macOS")
def test_a_link_in_remote_is_removed_as_a_link_and_not_followed(isolated: Isolated, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep", encoding="utf-8")
    remote = isolated.paths.remote
    remote.mkdir(parents=True)
    (remote / "folder-link").symlink_to(outside, target_is_directory=True)
    (remote / "file-link").symlink_to(outside / "precious.txt")
    sub = remote / "sub"
    sub.mkdir()
    (sub / "inner-link").symlink_to(outside, target_is_directory=True)
    assert clean("--remote")[0] == 0
    assert list(remote.iterdir()) == []
    assert (outside / "precious.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.skipif(os.name != "posix", reason="symbolic links need no privilege here only on Linux and macOS")
def test_remote_that_is_a_link_is_not_followed(isolated: Isolated, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep", encoding="utf-8")
    isolated.paths.cache.mkdir(parents=True)
    isolated.paths.remote.symlink_to(outside, target_is_directory=True)
    code, stderr = clean("--remote")
    assert code == 5
    assert "symbolic link" in stderr
    assert (outside / "precious.txt").exists()


@pytest.mark.skipif(os.name != "posix", reason="symbolic links need no privilege here only on Linux and macOS")
def test_a_run_folder_that_is_a_link_leaves_its_target(isolated: Isolated, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "run.json").write_text(json.dumps({"keep": False}), encoding="utf-8")
    (outside / "precious.txt").write_text("keep", encoding="utf-8")
    isolated.paths.runs.mkdir(parents=True)
    (isolated.paths.runs / "linked").symlink_to(outside, target_is_directory=True)
    assert clean("--all")[0] == 0
    code, _ = clean("linked")
    assert code == 5
    assert (outside / "precious.txt").exists()
    assert (outside / "run.json").exists()


@pytest.mark.skipif(os.name != "posix", reason="symbolic links need no privilege here only on Linux and macOS")
def test_a_link_inside_a_run_folder_is_not_followed(isolated: Isolated, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep", encoding="utf-8")
    folder = run_folder(isolated, "inside")
    (folder / "link").symlink_to(outside, target_is_directory=True)
    assert clean()[0] == 0
    assert not folder.exists()
    assert (outside / "precious.txt").exists()


# ---------------------------------------------------------------------- cache dir and cache list


def test_dir_prints_the_cache_folder_and_creates_nothing(isolated: Isolated) -> None:
    result = CliRunner().invoke(tlaup.cli.app, ["cache", "dir"])
    assert result.exit_code == 0
    assert result.stdout == f"{isolated.paths.cache}\n"
    assert not isolated.paths.cache.exists()


def record(run_id: str, **fields: object) -> RunRecord:
    base: dict[str, object] = {
        "run_id": run_id,
        "path": Path("/cache/runs") / run_id,
        "has_run_json": True,
        "spec": "/work/Spec.tla",
        "cfg": "/work/Spec.cfg",
        "build": "v1.7.4@5a47802",
        "started": datetime(2026, 11, 20, 9, 5, tzinfo=UTC),
        "ended": None,
        "last_change": datetime(2026, 11, 20, 9, 30, tzinfo=UTC),
        "size": 1_234_567,
        "in_use": False,
        "cannot_lock": False,
        "kept": False,
        "keep": False,
        "reason": None,
        "checkpoint_complete": False,
    }
    return RunRecord(**{**base, **fields})  # type: ignore[arg-type]


def test_the_rendering_of_cache_list(request: pytest.FixtureRequest) -> None:
    records = [
        record("20261121T080000Z-bbbbbbbb", started=datetime(2026, 11, 21, 8, 0, tzinfo=UTC), in_use=True, size=900),
        record(
            "20261120T090500Z-aaaaaaaa",
            kept=True,
            keep=True,
            reason="TLC crashed (exit 255)",
            checkpoint_complete=True,
        ),
        record(
            "20261119T120000Z-cccccccc",
            started=datetime(2026, 11, 19, 12, 0, tzinfo=UTC),
            keep=True,
            reason="unsettled after a kill",
            checkpoint_complete=True,
            size=52_000_000,
        ),
        record(
            "20261118T010000Z-dddddddd",
            has_run_json=False,
            spec=None,
            cfg=None,
            build=None,
            started=None,
            last_change=datetime(2026, 11, 18, 1, 0, tzinfo=UTC),
            size=0,
        ),
        record(
            "20261122T000000Z-eeeeeeee",
            kept=True,
            reason="interrupted",
            started=datetime(2026, 11, 22, 0, 0, tzinfo=UTC),
            cfg=None,
            size=3_000_000_000,
            checkpoint_complete=True,
        ),
    ]
    assert_matches("\n".join(render_runs(records)) + "\n", EXPECTED / "cache-list.txt", request)


def test_no_records_render_to_nothing() -> None:
    assert render_runs([]) == []


def test_a_java_check_that_is_a_folder_is_an_error_and_is_left_intact(isolated: Isolated) -> None:
    folder = isolated.paths.java_cache
    folder.mkdir(parents=True)
    (folder / "inner.txt").write_text("keep", encoding="utf-8")
    code, stderr = clean("--all")
    assert code == 5
    assert stderr.count("error:") == 1
    assert (folder / "inner.txt").read_text(encoding="utf-8") == "keep"


def test_the_total_counts_what_the_list_shows_as_kept() -> None:
    lines = render_runs([record("a", reason="unsettled after a kill", size=2000), record("b", size=500)])
    assert lines[-1] == "1 kept run folder holds 2.0 kB"
