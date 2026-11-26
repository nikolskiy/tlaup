"""Run folders under ``<cache>/runs/`` and their locks (design 11 R6).

One folder per run, ``runs/<run-id>/``, with its lock file ``runs/<run-id>.lock`` beside it. The steps are
one call each (decision D46), so that the stateful test can interleave several tlaups in one process:
``RunStart`` is "Start", ``RunFolder`` is settle and "End", ``EntryVisit`` is one entry of the sweep or of
``cache clean``. A run's own lock and the lock of the folder ``-recover`` names are ``RunLock``, tlaup's own
descriptor, which a JVM inherits on Linux and macOS (D51); the visits use ``filelock.FileLock``.

``run_folder`` is the steps in order for one ``TlcInvocation``; ``list_runs`` and ``clean_runs`` are what
``tlaup cache list`` and ``cache clean`` call; ``resume_command``, ``kept_note`` and ``reminder`` are the words a
kept folder is announced with.
"""

from __future__ import annotations

import json
import os
import secrets
import shlex
import shutil
import subprocess
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from typing import TYPE_CHECKING, Literal

import filelock

from tlaup.durations import format_elapsed
from tlaup.errors import FileOperationError, PathNotFound
from tlaup.versioning.app_version import get_app_version
from tlaup.versioning.spec import format_build

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence
    from pathlib import Path

    from tlaup.java.launcher import ProcessOutcome
    from tlaup.paths import AppPaths
    from tlaup.tlc.invocation import TlcInvocation

SCHEMA = 1
RUN_JSON = "run.json"
LOCK_SUFFIX = ".lock"
POLL = 0.05  # seconds between two attempts at a run's lock (R6's figure, not measured)
NO_RUN_JSON_AGE = timedelta(days=30)  # a folder with no run.json, counted from its newest change
LOCK_FILE_AGE = timedelta(hours=1)  # a lock file whose folder is gone
RUN_JSON_KEYS = (
    "schema",
    "spec",
    "cfg",
    "build",
    "pid",
    "started",
    "tlaup",
    "keep",
    "fp",
    "seed",
    "ended",
    "kept",
    "size",
)  # R6's order
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
    ended: datetime  # when settle kept it; the note's checkpoint time names the date when it is another day
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


def recover_path(extra_args: Sequence[str], cwd: Path) -> Path | None:
    """The word after the first ``-recover`` among TLC's arguments, made absolute against ``cwd`` as TLC reads it;
    None when there is no ``-recover`` or no word after it (TLC reports the missing value)."""
    args = list(extra_args)
    if "-recover" not in args:
        return None
    index = args.index("-recover")
    if index + 1 >= len(args):
        return None
    return cwd / args[index + 1]


@dataclass(frozen=True)
class RecoveredRun:
    """The run folder a ``-recover PATH`` among TLC's arguments points into (11 R6)."""

    run_id: str
    folder: Path  # paths.runs / run_id
    keep: bool  # its run.json says "keep": true or "kept": true
    fp: int | None  # from its run.json, when it has them
    seed: int | None


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def find_recovered_run(extra_args: Sequence[str], cwd: Path, runs: Path) -> RecoveredRun | None:
    """The run under ``runs`` that the word after ``-recover`` lies in, whether or not that path exists; else None.

    A relative path is read against ``cwd``, as TLC reads it, and links are resolved as far as the path exists. A
    run.json that is missing or cannot be read gives keep=False and no values; the run is still returned. Reads
    only; takes no lock. (Package 33's, moved here with package 35.)
    """
    path = recover_path(extra_args, cwd)
    if path is None:
        return None
    run_id = recovered_run_id(path, runs)
    if run_id is None:
        return None
    folder = runs / run_id
    record = _read_run_json(folder) or {}
    keep = record.get("keep") is True or record.get("kept") is True  # review finding FC1
    return RecoveredRun(run_id, folder, keep, _int_or_none(record.get("fp")), _int_or_none(record.get("seed")))


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

    def __init__(  # noqa: PLR0913 (the signature of 11 R6, with tlc_args and invocation from package 35)
        self,
        runs: Path,
        now: Callable[[], datetime],
        *,
        run_id: str | None = None,
        recover: Path | None = None,
        info: Mapping[str, object] | None = None,
        wait: float = 5.0,
        tlc_args: Sequence[str] = (),
        invocation: TlcInvocation | None = None,
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
        self.invocation = invocation
        self._own = RunLock(_lock_file(runs, self.run_id), wait=wait)
        self._recovered: RunLock | None = None
        self._recovered_path: Path | None = None
        self._recovered_values: tuple[int | None, int | None] = (None, None)  # its fp and seed, read under the lock
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
        self._recovered_values = (_int_or_none(record.get("fp")), _int_or_none(record.get("seed")))

    def make_folder(self) -> None:
        try:
            self.path.mkdir()
        except OSError as error:
            raise _cannot("create", self.path, error) from error

    def write_run_json(self) -> None:
        """R6's fields, in R6's order, then any other field of ``info``."""
        record: dict[str, object] = {"schema": SCHEMA, **self.info}
        record.update(started=_utc(self.started), keep=self.keep, ended=None, kept=False, size=None)
        ordered = {key: record[key] for key in RUN_JSON_KEYS if key in record}
        _write_run_json(self.path, ordered | record)

    def sweep(self) -> KeptSummary:
        """The sweep of ``runs/``, which leaves this run's own entries alone since their locks are held."""
        self._kept_summary = _sweep_runs(self.runs, self.now)
        return self._kept_summary

    def entered(self) -> RunFolder:
        """Hand the locks to the folder; also after a failed step, so that the end steps release them."""
        values = (_int_or_none(self.info.get("fp")), _int_or_none(self.info.get("seed")))
        folder = RunFolder(
            path=self.path if self._own_folder() else None,
            run_id=self.run_id,
            now=self.now,
            started=self.started,
            keep=self.keep,
            tlc_args=self.tlc_args,
            own=self._own,
            recovered=self._recovered,
            recovered_path=self._recovered_path,
            kept_summary=self._kept_summary,
            invocation=self.invocation,
            values=values,
            resumes_exactly=self._recovered is not None and None not in values and self._recovered_values == values,
        )
        self._own = RunLock(self._own.path, wait=self.wait)  # an empty one: this start holds nothing more
        self._recovered = self._recovered_path = None
        return folder

    def _own_folder(self) -> bool:
        """False when the user passed their own -metadir: no folder and no lock of this run's own."""
        return self.invocation is None or self.invocation.metadir is not None

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
        invocation: TlcInvocation | None = None,
        values: tuple[int | None, int | None] = (None, None),
        resumes_exactly: bool = False,
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
        self._invocation = invocation
        self._values = values  # the fp and seed this run passes, as its run.json records them
        self.resumes_exactly = resumes_exactly  # resumed with the recovered run's own -fp and -seed (D54)

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

    def settle(self, process: ProcessOutcome | None, *, workers_reported: int | None = None) -> Settled:
        """Decide once whether the folder is kept; deletes nothing. A second call returns the first answer.

        ``workers_reported``: the count TLC's start line gave, when the run was parsed (for the resume command).
        """
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
                kept = self._kept(folder, checkpoint, _reason(process), ended, workers_reported)
                self._settled = Settled(kept, None)  # decided before run.json is written: a failed write keeps it
                _record_kept(kept, ended, self._values)
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

    def _kept(self, folder: Path, checkpoint: Path, reason: str, ended: datetime, workers_reported: int | None) -> Kept:
        command = None
        if self._invocation is not None:
            fp, seed = self._values
            command = resume_command(self._invocation, checkpoint, fp=fp, seed=seed, workers_reported=workers_reported)
        return Kept(
            path=folder,
            checkpoint_dir=checkpoint,
            size=_size(folder),
            stopped_after=ended - self._started,
            checkpoint_at=_checkpoint_at(checkpoint),
            reason=reason,
            ended=ended,
            resume_command=command,
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


def _record_kept(kept: Kept, ended: datetime, values: tuple[int | None, int | None]) -> None:
    """Write ended, kept, keep (FC1), size and reason into the kept folder's run.json, and the fp and seed this run
    passed, so that a later -recover of a resumed folder reads the values its checkpoint now continues with; a value
    this run did not record leaves the one there. A write that fails passes on; the decision is already made, so
    the end steps still leave the folder the user asked to keep (D53)."""
    record = _read_run_json(kept.path) or {"schema": SCHEMA}
    record.update(ended=_utc(ended), kept=True, keep=True, size=kept.size, reason=kept.reason)
    for key, value in zip(("fp", "seed"), values, strict=True):
        if value is not None:
            record[key] = value
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
        self.lock_error: OSError | None = None  # set by take_lock when the lock file could not be opened or made

    def take_lock(self) -> bool:
        """One attempt, no waiting; False: the entry is in use. Creates the lock file when there is none (K1-7).

        filelock's RuntimeError("Deadlock ...") is not caught: it comes only from a wait with no timeout.
        """
        self.lock_error = None
        try:
            self._lock.acquire(timeout=0)
        except filelock.Timeout:
            return False
        except OSError as error:
            self.lock_error = error  # a lock file that cannot be made: leave the entry alone
            return False
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


# ---------------------------------------------------------------------- one run: run_folder


def _flag_int(extra_args: Sequence[str], flag: str) -> int | None:
    """The integer after the first ``flag`` among TLC's arguments; None when it is missing or does not parse."""
    args = list(extra_args)
    if flag not in args:
        return None
    index = args.index(flag)
    try:
        return int(args[index + 1])
    except (IndexError, ValueError):
        return None


def _run_info(inv: TlcInvocation) -> dict[str, object]:
    """The fields of run.json that come from the invocation (R6): the value each run uses for -fp and -seed."""
    return {
        "spec": str(inv.spec),
        "cfg": None if inv.cfg is None else str(inv.cfg),
        "build": format_build(inv.build),
        "pid": os.getpid(),
        "tlaup": get_app_version(),
        "keep": inv.keep,
        "fp": inv.fp if inv.fp is not None else _flag_int(inv.extra_args, "-fp"),
        "seed": inv.seed if inv.seed is not None else _flag_int(inv.extra_args, "-seed"),
    }


def _end(folder: RunFolder) -> None:
    """The four end steps, own folder first; each runs even when one before it raised."""
    try:
        folder.end_own()
    finally:
        try:
            folder.release_own()
        finally:
            try:
                folder.end_recovered()
            finally:
                folder.release_recovered()


@contextmanager
def run_folder(
    inv: TlcInvocation, paths: AppPaths, now: Callable[[], datetime], *, wait: float = 5.0
) -> Iterator[RunFolder]:
    """The steps of "Start" in order, then the block, then the steps of "End" (R6).

    With the user's own ``-metadir`` (``inv.metadir`` is None) no folder and no lock of the run's own are made; the
    ``-recover`` rules and the sweep still apply. A start step that fails hands what it holds to the end steps,
    which release it, and its error goes on; a lock file whose lock was never taken is left to the one-hour rule.
    """
    start = RunStart(
        paths.runs,
        now,
        run_id=inv.run_id,
        recover=recover_path(inv.extra_args, inv.cwd),
        info=_run_info(inv),
        wait=wait,
        tlc_args=inv.extra_args,
        invocation=inv,
    )
    own = inv.metadir is not None
    try:
        if own:
            start.create_lock_file()
            start.take_lock()
        start.take_recover_lock()
        if own:
            start.make_folder()
            start.write_run_json()
        start.sweep()
    except BaseException:
        _end(start.entered())
        raise
    folder = start.entered()
    try:
        yield folder
    finally:
        _end(folder)


# ---------------------------------------------------------------------- the words of a kept folder


def resume_command(  # noqa: PLR0913 (R6's inputs, each needed)
    inv: TlcInvocation,
    checkpoint_dir: Path,
    *,
    fp: int | None,
    seed: int | None,
    workers_reported: int | None,
    windows: bool = WINDOWS,
) -> str:
    """The command that resumes a kept run, built from the request and the resolved paths (R6)."""
    request = inv.request
    words = ["tlaup", "tlc", str(inv.cwd / inv.spec)]
    if request.cfg is not None and inv.cfg is not None:
        words += ["--cfg", str(inv.cwd / inv.cfg)]
    words.append("--keep")
    if workers_reported is not None and "-workers" not in inv.extra_args:
        words += ["--workers", str(workers_reported)]
    elif request.workers is not None:
        words += ["--workers", request.workers]
    if request.coverage:
        words.append("--coverage")
    if request.raw:
        words.append("--raw")
    words += [f"--java-opt={option}" for option in request.java_opts]
    words.append("--")
    args = list(inv.extra_args)
    index = 0
    while index < len(args):
        if args[index] in ("-recover", "-fp", "-seed"):
            index += 2
            continue
        words.append(args[index])
        index += 1
    if fp is not None:
        words += ["-fp", str(fp)]
    if seed is not None:
        words += ["-seed", str(seed)]
    words += ["-recover", str(checkpoint_dir)]
    return subprocess.list2cmdline(words) if windows else shlex.join(words)


SIZE_UNITS = ("kB", "MB", "GB", "TB")
KILO = 1000


def format_size(n: int) -> str:
    """Decimal units with one decimal: ``512 B``, ``1.5 kB``, ``2.1 GB``. Rounded first, then given the unit of
    what it rounded to, so 999,960 bytes are ``1.0 MB``."""
    if n < KILO:
        return f"{max(n, 0)} B"
    value = float(n)
    for unit in SIZE_UNITS:
        value /= KILO
        tenths = round(value * 10)
        if tenths < KILO * 10 or unit == SIZE_UNITS[-1]:
            return f"{tenths / 10:.1f} {unit}"
    raise AssertionError  # pragma: no cover - the loop returns at its last unit


def _clock_time(moment: datetime, ended: datetime, zone: tzinfo | None) -> str:
    """``HH:MM`` in the local zone (or ``zone``), with the date before it when it is not the day the run ended."""
    local, end_local = moment.astimezone(zone), ended.astimezone(zone)
    if local.date() == end_local.date():
        return f"{local:%H:%M}"
    return f"{local:%Y-%m-%d %H:%M}"


def kept_note(kept: Kept, *, zone: tzinfo | None = None) -> tuple[str, str]:
    """The two lines of R6's note. ``zone``: the zone the checkpoint's time is shown in; None is the local zone."""
    if kept.resume_command is None:
        message = "a kept folder settled without an invocation has no resume command"
        raise ValueError(message)
    detail = (
        f"{format_size(kept.size)}, {kept.reason} after {format_elapsed(kept.stopped_after.total_seconds())}, "
        f"checkpoint of {_clock_time(kept.checkpoint_at, kept.ended, zone)}"
    )
    return f"Checkpoint kept ({detail}): {kept.path}", f"Resume with: {kept.resume_command}"


def reminder(summary: KeptSummary) -> str:
    """The line every ``tlaup tlc`` start prints while kept folders exist (R6)."""
    if summary.count == 1:
        return f"1 kept run folder holds {format_size(summary.size)} (tlaup cache list)"
    return f"{summary.count} kept run folders hold {format_size(summary.size)} (tlaup cache list)"


# ---------------------------------------------------------------------- tlaup cache list and cache clean


UNSETTLED = "unsettled after a kill"


@dataclass(frozen=True)
class RunRecord:
    """One folder, as ``tlaup cache list`` shows it (23 C1); not the reporter's RunInfo."""

    run_id: str
    path: Path
    has_run_json: bool  # False also for one that cannot be read
    spec: str | None
    cfg: str | None
    build: str | None  # the build the checkpoint was written by
    started: datetime | None
    ended: datetime | None
    last_change: datetime  # the newest modification time of anything under the folder
    size: int  # the recorded size of a kept folder, else measured
    in_use: bool  # its lock is held
    kept: bool
    keep: bool
    reason: str | None  # why kept; "unsettled after a kill" for an unsettled resumable folder
    checkpoint_complete: bool


@dataclass(frozen=True)
class CleanReport:
    removed: tuple[str, ...]  # run ids
    freed: int  # bytes
    in_use: tuple[str, ...]  # folders left because their lock was held
    cannot_lock: tuple[str, ...] = ()  # folders left because their lock file could not be opened or made


def _text(record: Mapping[str, object], key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) else None


def _moment(record: Mapping[str, object], key: str) -> datetime | None:
    value = record.get(key)
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _run_record(runs: Path, run_id: str, *, in_use: bool) -> RunRecord:
    folder = runs / run_id
    record = _read_run_json(folder)
    data: Mapping[str, object] = record or {}
    kept, keep = bool(data.get("kept")), bool(data.get("keep"))
    complete = complete_checkpoint(folder) is not None
    recorded = _int_or_none(data.get("size"))
    if kept:
        reason = _text(data, "reason")
    elif record is not None and keep and complete and not in_use:
        reason = UNSETTLED
    else:
        reason = None
    return RunRecord(
        run_id=run_id,
        path=folder,
        has_run_json=record is not None,
        spec=_text(data, "spec"),
        cfg=_text(data, "cfg"),
        build=_text(data, "build"),
        started=_moment(data, "started"),
        ended=_moment(data, "ended"),
        last_change=datetime.fromtimestamp(_newest_change(folder), tz=UTC),
        size=recorded if kept and recorded is not None else _size(folder),
        in_use=in_use,
        kept=kept,
        keep=keep,
        reason=reason,
        checkpoint_complete=complete,
    )


def list_runs(paths: AppPaths) -> list[RunRecord]:
    """One record per folder under ``<cache>/runs/``, by run id; each read under its lock when the lock is free."""
    records = []
    for run_id in list_entries(paths.runs, folders_only=True):
        visit = EntryVisit(paths.runs, run_id, lambda: datetime.now(UTC))
        free = visit.take_lock()
        try:
            records.append(_run_record(paths.runs, run_id, in_use=not free))
        except OSError:
            continue  # the folder went while it was looked at
        finally:
            if free:
                visit.release()
    return records


def clean_runs(paths: AppPaths, *, include_kept: bool, run_id: str | None = None) -> CleanReport:
    """``tlaup cache clean``'s rule for run folders (R6, D49): by default what the sweep would remove and is not
    resumable; with ``include_kept`` every folder whose lock is free; with ``run_id`` that one folder, whatever it
    is, or PathNotFound (4) when no folder has that id and FileOperationError (5) when its lock is held."""
    runs = paths.runs
    if run_id is not None:
        return _clean_one(runs, run_id)
    removed: list[str] = []
    in_use: list[str] = []
    cannot_lock: list[str] = []
    freed = 0
    for entry in list_entries(runs, folders_only=True):
        visit = EntryVisit(runs, entry, lambda: datetime.now(UTC))
        if not visit.take_lock():
            (in_use if visit.lock_error is None else cannot_lock).append(entry)
            continue
        try:
            size = _size(visit.path)
            if visit.clean(include_kept=include_kept):
                removed.append(entry)
                freed += size
        finally:
            visit.release()
    return CleanReport(tuple(removed), freed, tuple(in_use), tuple(cannot_lock))


def _clean_one(runs: Path, run_id: str) -> CleanReport:
    folder = runs / run_id
    if run_id not in list_entries(runs, folders_only=True):
        message = f"no run folder {run_id} in {runs}"
        raise PathNotFound(message, hint="tlaup cache list shows the run folders")
    visit = EntryVisit(runs, run_id, lambda: datetime.now(UTC))
    if not visit.take_lock():
        if visit.lock_error is not None:
            raise _cannot("lock", _lock_file(runs, run_id), visit.lock_error)
        message = f"the run folder {folder} is in use by another tlaup run"
        raise FileOperationError(message)
    try:
        size = _size(folder)
        if not visit.clean(include_kept=True):
            message = f"cannot remove {folder}"
            raise FileOperationError(message)
    finally:
        visit.release()
    return CleanReport((run_id,), size, ())
