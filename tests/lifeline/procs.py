"""Helpers for the lifeline tests: finding the JDK, watching a process, stopping one that is left."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

WINDOWS = sys.platform == "win32"


def find_tool(name: str) -> str:
    """``name`` from ``JAVA_HOME/bin`` first, then ``PATH``. A missing JDK is an error, not a skip."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        found = shutil.which(name, path=str(Path(java_home) / "bin"))
        if found:
            return found
    found = shutil.which(name)
    if found is None:
        msg = f"{name} not found: the lifeline tests need a real JDK (JAVA_HOME or PATH)"
        raise AssertionError(msg)
    return found


def wait_until(condition: Callable[[], bool], what: str, timeout: float) -> None:
    """Poll ``condition`` until it holds; fail with ``what`` when ``timeout`` seconds pass."""
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            msg = f"timed out after {timeout} s: {what}"
            raise AssertionError(msg)
        time.sleep(0.02)  # a poll interval, not a wait for an amount of time


def running(pid: int) -> bool:
    """Whether the process exists and has not ended (an ended orphan may stay a zombie until it is reaped)."""
    if WINDOWS:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=True)
        return str(pid) in out.stdout
    out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False)
    state = out.stdout.strip()
    return bool(state) and not state.startswith("Z")


def kill_quietly(pid: int) -> None:
    """Stop a process the test left behind; nothing if it has gone."""
    if WINDOWS:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)
        return
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, 9)
