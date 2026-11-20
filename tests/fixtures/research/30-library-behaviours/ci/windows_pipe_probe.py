"""Question 30, second CI run: what a write to a pipe whose reader has gone raises, with its errno and winerror.

Meant for Windows (where Rich's on_broken_pipe is never called, because the error is OSError EINVAL, not
BrokenPipeError); runs anywhere for comparison. Needs rich (uv run --no-project --with rich python ...); the plain
print cases need nothing. Run from the `ci` folder: python q30/windows_pipe_probe.py
Exits 0 whatever the outcome.
"""

from __future__ import annotations

import os
import subprocess
import sys

OS = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)

CHILD = r'''
import os, sys
mode, how = sys.argv[1], sys.argv[2]
def report(e):
    sys.__stderr__.write(f"NOTE {type(e).__name__} errno={getattr(e, 'errno', None)} winerror={getattr(e, 'winerror', None)} "
                         f"is-BrokenPipeError={isinstance(e, BrokenPipeError)}\n")
    sys.__stderr__.flush()
try:
    if how == "rich":
        from rich.console import Console
        class C(Console):
            def on_broken_pipe(self):
                sys.__stderr__.write("NOTE on_broken_pipe called\n")
                raise BrokenPipeError
        c = C()
        for i in range(int(mode)):
            c.print(f"line {i}")
    else:
        for i in range(int(mode)):
            print(f"line {i}", flush=True)
except BaseException as e:
    report(e)
    try:
        devnull = os.open(os.devnull, os.O_WRONLY); os.dup2(devnull, 1)
    except OSError:
        pass
    os._exit(7)
os._exit(0)
'''


def closed_before_start(how: str, n: int) -> str:
    r, w = os.pipe()
    os.close(r)
    p = subprocess.Popen([sys.executable, "-c", CHILD, str(n), how], stdout=w, stderr=subprocess.PIPE, text=True)
    os.close(w)
    try:
        err = p.communicate(timeout=60)[1]
    except subprocess.TimeoutExpired:
        p.kill()
        err = p.communicate()[1]
    notes = [line for line in err.splitlines() if line.startswith("NOTE")]
    return f"exit {p.returncode}; {' | '.join(notes) or err.strip()[-200:]}"


def reader_exits(how: str, n: int) -> str:
    reader = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.readline()"], stdin=subprocess.PIPE)
    p = subprocess.Popen([sys.executable, "-c", CHILD, str(n), how], stdout=reader.stdin, stderr=subprocess.PIPE,
                         text=True)
    reader.stdin.close()
    try:
        err = p.communicate(timeout=60)[1]
        reader.wait(10)
    except subprocess.TimeoutExpired:
        p.kill()
        reader.kill()
        err = p.communicate()[1]
    notes = [line for line in err.splitlines() if line.startswith("NOTE")]
    return f"exit {p.returncode}; {' | '.join(notes) or err.strip()[-200:]}"


def main() -> None:
    try:
        from importlib.metadata import version

        rich_v = version("rich")
    except Exception:  # noqa: BLE001
        rich_v = None
    hows = ["print"] + (["rich"] if rich_v else [])
    for how in hows:
        tag = f"rich {rich_v}" if how == "rich" else "print"
        print(f"RESULT q30 pipe-error-closed-{how} {OS} : INFO ({tag}, Python {sys.version.split()[0]}) - "
              f"3 lines, reader closed before start: {closed_before_start(how, 3)}", flush=True)
        print(f"RESULT q30 pipe-error-reader-exits-{how} {OS} : INFO ({tag}, Python {sys.version.split()[0]}) - "
              f"200000 lines, reader reads one line and exits: {reader_exits(how, 200000)}", flush=True)


if __name__ == "__main__":
    main()
    sys.exit(0)
