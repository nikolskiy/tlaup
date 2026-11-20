"""Question 30: Rich's Live display on the alternate screen through a real pty, read back with pyte (22 O4).

POSIX only (pty). Needs rich and pyte installed, for example
    uv run --no-project --with rich==13.9.4 --with pyte python q30/rich_live_pty_probe.py
Exits 0 whatever the outcome.
"""

from __future__ import annotations

import os
import re
import sys
import time

OS = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)

CHILD = r'''
import sys, time
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

err = Console(stderr=True)
state = {"phase": "Checking", "t0": time.monotonic()}

def render():
    el = int((time.monotonic() - state["t0"]) * 10)
    lay = Layout()
    lay.split_column(Layout(name="h", size=2), Layout(name="s", size=4), Layout(name="p", size=6), Layout(name="o"))
    lay["h"].update(Text("TLC rolling@bc1b506, Java 25\nSpec.tla  cfg: Spec.cfg"))
    status = Text()
    status.append(state["phase"], style="bold green")
    status.append(f"   tick {el:04d}   ")
    status.append("errors 1", style="red")
    lay["s"].update(Group(Rule("Status"), status, Text("Ctrl-C to interrupt", style="dim")))
    t = Table(show_edge=False, box=None)
    for c in ("Time", "Diameter", "Generated"):
        t.add_column(c, justify="right")
    t.add_row("22:26:59", "96", "912,004")
    lay["p"].update(Group(Rule("State space progress"), t))
    lay["o"].update(Group(Rule("Output"), Text("a line of output " + "x" * 120, overflow="ellipsis", no_wrap=True)))
    return lay

live = Live(console=err, screen=True, get_renderable=render, refresh_per_second=10,
            redirect_stdout=False, redirect_stderr=False, auto_refresh=True)
live.start()
time.sleep(1.5)                      # no updates from outside: only the refresh thread draws
state["phase"] = "Finished"
live.refresh()
live.stop()
print("after the layout: plain result line")
sys.stdout.flush()
'''


def main() -> None:
    try:
        import pty  # noqa: F401
    except ImportError:
        print(f"RESULT q30 rich-live-pty {OS} : SKIP - no pty module")
        return
    import fcntl
    import struct
    import subprocess
    import termios
    from importlib.metadata import version

    import pyte

    rich_v, pyte_v = version("rich"), version("pyte")
    tag = f"(rich {rich_v}, pyte {pyte_v}, Python {sys.version.split()[0]})"
    master, slave = os.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
    env = {k: v for k, v in os.environ.items() if k not in ("COLUMNS", "LINES", "NO_COLOR", "FORCE_COLOR")}
    env["TERM"] = "xterm-256color"
    p = subprocess.Popen([sys.executable, "-c", CHILD], stdin=slave, stdout=slave, stderr=slave, env=env,
                         start_new_session=True)
    os.close(slave)
    data = bytearray()
    chunks: list[bytes] = []
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            b = os.read(master, 65536)
        except OSError:  # EIO on Linux when the child has closed the pty
            break
        if not b:
            break
        data += b
        chunks.append(b)
    os.close(master)
    try:
        p.wait(5)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
    raw = bytes(data)
    enter, leave = b"\x1b[?1049h", b"\x1b[?1049l"
    i, j = raw.find(enter), raw.rfind(leave)
    if i < 0 or j < 0:
        print(f"RESULT q30 rich-live-pty {OS} : FAIL {tag} - alternate screen sequences enter={i >= 0} leave={j >= 0}; "
              f"exit {p.returncode}; first bytes {raw[:200]!r}")
        return
    middle = raw[i + len(enter):j]
    # Feed the middle in pieces, keeping every distinct screen.
    screen = pyte.Screen(100, 30)
    stream = pyte.ByteStream(screen)
    screens: list[list[str]] = []
    titles_seen = False
    ticks: set[str] = set()
    coloured = set()
    step = 512
    for k in range(0, len(middle), step):
        stream.feed(middle[k:k + step])
        disp = list(screen.display)
        text = "\n".join(disp)
        if all(t in text for t in ("TLC rolling", "Status", "State space progress", "Output")):
            titles_seen = True
        ticks.update(re.findall(r"tick (\d{4})", text))
        for line in screen.buffer.values():
            for ch in line.values():
                if ch.fg not in ("default",):
                    coloured.add(ch.fg)
        if not screens or screens[-1] != disp:
            screens.append(disp)
    last = "\n".join(screen.display)
    after = pyte.Screen(100, 30)
    pyte.ByteStream(after).feed(raw[j + len(leave):])
    after_text = "\n".join(after.display)
    ellipsis = "…" in last
    ok = titles_seen and len(ticks) >= 5 and "Finished" in last and "after the layout" in after_text
    print(
        f"RESULT q30 rich-live-pty {OS} : {'PASS' if ok else 'FAIL'} {tag} - enter/leave written; "
        f"four titles on one screen: {titles_seen}; distinct ticks drawn by the refresh thread: {len(ticks)}; "
        f"last frame has Finished: {'Finished' in last}; "
        f"colours seen by pyte: {sorted(coloured)}; ellipsis kept: {ellipsis}; "
        f"text after leave: {'after the layout' in after_text}; bytes {len(raw)}; exit {p.returncode}"
    )


if __name__ == "__main__":
    main()
    sys.exit(0)
