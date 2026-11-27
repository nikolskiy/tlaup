"""The run functions' frame: run_tlc and run_tlc_raw with the fake ``java`` and a CollectingReporter (package 37).

Design 11 (the frame, R1 to R3, R6 "Unit, the frame"), 22 O1 (the order of the reporter calls), 20 G3 (the two
signals at an exact moment, the waiting line). The fake ``java`` is a real child of the test process; every signal is
sent to the test process itself from a reporter callback, on the main thread, under the frame's ``signals_held``,
which restores pytest's handlers afterwards. Every run folder has the injected clock. ``no_child_left`` kills by
process id any fake that is still alive at the end and fails the test.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import select
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests.clock import FakeClock
from tests.fakes._fakelib import GOLDEN_DIR
from tests.unit.tlc.invocations import make_invocation
from tlaup.errors import ToolStartError
from tlaup.java.launcher import TAIL_LINES
from tlaup.java.locate import JavaRuntime, JavaTool
from tlaup.reporters.collecting import CollectingReporter
from tlaup.tlc.command import build_tlc_command
from tlaup.tlc.invocation import TlcRequest
from tlaup.tlc.rundirs import Kept, RunStart, complete_checkpoint, kept_note, list_entries, reminder, sweep
from tlaup.tlc.runner import RunOutcome, run_tlc, run_tlc_raw, waiting_line
from tlaup_parse import CheckpointStarted, CheckpointWritten, RunResult, Status, TlcParser, Verdict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tests.conftest import Isolated
    from tests.fakes.control import Fakes
    from tlaup.java.launcher import JavaInvocation, SignalName
    from tlaup.paths import AppPaths
    from tlaup.reporters.base import RunInfo
    from tlaup.tlc.invocation import TlcInvocation
    from tlaup_parse import Event

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX signals sent to the test process (D15)")

START = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
ROLLING = "tlc/2026.11.15.002146"
VIOLATION = f"{ROLLING}/violation.out"
SUCCESS = f"{ROLLING}/success.out"
CHECKPOINT_RUN = f"{ROLLING}/checkpoint-run.out"  # 2195 on lines 37 to 39, 2196 on lines 40 to 42
CHECKPOINT_RECOVER = f"{ROLLING}/checkpoint-recover.out"  # 2197 and 2198
INVALID_UTF8 = "synthetic/invalid-utf8.out"
END_OF_2195 = 39
START_OF_2196 = 40
END_OF_2196 = 42
CHECKPOINT_FILES = ["queue.chkpt", "vars.chkpt"]
TIMESTAMPED = "20261115-100000"  # stands for TLC's timestamped folder in a kept folder made by the test
FP, SEED = 58, 8556987057680880581  # what make_invocation passes


class ReporterError(Exception):
    """An error of the reporter's own."""


def wait_until(condition: Callable[[], bool], what: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting until {what}"
        time.sleep(0.005)


# ---------------------------------------------------------------------- the fake, the reporter, the invocation


class Java:
    """The fake ``java`` on PATH with one scripted ``tlc2.TLC`` run, and what it logged."""

    def __init__(self, fakes: Fakes) -> None:
        self.fakes = fakes
        self.path = fakes.bin / "java"

    def script(self, **run: Any) -> None:
        self.fakes.script("java", {"runs": [{"main": "tlc2.TLC", **run}]})

    def log(self) -> list[dict[str, Any]]:
        return self.fakes.log("java")

    def events(self, event: str) -> list[dict[str, Any]]:
        return [line for line in self.log() if line["event"] == event]

    def signals(self) -> list[str]:
        return [line["name"] for line in self.events("signal")]

    def start(self) -> dict[str, Any]:
        starts = self.events("start")
        assert len(starts) == 1, starts
        return starts[0]

    def exited(self) -> bool:
        return bool(self.events("exit"))

    def began_checkpoint(self) -> bool:
        return bool(self.events("checkpoint"))


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
def java(fakes: Fakes) -> Iterator[Java]:
    fake = Java(fakes)
    yield fake
    left = []
    for line in fake.events("start"):
        pid = line["pid"]
        try:
            reaped, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:  # reaped by the launcher, or not our child (the closed-pipe helper's)
            if alive(pid) and not fake.exited():
                left.append(pid)
                os.kill(pid, signal.SIGKILL)
            continue
        left.append(pid)
        if reaped == 0:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
    assert not left, f"these fakes were left behind: {left}"


class Reporter(CollectingReporter):
    """A CollectingReporter whose callbacks can act: send a signal, raise, or fail in ``close``."""

    def __init__(self, calls: list[str]) -> None:
        super().__init__(calls)
        self.on_start: Callable[[], None] | None = None
        self.on_handle: Callable[[Event, RunResult], None] | None = None
        self.on_finish: Callable[[], None] | None = None
        self.close_error: OSError | None = None
        self.finished = False
        self.closed = 0

    def start(self, run: RunInfo) -> None:
        super().start(run)
        if self.on_start is not None:
            self.on_start()

    def handle(self, event: Event, result: RunResult) -> None:
        super().handle(event, result)
        if self.on_handle is not None:
            self.on_handle(event, result)

    def finish(self, outcome: RunOutcome) -> None:
        super().finish(outcome)
        if self.on_finish is not None:
            self.on_finish()
        self.finished = True  # the callback returned

    def close(self) -> None:
        self.closed += 1
        if self.closed == 1 and self.close_error is not None:
            self.write_error = self.close_error
        super().close()


@dataclasses.dataclass
class Run:
    """One test's run: the invocation, the shared list of calls and notes, the reporter, the paths."""

    inv: TlcInvocation
    java_inv: JavaInvocation
    calls: list[str]
    reporter: Reporter
    paths: AppPaths
    clock: FakeClock

    def note(self, line: str) -> None:
        self.calls.append(f"note: {line}")

    def parsed(self) -> RunOutcome:
        return run_tlc(self.inv, self.java_inv, self.reporter, paths=self.paths, now=self.clock.now, notice=self.note)

    def raw(self) -> RunOutcome:
        return run_tlc_raw(self.inv, self.java_inv, paths=self.paths, now=self.clock.now, notice=self.note)

    @property
    def folder(self) -> Path:
        return self.paths.runs / self.inv.run_id

    def notes(self) -> list[str]:
        return [entry for entry in self.calls if entry.startswith("note: ")]


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(START)


@pytest.fixture
def make_run(isolated: Isolated, java: Java, clock: FakeClock) -> Callable[..., Run]:
    (isolated.work / "Spec.tla").write_text("---- MODULE Spec ----\n====\n", encoding="utf-8")

    def make(*extra: str, keep: bool = False, raw: bool = False, java_path: Path | None = None) -> Run:
        request = TlcRequest(spec="Spec.tla", keep=keep, raw=raw, extra_args=extra)
        runtime = JavaRuntime(JavaTool(java_path or java.path, "PATH"), "25.0.5", 25, ())
        inv = make_invocation(isolated.work, isolated.paths.runs, request=request, extra_args=extra, java=runtime)
        calls: list[str] = []
        return Run(inv, build_tlc_command(inv), calls, Reporter(calls), isolated.paths, clock)

    return make


def nothing_left(paths: AppPaths) -> bool:
    """No run folder and no lock file under ``paths.runs``."""
    return list_entries(paths.runs) == [] and not any(paths.runs.glob("*.lock"))


def expected_events(name: str) -> list[str]:
    """The event types the parser gives for a capture, fed as the launcher hands lines on."""
    parser = TlcParser()
    events: list[Event] = []
    for line in (GOLDEN_DIR / name).read_bytes().splitlines(keepends=True):
        events.extend(parser.feed(line.decode("utf-8", errors="replace")))
    events.extend(parser.close())
    return [type(event).__name__ for event in events]


def send(number: int) -> Callable[..., None]:
    def sender(*_args: object) -> None:
        os.kill(os.getpid(), number)  # the handler has run when this returns

    return sender


def once(action: Callable[..., None]) -> Callable[..., None]:
    done = False

    def first(*args: object) -> None:
        nonlocal done
        if not done:
            done = True
            action(*args)

    return first


def without_stderr(calls: list[str]) -> list[str]:
    return [call for call in calls if call != "stderr_line"]


# ---------------------------------------------------------------------- the frame and the reporter (22 O1)


def test_a_violation_gives_its_events_in_order_and_the_calls_in_order(make_run: Callable[..., Run], java: Java) -> None:
    java.script(stdout=VIOLATION, stderr={"text": "a line on stderr\n"}, exit=12)
    run = make_run()
    outcome = run.parsed()
    assert [type(event).__name__ for event in run.reporter.events] == expected_events(VIOLATION)
    assert run.reporter.stderr_lines == ["a line on stderr\n"]
    events = len(run.reporter.events)
    assert without_stderr(run.calls) == ["start", *["handle"] * events, "finish", "close"]
    assert run.reporter.run is not None
    assert run.reporter.run.command == (str(java.path), *java.start()["args"])
    assert run.reporter.outcome is outcome
    assert (outcome.exit_code, outcome.tool_exit_code, outcome.stopped_by) == (12, 12, None)
    assert outcome.result is not None
    assert outcome.result.status is Status.FAILURE
    assert outcome.result.verdict is Verdict.ERRORS
    assert outcome.stderr_tail == ("a line on stderr",)


def test_the_run_info_comes_from_the_invocation(make_run: Callable[..., Run], java: Java) -> None:
    java.script(stdout=SUCCESS)
    run = make_run()
    run.parsed()
    info = run.reporter.run
    assert info is not None
    inv = run.inv
    assert (info.tool, info.spec, info.cfg, info.build, info.java) == ("tlc", inv.spec, inv.cfg, inv.build, inv.java)
    assert (info.workers, info.project_root, info.override_classes) == ("1", None, ())
    assert info.cwd == inv.cwd
    assert info.command == tuple(run.java_inv.argv())


@pytest.mark.parametrize(("extra", "asked"), [((), False), (("-help",), True), (("-workers", "2"), False)])
def test_the_outcome_says_whether_tlc_was_asked_for_its_help(
    make_run: Callable[..., Run], java: Java, extra: tuple[str, ...], asked: bool
) -> None:
    java.script(stdout=SUCCESS, exit=1 if asked else 0)
    outcome = make_run(*extra).parsed()
    assert outcome.asked_for_help is asked


def test_finish_and_close_come_after_an_interrupt(make_run: Callable[..., Run], java: Java) -> None:
    java.script(stdout=SUCCESS, hang_after_line=3)
    run = make_run()
    run.reporter.on_handle = once(send(signal.SIGINT))
    outcome = run.parsed()
    assert run.calls[-2:] == ["finish", "close"]
    assert run.reporter.outcome is outcome
    assert outcome.result is not None
    assert outcome.result.status is Status.INTERRUPTED
    assert outcome.result.verdict is Verdict.INCOMPLETE
    assert (outcome.exit_code, outcome.stopped_by) == (130, "int")
    assert java.signals() == ["SIGTERM"]


def test_a_java_that_cannot_be_started_gives_start_close_and_the_start_error(
    make_run: Callable[..., Run], tmp_path: Path
) -> None:
    run = make_run(java_path=tmp_path / "no-such-java")
    with pytest.raises(ToolStartError, match="could not be started"):
        run.parsed()
    assert run.calls == ["start", "close"]
    assert nothing_left(run.paths)


def test_a_write_error_held_by_close_is_raised_after_a_run_that_succeeded(
    make_run: Callable[..., Run], java: Java
) -> None:
    java.script(stdout=SUCCESS)
    run = make_run()
    broken = BrokenPipeError()
    run.reporter.close_error = broken
    with pytest.raises(BrokenPipeError) as raised:
        run.parsed()
    assert raised.value is broken
    assert run.calls[-2:] == ["finish", "close"]
    assert getattr(broken, "__notes__", []) == []
    assert nothing_left(run.paths)


def test_the_error_of_the_middle_comes_out_and_not_the_write_error(make_run: Callable[..., Run], java: Java) -> None:
    java.script(stdout=SUCCESS)
    run = make_run()
    run.reporter.close_error = BrokenPipeError()

    def fail(*_args: object) -> None:
        raise ReporterError

    run.reporter.on_handle = fail
    with pytest.raises(ReporterError):
        run.parsed()
    assert "close" in run.calls
    assert "finish" not in run.calls


# ---------------------------------------------------------------------- settle on every way out, and the note (R6)


@pytest.mark.parametrize(("capture", "code"), [(SUCCESS, 0), (VIOLATION, 12)])
def test_a_run_that_ends_by_itself_leaves_no_folder_and_no_lock_file(
    make_run: Callable[..., Run], java: Java, capture: str, code: int
) -> None:
    java.script(stdout=capture, exit=code)
    run = make_run(keep=True)
    outcome = run.parsed()
    assert outcome.exit_code == code
    assert (outcome.kept, outcome.dropped_checkpoint) == (None, None)
    assert nothing_left(run.paths)


def kept_folder(run: Run) -> Path:
    states = complete_checkpoint(run.folder)
    assert states is not None, "the run folder holds no complete checkpoint"
    return states


def test_a_failing_reporter_keeps_the_checkpoint_and_the_note_travels_on_the_error(
    make_run: Callable[..., Run], java: Java
) -> None:
    java.script(stdout=SUCCESS, write_into_metadir=CHECKPOINT_FILES, hang_after_line=3)
    run = make_run(keep=True)

    def fail(*_args: object) -> None:
        raise ReporterError

    run.reporter.on_handle = fail
    with pytest.raises(ReporterError) as raised:
        run.parsed()
    assert run.calls[-1] == "close"
    states = kept_folder(run)
    notes = raised.value.__notes__
    assert len(notes) == 2
    assert notes[0].startswith("Checkpoint kept (")
    assert "tlaup failed after " in notes[0]
    assert notes[0].endswith(f"): {run.folder}")
    assert notes[1].startswith("Resume with: tlaup tlc ")
    assert notes[1].endswith(f"-recover {states}")
    assert json.loads((run.folder / "run.json").read_text(encoding="utf-8"))["reason"] == "tlaup failed"
    assert java.exited()


def test_a_failing_reporter_without_a_checkpoint_leaves_no_note_and_no_folder(
    make_run: Callable[..., Run], java: Java
) -> None:
    java.script(stdout=SUCCESS, hang_after_line=3)
    run = make_run(keep=True)

    def fail(*_args: object) -> None:
        raise ReporterError

    run.reporter.on_handle = fail
    with pytest.raises(ReporterError) as raised:
        run.parsed()
    assert getattr(raised.value, "__notes__", []) == []
    assert run.calls[-1] == "close"
    assert nothing_left(run.paths)


def interrupted_with_checkpoint(make_run: Callable[..., Run], java: Java, *, keep: bool) -> Run:
    java.script(stdout=SUCCESS, write_into_metadir=CHECKPOINT_FILES, hang_after_line=3)
    run = make_run(keep=keep)
    run.reporter.on_handle = once(send(signal.SIGINT))
    return run


def test_a_write_error_after_a_kept_run_carries_the_note(make_run: Callable[..., Run], java: Java) -> None:
    run = interrupted_with_checkpoint(make_run, java, keep=True)
    run.reporter.close_error = BrokenPipeError()
    with pytest.raises(BrokenPipeError) as raised:
        run.parsed()
    outcome = run.reporter.outcome
    assert outcome is not None
    assert outcome.kept is not None
    assert raised.value.__notes__ == list(kept_note(outcome.kept))
    kept_folder(run)


def test_a_kept_run_returns_its_kept_folder(make_run: Callable[..., Run], java: Java) -> None:
    run = interrupted_with_checkpoint(make_run, java, keep=True)
    outcome = run.parsed()
    assert isinstance(outcome.kept, Kept)
    assert outcome.kept.path == run.folder
    assert outcome.kept.reason == "interrupted"
    assert outcome.run_folder_kept == outcome.kept.path
    assert outcome.resume_command == outcome.kept.resume_command
    assert outcome.resume_command is not None
    assert outcome.dropped_checkpoint is None
    assert outcome.kept.checkpoint_dir == kept_folder(run)
    assert run.notes() == []  # the note is the command's, for a run that returns


def test_a_run_that_did_not_ask_keeps_nothing_and_says_why(make_run: Callable[..., Run], java: Java) -> None:
    run = interrupted_with_checkpoint(make_run, java, keep=False)
    outcome = run.parsed()
    assert (outcome.kept, outcome.run_folder_kept, outcome.resume_command) == (None, None, None)
    assert outcome.dropped_checkpoint == "not-asked"
    assert nothing_left(run.paths)


def make_kept(
    paths: AppPaths, clock: FakeClock, run_id: str, *, fp: int | None = None, seed: int | None = None
) -> Path:
    """A kept folder, made with 35's steps; returns its timestamped folder."""
    start = RunStart(paths.runs, clock.now, run_id=run_id, info={"keep": True, "fp": fp, "seed": seed}, wait=0)
    start.create_lock_file()
    start.take_lock()
    start.make_folder()
    start.write_run_json()
    states = start.path / TIMESTAMPED
    states.mkdir()
    for name in CHECKPOINT_FILES:
        (states / name).write_bytes(b"checkpoint")
    folder = start.entered()
    assert folder.settle(None).kept is not None
    folder.end_own()
    folder.release_own()
    return states


def test_the_reminder_comes_once_before_start(make_run: Callable[..., Run], java: Java, clock: FakeClock) -> None:
    java.script(stdout=SUCCESS)
    run = make_run()
    make_kept(run.paths, clock, "old1")
    make_kept(run.paths, clock, "old2")
    summary = sweep(run.paths, clock.now)
    assert summary.count == 2
    run.parsed()
    assert run.notes() == [f"note: {reminder(summary)}"]
    assert run.calls.index(f"note: {reminder(summary)}") < run.calls.index("start")


def test_no_kept_folder_no_reminder(make_run: Callable[..., Run], java: Java) -> None:
    java.script(stdout=SUCCESS)
    run = make_run()
    run.parsed()
    assert run.notes() == []


@pytest.mark.parametrize(("extra", "approximate"), [((), False), (("-fp", "3"), True)])
def test_a_resumed_run_counts_exactly_only_with_the_recorded_fp_and_seed(
    make_run: Callable[..., Run], java: Java, clock: FakeClock, extra: tuple[str, ...], approximate: bool
) -> None:
    java.script(stdout=CHECKPOINT_RECOVER)
    probe = make_run()
    states = make_kept(probe.paths, clock, "old", fp=FP, seed=SEED)
    run = make_run(*extra, "-recover", str(states))
    outcome = run.parsed()
    assert outcome.result is not None
    assert outcome.result.resumed
    assert outcome.result.counts_approximate is approximate
    assert outcome.exit_code == 0


# ---------------------------------------------------------------------- signals at an exact moment (20 G3)


def test_a_sigterm_before_the_child_starts_nothing(make_run: Callable[..., Run], java: Java) -> None:
    java.script(stdout=SUCCESS)
    run = make_run()
    run.reporter.on_start = send(signal.SIGTERM)
    outcome = run.parsed()
    assert java.log() == []
    assert (outcome.exit_code, outcome.tool_exit_code, outcome.stopped_by) == (143, None, "term")
    assert run.calls[-2:] == ["finish", "close"]
    assert outcome.result is not None
    assert outcome.result.status is Status.INTERRUPTED
    assert nothing_left(run.paths)


def test_a_second_sigint_during_the_summary_changes_nothing(make_run: Callable[..., Run], java: Java) -> None:
    java.script(stdout=SUCCESS, hang_after_line=3)
    run = make_run()
    run.reporter.on_handle = once(send(signal.SIGINT))
    run.reporter.on_finish = send(signal.SIGINT)
    outcome = run.parsed()
    assert run.reporter.finished
    assert run.calls[-2:] == ["finish", "close"]
    assert outcome.exit_code == 130
    assert java.exited()
    assert java.signals() == ["SIGTERM"]


# ---------------------------------------------------------------------- the checkpoint deferral (D52, R2)


@dataclasses.dataclass
class Deferral:
    run: Run
    written_handled: bool = False
    started_at: int | None = None  # the index in the shared list of the handle of 2195's event


def deferral(
    make_run: Callable[..., Run], java: Java, number: int, *, times: int, release: Path, give_release: bool
) -> Deferral:
    """The fake prints 2195, begins its checkpoint and waits for ``release``, then commits, prints 2196 and hangs.

    The reporter sends the signals from ``handle`` of 2195, once the fake has begun its checkpoint, and then gives
    the release when ``give_release`` is set. A first signal sent on at once would reach the fake while it waits,
    before it commits: it would never print 2196 and nothing would be kept.
    """
    java.script(
        stdout=CHECKPOINT_RUN,
        checkpoint={"begin_after_line": END_OF_2195, "commit_before_line": START_OF_2196, "release_file": str(release)},
        hang_after_line=END_OF_2196,
    )
    state = Deferral(make_run(keep=True))

    def on_handle(event: Event, _result: RunResult) -> None:
        if isinstance(event, CheckpointStarted):
            state.started_at = len(state.run.calls) - 1
            wait_until(java.began_checkpoint, "the fake has begun its checkpoint")
            for _ in range(times):
                os.kill(os.getpid(), number)
            if give_release:
                release.write_text("", encoding="utf-8")
        elif isinstance(event, CheckpointWritten):
            state.written_handled = True

    state.run.reporter.on_handle = on_handle
    return state


@pytest.mark.parametrize(("number", "name", "code"), [(signal.SIGINT, "int", 130), (signal.SIGTERM, "term", 143)])
def test_a_first_signal_waits_for_the_checkpoint(
    make_run: Callable[..., Run],
    java: Java,
    capfd: pytest.CaptureFixture[str],
    tmp_path: Path,
    number: int,
    name: SignalName,
    code: int,
) -> None:
    state = deferral(make_run, java, number, times=1, release=tmp_path / "release", give_release=True)
    run = state.run
    outcome = run.parsed()
    assert run.reporter.notices == [waiting_line(name)]
    assert run.calls.count("notice") == 1
    assert state.started_at is not None
    assert run.calls.index("notice") > state.started_at
    assert run.notes() == []
    assert capfd.readouterr() == ("", "")  # nothing on the streams while the reporter was open
    assert state.written_handled  # the fake was not stopped while it waited
    assert java.signals() == ["SIGTERM"]
    assert (outcome.exit_code, outcome.stopped_by) == (code, name)
    assert outcome.kept is not None
    assert kept_folder(run) == outcome.kept.checkpoint_dir


def test_two_sigints_during_the_checkpoint_kill_at_once_and_keep_nothing(
    make_run: Callable[..., Run], java: Java, tmp_path: Path
) -> None:
    release = tmp_path / "never-created"
    state = deferral(make_run, java, signal.SIGINT, times=2, release=release, give_release=False)
    run = state.run
    outcome = run.parsed()
    assert java.signals() == []  # killed, never sent SIGTERM
    assert not java.exited()
    assert not state.written_handled  # 2196 never came
    assert not release.exists()
    assert outcome.exit_code == 130
    assert outcome.kept is None
    assert outcome.dropped_checkpoint == "incomplete"
    assert nothing_left(run.paths)


def test_the_waiting_lines() -> None:
    assert waiting_line("int") == "waiting for TLC to finish writing its checkpoint; press Ctrl-C again to stop now"
    assert waiting_line("term") == (
        "SIGTERM received: waiting for TLC to finish writing its checkpoint; send it again to stop now"
    )
    assert waiting_line("hup") == (
        "SIGHUP received: waiting for TLC to finish writing its checkpoint; send it again to stop now"
    )


# ---------------------------------------------------------------------- closed stdout (D58) and the stderr tail


def test_a_broken_pipe_in_the_reporter_passes_through_and_keeps_the_checkpoint(
    make_run: Callable[..., Run], java: Java
) -> None:
    java.script(stdout=SUCCESS, write_into_metadir=CHECKPOINT_FILES, hang_after_line=3)
    run = make_run(keep=True)

    def broken(*_args: object) -> None:
        raise BrokenPipeError

    run.reporter.on_handle = broken
    with pytest.raises(BrokenPipeError) as raised:
        run.parsed()
    assert java.exited()
    assert run.calls[-1] == "close"
    kept_folder(run)
    assert len(raised.value.__notes__) == 2
    assert raised.value.__notes__[0].startswith("Checkpoint kept (")


HELPER = Path(__file__).with_name("closed_pipe_child.py")


@pytest.mark.parametrize(
    "raw",
    [
        False,
        pytest.param(True, marks=pytest.mark.skipif(not hasattr(select, "poll"), reason="D58: no poll")),
    ],
)
def test_a_reader_that_went_away_stops_tlc_with_141(isolated: Isolated, java: Java, raw: bool) -> None:
    (isolated.work / "Spec.tla").write_text("---- MODULE Spec ----\n====\n", encoding="utf-8")
    java.script(stdout=SUCCESS, write_into_metadir=CHECKPOINT_FILES, hang_after_line=3)
    read_end, write_end = os.pipe()
    argument = json.dumps({"work": str(isolated.work), "java": str(java.path), "raw": raw, "keep": True})
    try:
        child = subprocess.Popen(
            [sys.executable, str(HELPER), argument], stdout=write_end, stderr=subprocess.PIPE, text=True
        )
    finally:
        os.close(write_end)
    try:
        try:
            # The reader goes once the fake has installed its handlers, so that its log shows the SIGTERM it gets.
            wait_until(lambda: bool(java.events("start")), "the fake has started")
        finally:
            os.close(read_end)
        _, err = child.communicate(timeout=60)
    finally:
        with contextlib.suppress(ProcessLookupError):
            child.kill()
        child.wait()
    assert child.returncode == 0, err
    fields = json.loads(err.strip().splitlines()[-1])
    assert fields["exit_code"] == 141
    assert fields["stopped_for_closed_pipe"] is True
    assert fields["stopped_by"] is None
    assert "SIGTERM" in java.signals()
    assert java.exited()
    assert fields["kept_reason"] == "interrupted"
    folder = Path(fields["run_folder_kept"])
    assert complete_checkpoint(folder) is not None
    if not raw:
        assert fields["status"] == "running"
        assert fields["verdict"] == "incomplete"


def test_the_stderr_tail_holds_the_last_50_lines(make_run: Callable[..., Run], java: Java) -> None:
    text = "".join(f"err {i}\n" for i in range(1, 81))
    java.script(stdout=SUCCESS, stderr={"text": text})
    run = make_run()
    outcome = run.parsed()
    assert outcome.stderr_tail == tuple(f"err {i}" for i in range(81 - TAIL_LINES, 81))
    assert len(run.reporter.stderr_lines) == 80


# ---------------------------------------------------------------------- non-UTF-8 output (R3)


def test_invalid_utf8_completes_with_the_lines_intact(make_run: Callable[..., Run], java: Java) -> None:
    java.script(stdout=INVALID_UTF8, exit=12)
    run = make_run()
    outcome = run.parsed()
    assert outcome.exit_code == 12
    assert outcome.result is not None
    expected = json.loads((GOLDEN_DIR / "synthetic/invalid-utf8.json").read_text(encoding="utf-8"))
    assert outcome.result.to_dict() == expected
    trace = outcome.result.errors[0].trace
    assert trace is not None
    assert "a d�liberately long note" in trace.states[1].variables[2].raw


# ---------------------------------------------------------------------- raw runs


def test_a_raw_run_passes_the_code_and_leaves_nothing(
    make_run: Callable[..., Run], java: Java, capfd: pytest.CaptureFixture[str]
) -> None:
    java.script(stdout={"text": "out\n"}, stderr={"text": "err\n"}, exit=12)
    run = make_run(raw=True)
    outcome = run.raw()
    assert (outcome.exit_code, outcome.tool_exit_code, outcome.result, outcome.stderr_tail) == (12, 12, None, ())
    assert nothing_left(run.paths)
    args = java.start()["args"]
    index = args.index("-metadir")
    assert args[index + 1] == str(run.paths.runs / run.inv.run_id)
    assert "-tool" not in args
    assert capfd.readouterr() == ("out\n", "err\n")  # the child had the test process's own descriptors


def test_a_raw_run_whose_java_cannot_be_started_leaves_nothing(make_run: Callable[..., Run], tmp_path: Path) -> None:
    run = make_run(raw=True, java_path=tmp_path / "no-such-java")
    with pytest.raises(ToolStartError, match="could not be started"):
        run.raw()
    assert nothing_left(run.paths)
