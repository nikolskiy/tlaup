"""The launcher's two run functions and their steps, with the fake `java` as a real child (design 20 G3, 11 R1-R3).

Signals sent here go to the test process only, under `signals_held`, whose handlers are restored on the way out.
Every child is reaped by the launcher; `no_child_left` kills by process id any that is not, and fails the test.
"""

from __future__ import annotations

import contextlib
import dataclasses
import os
import signal
import sys
import threading
import time
from typing import TYPE_CHECKING, Any

import pytest

from tlaup.errors import InternalError, ToolStartError
from tlaup.java.launcher import (
    QUEUE_BOUND,
    ChildRun,
    JavaInvocation,
    ProcessOutcome,
    SignalName,
    Signals,
    run_passthrough,
    run_streaming,
    signals_held,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from tests.fakes.control import Fakes

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX signals and process groups")

TLC = "tlc2.TLC"
SANY = "tla2sany.SANY"


def invocation(java: Path, main_class: str = TLC, args: tuple[str, ...] = ()) -> JavaInvocation:
    return JavaInvocation(
        java=java, jvm_options=(), system_properties=(), classpath=(), main_class=main_class, args=args
    )


def never(_fd: int) -> bool:
    return False


def wait_until(condition: Callable[[], bool], what: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting until {what}"
        time.sleep(0.005)


def reader_threads() -> list[threading.Thread]:
    return [thread for thread in threading.enumerate() if thread.name.startswith("tlaup-reader-")]


class Lines:
    def __init__(self) -> None:
        self.stdout: list[str] = []
        self.stderr: list[str] = []

    def out(self, line: str) -> None:
        self.stdout.append(line)

    def err(self, line: str) -> None:
        self.stderr.append(line)


class Java:
    """The fake `java` on PATH with one scripted run, and what it logged."""

    def __init__(self, fakes: Fakes) -> None:
        self.fakes = fakes
        self.path = fakes.bin / "java"

    def script(self, main_class: str = TLC, **run: Any) -> JavaInvocation:
        self.fakes.script("java", {"runs": [{"main": main_class, **run}]})
        return invocation(self.path, main_class)

    def log(self) -> list[dict[str, Any]]:
        return self.fakes.log("java")

    def signals(self) -> list[str]:
        return [line["name"] for line in self.log() if line["event"] == "signal"]

    def start(self) -> dict[str, Any]:
        starts = [line for line in self.log() if line["event"] == "start"]
        assert len(starts) == 1, starts
        return starts[0]

    def started(self) -> bool:
        """The fake has installed its handlers and written its start line."""
        return any(line["event"] == "start" for line in self.log())

    def exited(self) -> bool:
        return any(line["event"] == "exit" for line in self.log())


@pytest.fixture
def java(fakes: Fakes) -> Iterator[Java]:
    fake = Java(fakes)
    yield fake
    left = []
    for line in fake.log():
        if line["event"] != "start":
            continue
        try:
            pid, _ = os.waitpid(line["pid"], os.WNOHANG)
        except ChildProcessError:
            continue  # reaped by the launcher
        left.append(line["pid"])
        if pid == 0:
            os.kill(line["pid"], signal.SIGKILL)
            os.waitpid(line["pid"], 0)
    assert not left, f"the launcher left these children unreaped: {left}"


def streaming(inv: JavaInvocation, signals: Signals, lines: Lines | None = None, **options: Any) -> ProcessOutcome:
    lines = lines or Lines()
    options.setdefault("reader_gone", never)
    return run_streaming(inv, on_stdout=lines.out, on_stderr=lines.err, signals=signals, **options)


@contextlib.contextmanager
def started(run: ChildRun) -> Iterator[ChildRun]:
    """A run driven a step at a time, stopped on the way out whatever happens."""
    assert run.may_start()
    run.spawn()
    try:
        run.attach()
        yield run
    finally:
        run.stop()


def turn_until(run: ChildRun, condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + 10
    while not condition():
        assert time.monotonic() < deadline, f"timed out turning until {what}"
        assert not run.turn(timeout=0.02), f"the child ended before {what}"


def finish(run: ChildRun) -> ProcessOutcome:
    deadline = time.monotonic() + 10
    while not run.turn(timeout=0.02):
        assert time.monotonic() < deadline, "the loop did not end"
    return run.outcome()


# ---------------------------------------------------------------------- output


def test_invalid_utf8_arrives_as_replacement_characters(java: Java, tmp_path: Path) -> None:
    replay = tmp_path / "invalid.out"
    replay.write_bytes(b"plain\n\xff\xfe bytes\r\nlast\n")
    lines = Lines()
    outcome = streaming(java.script(stdout=str(replay)), Signals(), lines)
    assert lines.stdout == ["plain\n", "�� bytes\r\n", "last\n"]
    assert outcome == ProcessOutcome(0, 0, None, ())


def test_many_lines_arrive_in_order_and_the_queue_stays_bounded(java: Java) -> None:
    count = QUEUE_BOUND * 10
    inv = java.script(generate_lines=count)
    seen: list[str] = []
    most = 0
    run: ChildRun

    def slow(line: str) -> None:
        nonlocal most
        if not seen:  # fall behind at the start, so the readers meet the bound
            wait_until(lambda: run.queued >= QUEUE_BOUND, "the queue is full")
        most = max(most, run.queued)
        seen.append(line)

    run = ChildRun(inv, Signals(), on_stdout=slow, on_stderr=lambda _: None, reader_gone=never)
    with started(run):
        outcome = finish(run)
    assert outcome.exit_code == 0
    assert most == QUEUE_BOUND
    assert seen == [f"line {i}\n" for i in range(1, count + 1)]


def test_a_callback_that_raises_stops_the_child_and_goes_on(java: Java) -> None:
    inv = java.script(generate_lines=QUEUE_BOUND * 10)
    seen: list[str] = []

    def fails_at_the_fifth(line: str) -> None:
        seen.append(line)
        if len(seen) == 5:
            raise BrokenPipeError

    began = time.monotonic()
    with pytest.raises(BrokenPipeError):
        run_streaming(inv, on_stdout=fails_at_the_fifth, on_stderr=lambda _: None, signals=Signals(), reader_gone=never)
    assert time.monotonic() - began < 5
    assert java.exited()
    assert java.signals() == ["SIGTERM"]
    wait_until(lambda: not reader_threads(), "the reader threads have ended", timeout=3)


def test_stderr_arrives_through_on_stderr_and_its_tail_is_kept(java: Java) -> None:
    errors = "".join(f"error {i}\n" for i in range(1, 61))
    lines = Lines()
    outcome = streaming(java.script(stderr={"text": errors}, stdout={"text": "out\n"}, exit=1), Signals(), lines)
    assert lines.stdout == ["out\n"]
    assert lines.stderr == errors.splitlines(keepends=True)
    assert outcome.stderr_tail == tuple(f"error {i}" for i in range(11, 61))
    assert (outcome.exit_code, outcome.tool_exit_code) == (1, 1)


def test_merged_stderr_arrives_through_on_stdout(java: Java) -> None:
    lines = Lines()
    inv = java.script(SANY, stderr={"text": "first\n"}, stdout={"text": "second\nthird\n"})
    outcome = streaming(inv, Signals(), lines, merge_stderr=True)
    assert lines.stdout == ["first\n", "second\n", "third\n"]
    assert lines.stderr == []
    assert outcome.stderr_tail == ()


# ---------------------------------------------------------------------- starting


def test_a_missing_executable_is_a_start_error(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-java"
    with pytest.raises(ToolStartError) as caught:
        streaming(invocation(missing), Signals())
    assert caught.value.exit_code == 5
    assert str(missing) in caught.value.message
    assert caught.value.message.startswith(f"{missing} could not be started: ")  # as locate words it (20)


def test_a_file_that_is_there_is_not_reported_as_not_found(tmp_path: Path) -> None:
    locked = tmp_path / "java"
    locked.write_text("#!/bin/sh\n", encoding="utf-8")
    locked.chmod(0o644)
    with pytest.raises(ToolStartError) as caught:
        streaming(invocation(locked), Signals())
    assert str(locked) in caught.value.message
    assert "permission denied" in caught.value.message.lower()
    assert "not found" not in caught.value.message.lower()


def test_a_missing_working_folder_is_named_as_what_could_not_be_used(java: Java, tmp_path: Path) -> None:
    folder = tmp_path / "no-such-folder"
    inv = dataclasses.replace(java.script(), cwd=folder)
    with pytest.raises(ToolStartError) as caught:
        streaming(inv, Signals())
    assert caught.value.message.startswith(f"{folder} could not be started: ")
    assert str(java.path) not in caught.value.message
    assert java.log() == []


def test_a_childrun_refuses_a_clock_of_its_own(java: Java) -> None:
    signals = Signals(clock=lambda: 0.0)
    with pytest.raises(InternalError):
        ChildRun(java.script(), signals, clock=time.monotonic)
    ChildRun(java.script(), signals, clock=signals.clock)  # the same clock is accepted


def test_a_signal_that_came_first_starts_nothing(java: Java) -> None:
    inv = java.script(generate_lines=1)
    signals = Signals()
    signals.first = "term"
    outcome = streaming(inv, signals)
    assert java.log() == []
    assert outcome == ProcessOutcome(143, None, "term", ())


def test_the_tools_own_code_passes_through(java: Java) -> None:
    assert streaming(java.script(exit=3), Signals()).exit_code == 3


def test_a_child_killed_by_a_signal_tlaup_did_not_send_gives_128_plus_n(java: Java) -> None:
    inv = java.script(generate_lines=1, hang_after_line=1)

    def kill_it(_line: str) -> None:
        os.kill(java.start()["pid"], signal.SIGKILL)

    outcome = run_streaming(inv, on_stdout=kill_it, on_stderr=lambda _: None, signals=Signals(), reader_gone=never)
    assert outcome == ProcessOutcome(137, -9, None, ())


# ---------------------------------------------------------------------- pass_fds

FD_REPORTER = """#!{python}
import os, sys
try:
    os.fstat(int(sys.argv[-1]))
    print("open")
except OSError:
    print("closed")
"""


def fd_reporter(tmp_path: Path) -> Path:
    script = tmp_path / "fd-java"
    script.write_text(FD_REPORTER.format(python=sys.executable), encoding="utf-8")
    script.chmod(0o755)
    return script


def is_open(fd: int) -> bool:
    try:
        os.fstat(fd)
    except OSError:
        return False
    return True


@pytest.fixture
def passed_fd() -> Iterator[int]:
    read, write = os.pipe()
    fd = os.dup(read)  # the duplicate a caller makes for the child
    yield fd
    for other in (read, write, fd):
        with contextlib.suppress(OSError):
            os.close(other)


def test_a_passed_descriptor_is_open_in_the_child_and_closed_in_the_parent(tmp_path: Path, passed_fd: int) -> None:
    lines = Lines()
    inv = invocation(fd_reporter(tmp_path), args=(str(passed_fd),))
    outcome = streaming(inv, Signals(), lines, pass_fds=(passed_fd,))
    assert lines.stdout == ["open\n"]
    assert outcome.exit_code == 0
    assert not is_open(passed_fd)


def test_without_pass_fds_the_child_does_not_inherit_it(tmp_path: Path, passed_fd: int) -> None:
    lines = Lines()
    streaming(invocation(fd_reporter(tmp_path), args=(str(passed_fd),)), Signals(), lines)
    assert lines.stdout == ["closed\n"]
    assert is_open(passed_fd)


def test_passed_descriptors_are_closed_when_nothing_starts(tmp_path: Path, passed_fd: int) -> None:
    signals = Signals()
    signals.first = "int"
    streaming(invocation(fd_reporter(tmp_path)), signals, pass_fds=(passed_fd,))
    assert not is_open(passed_fd)


def test_passed_descriptors_are_closed_once(tmp_path: Path, passed_fd: int) -> None:
    signals = Signals()
    signals.first = "int"
    run = ChildRun(invocation(fd_reporter(tmp_path)), signals, pass_fds=(passed_fd,))
    assert not run.may_start()
    reused = os.open(os.devnull, os.O_RDONLY)  # the freed number, now someone else's
    try:
        assert reused == passed_fd
        assert not run.may_start()
        assert is_open(reused)
    finally:
        os.close(reused)


def test_passed_descriptors_are_closed_when_the_start_fails(tmp_path: Path, passed_fd: int) -> None:
    with pytest.raises(ToolStartError):
        streaming(invocation(tmp_path / "missing"), Signals(), pass_fds=(passed_fd,))
    assert not is_open(passed_fd)


# ---------------------------------------------------------------------- signals in a run


def test_a_child_that_ignores_sigterm_is_killed_when_the_grace_period_runs_out(java: Java) -> None:
    inv = java.script(generate_lines=1, hang_after_line=1, on_sigterm="ignore")
    with signals_held() as signals:

        def stop_it(_line: str) -> None:
            os.kill(os.getpid(), signal.SIGTERM)

        outcome = run_streaming(
            inv, on_stdout=stop_it, on_stderr=lambda _: None, signals=signals, grace_seconds=0.5, reader_gone=never
        )
    assert outcome == ProcessOutcome(143, -9, "term", ())
    assert java.signals() == ["SIGTERM"]


class Checkpoint:
    """Stands for the runner: the first line is 2195, the second 2196 (D52)."""

    def __init__(self, signals: Signals, *, at_first: Callable[[], None]) -> None:
        self.signals = signals
        self.at_first = at_first
        self.lines: list[str] = []
        self.held: list[SignalName] = []
        self.signals_at_second: list[str] | None = None
        self.java: Java | None = None

    def on_stdout(self, line: str) -> None:
        self.lines.append(line)
        if len(self.lines) == 1:
            self.signals.checkpoint_started()
            self.at_first()
        elif len(self.lines) == 2:
            assert self.java is not None
            self.signals_at_second = self.java.signals()
            self.signals.checkpoint_written()


def checkpoint_script(java: Java, **extra: Any) -> JavaInvocation:
    # The pause outlasts the look at the reader, which comes at most every TURN_SECONDS.
    return java.script(generate_lines=2, line_delay_ms=500, hang_after_line=2, **extra)


@pytest.mark.parametrize(("number", "name"), [(signal.SIGINT, "int"), (signal.SIGTERM, "term")])
def test_a_first_signal_during_a_checkpoint_waits_for_it(java: Java, number: int, name: SignalName) -> None:
    inv = checkpoint_script(java)
    with signals_held() as signals:
        mark = Checkpoint(signals, at_first=lambda: os.kill(os.getpid(), number))
        mark.java = java
        outcome = run_streaming(
            inv,
            on_stdout=mark.on_stdout,
            on_stderr=lambda _: None,
            signals=signals,
            on_held=mark.held.append,
            reader_gone=never,
        )
    assert mark.signals_at_second == []  # nothing was sent while the checkpoint was written
    assert java.signals() == ["SIGTERM"]
    assert mark.held == [name]
    assert outcome == ProcessOutcome({"int": 130, "term": 143}[name], 143, name, ())


def test_a_second_signal_during_a_checkpoint_kills_at_once(java: Java) -> None:
    inv = checkpoint_script(java)

    def twice() -> None:
        os.kill(os.getpid(), signal.SIGINT)
        os.kill(os.getpid(), signal.SIGINT)

    with signals_held() as signals:
        mark = Checkpoint(signals, at_first=twice)
        mark.java = java
        outcome = run_streaming(
            inv, on_stdout=mark.on_stdout, on_stderr=lambda _: None, signals=signals, reader_gone=never
        )
    assert mark.lines == ["line 1\n"]
    assert java.signals() == []  # SIGKILL leaves no note
    assert outcome == ProcessOutcome(130, -9, "int", ())
    assert not signals.held


def test_the_grace_period_runs_from_the_written_checkpoint(java: Java) -> None:
    inv = checkpoint_script(java, on_sigterm="ignore")
    now = [1000.0]

    def interrupt_and_wait_long() -> None:
        os.kill(os.getpid(), signal.SIGINT)
        now[0] += 100  # far past the grace period while the signal is held

    with signals_held(clock=lambda: now[0]) as signals:
        mark = Checkpoint(signals, at_first=interrupt_and_wait_long)
        mark.java = java
        run = ChildRun(inv, signals, on_stdout=mark.on_stdout, grace_seconds=5, reader_gone=never)
        with started(run):
            turn_until(run, lambda: len(mark.lines) == 2, "the checkpoint is written")
            assert signals.first_at == 1100.0
            wait_until(lambda: java.signals() == ["SIGTERM"], "the fake got SIGTERM")
            for _ in range(5):
                assert not run.turn(timeout=0.01)
            assert run.alive()
            now[0] += 5
            outcome = finish(run)
    assert outcome == ProcessOutcome(130, -9, "int", ())


def test_sigquit_reaches_the_jvm_of_a_parsed_run_and_changes_nothing(java: Java) -> None:
    inv = java.script(generate_lines=2, line_delay_ms=1000)

    def quit_at_the_first(line: str) -> None:
        if line == "line 1\n":
            os.kill(os.getpid(), signal.SIGQUIT)
            wait_until(lambda: java.signals() == ["SIGQUIT"], "the fake noted SIGQUIT")

    with signals_held() as signals:
        outcome = run_streaming(
            inv, on_stdout=quit_at_the_first, on_stderr=lambda _: None, signals=signals, reader_gone=never
        )
        assert (signals.first, signals.count, signals.held) == (None, 0, False)
    assert outcome == ProcessOutcome(0, 0, None, ())


def test_sigquit_is_not_sent_on_in_a_passthrough_run(java: Java) -> None:
    inv = java.script(generate_lines=1, line_delay_ms=1000)
    with signals_held() as signals:
        run = ChildRun(inv, signals, passthrough=True)
        with started(run):
            wait_until(java.started, "the fake has started")
            os.kill(os.getpid(), signal.SIGQUIT)
            outcome = finish(run)
        assert (signals.first, signals.count) == (None, 0)
    assert java.signals() == []
    assert outcome == ProcessOutcome(0, 0, None, ())


# ---------------------------------------------------------------------- process groups (D60)


def test_a_parsed_run_has_a_process_group_of_its_own(java: Java) -> None:
    streaming(java.script(), Signals())
    start = java.start()
    assert start["pgid"] == start["pid"]
    assert start["pgid"] != os.getpgrp()


def test_a_merged_run_stays_in_tlaups_group(java: Java) -> None:
    streaming(java.script(SANY), Signals(), merge_stderr=True)
    assert java.start()["pgid"] == os.getpgrp()


def test_a_passthrough_run_stays_in_tlaups_group(java: Java) -> None:
    run_passthrough(java.script(), signals=Signals(), forward_interrupt=True)
    assert java.start()["pgid"] == os.getpgrp()


# ---------------------------------------------------------------------- a closed pipe (D58, FC9)


class Reader:
    """`reader_gone` as the test says."""

    def __init__(self) -> None:
        self.gone = False

    def __call__(self, fd: int) -> bool:
        assert fd == 1
        return self.gone


def test_a_closed_pipe_then_a_signal_gives_141_and_a_kill(java: Java) -> None:
    inv = java.script(generate_lines=1, hang_after_line=1, on_sigterm="ignore")
    reader = Reader()
    with signals_held() as signals:
        run = ChildRun(inv, signals, on_stdout=lambda _: setattr(reader, "gone", True), reader_gone=reader)
        with started(run):
            turn_until(run, lambda: java.signals() == ["SIGTERM"], "the closed pipe stopped the child")
            os.kill(os.getpid(), signal.SIGINT)  # a second stop: kill() at once
            outcome = finish(run)
        assert signals.first is None
    assert outcome == ProcessOutcome(141, -9, None, (), stopped_for_closed_pipe=True)


def test_a_signal_then_a_closed_pipe_gives_the_signals_code(java: Java) -> None:
    inv = java.script(generate_lines=1, hang_after_line=1, on_sigterm="ignore")
    reader = Reader()
    now = [0.0]
    with signals_held(clock=lambda: now[0]) as signals:
        run = ChildRun(inv, signals, on_stdout=lambda _: os.kill(os.getpid(), signal.SIGINT), reader_gone=reader)
        with started(run):
            turn_until(run, lambda: java.signals() == ["SIGTERM"], "the signal stopped the child")
            reader.gone = True
            turn_until(run, lambda: run.closed_pipe_seen, "the closed pipe was seen")
            assert run.alive()  # the closed pipe after a signal is no second stop
            now[0] += 10
            outcome = finish(run)
    assert outcome == ProcessOutcome(130, -9, "int", (), stopped_for_closed_pipe=True)


def test_a_closed_pipe_does_not_wait_for_a_checkpoint(java: Java) -> None:
    inv = checkpoint_script(java)
    reader = Reader()

    def held_then_gone() -> None:
        os.kill(os.getpid(), signal.SIGINT)
        reader.gone = True

    with signals_held() as signals:
        mark = Checkpoint(signals, at_first=held_then_gone)
        mark.java = java
        run = ChildRun(inv, signals, on_stdout=mark.on_stdout, reader_gone=reader)
        with started(run):
            outcome = finish(run)
    assert mark.lines == ["line 1\n"]  # stopped before the checkpoint was written
    assert java.signals() == ["SIGTERM"]
    assert outcome == ProcessOutcome(130, 143, "int", (), stopped_for_closed_pipe=True)


def test_a_closed_pipe_stops_a_parsed_run_with_141(java: Java) -> None:
    inv = java.script(generate_lines=1, hang_after_line=1)
    outcome = streaming(inv, Signals(), reader_gone=lambda _: java.started())
    assert java.signals() == ["SIGTERM"]
    assert outcome == ProcessOutcome(141, 143, None, (), stopped_for_closed_pipe=True)


# ---------------------------------------------------------------------- run_passthrough


def test_passthrough_runs_to_its_end_when_the_closed_pipe_cannot_be_seen(java: Java) -> None:
    inv = java.script(generate_lines=3, exit=4)
    outcome = run_passthrough(
        inv, signals=Signals(), forward_interrupt=True, stop_when_reader_gone=True, reader_gone=never
    )
    assert java.signals() == []
    assert outcome == ProcessOutcome(4, 4, None, ())


def test_passthrough_stops_for_a_closed_pipe_when_asked(java: Java) -> None:
    inv = java.script(generate_lines=1, hang_after_line=1)
    outcome = run_passthrough(
        inv, signals=Signals(), forward_interrupt=True, stop_when_reader_gone=True, reader_gone=lambda _: java.started()
    )
    assert java.signals() == ["SIGTERM"]
    assert outcome == ProcessOutcome(141, 143, None, (), stopped_for_closed_pipe=True)


@pytest.mark.parametrize(("leave", "forward"), [(True, True), (False, False)])
def test_passthrough_refuses_a_forward_interrupt_that_disagrees_with_the_block(
    java: Java, *, leave: bool, forward: bool
) -> None:
    inv = java.script()
    with pytest.raises(InternalError):
        run_passthrough(inv, signals=Signals(leave_interrupt=leave), forward_interrupt=forward)
    assert java.log() == []


def test_streaming_refuses_a_block_that_leaves_sigint_to_the_child(java: Java) -> None:
    inv = java.script()
    with pytest.raises(InternalError):
        streaming(inv, Signals(leave_interrupt=True))
    assert java.log() == []
