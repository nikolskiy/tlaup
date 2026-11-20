"""Question 33 (Windows): can a run's lock outlive a killed tlaup by letting the child inherit the lock's handle?

Run from the `ci` folder with filelock 4.2.10 available, for example
    uv run --no-project --with filelock==4.2.10 python q33/inherit_lock_windows.py
Without filelock the filelock parts print "skipped". `java` must be on PATH (or set Q33_JAVA); the real-TLC
checks use TLA2TOOLS_174 and TLA2TOOLS_ROLLING when set. Optional argument: a substring; only the checks whose
name contains it run. Prints one RESULT line per check and exits 0 whatever the outcome.

filelock 4.2.10 on Windows locks one byte at offset 0 with LockFileEx on a handle it opens non-inheritable
(O_NOINHERIT). Byte-range locks belong to the process that took them, so the expectation is that an inherited
handle does NOT keep the lock after the holder is killed. The second mechanism tried is a share-mode "lock":
a handle opened without FILE_SHARE_WRITE makes every later open for writing fail with a sharing violation for as
long as any copy of the handle is open, in any process.

Each check: a "holder" (stands for tlaup) takes the lock, starts a child (stands for the JVM) with the handle
made inheritable and passed in STARTUPINFO's handle list, and is then killed (TerminateProcess) by the driver.
The driver tries the lock from third processes while the child lives and again after it ended by itself:
filelock with timeout 0, and a raw attempt (os.open for read/write, then msvcrt.locking of byte 0).

Holder variants:
  fl-hook        filelock.FileLock with the public on_acquired hook (gives the descriptor); handle inherited
  fl-descriptor  os.open by the holder, then the public filelock.lock_descriptor(fd); handle inherited
  msvcrt         os.open + msvcrt.locking(LK_NBLCK, 1 byte at 0); handle inherited
  fl-noinherit   filelock.FileLock, child started without the handle: control
  share-deny     CreateFileW(GENERIC_READ, FILE_SHARE_READ, inheritable); no byte-range lock; handle inherited
  share-deny-own as share-deny, but the holder then closes its own copy (only the child's copy is left)
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OS = "windows" if sys.platform == "win32" else sys.platform
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

if sys.platform == "win32":
    from ctypes import wintypes

    K32 = ctypes.WinDLL("kernel32", use_last_error=True)
    K32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    K32.CreateFileW.restype = wintypes.HANDLE
    K32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    K32.OpenProcess.restype = wintypes.HANDLE
    K32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    K32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    K32.CloseHandle.argtypes = [wintypes.HANDLE]

    class SECURITY_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p),
                    ("bInheritHandle", wintypes.BOOL)]


def role_try(path: str, method: str) -> None:
    try:
        if method == "filelock":
            if not HAVE_FL:
                print("skipped")
                return
            import filelock as fl

            lk = fl.FileLock(path, timeout=0, preserve_lock_file=True)
            try:
                lk.acquire()
            except fl.Timeout:
                print("refused")
                return
            lk.release()
            print("granted")
            return
        import msvcrt

        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT)
        except PermissionError as e:
            print(f"refused(open:{e.winerror})")
            return
        try:
            os.lseek(fd, 0, 0)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            os.lseek(fd, 0, 0)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            print("granted")
        except OSError as e:
            print(f"refused(lock:{e.errno})")
        finally:
            os.close(fd)
    except Exception as e:
        print(f"error:{type(e).__name__}:{e}")


_KEEP = []


def role_holder(how: str, path: str, child: list[str]) -> None:
    import msvcrt

    handle = None
    if how in ("fl-hook", "fl-noinherit"):
        import filelock as fl

        got = {}
        lock = fl.FileLock(path, on_acquired=lambda d: got.__setitem__("fd", d))
        lock.acquire(timeout=5)
        _KEEP.append(lock)
        handle = msvcrt.get_osfhandle(got["fd"])
    elif how == "fl-descriptor":
        import filelock as fl

        fd = os.open(path, os.O_RDWR | os.O_CREAT)
        if not fl.lock_descriptor(fd, blocking=False):
            print("HOLDER-ERROR not locked", flush=True)
            return
        handle = msvcrt.get_osfhandle(fd)
    elif how == "msvcrt":
        fd = os.open(path, os.O_RDWR | os.O_CREAT)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        handle = msvcrt.get_osfhandle(fd)
    elif how.startswith("share-deny"):
        sa = SECURITY_ATTRIBUTES(ctypes.sizeof(SECURITY_ATTRIBUTES), None, True)
        GENERIC_READ, FILE_SHARE_READ, OPEN_ALWAYS, NORMAL = 0x80000000, 1, 4, 0x80
        h = K32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, ctypes.byref(sa), OPEN_ALWAYS, NORMAL, None)
        if h in (None, wintypes.HANDLE(-1).value):
            print(f"HOLDER-ERROR CreateFileW {ctypes.get_last_error()}", flush=True)
            return
        handle = h
    kw = {}
    if how != "fl-noinherit":
        os.set_handle_inheritable(handle, True)
        si = subprocess.STARTUPINFO()
        si.lpAttributeList = {"handle_list": [handle]}
        kw["startupinfo"] = si
    log = open(os.path.join(os.path.dirname(path), "child.log"), "ab")
    try:
        p = subprocess.Popen(child, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             close_fds=True, **kw)
    except Exception as e:
        print(f"HOLDER-ERROR popen {type(e).__name__}: {e}", flush=True)
        return
    if how == "share-deny-own":
        K32.CloseHandle(handle)
    print(f"CHILD {p.pid} HANDLE {handle}", flush=True)
    time.sleep(600)


def alive(pid: int) -> bool:
    h = K32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        K32.GetExitCodeProcess(h, ctypes.byref(code))
        return code.value == 259  # STILL_ACTIVE
    finally:
        K32.CloseHandle(h)


def kill_pid(pid: int) -> None:
    h = K32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
    if h:
        K32.TerminateProcess(h, 1)
        K32.CloseHandle(h)


def attempt(path: str, method: str) -> str:
    try:
        r = subprocess.run([sys.executable, SCRIPT, "try", path, method], capture_output=True, text=True, timeout=30)
        return (r.stdout.strip() or ("error:" + r.stderr.strip()[-200:])).splitlines()[-1]
    except subprocess.TimeoutExpired:
        return "error:timeout"


def readline_with_timeout(proc: subprocess.Popen, seconds: float) -> str:
    import threading

    out = []
    t = threading.Thread(target=lambda: out.append(proc.stdout.readline()), daemon=True)
    t.start()
    t.join(seconds)
    return out[0].decode(errors="replace").strip() if out else ""


def run_check(name: str, work: Path, how: str, child: list[str], child_timeout: float) -> None:
    lockdir = work / name
    lockdir.mkdir(parents=True, exist_ok=True)
    path = str(lockdir / "run.lock")
    if (how.startswith("fl-")) and not HAVE_FL:
        print(f"RESULT q33 {name} {OS} : skipped (filelock not installed)", flush=True)
        return
    holder = subprocess.Popen([sys.executable, SCRIPT, "holder", how, path, "--", *child],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cpid = None
    try:
        line = readline_with_timeout(holder, 60)
        if not line.startswith("CHILD"):
            print(f"RESULT q33 {name} {OS} : error (holder said {line!r})", flush=True)
            return
        cpid = int(line.split()[1])
        time.sleep(1.5)
        before = {m: attempt(path, m) for m in ("filelock", "raw")}
        holder.kill()  # TerminateProcess
        holder.wait(timeout=10)
        time.sleep(1.0)
        if not alive(cpid):
            log = (lockdir / "child.log").read_bytes()[-300:].decode(errors="replace")
            print(f"RESULT q33 {name} {OS} : inconclusive (child ended before the check); log tail {log!r}",
                  flush=True)
            return
        during = {m: attempt(path, m) for m in ("filelock", "raw")}
        deadline = time.time() + child_timeout
        while alive(cpid) and time.time() < deadline:
            time.sleep(0.2)
        ended = not alive(cpid)
        if not ended:
            kill_pid(cpid)
            time.sleep(1.0)
        afterwards = {m: attempt(path, m) for m in ("filelock", "raw")}

        def fmt(d: dict) -> str:
            return " ".join(f"{k}={v}" for k, v in d.items())

        refused = all(v.startswith("refused") for v in during.values())
        granted = all(v == "granted" for v in afterwards.values())
        verdict = "lock held by child after holder kill, freed when child ended" if refused and granted else \
            "lock NOT held by child after holder kill" if all(v == "granted" for v in during.values()) else "mixed"
        tail = (lockdir / "child.log").read_bytes()[-2000:].decode(errors="replace").strip().splitlines()
        last = next((ln for ln in reversed(tail) if "Finished" in ln or "rror" in ln), tail[-1] if tail else "")
        print(f"RESULT q33 {name} {OS} : {verdict} | holder alive: {fmt(before)} | while child lives: "
              f"{fmt(during)} | after child {'ended by itself' if ended else 'was killed (timeout)'}: "
              f"{fmt(afterwards)} | child log: {last[:120]!r}", flush=True)
    finally:
        if holder.poll() is None:
            holder.kill()
        if cpid and alive(cpid):
            kill_pid(cpid)


def java_version(java: str) -> str:
    try:
        r = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=30)
        return (r.stderr or r.stdout).splitlines()[0]
    except Exception as e:
        return f"unavailable ({type(e).__name__})"


def main(args: list[str]) -> None:
    if sys.platform != "win32":
        print(f"RESULT q33 windows-only {OS} : skipped (not Windows)", flush=True)
        return
    sel = args[0] if args else ""
    java = os.environ.get("Q33_JAVA") or shutil.which("java") or "java"
    print(f"INFO q33 {OS} python {platform.python_version()} filelock {FL_VER} java: {java_version(java)}",
          flush=True)
    base = Path(tempfile.mkdtemp(prefix="q33-", dir=os.getcwd()))
    (base / "Sleep.java").write_text(SLEEP_JAVA)
    (base / "Long.tla").write_text(LONG_TLA)
    n = os.environ.get("Q33_TLC_N", "1500")
    (base / "Long.cfg").write_text(f"INIT Init\nNEXT Next\nCONSTANT N = {n}\n")
    py_sleep = [sys.executable, "-c", "import time, sys; time.sleep(float(sys.argv[1]))", "8"]
    j_sleep = [java, str(base / "Sleep.java"), "12"]
    checks = [(f"py-{how}-kill", how, py_sleep, 30)
              for how in ("fl-hook", "fl-descriptor", "msvcrt", "fl-noinherit", "share-deny", "share-deny-own")]
    checks += [("java-sleep-fl-hook-kill", "fl-hook", j_sleep, 60),
               ("java-sleep-share-deny-kill", "share-deny", j_sleep, 60)]
    for label, var in (("tlc174", "TLA2TOOLS_174"), ("tlcrolling", "TLA2TOOLS_ROLLING")):
        jar = os.environ.get(var)
        if not jar:
            print(f"RESULT q33 {label} {OS} : skipped ({var} not set)", flush=True)
            continue
        tlc = [java, "-XX:+UseParallelGC", "-cp", jar, "tlc2.TLC", "-workers", "1", "-deadlock",
               "-metadir", str(base / f"meta-{label}"), "-config", str(base / "Long.cfg"), str(base / "Long.tla")]
        checks.append((f"{label}-fl-hook-kill", "fl-hook", tlc, 600))
        checks.append((f"{label}-share-deny-kill", "share-deny", tlc, 600))
    for name, how, child, tmo in checks:
        if sel and sel not in name:
            continue
        try:
            run_check(name, base, how, child, tmo)
        except Exception as e:
            print(f"RESULT q33 {name} {OS} : error ({type(e).__name__}: {e})", flush=True)
    time.sleep(1.0)
    shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "try":
        role_try(sys.argv[2], sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == "holder":
        i = sys.argv.index("--")
        role_holder(sys.argv[2], sys.argv[3], sys.argv[i + 1:])
    else:
        main(sys.argv[1:])
    sys.exit(0)
