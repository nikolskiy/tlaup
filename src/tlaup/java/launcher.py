"""Starting a Java tool: the invocation, the signals round it, and reading its output (design 20 G3, 11 R1 to R3).

`run_streaming` reads the tool's output line by line; `run_passthrough` leaves the terminal to it. Both are loops
over the steps of `ChildRun` (decision D46), which the stateful test drives one at a time. The handlers that
`signals_held` installs record a signal on `Signals` and, when a child is attached, act on it; they never raise and
never print. The launcher prints nothing and imports neither Typer nor `tlaup.cli`.
"""

from __future__ import annotations

import collections
import contextlib
import os
import queue
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Literal

from tlaup import stdio
from tlaup.errors import InternalError, ToolStartError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from types import FrameType

SignalName = Literal["int", "term", "hup"]
Stream = Literal["stdout", "stderr"]

LIFELINE_JAR = Path(__file__).resolve().with_name("lifeline.jar")
ENCODING_OPTIONS = ("-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8")  # D56
CODES: dict[SignalName, int] = {"int": 130, "term": 143, "hup": 129}
CLOSED_PIPE_CODE = 141
QUEUE_BOUND = 10_000
TAIL_LINES = 50
TURN_SECONDS = 0.2  # the longest the main thread waits for a line or for the child
DRAIN_SECONDS = 2.0  # how long the way out empties the queue; a guess (G3, Risks)
GRACE_SECONDS = 10.0
POSIX = os.name != "nt"

# The signals acted on, where the platform has them (D15).
_ACTED_ON: tuple[tuple[str, SignalName], ...] = (("SIGINT", "int"), ("SIGTERM", "term"), ("SIGHUP", "hup"))
NAMES: dict[int, SignalName] = {getattr(signal, attr): name for attr, name in _ACTED_ON if hasattr(signal, attr)}
SIGQUIT: int | None = getattr(signal, "SIGQUIT", None)


@dataclass(frozen=True)
class JavaInvocation:
    java: Path
    jvm_options: tuple[str, ...]
    system_properties: tuple[tuple[str, str], ...]
    classpath: tuple[Path, ...]
    main_class: str
    args: tuple[str, ...]
    cwd: Path | None = None  # None: do not change folder
    lifeline: bool = True  # D51: add the lifeline agent; False for --show-command alone

    def argv(self) -> list[str]:
        """java, the lifeline, the encoding options, the JVM options, -Dk=v ..., -cp and the classpath, the main
        class, the arguments. An empty classpath leaves `-cp` out."""
        argv = [str(self.java)]
        if self.lifeline:
            argv.append(f"-javaagent:{LIFELINE_JAR}=pid={os.getpid()}")
        argv.extend(ENCODING_OPTIONS)  # before the user's options, so that one of theirs wins
        argv.extend(self.jvm_options)
        argv.extend(f"-D{key}={value}" for key, value in self.system_properties)
        if self.classpath:
            argv.extend(("-cp", os.pathsep.join(str(entry) for entry in self.classpath)))
        argv.append(self.main_class)
        argv.extend(self.args)
        return argv


@dataclass(frozen=True)
class ProcessOutcome:
    exit_code: int  # what tlaup should exit with (02 X1)
    tool_exit_code: int | None  # what the process returned; None if it never started
    stopped_by: SignalName | None
    stderr_tail: tuple[str, ...]  # the last 50 lines the tool wrote to stderr; empty for a passthrough run
    stopped_for_closed_pipe: bool = False  # the reader of tlaup's stdout went away while the child ran


class Signals:
    """The state the handlers write to; one child at a time is attached to it."""

    def __init__(self, *, leave_interrupt: bool = False, clock: Callable[[], float] = time.monotonic) -> None:
        self.first: SignalName | None = None  # the first signal acted on
        self.first_at: float | None = None  # the clock when it was sent on to the child
        self.count = 0  # signals acted on; an unforwarded SIGINT and SIGQUIT are not counted
        self.leave_interrupt = leave_interrupt  # SIGINT is the child's business (repl)
        self.checkpointing = False  # D52: the parser has seen 2195 and not yet 2196
        self.held = False  # D52: a first signal is recorded and waits for the checkpoint
        self.clock = clock
        self._run: ChildRun | None = None

    def checkpoint_started(self) -> None:
        self.checkpointing = True

    def checkpoint_written(self) -> None:
        """Sends a held first signal on: `terminate()`, and the grace period runs from now."""
        self.checkpointing = False
        if not self.held:
            return
        self.held = False
        run = self._run
        if run is not None and run.alive():
            self.first_at = self.clock()
            run.send_terminate(self.first_at)

    def handle(self, number: int, _frame: FrameType | None = None) -> None:
        """The handler of SIGINT, SIGTERM and SIGHUP. It never raises and does no I/O."""
        name = NAMES[number]
        if name == "int" and self.leave_interrupt:
            return
        self.count += 1
        run = self._run
        alive = run is not None and run.alive()
        if run is not None and run.closed_pipe_first:
            # The closed pipe was the first stop and is not a signal (FC9): this one is a second stop.
            if alive:
                run.send_kill()
            return
        if self.first is None:
            self.first = name
        if run is None or not alive:
            return
        if self.count > 1 or run.terminate_sent:
            self.held = False
            run.send_kill()
        elif self.checkpointing:
            self.held = True  # sent on by checkpoint_written, or at once by a second signal
        else:
            self.first_at = self.clock()
            run.send_terminate(self.first_at)

    def handle_quit(self, _number: int, _frame: FrameType | None = None) -> None:
        """SIGQUIT is never recorded. Only the JVM of a parsed run, in a group of its own (D60), gets it forwarded;
        every other child already has it from the terminal."""
        run = self._run
        if SIGQUIT is not None and run is not None and run.own_group and run.alive():
            run.send(SIGQUIT)


@contextlib.contextmanager
def signals_held(*, leave_interrupt: bool = False, clock: Callable[[], float] = time.monotonic) -> Iterator[Signals]:
    """Installs the handlers for the whole run and restores the previous ones; a signal ignored on entry is left
    alone. The main thread only."""
    if threading.current_thread() is not threading.main_thread():
        message = "signals_held was entered off the main thread"
        raise InternalError(message)
    signals = Signals(leave_interrupt=leave_interrupt, clock=clock)
    handlers: dict[int, Callable[[int, FrameType | None], None]] = dict.fromkeys(NAMES, signals.handle)
    if SIGQUIT is not None:
        handlers[SIGQUIT] = signals.handle_quit
    previous: dict[int, Callable[[int, FrameType | None], object] | int | None] = {}
    try:
        for number, handler in handlers.items():
            if signal.getsignal(number) == signal.SIG_IGN:
                continue  # nohup, a background job of a shell script: the caller's choice stands
            previous[number] = signal.signal(number, handler)
        yield signals
    finally:
        for number, old in previous.items():
            signal.signal(number, signal.SIG_DFL if old is None else old)


def _close_all(fds: tuple[int, ...]) -> None:
    for fd in fds:
        with contextlib.suppress(OSError):
            os.close(fd)


class ChildRun:
    """One child under `signals_held`, a step at a time: `may_start`, `spawn`, `attach`, `turn` until it says the
    child is gone, `stop` in the `finally`, then `outcome`."""

    def __init__(  # noqa: PLR0913 - the design's signature (G3) and its joints
        self,
        inv: JavaInvocation,
        signals: Signals,
        *,
        on_stdout: Callable[[str], None] | None = None,
        on_stderr: Callable[[str], None] | None = None,
        on_held: Callable[[SignalName], None] | None = None,
        merge_stderr: bool = False,
        passthrough: bool = False,
        pass_fds: tuple[int, ...] = (),
        stop_when_reader_gone: bool | None = None,  # None: when the output is read (run_streaming always polls)
        reader_gone: Callable[[int], bool] = stdio.reader_gone,
        grace_seconds: float = GRACE_SECONDS,
        clock: Callable[[], float] | None = None,  # None: the clock of `signals`
    ) -> None:
        if signals.leave_interrupt and not passthrough:
            _close_all(pass_fds)
            message = "a run whose output is read needs signals_held(leave_interrupt=False)"
            raise InternalError(message)
        self.inv = inv
        self.signals = signals
        self.on_stdout = on_stdout
        self.on_stderr = on_stderr
        self.on_held = on_held
        self.merge_stderr = merge_stderr and not passthrough
        self.passthrough = passthrough
        self.own_group = POSIX and not passthrough and not merge_stderr  # D60: a parsed TLC run only
        self._pass_fds = pass_fds
        self._watch_reader = (not passthrough) if stop_when_reader_gone is None else stop_when_reader_gone
        self._reader_gone = reader_gone
        self._grace = grace_seconds
        self._clock = signals.clock if clock is None else clock
        self._proc: subprocess.Popen[bytes] | None = None
        self._queue: queue.Queue[tuple[Stream, bytes | None]] = queue.Queue(maxsize=QUEUE_BOUND)
        self._open_streams = 0
        self._tail: collections.deque[str] = collections.deque(maxlen=TAIL_LINES)
        self._terminated_at: float | None = None
        self._kill_sent = False
        self._held_told = False
        self._outcome: ProcessOutcome | None = None
        self.closed_pipe_seen = False
        self.closed_pipe_first = False  # seen before any signal was recorded

    # ------------------------------------------------------------------ what the handlers use

    @property
    def pid(self) -> int | None:
        return None if self._proc is None else self._proc.pid

    @property
    def terminate_sent(self) -> bool:
        return self._terminated_at is not None

    @property
    def queued(self) -> int:
        """Lines read and not yet handed on; never more than `QUEUE_BOUND`."""
        return self._queue.qsize()

    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def send(self, number: int) -> None:
        if self._proc is not None:
            self._proc.send_signal(number)  # looks first, so a child already reaped gets nothing

    def send_terminate(self, now: float) -> None:
        """`terminate()`; the grace period runs from `now`."""
        self._terminated_at = now
        if self._proc is not None:
            self._proc.terminate()

    def send_kill(self) -> None:
        self._kill_sent = True
        if self._proc is not None:
            self._proc.kill()

    # ------------------------------------------------------------------ the steps

    def may_start(self) -> bool:
        """False when a signal came first: nothing is started, and the outcome is that signal's."""
        first = self.signals.first
        if first is None:
            return True
        _close_all(self._pass_fds)
        self._outcome = ProcessOutcome(CODES[first], None, first, ())
        return False

    def spawn(self) -> None:
        """Starts the child; `OSError` becomes `ToolStartError`. The descriptors in `pass_fds` are closed here
        whether or not the start worked: they are duplicates made for the child alone."""
        if self._proc is not None or self._outcome is not None:
            message = "a ChildRun starts one child, once"
            raise InternalError(message)
        argv = self.inv.argv()
        if self.passthrough:
            stdin: int | None = None
            stdout: int | None = None
            stderr: int | None = None
        else:
            stdin, stdout = subprocess.DEVNULL, subprocess.PIPE
            stderr = subprocess.STDOUT if self.merge_stderr else subprocess.PIPE
        try:
            self._proc = subprocess.Popen(  # an argument list, never a shell
                argv,
                cwd=self.inv.cwd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                pass_fds=self._pass_fds if POSIX else (),
                process_group=0 if self.own_group else None,
            )
        except OSError as error:
            message = f"{self.inv.java} could not be started: {error.strerror or error}"
            raise ToolStartError(message, hint="check that the file is a Java program for this machine") from error
        finally:
            _close_all(self._pass_fds)
        for stream, pipe in (("stdout", self._proc.stdout), ("stderr", self._proc.stderr)):
            if pipe is not None:
                self._open_streams += 1
                reader = threading.Thread(
                    target=self._read, args=(stream, pipe), name=f"tlaup-reader-{stream}", daemon=True
                )
                reader.start()

    def _read(self, stream: Stream, pipe: IO[bytes]) -> None:
        """A reader thread: lines split on newline with their ending kept, then the end marker."""
        try:
            with pipe:
                for line in pipe:
                    self._queue.put((stream, line))
        finally:
            self._queue.put((stream, None))

    def attach(self) -> None:
        """Attach first, look second: a signal between the two still reaches the child (finding K3-2)."""
        self.signals._run = self  # Signals and ChildRun are one mechanism
        if self.signals.first is not None and self._proc is not None and not self.terminate_sent:
            self.signals.first_at = self.signals.clock()
            self.send_terminate(self.signals.first_at)

    def turn(self, timeout: float = TURN_SECONDS) -> bool:
        """One turn of the loop: a line handed on, or a wait for the child. True when the child is gone and its
        pipes are closed; the outcome is taken then."""
        if self._outcome is not None:
            return True
        proc = self._started()
        self._watch()
        if self._open_streams:
            try:
                stream, data = self._queue.get(timeout=timeout)
            except queue.Empty:
                return False
            if data is None:
                self._open_streams -= 1
            else:
                self._deliver(stream, data)
            return False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return False
        self._finish()
        return True

    def stop(self) -> None:
        """The `finally` round the loop: stop the child if it runs (`terminate()`, `kill()` after the grace period),
        then empty the queue until both readers have finished or two seconds have passed."""
        if self._outcome is not None or self._proc is None:
            return
        proc = self._proc
        if proc.poll() is None and not self.terminate_sent:
            self.send_terminate(self._clock())
        while proc.poll() is None:
            if not self._kill_sent and self._grace_over():
                self.send_kill()
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=0.05)
        deadline = time.monotonic() + DRAIN_SECONDS  # real time: the injected clock is for the grace period
        while self._open_streams and time.monotonic() < deadline:
            try:
                _, data = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if data is None:
                self._open_streams -= 1
        self._finish()

    def outcome(self) -> ProcessOutcome:
        """Taken once, when the launcher saw the child gone (or nothing started); the same answer every time."""
        if self._outcome is None:
            message = "the outcome of a child that is still running was asked for"
            raise InternalError(message)
        return self._outcome

    # ------------------------------------------------------------------ inside a turn

    def _started(self) -> subprocess.Popen[bytes]:
        if self._proc is None:
            message = "the loop was turned before the child was started"
            raise InternalError(message)
        return self._proc

    def _grace_over(self) -> bool:
        return self._terminated_at is not None and self._clock() - self._terminated_at >= self._grace

    def _watch(self) -> None:
        """The grace period, the reader of tlaup's stdout, a held signal."""
        if not self.alive():
            return
        if self.terminate_sent and not self._kill_sent and self._grace_over():
            self.send_kill()
        if self._watch_reader and not self.closed_pipe_seen and self._reader_gone(1):
            self._closed_pipe()
        if self.signals.held and not self._held_told:
            self._held_told = True
            if self.on_held is not None and self.signals.first is not None:
                self.on_held(self.signals.first)

    def _closed_pipe(self) -> None:
        """Nobody reads the result (D58): stop the child as for a first signal, but it is not one (FC9)."""
        self.closed_pipe_seen = True
        signals = self.signals
        if signals.first is None:
            self.closed_pipe_first = True
        if self.terminate_sent:
            return
        now = self._clock()
        if signals.held:  # does not wait for the checkpoint: nobody can use it
            signals.held = False
            signals.first_at = now
        self.send_terminate(now)

    def _deliver(self, stream: Stream, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")  # cannot raise (R3)
        if stream == "stdout":
            if self.on_stdout is not None:
                self.on_stdout(text)
            return
        self._tail.append(text.rstrip("\r\n"))
        if self.on_stderr is not None:
            self.on_stderr(text)

    def _finish(self) -> None:
        proc = self._started()
        returned = proc.returncode
        first = self.signals.first
        stopped_by: SignalName | None = None
        if self.closed_pipe_first:
            code = CLOSED_PIPE_CODE
        elif first is not None:
            code, stopped_by = CODES[first], first
        elif returned < 0:
            code = 128 - returned  # killed by a signal tlaup did not send
        else:
            code = returned
        self._outcome = ProcessOutcome(code, returned, stopped_by, tuple(self._tail), self.closed_pipe_seen)


def _drive(run: ChildRun) -> ProcessOutcome:
    if not run.may_start():
        return run.outcome()
    run.spawn()
    try:
        run.attach()
        while not run.turn():
            pass
    finally:
        run.stop()  # nothing to do after a loop that ended; a callback's exception goes on unchanged
    return run.outcome()


def run_streaming(  # noqa: PLR0913 - the design's signature (G3)
    inv: JavaInvocation,
    *,
    on_stdout: Callable[[str], None],
    on_stderr: Callable[[str], None],
    signals: Signals,
    merge_stderr: bool = False,
    pass_fds: tuple[int, ...] = (),
    on_held: Callable[[SignalName], None] | None = None,
    grace_seconds: float = GRACE_SECONDS,
    reader_gone: Callable[[int], bool] = stdio.reader_gone,
) -> ProcessOutcome:
    """Runs the tool with its output read line by line; `signals` must not leave SIGINT to the child."""
    run = ChildRun(
        inv,
        signals,
        on_stdout=on_stdout,
        on_stderr=on_stderr,
        on_held=on_held,
        merge_stderr=merge_stderr,
        pass_fds=pass_fds,
        stop_when_reader_gone=True,
        reader_gone=reader_gone,
        grace_seconds=grace_seconds,
    )
    return _drive(run)


def run_passthrough(  # noqa: PLR0913 - the design's signature (G3)
    inv: JavaInvocation,
    *,
    signals: Signals,
    forward_interrupt: bool,
    pass_fds: tuple[int, ...] = (),
    stop_when_reader_gone: bool = False,
    grace_seconds: float = GRACE_SECONDS,
    reader_gone: Callable[[int], bool] = stdio.reader_gone,
) -> ProcessOutcome:
    """Runs the tool on tlaup's own streams; nothing is read. `forward_interrupt` must be the opposite of the
    block's `leave_interrupt`."""
    if forward_interrupt == signals.leave_interrupt:
        _close_all(pass_fds)
        message = (
            f"run_passthrough(forward_interrupt={forward_interrupt}) under leave_interrupt={signals.leave_interrupt}"
        )
        raise InternalError(message)
    run = ChildRun(
        inv,
        signals,
        passthrough=True,
        pass_fds=pass_fds,
        stop_when_reader_gone=stop_when_reader_gone,
        reader_gone=reader_gone,
        grace_seconds=grace_seconds,
    )
    return _drive(run)
