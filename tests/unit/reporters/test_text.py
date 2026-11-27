"""The pure text functions of the terminal reporter and of `tlaup sany` (design 22 O3, 21 S1), one by one."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tlaup.reporters.text import (
    diff_values,
    format_count,
    format_diagnostic,
    format_path,
    progress_line,
    render_value_diff,
    result_line,
    source_excerpt,
    stats_line,
)
from tlaup.tlc.runner import RunOutcome
from tlaup_parse import (
    Diagnostic,
    ErrorKind,
    FinalStats,
    Location,
    Progress,
    RunResult,
    TlcError,
    TlcMessage,
    Verdict,
    parse_value,
)

CWD = Path("/work/project").absolute()
SEMERR = """---- MODULE SemErr ----
EXTENDS Naturals
VARIABLE x
Init == x = y
Next == x' = x + 1 + Foo(2)
====
"""


# --- format_count, format_path, progress and statistics -----------------------------------------------------------


def test_format_count() -> None:
    assert format_count(0) == "0"
    assert format_count(1771600) == "1,771,600"
    assert format_count(1771600, approximate=True) == "about 1,771,600"


def test_format_path_beneath_the_folder_is_relative() -> None:
    assert format_path(CWD / "specs" / "Spec.tla", CWD) == str(Path("specs") / "Spec.tla")
    assert format_path(str(CWD / "Spec.tla"), CWD) == "Spec.tla"


def test_format_path_outside_the_folder_is_absolute() -> None:
    outside = CWD.parent / "other" / "Spec.tla"
    assert format_path(outside, CWD) == str(outside)


def test_progress_line_leaves_out_a_count_of_minus_one() -> None:
    assert progress_line(Progress(4, 44, 44, 35, "x")) == "44 states generated, 44 distinct, 35 on queue, diameter 4"
    assert (
        progress_line(Progress(12, 1234567, 1000, -1, "x")) == "1,234,567 states generated, 1,000 distinct, diameter 12"
    )


def test_stats_line() -> None:
    stats = FinalStats(44, 44, 35, 4, None, None)
    assert stats_line(stats, approximate=False) == "44 states generated, 44 distinct, 35 left on queue; depth 4"
    assert stats_line(stats, approximate=True) == (
        "about 44 states generated, about 44 distinct, about 35 left on queue; depth 4"
    )
    assert stats_line(FinalStats(None, None, None, 7, None, None), approximate=False) == "depth 7"


# --- format_diagnostic: S1's four examples ------------------------------------------------------------------------


def _diagnostic(**fields: Any) -> Diagnostic:
    values: dict[str, Any] = {
        "tool": "sany",
        "severity": "error",
        "message": "Unknown operator: `y'.",
        "module": "SemErr",
        "file": str(CWD / "SemErr.tla"),
        "location": Location("SemErr", 4, 13, 4, 13),
    }
    values.update(fields)
    return Diagnostic(**values)


PARSE = _diagnostic(
    message='Was expecting "Expression or Instance"; Encountered "Beginning of definition" at line 4, column 9 '
    'and token "=="',
    module="ParseErr",
    file=str(CWD / "ParseErr.tla"),
    location=Location("ParseErr", 4, 9, None, None),
    details=("Definition starting at line 4, column 1.", "Module body starting at line 3, column 1."),
)
MISSING = _diagnostic(
    message="Cannot find source file for module NoSuchModule imported in module MissingMod.",
    module=None,
    file=None,
    location=None,
)
WARNING = _diagnostic(
    severity="warning",
    message="The PlusCal algorithm in module Pcal has changed since its last translation.",
    module="Pcal",
    file=str(CWD / "Pcal.tla"),
    location=None,
)


def test_format_diagnostic_with_a_location() -> None:
    lines = format_diagnostic(_diagnostic(), cwd=CWD, spec=CWD / "SemErr.tla", source_text=None)
    assert lines == ["SemErr.tla:4:13: error: Unknown operator: `y'."]


def test_format_diagnostic_of_a_parse_error_puts_the_details_under_it() -> None:
    lines = format_diagnostic(PARSE, cwd=CWD, spec=CWD / "ParseErr.tla", source_text=None)
    assert lines == [
        'ParseErr.tla:4:9: error: Was expecting "Expression or Instance"; Encountered "Beginning of definition" '
        'at line 4, column 9 and token "=="',
        "  Definition starting at line 4, column 1.",
        "  Module body starting at line 3, column 1.",
    ]


def test_format_diagnostic_with_no_location_has_no_line_and_column() -> None:
    lines = format_diagnostic(MISSING, cwd=CWD, spec=CWD / "MissingMod.tla", source_text=None)
    assert lines == [
        "MissingMod.tla: error: Cannot find source file for module NoSuchModule imported in module MissingMod."
    ]


def test_format_diagnostic_of_a_warning() -> None:
    lines = format_diagnostic(WARNING, cwd=CWD, spec=CWD / "Pcal.tla", source_text=None)
    assert lines == ["Pcal.tla: warning: The PlusCal algorithm in module Pcal has changed since its last translation."]


def test_format_diagnostic_of_a_module_that_was_not_announced_names_the_spec() -> None:
    lines = format_diagnostic(_diagnostic(file=None), cwd=CWD, spec=CWD / "sub" / "Spec.tla", source_text=None)
    assert lines == [f"{Path('sub') / 'Spec.tla'}:4:13: error: Unknown operator: `y'."]


def test_format_diagnostic_with_the_source_gives_the_line_the_excerpt_then_the_details() -> None:
    source = "---- MODULE ParseErr ----\nEXTENDS Naturals\nVARIABLE x\nInit == == 1\n====\n"
    lines = format_diagnostic(PARSE, cwd=CWD, spec=CWD / "ParseErr.tla", source_text=source)
    assert lines[0].startswith("ParseErr.tla:4:9: error: Was expecting")
    assert lines[1:] == [
        "     2 | EXTENDS Naturals",
        "     3 | VARIABLE x",
        "     4 | Init == == 1",
        "       |         ^",
        "       | Error here: line 4, col 9",
        "     5 | ====",
        "  Definition starting at line 4, column 1.",
        "  Module body starting at line 3, column 1.",
    ]
    first = format_diagnostic(_diagnostic(), cwd=CWD, spec=CWD / "SemErr.tla", source_text=SEMERR)
    assert first == [
        "SemErr.tla:4:13: error: Unknown operator: `y'.",
        *source_excerpt(SEMERR, Location("SemErr", 4, 13, 4, 13)),
    ]


# --- source_excerpt: S1's unit test --------------------------------------------------------------------------------


def test_source_excerpt_on_line_4_is_s1s_example() -> None:
    assert source_excerpt(SEMERR, Location("SemErr", 4, 13, 4, 13)) == [
        "     2 | EXTENDS Naturals",
        "     3 | VARIABLE x",
        "     4 | Init == x = y",
        "       |             ^",
        "       | Error here: line 4, col 13 to 13",
        "     5 | Next == x' = x + 1 + Foo(2)",
        "     6 | ====",
    ]
    assert source_excerpt(SEMERR, Location("SemErr", 5, 22, 5, 24)) == [
        "     3 | VARIABLE x",
        "     4 | Init == x = y",
        "     5 | Next == x' = x + 1 + Foo(2)",
        "       |                      ^^^",
        "       | Error here: line 5, col 22 to 24",
        "     6 | ====",
    ]


def test_source_excerpt_on_line_1_has_that_line_alone_before_the_marks() -> None:
    assert source_excerpt(SEMERR, Location("SemErr", 1, 6, 1, 11)) == [
        "     1 | ---- MODULE SemErr ----",
        "       |      ^^^^^^",
        "       | Error here: line 1, col 6 to 11",
        "     2 | EXTENDS Naturals",
        "     3 | VARIABLE x",
    ]


def test_source_excerpt_over_two_lines_marks_to_the_end_of_the_first() -> None:
    assert source_excerpt(SEMERR, Location("SemErr", 4, 13, 5, 2)) == [
        "     2 | EXTENDS Naturals",
        "     3 | VARIABLE x",
        "     4 | Init == x = y",
        "       |             ^",
        "       | Error here: line 4, col 13 to line 5, col 2",
        "     5 | Next == x' = x + 1 + Foo(2)",
        "     6 | ====",
    ]
    assert source_excerpt(SEMERR, Location("SemErr", 4, 9, 5, 2))[3] == "       |         ^^^^^"


def test_source_excerpt_with_no_end_has_one_mark() -> None:
    assert source_excerpt(SEMERR, Location("SemErr", 4, 13, None, None))[3:5] == [
        "       |             ^",
        "       | Error here: line 4, col 13",
    ]


def test_source_excerpt_copies_a_tab_in_front_of_the_column() -> None:
    text = "---- MODULE T ----\n\tInit == y\n====\n"
    assert source_excerpt(text, Location("T", 2, 10, 2, 10)) == [
        "     1 | ---- MODULE T ----",
        "     2 | \tInit == y",
        "       | \t        ^",
        "       | Error here: line 2, col 10 to 10",
        "     3 | ====",
    ]


def test_source_excerpt_at_the_last_line_has_no_lines_after() -> None:
    assert source_excerpt(SEMERR, Location("SemErr", 6, 1, 6, 4)) == [
        "     4 | Init == x = y",
        "     5 | Next == x' = x + 1 + Foo(2)",
        "     6 | ====",
        "       | ^^^^",
        "       | Error here: line 6, col 1 to 4",
    ]


def test_source_excerpt_of_a_line_past_the_end_is_nothing() -> None:
    assert source_excerpt(SEMERR, Location("SemErr", 7, 1, 7, 2)) == []
    assert source_excerpt("", Location("SemErr", 1, 1, 1, 1)) == []


# --- result_line: each row of O3's table ---------------------------------------------------------------------------


def _outcome(code: int | None = 0, **fields: Any) -> RunOutcome:
    values: dict[str, Any] = {
        "result": None,
        "exit_code": 0 if code is None else code,
        "tool_exit_code": code,
        "stopped_by": None,
        "stderr_tail": (),
        "warnings": (),
        "run_folder_kept": None,
        "resume_command": None,
        "dropped_checkpoint": None,
        "stopped_for_closed_pipe": False,
        "kept": None,
    }
    values.update(fields)
    return RunOutcome(**values)


def _error(kind: ErrorKind) -> TlcError:
    return TlcError(kind=kind, name=None, message=TlcMessage(1000, 1, "GENERAL", ("x",)), related=[], trace=None)


def _result(verdict: Verdict, **fields: Any) -> RunResult:
    return RunResult(verdict=verdict, **fields)


def test_result_line_errors() -> None:
    result = _result(Verdict.ERRORS, duration_ms=700, errors=[_error(ErrorKind.INVARIANT)])
    assert result_line(_outcome(12), result, 99.0) == (
        "Result: errors found (TLC exit code 12: an invariant was violated) in 0.7 s"
    )


def test_result_line_errors_with_exit_code_0() -> None:
    result = _result(Verdict.ERRORS, duration_ms=1500, errors=[_error(ErrorKind.INVARIANT)] * 2)
    assert result_line(_outcome(0), result, 1.0) == "Result: errors found (TLC exit code 0) in 1.5 s"


def test_result_line_no_error() -> None:
    assert result_line(_outcome(0), _result(Verdict.NO_ERROR, duration_ms=4200), 1.0) == (
        "Result: no error found, every state checked (TLC exit code 0) in 4.2 s"
    )


def test_result_line_no_error_bounded_names_the_search() -> None:
    simulation = _result(Verdict.NO_ERROR_BOUNDED, mode="simulate", duration_ms=60000)
    assert result_line(_outcome(0), simulation, 1.0) == (
        "Result: no error found in a bounded search (simulation) (TLC exit code 0) in 1 min 00 s"
    )
    dfid = _result(Verdict.NO_ERROR_BOUNDED, mode="depth-first", duration_ms=2000)
    assert result_line(_outcome(0), dfid, 1.0) == (
        "Result: no error found in a bounded search (depth-first) (TLC exit code 0) in 2.0 s"
    )


def test_result_line_falls_back_to_the_reporters_clock() -> None:
    assert result_line(_outcome(0), _result(Verdict.NO_ERROR), 45.2) == (
        "Result: no error found, every state checked (TLC exit code 0) in 45 s"
    )


@pytest.mark.parametrize(
    ("kind", "code", "words"),
    [
        (
            ErrorKind.PARSE,
            150,
            "the spec has errors (TLC exit code 150: the spec does not parse, or fails SANY's semantic checks)",
        ),
        (
            ErrorKind.CONFIG,
            151,
            "the configuration has errors (TLC exit code 151: the cfg file is missing or wrong)",
        ),
        (
            ErrorKind.USAGE,
            1,
            "TLC refused its arguments (TLC exit code 1: TLC rejected its command line, or the JVM "
            "could not start it for an option it does not accept or a main class it cannot find)",
        ),
        (
            ErrorKind.EXCEPTION,
            255,
            "TLC failed before computing the initial states (TLC exit code 255: TLC stopped on "
            "an error it does not classify; its output above says what went wrong)",
        ),
        (
            ErrorKind.OTHER,
            255,
            "TLC failed before computing the initial states (TLC exit code 255: TLC stopped on "
            "an error it does not classify; its output above says what went wrong)",
        ),
    ],
)
def test_result_line_not_checked_by_the_first_errors_kind(kind: ErrorKind, code: int, words: str) -> None:
    result = _result(Verdict.NOT_CHECKED, duration_ms=300, errors=[_error(kind)])
    assert result_line(_outcome(code), result, 1.0) == f"Result: not checked: {words}"


def test_result_line_not_checked_by_a_sany_error_with_no_error() -> None:
    result = _result(Verdict.NOT_CHECKED, sany=[_diagnostic()])
    assert result_line(_outcome(150), result, 1.0).startswith("Result: not checked: the spec has errors (TLC exit")


def test_result_line_incomplete() -> None:
    result = _result(Verdict.INCOMPLETE, duration_ms=500)
    assert result_line(_outcome(130, stopped_by="int"), result, 133.0) == (
        "Result: incomplete, interrupted after 2 min 13 s"
    )
    assert result_line(_outcome(141, stopped_for_closed_pipe=True), result, 3.0) == (
        "Result: incomplete, stopped because the output was closed"
    )
    assert result_line(_outcome(255), result, 3.0) == (
        "Result: incomplete, TLC stopped without finishing (TLC exit code 255: TLC stopped on an error it does not "
        "classify; its output above says what went wrong)"
    )


def test_result_line_of_a_code_x1_does_not_document() -> None:
    result = _result(Verdict.INCOMPLETE)
    assert result_line(_outcome(99), result, 1.0) == (
        "Result: incomplete, TLC stopped without finishing "
        "(TLC exit code 99: TLC ended with a code tlaup does not know)"
    )


@pytest.mark.parametrize(("code", "name"), [(130, "SIGINT"), (137, "SIGKILL"), (143, "SIGTERM"), (200, "72")])
def test_result_line_of_a_code_above_128_names_the_signal(code: int, name: str) -> None:
    result = _result(Verdict.INCOMPLETE)
    assert result_line(_outcome(code), result, 1.0) == (
        f"Result: incomplete, TLC stopped without finishing (TLC exit code {code}: Java was stopped by a signal "
        f"({name}))"
    )


def test_result_line_when_tlc_was_asked_for_its_help() -> None:
    result = _result(Verdict.INCOMPLETE)
    assert (
        result_line(_outcome(1, asked_for_help=True), result, 1.0) == "Result: TLC printed its help (TLC exit code 1)"
    )
    # Not when TLC exited with another code, nor when a signal or a closed pipe stopped the run, nor unasked.
    assert result_line(_outcome(1), result, 1.0).startswith("Result: incomplete, TLC stopped without finishing")
    assert result_line(_outcome(255, asked_for_help=True), result, 1.0).startswith("Result: incomplete, TLC stopped")
    assert result_line(_outcome(130, asked_for_help=True, stopped_by="int"), result, 3.0) == (
        "Result: incomplete, interrupted after 3.0 s"
    )
    closed = _outcome(1, asked_for_help=True, stopped_for_closed_pipe=True)
    assert result_line(closed, result, 3.0) == "Result: incomplete, stopped because the output was closed"


def test_result_line_of_a_false_postcondition() -> None:
    result = _result(Verdict.ERRORS, duration_ms=100, errors=[_error(ErrorKind.POSTCONDITION)])
    assert result_line(_outcome(10), result, 1.0) == (
        "Result: errors found (TLC exit code 10: a postcondition was false) in 0.1 s"
    )
    assumption = _result(Verdict.ERRORS, duration_ms=100, errors=[_error(ErrorKind.ASSUMPTION)])
    assert "(TLC exit code 10: an assumption in the spec is false)" in result_line(_outcome(10), assumption, 1.0)


def test_result_line_suffixes() -> None:
    resumed = _result(Verdict.NO_ERROR, duration_ms=100, resumed=True)
    assert result_line(_outcome(0), resumed, 1.0).endswith("in 0.1 s; resumed from a checkpoint")
    approximate = _result(Verdict.NO_ERROR, duration_ms=100, resumed=True, counts_approximate=True)
    assert result_line(_outcome(0), approximate, 1.0).endswith("; resumed from a checkpoint, state counts approximate")
    plain = _result(Verdict.NO_ERROR, duration_ms=100)
    assert result_line(_outcome(0, dropped_checkpoint="not-asked"), plain, 1.0).endswith(
        "; a checkpoint was not kept (use --keep to keep one)"
    )
    assert result_line(_outcome(0, dropped_checkpoint="incomplete"), plain, 1.0).endswith(
        "; the checkpoint was incomplete, nothing to resume"
    )
    assert result_line(_outcome(0, dropped_checkpoint="depth-first"), plain, 1.0).endswith(
        "; a -dfid run cannot be resumed"
    )


# --- diff_values ---------------------------------------------------------------------------------------------------


def _changed_texts(old: str, new: str) -> list[str]:
    value = parse_value(new)
    diff = diff_values(parse_value(old), value)
    return [value.text[start:end] for start, end in diff.spans]


def test_diff_values_of_equal_values_is_no_change() -> None:
    diff = diff_values(parse_value("[a |-> 1, b |-> {2}]"), parse_value("[a |-> 1,\n b |-> {2}]"))
    assert not diff.changed
    assert diff.spans == ()


def test_diff_values_with_nothing_before_is_all_new() -> None:
    value = parse_value("<<1, 2>>")
    assert diff_values(None, value).spans == ((0, len(value.text)),)


def test_diff_values_on_sets() -> None:
    assert _changed_texts("{1, 2}", "{1, 2, 13}") == ["13"]
    assert _changed_texts("{1, 2}", "{1}") == ["{1}"]  # a removal: the whole value


def test_diff_values_on_sequences() -> None:
    assert _changed_texts("<<1, 2, 3>>", "<<1, 5, 3>>") == ["5"]
    assert _changed_texts("<<1>>", "<<1, 2, 3>>") == ["2", "3"]
    assert _changed_texts("<<1, 2>>", "<<2>>") == ["<<2>>"]


def test_diff_values_on_records() -> None:
    assert _changed_texts("[a1 |-> 1, b |-> 1]", "[a1 |-> 1, b |-> 2]") == ["2"]
    assert _changed_texts('[op |-> "add", n |-> 1]', '[op |-> "del", n |-> 1]') == ['"del"']
    assert _changed_texts("[a |-> 1]", "[b |-> 1]") == ["[b |-> 1]"]


def test_diff_values_on_functions() -> None:
    assert _changed_texts("(1 :> 0 @@ 2 :> 0)", "(1 :> 0 @@ 2 :> 1)") == ["1"]
    assert diff_values(parse_value("(1 :> 0 @@ 2 :> 0)"), parse_value("(1 :> 0 @@ 2 :> 1)")).spans == ((16, 17),)


def test_diff_values_on_raw_values_compares_the_text() -> None:
    old, new = parse_value("[x \\in S |-> 1]"), parse_value("[x \\in T |-> 1]")
    assert old.kind == new.kind == "raw"
    assert diff_values(old, new).changed
    assert not diff_values(old, parse_value("[x \\in S |-> 1]")).changed


def test_diff_values_nested() -> None:
    old = "[alpha |-> {}, beta |-> {}, gamma |-> {}]"
    assert _changed_texts(old, "[alpha |-> {1}, beta |-> {}, gamma |-> {}]") == ["1"]


def test_render_value_diff_styles_only_the_changed_parts() -> None:
    value = parse_value("<<1, 5, 3>>")
    rendered = render_value_diff(value.text, diff_values(parse_value("<<1, 2, 3>>"), value), "yellow")
    assert rendered.plain == "<<1, 5, 3>>"
    assert [(span.start, span.end, span.style) for span in rendered.spans] == [(5, 6, "yellow")]
