"""Question 30: filelock behaviours that design 11 R6 relies on.

Run with the filelock version under test installed, for example
    uv run --no-project --with filelock==4.2.10 python q30/filelock_probe.py
Prints one RESULT line per check. Exits 0 whatever the outcome.

Checks
  recheck      the R6 property, with a deterministic interleaving: a waiter has opened the lock file
               and is about to lock it; the holder removes the lock file and releases; the waiter then
               locks. It must end up holding a lock on the file that exists at the path, and a third
               lock object must be refused.
  recheck_proc the same with the waiter in a second Python process.
  timeout      a second lock object waiting with a timeout raises filelock.Timeout after about that time.
  same_process a second lock object on the same path in the same process is refused (and is not the same
               object: no singleton by default).
  death        a lock held by a process that is killed is free at once.
  left_behind  the lock file is still there after a release (the library does not delete it).
  mtime        taking and releasing the lock of an existing lock file leaves its modification time.
  foreign_file a holder whose lock file was removed and replaced by another process's lock file does not
               remove or unlock that other file when it releases.
  creates      taking a lock creates the lock file when it is missing.
"""

from __future__ import annotations

import contextlib
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import filelock

OS = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
VER = getattr(filelock, "__version__", "?")
WIN = sys.platform == "win32"


def result(name: str, outcome: str, detail: str = "") -> None:
    print(f"RESULT q30 filelock-{name} {OS} : {outcome} (filelock {VER}){' - ' + detail if detail else ''}", flush=True)


def lock_fd(lock: filelock.BaseFileLock) -> int | None:
    ctx = getattr(lock, "_context", None)
    fd = getattr(ctx, "lock_file_fd", None) if ctx is not None else None
    if fd is None:
        fd = getattr(lock, "_lock_file_fd", None)
    return fd


def same_file_at_path(lock: filelock.BaseFileLock, path: Path) -> str:
    fd = lock_fd(lock)
    if fd is None:
        return "no-fd"
    try:
        st_path = os.stat(path)
    except FileNotFoundError:
        return "path-missing"
    st_fd = os.fstat(fd)
    if WIN:
        # st_ino is the file index on Windows (Python 3.5+ fills it from the handle too).
        pass
    return "same" if (st_fd.st_dev, st_fd.st_ino) == (st_path.st_dev, st_path.st_ino) else "different"


class GatedLock:
    """Pause the first native lock attempt made by one thread until told to go on."""

    def __init__(self) -> None:
        self.thread_ident: int | None = None
        self.opened = threading.Event()
        self.go = threading.Event()
        self.done = False
        if WIN:
            import msvcrt

            import filelock._windows as fw

            # filelock 4.x locks with LockFileEx through a module-level helper; older versions call msvcrt.locking.
            # 4.2.12 renamed the helper to lock_fd_nonblocking.
            name = next((n for n in ("lock_fd_nonblocking", "_lock_fd_nonblocking") if hasattr(fw, n)), None)
            if name:
                self.mod, self.attr = fw, name
            else:
                self.mod, self.attr = msvcrt, "locking"
        else:
            import fcntl

            self.mod, self.attr = fcntl, "flock"
        self.real = getattr(self.mod, self.attr)

        def wrapper(fd, *args):
            if not self.done and threading.get_ident() == self.thread_ident:
                self.done = True
                self.opened.set()
                self.go.wait(10)
            return self.real(fd, *args)

        self.wrapper = wrapper

    def __enter__(self):
        setattr(self.mod, self.attr, self.wrapper)
        return self

    def __exit__(self, *exc):
        setattr(self.mod, self.attr, self.real)


def check_recheck(tmp: Path) -> None:
    path = tmp / "recheck.lock"
    holder = filelock.FileLock(str(path))
    holder.acquire()
    gate = GatedLock()
    box: dict = {}

    def waiter() -> None:
        gate.thread_ident = threading.get_ident()
        lock = filelock.FileLock(str(path))
        try:
            lock.acquire(timeout=5)
            box["lock"] = lock
            # The lock's state is thread-local by default, so look at its descriptor from this thread.
            box["at_path"] = same_file_at_path(lock, path)
            box["release"] = threading.Event()
            box["release"].wait(10)
            lock.release()
        except BaseException as e:  # noqa: BLE001
            box["error"] = repr(e)

    with gate:
        t = threading.Thread(target=waiter)
        t.start()
        # The waiter blocks in its first lock call after opening the file; but if the holder still holds the
        # lock that first call would fail anyway. So: let it open, then unlink and release, then let it lock.
        if not gate.opened.wait(5):
            result("recheck", "ERROR", "the waiter never reached the lock call")
            gate.go.set()
            t.join(10)
            holder.release()
            return
        try:
            os.unlink(path)
            unlink = "unlinked"
        except OSError as e:
            unlink = f"unlink-failed:{e.__class__.__name__}"
        holder.release()
        gate.go.set()
        t0 = time.time()
        while "at_path" not in box and "error" not in box and t.is_alive() and time.time() - t0 < 10:
            time.sleep(0.01)
    if "lock" not in box:
        t.join(10)
        result("recheck", "ERROR", f"waiter did not get the lock: {box.get('error')} ({unlink})")
        return
    at_path = box["at_path"]
    third = filelock.FileLock(str(path))
    try:
        third.acquire(timeout=0)
        third_out = "third-GOT-LOCK"
        third.release()
    except filelock.Timeout:
        third_out = "third-refused"
    box["release"].set()
    t.join(10)
    ok = at_path == "same" and third_out == "third-refused"
    result("recheck", "PASS" if ok else "FAIL", f"{unlink}; waiter's file vs path: {at_path}; {third_out}")


WAITER_CODE = r"""
import os, sys, threading, time
sys.path[:0] = []
import filelock
path, ready, go = sys.argv[1], sys.argv[2], sys.argv[3]
if sys.platform == "win32":
    import msvcrt, filelock._windows as fw
    name = next((n for n in ("lock_fd_nonblocking", "_lock_fd_nonblocking") if hasattr(fw, n)), None)
    mod, attr = (fw, name) if name else (msvcrt, "locking")
else:
    import fcntl as mod; attr = "flock"
real = getattr(mod, attr)
state = {"done": False}
def wrapper(fd, *a):
    if not state["done"]:
        state["done"] = True
        open(ready, "w").close()
        t0 = time.time()
        while not os.path.exists(go) and time.time() - t0 < 10:
            time.sleep(0.01)
    return real(fd, *a)
setattr(mod, attr, wrapper)
lock = filelock.FileLock(path)
lock.acquire(timeout=5)
setattr(mod, attr, real)
fd = lock._context.lock_file_fd if hasattr(lock, "_context") else None
try:
    sp = os.stat(path); sf = os.fstat(fd)
    same = "same" if (sp.st_dev, sp.st_ino) == (sf.st_dev, sf.st_ino) else "different"
except FileNotFoundError:
    same = "path-missing"
print("WAITER", same, flush=True)
sys.stdin.readline()
lock.release()
"""


def check_recheck_proc(tmp: Path) -> None:
    path = tmp / "recheck-proc.lock"
    ready, go = tmp / "ready", tmp / "go"
    holder = filelock.FileLock(str(path))
    holder.acquire()
    p = subprocess.Popen(
        [sys.executable, "-c", WAITER_CODE, str(path), str(ready), str(go)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        t0 = time.time()
        while not ready.exists() and time.time() - t0 < 15:
            time.sleep(0.01)
        if not ready.exists():
            result("recheck_proc", "ERROR", "waiter never reached the lock call")
            return
        try:
            os.unlink(path)
            unlink = "unlinked"
        except OSError as e:
            unlink = f"unlink-failed:{e.__class__.__name__}"
        holder.release()
        go.touch()
        line = ""
        t0 = time.time()
        line = p.stdout.readline().strip()
        third = filelock.FileLock(str(path))
        try:
            third.acquire(timeout=0)
            third_out = "third-GOT-LOCK"
            third.release()
        except filelock.Timeout:
            third_out = "third-refused"
        p.stdin.write("\n")
        p.stdin.flush()
        p.wait(10)
        ok = line == "WAITER same" and third_out == "third-refused"
        err = p.stderr.read().strip().splitlines()[-1:] if not line else []
        result("recheck_proc", "PASS" if ok else "FAIL", f"{unlink}; waiter: {line or err}; {third_out}")
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def check_timeout(tmp: Path) -> None:
    path = tmp / "timeout.lock"
    a = filelock.FileLock(str(path))
    a.acquire()
    b = filelock.FileLock(str(path))
    t0 = time.monotonic()
    try:
        b.acquire(timeout=0.5)
        out, ok = "GOT-LOCK", False
    except filelock.Timeout:
        out, ok = "Timeout", True
    dt = time.monotonic() - t0
    a.release()
    ok = ok and 0.4 <= dt <= 3
    result("timeout", "PASS" if ok else "FAIL", f"{out} after {dt:.2f}s for timeout=0.5")


def check_same_process(tmp: Path) -> None:
    path = tmp / "same.lock"
    a = filelock.FileLock(str(path))
    b = filelock.FileLock(str(path))
    identical = a is b
    a.acquire()
    try:
        b.acquire(timeout=0)
        out = "second-object-GOT-LOCK"
        b.release()
    except filelock.Timeout:
        out = "second-object-refused"
    except Exception as e:  # noqa: BLE001
        out = f"second-object-raised:{e.__class__.__name__}:{e}"
    # Same object again: reentrant counter?
    try:
        a.acquire(timeout=0)
        reent = f"same-object-reentrant(counter={getattr(a, 'lock_counter', '?')})"
        a.release()
    except filelock.Timeout:
        reent = "same-object-refused"
    a.release()
    # From another thread, a separate object.
    a.acquire()
    box = {}

    def other() -> None:
        c = filelock.FileLock(str(path))
        try:
            c.acquire(timeout=0)
            box["r"] = "other-thread-object-GOT-LOCK"
            c.release()
        except filelock.Timeout:
            box["r"] = "other-thread-object-refused"

    t = threading.Thread(target=other)
    t.start()
    t.join(10)
    a.release()
    ok = (not identical) and out == "second-object-refused" and box.get("r") == "other-thread-object-refused"
    result("same_process", "PASS" if ok else "FAIL", f"singleton={identical}; {out}; {reent}; {box.get('r')}")


def check_death(tmp: Path) -> None:
    path = tmp / "death.lock"
    code = (
        "import sys, filelock, time; l = filelock.FileLock(sys.argv[1]); l.acquire(); "
        "print('held', flush=True); time.sleep(60)"
    )
    p = subprocess.Popen([sys.executable, "-c", code, str(path)], stdout=subprocess.PIPE, text=True)
    try:
        if p.stdout.readline().strip() != "held":
            result("death", "ERROR", "child did not take the lock")
            return
        b = filelock.FileLock(str(path))
        try:
            b.acquire(timeout=0)
            before = "GOT-LOCK-while-child-alive"
            b.release()
        except filelock.Timeout:
            before = "refused-while-alive"
        p.kill()
        p.wait(10)
        t0 = time.monotonic()
        try:
            b.acquire(timeout=2)
            after = f"free-after-kill({time.monotonic() - t0:.2f}s)"
            b.release()
        except filelock.Timeout:
            after = "still-held-after-kill"
        ok = before == "refused-while-alive" and after.startswith("free")
        result("death", "PASS" if ok else "FAIL", f"{before}; {after}")
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()


def check_left_behind(tmp: Path) -> None:
    path = tmp / "left.lock"
    a = filelock.FileLock(str(path))
    a.acquire()
    a.release()
    result("left_behind", "PASS" if path.exists() else "FAIL", "file kept after release" if path.exists() else "library deleted the lock file on release")


def check_mtime(tmp: Path) -> None:
    path = tmp / "mtime.lock"
    path.touch()
    old = time.time() - 7200
    os.utime(path, (old, old))
    a = filelock.FileLock(str(path))
    a.acquire()
    m1 = os.stat(path).st_mtime if path.exists() else None
    a.release()
    m2 = os.stat(path).st_mtime if path.exists() else None
    ok = m1 is not None and abs(m1 - old) < 1 and (m2 is None or abs(m2 - old) < 1)
    det = f"while held: {'unchanged' if m1 and abs(m1 - old) < 1 else 'CHANGED'}; after release: " + (
        "file gone" if m2 is None else ("unchanged" if abs(m2 - old) < 1 else "CHANGED")
    )
    result("mtime", "PASS" if ok else "FAIL", det)


def check_foreign_file(tmp: Path) -> None:
    path = tmp / "foreign.lock"
    a = filelock.FileLock(str(path))
    a.acquire()
    try:
        os.unlink(path)
    except OSError as e:
        a.release()
        result("foreign_file", "SKIP", f"cannot unlink a held lock file here: {e.__class__.__name__}")
        return
    d = filelock.FileLock(str(path))
    d.acquire(timeout=1)
    a.release()
    exists = path.exists()
    e = filelock.FileLock(str(path))
    try:
        e.acquire(timeout=0)
        third = "third-GOT-LOCK"
        e.release()
    except filelock.Timeout:
        third = "third-refused"
    d.release()
    ok = exists and third == "third-refused"
    result("foreign_file", "PASS" if ok else "FAIL", f"other's file {'kept' if exists else 'REMOVED'} by old holder's release; {third}")


def check_creates(tmp: Path) -> None:
    path = tmp / "creates.lock"
    a = filelock.FileLock(str(path))
    a.acquire()
    ex = path.exists()
    a.release()
    result("creates", "PASS" if ex else "FAIL", "lock file created by acquire" if ex else "no file while held")


def main() -> None:
    print(f"q30 filelock_probe: filelock {VER}, Python {platform.python_version()}, {platform.system()} {platform.machine()}, FileLock={filelock.FileLock.__name__}")
    with tempfile.TemporaryDirectory(dir=os.environ.get("Q30_TMP")) as d:
        tmp = Path(d)
        for check in (check_recheck, check_recheck_proc, check_timeout, check_same_process, check_death,
                      check_left_behind, check_mtime, check_foreign_file, check_creates):
            sub = tmp / check.__name__
            sub.mkdir()
            try:
                check(sub)
            except Exception as e:  # noqa: BLE001
                result(check.__name__.removeprefix("check_"), "ERROR", f"{e.__class__.__name__}: {e}")


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        main()
    sys.exit(0)
