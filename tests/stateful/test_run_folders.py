"""Stateful property test of the run folders (design 11 R6): the mirror of specs/RunFolders.tla.

Each tlaup process of the spec is a ``Proc`` holding its own step objects, and so its own
lock objects, and its position in the protocol. Each action of the spec is a rule with the
action's enabling condition as its precondition. The safety properties are checked on the
real files after every step. Time is the injected ``now``; a lock file's age is set with
``os.utime``.

Revised 2026-11-20 for the spec's revision (decisions D51 to D53): each run is started with
or without ``keep``; TLC writes a checkpoint in two rules, the ``.tmp`` files and then the
commit; a started TLC is a real child process (the JVM stand-in) that inherits duplicates of
the run's lock descriptors; a kill closes the tlaup's descriptors without unlocking, so the
child keeps the locks until the rule for the orphan's exit ends it.

Platform setting: the machine models the spec with ``LockFollowsTLC = TRUE``, which is
Linux and macOS (an inherited ``flock``). ``NoDeleteUnderTLC`` and ``OneTLCPerFolder`` are
therefore checked without the exception for a killed tlaup. The Windows forms
(``LockFollowsTLC = FALSE``, the window of finding K1-8) are not tested, and the module is
skipped on Windows (decision D15).

What differs from the spec, and why:

- A lock attempt is one call (``take_lock``), not an open and a flock: the lock code does
  both, and nothing can be interleaved between them from outside.
- The spec lets each sweep visit choose the age it finds; here one clock moves forward.
- A killed tlaup is a ``Proc`` whose step objects close their descriptors without unlocking
  (``abandon``), as the operating system does at a kill; a visit's ``FileLock`` is released.
- The orphan's end is a rule that may fire at any later step, as the spec's ``OrphanExit``;
  the lifeline's own timing is G3's test, not this one's.
- ``UnlinkOnRelease`` and ``cache clean <run-id>`` are not mirrored: the first is a property
  of a library version, pinned by R6's unit tests; the second is ``--all`` for one entry.
- A deletion never fails here, although the spec's main config has ``DeleteMayFail`` on: a
  failed deletion needs file-system tricks (a folder made unwritable, which root ignores).
  The spec checks those behaviours; FC1 of the 2026-11-20 review was found through one, and
  its replay below reaches the same state through a kill instead.

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
pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="models LockFollowsTLC = TRUE (an inherited flock: Linux, macOS); D15"
)

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
STATES = "states"  # stands for TLC's timestamped folder
LOCK_FOLLOWS_TLC = True  # the spec's constant: Linux and macOS (see the module's docstring)
JVM = "import sys; sys.stdin.readline()"  # the JVM stand-in: holds what it inherited until told to end


def complete(folder: Path) -> bool:
    """The completeness test of D52, written here apart from the code under test."""
    if not folder.is_dir():
        return False
    names = [p.name for p in folder.rglob("*")]
    if any(name.endswith(".tmp") or name == "settings.tmp.chkpt" for name in names):
        return False
    return (folder / STATES / "queue.chkpt").exists() and (folder / STATES / "vars.chkpt").exists()


def any_checkpoint(folder: Path) -> bool:
    return any(folder.rglob("*.chkpt")) or any(folder.rglob("*.tmp"))


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
    finished: bool = False
    keep: bool = False  # what the run asked for (--keep), drawn when it starts
    target_keep: bool = False  # the folder -recover names asked to be kept
    held: dict[str, int] = field(default_factory=dict)  # run id -> inode of the lock file it holds

    def forget(self) -> None:
        self.pc, self.mode, self.run, self.target, self.recover_locked = "idle", "run", None, None, False
        self.start = self.folder = self.visit = None
        self.visiting, self.snap, self.kept, self.made_folder = None, [], False, False
        self.finished = self.keep = self.target_keep = False
        self.held = {}

    def keeps(self) -> bool:
        """The run is a kept run: it asked, or it resumes a folder that asked (D53)."""
        return self.keep or (self.recover_locked and self.target_keep)


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
        self.jvm: dict[str, subprocess.Popen[str]] = {}  # run id -> the JVM stand-in of its TLC
        self.orphan_held: dict[str, dict[str, int]] = {}  # run id of an orphan TLC -> the locks it holds
        self.begun: set[str] = set()  # run ids whose TLC has begun a checkpoint and not committed it
        self.kills = 0
        self.failures = 0
        self.before: dict[str, dict[str, Any]] = {}
        self.may_remove: set[str] = set()  # folders a step may remove although they could be resumed
        self.stamped: set[int] = set()

    def teardown(self) -> None:
        for proc in self.procs:
            self.abandon(proc)
            proc.forget()
        for child in self.jvm.values():
            if child.poll() is None:
                child.kill()
            child.communicate()
        gc.collect()
        shutil.rmtree(self.root, ignore_errors=True)

    # ------------------------------------------------------------------ helpers

    def now(self) -> datetime:
        return self.clock

    def at(self, *pcs: str) -> list[Proc]:
        return [proc for proc in self.procs if proc.pc in pcs]

    def lock_file(self, run_id: str) -> Path:
        return self.runs / f"{run_id}.lock"

    def holders(self, run_id: str) -> list[str]:
        """Every lock object that holds the lock of ``run_id``: a tlaup's, or an orphan TLC's."""
        procs = [proc.name for proc in self.procs if run_id in proc.held]
        return procs + [f"TLC of {r}" for r, held in self.orphan_held.items() if run_id in held]

    def probe(self, run_id: str) -> bool:
        """One attempt by a lock object of the test's own; True if it got the lock (released at once)."""
        lock = filelock.FileLock(self.lock_file(run_id))
        try:
            lock.acquire(timeout=0)
        except filelock.Timeout:
            return False
        lock.release()
        return True

    def abandon(self, proc: Proc) -> None:
        """What a kill does to a tlaup's descriptors: closed, nothing unlocked."""
        for steps in (proc.start, proc.folder):
            if steps is not None:
                steps.abandon()
        if proc.visit is not None and proc.visiting in proc.held:
            proc.visit.release()  # a visit's lock is the process's alone; closing it frees it

    def end_jvm(self, run_id: str) -> None:
        child = self.jvm.pop(run_id)
        child.communicate("\n", timeout=30)

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
                "json": bool(record),
                "kept": bool(record.get("kept")),
                "keep": bool(record.get("keep")),
                "ended": datetime.fromisoformat(ended) if ended else None,
                "complete": complete(entry),
            }
        return found

    def enter(self, proc: Proc) -> None:
        """The run folder is entered: the step objects of the start hand over to the folder."""
        if proc.folder is None:
            proc.folder = proc.start.entered()
            proc.start = None

    # ------------------------------------------------------------------ earlier runs

    @initialize(data=st.data())
    def earlier_runs(self, data: st.DataObject) -> None:
        """Leave behind what earlier runs left, made with the same steps, then let time pass.

        Random steps alone seldom get as far as a kept folder; with this the interleaving
        starts where a kept folder, or the folder of a killed tlaup, is already there.
        """
        endings = ["kept", "killed", "killed with a checkpoint", "killed in a checkpoint", "lock file only"]
        for index in range(data.draw(st.integers(0, 2), label="earlier runs")):
            ending = data.draw(st.sampled_from(endings), label="ending")
            keep = ending == "kept" or data.draw(st.booleans(), label="--keep")
            start = self.impl.rundirs.RunStart(self.runs, self.now, run_id=f"old{index}", info={"keep": keep}, wait=0)
            start.create_lock_file()
            start.take_lock()
            if ending != "lock file only":
                start.make_folder()
                start.write_run_json()
            if ending in {"kept", "killed with a checkpoint", "killed in a checkpoint"}:
                (start.path / STATES).mkdir()
                (start.path / STATES / "queue.chkpt").write_bytes(b"")
                (start.path / STATES / "vars.chkpt").write_bytes(b"")
            if ending == "killed in a checkpoint":
                (start.path / STATES / "queue.tmp").write_bytes(b"")
            if ending == "kept":
                folder = start.entered()
                assert folder.settle(self.impl.outcome(255)).kept is not None
                folder.end_own()
                folder.release_own()
            else:
                start.abandon()  # killed: its TLC has ended since
            del start
            gc.collect()
        self.files_obey_the_properties()
        self.clock += data.draw(st.sampled_from([timedelta(0), timedelta(days=2), timedelta(days=31)]), label="later")
        if data.draw(st.booleans(), label="a run in progress"):
            # A run already as far as its TLC, through the same steps: otherwise a kill seldom
            # lands while a TLC runs, which is the kill D51 is about.
            proc = self.procs[0]
            keep = data.draw(st.booleans(), label="--keep")
            proc.run, proc.mode, proc.keep = f"run{self.counter}", "run", keep
            self.counter += 1
            proc.start = self.impl.rundirs.RunStart(self.runs, self.now, run_id=proc.run, info={"keep": keep}, wait=0)
            proc.start.create_lock_file()
            proc.start.take_lock()
            self.note_held(proc, proc.run)
            proc.start.make_folder()
            proc.made_folder = True
            proc.start.write_run_json()
            proc.start.sweep()
            self.files_obey_the_properties()
            self.start_the_tlc(proc)

    # ------------------------------------------------------------------ start

    @precondition(lambda self: self.at("idle") and self.counter < MAX_RUNS)
    @rule(data=st.data())
    def create_lock_file(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("idle")), label="process")
        folders = self.scan()
        target = data.draw(st.sampled_from([None, *sorted(folders)]), label="-recover into")
        keep = data.draw(st.booleans(), label="--keep")
        run_id = f"run{self.counter}"
        self.counter += 1
        recover = self.runs / target / STATES if target else None
        proc.start = self.impl.rundirs.RunStart(
            self.runs, self.now, run_id=run_id, recover=recover, info={"keep": keep}, wait=0
        )
        proc.start.create_lock_file()
        proc.run, proc.target, proc.mode, proc.pc = run_id, target, "run", "lock"
        proc.keep = keep
        proc.target_keep = bool(target and (folders[target]["keep"] or folders[target]["kept"]))

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
        self.enter(proc)
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
        record = json.loads((self.runs / proc.run / "run.json").read_text(encoding="utf-8"))
        asked = proc.keeps()
        assert record.get("keep") == asked, f"run.json says keep={record.get('keep')}, the run asked {asked}"
        proc.snap = self.impl.rundirs.list_entries(self.runs)
        proc.pc = "visit"

    def ready_to_start(self) -> list[Proc]:
        return [proc for proc in self.at("visit") if proc.mode == "run" and not proc.snap]

    @precondition(lambda self: (self.at("mkdir", "json") or self.ready_to_start()) and self.failures < MAX_FAILURES)
    @rule(data=st.data())
    def abort_start(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("mkdir", "json") + self.ready_to_start()), label="process")
        self.failures += 1
        self.enter(proc)
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
        folder = self.runs / proc.visiting
        was = self.scan().get(proc.visiting)
        if proc.mode in {"run", "sweep"}:
            proc.visit.sweep()
            if was is not None and was["json"] and not was["kept"] and not (was["keep"] and was["complete"]):
                assert not folder.exists(), f"D53: the sweep left {proc.visiting}, unsettled and not resumable"
        else:
            proc.visit.clean(include_kept=proc.mode == "cleanAll")
            if proc.mode == "cleanAll":
                self.may_remove.add(proc.visiting)
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
        self.start_the_tlc(data.draw(st.sampled_from(self.ready_to_start()), label="process"))

    def start_the_tlc(self, proc: Proc) -> None:
        self.enter(proc)  # the frame has entered the run folder before the child starts
        fds = proc.folder.lock_fds
        try:  # the launcher: Popen with the duplicates, then close tlaup's copies of them
            self.jvm[proc.run] = subprocess.Popen(
                [sys.executable, "-c", JVM], stdin=subprocess.PIPE, pass_fds=fds, text=True
            )
        finally:
            for fd in fds:
                os.close(fd)
        self.tlc[proc.run] = "live"
        self.where[proc.run] = {proc.run, proc.target} if proc.recover_locked else {proc.run}
        self.checkpoints[proc.run] = proc.target if proc.recover_locked else proc.run
        proc.pc = "tlc"

    def running(self) -> list[str]:
        return sorted(run_id for run_id, state in self.tlc.items() if state in {"live", "orphan"})

    def checkpoint_folder(self, run_id: str) -> Path:
        return self.runs / self.checkpoints[run_id] / STATES

    @precondition(lambda self: self.running())
    @rule(data=st.data())
    def checkpoint_begin(self, data: st.DataObject) -> None:
        """TLC starts a checkpoint: the .tmp files are there and the checkpoint is not complete."""
        run_id = data.draw(st.sampled_from(self.running()), label="TLC of")
        states = self.checkpoint_folder(run_id)
        if states.parent.is_dir():  # a TLC whose folder was deleted crashes instead (research 17)
            states.mkdir(exist_ok=True)
            (states / "queue.tmp").write_bytes(b"")
            (states / "vars.tmp").write_bytes(b"")
            self.begun.add(run_id)

    def writing(self) -> list[str]:
        return [r for r in self.running() if r in self.begun and self.checkpoint_folder(r).parent.is_dir()]

    @precondition(lambda self: self.writing())
    @rule(data=st.data())
    def checkpoint_end(self, data: st.DataObject) -> None:
        """TLC commits the checkpoint: the .tmp files become queue.chkpt and vars.chkpt."""
        run_id = data.draw(st.sampled_from(self.writing()), label="TLC of")
        states = self.checkpoint_folder(run_id)
        self.begun.discard(run_id)
        for name in ("queue", "vars"):
            (states / f"{name}.tmp").replace(states / f"{name}.chkpt")
        for leftover in states.glob("*.tmp"):  # what an earlier TLC left half written is replaced too
            leftover.unlink()

    @precondition(lambda self: self.at("tlc"))
    @rule(data=st.data())
    def tlc_exit(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("tlc")), label="process")
        self.tlc[proc.run] = "done"
        self.end_jvm(proc.run)  # the launcher has seen the child gone before anything is released
        proc.pc = "settle"

    @precondition(lambda self: "orphan" in self.tlc.values())
    @rule(data=st.data())
    def orphan_exit(self, data: st.DataObject) -> None:
        """The lifeline ends a killed tlaup's TLC; the system releases the locks it inherited."""
        orphans = sorted(run_id for run_id, state in self.tlc.items() if state == "orphan")
        run_id = data.draw(st.sampled_from(orphans), label="TLC of")
        self.tlc[run_id] = "done"
        self.end_jvm(run_id)
        for name in self.orphan_held.pop(run_id, {}):
            if self.lock_file(name).exists() and not self.holders(name):
                assert self.probe(name), f"the lock of {name} stayed held after the TLC that held it ended"

    @precondition(lambda self: self.at("settle"))
    @rule(data=st.data(), finished=st.booleans())
    def settle(self, data: st.DataObject, finished: bool) -> None:
        proc = data.draw(st.sampled_from(self.at("settle")), label="process")
        ran = self.tlc.get(proc.run) == "done"
        finished = finished and ran
        outcome = self.impl.outcome(0 if finished else 255) if ran else None
        settled_in = self.runs / (proc.target if proc.recover_locked else proc.run)
        expected = not finished and proc.keeps() and complete(settled_in)
        settled = proc.folder.settle(outcome)
        kept = settled.kept is not None
        assert kept == expected, f"settle kept={kept}, expected kept={expected}"
        assert not kept or complete(settled_in), "KeptIsComplete: a folder was kept without a complete checkpoint"
        if not finished and not kept and settled_in.is_dir() and any_checkpoint(settled_in):
            reason = "incomplete" if proc.keeps() else "not-asked"
            assert settled.dropped == reason, f"dropped is {settled.dropped!r}, not {reason!r}"
        assert proc.folder.settle(None) == settled, "a second settle changed the answer"
        proc.kept, proc.finished = kept, finished
        proc.pc = "eOwn"

    @precondition(lambda self: self.at("eOwn"))
    @rule(data=st.data())
    def end_own(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from(self.at("eOwn")), label="process")
        if proc.finished:
            self.may_remove.add(proc.run)  # its own run finished: nothing to resume
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
        if proc.finished:
            self.may_remove.add(proc.target)  # the resumed run finished: R6, -recover rule 3
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
        self.kill_one(data.draw(st.sampled_from([p for p in self.procs if p.pc != "idle"]), label="process"))

    @precondition(lambda self: self.kills < MAX_KILLS and self.at("tlc"))
    @rule(data=st.data())
    def kill_while_tlc_runs(self, data: st.DataObject) -> None:
        """The kill that matters for D51, given its own rule so that it is not left to chance."""
        self.kill_one(data.draw(st.sampled_from(self.at("tlc")), label="process"))

    def kill_one(self, proc: Proc) -> None:
        self.kills += 1
        held = dict(proc.held)
        inherited: dict[str, int] = {}
        if proc.run and self.tlc.get(proc.run) == "live":
            self.tlc[proc.run] = "orphan"
            names = [proc.run, proc.target] if proc.recover_locked else [proc.run]
            inherited = {name: held[name] for name in names if name in held and LOCK_FOLLOWS_TLC}
            self.orphan_held[proc.run] = inherited
        self.abandon(proc)
        proc.forget()
        gc.collect()
        for run_id in held:  # the kill freed what the TLC did not inherit, and nothing else
            if not self.lock_file(run_id).exists():
                continue
            if run_id in inherited:
                assert not self.probe(run_id), f"the TLC of {proc.name} lost the lock of {run_id} at the kill"
            elif not self.holders(run_id):
                assert self.probe(run_id), f"the lock of {run_id} stayed held after its holder was killed"

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
            working = [r for r, state in self.tlc.items() if state in {"live", "orphan"} and run_id in self.where[r]]
            assert not working, f"NoDeleteUnderTLC: {run_id} was deleted under the TLC of {working}"
            if was["kept"] and was["complete"]:
                assert run_id in self.may_remove, f"KeptSurvives: {run_id} was removed"
            if was["json"] and was["keep"] and was["complete"]:
                assert run_id in self.may_remove, f"CheckpointSurvives: {run_id} was removed"
        self.before = current
        self.may_remove = set()
        for path in self.runs.iterdir():  # what a step made is as old as the injected clock says
            inode = path.stat().st_ino
            if inode not in self.stamped:
                self.stamped.add(inode)
                os.utime(path, (self.clock.timestamp(), self.clock.timestamp()))

    def all_held(self) -> list[tuple[str, str, int]]:
        holds = [(proc.name, run_id, inode) for proc in self.procs for run_id, inode in proc.held.items()]
        orphans = [
            (f"TLC of {r}", run_id, inode) for r, held in self.orphan_held.items() for run_id, inode in held.items()
        ]
        return holds + orphans

    @invariant()
    def held_lock_is_on_the_file_at_the_name(self) -> None:
        for who, run_id, inode in self.all_held():
            path = self.lock_file(run_id)
            assert path.exists(), f"HeldIsCurrent: {who} holds {path.name}, which is gone"
            assert path.stat().st_ino == inode, f"HeldIsCurrent: {path.name} was replaced under {who}"

    @invariant()
    def one_lock_object_per_name(self) -> None:
        for run_id in {run_id for _, run_id, _ in self.all_held()}:
            names = self.holders(run_id)
            assert len(names) == 1, f"LockExclusive: {names} all hold the lock of {run_id}"

    @invariant()
    def live_run_has_its_folder_and_lock(self) -> None:
        for proc in self.procs:
            if proc.mode == "run" and proc.pc in {"json", "visit", "visit3", "visit4", "tlc", "settle"}:
                assert proc.run in proc.held, f"LiveRunLocked: {proc.name} lost the lock of {proc.run}"
                if proc.made_folder:
                    assert (self.runs / proc.run).is_dir(), f"LiveRunLocked: the folder of {proc.run} is gone"
        for run_id, state in self.tlc.items():
            if state == "orphan" and LOCK_FOLLOWS_TLC:
                assert run_id in self.orphan_held.get(run_id, {}), f"LiveRunLocked: the TLC of {run_id} lost its lock"

    @invariant()
    def one_tlc_per_folder(self) -> None:
        running = [run_id for run_id, state in self.tlc.items() if state in {"live", "orphan"}]
        for folder in {f for run_id in running for f in self.where[run_id]}:
            writers = [run_id for run_id in running if folder in self.where[run_id]]
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


# The kill rule above rests on the inherited lock (D51): a child that holds a duplicate of a
# RunLock's descriptor keeps the lock after its parent has closed its own copy without
# unlocking, and loses it when it ends; a release by the parent while the child lives frees it
# too (one open file description), which is why R6 releases only after the child is gone.


def jvm_keeps_the_lock(impl: SimpleNamespace, runs: Path) -> None:
    path = runs / "run0.lock"

    def probe() -> bool:
        lock = filelock.FileLock(path)
        try:
            lock.acquire(timeout=0)
        except filelock.Timeout:
            return False
        lock.release()
        return True

    for parent_ends in ("killed", "released"):
        own = impl.rundirs.RunLock(path, wait=0)
        own.acquire()
        fd = own.duplicate()
        try:
            jvm = subprocess.Popen([sys.executable, "-c", JVM], stdin=subprocess.PIPE, pass_fds=(fd,), text=True)
        finally:
            os.close(fd)
        try:
            assert not probe(), "a held RunLock was free"
            if parent_ends == "killed":
                own.abandon()
                assert not probe(), "the child did not keep the lock after its parent closed its copy"
            else:
                own.release()
                assert probe(), "a release in the parent did not free the child's copy"
        finally:
            jvm.communicate("\n", timeout=30)
        assert probe(), "the lock stayed held after the child ended"


def test_a_jvm_keeps_the_run_lock_reference_model(tmp_path: Path) -> None:
    jvm_keeps_the_lock(reference_impl(), tmp_path)


@pytest.mark.pending
def test_a_jvm_keeps_the_run_lock(tmp_path: Path) -> None:
    jvm_keeps_the_lock(tlaup_impl(), tmp_path)


# Finding FC1 of the 2026-11-20 review, replayed step by step: a folder that was kept by a
# resume that asked, although its own run did not, must survive a later resume that does not
# ask. Settle therefore writes "keep": true when it keeps, and a folder that says kept makes a
# kept run. Random steps reached this only by chance.


def kept_folder_survives_a_second_resume(impl: SimpleNamespace, runs: Path) -> None:
    clock = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)
    rd = impl.rundirs

    def now() -> datetime:
        return clock

    first = rd.RunStart(runs, now, run_id="run0", info={"keep": False}, wait=0)
    first.create_lock_file()
    first.take_lock()
    first.make_folder()
    first.write_run_json()
    (first.path / STATES).mkdir()
    for name in ("queue.chkpt", "vars.chkpt"):
        (first.path / STATES / name).write_bytes(b"")
    first.abandon()  # killed, its TLC gone: unsettled, keep false, a complete checkpoint

    def resume(run_id: str, *, keep: bool) -> Any:
        start = rd.RunStart(runs, now, run_id=run_id, recover=runs / "run0" / STATES, info={"keep": keep}, wait=0)
        start.create_lock_file()
        start.take_lock()
        start.take_recover_lock()
        folder = start.entered()  # it stops before its TLC starts
        settled = folder.settle(None)
        folder.end_own()
        folder.release_own()
        folder.end_recovered()
        folder.release_recovered()
        return settled

    assert resume("run1", keep=True).kept is not None, "a resume with --keep did not keep the folder"
    record = json.loads((runs / "run0" / "run.json").read_text(encoding="utf-8"))
    assert record.get("kept") and record.get("keep"), "settle kept the folder without writing keep"
    resume("run2", keep=False)
    assert (runs / "run0").is_dir(), "KeptSurvives: a resume without --keep deleted a kept folder"


def test_kept_folder_survives_a_second_resume_reference_model(tmp_path: Path) -> None:
    kept_folder_survives_a_second_resume(reference_impl(), tmp_path)


@pytest.mark.pending
def test_kept_folder_survives_a_second_resume(tmp_path: Path) -> None:
    kept_folder_survives_a_second_resume(tlaup_impl(), tmp_path)
