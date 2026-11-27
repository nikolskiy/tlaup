"""What the four fakes share: reading the script, writing the log, the start line.

Standard library only; no import of tlaup or pytest. A fake runs in its own
interpreter, started by a launcher that ``tests/fakes/control.py`` writes.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

FAKES_DIR = Path(__file__).resolve().parent
GOLDEN_DIR = FAKES_DIR.parent / "parse" / "golden"
CLASSES_DIR = FAKES_DIR / "classes"
JAVAC_ERRORS_DIR = FAKES_DIR / "javac-errors"

NO_SCRIPT = 127
# A hang, or a wait for a checkpoint's release, ends by itself after this long, as a guard
# against a leaked process. No test may rely on it.
GUARD_SECONDS = 120.0
GUARD_EXIT = 124


class ScriptError(Exception):
    """The script asks for something the fake cannot do; the fake exits 127 with the message."""


class FakeExit(Exception):  # noqa: N818 - a way out, not an error
    """Ends the fake with ``code``; raised from signal handlers and deep in the replay."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def script_variable(tool: str) -> str:
    return f"TLAUP_FAKE_{tool.upper()}"


def load_script(tool: str, baked: str | None) -> dict[str, Any] | None:
    """The script baked into the launcher, else the one named by TLAUP_FAKE_<TOOL>; None when neither."""
    name = baked or os.environ.get(script_variable(tool))
    if not name:
        return None
    try:
        data = json.loads(Path(name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        message = f"cannot read script {name}: {exc}"
        raise ScriptError(message) from exc
    if not isinstance(data, dict):
        message = f"script {name} is not a JSON object"
        raise ScriptError(message)
    return data


class Log:
    """One JSON line per event, written and flushed at once. No path: nothing is written."""

    def __init__(self, path: str | None) -> None:
        self.path = Path(path) if path else None

    def write(self, event: str, **fields: Any) -> None:
        if self.path is None:
            return
        line = json.dumps({"event": event, "pid": os.getpid(), **fields}) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()

    def read(self) -> list[dict[str, Any]]:
        if self.path is None or not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]


def stdout_is_pipe() -> bool:
    try:
        return stat.S_ISFIFO(os.fstat(1).st_mode)
    except OSError:
        return False


def start_fields(**extra: Any) -> dict[str, Any]:
    """The fields of a ``start`` line that every fake writes."""
    pgid = os.getpgrp() if hasattr(os, "getpgrp") else None
    return {
        "pgid": pgid,
        "path": str(Path(sys.argv[0]).absolute()),
        "args": sys.argv[1:],
        "cwd": str(Path.cwd()),
        "stdout_pipe": stdout_is_pipe(),
        **extra,
    }


def say(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.stderr.flush()


def text_or_file(value: Any, base: Path) -> bytes | None:
    """``null``; ``{"text": "..."}``; or a file, absolute or relative to ``base``."""
    if value is None:
        return None
    if isinstance(value, Mapping):
        if "text" not in value:
            message = f"expected {{'text': ...}}, got {value!r}"
            raise ScriptError(message)
        return str(value["text"]).encode("utf-8")
    path = Path(str(value))
    if not path.is_absolute():
        path = base / path
    try:
        return path.read_bytes()
    except OSError as exc:
        message = f"cannot read {path}: {exc}"
        raise ScriptError(message) from exc


def sleep_ms(ms: Any) -> None:
    if ms:
        time.sleep(float(ms) / 1000)


def run_tool(tool: str, baked: str | None, body: Any) -> int:
    """Load the script and run ``body(script, log)``; the common ways out of every fake.

    No script: ``fake <tool>: no script`` and 127. A script error: its message and 127.
    The ``exit`` line is written on every way out the fake controls.
    """
    try:
        script = load_script(tool, baked)
    except ScriptError as exc:
        say(f"fake {tool}: {exc}")
        return NO_SCRIPT
    if script is None:
        say(f"fake {tool}: no script")
        return NO_SCRIPT
    log = Log(script.get("log"))
    try:
        code = int(body(script, log))
    except FakeExit as done:
        code = done.code
    except ScriptError as exc:
        say(f"fake {tool}: {exc}")
        code = NO_SCRIPT
    log.write("exit", code=code)
    return code
