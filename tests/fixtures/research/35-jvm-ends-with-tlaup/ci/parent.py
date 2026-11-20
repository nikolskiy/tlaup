"""Stand-in for tlaup's Java launcher (research question 35).

Starts one java child the way the launcher would (stdout and stderr piped and drained by daemon threads,
stdin from the null device unless the mechanism needs it, same process group), applies one mechanism that is
meant to make the child end when this process ends, prints "CHILD <pid>" and "READY", and then waits to be
killed. If nobody kills it within --lifetime seconds it stops the child and exits, so nothing is left behind.

    python parent.py --mechanism NAME --agent-jar JAR [--lifetime S] [--from-thread] [--passthrough] -- java ARGS...

The java executable must be the first word after "--"; agent options are put right after it, before the
options that stand for the user's own.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import signal
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


def drain(stream) -> None:
    try:
        while stream.read(65536):
            pass
    except (OSError, ValueError):
        pass


def pdeathsig_preexec(parent_pid: int, sig: int):
    libc = ctypes.CDLL(None, use_errno=True)
    PR_SET_PDEATHSIG = 1

    def fn() -> None:
        if libc.prctl(PR_SET_PDEATHSIG, sig, 0, 0, 0) != 0:
            os._exit(121)
        # The parent may have died between fork and prctl; then the signal will never come.
        if os.getppid() != parent_pid:
            os._exit(122)

    return fn


def make_kill_on_close_job():
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

    class BASIC(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IOC(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("R", "W", "O", "RB", "WB", "OB")]

    class EXT(ctypes.Structure):
        _fields_ = [
            ("Basic", BASIC),
            ("Io", IOC),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job = k32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW")
    info = EXT()
    info.Basic.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):  # ExtendedLimitInformation
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject")

    def assign(proc: subprocess.Popen) -> None:
        if not k32.AssignProcessToJobObject(job, int(proc._handle)):
            raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject")

    return job, assign


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mechanism", required=True)
    ap.add_argument("--agent-jar")
    ap.add_argument("--agent-log", default="")
    ap.add_argument("--lifetime", type=float, default=90.0)
    ap.add_argument("--from-thread", action="store_true", help="start the child from a thread that then ends")
    ap.add_argument("--passthrough", action="store_true", help="child inherits stdin/stdout/stderr (repl)")
    ap.add_argument("--pdeathsig", default="TERM")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    java, rest = cmd[0], cmd[1:]
    me = os.getpid()
    m = a.mechanism
    log = f",log={a.agent_log}" if a.agent_log else ""

    kw: dict = {}
    if a.passthrough:
        kw.update(stdin=None, stdout=None, stderr=None)
    else:
        kw.update(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    prefix: list[str] = []
    agent: list[str] = []
    keep: list = []  # things that must stay open for the life of this process
    after = None

    if m == "none":
        pass
    elif m == "pdeathsig-preexec":
        kw["preexec_fn"] = pdeathsig_preexec(me, getattr(signal, "SIG" + a.pdeathsig))
    elif m == "pdeathsig-setpriv":
        prefix = ["setpriv", "--pdeathsig", a.pdeathsig, "--"]
    elif m == "agent-pipe":
        r, w = os.pipe()  # both non-inheritable; pass_fds makes r inheritable in the child only
        kw["pass_fds"] = (r,)
        agent = [f"-javaagent:{a.agent_jar}=pipe=/dev/fd/{r}{log}"]
        keep.append(w)

        def after(proc, r=r):  # noqa: E306
            os.close(r)
    elif m == "agent-stdin":
        kw["stdin"] = subprocess.PIPE
        agent = [f"-javaagent:{a.agent_jar}=stdin{log}"]
    elif m == "agent-pid":
        agent = [f"-javaagent:{a.agent_jar}=pid={me},interval=500{log}"]
    elif m == "agent-onexit":
        agent = [f"-javaagent:{a.agent_jar}=onexit={me}{log}"]
    elif m == "watcher":
        pass
    elif m == "job":
        job, assign = make_kill_on_close_job()
        keep.append(job)
        after = assign
    else:
        print(f"ERROR unknown mechanism {m}", flush=True)
        sys.exit(2)

    argv = prefix + [java] + agent + rest
    box: dict = {}

    def spawn() -> None:
        t0 = time.perf_counter()
        box["proc"] = subprocess.Popen(argv, **kw)
        box["spawn_s"] = time.perf_counter() - t0

    if a.from_thread:
        def spawn_and_linger() -> None:
            spawn()
            time.sleep(0.5)  # so the child has set up whatever it sets up before this thread ends

        t = threading.Thread(target=spawn_and_linger)
        t.start()
        t.join()  # the thread that forked the child has now ended; this process lives on
    else:
        spawn()
    proc: subprocess.Popen = box["proc"]
    if after:
        after(proc)
    if not a.passthrough:
        for s in (proc.stdout, proc.stderr):
            if s is not None:
                threading.Thread(target=drain, args=(s,), daemon=True).start()
    if m == "agent-stdin":
        keep.append(proc.stdin)

    watcher = None
    if m == "watcher":
        watcher = subprocess.Popen(
            [sys.executable, "-I", os.path.join(HERE, "watcher.py"), str(me), str(proc.pid)],
            stdin=subprocess.DEVNULL,
        )
    print(f"CHILD {proc.pid}", flush=True)
    print(f"SPAWN {box['spawn_s']:.4f}", flush=True)
    if watcher:
        print(f"WATCHER {watcher.pid}", flush=True)
    print("READY", flush=True)

    deadline = time.monotonic() + a.lifetime
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            print(f"CHILD-EXITED {proc.returncode}", flush=True)
            break
        time.sleep(0.1)
    else:
        proc.kill()
        proc.wait()
        print("LIFETIME-OVER child killed", flush=True)
    if watcher:
        try:
            watcher.wait(timeout=5)
        except subprocess.TimeoutExpired:
            watcher.kill()


if __name__ == "__main__":
    main()
