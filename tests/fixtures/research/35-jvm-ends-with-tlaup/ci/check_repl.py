"""Research question 35: do the mechanisms work for `tlaup repl`, whose stdin is the terminal? (POSIX only)

    python q35/check_repl.py

A pseudo-terminal held by this script stands for the user's terminal (so the terminal outlives the parent, as a
real one does). parent.py starts `java tlc2.REPL` (rolling jar, TLA2TOOLS_ROLLING) in passthrough mode on that
terminal with one mechanism; this script types `1+1`, expects `2`, kills the parent with SIGKILL and reports
whether the REPL is still there. Mechanism "none" is the control; "agent-stdin" is expected to collide with the
REPL (both read the terminal).

Prints:  RESULT q35 repl-<mechanism> <os> : <outcome>
"""

from __future__ import annotations

import os
import re
import select
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c  # noqa: E402


def read_for(fd: int, secs: float, until: str | None = None) -> str:
    buf = b""
    end = time.monotonic() + secs
    while time.monotonic() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try:
                d = os.read(fd, 4096)
            except OSError:
                break
            if not d:
                break
            buf += d
            if until and re.search(until, buf.decode("utf-8", "replace")):
                break
    return buf.decode("utf-8", "replace")


def one(mech: str, jar: str, tools: str) -> None:
    import pty

    name = f"repl-{mech}"
    master, slave = pty.openpty()
    home = os.path.join(c.WORK, "home")
    os.makedirs(home, exist_ok=True)
    env = dict(os.environ, HOME=home)
    log = os.path.join(c.WORK, f"repl-{mech}.log")
    if os.path.exists(log):
        os.remove(log)
    base = mech.replace("-thread", "")
    args = [sys.executable, os.path.join(c.HERE, "parent.py"), "--mechanism", base, "--agent-jar", jar,
            "--agent-log", log, "--passthrough", "--lifetime", "60", "--", c.JAVA, "-cp", tools, "tlc2.REPL"]
    p = subprocess.Popen(args, stdin=slave, stdout=slave, stderr=slave, env=env, start_new_session=True)
    os.close(slave)
    cpid = 0
    try:
        text = read_for(master, 30, r"Enter a constant-level[^\n]*\n[^\n]*>")
        m = re.search(r"CHILD (\d+)", text)
        cpid = int(m.group(1)) if m else 0
        if not cpid or "Enter a constant-level" not in text:
            c.result(name, f"ERROR no REPL prompt (saw {text[-200:]!r})")
            return
        os.write(master, b"1+1\n")
        ans = read_for(master, 10, r"\n2\r?\n")
        works = bool(re.search(r"(^|\n)2\r?\n", ans))
        os.kill(p.pid, signal.SIGKILL)
        p.wait(timeout=10)
        gone = c.wait_gone(cpid, 8)
        state = f"REPL ENDED {gone:.2f}s after the parent was killed" if gone is not None else \
            "REPL STILL RUNNING 8s after the parent was killed"
        c.result(name, f"{'1+1 answered 2' if works else '1+1 NOT answered'}; {state}")
    finally:
        if cpid and c.alive(cpid):
            c.hard_kill(cpid)
            c.wait_gone(cpid, 5)
        if p.poll() is None:
            p.kill()
            p.wait()
        os.close(master)


def main() -> None:
    os.makedirs(c.WORK, exist_ok=True)
    print(f"q35 check_repl on {c.host()}; java: {c.java_version()}", flush=True)
    if c.IS_WIN:
        c.result("repl", "skipped (POSIX only; the Windows mechanisms do not touch stdin)")
        return
    tools = os.environ.get("TLA2TOOLS_ROLLING")
    if not tools:
        c.result("repl", "skipped (TLA2TOOLS_ROLLING not set)")
        return
    jar, _ = c.build()
    mechs = ["none", "agent-pipe", "agent-pid", "agent-stdin", "watcher"]
    if c.IS_LINUX:
        mechs[1:1] = ["pdeathsig-preexec"] + (["pdeathsig-setpriv"] if shutil.which("setpriv") else [])
    for m in mechs:
        try:
            one(m, jar, tools)
        except Exception as e:  # noqa: BLE001
            c.result(f"repl-{m}", f"ERROR {type(e).__name__}: {e}")
    shutil.rmtree(os.path.join(c.WORK, "home"), ignore_errors=True)


if __name__ == "__main__":
    main()
