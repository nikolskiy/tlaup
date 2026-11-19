"""Stateful property test of the run folders (design 11 R6): the mirror of specs/RunFolders.tla.

Each tlaup process of the spec is a ``Proc`` holding its own step objects, and so its own
lock objects, and its position in the protocol. Each action of the spec is a rule with the
action's enabling condition as its precondition. The safety properties are checked on the
real files after every step. Time is the injected ``now``; a lock file's age is set with
``os.utime``.

What differs from the spec, and why:

- A lock attempt is one call (``take_lock``), not an open and a flock: the lock library
  does both, and nothing can be interleaved between them from outside.
- The spec lets each sweep visit choose the age it finds; here one clock moves forward.
- A killed tlaup is a ``Proc`` whose step objects are dropped, which releases their locks
  as the operating system would.

The machine runs against ``tlaup.tlc.rundirs`` (marked ``pending`` until that module is
built) and against the throwaway model in ``reference_rundirs.py``.
"""

from __future__ import annotations

import gc
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("hypothesis")
filelock = pytest.importorskip("filelock")

from hypothesis import settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402
from hypothesis.stateful import (  # noqa: E402
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)

PROJECT_ROOT = Path(__file__).parents[2]
PROCESSES = 3
MAX_RUNS = 4
MAX_KILLS = 1  # as in the spec's model; more would seldom let a run get anywhere
MAX_FAILURES = 2  # lock timeouts and aborted starts in one example, for the same reason
KEEP = timedelta(days=30)
STATES = "states"  # stands for TLC's timestamped folder


def reference_impl() -> SimpleNamespace:
    module = importlib.import_module("tests.stateful.reference_rundirs")
    return SimpleNamespace(
        name=module.__name__,
        rundirs=module,
        errors=(module.FileOperationError,),
        outcome=lambda code: module.ProcessOutcome(exit_code=code),
    )


def tlaup_impl() -> SimpleNamespace:
    rundirs = importlib.import_module("tlaup.tlc.rundirs")
    errors = importlib.import_module("tlaup.errors")
    launcher = importlib.import_module("tlaup.java.launcher")
    return SimpleNamespace(
        name=rundirs.__name__,
        rundirs=rundirs,
        errors=(errors.FileOperationError,),
        outcome=lambda code: launcher.ProcessOutcome(
            exit_code=code, tool_exit_code=code, stopped_by=None, stderr_tail=()
        ),
    )


@dataclass
class Proc:
    """One tlaup process: its step objects (and so its locks) and where it is."""

    name: str
    pc: str = "idle"
    mode: str = "run"
    run: str | None = None
    target: str | None = None
    recover_locked: bool = False
    made_folder: bool = False
    start: Any = None
    folder: Any = None
    visit: Any = None
    visiting: str | None = None
    snap: list[str] = field(default_factory=list)
    kept: bool = False
    held: dict[str, int] = field(default_factory=dict)  # run id -> inode of the lock file it holds

    def forget(self) -> None:
        self.pc, self.mode, self.run, self.target, self.recover_locked = "idle", "run", None, None, False
        self.start = self.folder = self.visit = None
        self.visiting, self.snap, self.kept, self.made_folder = None, [], False, False
        self.held = {}


class RunFoldersMachine(RuleBasedStateMachine):
    impl: SimpleNamespace
    base: Path

    def __init__(self) -> None:
        super().__init__()
        self.root = Path(tempfile.mkdtemp(dir=self.base))
        self.runs = self.root / "runs"
        self.runs.mkdir()
        self.clock = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
        self.procs = [Proc(f"p{i}") for i in range(PROCESSES)]
        self.counter = 0
        self.tlc: dict[str, str] = {}  # run id -> "live", "orphan" or "done"
        self.where: dict[str, set[str]] = {}  # run id -> the folders its TLC works in
        self.checkpoints: dict[str, str] = {}  # run id -> the folder its TLC writes checkpoints in
        self.kills = 0
        self.failures = 0
        self.before: dict[str, dict[str, Any]] = {}
        self.may_remove_kept: set[str] = set()
        self.stamped: set[int] = set()

    def teardown(self) -> None:
        for proc in self.procs:
            proc.forget()
        gc.collect()
        shutil.rmtree(self.root, ignore_errors=True)

    # ------------------------------------------------------------------ helpers

    def now(self) -> datetime:
        return self.clock

    def at(self, *pcs: str) -> list[Proc]:
        return [proc for proc in self.procs if proc.pc in pcs]

    def lock_file(self, run_id: str) -> Path:
        return self.runs / f"{run_id}.lock"

    def holders(self, run_id: str) -> list[Proc]:
        return [proc for proc in self.procs if run_id in proc.held]

    def note_held(self, proc: Proc, run_id: str) -> None:
        proc.held[run_id] = self.lock_file(run_id).stat().st_ino

    def note_unlinked(self, proc: Proc, run_id: str | None) -> None:
        """Forget a hold whose file the process has removed: it only has the release left."""
        if run_id is None or run_id not in proc.held:
            return
        path = self.lock_file(run_id)
        if not path.exists() or path.stat().st_ino != proc.held[run_id]:
            del proc.held[run_id]

    def scan(self) -> dict[str, dict[str, Any]]:
        found: dict[str, dict[str, Any]] = {}
        for entry in self.runs.iterdir():
            if not entry.is_dir():
                continue
            try:
                record = json.loads((entry / "run.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                record = {}
            ended = record.get("ended")
            found[entry.name] = {
                "kept": bool(record.get("kept")),
                "ended": datetime.fromisoformat(ended) if ended else None,
                "checkpoint": any(entry.rglob("*.chkpt")),
            }
        return found

    def ending_tlc(self, proc: Proc) -> None:
        """The run function returns: the step objects of the start hand over to the folder."""
        proc.folder = proc.start.entered()
        proc.start = None

    # ------------------------------------------------------------------ earlier runs

    @initialize(data=st.data())
    def earlier_runs(self, data: st.DataObject) -> None:
        """Leave behind what earlier runs left, made with the same steps, then let time pass.

        Random steps alone seldom get as far as a kept folder; with this the interleaving
        starts where a kept folder, or the folder of a killed tlaup, is already there.
        """
        endings = ["kept", "killed", "killed with a checkpoint", "lock file only"]
        for index in range(data.draw(st.integers(0, 2), label="earlier runs")):
            ending = data.draw(st.sampled_from(endings), label="ending")
            start = self.impl.rundirs.RunStart(self.runs, self.now, run_id=f"old{index}", wait=0)
            start.create_lock_file()
            start.take_lock()
            if ending != "lock file only":
                start.make_folder()
                start.write_run_json()
            if ending in {"kept", "killed with a checkpoint"}:
                (start.path / STATES).mkdir()
                (start.path / STATES / "queue.chkpt").write_bytes(b"")
            if ending == "kept":
                folder = start.entered()
                assert folder.settle(self.impl.outcome(255)) is not None
                folder.end_own()
                folder.release_own()
            del start
            gc.collect()
        self.files_obey_the_properties()
        self.clock += data.draw(st.sampled_from([timedelta(0), timedelta(days=2), timedelta(days=31)]), label="later")

    # ------------------------------------------------------------------ start

    @precondition(lambda self: self.at("idle") and self.counter < MAX_RUNS)
    @rule(data=st.data())
    def create_lock_file(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("idle")), label="process")
        folders = sorted(self.scan())
        target = data.draw(st.sampled_from([None, *folders]), label="-recover into")
        run_id = f"run{self.counter}"
        self.counter += 1
        recover = self.runs / target / STATES if target else None
        proc.start = self.impl.rundirs.RunStart(self.runs, self.now, run_id=run_id, recover=recover, wait=0)
        proc.start.create_lock_file()
        proc.run, proc.target, proc.mode, proc.pc = run_id, target, "run", "lock"

    @precondition(lambda self: self.at("lock"))
    @rule(data=st.data())
    def take_lock(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("lock")), label="process")
        free = not self.holders(proc.run)
        try:
            proc.start.take_lock()
        except self.impl.errors:
            assert not free, "the run's own lock was free and could not be taken"
            return
        assert free, "the run's own lock was taken while another lock object held it"
        self.note_held(proc, proc.run)
        proc.pc = "rlock" if proc.target else "mkdir"

    @precondition(lambda self: self.at("lock") and self.failures < MAX_FAILURES)
    @rule(data=st.data())
    def take_lock_timeout(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("lock")), label="process")
        self.failures += 1
        proc.forget()
        gc.collect()

    @precondition(lambda self: self.at("rlock"))
    @rule(data=st.data())
    def take_recover_lock(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("rlock")), label="process")
        there = (self.runs / proc.target).is_dir()
        free = not self.holders(proc.target)
        try:
            proc.start.take_recover_lock()
        except self.impl.errors:
            assert there, "a folder that is gone has no lock to wait for"
            assert not free, "the recovered folder's lock was free and could not be taken"
            return
        if there:
            assert free, "the recovered folder's lock was taken while another lock object held it"
            self.note_held(proc, proc.target)
            proc.recover_locked = True
        proc.pc = "mkdir"

    @precondition(lambda self: self.at("rlock") and self.failures < MAX_FAILURES)
    @rule(data=st.data())
    def recover_refused(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("rlock")), label="process")
        self.failures += 1
        self.ending_tlc(proc)
        proc.kept = False
        proc.pc = "eOwn"

    @precondition(lambda self: self.at("mkdir"))
    @rule(data=st.data())
    def make_folder(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("mkdir")), label="process")
        proc.start.make_folder()
        proc.made_folder = True
        proc.pc = "json"

    @precondition(lambda self: self.at("json"))
    @rule(data=st.data())
    def write_run_json(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("json")), label="process")
        proc.start.write_run_json()
        proc.snap = self.impl.rundirs.list_entries(self.runs)
        proc.pc = "visit"

    def ready_to_start(self) -> list[Proc]:
        return [proc for proc in self.at("visit") if proc.mode == "run" and not proc.snap]

    @precondition(lambda self: (self.at("mkdir", "json") or self.ready_to_start()) and self.failures < MAX_FAILURES)
    @rule(data=st.data())
    def abort_start(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("mkdir", "json") + self.ready_to_start()), label="process")
        self.failures += 1
        self.ending_tlc(proc)
        proc.pc = "settle"

    # ------------------------------------------------------------------ sweep and cache clean

    @precondition(lambda self: self.at("idle"))
    @rule(data=st.data(), mode=st.sampled_from(["sweep", "clean", "cleanAll"]))
    def begin_sweep_or_clean(self, data: st.DataObject, mode: str) -> None:
        proc = data.draw(st.sampled_from(self.at("idle")), label="process")
        proc.mode = mode
        proc.snap = self.impl.rundirs.list_entries(self.runs, folders_only=mode != "sweep")
        proc.pc = "visit"

    @precondition(lambda self: any(proc.snap for proc in self.at("visit")))
    @rule(data=st.data())
    def visit_take_lock(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from([p for p in self.at("visit") if p.snap]), label="process")
        run_id = data.draw(st.sampled_from(proc.snap), label="entry")
        proc.snap.remove(run_id)
        free = not self.holders(run_id)
        visit = self.impl.rundirs.EntryVisit(self.runs, run_id, self.now)
        got = visit.take_lock()
        assert got == free, f"take_lock gave {got} with the lock {'free' if free else 'held'}"
        if got:
            proc.visit, proc.visiting, proc.pc = visit, run_id, "visit3"
            self.note_held(proc, run_id)

    @precondition(lambda self: self.at("visit3"))
    @rule(data=st.data())
    def visit_act(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("visit3")), label="process")
        if proc.mode in {"run", "sweep"}:
            proc.visit.sweep()
        else:
            folder = self.runs / proc.visiting
            resumable = folder.is_dir() and (folder / "run.json").exists() and any(folder.rglob("*.chkpt"))
            proc.visit.clean(include_kept=proc.mode == "cleanAll")
            if proc.mode == "cleanAll":
                self.may_remove_kept.add(proc.visiting)
            else:
                assert not resumable or folder.is_dir(), f"CheckpointSurvives: cache clean removed {proc.visiting}"
        self.note_unlinked(proc, proc.visiting)
        proc.pc = "visit4"

    @precondition(lambda self: self.at("visit4"))
    @rule(data=st.data())
    def visit_release(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("visit4")), label="process")
        proc.visit.release()
        proc.held.pop(proc.visiting, None)
        proc.visit, proc.visiting, proc.pc = None, None, "visit"

    @precondition(lambda self: any(not p.snap and p.mode != "run" for p in self.at("visit")))
    @rule(data=st.data())
    def visit_done(self, data: st.DataObject) -> None:
        done = [p for p in self.at("visit") if not p.snap and p.mode != "run"]
        data.draw(st.sampled_from(done), label="process").forget()

    # ------------------------------------------------------------------ the run, settle, end

    @precondition(lambda self: self.ready_to_start())
    @rule(data=st.data())
    def start_tlc(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.ready_to_start()), label="process")
        self.tlc[proc.run] = "live"
        self.where[proc.run] = {proc.run, proc.target} if proc.recover_locked else {proc.run}
        self.checkpoints[proc.run] = proc.target if proc.recover_locked else proc.run
        proc.pc = "tlc"

    def running(self) -> list[str]:
        return sorted(run_id for run_id, state in self.tlc.items() if state in {"live", "orphan"})

    @precondition(lambda self: self.running())
    @rule(data=st.data())
    def tlc_checkpoint(self, data: st.DataObject) -> None:
        run_id = data.draw(st.sampled_from(self.running()), label="TLC of")
        folder = self.runs / self.checkpoints[run_id]
        if folder.is_dir():  # a TLC whose folder was deleted crashes instead (research 17)
            (folder / STATES).mkdir(exist_ok=True)
            (folder / STATES / "queue.chkpt").write_bytes(b"")

    @precondition(lambda self: self.at("tlc"))
    @rule(data=st.data())
    def tlc_exit(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("tlc")), label="process")
        self.tlc[proc.run] = "done"
        self.ending_tlc(proc)
        proc.pc = "settle"

    @precondition(lambda self: "orphan" in self.tlc.values())
    @rule(data=st.data())
    def orphan_exit(self, data: st.DataObject) -> None:
        orphans = sorted(run_id for run_id, state in self.tlc.items() if state == "orphan")
        self.tlc[data.draw(st.sampled_from(orphans), label="TLC of")] = "done"

    @precondition(lambda self: self.at("settle"))
    @rule(data=st.data(), finished=st.booleans())
    def settle(self, data: st.DataObject, finished: bool) -> None:
        proc = data.draw(st.sampled_from(self.at("settle")), label="process")
        ran = self.tlc.get(proc.run) == "done"
        finished = finished and ran
        outcome = self.impl.outcome(0 if finished else 255) if ran else None
        settled = self.runs / (proc.target if proc.recover_locked else proc.run)
        expected = not finished and settled.is_dir() and any(settled.rglob("*.chkpt"))
        kept = proc.folder.settle(outcome)
        assert (kept is not None) == expected, f"settle kept {kept}, expected kept={expected}"
        assert proc.folder.settle(None) == kept, "a second settle changed the answer"
        proc.kept = kept is not None
        proc.pc = "eOwn"

    @precondition(lambda self: self.at("eOwn"))
    @rule(data=st.data())
    def end_own(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("eOwn")), label="process")
        proc.folder.end_own()
        self.note_unlinked(proc, proc.run)
        proc.pc = "eOwnRel"

    @precondition(lambda self: self.at("eOwnRel"))
    @rule(data=st.data())
    def release_own(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("eOwnRel")), label="process")
        proc.folder.release_own()
        proc.held.pop(proc.run, None)
        if proc.recover_locked:
            proc.pc = "eRec"
        else:
            proc.forget()

    @precondition(lambda self: self.at("eRec"))
    @rule(data=st.data())
    def end_recovered(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("eRec")), label="process")
        if not proc.kept:
            self.may_remove_kept.add(proc.target)  # the resumed run finished: R6, -recover rule 3
        proc.folder.end_recovered()
        self.note_unlinked(proc, proc.target)
        proc.pc = "eRecRel"

    @precondition(lambda self: self.at("eRecRel"))
    @rule(data=st.data())
    def release_recovered(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("eRecRel")), label="process")
        proc.folder.release_recovered()
        proc.forget()

    # ------------------------------------------------------------------ the environment

    @precondition(lambda self: self.kills < MAX_KILLS and any(proc.pc != "idle" for proc in self.procs))
    @rule(data=st.data())
    def kill(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from([p for p in self.procs if p.pc != "idle"]), label="process")
        self.kills += 1
        held = list(proc.held)
        if proc.run and self.tlc.get(proc.run) == "live":
            self.tlc[proc.run] = "orphan"
        proc.forget()
        gc.collect()
        for run_id in held:  # the simulated kill must have released the locks, as the system would
            if self.lock_file(run_id).exists() and not self.holders(run_id):
                probe = filelock.FileLock(self.lock_file(run_id))
                probe.acquire(blocking=False)
                probe.release()

    @precondition(lambda self: any(self.runs.glob("*.lock")))
    @rule(data=st.data())
    def age_lock_file(self, data: st.DataObject) -> None:
        path = data.draw(st.sampled_from(sorted(self.runs.glob("*.lock"))), label="lock file")
        old = (self.clock - timedelta(hours=2)).timestamp()
        os.utime(path, (old, old))

    @rule(days=st.sampled_from([1, 31]))
    def time_passes(self, days: int) -> None:
        self.clock += timedelta(days=days, minutes=1)

    # ------------------------------------------------------------------ the properties, on the files

    @invariant()
    def files_obey_the_properties(self) -> None:
        current = self.scan()
        for run_id, was in self.before.items():
            if run_id in current:
                continue
            under = [r for r, state in self.tlc.items() if state == "live" and run_id in self.where[r]]
            assert not under, f"NoDeleteUnderTLC: {run_id} was deleted under the TLC of {under}"
            young = was["ended"] is not None and self.clock - was["ended"] <= KEEP
            if was["kept"] and was["checkpoint"] and young:
                assert run_id in self.may_remove_kept, f"KeptSurvives: {run_id} was removed"
        self.before = current
        self.may_remove_kept = set()
        for path in self.runs.iterdir():  # what a step made is as old as the injected clock says
            inode = path.stat().st_ino
            if inode not in self.stamped:
                self.stamped.add(inode)
                os.utime(path, (self.clock.timestamp(), self.clock.timestamp()))

    @invariant()
    def held_lock_is_on_the_file_at_the_name(self) -> None:
        for proc in self.procs:
            for run_id, inode in proc.held.items():
                path = self.lock_file(run_id)
                assert path.exists(), f"HeldIsCurrent: {proc.name} holds {path.name}, which is gone"
                assert path.stat().st_ino == inode, f"HeldIsCurrent: {path.name} was replaced under {proc.name}"

    @invariant()
    def one_lock_object_per_name(self) -> None:
        for run_id in {run_id for proc in self.procs for run_id in proc.held}:
            names = [proc.name for proc in self.holders(run_id)]
            assert len(names) == 1, f"LockExclusive: {names} all hold the lock of {run_id}"

    @invariant()
    def live_run_has_its_folder_and_lock(self) -> None:
        for proc in self.procs:
            if proc.mode == "run" and proc.pc in {"json", "visit", "visit3", "visit4", "tlc", "settle"}:
                assert proc.run in proc.held, f"LiveRunLocked: {proc.name} lost the lock of {proc.run}"
                if proc.made_folder:
                    assert (self.runs / proc.run).is_dir(), f"LiveRunLocked: the folder of {proc.run} is gone"

    @invariant()
    def one_tlc_per_folder(self) -> None:
        live = [run_id for run_id, state in self.tlc.items() if state == "live"]
        for folder in {f for run_id in live for f in self.where[run_id]}:
            writers = [run_id for run_id in live if folder in self.where[run_id]]
            assert len(writers) <= 1, f"OneTLCPerFolder: {writers} all work in {folder}"


def run_machine(impl: SimpleNamespace, base: Path) -> None:
    machine = type("RunFolders", (RunFoldersMachine,), {"impl": impl, "base": base})
    run_state_machine_as_test(machine, settings=settings(stateful_step_count=80))


def test_run_folders_machine_against_the_reference_model(tmp_path: Path) -> None:
    run_machine(reference_impl(), tmp_path)


@pytest.mark.pending
def test_run_folders_machine(tmp_path: Path) -> None:
    run_machine(tlaup_impl(), tmp_path)


# One lock object in this process must stand for another tlaup process: the machine above
# rests on it. A second Python process confirms it for the run folders' own lock step.

CHILD = """
import importlib, sys
from datetime import UTC, datetime
from pathlib import Path
module, runs, run_id, hold = sys.argv[1:5]
visit = importlib.import_module(module).EntryVisit(Path(runs), run_id, lambda: datetime.now(UTC))
got = visit.take_lock()
print(got, flush=True)
if got and hold == "hold":
    sys.stdin.readline()
"""


def child(module: str, runs: Path, run_id: str, *, hold: bool) -> subprocess.Popen[str]:
    argv = [sys.executable, "-c", CHILD, module, str(runs), run_id, "hold" if hold else "once"]
    return subprocess.Popen(argv, cwd=PROJECT_ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)


def second_process_agrees(impl: SimpleNamespace, runs: Path) -> None:
    now = lambda: datetime.now(UTC)  # noqa: E731
    first = impl.rundirs.EntryVisit(runs, "run0", now)
    second = impl.rundirs.EntryVisit(runs, "run0", now)

    assert first.take_lock()
    assert not second.take_lock(), "a second lock object in this process got a held lock"
    other = child(impl.name, runs, "run0", hold=False)
    assert other.communicate(timeout=30)[0].strip() == "False", "another process got a held lock"
    first.release()

    other = child(impl.name, runs, "run0", hold=True)
    try:
        assert other.stdout is not None
        assert other.stdout.readline().strip() == "True", "another process could not take a free lock"
        assert not second.take_lock(), "this process got a lock that another process holds"
    finally:
        other.communicate("\n", timeout=30)
    assert second.take_lock(), "the lock of a process that has exited was not free"
    second.release()


def test_a_lock_object_stands_for_a_process_reference_model(tmp_path: Path) -> None:
    second_process_agrees(reference_impl(), tmp_path)


@pytest.mark.pending
def test_a_lock_object_stands_for_a_process(tmp_path: Path) -> None:
    second_process_agrees(tlaup_impl(), tmp_path)
