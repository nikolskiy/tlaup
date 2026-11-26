"""Run folders under ``<cache>/runs/`` and their locks (design 11 R6).

One folder per run, ``runs/<run-id>/``, with its lock file ``runs/<run-id>.lock`` beside it. The steps are
one call each (decision D46), so that the stateful test can interleave several tlaups in one process:
``RunStart`` is "Start", ``RunFolder`` is settle and "End", ``EntryVisit`` is one entry of the sweep or of
``cache clean``. A run's own lock and the lock of the folder ``-recover`` names are ``RunLock``, tlaup's own
descriptor, which a JVM inherits on Linux and macOS (D51); the visits use ``filelock.FileLock``.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

import filelock

from tlaup.errors import FileOperationError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from tlaup.java.launcher import ProcessOutcome
    from tlaup.paths import AppPaths

SCHEMA = 1
RUN_JSON = "run.json"
LOCK_SUFFIX = ".lock"
POLL = 0.05  # seconds between two attempts at a run's lock (R6's figure, not measured)
NO_RUN_JSON_AGE = timedelta(days=30)  # a folder with no run.json, counted from its newest change
LOCK_FILE_AGE = timedelta(hours=1)  # a lock file whose folder is gone
FINISHED = frozenset({0, 10, 11, 12, 13, 14})  # TLC's clean finish and its violation codes (research 15)
WINDOWS = os.name == "nt"

Dropped = Literal["not-asked", "incomplete", "depth-first"]


@dataclass(frozen=True)
class Kept:
    path: Path  # the run folder; after -recover, the recovered run's folder
    checkpoint_dir: Path  # TLC's timestamped folder in it, where the *.chkpt files are
    size: int  # bytes, the whole run folder
    stopped_after: timedelta  # from this run's start to the end of the run
    checkpoint_at: datetime  # when the complete checkpoint was written
    reason: str  # "interrupted", "tlaup failed" or "TLC crashed (exit N)"
    resume_command: str | None = None  # None for a folder built without an invocation


@dataclass(frozen=True)
class Settled:
    kept: Kept | None
    dropped: Dropped | None  # a checkpoint was there and was not kept, and why


@dataclass(frozen=True)
class KeptSummary:
    count: int
    size: int


# ---------------------------------------------------------------------- the files


def _lock_file(runs: Path, run_id: str) -> Path:
    return runs / f"{run_id}{LOCK_SUFFIX}"


def list_entries(runs: Path, *, folders_only: bool = False) -> list[str]:
    """The run ids that have a folder or, unless ``folders_only``, a lock file; sorted."""
    ids: set[str] = set()
    try:
        entries = list(runs.iterdir())
    except FileNotFoundError:
        return []
    except OSError as error:
        raise _cannot("read", runs, error) from error
    for entry in entries:
        if entry.is_dir():
            ids.add(entry.name)
        elif not folders_only and entry.name.endswith(LOCK_SUFFIX) and len(entry.name) > len(LOCK_SUFFIX):
            ids.add(entry.name[: -len(LOCK_SUFFIX)])
    return sorted(ids)


def _cannot(action: str, path: Path, error: OSError) -> FileOperationError:
    return FileOperationError(f"cannot {action} {path}: {error.strerror or error}")


def _read_run_json(folder: Path) -> dict[str, object] | None:
    """The folder's run.json, or None when there is none or it cannot be read (R6 Risks: the 30-day rule)."""
    try:
        loaded = json.loads((folder / RUN_JSON).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _write_run_json(folder: Path, record: Mapping[str, object]) -> None:
    """Write beside, then move into place. The temporary name does not end in ``.tmp``, which would make the
    folder's checkpoint look incomplete (D52)."""
    path = folder / RUN_JSON
    staged = folder / f".{RUN_JSON}.new"
    try:
        staged.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        staged.replace(path)
    except OSError as error:
        with suppress(OSError):
            staged.unlink(missing_ok=True)
        raise _cannot("write", path, error) from error


def _utc(moment: datetime) -> str:
    return f"{moment.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}"


def _broken(name: str) -> bool:
    return name.endswith(".tmp") or name == "settings.tmp.chkpt"


def complete_checkpoint(folder: Path) -> Path | None:
    """The timestamped folder that holds a complete checkpoint (D52), or None.

    Complete: ``queue.chkpt`` and ``vars.chkpt`` side by side, and nothing under ``folder`` ends in ``.tmp`` or
    is named ``settings.tmp.chkpt``.
    """
    try:
        if not folder.is_dir():
            return None
        names = list(folder.rglob("*"))
    except OSError:
        return None
    if any(_broken(path.name) for path in names):
        return None
    for queue in sorted(path for path in names if path.name == "queue.chkpt"):
        if (queue.parent / "vars.chkpt").is_file():
            return queue.parent
    return None


def _any_checkpoint(folder: Path) -> bool:
    try:
        return any(path.name.endswith((".chkpt", ".tmp")) for path in folder.rglob("*"))
    except OSError:
        return False


def _size(folder: Path) -> int:
    """Bytes of every file under ``folder``; what cannot be read counts as nothing."""
    total = 0
    with suppress(OSError):
        for path in folder.rglob("*"):
            with suppress(OSError):
                info = path.lstat()
                if not path.is_dir():
                    total += info.st_size
    return total


def _newest_change(folder: Path) -> float:
    """The newest modification time of the folder or anything under it (research 34)."""
    newest = folder.stat().st_mtime
    with suppress(OSError):
        for path in folder.rglob("*"):
            with suppress(OSError):
                newest = max(newest, path.lstat().st_mtime)
    return newest


def _checkpoint_at(checkpoint_dir: Path) -> datetime:
    """The newer modification time of ``queue.chkpt`` and ``vars.chkpt``."""
    stamps = [(checkpoint_dir / name).stat().st_mtime for name in ("queue.chkpt", "vars.chkpt")]
    return datetime.fromtimestamp(max(stamps), tz=UTC)


def _remove_tree(folder: Path) -> None:
    """Errors are ignored; a later sweep tries again (R6)."""
    shutil.rmtree(folder, ignore_errors=True)


def recovered_run_id(path: Path, runs: Path) -> str | None:
    """The id of the run folder ``path`` lies under, when that folder exists, whether or not ``path`` exists.

    ``path`` is absolute (a relative ``-recover`` is made absolute by the caller); links are resolved as far as
    the path exists (question Q9).
    """
    target = path.resolve()  # not strict: resolves what exists, keeps the rest
    try:
        parts = target.relative_to(runs.resolve()).parts
    except ValueError:
        return None
    if not parts or not (runs / parts[0]).is_dir():
        return None
    return parts[0]


# ---------------------------------------------------------------------- the run's own locks


class RunLock:
    """tlaup's own lock on one ``<id>.lock`` (D51): a descriptor it owns, so that a JVM can inherit it."""

    def __init__(self, path: Path, *, wait: float) -> None:
        self.path = path
        self.wait = wait
        self._fd: int | None = None
        self._unlink_after_release = False

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self) -> None:
        """``try_acquire``, with FileOperationError when the lock stayed held for the whole wait."""
        if not self.try_acquire():
            raise FileOperationError(f"{self.path} is held by another tlaup run")  # noqa: TRY003

    def try_acquire(self) -> bool:
        """One attempt every 50 ms until ``wait`` is over; False if the lock stayed held. ``wait=0`` makes one.

        A second look that finds the file gone or replaced is not a failed try: the attempt starts over at once,
        on the file now at the name. An open or lock that fails for another reason is FileOperationError.
        """
        deadline = time.monotonic() + self.wait
        while True:
            got = self._attempt()
            if got is None:
                continue  # the file lost its name under the lock: look again at once
            if got:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(POLL)

    def _attempt(self) -> bool | None:
        """True: locked; False: held by another; None: the second look failed."""
        try:
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)  # never O_TRUNC: the file's age stays
        except OSError as error:
            raise _cannot("open", self.path, error) from error
        try:
            if filelock.lock_descriptor(fd, blocking=False):
                if self._is_at_the_path(fd):
                    self._fd = fd
                    return True
                filelock.unlock_descriptor(fd)  # the second look: the file was removed under the lock (K1-2)
                os.close(fd)
                return None
        except OSError as error:
            os.close(fd)
            raise _cannot("lock", self.path, error) from error
        os.close(fd)
        return False

    def _is_at_the_path(self, fd: int) -> bool:
        try:
            current = self.path.stat()
        except FileNotFoundError:
            return False
        mine = os.fstat(fd)
        return (current.st_dev, current.st_ino) == (mine.st_dev, mine.st_ino)

    def duplicate(self) -> int:
        """``os.dup`` of the locked descriptor, for ``pass_fds``; the caller closes it."""
        if self._fd is None:
            message = f"{self.path} is not held"
            raise RuntimeError(message)
        return os.dup(self._fd)

    def remove_file(self) -> None:
        """Remove the lock file while the lock is held: the last thing done under it (K1-1).

        On Windows an open file cannot be removed; the file is then removed after the release (R6, "End").
        """
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            self._unlink_after_release = WINDOWS

    def release(self) -> None:
        """Unlock, then close. Only after the child is gone: the JVM's copy is the same lock."""
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            filelock.unlock_descriptor(fd)
        finally:
            os.close(fd)
        if self._unlink_after_release:
            self._unlink_after_release = False
            with suppress(OSError):
                self.path.unlink(missing_ok=True)

    def abandon(self) -> None:
        """Close without unlocking, as the operating system does at a kill; a JVM's duplicate keeps the lock."""
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        with suppress(OSError):
            os.close(fd)


# ---------------------------------------------------------------------- Start


class RunStart:
    """The steps of "Start", one call each, in this order: create_lock_file, take_lock, take_recover_lock,
    make_folder, write_run_json, sweep; then ``entered``."""

    def __init__(  # noqa: PLR0913 (the signature of 11 R6, with tlc_args from package 35)
        self,
        runs: Path,
        now: Callable[[], datetime],
        *,
        run_id: str | None = None,
        recover: Path | None = None,
        info: Mapping[str, object] | None = None,
        wait: float = 5.0,
        tlc_args: Sequence[str] = (),
    ) -> None:
        self.runs = runs
        self.now = now
        self.started = now()
        self.run_id = (
            run_id if run_id is not None else f"{self.started.astimezone(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"
        )
        self.path = runs / self.run_id
        self.recover = recover
        self.info = dict(info or {})
        self.keep = bool(self.info.get("keep"))
        self.wait = wait
        self.tlc_args = tuple(tlc_args)
        self._own = RunLock(_lock_file(runs, self.run_id), wait=wait)
        self._recovered: RunLock | None = None
        self._recovered_path: Path | None = None
        self._kept_summary = KeptSummary(0, 0)

    def create_lock_file(self) -> None:
        """Make ``runs/`` if it is missing, and the lock file beside the folder that does not exist yet."""
        path = self._own.path
        try:
            self.runs.mkdir(parents=True, exist_ok=True)
            os.close(os.open(path, os.O_RDWR | os.O_CREAT, 0o644))
        except OSError as error:
            raise _cannot("create", path, error) from error

    def take_lock(self) -> None:
        """The run's own lock; FileOperationError after ``wait``."""
        self._own.acquire()

    def take_recover_lock(self) -> None:
        """The lock of the run folder ``recover`` lies under, if that folder exists; FileOperationError after
        ``wait``. Its run.json, read under the lock, makes this a kept run when it says keep or kept (FC1)."""
        if self.recover is None:
            return
        run_id = recovered_run_id(self.recover, self.runs)
        if run_id is None:
            return
        folder = self.runs / run_id
        lock = RunLock(_lock_file(self.runs, run_id), wait=self.wait)
        if not lock.try_acquire():  # only a wait that ran out; an open or lock error passes as it is
            raise FileOperationError(f"the run folder {folder} is in use by another tlaup run")  # noqa: TRY003
        self._recovered, self._recovered_path = lock, folder
        record = _read_run_json(folder) or {}
        if record.get("keep") or record.get("kept"):
            self.keep = True

    def make_folder(self) -> None:
        try:
            self.path.mkdir()
        except OSError as error:
            raise _cannot("create", self.path, error) from error

    def write_run_json(self) -> None:
        record: dict[str, object] = {"schema": SCHEMA, **self.info}
        record.update(started=_utc(self.started), keep=self.keep, ended=None, kept=False, size=None)
        _write_run_json(self.path, record)

    def sweep(self) -> KeptSummary:
        """The sweep of ``runs/``, which leaves this run's own entries alone since their locks are held."""
        self._kept_summary = _sweep_runs(self.runs, self.now)
        return self._kept_summary

    def entered(self) -> RunFolder:
        """Hand the locks to the folder; also after a failed step, so that the end steps release them."""
        folder = RunFolder(
            path=self.path,
            run_id=self.run_id,
            now=self.now,
            started=self.started,
            keep=self.keep,
            tlc_args=self.tlc_args,
            own=self._own,
            recovered=self._recovered,
            recovered_path=self._recovered_path,
            kept_summary=self._kept_summary,
        )
        self._own = RunLock(self._own.path, wait=self.wait)  # an empty one: this start holds nothing more
        self._recovered = self._recovered_path = None
        return folder

    def abandon(self) -> None:
        """Every lock descriptor closed, nothing unlocked: a kill."""
        self._own.abandon()
        if self._recovered is not None:
            self._recovered.abandon()


# ---------------------------------------------------------------------- settle and End


class RunFolder:
    """A run folder that has been entered: settle, then the four steps of "End"."""

    def __init__(  # noqa: PLR0913 (built only by RunStart.entered, which hands over everything it holds)
        self,
        *,
        path: Path | None,
        run_id: str,
        now: Callable[[], datetime],
        started: datetime,
        keep: bool,
        tlc_args: Sequence[str],
        own: RunLock,
        recovered: RunLock | None,
        recovered_path: Path | None,
        kept_summary: KeptSummary,
    ) -> None:
        self.path = path
        self.run_id = run_id
        self.kept_summary = kept_summary
        self._now = now
        self._started = started
        self._keep = keep
        self._tlc_args = tuple(tlc_args)
        self._own = own
        self._recovered = recovered
        self._recovered_path = recovered_path
        self._settled: Settled | None = None

    @property
    def lock_fds(self) -> tuple[int, ...]:
        """Fresh duplicates of the held locks for the JVM (D51), owned by the caller; empty on Windows."""
        if WINDOWS:
            return ()
        return tuple(lock.duplicate() for lock in (self._own, self._recovered) if lock is not None and lock.held)

    def _settles_in(self) -> Path | None:
        """After -recover into a managed folder the checkpoint is looked for there."""
        if self._recovered is not None and self._recovered.held:
            return self._recovered_path
        return self.path

    def settle(self, process: ProcessOutcome | None) -> Settled:
        """Decide once whether the folder is kept; deletes nothing. A second call returns the first answer."""
        if self._settled is not None:
            return self._settled
        folder = self._settles_in()
        finished = _finished(process)
        kept: Kept | None = None
        dropped: Dropped | None = None
        if folder is not None and not finished:
            checkpoint = complete_checkpoint(folder) if self._keep else None
            if checkpoint is not None:
                ended = self._now()
                kept = self._kept(folder, checkpoint, _reason(process), ended)
                self._settled = Settled(kept, None)  # decided before run.json is written: a failed write keeps it
                _record_kept(kept, ended)
                return self._settled
            if _any_checkpoint(folder):
                if not self._keep:
                    dropped = "not-asked"
                elif "-dfid" in self._tlc_args:
                    dropped = "depth-first"
                else:
                    dropped = "incomplete"
        self._settled = Settled(kept, dropped)
        return self._settled

    def _kept(self, folder: Path, checkpoint: Path, reason: str, ended: datetime) -> Kept:
        return Kept(
            path=folder,
            checkpoint_dir=checkpoint,
            size=_size(folder),
            stopped_after=ended - self._started,
            checkpoint_at=_checkpoint_at(checkpoint),
            reason=reason,
        )

    def _kept_path(self) -> Path | None:
        return None if self._settled is None or self._settled.kept is None else self._settled.kept.path

    def end_own(self) -> None:
        """Delete the folder and remove its lock file under the lock, unless it is kept."""
        if not self._own.held or (self.path is not None and self._kept_path() == self.path):
            return
        if self.path is not None:
            _remove_tree(self.path)
        self._own.remove_file()

    def release_own(self) -> None:
        self._own.release()

    def end_recovered(self) -> None:
        """The same for the folder -recover named."""
        if self._recovered is None or not self._recovered.held or self._recovered_path is None:
            return
        if self._kept_path() == self._recovered_path:
            return
        _remove_tree(self._recovered_path)
        self._recovered.remove_file()

    def release_recovered(self) -> None:
        if self._recovered is not None:
            self._recovered.release()

    def abandon(self) -> None:
        """RunLock.abandon for both locks: a kill, or a way out that cannot confirm the child is gone."""
        self._own.abandon()
        if self._recovered is not None:
            self._recovered.abandon()


def _record_kept(kept: Kept, ended: datetime) -> None:
    """Write ended, kept, keep (FC1), size and reason into the kept folder's run.json. A write that fails passes
    on; the decision is already made, so the end steps still leave the folder the user asked to keep (D53)."""
    record = _read_run_json(kept.path) or {"schema": SCHEMA}
    record.update(ended=_utc(ended), kept=True, keep=True, size=kept.size, reason=kept.reason)
    _write_run_json(kept.path, record)


def _finished(process: ProcessOutcome | None) -> bool:
    """A clean finish or a violation: nothing to resume."""
    return (
        process is not None
        and process.stopped_by is None
        and not process.stopped_for_closed_pipe
        and process.tool_exit_code in FINISHED
    )


def _reason(process: ProcessOutcome | None) -> str:
    if process is None:
        return "tlaup failed"
    if process.stopped_by is not None or process.stopped_for_closed_pipe:
        return "interrupted"  # a closed pipe is settled as an interruption (D58)
    code = process.tool_exit_code if process.tool_exit_code is not None else process.exit_code
    return f"TLC crashed (exit {code})"


# ---------------------------------------------------------------------- the sweep and cache clean


class EntryVisit:
    """One entry of ``runs/`` under its lock, held only while it looks: the sweep's or ``cache clean``'s rule."""

    def __init__(self, runs: Path, run_id: str, now: Callable[[], datetime]) -> None:
        self.runs = runs
        self.run_id = run_id
        self.path = runs / run_id
        self._now = now
        self._lock_file = _lock_file(runs, run_id)
        self._lock = filelock.FileLock(self._lock_file)  # this object's own: a second object is refused
        self.kept_size: int | None = None  # set by sweep for a kept folder it leaves

    def take_lock(self) -> bool:
        """One attempt, no waiting; False: the entry is in use. Creates the lock file when there is none (K1-7).

        filelock's RuntimeError("Deadlock ...") is not caught: it comes only from a wait with no timeout.
        """
        try:
            self._lock.acquire(timeout=0)
        except filelock.Timeout:
            return False
        except OSError:
            return False  # a lock file that cannot be made: leave the entry alone
        return True

    def _resumable(self, record: Mapping[str, object]) -> bool:
        return bool(record.get("keep")) and complete_checkpoint(self.path) is not None

    def sweep(self) -> None:
        """A kept folder never; an unsettled one at once unless it is resumable (D49, D53); one without a
        readable run.json 30 days after its newest change; a lock file whose folder is gone after an hour."""
        self.kept_size = None
        if self.path.is_dir():
            record = _read_run_json(self.path)
            if record is None:
                remove = self._age(_newest_change(self.path)) > NO_RUN_JSON_AGE
            elif record.get("kept"):
                remove = False
                size = record.get("size")
                self.kept_size = size if isinstance(size, int) and not isinstance(size, bool) else _size(self.path)
            else:
                remove = not self._resumable(record)
            if remove:
                _remove_tree(self.path)
        if not self.path.exists():
            with suppress(OSError):
                if self._age(self._lock_file.stat().st_mtime) > LOCK_FILE_AGE:
                    self._lock_file.unlink()

    def _age(self, mtime: float) -> timedelta:
        return self._now() - datetime.fromtimestamp(mtime, tz=UTC)

    def clean(self, *, include_kept: bool) -> bool:
        """``cache clean``'s rule: what the sweep would remove and is not resumable; with ``include_kept`` every
        folder. The lock file goes with its folder. True if the folder went."""
        if not self.path.is_dir():
            return False
        if not include_kept:
            record = _read_run_json(self.path)
            if record is None or record.get("kept") or self._resumable(record):
                return False
        _remove_tree(self.path)
        if self.path.exists():
            return False
        with suppress(OSError):
            self._lock_file.unlink(missing_ok=True)
        return True

    def release(self) -> None:
        self._lock.release()


def _sweep_runs(runs: Path, now: Callable[[], datetime]) -> KeptSummary:
    count = size = 0
    for run_id in list_entries(runs):
        visit = EntryVisit(runs, run_id, now)
        if not visit.take_lock():
            continue
        try:
            visit.sweep()
        finally:
            visit.release()
        if visit.kept_size is not None:
            count += 1
            size += visit.kept_size
    return KeptSummary(count, size)


def sweep(paths: AppPaths, now: Callable[[], datetime]) -> KeptSummary:
    """Every entry of ``<cache>/runs/`` whose lock can be had at once; what it left kept, counted."""
    return _sweep_runs(paths.runs, now)
