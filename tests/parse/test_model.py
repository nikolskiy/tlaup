"""The result model of ``tlaup_parse`` (design 10 P3, package 09): the dictionary form, defaults and readers.

The messages here are built from made-up lines on purpose: real output is tested against the captures by the
framing and parser packages (01 T12 rule 3).
"""

from __future__ import annotations

import dataclasses
import json
import typing

import tlaup_parse
from tlaup_parse import (
    CoverageItem,
    Diagnostic,
    ErrorKind,
    Event,
    FinalStats,
    Location,
    Phase,
    Progress,
    RunResult,
    Status,
    TlcError,
    TlcMessage,
    ToolInfo,
    Trace,
    TraceState,
    Value,
    Variable,
    Verdict,
)


def _values() -> list[Value]:
    """A value of each kind, nested where the kind holds others."""
    one = Value(kind="int", text="1", scalar=1)
    yes = Value(kind="bool", text="TRUE", scalar=True)
    word = Value(kind="string", text='"a"', scalar="a")
    model = Value(kind="model", text="m1", scalar="m1")
    return [
        one,
        yes,
        word,
        model,
        Value(kind="set", text="{1, TRUE}", items=(one, yes)),
        Value(kind="seq", text='<<"a">>', items=(word,)),
        Value(kind="record", text="[x |-> 1]", fields=(("x", one),)),
        Value(kind="function", text="(m1 :> 1)", pairs=((model, one),)),
        Value(kind="interval", text="1..3", bounds=(1, 3)),
        Value(kind="raw", text="SUBSET S", scalar="SUBSET S"),
    ]


def _location(line: int = 1) -> Location:
    return Location(module="M", line=line, column=2, end_line=line + 1, end_column=4)


def _full_result() -> RunResult:
    """A result in which every type and every optional branch occurs."""
    nested = TlcMessage(code=1000, severity=0, name="NESTED", body=("n",), before=": ", after=",")
    opened = TlcMessage(code=2110, severity=1, name="INVARIANT", body=("a", nested, "b"))
    truncated = TlcMessage(code=2103, severity=1, name=None, body=("c",), truncated=True)
    state_message = TlcMessage(code=2217, severity=4, name="STATE", body=("1: <Initial predicate>", "x = 1"))
    variables = tuple(
        Variable(name=f"v{i}", value=value, raw=value.text, printed=i % 2 == 0) for i, value in enumerate(_values())
    )
    states = [
        TraceState(
            index=1,
            action=None,
            location=None,
            header="1: <Initial predicate>",
            variables=variables,
            lines=("1: <Initial predicate>", ""),
        ),
        TraceState(index=2, action="Next", location=_location(3), header="2: <Next>", variables=(), lines=()),
    ]
    with_trace = TlcError(
        kind=ErrorKind.INVARIANT,
        name="Inv",
        message=opened,
        related=[truncated],
        trace=Trace(states=states, loop_to=1, stuttering=False),
    )
    without_trace = TlcError(kind=ErrorKind.OTHER, name=None, message=truncated, related=[], trace=None)
    return RunResult(
        tool=ToolInfo(version="2.19", revision="5a47802", date="08 August 2024", line="stable", raw="TLC2 ..."),
        mode="exhaustive search",
        workers=1,
        phase=Phase.FINISHED,
        status=Status.FAILURE,
        verdict=Verdict.ERRORS,
        resumed=True,
        counts_approximate=True,
        errors=[with_trace, without_trace],
        warnings=[TlcMessage(code=2262, severity=3, name=None, body=())],
        sany=[
            Diagnostic(
                tool="sany",
                severity="error",
                message="m",
                module="M",
                file="M.tla",
                location=_location(),
                details=("d1", "d2"),
            ),
            Diagnostic(tool="pcal", severity="warning", message="w", module=None, file=None, location=None),
        ],
        module_files={"M": "M.tla"},
        overrides_loaded=["C.op"],
        progress=[Progress(diameter=1, generated=2, distinct=3, queue=-1, at="2026-11-14 22:26:52")],
        stats=FinalStats(
            total_states=10,
            distinct_states=5,
            queue=0,
            state_depth=3,
            collision_probability="1.0E-18",
            outdegree="The average outdegree ...",
        ),
        coverage=[
            CoverageItem(
                kind="action",
                name="Next",
                location=_location(),
                sub_location=_location(6),
                count=4,
                distinct=2,
                depth=0,
            ),
            CoverageItem(
                kind="expression",
                name=None,
                location=_location(),
                sub_location=None,
                count=None,
                distinct=None,
                depth=2,
            ),
        ],
        output=["out"],
        output_dropped=2,
        unframed_lines=1,
        sany_lines_used=7,
        unknown_messages=[state_message],
        info=[TlcMessage(code=2212, severity=0, name="INFO", body=("i",))],
        started="2026-11-14 22:26:52",
        finished="2026-11-14 22:26:53",
        duration_ms=1000,
    )


def _only_json_types(data: object, where: str = "result") -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            assert isinstance(key, str), f"{where}: key {key!r}"
            _only_json_types(value, f"{where}.{key}")
    elif isinstance(data, list):
        for index, item in enumerate(data):
            _only_json_types(item, f"{where}[{index}]")
    else:
        assert data is None or type(data) in (str, int, bool), f"{where}: {type(data).__name__} {data!r}"


# --- The dictionary form --------------------------------------------------------------------------------------


def test_to_dict_holds_only_json_types() -> None:
    data = _full_result().to_dict()
    _only_json_types(data)
    json.dumps(data)


def test_round_trip_of_a_full_result() -> None:
    result = _full_result()
    assert RunResult.from_dict(result.to_dict()) == result
    assert RunResult.from_dict(json.loads(json.dumps(result.to_dict()))) == result


def test_round_trip_of_a_fresh_result() -> None:
    assert RunResult.from_dict(RunResult().to_dict()) == RunResult()


def test_round_trip_keeps_value_text() -> None:
    result = RunResult.from_dict(_full_result().to_dict())
    trace = result.errors[0].trace
    assert trace is not None
    assert [variable.value.text for variable in trace.states[0].variables] == [value.text for value in _values()]
    function = trace.states[0].variables[7].value
    assert function.pairs[0][0].text == "m1"


def test_every_field_is_written_even_when_empty() -> None:
    data = RunResult().to_dict()
    assert list(data) == [
        "tool",
        "mode",
        "workers",
        "phase",
        "status",
        "verdict",
        "resumed",
        "counts_approximate",
        "errors",
        "warnings",
        "sany",
        "module_files",
        "overrides_loaded",
        "progress",
        "stats",
        "coverage",
        "output",
        "output_dropped",
        "unframed_lines",
        "sany_lines_used",
        "unknown_messages",
        "info",
        "started",
        "finished",
        "duration_ms",
    ]
    assert Diagnostic(tool="sany", severity="error", message="m", module=None, file=None, location=None).to_dict() == {
        "tool": "sany",
        "severity": "error",
        "message": "m",
        "module": None,
        "file": None,
        "location": None,
        "details": [],
    }


def test_final_stats_keys() -> None:
    stats = FinalStats(
        total_states=1, distinct_states=2, queue=3, state_depth=4, collision_probability=None, outdegree=None
    )
    assert stats.to_dict() == {
        "totalStates": 1,
        "distinctStates": 2,
        "queue": 3,
        "stateDepth": 4,
        "collision_probability": None,
        "outdegree": None,
    }


def test_enum_words() -> None:
    verdicts = {
        Verdict.ERRORS: "errors",
        Verdict.NO_ERROR: "no-error",
        Verdict.NO_ERROR_BOUNDED: "no-error-bounded",
        Verdict.INCOMPLETE: "incomplete",
        Verdict.NOT_CHECKED: "not-checked",
    }
    statuses = {
        Status.RUNNING: "running",
        Status.SUCCESS: "success",
        Status.FAILURE: "failure",
        Status.INTERRUPTED: "interrupted",
    }
    phases = {
        Phase.NOT_STARTED: "not-started",
        Phase.PARSING: "parsing",
        Phase.STARTING: "starting",
        Phase.INITIAL_STATES: "initial-states",
        Phase.CHECKING: "checking",
        Phase.LIVENESS: "liveness",
        Phase.FINISHED: "finished",
    }
    assert len(verdicts) == len(Verdict)
    assert len(statuses) == len(Status)
    assert len(phases) == len(Phase)
    for verdict, text in verdicts.items():
        assert RunResult(verdict=verdict).to_dict()["verdict"] == text
    for status, text in statuses.items():
        assert RunResult(status=status).to_dict()["status"] == text
    for phase, text in phases.items():
        assert RunResult(phase=phase).to_dict()["phase"] == text


def test_error_kind_words() -> None:
    words = [
        "invariant",
        "deadlock",
        "property",
        "assertion",
        "assumption",
        "postcondition",
        "evaluation",
        "config",
        "parse",
        "exception",
        "usage",
        "other",
    ]
    message = TlcMessage(code=1000, severity=1, name=None, body=())
    assert [kind.value for kind in ErrorKind] == words
    for kind in ErrorKind:
        error = TlcError(kind=kind, name=None, message=message, related=[], trace=None)
        assert error.to_dict()["kind"] == kind.value


def test_message_body_and_value_shapes() -> None:
    nested = TlcMessage(code=1000, severity=0, name=None, body=("n",), before=": ")
    message = TlcMessage(code=2110, severity=1, name="X", body=("a", nested))
    assert message.to_dict()["body"] == ["a", nested.to_dict()]
    one = Value(kind="int", text="1", scalar=1)
    record = Value(kind="record", text="[x |-> 1]", fields=(("x", one),)).to_dict()
    assert record["fields"] == [["x", one.to_dict()]]
    function = Value(kind="function", text="(1 :> 1)", pairs=((one, one),)).to_dict()
    assert function["pairs"] == [[one.to_dict(), one.to_dict()]]
    assert Value(kind="interval", text="1..3", bounds=(1, 3)).to_dict()["bounds"] == [1, 3]
    assert one.to_dict()["bounds"] is None


# --- Value equality -------------------------------------------------------------------------------------------


def test_value_equality_ignores_text() -> None:
    assert Value(kind="int", text="1", scalar=1) == Value(kind="int", text=" 1 ", scalar=1)
    assert Value(kind="raw", text="a", scalar="a") != Value(kind="raw", text="a", scalar="b")


# --- TlcMessage's readers -------------------------------------------------------------------------------------


def test_lines_and_nested_keep_order() -> None:
    first = TlcMessage(code=1, severity=0, name=None, body=("x",))
    second = TlcMessage(code=2, severity=0, name=None, body=("y",))
    message = TlcMessage(code=3, severity=1, name=None, body=("a", first, "b", second, "c"))
    assert message.lines == ("a", "b", "c")
    assert message.nested == (first, second)


def test_text_lines_puts_before_and_after_around_a_nested_message() -> None:
    nested = TlcMessage(code=1, severity=0, name=None, body=("b", "c"), before="<", after=">")
    message = TlcMessage(code=2, severity=1, name=None, body=("a", nested, "d"), before="x", after="y")
    assert message.text_lines() == ("a", "<b", "c>", "d")


def test_text_lines_two_deep() -> None:
    inner = TlcMessage(code=1, severity=0, name=None, body=("c",), before="(", after=")")
    middle = TlcMessage(code=2, severity=0, name=None, body=("b", inner), before="[", after="]")
    outer = TlcMessage(code=3, severity=1, name=None, body=("a", middle))
    assert outer.text_lines() == ("a", "[b", "(c)]")


def test_text_lines_of_a_nested_message_without_lines() -> None:
    marked = TlcMessage(code=1, severity=0, name=None, body=(), before="<", after=">")
    blank = TlcMessage(code=2, severity=0, name=None, body=())
    message = TlcMessage(code=3, severity=1, name=None, body=("a", marked, blank, "b"))
    assert message.text_lines() == ("a", "<>", "b")


# --- Defaults and the events ----------------------------------------------------------------------------------


def test_defaults_of_a_fresh_result() -> None:
    result = RunResult()
    for name in ("tool", "mode", "workers", "stats", "started", "finished", "duration_ms"):
        assert getattr(result, name) is None, name
    for name in (
        "errors",
        "warnings",
        "sany",
        "module_files",
        "overrides_loaded",
        "progress",
        "coverage",
        "output",
        "unknown_messages",
        "info",
    ):
        assert not getattr(result, name), name
    assert result.module_files == {}
    assert (result.output_dropped, result.unframed_lines, result.sany_lines_used) == (0, 0, 0)
    assert (result.resumed, result.counts_approximate) == (False, False)
    assert result.phase is Phase.NOT_STARTED
    assert result.status is Status.RUNNING
    assert result.verdict is Verdict.INCOMPLETE
    assert RunResult().errors is not result.errors  # each result has its own lists


def test_event_union_has_the_twenty_members() -> None:
    names = [
        "VersionSeen",
        "ModeSeen",
        "PhaseChanged",
        "ProgressMade",
        "OutputLine",
        "DiagnosticFound",
        "ErrorOpened",
        "ErrorExtended",
        "TraceStateAdded",
        "TraceClosed",
        "WarningFound",
        "OverrideLoaded",
        "CoverageAdded",
        "StatsUpdated",
        "CheckpointStarted",
        "CheckpointWritten",
        "Recovered",
        "Information",
        "UnknownMessage",
        "Finished",
    ]
    members = typing.get_args(Event)
    assert [member.__name__ for member in members] == names
    assert all(getattr(tlaup_parse, name) is member for name, member in zip(names, members, strict=True))


# Each event's fields, in order, as package 09's code block gives them.
EVENT_FIELDS = {
    "VersionSeen": ["message", "tool"],
    "ModeSeen": ["message", "mode", "workers"],
    "PhaseChanged": ["message", "phase"],
    "ProgressMade": ["message", "progress"],
    "OutputLine": ["line"],
    "DiagnosticFound": ["diagnostic"],
    "ErrorOpened": ["message", "error"],
    "ErrorExtended": ["message", "error"],
    "TraceStateAdded": ["message", "error", "state"],
    "TraceClosed": ["message", "error", "trace"],
    "WarningFound": ["message"],
    "OverrideLoaded": ["message", "operator", "java_class"],
    "CoverageAdded": ["message", "item"],
    "StatsUpdated": ["message", "stats"],
    "CheckpointStarted": ["message", "folder"],
    "CheckpointWritten": ["message"],
    "Recovered": ["message", "examined", "queued"],
    "Information": ["message"],
    "UnknownMessage": ["message"],
    "Finished": ["message", "duration_ms", "finished"],
}


def test_event_fields_follow_the_package() -> None:
    members = typing.get_args(Event)
    assert [member.__name__ for member in members] == list(EVENT_FIELDS)
    for member in members:
        assert dataclasses.is_dataclass(member)
        assert member.__dataclass_params__.frozen, member.__name__  # type: ignore[attr-defined]
        assert [f.name for f in dataclasses.fields(member)] == EVENT_FIELDS[member.__name__], member.__name__
