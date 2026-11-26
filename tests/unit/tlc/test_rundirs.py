"""Settle, the sweep and the visits of the run folders (design 11 R6, "Unit (rundirs)"; package 35a).

Real files under the test's folder, the injected clock of ``tests.clock`` and ages set with ``os.utime``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from tests.clock import FakeClock
from tlaup.errors import FileOperationError
from tlaup.java.launcher import ProcessOutcome
from tlaup.paths import AppPaths
from tlaup.tlc.rundirs import (
    EntryVisit,
    KeptSummary,
    RunFolder,
    RunStart,
    complete_checkpoint,
    list_entries,
    sweep,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

    from tlaup.java.launcher import SignalName

STATES = "20261115-100000"  # stands for TLC's timestamped folder
START = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
HOLD = """
import sys
import filelock
lock = filelock.FileLock(sys.argv[1])
lock.acquire(timeout=0)
print("held", flush=True)
sys.stdin.readline()
"""


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(START)


@pytest.fixture
def paths(tmp_path: Path) -> AppPaths:
    return AppPaths(config=tmp_path / "config", cache=tmp_path / "cache", data=tmp_path / "data")


@pytest.fixture
def runs(paths: AppPaths) -> Path:
    paths.runs.mkdir(parents=True)
    return paths.runs


def outcome(tool: int | None, *, stopped_by: SignalName | None = None, closed_pipe: bool = False) -> ProcessOutcome:
    code = tool if tool is not None else 1
    return ProcessOutcome(
        exit_code=code,
        tool_exit_code=tool,
        stopped_by=stopped_by,
        stderr_tail=(),
        stopped_for_closed_pipe=closed_pipe,
    )


def started(
    runs: Path,
    clock: FakeClock,
    run_id: str = "run0",
    *,
    keep: bool = False,
    recover: Path | None = None,
    tlc_args: Sequence[str] = (),
) -> RunStart:
    """A start as far as its run.json, as run_folder takes it."""
    start = RunStart(runs, clock.now, run_id=run_id, recover=recover, info={"keep": keep}, wait=0, tlc_args=tlc_args)
    start.create_lock_file()
    start.take_lock()
    start.take_recover_lock()
    start.make_folder()
    start.write_run_json()
    return start


def write_checkpoint(folder: Path, *names: str) -> Path:
    states = folder / STATES
    states.mkdir(parents=True, exist_ok=True)
    for name in names or ("queue.chkpt", "vars.chkpt"):
        (states / name).write_bytes(b"checkpoint")
    return states


def record(folder: Path) -> dict[str, object]:
    loaded: dict[str, object] = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    return loaded


def end(folder: RunFolder) -> None:
    folder.end_own()
    folder.release_own()
    folder.end_recovered()
    folder.release_recovered()


def unsettled(runs: Path, clock: FakeClock, run_id: str, *, keep: bool, checkpoint: bool) -> Path:
    """The folder of a killed tlaup: run.json, never settled, its locks gone with it."""
    start = started(runs, clock, run_id, keep=keep)
    if checkpoint:
        write_checkpoint(start.path)
    start.abandon()
    return start.path


def kept(runs: Path, clock: FakeClock, run_id: str, *, size: int | None = None) -> Path:
    start = started(runs, clock, run_id, keep=True)
    write_checkpoint(start.path)
    folder = start.entered()
    assert folder.settle(outcome(255)).kept is not None
    end(folder)
    if size is not None:
        data = record(start.path)
        data["size"] = size
        (start.path / "run.json").write_text(json.dumps(data), encoding="utf-8")
    return start.path


def age(path: Path, moment: datetime) -> None:
    os.utime(path, (moment.timestamp(), moment.timestamp()))


def visit_sweep(runs: Path, clock: FakeClock, run_id: str) -> bool:
    """One visit of the sweep; True if the entry's lock could be had."""
    visit = EntryVisit(runs, run_id, clock.now)
    if not visit.take_lock():
        return False
    try:
        visit.sweep()
    finally:
        visit.release()
    return True


@pytest.fixture
def holder(tmp_path: Path) -> Iterator[list[subprocess.Popen[str]]]:
    """Second Python processes that hold a lock until the test ends."""
    children: list[subprocess.Popen[str]] = []
    yield children
    for child in children:
        child.communicate("\n", timeout=30)


def hold_in_another_process(holder: list[subprocess.Popen[str]], lock_file: Path) -> None:
    child = subprocess.Popen(
        [sys.executable, "-c", HOLD, str(lock_file)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    holder.append(child)
    assert child.stdout is not None
    assert child.stdout.readline().strip() == "held"


# ---------------------------------------------------------------------- the steps of a start


def test_a_start_writes_run_json_with_the_injected_start(runs: Path, clock: FakeClock) -> None:
    start = started(runs, clock, keep=True)
    assert (runs / "run0.lock").is_file()
    assert record(start.path) == {
        "schema": 1,
        "keep": True,
        "started": "2026-11-15T10:00:00Z",
        "ended": None,
        "kept": False,
        "size": None,
    }


def test_create_lock_file_makes_the_runs_folder(tmp_path: Path, clock: FakeClock) -> None:
    runs = tmp_path / "cache" / "runs"
    RunStart(runs, clock.now, run_id="run0").create_lock_file()
    assert (runs / "run0.lock").is_file()


def test_a_run_id_is_made_from_the_start_time_when_none_is_given(runs: Path, clock: FakeClock) -> None:
    start = RunStart(runs, clock.now)
    stamp, _, digits = start.run_id.partition("-")
    assert stamp == "20261115T100000Z"
    assert len(digits) == 8
    assert ":" not in start.run_id


def test_a_held_own_lock_is_a_file_operation_error(runs: Path, clock: FakeClock) -> None:
    started(runs, clock)
    second = RunStart(runs, clock.now, run_id="run0", wait=0)
    with pytest.raises(FileOperationError):
        second.take_lock()


def test_a_held_recovered_lock_says_the_folder_is_in_use(runs: Path, clock: FakeClock) -> None:
    first = started(runs, clock)
    second = RunStart(runs, clock.now, run_id="run1", recover=first.path / STATES, wait=0)
    second.create_lock_file()
    second.take_lock()
    with pytest.raises(FileOperationError, match="is in use by another tlaup run"):
        second.take_recover_lock()


def test_a_recover_path_under_no_existing_folder_takes_no_lock(runs: Path, clock: FakeClock) -> None:
    folder = started(runs, clock, recover=runs / "gone" / STATES).entered()
    assert not (runs / "gone.lock").exists()
    fds = folder.lock_fds
    for fd in fds:
        os.close(fd)
    assert len(fds) == (0 if os.name == "nt" else 1)  # the run's own lock only
    end(folder)


def test_a_recovered_folder_that_was_kept_makes_a_kept_run(runs: Path, clock: FakeClock) -> None:
    old = kept(runs, clock, "old")
    start = started(runs, clock, "run1", keep=False, recover=old / STATES)
    assert record(start.path)["keep"] is True


# ---------------------------------------------------------------------- settle


@pytest.mark.parametrize("code", [0, 10, 11, 12, 13, 14])
def test_a_finished_run_keeps_nothing(runs: Path, clock: FakeClock, code: int) -> None:
    start = started(runs, clock, keep=True)
    write_checkpoint(start.path)
    folder = start.entered()
    assert folder.settle(outcome(code)).kept is None
    assert folder.settle(None).dropped is None
    end(folder)
    assert list_entries(runs) == []


@pytest.mark.parametrize(
    ("process", "reason"),
    [
        (outcome(255), "TLC crashed (exit 255)"),
        (outcome(1), "TLC crashed (exit 1)"),
        (outcome(130, stopped_by="int"), "interrupted"),
        (outcome(0, closed_pipe=True), "interrupted"),
        (None, "tlaup failed"),
    ],
)
def test_a_run_that_did_not_finish_and_asked_keeps_its_complete_checkpoint(
    runs: Path, clock: FakeClock, process: ProcessOutcome | None, reason: str
) -> None:
    start = started(runs, clock, keep=True)
    states = write_checkpoint(start.path)
    folder = start.entered()
    clock.advance(8000)
    settled = folder.settle(process)
    assert settled.dropped is None
    assert settled.kept is not None
    assert settled.kept.path == start.path
    assert settled.kept.checkpoint_dir == states
    assert settled.kept.reason == reason
    assert settled.kept.stopped_after == timedelta(seconds=8000)
    assert settled.kept.resume_command is None
    newest = max((states / name).stat().st_mtime for name in ("queue.chkpt", "vars.chkpt"))
    assert settled.kept.checkpoint_at == datetime.fromtimestamp(newest, tz=UTC)
    end(folder)
    assert start.path.is_dir()
    assert visit_sweep(runs, clock, "run0")  # released


def test_a_kept_folder_records_kept_keep_ended_size_and_reason(runs: Path, clock: FakeClock) -> None:
    start = started(runs, clock, keep=False, recover=None)
    write_checkpoint(start.path)
    start.abandon()
    resume = started(runs, clock, "run1", keep=True, recover=start.path / STATES)
    folder = resume.entered()
    clock.advance(60)
    settled = folder.settle(outcome(255))
    assert settled.kept is not None
    data = record(start.path)
    assert data["kept"] is True
    assert data["keep"] is True  # FC1
    assert data["ended"] == "2026-11-15T10:01:00Z"
    assert data["reason"] == "TLC crashed (exit 255)"
    assert data["size"] == settled.kept.size
    assert settled.kept.size >= 2 * len(b"checkpoint")
    end(folder)
    assert start.path.is_dir()
    assert not resume.path.exists()  # the new run's own folder holds no checkpoint


@pytest.mark.parametrize("process", [outcome(255), None])
def test_a_run_that_did_not_ask_drops_its_checkpoint(
    runs: Path, clock: FakeClock, process: ProcessOutcome | None
) -> None:
    start = started(runs, clock, keep=False)
    write_checkpoint(start.path)
    folder = start.entered()
    assert folder.settle(process) == folder.settle(None)
    assert folder.settle(None).kept is None
    assert folder.settle(None).dropped == "not-asked"
    end(folder)
    assert list_entries(runs) == []


@pytest.mark.parametrize(
    "names",
    [
        ("queue.chkpt", "vars.chkpt", "queue.tmp"),
        ("settings.tmp.chkpt",),
        ("queue.chkpt",),
    ],
    ids=["tmp-beside", "settings-tmp-alone", "vars-missing"],
)
def test_an_incomplete_checkpoint_is_not_kept(runs: Path, clock: FakeClock, names: tuple[str, ...]) -> None:
    start = started(runs, clock, keep=True)
    write_checkpoint(start.path, *names)
    assert complete_checkpoint(start.path) is None
    folder = start.entered()
    settled = folder.settle(outcome(255))
    assert settled.kept is None
    assert settled.dropped == "incomplete"
    end(folder)
    assert list_entries(runs) == []


def test_a_depth_first_run_cannot_be_resumed(runs: Path, clock: FakeClock) -> None:
    start = started(runs, clock, keep=True, tlc_args=["-dfid", "10"])
    write_checkpoint(start.path, "Spec_0.fp.chkpt", "Spec.st.chkpt")  # a -dfid checkpoint has no queue (TU7)
    settled = start.entered().settle(outcome(130, stopped_by="int"))
    assert settled.kept is None
    assert settled.dropped == "depth-first"


def test_no_checkpoint_is_nothing_dropped(runs: Path, clock: FakeClock) -> None:
    folder = started(runs, clock, keep=True).entered()
    assert folder.settle(outcome(255)) == folder.settle(None)
    assert folder.settle(None).kept is None
    assert folder.settle(None).dropped is None


def test_settle_decides_once(runs: Path, clock: FakeClock) -> None:
    start = started(runs, clock, keep=True)
    write_checkpoint(start.path)
    folder = start.entered()
    first = folder.settle(outcome(0))  # finished; then an exception passes and the frame settles again
    assert folder.settle(None) == first
    assert first.kept is None


def test_complete_checkpoint_names_the_timestamped_folder(tmp_path: Path) -> None:
    assert complete_checkpoint(tmp_path / "missing") is None
    assert complete_checkpoint(tmp_path) is None
    states = write_checkpoint(tmp_path)
    assert complete_checkpoint(tmp_path) == states


# ---------------------------------------------------------------------- the sweep


def test_a_kept_folder_survives_a_sweep_at_400_days(runs: Path, clock: FakeClock, paths: AppPaths) -> None:
    folder = kept(runs, clock, "old")
    clock.advance(timedelta(days=400).total_seconds())
    sweep(paths, clock.now)
    assert folder.is_dir()


def test_an_unsettled_folder_that_asked_with_a_complete_checkpoint_survives(
    runs: Path, clock: FakeClock, paths: AppPaths
) -> None:
    folder = unsettled(runs, clock, "old", keep=True, checkpoint=True)
    clock.advance(timedelta(days=400).total_seconds())
    sweep(paths, clock.now)
    assert folder.is_dir()


@pytest.mark.parametrize(("keep", "checkpoint"), [(False, True), (False, False), (True, False)])
def test_an_unsettled_folder_that_cannot_be_resumed_is_removed_at_once(
    runs: Path, clock: FakeClock, paths: AppPaths, keep: bool, checkpoint: bool
) -> None:
    folder = unsettled(runs, clock, "old", keep=keep, checkpoint=checkpoint)
    age(runs / "old.lock", START)
    sweep(paths, clock.now)
    assert not folder.exists()
    assert (runs / "old.lock").exists()  # a young lock file is left for the one-hour rule


def test_a_folder_without_run_json_is_removed_30_days_after_its_newest_file(
    runs: Path, clock: FakeClock, paths: AppPaths
) -> None:
    folder = runs / "pasted"
    states = write_checkpoint(folder)
    for path in (folder, states):
        age(path, START - timedelta(days=60))  # the folders' own times do not move while files grow
    for path in states.iterdir():
        age(path, START)
    clock.advance(timedelta(days=29).total_seconds())
    sweep(paths, clock.now)
    assert folder.is_dir()
    clock.advance(timedelta(days=2).total_seconds())
    sweep(paths, clock.now)
    assert not folder.exists()


def test_a_run_json_that_cannot_be_read_counts_as_none(runs: Path, clock: FakeClock, paths: AppPaths) -> None:
    folder = kept(runs, clock, "old")
    (folder / "run.json").write_text("{not json", encoding="utf-8")
    for path in (folder, *folder.rglob("*")):
        age(path, START)
    clock.advance(timedelta(days=29).total_seconds())
    sweep(paths, clock.now)
    assert folder.is_dir()  # a damaged kept folder is not lost at the next sweep
    clock.advance(timedelta(days=2).total_seconds())
    sweep(paths, clock.now)
    assert not folder.exists()


@pytest.mark.parametrize(("minutes", "removed"), [(59, False), (61, True)])
def test_a_lock_file_without_a_folder_goes_after_an_hour(
    runs: Path, clock: FakeClock, paths: AppPaths, minutes: int, removed: bool
) -> None:
    lock_file = runs / "starting.lock"
    lock_file.touch()
    age(lock_file, START)
    clock.advance(minutes * 60)
    sweep(paths, clock.now)
    assert lock_file.exists() is not removed


def test_the_sweep_leaves_entries_whose_lock_is_held_by_this_process(
    runs: Path, clock: FakeClock, paths: AppPaths
) -> None:
    folder = unsettled(runs, clock, "old", keep=False, checkpoint=False)
    orphan = runs / "starting.lock"
    orphan.touch()
    age(orphan, START - timedelta(hours=2))
    own = EntryVisit(runs, "old", clock.now)
    other = EntryVisit(runs, "starting", clock.now)
    assert own.take_lock()
    assert other.take_lock()
    try:
        assert not visit_sweep(runs, clock, "old")
        assert not visit_sweep(runs, clock, "starting")
        sweep(paths, clock.now)
        assert folder.is_dir()
        assert orphan.exists()
    finally:
        own.release()
        other.release()


def test_the_sweep_leaves_entries_whose_lock_another_process_holds(
    runs: Path, clock: FakeClock, paths: AppPaths, holder: list[subprocess.Popen[str]]
) -> None:
    folder = unsettled(runs, clock, "old", keep=False, checkpoint=False)
    orphan = runs / "starting.lock"
    orphan.touch()
    age(orphan, START - timedelta(hours=2))
    hold_in_another_process(holder, runs / "old.lock")
    hold_in_another_process(holder, orphan)
    sweep(paths, clock.now)
    assert folder.is_dir()
    assert orphan.exists()


def test_a_sweep_visit_leaves_a_new_empty_lock_file_behind(runs: Path, clock: FakeClock) -> None:
    folder = runs / "pasted"
    folder.mkdir()
    assert visit_sweep(runs, clock, "pasted")  # K1-7
    assert folder.is_dir()
    assert (runs / "pasted.lock").is_file()


def test_the_kept_summary_counts_the_recorded_sizes(runs: Path, clock: FakeClock, paths: AppPaths) -> None:
    kept(runs, clock, "a", size=1000)
    kept(runs, clock, "b", size=2500)
    unsettled(runs, clock, "c", keep=False, checkpoint=True)
    assert sweep(paths, clock.now) == KeptSummary(2, 3500)


def test_the_kept_summary_measures_a_folder_that_records_no_size(runs: Path, clock: FakeClock, paths: AppPaths) -> None:
    folder = kept(runs, clock, "a")
    data = record(folder)
    del data["size"]
    (folder / "run.json").write_text(json.dumps(data), encoding="utf-8")
    measured = sum(path.stat().st_size for path in folder.rglob("*") if path.is_file())
    assert sweep(paths, clock.now) == KeptSummary(1, measured)


def test_the_kept_summary_skips_a_kept_folder_whose_lock_is_held(runs: Path, clock: FakeClock) -> None:
    folder = kept(runs, clock, "a", size=1000)
    start = started(runs, clock, "run1", keep=False, recover=folder / STATES)  # it is being resumed
    assert start.sweep() == KeptSummary(0, 0)
    entered = start.entered()
    assert entered.kept_summary == KeptSummary(0, 0)
    entered.release_own()
    entered.release_recovered()


def test_a_start_sweeps_and_hands_the_summary_to_its_folder(runs: Path, clock: FakeClock) -> None:
    kept(runs, clock, "a", size=1000)
    start = started(runs, clock, "run1")
    assert start.sweep() == KeptSummary(1, 1000)
    folder = start.entered()
    assert folder.kept_summary == KeptSummary(1, 1000)
    end(folder)


# ---------------------------------------------------------------------- cache clean, one visit


def clean(runs: Path, clock: FakeClock, run_id: str, *, include_kept: bool) -> bool:
    visit = EntryVisit(runs, run_id, clock.now)
    assert visit.take_lock()
    try:
        return visit.clean(include_kept=include_kept)
    finally:
        visit.release()


def resumable_kept_and_pasted(runs: Path, clock: FakeClock) -> list[Path]:
    pasted = runs / "pasted"
    pasted.mkdir()
    return [
        unsettled(runs, clock, "resumable", keep=True, checkpoint=True),
        kept(runs, clock, "kept"),
        pasted,
    ]


def test_clean_leaves_what_can_be_resumed_and_what_tlaup_did_not_make(runs: Path, clock: FakeClock) -> None:
    folders = resumable_kept_and_pasted(runs, clock)
    for folder in folders:
        assert not clean(runs, clock, folder.name, include_kept=False)
        assert folder.is_dir()


def test_clean_with_include_kept_removes_them_with_their_lock_files(runs: Path, clock: FakeClock) -> None:
    for folder in resumable_kept_and_pasted(runs, clock):
        assert clean(runs, clock, folder.name, include_kept=True)
        assert not folder.exists()
    assert list_entries(runs) == []


def test_clean_removes_an_unsettled_folder_that_cannot_be_resumed(runs: Path, clock: FakeClock) -> None:
    folder = unsettled(runs, clock, "old", keep=False, checkpoint=True)
    assert clean(runs, clock, "old", include_kept=False)
    assert not folder.exists()
    assert not (runs / "old.lock").exists()


def test_a_visit_to_a_held_entry_is_refused(runs: Path, clock: FakeClock) -> None:
    started(runs, clock)
    assert not EntryVisit(runs, "run0", clock.now).take_lock()


# ---------------------------------------------------------------------- list_entries and the end


def test_list_entries(runs: Path, clock: FakeClock) -> None:
    (runs / "a").mkdir()
    (runs / "b.lock").touch()
    (runs / ".lock").touch()
    (runs / "notes.txt").touch()
    assert list_entries(runs) == ["a", "b"]
    assert list_entries(runs, folders_only=True) == ["a"]
    assert list_entries(runs.parent / "missing") == []


def test_the_end_deletes_the_folder_and_removes_the_lock_file_under_the_lock(runs: Path, clock: FakeClock) -> None:
    folder = started(runs, clock).entered()
    folder.settle(outcome(0))
    folder.end_own()
    assert not (runs / "run0").exists()
    assert not (runs / "run0.lock").exists()
    folder.release_own()
    assert list_entries(runs) == []


def test_a_start_that_failed_at_its_own_lock_leaves_its_lock_file(runs: Path, clock: FakeClock) -> None:
    started(runs, clock)
    second = RunStart(runs, clock.now, run_id="run0", wait=0)
    with pytest.raises(FileOperationError):
        second.take_lock()
    folder = second.entered()
    end(folder)
    assert (runs / "run0").is_dir()  # the other holder's folder is untouched
    assert (runs / "run0.lock").exists()
