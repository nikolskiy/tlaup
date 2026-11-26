"""The terminal reporter in layout mode and the layout's frames (design 22 O4, O5, O6, O7; package 40a).

A reporter driven directly with events is a boundary of its own (01 T12, rule 1). Every test here draws without
a terminal (O6): a `Ui` on `StringIO` streams forced to terminal mode at a known size, colour off, and
``TERM=xterm-256color`` set by the test, since under the isolation fixture's ``TERM=dumb`` Rich's `Live` writes no
frame at all. The reporter draws no frame by itself (``refresh_thread=False``). The frame files under
``expected/layout/`` are what a user sees on the screen at those points and are reviewed as such; they are made
from the v1.7.4 captures, which no newer capture replaces (01 T3).
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from tests.clock import FakeClock
from tests.expected import assert_matches
from tests.unit.reporters.replay import EventClock, load_case, make_outcome, make_run, make_ui, replay
from tests.unit.tlc.invocations import make_invocation
from tlaup.errors import ToolStartError
from tlaup.java.locate import JavaRuntime, JavaTool
from tlaup.reporters.layout import LayoutView, format_clock, render_layout
from tlaup.reporters.terminal import TerminalReporter
from tlaup.tlc.command import build_tlc_command
from tlaup.tlc.runner import run_tlc, waiting_line
from tlaup_parse import OutputLine, Phase, Progress, ProgressMade, RunResult, TlcParser

if TYPE_CHECKING:
    from tests.conftest import Isolated
    from tests.unit.reporters.replay import Replay
    from tlaup.reporters.base import Reporter
    from tlaup_parse import Event

BUILD = "v1.7.4"
CASES = ("success", "violation", "big-states")
EXPECTED = Path(__file__).resolve().parent / "expected"
PLAIN = EXPECTED / "terminal" / BUILD
FRAMES = EXPECTED / "layout"
ENTER = "\x1b[?1049h"  # the alternate screen
LEAVE = "\x1b[?1049l"
HIDE_CURSOR = "\x1b[?25l"
ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
TITLES = ("── Status ", "── State space progress ", "── Output ")
FRAME_START = TITLES[0]  # one Status title per frame drawn
HINT = "Ctrl-C to interrupt"

_typecheck: Reporter = TerminalReporter(make_ui()[0], mode="layout", clock=EventClock())


@pytest.fixture(autouse=True)
def terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """O6: Rich reads ``TERM`` from the process; the isolation fixture's ``dumb`` would draw nothing."""
    monkeypatch.setenv("TERM", "xterm-256color")


def frame_text(view: LayoutView, now: float, width: int = 100, height: int = 30) -> str:
    """A frame printed to a colourless console of the size, each line without the spaces Rich pads it with."""
    stream = io.StringIO()
    console = Console(file=stream, width=width, height=height, color_system=None, no_color=True, legacy_windows=False)
    console.print(render_layout(view, now, width, height))
    return "".join(line.rstrip() + "\n" for line in stream.getvalue().splitlines())


def layout_replay(name: str, **options: object) -> Replay:
    return replay(BUILD, name, terminal=True, mode="layout", **options)  # type: ignore[arg-type]


def parts(stderr: str) -> tuple[str, str, str]:
    """What stands before the enter sequence, between the two sequences, and after the leave sequence."""
    before, _, rest = stderr.partition(ENTER)
    during, _, after = rest.partition(LEAVE)
    return before, during, after


def screens(during: str) -> list[str]:
    """The frames between the two sequences, as text, split at each frame's Status title."""
    text = ESCAPE.sub("", during)
    pieces = text.split(FRAME_START)
    return [FRAME_START + piece for piece in pieces[1:]]


# --- Layout frames (O6) ----------------------------------------------------------------------------------------


def _frames(name: str, *, width: int = 100, height: int = 30) -> list[str]:
    """The frames after start, after half the events and after the last event; the clock of each is the event
    clock's: one second per event handed over."""
    total = len(layout_replay(name).events)
    frames: list[str] = []
    handed = [0]

    def draw(reporter: TerminalReporter) -> None:
        assert reporter.view is not None
        frames.append(frame_text(reporter.view, reporter.view.started_at + handed[0], width, height))

    def at_event(reporter: TerminalReporter, _event: Event) -> None:
        handed[0] += 1
        if handed[0] in {total // 2, total}:
            draw(reporter)

    layout_replay(name, after_start=draw, after_event=at_event)
    return frames


@pytest.mark.parametrize("name", CASES)
def test_layout_frames(name: str, request: pytest.FixtureRequest) -> None:
    frames = _frames(name)
    assert len(frames) == 3
    for number, frame in enumerate(frames, start=1):
        assert_matches(frame, FRAMES / f"{name}-{number}.txt", request)


def test_the_smallest_frame(request: pytest.FixtureRequest) -> None:
    """60 by 15, the smallest size the layout accepts (O6), after the last event of ``violation``."""
    frame = _frames("violation", width=60, height=15)[-1]
    assert len(frame.splitlines()) == 15
    assert max(len(line) for line in frame.splitlines()) <= 60
    assert_matches(frame, FRAMES / "violation-60x15.txt", request)


def test_every_frame_file_has_its_test() -> None:
    names = {f"{name}-{number}.txt" for name in CASES for number in (1, 2, 3)} | {"violation-60x15.txt"}
    assert {path.name for path in FRAMES.glob("*.txt")} == names


@pytest.mark.parametrize("width", [60, 80, 100, 200])
def test_the_progress_columns_do_not_move_as_the_counts_grow(width: int) -> None:
    run = make_run(load_case(BUILD, "violation"))
    small = Progress(diameter=4, generated=44, distinct=44, queue=35, at="2026-11-14 22:25:56")
    large = Progress(diameter=4_000, generated=9_876_543_210, distinct=1_234_567_890, queue=35_000_000, at=small.at)

    def columns(*rows: Progress) -> list[str]:
        view = LayoutView(run, Phase.CHECKING, 0.0, 0, 0, rows, ())
        lines = frame_text(view, 0, width, 30).splitlines()
        first = next(number for number, line in enumerate(lines) if line.startswith(" " + TITLES[1])) + 1
        return lines[first : first + 1 + len(rows)]

    empty, with_small, with_large = columns(), columns(small), columns(small, large)
    assert empty[0] == with_small[0] == with_large[0]  # the headings
    assert with_small[1] == with_large[1]
    if width >= 100:
        ends = [line.rstrip() for line in with_large[1:]]
        assert len({len(line) for line in ends}) == 1  # right-aligned to the same column


def test_format_clock() -> None:
    assert [format_clock(s) for s in (0, 0.9, 133, 3600 * 101 + 61, -1)] == [
        "00:00:00",
        "00:00:00",
        "00:02:13",
        "101:01:01",
        "00:00:00",
    ]


# --- The two modes give one text, and the two streams (O6, D30, D40) ---------------------------------------------


@pytest.mark.parametrize("name", CASES)
def test_the_two_modes_give_one_text(name: str, request: pytest.FixtureRequest) -> None:
    run = layout_replay(name)
    assert_matches(run.stdout, PLAIN / f"{name}.stdout.txt", request)


@pytest.mark.parametrize("name", CASES)
def test_the_two_streams(name: str) -> None:
    stdout = io.StringIO()
    seen: list[str] = []
    run = layout_replay(
        name,
        stdout=stdout,
        after_event=lambda _r, _e: seen.append(stdout.getvalue()),
        before_finish=lambda _result: seen.append(stdout.getvalue()),
    )
    assert set(seen) == {""}, "stdout got something before close"
    assert ESCAPE.search(run.stdout) is None
    before, during, after = parts(run.stderr)
    assert before.splitlines() == replay(BUILD, name).stderr.splitlines()[:2]  # the header, before the layout
    assert run.stderr.count(ENTER) == 1
    assert run.stderr.count(LEAVE) == 1
    assert all(title in screens(during)[-1] for title in TITLES)
    assert after == ""  # these cases have no stderr lines; and nothing of the result text


def started(
    *, interval: float = 1.0, spool_dir: Path | None = None
) -> tuple[TerminalReporter, io.StringIO, io.StringIO]:
    """A layout-mode reporter on 100 by 30, started on ``violation``'s run, no frame drawn but start's."""
    ui, out, err = make_ui(terminal=True)
    reporter = TerminalReporter(
        ui, mode="layout", interval=interval, clock=EventClock(), refresh_thread=False, spool_dir=spool_dir
    )
    reporter.start(make_run(load_case(BUILD, "violation")))
    return reporter, out, err


def feed(reporter: TerminalReporter, name: str, *, until: type | None = None) -> RunResult:
    """The case's lines through a parser into the reporter; with ``until``, stop after the first such event."""
    parser = TlcParser()
    for line in load_case(BUILD, name).lines:
        for event in parser.feed(line):
            reporter.handle(event, parser.result)
            if until is not None and isinstance(event, until):
                return parser.result
    for event in parser.close():
        reporter.handle(event, parser.result)
    return parser.result


def test_the_tools_stderr_lines_stand_after_the_layout_in_order_and_unmarked() -> None:
    reporter, out, err = started()
    result = feed(reporter, "violation")
    reporter.stderr_line("first literal line")
    reporter.stderr_line("second literal line")
    reporter.refresh()
    _, during, _ = parts(err.getvalue())
    assert "stderr: first literal line" in screens(during)[-1]  # marked in the Output panel
    reporter.finish(make_outcome(load_case(BUILD, "violation"), result))
    _, _, after = parts(err.getvalue())
    assert after == "first literal line\nsecond literal line\n"
    assert "literal" not in out.getvalue()


# --- close (O1, O6) -----------------------------------------------------------------------------------------------


def test_close_without_finish_leaves_the_layout_and_writes_the_text_so_far() -> None:
    reporter, out, err = started()
    feed(reporter, "violation", until=ProgressMade)
    reporter.handle(OutputLine("printed by the spec"), RunResult())
    assert out.getvalue() == ""
    reporter.close()
    assert err.getvalue().count(LEAVE) == 1
    assert out.getvalue().splitlines()[-1] == "printed by the spec"
    assert "Result:" not in out.getvalue()
    written = (out.getvalue(), err.getvalue())
    reporter.close()
    assert (out.getvalue(), err.getvalue()) == written


def test_close_on_a_reporter_never_started_writes_nothing() -> None:
    ui, out, err = make_ui(terminal=True)
    reporter = TerminalReporter(ui, mode="layout", clock=EventClock(), refresh_thread=False)
    reporter.close()
    reporter.close()
    assert (out.getvalue(), err.getvalue(), reporter.write_error) == ("", "", None)


class _FailsOnEnter(io.StringIO):
    """A stderr stream whose first write of the enter sequence raises: `start` fails after the spools exist."""

    def __init__(self) -> None:
        super().__init__()
        self.raised = False

    def write(self, text: str) -> int:
        if ENTER in text and not self.raised:
            self.raised = True
            message = "no space left on device"
            raise OSError(message)
        return super().write(text)


def spools(tmp_path: Path) -> Path:
    folder = tmp_path / "spools"
    folder.mkdir(exist_ok=True)
    return folder


def _open_descriptors() -> int | None:
    for folder in ("/proc/self/fd", "/dev/fd"):
        if Path(folder).is_dir():
            return sum(1 for _ in Path(folder).iterdir())
    return None  # Windows: the folder listing below is the check there


def test_a_start_that_fails_half_way_leaves_no_spool_and_no_leave_sequence(tmp_path: Path) -> None:
    """The spools are put on disk at once, in a folder of the test's (``spool_dir``, a constructor argument
    production never passes), so the check is of real files: none left in the folder, no descriptor left open."""
    err = _FailsOnEnter()
    ui, out, _ = make_ui(terminal=True, stderr=err)
    reporter = TerminalReporter(ui, mode="layout", clock=EventClock(), refresh_thread=False, spool_dir=spools(tmp_path))
    descriptors = _open_descriptors()
    with pytest.raises(OSError, match="no space left"):
        reporter.start(make_run(load_case(BUILD, "violation")))
    assert err.raised
    if descriptors is not None:
        assert _open_descriptors() == descriptors + 2  # the two spools, on disk
    reporter.close()
    assert list((tmp_path / "spools").iterdir()) == []
    assert descriptors is None or _open_descriptors() == descriptors
    assert LEAVE not in err.getvalue()
    assert (out.getvalue(), reporter.write_error) == ("", None)


def test_the_spools_on_disk_are_copied_and_deleted(tmp_path: Path) -> None:
    descriptors = _open_descriptors()
    reporter, out, _ = started(spool_dir=spools(tmp_path))
    reporter.handle(OutputLine("kept on disk"), RunResult())
    reporter.close()
    assert out.getvalue() == "kept on disk\n"
    assert list((tmp_path / "spools").iterdir()) == []
    assert descriptors is None or _open_descriptors() == descriptors


class _FailsOnHide(io.StringIO):
    """A stderr stream whose first write of the hide-cursor sequence raises: `Live.start` fails after the enter
    sequence is out."""

    def __init__(self) -> None:
        super().__init__()
        self.raised = False

    def write(self, text: str) -> int:
        if HIDE_CURSOR in text and not self.raised:
            self.raised = True
            message = "the terminal went away"
            raise OSError(message)
        return super().write(text)


def test_a_start_that_fails_after_the_enter_sequence_leaves_the_alternate_screen() -> None:
    err = _FailsOnHide()
    ui, out, _ = make_ui(terminal=True, stderr=err)
    reporter = TerminalReporter(ui, mode="layout", clock=EventClock(), refresh_thread=False)
    with pytest.raises(OSError, match="went away"):
        reporter.start(make_run(load_case(BUILD, "violation")))
    assert err.raised
    written = err.getvalue()
    assert written.count(ENTER) == 1
    assert written.count(LEAVE) == 1
    assert written.index(ENTER) < written.index(LEAVE)
    reporter.close()
    assert err.getvalue().count(LEAVE) == 1  # close does not stop a display that never started
    assert out.getvalue() == ""


class _ClosedPipe(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.error = BrokenPipeError(32, "Broken pipe")

    def write(self, _text: str) -> int:
        raise self.error


def test_a_closed_pipe_on_stdout_is_held_by_close() -> None:
    stdout = _ClosedPipe()
    ui, _, err = make_ui(terminal=True, stdout=stdout)
    reporter = TerminalReporter(ui, mode="layout", clock=EventClock(), refresh_thread=False)
    reporter.start(make_run(load_case(BUILD, "violation")))
    reporter.stderr_line("a line of TLC's stderr")
    reporter.handle(OutputLine("lost to the closed pipe"), RunResult())
    reporter.close()
    assert err.getvalue().count(LEAVE) == 1
    assert parts(err.getvalue())[2] == "a line of TLC's stderr\n"
    assert reporter.write_error is stdout.error


def test_a_tool_that_cannot_start_leaves_the_layout_before_the_error(isolated: Isolated, tmp_path: Path) -> None:
    """Through `run_tlc` (37): the leave sequence is written when the start error leaves it, so the application's
    ``error:`` line lands on the ordinary screen."""
    runtime = JavaRuntime(JavaTool(tmp_path / "no-such-java", "PATH"), "25.0.5", 25, ())
    inv = make_invocation(isolated.work, isolated.paths.runs, java=runtime)
    (isolated.work / "Spec.tla").write_text("---- MODULE Spec ----\n====\n", encoding="utf-8")
    ui, out, err = make_ui(terminal=True)
    reporter = TerminalReporter(ui, mode="layout", clock=EventClock(), refresh_thread=False)
    with pytest.raises(ToolStartError):
        run_tlc(inv, build_tlc_command(inv), reporter, paths=isolated.paths, now=FakeClock().now, notice=ui.note)
    assert err.getvalue().count(ENTER) == 1
    assert err.getvalue().endswith(LEAVE)
    assert out.getvalue() == ""


# --- Markup (10 P11), the interval (O5), the clock -----------------------------------------------------------------

MARKUP = ["[a |-> 1]", "[/]", "[bold]x[/bold]", "\\["]


def test_tlc_text_is_never_markup_in_the_output_panel_p11() -> None:
    reporter, out, _ = started()
    for text in MARKUP:
        reporter.handle(OutputLine(text), RunResult())
    assert reporter.view is not None
    shown = frame_text(reporter.view, 0).splitlines()
    first = next(number for number, line in enumerate(shown) if line.startswith(" " + TITLES[2])) + 1
    assert [line.strip() for line in shown[first : first + len(MARKUP)]] == MARKUP
    reporter.close()
    assert out.getvalue().splitlines() == MARKUP


@pytest.mark.parametrize(("interval", "per_second"), [(0.5, 2), (2, 0.5)])
def test_the_interval_reaches_live(interval: float, per_second: float) -> None:
    """O5's one look at a Rich object: the value the constructor of `Live` was given."""
    reporter, _, _ = started(interval=interval)
    assert reporter.live is not None
    assert reporter.live.refresh_per_second == per_second
    reporter.close()


def test_two_refreshes_one_second_apart_show_elapsed_one_second_apart() -> None:
    ui, _, err = make_ui(terminal=True)
    clock = EventClock()
    reporter = TerminalReporter(ui, mode="layout", clock=clock, refresh_thread=False)
    reporter.start(make_run(load_case(BUILD, "violation")))
    clock.now = 41.0
    reporter.refresh()
    clock.now = 42.0
    reporter.refresh()
    reporter.close()
    elapsed = re.findall(r"elapsed (\d\d:\d\d:\d\d)", ESCAPE.sub("", err.getvalue()))
    assert elapsed[-2:] == ["00:00:41", "00:00:42"]


# --- O7, layout mode ----------------------------------------------------------------------------------------------


def test_a_long_output_keeps_the_view_and_the_frames_bounded() -> None:
    reporter, out, err = started()
    parser = TlcParser()
    count = 300_000
    for number in range(1, count + 1):
        for event in parser.feed(f"line {number}\n"):
            reporter.handle(event, parser.result)
        if number in {1_000, 200_000}:
            reporter.refresh()
    for event in parser.close():
        reporter.handle(event, parser.result)
    assert reporter.view is not None
    assert len(reporter.view.tail) == 200
    assert reporter.view.tail[-1].plain == f"line {count}"
    reporter.finish(make_outcome(load_case(BUILD, "violation"), parser.result))
    assert err.getvalue().count(FRAME_START) == 4  # start, the two refreshes, finish
    lines = out.getvalue().splitlines()
    assert lines[:count] == [f"line {number}" for number in range(1, count + 1)]
    assert lines[count].startswith("Result: ")


# --- The size, read at start (O4) ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), [(59, 15), (60, 14)])
def test_a_terminal_too_small_gets_plain_output(width: int, height: int) -> None:
    run = layout_replay("violation", width=width, height=height)
    plain = replay(BUILD, "violation", width=width, height=height)
    assert ENTER not in run.stderr
    assert (run.stdout, run.stderr) == (plain.stdout, plain.stderr)


def test_the_smallest_terminal_gets_the_layout() -> None:
    run = layout_replay("violation", width=60, height=15)
    assert run.stderr.count(ENTER) == 1


# --- The phase words, the waiting line (O4, O6, Q12) ------------------------------------------------------------


def test_the_phase_before_tlc_reports_one_is_starting() -> None:
    reporter, _, _ = started()
    assert reporter.view is not None
    assert frame_text(reporter.view, 0).splitlines()[3].split()[0] == "Starting"
    reporter.close()


def test_an_interrupted_run_ends_on_interrupted() -> None:
    run = layout_replay("violation", stopped_by="int", exit_code=130)
    last = screens(parts(run.stderr)[1])[-1]
    assert "Interrupted" in last
    assert "Finished" not in last


def test_the_waiting_line_takes_the_hints_place_and_follows_the_stderr_lines() -> None:
    reporter, out, err = started()
    result = feed(reporter, "violation", until=ProgressMade)
    reporter.refresh()
    assert HINT in screens(parts(err.getvalue())[1])[-1]
    line = waiting_line("int")
    reporter.stderr_line("before the signal")
    reporter.notice(line)
    reporter.stderr_line("after the signal")
    reporter.refresh()
    frame = screens(parts(err.getvalue())[1])[-1]
    assert line in frame
    assert HINT not in frame
    reporter.finish(make_outcome(load_case(BUILD, "violation"), result))
    assert parts(err.getvalue())[2] == f"before the signal\n{line}\nafter the signal\n"
    assert "waiting" not in out.getvalue()


_FORGETS_CLOSE = """
import sys
from tests.unit.reporters.replay import EventClock, load_case, make_run
from tlaup.reporters.terminal import TerminalReporter
from tlaup.ui import Ui

ui = Ui(sys.stdout, sys.stderr, sys.stdin, color=False, env={}, terminal=True, size=(100, 30))
reporter = TerminalReporter(ui, mode="layout", clock=EventClock(), refresh_thread=False)
reporter.start(make_run(load_case("v1.7.4", "violation")))
sys.stderr.write("started\\n")
"""


def test_the_atexit_hook_leaves_the_layout_when_close_is_forgotten() -> None:
    """O4's second line of defence, in a process of its own that exits without `close`."""
    root = Path(__file__).resolve().parents[3]
    env = {**os.environ, "TERM": "xterm-256color", "PYTHONPATH": str(root)}
    done = subprocess.run(
        [sys.executable, "-c", _FORGETS_CLOSE],
        capture_output=True,
        text=True,
        env=env,
        cwd=root,
        check=True,
        timeout=60,
    )
    assert done.stderr.count(ENTER) == 1
    assert done.stderr.index("started") < done.stderr.index(LEAVE)


def test_close_removes_the_atexit_hook() -> None:
    """With `close` called, the process's exit writes no second leave sequence."""
    code = _FORGETS_CLOSE + "reporter.close()\nsys.stderr.write('closed\\n')\n"
    root = Path(__file__).resolve().parents[3]
    env = {**os.environ, "TERM": "xterm-256color", "PYTHONPATH": str(root)}
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=root, check=True, timeout=60
    )
    assert done.stderr.count(LEAVE) == 1
    assert done.stderr.endswith("closed\n")
