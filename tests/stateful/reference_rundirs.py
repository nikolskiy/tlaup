"""A throwaway model of the run-folder steps of design 11 R6.

It exists so that the state machine in ``test_run_folders.py`` can be run before
``tlaup.tlc.rundirs`` is written, to show that the machine itself is sound. It has the
step-level interface R6 names and nothing else of the runner. It is not product code:
the work package that builds ``tlaup.tlc.rundirs`` deletes this file and the reference
test with it.

Revised 2026-11-20 for decisions D51 to D53: the run's own and recovered locks are
``RunLock`` (tlaup's own descriptor, locked with ``filelock.lock_descriptor``, with its own
wait and second look), whose duplicates a JVM inherits; keeping is asked for per run; only a
complete checkpoint is trusted; the sweep never removes a kept folder.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import filelock

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

NO_RUN_JSON = timedelta(days=30)
LOCK_FILE_AGE = timedelta(hours=1)
FINISHED = frozenset({0, 10, 11, 12, 13, 14})


class FileOperationError(Exception):
    """A lock that could not be had."""


@dataclass(frozen=True)
class ProcessOutcome:
    exit_code: int
    stopped_by: str | None = None


@dataclass(frozen=True)
class Kept:
    path: Path
    checkpoint_dir: Path


@dataclass(frozen=True)
class Settled:
    kept: Kept | None
    dropped: str | None  # "not-asked" or "incomplete" when a checkpoint was there and was not kept


def list_entries(runs: Path, *, folders_only: bool = False) -> list[str]:
    """The run ids that have a folder or, unless ``folders_only``, a lock file."""
    ids: set[str] = set()
    for entry in runs.iterdir():
        if entry.is_dir():
            ids.add(entry.name)
        elif entry.suffix == ".lock" and not folders_only:
            ids.add(entry.stem)
    return sorted(ids)


def _lock_file(runs: Path, run_id: str) -> Path:
    return runs / f"{run_id}.lock"


class RunLock:
    """tlaup's own lock on one ``<id>.lock`` (D51): a descriptor it owns, so a JVM can inherit it."""

    def __init__(self, path: Path, *, wait: float) -> None:
        self.path = path
        self.wait = wait
        self.fd: int | None = None

    def acquire(self) -> None:
        deadline = time.monotonic() + self.wait
        while True:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)  # never O_TRUNC: the age stays
            if filelock.lock_descriptor(fd, blocking=False):
                try:
                    current = self.path.stat()
                except FileNotFoundError:
                    current = None
                mine = os.fstat(fd)
                if current is not None and (current.st_dev, current.st_ino) == (mine.st_dev, mine.st_ino):
                    self.fd = fd
                    return
                filelock.unlock_descriptor(fd)  # the second look: the file was unlinked under it
            os.close(fd)
            if time.monotonic() >= deadline:
                raise FileOperationError(self.path.name)
            time.sleep(0.01)

    def duplicate(self) -> int:
        assert self.fd is not None
        return os.dup(self.fd)

    def release(self) -> None:
        if self.fd is not None:
            filelock.unlock_descriptor(self.fd)
            os.close(self.fd)
            self.fd = None

    def abandon(self) -> None:
        """Close without unlocking: what the operating system does at a kill."""
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def _read_run_json(folder: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def complete_checkpoint(folder: Path) -> Path | None:
    """TLC's timestamped folder when it holds a complete checkpoint (D52), else None."""
    if not folder.is_dir():
        return None
    if any(p.name.endswith(".tmp") or p.name == "settings.tmp.chkpt" for p in folder.rglob("*")):
        return None
    for queue in sorted(folder.rglob("queue.chkpt")):
        if (queue.parent / "vars.chkpt").exists():
            return queue.parent
    return None


def _any_checkpoint(folder: Path) -> bool:
    return any(folder.rglob("*.chkpt")) or any(folder.rglob("*.tmp"))


def _newest_change(folder: Path) -> float:
    return max([folder.stat().st_mtime, *(p.stat().st_mtime for p in folder.rglob("*"))])


def _recovered_run(runs: Path, recover: Path | None) -> str | None:
    """The id of the run folder ``recover`` is inside, if it is inside one that exists."""
    if recover is None:
        return None
    resolved = recover.resolve()
    if not resolved.is_relative_to(runs.resolve()):
        return None
    parts = resolved.relative_to(runs.resolve()).parts
    if not parts or not (runs / parts[0]).is_dir():
        return None
    return parts[0]


class RunStart:
    """The steps of "Start", one call each."""

    def __init__(
        self,
        runs: Path,
        now: Callable[[], datetime],
        *,
        run_id: str,
        recover: Path | None = None,
        info: dict[str, Any] | None = None,
        wait: float = 5.0,
    ) -> None:
        self.runs = runs
        self.now = now
        self.run_id = run_id
        self.path = runs / run_id
        self.recover = recover
        self.info = dict(info or {})
        self.keep = bool(self.info.get("keep"))
        self.wait = wait
        self._own: RunLock | None = None
        self._recovered: RunLock | None = None
        self._recovered_id: str | None = None

    def create_lock_file(self) -> None:
        _lock_file(self.runs, self.run_id).open("x").close()

    def take_lock(self) -> None:
        lock = RunLock(_lock_file(self.runs, self.run_id), wait=self.wait)
        lock.acquire()
        self._own = lock

    def take_recover_lock(self) -> None:
        run_id = _recovered_run(self.runs, self.recover)
        if run_id is None:
            return
        lock = RunLock(_lock_file(self.runs, run_id), wait=self.wait)
        lock.acquire()
        self._recovered = lock
        self._recovered_id = run_id
        record = _read_run_json(self.runs / run_id) or {}
        if record.get("keep") or record.get("kept"):
            self.keep = True  # a resume of a folder that asked to be kept, or was kept, is a kept run (D53)

    def make_folder(self) -> None:
        self.path.mkdir()

    def write_run_json(self) -> None:
        record = {
            "schema": 1,
            **self.info,
            "keep": self.keep,
            "started": self.now().isoformat(),
            "ended": None,
            "kept": False,
        }
        (self.path / "run.json").write_text(json.dumps(record), encoding="utf-8")

    def sweep(self) -> None:
        sweep(self.runs, self.now)

    def entered(self) -> RunFolder:
        if self._own is None:
            raise RuntimeError(self.run_id)
        folder = RunFolder(self.runs, self.run_id, self.now, self._own, self._recovered, self._recovered_id, self.keep)
        self._own = self._recovered = None
        return folder

    def abandon(self) -> None:
        """A kill before the folder was entered: every descriptor closed, nothing unlocked."""
        for lock in (self._own, self._recovered):
            if lock is not None:
                lock.abandon()


class RunFolder:
    """A run folder that has been entered: settle, then the steps of "End"."""

    def __init__(
        self,
        runs: Path,
        run_id: str,
        now: Callable[[], datetime],
        own: RunLock,
        recovered: RunLock | None,
        recovered_id: str | None,
        keep: bool,
    ) -> None:
        self.runs = runs
        self.run_id = run_id
        self.path = runs / run_id
        self.now = now
        self.keep = keep
        self._own = own
        self._recovered = recovered
        self._recovered_id = recovered_id
        self._settled: Settled | None = None

    @property
    def lock_fds(self) -> tuple[int, ...]:
        """Duplicates for the JVM (D51); the caller closes them once Popen has returned."""
        return tuple(lock.duplicate() for lock in (self._own, self._recovered) if lock is not None)

    def settle(self, process: ProcessOutcome | None) -> Settled:
        if self._settled is not None:
            return self._settled
        finished = process is not None and process.stopped_by is None and process.exit_code in FINISHED
        folder = self.runs / self._recovered_id if self._recovered_id is not None else self.path
        complete = complete_checkpoint(folder)
        kept, dropped = None, None
        if not finished and self.keep and complete is not None:
            record = _read_run_json(folder) or {"schema": 1}
            record.update(ended=self.now().isoformat(), kept=True, keep=True)  # FC1: keep goes with kept
            (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
            kept = Kept(folder, complete)
        elif not finished and folder.is_dir() and _any_checkpoint(folder):
            dropped = "incomplete" if self.keep else "not-asked"
        self._settled = Settled(kept, dropped)
        return self._settled

    def _kept_path(self) -> Path | None:
        return None if self._settled is None or self._settled.kept is None else self._settled.kept.path

    def end_own(self) -> None:
        if self._kept_path() == self.path:
            return
        shutil.rmtree(self.path, ignore_errors=True)
        _lock_file(self.runs, self.run_id).unlink(missing_ok=True)

    def release_own(self) -> None:
        self._own.release()

    def end_recovered(self) -> None:
        if self._recovered_id is None or self._kept_path() is not None:
            return
        shutil.rmtree(self.runs / self._recovered_id, ignore_errors=True)
        _lock_file(self.runs, self._recovered_id).unlink(missing_ok=True)

    def release_recovered(self) -> None:
        if self._recovered is not None:
            self._recovered.release()

    def abandon(self) -> None:
        """A kill: every descriptor closed, nothing unlocked, so a JVM's duplicate keeps the lock."""
        for lock in (self._own, self._recovered):
            if lock is not None:
                lock.abandon()


class EntryVisit:
    """One entry of runs/ under its lock: what the sweep and ``cache clean`` do to it."""

    def __init__(self, runs: Path, run_id: str, now: Callable[[], datetime]) -> None:
        self.runs = runs
        self.run_id = run_id
        self.path = runs / run_id
        self.now = now
        self._lock = filelock.FileLock(_lock_file(runs, run_id))

    def take_lock(self) -> bool:
        try:
            self._lock.acquire(timeout=0)  # one attempt, with a finite timeout (research 30)
        except filelock.Timeout:
            return False
        return True

    def _resumable(self, record: dict[str, Any]) -> bool:
        return bool(record.get("keep")) and complete_checkpoint(self.path) is not None

    def sweep(self) -> None:
        if self.path.is_dir():
            record = _read_run_json(self.path)
            if record is None:
                modified = datetime.fromtimestamp(_newest_change(self.path), tz=self.now().tzinfo)
                remove = self.now() - modified > NO_RUN_JSON
            elif record.get("kept"):
                remove = False  # a kept folder is never swept (D53)
            else:
                remove = not self._resumable(record)  # unsettled: at once, unless resumable
            if remove:
                shutil.rmtree(self.path, ignore_errors=True)
        lock_file = _lock_file(self.runs, self.run_id)
        if not self.path.exists() and lock_file.exists():
            modified = datetime.fromtimestamp(lock_file.stat().st_mtime, tz=self.now().tzinfo)
            if self.now() - modified > LOCK_FILE_AGE:
                lock_file.unlink()

    def clean(self, *, include_kept: bool) -> bool:
        if not self.path.is_dir():
            return False
        record = _read_run_json(self.path)
        if not include_kept and (record is None or record.get("kept") or self._resumable(record)):
            return False
        shutil.rmtree(self.path, ignore_errors=True)
        if self.path.exists():
            return False
        _lock_file(self.runs, self.run_id).unlink(missing_ok=True)
        return True

    def release(self) -> None:
        self._lock.release()


def sweep(runs: Path, now: Callable[[], datetime]) -> None:
    for run_id in list_entries(runs):
        visit = EntryVisit(runs, run_id, now)
        if visit.take_lock():
            try:
                visit.sweep()
            finally:
                visit.release()
