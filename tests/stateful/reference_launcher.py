"""A throwaway model of the launcher's signal handling, a step at a time (design 20 G3, 11 R2).

It exists so that the state machine in ``test_signals.py`` can be run before
``tlaup.java.launcher`` is written, to show that the machine itself is sound. It is not
product code: the work package that builds the launcher deletes this file and the
reference test with it.

Revised 2026-11-20 for decisions D51 and D52: a first signal while a checkpoint is being
written is held until ``checkpoint_written`` (the grace period runs from then), and the
child is given a lifeline. The real lifeline is a Java agent; the fake child of the tests
is a Python script, so here it is the environment variable ``LIFELINE_PID``, which the fake
child watches the same way the agent watches tlaup's process id.
"""

from __future__ import annotations

import contextlib
import os
import queue
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence
    from types import FrameType

NAMES = {signal.SIGINT: "int", signal.SIGTERM: "term", signal.SIGHUP: "hup"}
CODES = {"int": 130, "term": 143, "hup": 129}


@dataclass(frozen=True)
class ProcessOutcome:
    exit_code: int
    tool_exit_code: int | None
    stopped_by: str | None


class Signals:
    def __init__(self, *, leave_interrupt: bool, clock: Callable[[], float]) -> None:
        self.first: str | None = None
        self.first_at: float | None = None
        self.count = 0
        self.leave_interrupt = leave_interrupt
        self.clock = clock
        self.child: subprocess.Popen[bytes] | None = None
        self.checkpointing = False
        self.held = False

    def handle(self, number: int, _frame: FrameType | None) -> None:
        if number == signal.SIGINT and self.leave_interrupt:
            return
        self.count += 1
        if self.first is None:
            self.first = NAMES[signal.Signals(number)]
        if self.child is not None and self.child.poll() is None:
            if self.count == 1 and self.checkpointing:
                self.held = True  # D52: sent on when the checkpoint is written
            elif self.count == 1:
                self.first_at = self.clock()
                self.child.terminate()
            else:
                self.held = False
                self.child.kill()
        elif self.first_at is None:
            self.first_at = self.clock()

    def checkpoint_started(self) -> None:
        self.checkpointing = True

    def checkpoint_written(self) -> None:
        self.checkpointing = False
        if self.held:
            self.held = False
            self.first_at = self.clock()
            if self.child is not None and self.child.poll() is None:
                self.child.terminate()


@contextlib.contextmanager
def signals_held(*, leave_interrupt: bool = False, clock: Callable[[], float] = time.monotonic) -> Iterator[Signals]:
    signals = Signals(leave_interrupt=leave_interrupt, clock=clock)
    previous = {}
    for number in (*NAMES, signal.SIGQUIT):
        if signal.getsignal(number) is signal.SIG_IGN:
            continue  # ignored when tlaup started: left ignored
        handler = signals.handle if number in NAMES else (lambda _number, _frame: None)
        previous[number] = signal.signal(number, handler)
    try:
        yield signals
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


class ChildRun:
    """One child under ``signals_held``, a step at a time."""

    def __init__(
        self,
        argv: Sequence[str],
        signals: Signals,
        *,
        on_stdout: Callable[[str], None] | None = None,
        passthrough: bool = False,
        lifeline: bool = True,
        grace_seconds: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.argv = list(argv)
        self.signals = signals
        self.on_stdout = on_stdout
        self.passthrough = passthrough
        self.lifeline = lifeline
        self.grace = grace_seconds
        self.clock = clock
        self.proc: subprocess.Popen[bytes] | None = None
        self._lines: queue.Queue[bytes | None] = queue.Queue(maxsize=10_000)
        self._open_pipes = 0
        self._stopped_at: float | None = None
        self._outcome: ProcessOutcome | None = None

    @property
    def pid(self) -> int | None:
        return None if self.proc is None else self.proc.pid

    def may_start(self) -> bool:
        return self.signals.first is None

    def spawn(self) -> None:
        pipe = None if self.passthrough else subprocess.PIPE
        stdin = None if self.passthrough else subprocess.DEVNULL
        env = {**os.environ, "LIFELINE_PID": str(os.getpid())} if self.lifeline else None
        self.proc = subprocess.Popen(self.argv, stdin=stdin, stdout=pipe, env=env)
        if self.proc.stdout is not None:
            self._open_pipes = 1
            threading.Thread(target=self._read, args=(self.proc.stdout,), daemon=True).start()

    def _read(self, pipe: IO[bytes]) -> None:
        for line in pipe:
            self._lines.put(line)
        self._lines.put(None)

    def attach(self) -> None:
        self.signals.child = self.proc  # first attach, then look: the other order leaves a gap
        if self.signals.first is not None and self.proc is not None:
            self.signals.first_at = self.clock()
            self.proc.terminate()

    def _grace_over(self) -> bool:
        started = self._stopped_at if self._stopped_at is not None else self.signals.first_at
        return started is not None and self.clock() - started >= self.grace

    def turn(self, timeout: float = 0.2) -> bool:
        """One turn of the loop. True when the child is gone and its pipes are closed."""
        assert self.proc is not None
        if self.proc.poll() is None and self._grace_over():
            self.proc.kill()
        if self._open_pipes:
            try:
                line = self._lines.get(timeout=timeout)
            except queue.Empty:
                return False
            if line is None:
                self._open_pipes -= 1
            elif self.on_stdout is not None:
                self.on_stdout(line.decode("utf-8", errors="replace"))
            return False
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return False
        return True

    def stop(self) -> None:
        """The ``finally`` round the loop: stop the child, then empty the queue."""
        assert self.proc is not None
        if self.proc.poll() is None:
            self.proc.terminate()
            self._stopped_at = self.clock()
        deadline = time.monotonic() + 30
        while self.proc.poll() is None and time.monotonic() < deadline:
            if self._grace_over():
                self.proc.kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.proc.wait(timeout=0.05)
        deadline = time.monotonic() + 2
        while self._open_pipes and time.monotonic() < deadline:
            with contextlib.suppress(queue.Empty):
                if self._lines.get(timeout=0.05) is None:
                    self._open_pipes -= 1

    def outcome(self) -> ProcessOutcome:
        if self._outcome is None:
            stopped_by = self.signals.first
            tool = None if self.proc is None else self.proc.returncode
            if stopped_by is not None:
                code = CODES[stopped_by]
            elif tool is None:
                code = 0
            else:
                code = tool if tool >= 0 else 128 - tool
            self._outcome = ProcessOutcome(code, tool, stopped_by)
        return self._outcome
