"""The terminal reporter in plain mode, driven with the events of the golden cases (design 22 O3, O6, O7).

A reporter driven directly with events is a boundary of its own (01 T12, rule 1). The expected files under
``expected/terminal/<build>/`` are what a user sees after each case and are reviewed as such; they hold
inventory rows R9 (``coverage``), R15 (``print-output``, and an unknown message in ``unknown-code`` of the
synthetic folder through its own test below), R16 (the progress lines on stderr), R18 (``violation``), R19
(``tool-assum``: an error with no trace) and R20 and R21 (``sany-semantic-error``, ``parse-error``).
"""

from __future__ import annotations

import dataclasses
import io
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.expected import assert_matches
from tests.parse.drive import golden_root, read_lines
from tests.unit.reporters.replay import (
    SecondClock,
    case_names,
    load_case,
    make_build,
    make_outcome,
    make_run,
    make_ui,
    replay,
)
from tlaup.reporters.terminal import TerminalReporter, header_lines, render_inline_coverage
from tlaup.tlc.run import waiting_line
from tlaup_parse import (
    CoverageItem,
    ErrorKind,
    ErrorOpened,
    Location,
    OutputLine,
    ProgressMade,
    RunResult,
    TlcError,
    TlcMessage,
    TlcParser,
    Trace,
    TraceState,
    TraceStateAdded,
    Variable,
    parse_value,
)

if TYPE_CHECKING:
    from tlaup.reporters.base import Reporter
    from tlaup_parse import Event

# The builds whose expected files exist. Package 38b adds "2026.11.15.002146" with its files.
BUILDS = ("v1.7.4",)
EXPECTED = Path(__file__).resolve().parent / "expected" / "terminal"
CASES = [(build, name) for build in BUILDS for name in case_names(build)]
ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
EXCERPT_LINE = re.compile(r"^  ( {3}\d| {2}\d\d| \d{3}|\d{4}| {4}) \| ")

_typecheck: Reporter = TerminalReporter(make_ui()[0], clock=SecondClock())


# --- Plain mode: every golden case ------------------------------------------------------------------------------


@pytest.mark.parametrize(("build", "name"), CASES, ids=[f"{build}/{name}" for build, name in CASES])
def test_plain_mode(build: str, name: str, request: pytest.FixtureRequest) -> None:
    run = replay(build, name)
    assert_matches(run.stdout, EXPECTED / build / f"{name}.stdout.txt", request)
    assert_matches(run.stderr, EXPECTED / build / f"{name}.stderr.txt", request)


def test_every_expected_file_has_its_case() -> None:
    names = {f"{build}/{name}.{stream}.txt" for build, name in CASES for stream in ("stdout", "stderr")}
    names |= {"v1.7.4/violation.color.stdout.txt", "v1.7.4/violation.w40.stdout.txt"}
    present = {path.relative_to(EXPECTED).as_posix() for path in EXPECTED.rglob("*.txt")}
    assert present <= names


def test_an_unknown_message_is_shown_with_its_code() -> None:
    """R15's second half: a code that is not in the table, from the synthetic capture."""
    ui, out, _ = make_ui()
    reporter = TerminalReporter(ui, clock=SecondClock())
    reporter.start(make_run(load_case("v1.7.4", "success")))
    parser = TlcParser()
    for line in read_lines(golden_root() / "synthetic" / "unknown-code.out"):
        for event in parser.feed(line):
            reporter.handle(event, parser.result)
    lines = out.getvalue().splitlines()
    assert (
        "Warning: TLC message 9902: Please run the Java VM which executes TLC with a throughput optimized "
        'garbage collector by passing the "-XX:+UseParallelGC" property.' in lines
    )
    assert (
        "TLC message 9903: Finished computing initial states: 1 distinct state generated at 2026-11-14 "
        "22:25:56." in lines
    )
    assert "Error: TLC message 9901: Invariant Small is violated." in lines


# --- The header and TLC's version line -----------------------------------------------------------------------------


def test_the_header_leaves_out_what_is_not_known() -> None:
    case = load_case("2026.11.15.002146", "success")
    full = make_run(case)
    assert [line.plain for line in header_lines(full)] == [
        "TLC rolling@bc1b506 (2026.11.15.002146), Java 25.0.5, workers auto",
        "Success.tla  cfg: Success.cfg",
    ]
    java = dataclasses.replace(full.java, version=None)
    bare = dataclasses.replace(full, cfg=None, workers=None, java=java, build=make_build("v1.7.4"))
    assert [line.plain for line in header_lines(bare)] == ["TLC v1.7.4@5a47802", "Success.tla"]


def test_tlcs_version_line_is_shown_only_when_it_differs_from_the_store() -> None:
    assert len(replay("v1.7.4", "success").stderr.splitlines()) == 3  # header and one progress line
    lines = replay("2026.11.15.002146", "success").stderr.splitlines()
    assert not any(line.startswith("TLC2 Version") for line in lines)
    case = load_case("v1.7.4", "success")
    run = make_run(case)
    other = dataclasses.replace(run, build=dataclasses.replace(run.build, commit="0" * 40))
    ui, _, err = make_ui()
    reporter = TerminalReporter(ui, clock=SecondClock())
    reporter.start(other)
    parser = TlcParser()
    for text in case.lines[:3]:
        for event in parser.feed(text):
            reporter.handle(event, parser.result)
    assert err.getvalue().splitlines()[-1] == "TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)"


def test_an_action_that_generated_no_state_is_marked_never_reached_r9() -> None:
    run = make_run(load_case("v1.7.4", "coverage"))
    where = Location("Success", 6, 1, 6, 4)
    reached = CoverageItem("action", "Next", where, Location("Success", 6, 12, 6, 40), 12, 3, 0)
    unreached = CoverageItem("action", "Next", where, Location("Success", 8, 12, 8, 47), 0, 0, 0)
    lines = [line.plain for line in render_inline_coverage([reached, unreached], run)]
    assert lines[6] == "  3    6 | Next == \\/ x < 3 /\\ x' = x + 1 /\\ y' = y"
    assert lines[8] == "  0    8 |         \\/ x = 3 /\\ y = 3 /\\ UNCHANGED <<x, y>>  <-- never reached"


# --- P10, streams, P11 -------------------------------------------------------------------------------------------


def test_the_invariant_text_stands_above_the_trace_p10() -> None:
    lines = replay("v1.7.4", "violation").stdout.splitlines()
    at = lines.index("Error: Invariant Small is violated.")
    assert lines[at + 1 : at + 3] == ["  The behavior up to this point is:", "  1: Initial predicate"]
    assert "" not in lines  # TLC printed no blank line in this case's messages


def test_stdout_holds_the_result_and_stderr_the_header_and_progress() -> None:
    run = replay("v1.7.4", "violation")
    progress = [event for event in run.events if isinstance(event, ProgressMade)]
    assert run.stderr.splitlines() == [
        "TLC v1.7.4@5a47802, Java 25.0.5, workers auto",
        "Violation.tla  cfg: Violation.cfg",
        *("44 states generated, 44 distinct, 35 on queue, diameter 4" for _ in progress),
    ]
    assert len(progress) == 1
    out = run.stdout.splitlines()
    assert "Error: Invariant Small is violated." in out
    assert out[-1].startswith("Result: errors found (TLC exit code 12: an invariant was violated)")
    assert not any(line.startswith("TLC v1.7.4") or "on queue, diameter" in line for line in out)


MARKUP = ["[a |-> 1]", "[/]", "[bold]x[/bold]", "\\["]


def _color_ui(monkeypatch: pytest.MonkeyPatch) -> tuple[TerminalReporter, io.StringIO]:
    monkeypatch.setenv("TERM", "xterm-256color")
    ui, out, _ = make_ui(color=True, terminal=True)
    reporter = TerminalReporter(ui, clock=SecondClock())
    reporter.start(make_run(load_case("v1.7.4", "violation")))
    return reporter, out


def test_tlc_text_is_never_markup_p11(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter, out = _color_ui(monkeypatch)
    result = RunResult()
    for text in MARKUP:
        reporter.handle(OutputLine(text), result)
    assert ESCAPE.sub("", out.getvalue()).splitlines() == MARKUP


def test_values_in_a_trace_are_never_markup_p11(monkeypatch: pytest.MonkeyPatch) -> None:
    reporter, out = _color_ui(monkeypatch)
    message = TlcMessage(2110, 1, "TLC_INVARIANT_VIOLATED_BEHAVIOR", ("Invariant Inv is violated.",))
    error = TlcError(ErrorKind.INVARIANT, "Inv", message, [], Trace([], None, False))
    result = RunResult(errors=[error])
    reporter.handle(ErrorOpened(message, error), result)
    for index, values in enumerate((["0"] * len(MARKUP), MARKUP), start=1):
        variables = tuple(
            Variable(f"v{n}", parse_value(f"[f |-> {value}]"), f"[f |-> {value}]") for n, value in enumerate(values)
        )
        header = "Initial predicate" if index == 1 else "Next"
        state = TraceState(index, None, None, header, variables, ())
        assert error.trace is not None
        error.trace.states.append(state)
        reporter.handle(TraceStateAdded(TlcMessage(2217, 4, "TLC_STATE_PRINT2", ()), error, state), result)
    lines = ESCAPE.sub("", out.getvalue()).splitlines()
    assert lines[-len(MARKUP) :] == [f"     * v{n} = [f |-> {value}]" for n, value in enumerate(MARKUP)]


def test_violation_with_colour(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")
    run = replay("v1.7.4", "violation", color=True, terminal=True)
    assert "\x1b[" in run.stdout
    assert_matches(run.stdout, EXPECTED / "v1.7.4" / "violation.color.stdout.txt", request)
    assert ESCAPE.sub("", run.stdout) == replay("v1.7.4", "violation").stdout


def test_violation_at_width_40_is_not_wrapped(request: pytest.FixtureRequest) -> None:
    run = replay("v1.7.4", "violation", width=40)
    assert max(len(line) for line in run.stdout.splitlines()) > 40
    assert run.stdout == replay("v1.7.4", "violation").stdout
    assert_matches(run.stdout, EXPECTED / "v1.7.4" / "violation.w40.stdout.txt", request)


# --- The source excerpt (D66, R21) --------------------------------------------------------------------------------


@pytest.mark.parametrize("build", BUILDS)
@pytest.mark.parametrize(
    ("name", "editor", "after"),
    [
        (
            "sany-semantic-error",
            "SanyError.tla:5:18: error: Unknown operator: `undefinedThing'.",
            ["     6 | Spec == Init /\\ [][Next]_x", "     7 | ===="],
        ),
        (
            "parse-error",
            'ParseError.tla:6:1: error: Encountered "Beginning of definition" at line 6, column 1 and token "1"',
            ["     7 | ===="],
        ),
    ],
)
def test_the_source_excerpt_stands_under_the_editor_form_line(
    build: str, name: str, editor: str, after: list[str]
) -> None:
    lines = replay(build, name).stdout.splitlines()
    at = lines.index(editor)
    excerpt = lines[at + 1 : at + 1 + 5 + len(after)]
    assert all(EXCERPT_LINE.match(line) for line in excerpt)
    assert re.fullmatch(r"       \| *\^+", excerpt[3])
    assert excerpt[4].startswith("       | Error here: line ")
    assert excerpt[-len(after) :] == after


@pytest.mark.parametrize("build", BUILDS)
@pytest.mark.parametrize("name", ["sany-semantic-error", "parse-error"])
def test_with_the_folder_not_mapped_there_is_no_excerpt(build: str, name: str) -> None:
    mapped = replay(build, name).stdout.splitlines()
    unmapped = replay(build, name, map_folder=False).stdout.splitlines()
    captured = load_case(build, name).captured_folder
    assert captured is not None
    assert not any(EXCERPT_LINE.match(line) for line in unmapped)
    assert [line.replace(f"{captured}/", "") for line in unmapped] == [
        line for line in mapped if not EXCERPT_LINE.match(line)
    ]


# --- The waiting line (O1, Q12) -----------------------------------------------------------------------------------


def test_the_waiting_line_is_on_stderr_at_once() -> None:
    case = load_case("v1.7.4", "violation")
    ui, out, err = make_ui()
    reporter = TerminalReporter(ui, clock=SecondClock())
    reporter.start(make_run(case))
    parser = TlcParser()
    line = waiting_line("int")
    noticed = False
    for text in case.lines:
        for event in parser.feed(text):
            reporter.handle(event, parser.result)
            if isinstance(event, ProgressMade) and not noticed:
                reporter.notice(line)
                noticed = True
                assert err.getvalue().splitlines()[-1] == line
    reporter.finish(make_outcome(case, parser.result))
    assert err.getvalue().splitlines() == [
        "TLC v1.7.4@5a47802, Java 25.0.5, workers auto",
        "Violation.tla  cfg: Violation.cfg",
        "44 states generated, 44 distinct, 35 on queue, diameter 4",
        "waiting for TLC to finish writing its checkpoint; press Ctrl-C again to stop now",
    ]
    assert "waiting" not in out.getvalue()


def test_stderr_lines_are_written_unchanged_and_at_once() -> None:
    run = replay("v1.7.4", "tool-missing-module")
    assert run.stderr.splitlines()[-1].startswith("File does not exist: <tmp>/q22/work/v1.7.4/tool-missing-module/")
    assert "File does not exist" not in run.stdout


# --- The override hint (11 R7, part 4) ----------------------------------------------------------------------------

CLASSES = ("tlc2.overrides.TLCOverrides",)
GENERAL = "hint: TLC failed while loading the spec. If the error comes from a Java override"
OVERRIDE_CASES = [name for name in case_names("v1.7.4") if name.startswith("override-")]


def _hints(stderr: str) -> list[str]:
    return [line for line in stderr.splitlines() if line.startswith("hint:")]


@pytest.mark.parametrize(
    ("name", "found"), [("override-class-too-new-index", "TLCOverrides"), ("override-class-too-new-listed", "Newer")]
)
def test_a_class_too_new_gets_the_specific_hint(name: str, found: str) -> None:
    (hint,) = _hints(replay("v1.7.4", name, override_classes=CLASSES).stderr)
    assert hint.startswith(f"hint: the override class tlc2.overrides.{found} was compiled for Java 25 (class file 69)")
    assert "TLC runs on Java 11 (up to 55)" in hint


@pytest.mark.parametrize(
    "name",
    ["override-ctor_private", "override-ctor_throws", "override-method_not_public", "override-static_init_throws"],
)
def test_an_override_that_breaks_while_loading_gets_the_general_hint(name: str) -> None:
    assert _hints(replay("v1.7.4", name, override_classes=CLASSES).stderr) == [
        f"{GENERAL}, one of these classes failed to load: tlc2.overrides.TLCOverrides"
    ]


def test_a_false_postcondition_on_v174_gets_no_hint() -> None:
    assert _hints(replay("v1.7.4", "postcondition-false", override_classes=CLASSES).stderr) == []


@pytest.mark.parametrize("name", OVERRIDE_CASES)
def test_with_no_override_classes_only_2173_gets_a_hint(name: str) -> None:
    hints = _hints(replay("v1.7.4", name).stderr)
    assert len(hints) == (1 if name == "override-class-too-new-index" else 0)


def test_no_hint_goes_to_stdout() -> None:
    assert "hint:" not in replay("v1.7.4", "override-ctor_throws", override_classes=CLASSES).stdout


# --- The result line on hand-built outcomes -----------------------------------------------------------------------


def _last(stdout: str) -> str:
    return stdout.splitlines()[-1]


def test_an_interrupted_run() -> None:
    line = _last(replay("v1.7.4", "checkpoint-run", stopped_by="int", exit_code=130).stdout)
    assert line == "Result: incomplete, interrupted after 1.0 s"


def test_a_run_stopped_for_a_closed_pipe() -> None:
    line = _last(replay("v1.7.4", "checkpoint-run", stopped_for_closed_pipe=True, exit_code=141).stdout)
    assert line == "Result: incomplete, stopped because the output was closed"


@pytest.mark.parametrize(
    ("dropped", "suffix"),
    [
        ("not-asked", "; a checkpoint was not kept (use --keep to keep one)"),
        ("incomplete", "; the checkpoint was incomplete, nothing to resume"),
        ("depth-first", "; a -dfid run cannot be resumed"),
    ],
)
def test_a_dropped_checkpoint(dropped: str, suffix: str) -> None:
    line = _last(replay("v1.7.4", "violation", dropped_checkpoint=dropped).stdout)
    assert line == f"Result: errors found (TLC exit code 12: an invariant was violated) in 1.1 s{suffix}"


def test_a_resumed_run() -> None:
    lines = replay("v1.7.4", "checkpoint-recover").stdout.splitlines()
    assert lines[-1].endswith("; resumed from a checkpoint")
    assert "about" not in lines[-2]


def test_a_resumed_run_with_approximate_counts() -> None:
    def approximate(result: RunResult) -> None:
        result.counts_approximate = True

    lines = replay("v1.7.4", "checkpoint-recover", before_finish=approximate).stdout.splitlines()
    assert lines[-1].endswith("; resumed from a checkpoint, state counts approximate")
    assert lines[-2].startswith("about ")
    assert ", about " in lines[-2]


def test_a_false_postcondition_on_rolling() -> None:
    line = _last(replay("2026.11.15.002146", "postcondition-false").stdout)
    assert line.startswith("Result: errors found (TLC exit code 10: a postcondition was false) in ")


def test_errors_found_with_exit_code_0() -> None:
    line = _last(replay("v1.7.4", "deadlock-flag-multierror").stdout)
    assert line.startswith("Result: errors found (TLC exit code 0) in ")


# --- close and write errors ---------------------------------------------------------------------------------------


def test_close_before_start_does_nothing() -> None:
    ui, out, err = make_ui()
    reporter = TerminalReporter(ui, clock=SecondClock())
    reporter.close()
    reporter.close()
    assert (out.getvalue(), err.getvalue(), reporter.write_error) == ("", "", None)


def test_close_twice_after_finish_writes_nothing() -> None:
    case = load_case("v1.7.4", "success")
    ui, out, err = make_ui()
    reporter = TerminalReporter(ui, clock=SecondClock())
    reporter.start(make_run(case))
    reporter.finish(make_outcome(case, RunResult()))
    written = (out.getvalue(), err.getvalue())
    reporter.close()
    reporter.close()
    assert (out.getvalue(), err.getvalue(), reporter.write_error) == (*written, None)


class _Broken(io.StringIO):
    def write(self, _text: str) -> int:
        raise BrokenPipeError


def test_a_closed_pipe_passes_out_of_handle_and_close_holds_nothing() -> None:
    ui, _, err = make_ui(stdout=_Broken())
    reporter = TerminalReporter(ui, clock=SecondClock())
    reporter.start(make_run(load_case("v1.7.4", "success")))
    written = err.getvalue()
    with pytest.raises(BrokenPipeError):
        reporter.handle(OutputLine("x"), RunResult())
    reporter.close()
    assert err.getvalue() == written
    assert reporter.write_error is None


# --- O7, plain mode -----------------------------------------------------------------------------------------------


class _Null(io.TextIOBase):
    """A stream that counts its write calls and keeps nothing."""

    def __init__(self) -> None:
        super().__init__()
        self.writes = 0

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self.writes += 1
        return len(text)


def _numbered(count: int) -> tuple[RunResult, _Null]:
    stream = _Null()
    ui, _, _ = make_ui(stdout=stream)
    reporter = TerminalReporter(ui, clock=SecondClock())
    reporter.start(make_run(load_case("v1.7.4", "success")))
    parser = TlcParser()
    events: list[Event] = []
    for number in range(1, count + 1):
        events = parser.feed(f"line {number}\n")
        for event in events:
            reporter.handle(event, parser.result)
    for event in parser.close():
        reporter.handle(event, parser.result)
    return parser.result, stream


def test_a_long_output_keeps_memory_bounded() -> None:
    result, _ = _numbered(300_000)
    assert len(result.output) == 10_000
    assert result.output_dropped == 290_000


def test_the_cost_is_linear_in_the_lines() -> None:
    _, small = _numbered(1_000)
    _, large = _numbered(10_000)
    assert 9.5 <= large.writes / small.writes <= 10.5
