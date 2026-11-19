"""A throwaway model of the run-folder steps of design 11 R6.

It exists so that the state machine in ``test_run_folders.py`` can be run before
``tlaup.tlc.rundirs`` is written, to show that the machine itself is sound. It has the
step-level interface R6 names and nothing else of the runner. It is not product code:
the work package that builds ``tlaup.tlc.rundirs`` deletes this file and the reference
test with it.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import filelock

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

KEEP = timedelta(days=30)
UNSETTLED = timedelta(days=1)
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


def _acquire(lock: filelock.FileLock, wait: float) -> bool:
    try:
        if wait > 0:
            lock.acquire(timeout=wait)
        else:
            lock.acquire(blocking=False)
    except filelock.Timeout:
        return False
    return True


def _read_run_json(folder: Path) -> dict[str, Any] | None:
    try:
        loaded = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _checkpoint_dir(folder: Path) -> Path | None:
    found = sorted(folder.rglob("*.chkpt"))
    return found[0].parent if found else None


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
        self.info = info or {}
        self.wait = wait
        self._own: filelock.FileLock | None = None
        self._recovered: filelock.FileLock | None = None
        self._recovered_id: str | None = None

    def create_lock_file(self) -> None:
        _lock_file(self.runs, self.run_id).open("x").close()

    def take_lock(self) -> None:
        lock = filelock.FileLock(_lock_file(self.runs, self.run_id))
        if not _acquire(lock, self.wait):
            raise FileOperationError(self.run_id)
        self._own = lock

    def take_recover_lock(self) -> None:
        run_id = _recovered_run(self.runs, self.recover)
        if run_id is None:
            return
        lock = filelock.FileLock(_lock_file(self.runs, run_id))
        if not _acquire(lock, self.wait):
            raise FileOperationError(run_id)
        self._recovered = lock
        self._recovered_id = run_id

    def make_folder(self) -> None:
        self.path.mkdir()

    def write_run_json(self) -> None:
        record = {"schema": 1, **self.info, "started": self.now().isoformat(), "ended": None, "kept": False}
        (self.path / "run.json").write_text(json.dumps(record), encoding="utf-8")

    def sweep(self) -> None:
        sweep(self.runs, self.now)

    def entered(self) -> RunFolder:
        if self._own is None:
            raise RuntimeError(self.run_id)
        return RunFolder(self.runs, self.run_id, self.now, self._own, self._recovered, self._recovered_id)


class RunFolder:
    """A run folder that has been entered: settle, then the steps of "End"."""

    def __init__(
        self,
        runs: Path,
        run_id: str,
        now: Callable[[], datetime],
        own: filelock.FileLock,
        recovered: filelock.FileLock | None,
        recovered_id: str | None,
    ) -> None:
        self.runs = runs
        self.run_id = run_id
        self.path = runs / run_id
        self.now = now
        self._own = own
        self._recovered = recovered
        self._recovered_id = recovered_id
        self._settled = False
        self._kept: Kept | None = None

    def settle(self, process: ProcessOutcome | None) -> Kept | None:
        if self._settled:
            return self._kept
        self._settled = True
        finished = process is not None and process.stopped_by is None and process.exit_code in FINISHED
        folder = self.runs / self._recovered_id if self._recovered_id is not None else self.path
        checkpoint = _checkpoint_dir(folder) if folder.is_dir() else None
        if not finished and checkpoint is not None:
            record = _read_run_json(folder) or {"schema": 1}
            record.update(ended=self.now().isoformat(), kept=True)
            (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
            self._kept = Kept(folder, checkpoint)
        return self._kept

    def end_own(self) -> None:
        if self._kept is not None and self._kept.path == self.path:
            return
        shutil.rmtree(self.path, ignore_errors=True)
        _lock_file(self.runs, self.run_id).unlink(missing_ok=True)

    def release_own(self) -> None:
        self._own.release()

    def end_recovered(self) -> None:
        if self._recovered_id is None or self._kept is not None:
            return
        shutil.rmtree(self.runs / self._recovered_id, ignore_errors=True)
        _lock_file(self.runs, self._recovered_id).unlink(missing_ok=True)

    def release_recovered(self) -> None:
        if self._recovered is not None:
            self._recovered.release()


class EntryVisit:
    """One entry of runs/ under its lock: what the sweep and ``cache clean`` do to it."""

    def __init__(self, runs: Path, run_id: str, now: Callable[[], datetime]) -> None:
        self.runs = runs
        self.run_id = run_id
        self.path = runs / run_id
        self.now = now
        self._lock = filelock.FileLock(_lock_file(runs, run_id))

    def take_lock(self) -> bool:
        return _acquire(self._lock, 0)

    def _age(self, text: object) -> timedelta:
        if isinstance(text, str):
            return self.now() - datetime.fromisoformat(text)
        modified = datetime.fromtimestamp(self.path.stat().st_mtime, tz=self.now().tzinfo)
        return self.now() - modified

    def sweep(self) -> None:
        if self.path.is_dir():
            record = _read_run_json(self.path)
            if record is None:
                old = self._age(None) > KEEP
            elif record.get("kept"):
                old = self._age(record.get("ended")) > KEEP
            else:
                limit = KEEP if _checkpoint_dir(self.path) is not None else UNSETTLED
                old = self._age(record.get("started")) > limit
            if old:
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
        if not include_kept and (record is None or record.get("kept")):
            return False
        resumable = _checkpoint_dir(self.path) is not None and not record.get("no_keep")
        if not include_kept and resumable:  # never settled, and can be resumed (decision D49)
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
