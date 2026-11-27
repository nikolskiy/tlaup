"""The real-process runner of the feature steps: pipes, closed pipes, signals, the foreground group (01 T5).

``when.py`` wraps ``run_as_process`` and ``start_and_signal``; the unit tests call them with small programs
as ``argv``. Every wait is for a condition with a timeout (T12 rule 5); a process that outlives its wait is
killed by its process id (or its group) and the step fails with what it printed.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Literal

import pytest

from tests.steps._scenario import POLL_SECONDS, VERSION_START, Outcome, _process_alive, fail

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from tests.fakes.control import Fakes, Tool
    from tests.steps._scenario import Scenario

WAIT_SECONDS = 60.0  # every real-process step waits this long for the process to end
LOG_WAIT_SECONDS = 10.0  # and this long for a line of the fake's log or a text on stderr
# The signals a send step may name: 11 R2's three and 39's SIGQUIT for its Ctrl-\ form.
SIGNAL_NAMES = ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT")
# The part both wordings of 11 R2's waiting line share.
WAITING_LINE = "waiting for TLC to finish writing its checkpoint"
POSIX = os.name != "nt"

Arrangement = Literal["captured", "input", "reader", "closed-stdout", "closed-both", "null-and-closed"]
Moment = Literal["running", "twice", "checkpoint"]


def _child_setup(*, reset_sigint: bool, new_group: bool) -> Callable[[], None] | None:
    if not POSIX or not (reset_sigint or new_group):
        return None

    def setup() -> None:
        if reset_sigint:
            signal.signal(signal.SIGINT, signal.SIG_DFL)
        if new_group:
            os.setpgid(0, 0)

    return setup


def start(
    argv: Sequence[str],
    *,
    stdin: Any,
    stdout: Any,
    stderr: Any,
    new_group: bool = False,
    reset_sigint: bool = True,
    env: Mapping[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    """Start ``argv`` with the isolation fixture's environment (T2), SIGINT at its default (research 23's rule).

    ``new_group`` makes the child the leader of a new process group, for the foreground-group forms.
    """
    if new_group and not POSIX:
        pytest.skip("process groups are POSIX; no Windows CI (D15)")
    environment = dict(os.environ if env is None else env)
    setup = _child_setup(reset_sigint=reset_sigint, new_group=new_group)
    # Test code only: the rule against preexec_fn is the launcher's (20 G3).
    return subprocess.Popen(
        list(argv),
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        env=environment,
        preexec_fn=setup,  # noqa: PLW1509
    )


def closed_pipe() -> int:
    """A pipe whose read end is closed already, so the first write fails whatever the size and timing."""
    read_end, write_end = os.pipe()
    os.close(read_end)
    return write_end


def exit_code_of(returncode: int) -> int:
    """The code as a shell reports it: a process ended by signal ``s`` is ``128 + s``."""
    return 128 - returncode if returncode < 0 else returncode


def signal_number(name: str) -> int:
    """The signal a step names; skips where the platform lacks it (D15)."""
    if name not in SIGNAL_NAMES:
        fail(f"a send step takes {', '.join(SIGNAL_NAMES)}, not {name}")
    if not POSIX or not hasattr(signal, name):
        pytest.skip(f"{name} does not exist on this platform; no Windows CI (D15)")
    number: int = getattr(signal, name)
    return number


def read_log(fakes: Fakes, tool: Tool) -> list[dict[str, Any]]:
    """The fake's log so far; a line still being written counts as not there yet."""
    try:
        return fakes.log(tool)
    except ValueError:
        return []


def find_log(fakes: Fakes, tool: Tool, predicate: Callable[[dict[str, Any]], bool], *, after: int) -> dict | None:
    """The first line from line ``after`` on that satisfies ``predicate``, or None."""
    for line in read_log(fakes, tool)[after:]:
        if predicate(line):
            return line
    return None


def wait_for_log(
    fakes: Fakes,
    tool: Tool,
    predicate: Callable[[dict[str, Any]], bool],
    *,
    after: int,
    timeout: float = LOG_WAIT_SECONDS,
    process: subprocess.Popen[bytes] | None = None,
    what: str = "the line",
) -> dict:
    """Poll the fake's log for a line, from line ``after`` on, that satisfies ``predicate``.

    Fails with the log so far after ``timeout``, or as soon as ``process`` has ended without the line.
    """
    deadline = time.monotonic() + timeout
    while True:
        ended = process is not None and process.poll() is not None
        line = find_log(fakes, tool, predicate, after=after)
        if line is not None:
            return line
        if ended or time.monotonic() >= deadline:
            why = "the process ended" if ended else f"{timeout} seconds passed"
            fail(f"{why} before the {tool} log showed {what}; the log so far:\n{read_log(fakes, tool)[after:]}")
        time.sleep(POLL_SECONDS)


def reap_fakes(fakes: Fakes | None, after: int) -> None:
    """SIGKILL, by process id, every fake java started since line ``after`` that is still alive.

    For a run that was killed: a JVM in a group of its own (D60) is not reached by killing tlaup's group.
    """
    if fakes is None or not POSIX:
        return
    killed = []
    for line in read_log(fakes, "java")[after:]:
        if line.get("event") == "start" and _process_alive(int(line["pid"])):
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(line["pid"]), signal.SIGKILL)
                killed.append(int(line["pid"]))
    deadline = time.monotonic() + LOG_WAIT_SECONDS  # a SIGKILL lands soon, not at once
    while any(_process_alive(pid) for pid in killed) and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)


def kill_group(pgid: int) -> None:
    """SIGKILL a whole group, whether or not its leader is still there."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, signal.SIGKILL)


def is_tool_start(line: dict[str, Any]) -> bool:
    """A ``start`` line of a tool's main class, not the version check that comes first (T5)."""
    return line.get("event") == "start" and line.get("main") not in (None, VERSION_START)


def _text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


@dataclass
class ProcessRun:
    """One started process and where its streams go."""

    process: subprocess.Popen[bytes]
    stdout_file: Path | None  # None: not captured (a closed pipe, the null device, or read by the step)
    stderr_file: Path | None
    stdin: IO[bytes] | None  # the pipe the I start steps hold open until the process has ended
    group: bool
    pgid: int | None
    stdout_text: str | None = None  # what the step itself read from stdout (the reader form)
    fakes: Fakes | None = None  # whose java starts since line ``after`` a kill also ends
    after: int = 0

    def stderr_so_far(self) -> str:
        return _text(self.stderr_file.read_bytes()) if self.stderr_file is not None else ""

    def send(self, number: int) -> None:
        """To tlaup alone (``os.kill``), or to its group, as Ctrl-C in a terminal does (``os.killpg``)."""
        if self.group:
            assert self.pgid is not None
            os.killpg(self.pgid, number)
        else:
            os.kill(self.process.pid, number)

    def wait_for_stderr(self, text: str, *, timeout: float = LOG_WAIT_SECONDS) -> None:
        deadline = time.monotonic() + timeout
        while text not in self.stderr_so_far():
            if self.process.poll() is not None and text not in self.stderr_so_far():
                self.fail_with_output(f"the process ended before stderr contained {text!r}")
            if time.monotonic() >= deadline:
                self.fail_with_output(f"stderr did not contain {text!r} within {timeout} seconds")
            time.sleep(POLL_SECONDS)

    def kill(self) -> None:
        """tlaup (its whole group, when it has one of its own), then every fake java of this run."""
        if self.group and self.pgid is not None:
            kill_group(self.pgid)
        elif self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        reap_fakes(self.fakes, self.after)

    def close(self) -> None:
        if self.stdin is not None:
            self.stdin.close()
            self.stdin = None

    def output(self) -> str:
        out = self.stdout_text
        if out is None and self.stdout_file is not None:
            out = _text(self.stdout_file.read_bytes())
        err = self.stderr_so_far() if self.stderr_file is not None else None
        return f"\n--- stdout ---\n{out}\n--- stderr ---\n{err}"

    def fail_with_output(self, message: str) -> None:
        self.kill()
        self.close()
        fail(f"{message}; it was killed{self.output()}")

    def finish(self, *, timeout: float = WAIT_SECONDS) -> Outcome:
        """Wait for the end, then close the held pipe; a process still running after ``timeout`` is killed."""
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.fail_with_output(f"the process was still running after {timeout} seconds")
        self.close()
        stdout = self.stdout_text
        if stdout is None and self.stdout_file is not None:
            stdout = _text(self.stdout_file.read_bytes())
        stderr = self.stderr_so_far() if self.stderr_file is not None else None
        return Outcome(
            exit_code=exit_code_of(self.process.returncode),
            stdout=stdout,
            stderr=stderr,
            pid=self.process.pid,
            pgid=self.pgid,
        )


def group_of(process: subprocess.Popen[bytes], *, new_group: bool) -> int | None:
    if not POSIX:
        return None
    try:
        return os.getpgid(process.pid)
    except ProcessLookupError:  # already gone and reaped elsewhere; the group it was given
        return process.pid if new_group else os.getpgrp()


def _streams_folder(scenario: Scenario) -> Path:
    base = scenario.folder / "streams"
    base.mkdir(parents=True, exist_ok=True)
    folder = base / f"run-{sum(1 for _ in base.iterdir())}"
    folder.mkdir()
    return folder


def tlaup_argv(scenario: Scenario, command: str) -> list[str]:
    """``python -m tlaup`` with the command's words after ``tlaup``, placeholders expanded."""
    return [sys.executable, "-m", "tlaup", *scenario.words(command)[1:]]


def prepare(scenario: Scenario) -> int:
    """The ``before_run`` hooks; returns how many lines the fake java's log has now."""
    for hook in scenario.before_run:
        hook()
    return len(read_log(scenario.fakes, "java"))


def launch(
    scenario: Scenario,
    argv: Sequence[str],
    *,
    stdin: Literal["null", "pipe"],
    stdout: Literal["file", "pipe", "closed", "null"],
    stderr: Literal["file", "closed"],
    new_group: bool = False,
    after: int = 0,
) -> ProcessRun:
    """Start ``argv`` with its three streams arranged as a step says; ``after`` is the java log's length."""
    folder = _streams_folder(scenario)
    to_close: list[Any] = []
    out_file = folder / "stdout" if stdout == "file" else None
    err_file = folder / "stderr" if stderr == "file" else None
    closed = closed_pipe() if "closed" in (stdout, stderr) else None
    if closed is not None:
        to_close.append(closed)

    def stream(kind: str, file: Path | None) -> Any:
        if kind == "file":
            assert file is not None
            handle = file.open("wb")
            to_close.append(handle)
            return handle
        if kind == "pipe":
            return subprocess.PIPE
        if kind == "closed":
            return closed
        return subprocess.DEVNULL

    try:
        process = start(
            argv,
            stdin=subprocess.DEVNULL if stdin == "null" else subprocess.PIPE,
            stdout=stream(stdout, out_file),
            stderr=stream(stderr, err_file),
            new_group=new_group,
        )
    finally:
        for item in to_close:
            if isinstance(item, int):
                os.close(item)
            else:
                item.close()
    return ProcessRun(
        process=process,
        stdout_file=out_file,
        stderr_file=err_file,
        stdin=process.stdin,
        group=new_group,
        pgid=group_of(process, new_group=new_group),
        fakes=scenario.fakes,
        after=after,
    )


def _read_lines(run: ProcessRun, count: int, timeout: float) -> str:
    """Read ``count`` lines of stdout in a thread, so a silent process cannot hold the step past ``timeout``."""
    pipe = run.process.stdout
    assert pipe is not None
    lines: list[bytes] = []

    def reader() -> None:
        for _ in range(count):
            line = pipe.readline()
            if not line:
                return
            lines.append(line)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        run.kill()  # ends the read with end of file
        thread.join()
        pipe.close()
        run.fail_with_output(f"{count} lines of stdout did not come within {timeout} seconds")
    pipe.close()  # the reader goes away
    return _text(b"".join(lines))


def run_as_process(
    scenario: Scenario,
    argv: Sequence[str],
    arrangement: Arrangement = "captured",
    *,
    text: str | None = None,
    lines: int = 0,
    timeout: float = WAIT_SECONDS,
) -> Outcome:
    """The ``I run ... as a process`` forms (T5's table); stdin is the null device unless ``input``."""
    after = prepare(scenario)
    stdout: Literal["file", "pipe", "closed", "null"] = "file"
    stderr: Literal["file", "closed"] = "file"
    if arrangement == "reader":
        stdout = "pipe"
    elif arrangement == "closed-stdout":
        stdout = "closed"
    elif arrangement == "closed-both":
        stdout, stderr = "closed", "closed"
    elif arrangement == "null-and-closed":
        stdout, stderr = "null", "closed"
    stdin: Literal["null", "pipe"] = "pipe" if arrangement == "input" else "null"
    run = launch(scenario, argv, stdin=stdin, stdout=stdout, stderr=stderr, after=after)
    if arrangement == "input":
        assert run.stdin is not None
        with contextlib.suppress(BrokenPipeError):  # it ended without reading; its outcome says so
            run.stdin.write(scenario.expand(text or "").encode("utf-8"))
        run.close()
    if arrangement == "reader":
        run.stdout_text = _read_lines(run, lines, timeout)
    scenario.outcome = run.finish(timeout=timeout)
    return scenario.outcome


def _release_file(scenario: Scenario, start_line: dict[str, Any]) -> Path:
    index = start_line.get("run")
    runs = scenario.java_runs
    checkpoint = runs[index].get("checkpoint") if isinstance(index, int) and index < len(runs) else None
    if not checkpoint:
        fail('this java run declares no checkpoint: "java begins a checkpoint after line ..." comes first')
    return Path(checkpoint["release_file"])


def release_when_waiting(
    scenario: Scenario,
    start_line: dict[str, Any],
    shown: Callable[[], bool],
    *,
    after: int,
    ended: Callable[[], bool],
    pump: Callable[[], None],
) -> bool:
    """Create the run's release file once ``shown()`` (tlaup holds the signal), or give none.

    No release when the fake logs its ``exit`` first (a raw run, where it got the signal itself) or the
    process has ended. ``pump`` is called between checks (the terminal reads its pty there). Returns
    whether the release was given.
    """
    fakes, pid = scenario.fakes, start_line["pid"]
    release = _release_file(scenario, start_line)
    deadline = time.monotonic() + LOG_WAIT_SECONDS
    while True:
        if shown():
            release.touch()
            return True
        if find_log(fakes, "java", lambda line: line.get("event") == "exit" and line.get("pid") == pid, after=after):
            return False
        if ended():
            return shown() and _touch(release)  # else the outcome shows what it printed
        if time.monotonic() >= deadline:
            fail(f"tlaup did not show the waiting line {WAITING_LINE!r} within {LOG_WAIT_SECONDS} seconds")
        pump()


def _touch(path: Path) -> bool:
    path.touch()
    return True


def start_and_signal(
    scenario: Scenario,
    argv: Sequence[str],
    signal_name: str,
    moment: Moment,
    *,
    group: bool = False,
    again_once: str | None = None,
    timeout: float = WAIT_SECONDS,
) -> Outcome:
    """The ``I start ... and send <signal> ...`` forms (T5's table); stdin a pipe held open to the end."""
    number = signal_number(signal_name)
    after = prepare(scenario)
    run = launch(scenario, argv, stdin="pipe", stdout="file", stderr="file", new_group=group, after=after)
    fakes = scenario.fakes
    try:
        if moment == "checkpoint":
            mark = wait_for_log(
                fakes,
                "java",
                lambda line: line.get("event") == "checkpoint",
                after=after,
                process=run.process,
                what="a checkpoint line",
            )
            start_line = wait_for_log(
                fakes,
                "java",
                lambda line: is_tool_start(line) and line.get("pid") == mark["pid"],
                after=after,
                what="the start line of the checkpointing run",
            )
        else:
            start_line = wait_for_log(
                fakes, "java", is_tool_start, after=after, process=run.process, what="a tool's start line"
            )
        run.send(number)
        if moment == "twice":
            wait_for_log(
                fakes,
                "java",
                lambda line: line.get("event") == "signal" and line.get("pid") == start_line["pid"],
                after=after,
                process=run.process,
                what="a signal line of the fake's own",
            )
            run.send(number)
        elif moment == "checkpoint" and again_once is not None:
            run.wait_for_stderr(again_once)
            run.send(number)
        elif moment == "checkpoint":
            release_when_waiting(
                scenario,
                start_line,
                lambda: WAITING_LINE in run.stderr_so_far(),
                after=after,
                ended=lambda: run.process.poll() is not None,
                pump=lambda: time.sleep(POLL_SECONDS),
            )
    except BaseException:
        run.kill()
        run.close()
        raise
    scenario.outcome = run.finish(timeout=timeout)
    return scenario.outcome
