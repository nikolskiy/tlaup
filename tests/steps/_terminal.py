"""The terminal runner of the feature steps: a pty read through ``pyte`` (design 01 T5, 22 O4).

The child is the leader of a new session with the pty as its controlling terminal, so the interrupt
character typed into the pty is the terminal's own SIGINT to the foreground group. ``pyte`` does not model
the alternate screen, so what stays on the user's terminal is the screen of the bytes outside each part from
``ENTER_ALT`` to ``LEAVE_ALT``.
"""

from __future__ import annotations

import errno
import os
import re
import select
import signal
import struct
import subprocess
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pyte
import pytest

from tests.steps._process import (
    POSIX,
    WAIT_SECONDS,
    WAITING_LINE,
    exit_code_of,
    find_log,
    is_tool_start,
    kill_group,
    prepare,
    reap_fakes,
    release_when_waiting,
    wait_for_log,
)
from tests.steps._scenario import POLL_SECONDS, Outcome, fail

try:  # POSIX only; none on Windows, where the terminal steps skip (D15)
    import fcntl
    import termios
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from tests.steps._scenario import Scenario

ENTER_ALT = b"\x1b[?1049h"
LEAVE_ALT = b"\x1b[?1049l"
INTERRUPT = "\x03"  # Ctrl-C, which the terminal turns into SIGINT for its foreground group
QUIT = "\x1c"  # Ctrl-\, which the terminal turns into SIGQUIT for its foreground group (package 39)
TERMINAL_TYPE = "xterm-256color"
FEED_SECONDS = 10.0
HISTORY_LINES = 100_000
HOME = b"\x1b[H"  # the cursor to the top left: where each frame of the layout starts (package 40)
# The layout's panel titles (22 O4); the header has none, it is the lines above the Status panel.
PANEL_TITLES = ("── Status ", "── State space progress ", "── Output ")
ELAPSED = re.compile(r"elapsed (\d+):(\d\d):(\d\d)")
# Escape sequences, for "the whole output with escape sequences removed": CSI, OSC, and the two-byte forms.
# DCS strings first, since ESC P is also a two-byte form; the two-byte forms include ESC 7, ESC 8, ESC = and ESC >.
_ESCAPES = re.compile(
    rb"\x1bP.*?\x1b\\|\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][0-9A-Za-z]|\x1b[0-Z\\-~]",
    re.DOTALL,
)


def _new_screen(size: tuple[int, int]) -> tuple[pyte.HistoryScreen, pyte.ByteStream]:
    columns, lines = size
    screen = pyte.HistoryScreen(columns, lines, history=HISTORY_LINES)
    return screen, pyte.ByteStream(screen)


def _lines(screen: pyte.HistoryScreen) -> list[str]:
    """The lines that scrolled off, then the screen, each with trailing spaces removed."""
    scrolled = ["".join(line[x].data for x in range(screen.columns)).rstrip() for line in screen.history.top]
    return [*scrolled, *(line.rstrip() for line in screen.display)]


def _join(lines: list[str]) -> str:
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n" if lines else ""


def screen_text(data: bytes, size: tuple[int, int]) -> str:
    """``data`` replayed through ``pyte``: the lines that scrolled off count, trailing empty lines dropped."""
    screen, stream = _new_screen(size)
    stream.feed(data)
    return _join(_lines(screen))


def main_screen(data: bytes) -> bytes:
    """The bytes written to the main screen: ``data`` without each part from ``ENTER_ALT`` to its ``LEAVE_ALT``.

    ``?1049h`` saves the cursor and ``?1049l`` restores it with the main screen, so the bytes before the enter
    sequence and after the leave sequence follow on from each other (package 40: the header written before the
    layout opens is still on the terminal after it closes). An enter sequence never left keeps what follows it.
    """
    kept = bytearray()
    rest = data
    while True:
        before, entered, after = rest.partition(ENTER_ALT)
        _, left, tail = after.partition(LEAVE_ALT)
        if not (entered and left):
            kept += rest
            return bytes(kept)
        kept += before
        rest = tail


def final_screen(data: bytes, size: tuple[int, int]) -> str:
    """What stays on the user's terminal: the screen of the bytes written to the main screen (`main_screen`)."""
    return screen_text(main_screen(data), size)


def without_escapes(data: bytes) -> str:
    """Every byte written, escape sequences removed: text that was drawn and then overwritten stays."""
    return _ESCAPES.sub(b"", data).decode("utf-8", errors="replace")


def _shows(screen: pyte.HistoryScreen, text: str) -> bool:
    # A full-width line ran on into the next (it wrapped); any other line ends with a newline, so a text
    # is never found across two separate lines.
    joined = "".join(line if len(line) == screen.columns else line + "\n" for line in _lines(screen))
    return text in joined


def _during_layout(data: bytes) -> bytes | None:
    """The bytes between the first ``ENTER_ALT`` and the ``LEAVE_ALT`` after it; None unless both were written."""
    _, entered, rest = data.partition(ENTER_ALT)
    during, left, _ = rest.partition(LEAVE_ALT)
    return during if entered and left else None


def layout_screens(data: bytes, size: tuple[int, int]) -> list[str]:
    """Each screen the layout showed: the alternate screen's bytes replayed through ``pyte`` (which does not model
    the alternate screen, so they get a screen of their own), the text taken just before each frame starts again
    at the top left and once at the end."""
    during = _during_layout(data)
    if during is None:
        return []
    screen = pyte.Screen(*size)
    stream = pyte.ByteStream(screen)
    shown: list[str] = []
    pieces = during.split(HOME)
    for number, piece in enumerate(pieces):
        stream.feed(piece if number == 0 else HOME + piece)
        shown.append(_join([line.rstrip() for line in screen.display]))
    return shown


def elapsed_seconds(text: str) -> int | None:
    """The Status panel's ``elapsed HH:MM:SS`` on a screen, in seconds; None when it shows none."""
    found = ELAPSED.search(text)
    if found is None:
        return None
    hours, minutes, seconds = (int(part) for part in found.groups())
    return hours * 3600 + minutes * 60 + seconds


@dataclass
class TerminalRun:
    """One process on a pty, and everything read from it so far."""

    process: subprocess.Popen[bytes]
    master: int  # the pty's master end
    size: tuple[int, int]  # columns, lines
    redirect: dict[str, Path] = field(default_factory=dict)
    output: bytearray = field(default_factory=bytearray)
    fakes: Any = None  # whose java starts since line ``after`` a kill also ends (set by watch)
    after: int = 0
    ended: bool = False  # end of output was read
    screen: Any = None
    stream: Any = None

    def __post_init__(self) -> None:
        self.screen, self.stream = _new_screen(self.size)

    def read(self, wait: float = POLL_SECONDS, *, each_frame: Callable[[], None] | None = None) -> None:
        """Read what is there within ``wait``; end of output is EIO on Linux, an empty read on macOS.

        With ``each_frame`` the bytes are fed in parts that start at ``HOME``, where the layout starts each frame,
        and it is called after each part, so no screen of several read at once is missed (package 40).
        """
        if self.ended:
            return
        ready, _, _ = select.select([self.master], [], [], wait)
        if not ready:
            return
        try:
            data = os.read(self.master, 65536)
        except OSError as error:
            if error.errno != errno.EIO:
                raise
            data = b""
        if not data:
            self.ended = True
            return
        self.output += data
        if each_frame is None:
            self.stream.feed(data)
            return
        for number, piece in enumerate(data.split(HOME)):
            self.stream.feed(piece if number == 0 else HOME + piece)
            each_frame()

    def last_screen(self) -> str:
        return _join(_lines(self.screen))

    def watch(self, fakes: Any, after: int) -> TerminalRun:
        """A kill also ends every fake java started since line ``after`` of its log."""
        self.fakes, self.after = fakes, after
        return self

    def kill(self) -> None:
        """The session's group (tlaup and a fake in its group), then every fake java of this run."""
        kill_group(self.process.pid)
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        reap_fakes(self.fakes, self.after)

    def fail_with_screen(self, message: str) -> None:
        self.kill()
        self.close()
        fail(f"{message}; it was killed. The last screen:\n{self.last_screen()}")

    def close(self) -> None:
        if self.master >= 0:
            os.close(self.master)
            self.master = -1

    def pump_until(
        self,
        condition: Callable[[], bool],
        *,
        timeout: float,
        what: str,
        each_frame: Callable[[], None] | None = None,
    ) -> None:
        """Read the pty until ``condition()``; fails with the last screen after ``timeout`` or at end of output."""
        deadline = time.monotonic() + timeout
        while not condition():
            if self.ended:
                self.fail_with_screen(f"the output ended before {what}")
            if time.monotonic() >= deadline:
                self.fail_with_screen(f"{what} did not happen within {timeout} seconds")
            self.read(each_frame=each_frame)

    def feed_until(self, text: str, *, timeout: float = FEED_SECONDS) -> pyte.Screen:
        """Read and feed the emulator until the screen shows ``text``; fails with the last screen it saw."""
        self.pump_until(lambda: _shows(self.screen, text), timeout=timeout, what=f"the terminal showing {text!r}")
        return self.screen

    def type(self, text: str) -> None:
        os.write(self.master, text.encode("utf-8"))

    def finish(self, *, timeout: float = WAIT_SECONDS) -> Outcome:
        """Read to end of output, then wait; a process still running after ``timeout`` is killed."""
        deadline = time.monotonic() + timeout
        while not self.ended:
            if time.monotonic() >= deadline:
                self.fail_with_screen(f"the output did not end within {timeout} seconds")
            self.read(0.1)
        try:
            self.process.wait(timeout=max(deadline - time.monotonic(), 0.1))
        except subprocess.TimeoutExpired:
            self.fail_with_screen(f"the process was still running after {timeout} seconds")
        self.close()
        data = bytes(self.output)
        on_pty = screen_text(data, self.size)

        def stream(name: str) -> str:
            path = self.redirect.get(name)
            return path.read_bytes().decode("utf-8", errors="replace") if path is not None else on_pty

        return Outcome(
            exit_code=exit_code_of(self.process.returncode),
            stdout=stream("stdout"),
            stderr=stream("stderr"),
            terminal=data,
            terminal_size=self.size,
            pid=self.process.pid,
            pgid=self.process.pid,  # the session leader leads its own group
        )


def run_on_terminal(
    argv: Sequence[str], *, size: tuple[int, int], redirect: Mapping[str, Path] | None = None
) -> TerminalRun:
    """Start ``argv`` on a new pty of ``size`` (columns, lines), as the leader of a new session.

    stdin and both streams are on the pty unless redirected to a file; ``TERM=xterm-256color`` and no
    ``COLUMNS`` or ``LINES``, which Rich would take over the terminal's own size (T2).
    """
    if not POSIX or fcntl is None or termios is None:
        pytest.skip("no pty on this platform; no Windows CI (D15)")
    columns, lines = size
    master, slave = os.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", lines, columns, 0, 0))
    env = dict(os.environ)
    env["TERM"] = TERMINAL_TYPE
    env.pop("COLUMNS", None)
    env.pop("LINES", None)
    targets = dict(redirect or {})
    files = {name: path.open("wb") for name, path in targets.items()}

    def setup() -> None:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)  # stdin is the pty: it becomes the controlling terminal

    try:
        # Test code only: the rule against preexec_fn is the launcher's (20 G3).
        process = subprocess.Popen(
            list(argv),
            stdin=slave,
            stdout=files.get("stdout", slave),
            stderr=files.get("stderr", slave),
            env=env,
            preexec_fn=setup,  # noqa: PLW1509
        )
    except BaseException:
        os.close(master)
        raise
    finally:
        os.close(slave)  # else end of output never comes
        for handle in files.values():
            handle.close()
    return TerminalRun(process=process, master=master, size=size, redirect=targets)


def run_in_terminal(
    scenario: Scenario,
    argv: Sequence[str],
    size: tuple[int, int],
    *,
    redirect: Mapping[str, Path] | None = None,
    answers: str | None = None,
) -> Outcome:
    """``I run ... in a terminal <w> by <h>``, redirected or answered: the answers typed at once (T5's note)."""
    after = prepare(scenario)
    run = run_on_terminal(argv, size=size, redirect=redirect).watch(scenario.fakes, after)
    try:
        if answers is not None:
            run.type("".join(f"{answer.strip()}\n" for answer in answers.split(",")))
        scenario.outcome = run.finish()
    except BaseException:
        run.kill()
        run.close()
        raise
    return scenario.outcome


def ctrl_c_once_shown(
    scenario: Scenario, argv: Sequence[str], size: tuple[int, int], first: str, second: str
) -> Outcome:
    """``... and press Ctrl-C once the terminal has shown "<a>" and then "<b>"``."""
    after = prepare(scenario)
    run = run_on_terminal(argv, size=size).watch(scenario.fakes, after)
    try:
        run.feed_until(first)
        run.feed_until(second)
        run.type(INTERRUPT)
        scenario.outcome = run.finish()
    except BaseException:
        run.kill()
        run.close()
        raise
    return scenario.outcome


def ctrl_c_once_elapsed(
    scenario: Scenario,
    argv: Sequence[str],
    size: tuple[int, int],
    first: str,
    seconds: int,
    *,
    found: list[int | None] | None = None,
) -> Outcome:
    """``... press Ctrl-C once the terminal has shown "<text>" and then an elapsed time <n> seconds later`` (40).

    The second wait is for a screen that still shows the text and whose ``elapsed`` value is at least ``seconds``
    greater than the one on the screen where the text was first seen: two values read from the screen, so the
    step does not depend on how long the process took to get there (01 T5, 22 O4). Each frame's screen is looked
    at, also of frames read together. Each wait has ``FEED_SECONDS``. ``found``, if given, receives the two
    elapsed values the step read (for its own test).
    """
    after = prepare(scenario)
    run = run_on_terminal(argv, size=size).watch(scenario.fakes, after)
    seen: list[int | None] = []  # the elapsed value where the text was first seen
    later: list[int] = []  # the first value at least ``seconds`` after it, on a screen that shows the text

    def look() -> None:
        if later or not _shows(run.screen, first):
            return
        now = elapsed_seconds("\n".join(run.screen.display))
        if not seen:
            seen.append(now)
        elif seen[0] is not None and now is not None and now >= seen[0] + seconds:
            later.append(now)

    try:
        run.pump_until(
            lambda: bool(seen), timeout=FEED_SECONDS, what=f"the terminal showing {first!r}", each_frame=look
        )
        if seen[0] is None:
            run.fail_with_screen(f"the screen that first showed {first!r} has no elapsed time")
        what = f"a screen showing {first!r} with an elapsed time {seconds} seconds after {seen[0]} seconds"
        run.pump_until(lambda: bool(later), timeout=FEED_SECONDS, what=what, each_frame=look)
        if found is not None:
            found.extend([seen[0], later[0]])
        run.type(INTERRUPT)
        scenario.outcome = run.finish()
    except BaseException:
        run.kill()
        run.close()
        raise
    return scenario.outcome


def quit_once_shown(scenario: Scenario, argv: Sequence[str], size: tuple[int, int], first: str, second: str) -> Outcome:
    """``... and press Ctrl-\\ once the terminal has shown "<a>" and then "<b>"`` (package 39, D60's SIGQUIT)."""
    after = prepare(scenario)
    run = run_on_terminal(argv, size=size).watch(scenario.fakes, after)
    try:
        run.feed_until(first)
        run.feed_until(second)
        run.type(QUIT)
        scenario.outcome = run.finish()
    except BaseException:
        run.kill()
        run.close()
        raise
    return scenario.outcome


def ctrl_c_at_checkpoint(scenario: Scenario, argv: Sequence[str], size: tuple[int, int]) -> Outcome:
    """``... and press Ctrl-C once java has begun its checkpoint``: the pty is read all the while."""
    after = prepare(scenario)
    run = run_on_terminal(argv, size=size).watch(scenario.fakes, after)
    fakes = scenario.fakes
    try:
        marks: list[dict[str, Any]] = []

        def checkpoint_logged() -> bool:
            line = find_log(fakes, "java", lambda line: line.get("event") == "checkpoint", after=after)
            if line is not None:
                marks.append(line)
            return line is not None

        run.pump_until(checkpoint_logged, timeout=FEED_SECONDS, what="the fake java's checkpoint line")
        start_line = wait_for_log(
            fakes,
            "java",
            lambda line: is_tool_start(line) and line.get("pid") == marks[0]["pid"],
            after=after,
            what="the start line of the checkpointing run",
        )
        run.type(INTERRUPT)
        release_when_waiting(
            scenario,
            start_line,
            lambda: _shows(run.screen, WAITING_LINE),
            after=after,
            ended=lambda: run.ended,
            pump=run.read,
        )
        scenario.outcome = run.finish()
    except BaseException:
        run.kill()
        run.close()
        raise
    return scenario.outcome


# Then: the terminal


def _terminal(scenario: Scenario) -> tuple[bytes, tuple[int, int]]:
    outcome = scenario.result()
    if outcome.terminal is None or outcome.terminal_size is None:
        fail('the last run was not on a terminal: a terminal step needs "I run ... in a terminal <w> by <h>"')
    return outcome.terminal, outcome.terminal_size


def check_terminal_contains(scenario: Scenario, text: str) -> None:
    data, size = _terminal(scenario)
    wanted, screen = scenario.expand(text), final_screen(data, size)
    if wanted not in screen:
        fail(f"the terminal does not show {wanted!r}; it ends with:\n{screen}")


def check_terminal_not_contains(scenario: Scenario, text: str) -> None:
    data, size = _terminal(scenario)
    wanted, screen = scenario.expand(text), final_screen(data, size)
    if wanted in screen:
        fail(f"the terminal shows {wanted!r}; it ends with:\n{screen}")
    if wanted in without_escapes(data):
        fail(f"{wanted!r} was written to the terminal, though it is no longer on the screen:\n{screen}")


def check_showed_the_layout(scenario: Scenario) -> None:
    """``the terminal showed the layout``: the enter sequence, a screen with the panel titles, the leave sequence;
    nothing about how the run ended (22 O4)."""
    data, size = _terminal(scenario)
    if ENTER_ALT not in data:
        fail(f"the alternate screen was never entered; the terminal ends with:\n{final_screen(data, size)}")
    shown = layout_screens(data, size)
    if not shown:
        fail(
            f"the alternate screen was never left; its last screen:\n{screen_text(data.partition(ENTER_ALT)[2], size)}"
        )
    if not any(all(title in text for title in PANEL_TITLES) for text in shown):
        fail(f"no screen of the layout had the panel titles {PANEL_TITLES}; the last one:\n{shown[-1]}")


def check_last_frame_contains(scenario: Scenario, text: str) -> None:
    """``the last layout frame contains "<text>"``: the last screen before the leave sequence."""
    data, size = _terminal(scenario)
    shown = layout_screens(data, size)
    if not shown:
        fail("the terminal did not show the layout: no enter and leave sequences of the alternate screen")
    wanted = scenario.expand(text)
    if wanted not in shown[-1]:
        fail(f"the last layout frame does not show {wanted!r}; it was:\n{shown[-1]}")


def check_stayed_on_the_main_screen(scenario: Scenario) -> None:
    """``the terminal stayed on the main screen``: the alternate screen was neither entered nor left."""
    data, size = _terminal(scenario)
    if ENTER_ALT in data or LEAVE_ALT in data:
        fail(f"the alternate screen was used; the terminal ends with:\n{final_screen(data, size)}")


def terminal_end(scenario: Scenario) -> str:
    data, size = _terminal(scenario)
    return final_screen(data, size)
