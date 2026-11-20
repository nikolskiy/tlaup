"""Question 30: what select.poll reports on the write end of a pipe whose reader has gone (14 F10, reader_gone).

Standard library only. Run from the `ci` folder: python q30/select_poll_probe.py
Exits 0 whatever the outcome.
"""

from __future__ import annotations

import os
import select
import subprocess
import sys

OS = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)


def names(ev: int) -> str:
    out = [n for n in ("POLLIN", "POLLOUT", "POLLERR", "POLLHUP", "POLLNVAL", "POLLPRI") if ev & getattr(select, n, 0)]
    return "|".join(out) or "none"


def poll_fd(fd: int) -> int:
    p = select.poll()
    p.register(fd, select.POLLOUT)  # what is asked for does not limit POLLERR/POLLHUP/POLLNVAL
    ev = p.poll(0)
    return ev[0][1] if ev else 0


def poll_fd_noevents(fd: int) -> int:
    p = select.poll()
    p.register(fd, 0)  # ask for nothing: only POLLERR/POLLHUP/POLLNVAL can come back
    ev = p.poll(0)
    return ev[0][1] if ev else 0


def main() -> None:
    if not hasattr(select, "poll"):
        print(f"RESULT q30 select-poll {OS} : SKIP - select.poll does not exist on this platform (reader_gone is false)")
        return
    # 1. Reader alive.
    r, w = os.pipe()
    alive, alive0 = poll_fd(w), poll_fd_noevents(w)
    # 2. Reader closed.
    os.close(r)
    gone, gone0 = poll_fd(w), poll_fd_noevents(w)
    os.close(w)
    # 3. Reader was a process that exited (as with `| head -1`).
    rr, ww = os.pipe()
    child = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.readline()"], stdin=rr)
    os.close(rr)
    os.write(ww, b"one line\n")
    child.wait(10)
    proc_gone, proc_gone0 = poll_fd(ww), poll_fd_noevents(ww)
    os.close(ww)
    # 4. A full pipe whose reader is alive (not reading): must not look like "gone".
    r2, w2 = os.pipe()
    os.set_blocking(w2, False)
    try:
        while True:
            os.write(w2, b"x" * 65536)
    except BlockingIOError:
        pass
    full, full0 = poll_fd(w2), poll_fd_noevents(w2)
    os.close(r2)
    os.close(w2)
    # 5. A regular file and the null device: not pipes.
    nul = os.open(os.devnull, os.O_WRONLY)
    devnull = poll_fd(nul)
    os.close(nul)
    # 6. A closed descriptor.
    r3, w3 = os.pipe()
    os.close(r3)
    os.close(w3)
    closed = poll_fd(w3)

    def gone_rule(ev: int) -> bool:
        return bool(ev & (select.POLLERR | select.POLLHUP))

    detail = (
        f"reader alive: {names(alive)} / no-events: {names(alive0)}; reader closed: {names(gone)} / {names(gone0)}; "
        f"reader process exited: {names(proc_gone)} / {names(proc_gone0)}; full pipe, reader alive: {names(full)} / "
        f"{names(full0)}; null device: {names(devnull)}; closed fd: {names(closed)}"
    )
    ok = gone_rule(gone) and gone_rule(proc_gone) and not gone_rule(alive) and not gone_rule(full)
    print(f"RESULT q30 select-poll {OS} : {'PASS' if ok else 'FAIL'} - ERR|HUP marks a gone reader and only then. {detail}")


if __name__ == "__main__":
    main()
    sys.exit(0)
