"""Question 33 (POSIX: Linux and macOS): can a run's lock outlive a killed tlaup by letting the child inherit it?

Run from the `ci` folder with filelock 4.2.10 available, for example
    uv run --no-project --with filelock==4.2.10 python q33/inherit_lock_posix.py
Without filelock the filelock parts print "skipped". `java` must be on PATH (or set Q33_JAVA); the real-TLC
checks use TLA2TOOLS_174 and TLA2TOOLS_ROLLING when set. Optional argument: a substring; only the checks
whose name contains it run. Prints one RESULT line per check and exits 0 whatever the outcome.

Each check has three processes: a "holder" (stands for tlaup) takes the lock, starts a child (stands for the
JVM) with the lock's descriptor passed on or not, and then does one thing: is killed with SIGKILL by the
driver, releases normally, closes its descriptor without unlocking, or exits normally. The driver then tries
the lock from third processes (filelock with timeout 0, a raw flock on a fresh open, and a raw lockf where
that is the lock in use) while the child lives, and again after the child has ended on its own.

Holder variants ("how"):
  fl-hook        filelock.FileLock with the public on_acquired hook, which hands over the descriptor; pass_fds
  fl-private     filelock.FileLock, descriptor read from lock._context.lock_file_fd (private); pass_fds
  fl-descriptor  os.open by the holder, then the public filelock.lock_descriptor(fd); pass_fds
  flock          os.open + fcntl.flock by the holder; pass_fds
  lockf          os.open + fcntl.lockf (a POSIX record lock); pass_fds
  fl-noinherit   filelock.FileLock, child started without pass_fds (the default, close_fds=True): control
  fl-preexec     as fl-hook, but Popen also gets preexec_fn (what PR_SET_PDEATHSIG from Python would need)
  fl-dup-preexec as fl-preexec, but the child gets an os.dup of filelock's descriptor
  flock-preexec  as flock, with preexec_fn: the control for fl-preexec
"""

from __future__ import annotations

import contextlib
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OS = {"linux": "linux", "darwin": "macos"}.get(sys.platform, sys.platform)
SCRIPT = os.path.abspath(__file__)

try:
    import filelock  # noqa: F401

    HAVE_FL = True
    FL_VER = filelock.__version__
except ImportError:
    HAVE_FL = False
    FL_VER = "absent"

SLEEP_JAVA = """public class Sleep { public static void main(String[] a) throws Exception {
  Thread.sleep((long) (Double.parseDouble(a[0]) * 1000)); } }
"""

LONG_TLA = """---- MODULE Long ----
EXTENDS Naturals
CONSTANT N
VARIABLES x, y
Init == x = 0 /\\ y = 0
Next == \\/ x < N /\\ x' = x + 1 /\\ UNCHANGED y
        \\/ y < N /\\ y' = y + 1 /\\ UNCHANGED x
====
"""


# ---------------------------------------------------------------------------------------------------------------
# third process: one lock attempt
def role_try(path: str, method: str) -> None:
    import fcntl

    try:
        if method == "filelock":
            if not HAVE_FL:
                print("skipped")
                return
            import filelock as fl

            lk = fl.FileLock(path, timeout=0)
            try:
                lk.acquire()
            except fl.Timeout:
                print("refused")
                return
            lk.release()
            print("granted")
            return
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            if method == "flock":
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
            else:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.lockf(fd, fcntl.LOCK_UN)
            print("granted")
        except OSError as e:
            print("refused" if e.errno in (11, 35, 13) else f"error:{e.errno}")
        finally:
            os.close(fd)
    except Exception as e:  # report, never crash
        print(f"error:{type(e).__name__}:{e}")


# ---------------------------------------------------------------------------------------------------------------
# holder: stands for tlaup
_KEEP = []  # module-level references, so an "exit" holder still has its lock object at interpreter exit


def role_holder(how: str, after: str, path: str, child: list[str]) -> None:
    import fcntl

    fd = None
    lock = None
    got = {}
    if how in ("fl-hook", "fl-preexec", "fl-noinherit", "fl-private", "fl-dup-preexec"):
        import filelock as fl

        if how == "fl-private":
            lock = fl.FileLock(path)
        else:
            lock = fl.FileLock(path, on_acquired=lambda d: got.__setitem__("fd", d))
        lock.acquire(timeout=5)
        fd = lock._context.lock_file_fd if how == "fl-private" else got["fd"]
        _KEEP.append(lock)
        if how == "fl-dup-preexec":
            fd = os.dup(fd)  # same open file description, a descriptor filelock does not know about
    elif how == "fl-descriptor":
        import filelock as fl

        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        if not fl.lock_descriptor(fd, blocking=False):
            print("HOLDER-ERROR not locked", flush=True)
            return
    elif how in ("flock", "flock-preexec"):
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    elif how == "lockf":
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    inheritable = os.get_inheritable(fd)
    kw = {}
    if how != "fl-noinherit":
        kw["pass_fds"] = (fd,)
    if how.endswith("preexec"):
        kw["preexec_fn"] = lambda: None
    log = open(os.path.join(os.path.dirname(path), "child.log"), "ab")
    try:
        p = subprocess.Popen(child, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **kw)
    except Exception as e:
        print(f"HOLDER-ERROR popen {type(e).__name__}: {e}", flush=True)
        return
    print(f"CHILD {p.pid} FD {fd} INHERITABLE-IN-HOLDER {inheritable}", flush=True)
    time.sleep(0.5)
    if after == "release":
        if lock is not None:
            lock.release()
        elif how == "fl-descriptor":
            import filelock as fl

            fl.unlock_descriptor(fd)
        elif how == "flock":
            fcntl.flock(fd, fcntl.LOCK_UN)
        else:
            fcntl.lockf(fd, fcntl.LOCK_UN)
        print("DONE", flush=True)
    elif after == "close":
        # close our descriptor without unlocking (not possible through FileLock's public API)
        os.close(fd)
        print("DONE", flush=True)
    elif after == "exit":
        print("DONE", flush=True)
        return  # normal interpreter exit with the lock object still referenced
    time.sleep(600)


# ---------------------------------------------------------------------------------------------------------------
# driver
def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if OS == "linux":
        try:
            # A thread-group leader that has exited shows "Z" while the other threads (a JVM's) still run and
            # still hold the descriptors, so count the threads too.
            st = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            threads = next((int(ln.split()[1]) for ln in Path(f"/proc/{pid}/status").read_text().splitlines()
                            if ln.startswith("Threads:")), 1)
            return st != "Z" or threads > 1
        except OSError:
            return False
    try:
        out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
        return bool(out.stdout.strip()) and not out.stdout.strip().startswith("Z")
    except Exception:
        return True


def fd_in_child(pid: int, path: str) -> str:
    real = os.path.realpath(path)
    if OS == "linux":
        try:
            fds = [n for n in os.listdir(f"/proc/{pid}/fd")
                   if os.path.realpath(os.readlink(f"/proc/{pid}/fd/{n}")) == real]
            locks = []
            for n in fds:
                with contextlib.suppress(OSError):
                    locks += [ln.split(":", 2)[2].strip().split()[0:3] for ln in
                              Path(f"/proc/{pid}/fdinfo/{n}").read_text().splitlines() if ln.startswith("lock:")]
            kinds = ",".join(" ".join(k) for k in locks) or "none listed"
            return ("fd " + ",".join(fds) + f" (fdinfo lock: {kinds})") if fds else "no fd"
        except OSError as e:
            return f"unknown ({e.errno})"
    if shutil.which("lsof"):
        try:
            out = subprocess.run(["lsof", "-a", "-p", str(pid), "-Fn"], capture_output=True, text=True, timeout=20)
            names = [ln[1:] for ln in out.stdout.splitlines() if ln.startswith("n")]
            return "open" if any(os.path.realpath(n) == real or n.endswith(os.path.basename(path)) for n in names) \
                else "not open"
        except Exception as e:
            return f"unknown ({type(e).__name__})"
    return "unknown (no lsof)"


def attempt(path: str, method: str) -> str:
    try:
        r = subprocess.run([sys.executable, SCRIPT, "try", path, method], capture_output=True, text=True, timeout=30)
        return (r.stdout.strip() or ("error:" + r.stderr.strip()[-200:])).splitlines()[-1]
    except subprocess.TimeoutExpired:
        return "error:timeout"


def readline(proc: subprocess.Popen, deadline: float) -> str:
    import selectors

    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    while time.time() < deadline:
        if sel.select(timeout=0.2):
            line = proc.stdout.readline()
            return line.decode(errors="replace").strip() if line else ""
        if proc.poll() is not None:
            line = proc.stdout.readline()
            return line.decode(errors="replace").strip()
    return ""


def kill_quiet(pid: int | None) -> None:
    if pid:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)


def run_check(name: str, work: Path, how: str, after: str, child: list[str], child_timeout: float) -> None:
    lockdir = work / name
    lockdir.mkdir(parents=True, exist_ok=True)
    path = str(lockdir / "run.lock")
    methods = ["filelock", "flock"] + (["lockf"] if how == "lockf" else [])
    needs_fl = how.startswith("fl-")
    if needs_fl and not HAVE_FL:
        print(f"RESULT q33 {name} {OS} : skipped (filelock not installed)", flush=True)
        return
    holder = subprocess.Popen([sys.executable, SCRIPT, "holder", how, after, path, "--", *child],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cpid = None
    detail = []
    try:
        line = readline(holder, time.time() + 60)
        if not line.startswith("CHILD"):
            err = holder.stderr.read().decode(errors="replace")[-300:] if holder.poll() is not None else ""
            print(f"RESULT q33 {name} {OS} : error (holder said {line!r}) {err!r}", flush=True)
            return
        parts = line.split()
        cpid = int(parts[1])
        detail.append(f"holder-fd={parts[3]} inheritable-in-holder={parts[5]}")
        time.sleep(1.0)  # give a JVM time to start
        if after in ("kill",):
            holder.kill()
            holder.wait(timeout=10)
        else:
            done = readline(holder, time.time() + 30)
            if done != "DONE":
                detail.append(f"holder said {done!r}")
            if after == "exit":
                holder.wait(timeout=30)
                detail.append(f"holder exit code {holder.returncode}")
        time.sleep(0.5)
        if not alive(cpid):
            log = (lockdir / "child.log").read_bytes()[-300:].decode(errors="replace")
            print(f"RESULT q33 {name} {OS} : inconclusive (child ended before the check) "
                  f"{'; '.join(detail)}; child log tail {log!r}", flush=True)
            return
        during = {m: attempt(path, m) for m in methods}
        fdinfo = fd_in_child(cpid, path)
        # wait for the child to end by itself
        deadline = time.time() + child_timeout
        while alive(cpid) and time.time() < deadline:
            time.sleep(0.2)
        ended = not alive(cpid)
        if not ended:
            kill_quiet(cpid)
        time.sleep(1.0)  # let the exit finish where it could not be observed (macOS)
        afterwards = {m: attempt(path, m) for m in methods}
        tail = (lockdir / "child.log").read_bytes()[-3000:].decode(errors="replace").strip().splitlines()
        last = next((ln for ln in reversed(tail) if "Finished" in ln or "rror" in ln), tail[-1] if tail else "")
        if last:
            detail.append(f"child log: {last.strip()[:100]!r}")
        d = " ".join(f"{m}={v}" for m, v in during.items())
        a = " ".join(f"{m}={v}" for m, v in afterwards.items())
        held = all(v == "refused" for v in during.values())
        free = all(v == "granted" for v in afterwards.values())
        verdict = ("lock held by child after holder " + after + ", freed when child ended") if held and free else \
            ("lock NOT held by child after holder " + after) if all(v == "granted" for v in during.values()) else \
            "mixed"
        print(f"RESULT q33 {name} {OS} : {verdict} | while child lives: {d}; child has lock file: {fdinfo}"
              f" | after child {'ended by itself' if ended else 'was killed (timeout)'}: {a} | {'; '.join(detail)}",
              flush=True)
    finally:
        kill_quiet(holder.pid if holder.poll() is None else None)
        with contextlib.suppress(Exception):
            holder.wait(timeout=5)
        if cpid and alive(cpid):
            kill_quiet(cpid)


def java_version(java: str) -> str:
    try:
        r = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=30)
        return (r.stderr or r.stdout).splitlines()[0]
    except Exception as e:
        return f"unavailable ({type(e).__name__})"


def main(args: list[str]) -> None:
    sel = args[0] if args else ""
    java = os.environ.get("Q33_JAVA") or shutil.which("java") or "java"
    jv = java_version(java)
    print(f"INFO q33 {OS} python {platform.python_version()} filelock {FL_VER} java: {jv}", flush=True)
    base = Path(os.environ.get("Q33_WORK") or tempfile.mkdtemp(prefix="q33-", dir=os.getcwd()))
    base.mkdir(parents=True, exist_ok=True)
    (base / "Sleep.java").write_text(SLEEP_JAVA)
    (base / "Long.tla").write_text(LONG_TLA)
    n = os.environ.get("Q33_TLC_N", "1500")
    (base / "Long.cfg").write_text(f"INIT Init\nNEXT Next\nCONSTANT N = {n}\n")
    py_sleep = [sys.executable, "-c", "import time, sys; time.sleep(float(sys.argv[1]))", "6"]
    j_sleep = [java, str(base / "Sleep.java"), "10"]
    checks = []
    for how in ("fl-hook", "fl-private", "fl-descriptor", "flock", "lockf", "fl-noinherit", "fl-preexec",
                "fl-dup-preexec", "flock-preexec"):
        checks.append((f"py-{how}-kill", how, "kill", py_sleep, 30))
    for how, after in (("fl-hook", "release"), ("flock", "release"), ("flock", "close"), ("fl-hook", "exit"),
                       ("flock", "exit")):
        checks.append((f"py-{how}-{after}", how, after, py_sleep, 30))
    checks.append(("java-sleep-fl-hook-kill", "fl-hook", "kill", j_sleep, 60))
    checks.append(("java-sleep-flock-kill", "flock", "kill", j_sleep, 60))
    for label, var in (("tlc174", "TLA2TOOLS_174"), ("tlcrolling", "TLA2TOOLS_ROLLING")):
        jar = os.environ.get(var)
        if not jar:
            if sel in label:
                print(f"RESULT q33 {label}-fl-hook-kill {OS} : skipped ({var} not set)", flush=True)
            continue
        meta = base / f"meta-{label}"
        tlc = [java, "-XX:+UseParallelGC", "-cp", jar, "tlc2.TLC", "-workers", "1", "-deadlock",
               "-metadir", str(meta), "-config", str(base / "Long.cfg"), str(base / "Long.tla")]
        checks.append((f"{label}-fl-hook-kill", "fl-hook", "kill", tlc, 600))
    for name, how, after, child, tmo in checks:
        if sel and sel not in name:
            continue
        try:
            run_check(name, base, how, after, child, tmo)
        except Exception as e:
            print(f"RESULT q33 {name} {OS} : error ({type(e).__name__}: {e})", flush=True)
    if not os.environ.get("Q33_WORK"):
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "try":
        role_try(sys.argv[2], sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == "holder":
        i = sys.argv.index("--")
        role_holder(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[i + 1:])
    else:
        main(sys.argv[1:])
    sys.exit(0)
