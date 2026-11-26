"""The lock rules the run folders rest on (design 11 R6, formal check and D51; package 35a).

The second look is reached by running the holder's removal and release inside the waiter's lock attempt, just
before its ``flock`` (the ``before_the_next_flock`` fixture of this folder's conftest): the waiter has opened the
old file and then locks a file that no longer has the name.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import filelock
import pytest

from tests.clock import FakeClock
from tlaup.errors import FileOperationError
from tlaup.tlc.rundirs import EntryVisit, RunLock

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.skipif(os.name != "posix", reason="flock and pass_fds: Linux and macOS (D15)")


def probe(path: Path) -> bool:
    """One attempt by a lock object of the test's own; True if it got the lock (released at once)."""
    lock = filelock.FileLock(path)
    try:
        lock.acquire(timeout=0)
    except filelock.Timeout:
        return False
    lock.release()
    return True


def identity(path: Path) -> tuple[int, int]:
    info = path.stat()
    return info.st_dev, info.st_ino


def held_identity(lock: RunLock) -> tuple[int, int]:
    fd = lock.duplicate()
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    return info.st_dev, info.st_ino


# ---------------------------------------------------------------------- RunLock


def test_a_waiter_holds_the_file_at_the_name_after_the_holder_removed_it(
    tmp_path: Path, before_the_next_flock: Callable[[Callable[[], None]], None]
) -> None:
    path = tmp_path / "run0.lock"
    holder = RunLock(path, wait=0)
    holder.acquire()

    def holder_ends() -> None:
        holder.remove_file()
        holder.release()

    before_the_next_flock(holder_ends)
    waiter = RunLock(path, wait=5)
    waiter.acquire()
    assert path.exists()
    assert held_identity(waiter) == identity(path)
    with pytest.raises(FileOperationError):
        RunLock(path, wait=0).acquire()
    waiter.release()


def test_a_release_leaves_the_lock_file_and_its_time(tmp_path: Path) -> None:
    path = tmp_path / "run0.lock"
    path.touch()
    old = time.time() - 7200
    os.utime(path, (old, old))
    lock = RunLock(path, wait=0)
    lock.acquire()
    assert path.stat().st_mtime == old
    lock.release()
    assert path.exists()
    assert path.stat().st_mtime == old


def test_a_wait_of_zero_makes_one_attempt(tmp_path: Path) -> None:
    path = tmp_path / "run0.lock"
    holder = RunLock(path, wait=0)
    holder.acquire()
    with pytest.raises(FileOperationError, match="held by another tlaup run"):
        RunLock(path, wait=0).acquire()
    holder.release()
    RunLock(path, wait=0).acquire()


def test_a_release_after_the_name_went_to_another_file_leaves_that_file(tmp_path: Path) -> None:
    path = tmp_path / "run0.lock"
    first = RunLock(path, wait=0)
    first.acquire()
    first.remove_file()
    second = RunLock(path, wait=0)
    second.acquire()  # the lock of a new file under the name
    first.release()
    assert path.exists()
    assert held_identity(second) == identity(path)
    assert not probe(path)
    second.release()


def test_abandon_closes_without_unlocking_and_release_after_it_does_nothing(tmp_path: Path) -> None:
    path = tmp_path / "run0.lock"
    lock = RunLock(path, wait=0)
    lock.acquire()
    lock.abandon()  # nothing else holds the descriptor, so the system frees the lock
    lock.release()
    assert probe(path)


# ---------------------------------------------------------------------- the FileLock of a visit


def test_a_visit_never_holds_a_file_that_lost_its_name(
    tmp_path: Path, before_the_next_flock: Callable[[Callable[[], None]], None]
) -> None:
    clock = FakeClock()
    runs = tmp_path
    path = runs / "run0.lock"
    holder = EntryVisit(runs, "run0", clock.now)
    assert holder.take_lock()

    def holder_ends() -> None:
        path.unlink()
        holder.release()

    before_the_next_flock(holder_ends)
    waiter = EntryVisit(runs, "run0", clock.now)
    if not waiter.take_lock():  # one attempt: it saw the file gone under its lock and let go
        assert waiter.take_lock()
    assert path.exists()
    assert not EntryVisit(runs, "run0", clock.now).take_lock()
    waiter.release()


def test_a_visit_leaves_the_lock_file_and_its_time(tmp_path: Path) -> None:
    path = tmp_path / "run0.lock"
    path.touch()
    old = time.time() - 7200
    os.utime(path, (old, old))
    visit = EntryVisit(tmp_path, "run0", FakeClock().now)
    assert visit.take_lock()
    assert path.stat().st_mtime == old
    visit.release()
    assert path.exists()
    assert path.stat().st_mtime == old


def test_a_visit_released_after_the_name_went_to_another_file_leaves_that_file(tmp_path: Path) -> None:
    clock = FakeClock()
    path = tmp_path / "run0.lock"
    first = EntryVisit(tmp_path, "run0", clock.now)
    assert first.take_lock()
    path.unlink()
    second = EntryVisit(tmp_path, "run0", clock.now)
    assert second.take_lock()
    first.release()
    assert path.exists()
    assert not probe(path)
    second.release()


def test_a_visit_and_a_run_lock_exclude_each_other(tmp_path: Path) -> None:
    path = tmp_path / "run0.lock"
    lock = RunLock(path, wait=0)
    lock.acquire()
    assert not EntryVisit(tmp_path, "run0", FakeClock().now).take_lock()
    lock.release()
    visit = EntryVisit(tmp_path, "run0", FakeClock().now)
    assert visit.take_lock()
    with pytest.raises(FileOperationError):
        RunLock(path, wait=0).acquire()
    visit.release()


# ---------------------------------------------------------------------- the inherited lock (D51)

PARENT = """
import os, subprocess, sys
from pathlib import Path
from tlaup.tlc.rundirs import RunLock
path, gate = Path(sys.argv[1]), int(sys.argv[2])
lock = RunLock(path, wait=0)
lock.acquire()
fd = lock.duplicate()
child = subprocess.Popen(
    [sys.executable, "-c", "import os, sys; os.read(int(sys.argv[1]), 1)", str(gate)],
    pass_fds=(fd, gate), stdin=subprocess.DEVNULL,
)
os.close(fd)
os.close(gate)
print(child.pid, flush=True)
if sys.stdin.readline().strip() == "release":
    lock.release()
    print("released", flush=True)
    sys.stdin.readline()
"""


def wait_until(condition: Callable[[], bool], *, timeout: float = 30) -> bool:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            return False
        time.sleep(0.01)
    return True


@pytest.mark.parametrize("parent_ends", ["killed", "released"])
def test_the_jvm_keeps_the_run_lock(tmp_path: Path, parent_ends: str) -> None:
    path = tmp_path / "run0.lock"
    gate_read, gate_write = os.pipe()  # the child ends when the test writes to it
    parent = subprocess.Popen(
        [sys.executable, "-c", PARENT, str(path), str(gate_read)],
        pass_fds=(gate_read,),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    os.close(gate_read)
    try:
        assert parent.stdout is not None
        assert parent.stdout.readline().strip().isdigit()
        assert not probe(path), "a held RunLock was free"
        if parent_ends == "killed":
            parent.kill()
            parent.wait(timeout=30)
            assert not probe(path), "the child did not keep the lock after its parent was killed"
        else:
            assert parent.stdin is not None
            parent.stdin.write("release\n")
            parent.stdin.flush()
            assert parent.stdout.readline().strip() == "released"
            assert probe(path), "a release in the parent did not free the child's copy"
    finally:
        os.write(gate_write, b"x")
        os.close(gate_write)
        parent.communicate("\n" if parent.poll() is None else None, timeout=30)
    assert wait_until(lambda: probe(path)), "the lock stayed held after the child ended"
