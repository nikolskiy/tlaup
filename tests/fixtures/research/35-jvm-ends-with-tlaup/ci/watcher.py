"""Watcher process for research question 35: wait until PARENT ends, then stop CHILD.

    python -I watcher.py PARENT_PID CHILD_PID

Linux: pidfd_open on both and poll; the child is signalled through its pidfd, so a reused pid is never hit.
macOS and the BSDs: kqueue EVFILT_PROC NOTE_EXIT on both.
Windows: WaitForMultipleObjects on both process handles, then TerminateProcess.
Ends by itself when CHILD ends first. Ignores SIGINT and SIGHUP: in a terminal they reach the whole process
group, and the JVM handles them itself.
"""

from __future__ import annotations

import os
import signal
import sys
import time

GRACE = 10.0


def _pidfd_funcs():
    """os.pidfd_open and signal.pidfd_send_signal, or the same system calls through ctypes when this Python was
    built without them (python-build-standalone, which uv installs, lacks both)."""
    if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
        return os.pidfd_open, signal.pidfd_send_signal, "os.pidfd_open"
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    NR_OPEN, NR_SEND = 434, 424  # same numbers on x86-64 and arm64

    def pidfd_open(pid: int) -> int:
        fd = libc.syscall(NR_OPEN, ctypes.c_int(pid), ctypes.c_uint(0))
        if fd < 0:
            e = ctypes.get_errno()
            raise ProcessLookupError(e, os.strerror(e)) if e == 3 else OSError(e, os.strerror(e))
        return fd

    def send(fd: int, sig: int) -> None:
        if libc.syscall(NR_SEND, ctypes.c_int(fd), ctypes.c_int(sig), None, ctypes.c_uint(0)) < 0:
            e = ctypes.get_errno()
            raise OSError(e, os.strerror(e))

    return pidfd_open, send, "ctypes syscall"


def linux(ppid: int, cpid: int) -> str:
    import select

    pidfd_open, pidfd_send_signal, via = _pidfd_funcs()

    try:
        cfd = pidfd_open(cpid)
    except ProcessLookupError:
        return "child-gone-at-start"
    try:
        pfd = pidfd_open(ppid)
    except ProcessLookupError:
        pfd = None
    if pfd is not None:
        p = select.poll()
        p.register(pfd, select.POLLIN)
        p.register(cfd, select.POLLIN)
        ready = {fd for fd, _ in p.poll()}
        if cfd in ready:
            return "child-ended-first"
    pidfd_send_signal(cfd, signal.SIGTERM)
    p = select.poll()
    p.register(cfd, select.POLLIN)
    if not p.poll(GRACE * 1000):
        pidfd_send_signal(cfd, signal.SIGKILL)
        return f"parent-gone sent TERM then KILL (pidfd via {via})"
    return f"parent-gone sent TERM (pidfd via {via})"


def kqueue(ppid: int, cpid: int) -> str:
    import select

    kq = select.kqueue()
    evs = []
    for pid in (ppid, cpid):
        evs.append(select.kevent(pid, filter=select.KQ_FILTER_PROC, flags=select.KQ_EV_ADD | select.KQ_EV_ONESHOT,
                                 fflags=select.KQ_NOTE_EXIT))
    gone_parent = False
    try:
        kq.control([evs[1]], 0, 0)
    except ProcessLookupError:
        return "child-gone-at-start"
    try:
        kq.control([evs[0]], 0, 0)
    except ProcessLookupError:
        gone_parent = True
    if not gone_parent:
        got = kq.control(None, 1, None)
        if got and got[0].ident == cpid:
            return "child-ended-first"
    os.kill(cpid, signal.SIGTERM)
    end = time.monotonic() + GRACE
    while time.monotonic() < end:
        got = kq.control(None, 1, 0.2)
        if got and got[0].ident == cpid:
            return "parent-gone sent TERM"
    os.kill(cpid, signal.SIGKILL)
    return "parent-gone sent TERM then KILL"


def windows(ppid: int, cpid: int) -> str:
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.WaitForMultipleObjects.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL,
                                           wintypes.DWORD]
    k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    SYNCHRONIZE, PROCESS_TERMINATE = 0x00100000, 0x0001
    ch = k32.OpenProcess(SYNCHRONIZE | PROCESS_TERMINATE, False, cpid)
    if not ch:
        return "child-gone-at-start"
    ph = k32.OpenProcess(SYNCHRONIZE, False, ppid)
    if ph:
        arr = (wintypes.HANDLE * 2)(ph, ch)
        r = k32.WaitForMultipleObjects(2, arr, False, 0xFFFFFFFF)
        if r == 1:
            return "child-ended-first"
    k32.TerminateProcess(ch, 143)
    return "parent-gone TerminateProcess"


def main() -> None:
    for name in ("SIGINT", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), signal.SIG_IGN)
    ppid, cpid = int(sys.argv[1]), int(sys.argv[2])
    if sys.platform.startswith("linux"):
        how = linux(ppid, cpid)
    elif sys.platform == "win32":
        how = windows(ppid, cpid)
    else:
        how = kqueue(ppid, cpid)
    log = os.environ.get("Q35_WATCHER_LOG")
    if log:
        with open(log, "a") as f:
            f.write(f"watcher {how}\n")


if __name__ == "__main__":
    main()
