"""Hand-written facts about the TLC golden captures, read from the files before the parser existed.

Design 01 T3 ("Two kinds of expectation", item 1) and 10 P1; package 08. A fact is one exact assertion on the
``RunResult`` of one case, on the release lines it holds for; ``test_facts.py`` runs every fact on every build
folder of those lines, and the integration tests (01 T9) run the same facts against live TLC runs.

Rules the facts follow (package 08, "Facts must hold for a live run too"):

- Never a time, a duration, a date, a pid, a seed, an ``fp`` number, heap sizes, rates, intermediate progress
  counts, or a path with ``<tmp>`` or ``<repo>`` in it; a file is asserted by its name.
- Final state counts only for a complete exhaustive search.
- Keyed by case, and by case and line where the two lines differ; never by an exact build.
- Each fact names the capture lines it was read from, as ``v1.7.4:N`` (``tlc/v1.7.4/<case>.out``) and
  ``rolling:N`` (``tlc/2026.11.15.002146/<case>.out``).

This module imports nothing from ``tlaup_parse`` at run time, so that it loads while the parser does not exist,
and nothing from pytest, so that the integration tests can use it. Names follow 10 P3 and package 09's model.
Enums are compared by member name for ``Status``, ``Verdict`` and ``Phase`` (package 09 names the members) and
by the dictionary value for ``ErrorKind`` (package 09 gives only the values).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from tests.parse.drive import build_folders, line_of, read_lines

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from tlaup_parse import CoverageItem, Diagnostic, Location, RunResult, TlcError, TlcMessage, Trace, Value, Variable

    Check = Callable[[RunResult], None]
    Loc = tuple[str, int, int, int | None, int | None]
    # (variable name, expected plain value, printed): printed is False where -difftrace left it out (P5)
    Var = tuple[str, object, bool]
    Row = tuple[str | None, Loc | None, Sequence[Var]]  # (action, location, variables) of one state

LINES = frozenset({"stable", "rolling"})  # the two values of `line` in build.toml (01 T3)
STABLE = frozenset({"stable"})
ROLLING = frozenset({"rolling"})
TOPICS = ("run", "errors", "sany", "traces")


@dataclass(frozen=True)
class Fact:
    case: str  # a case of cases.toml, e.g. "violation"
    topic: str  # "run", "errors", "sany" or "traces" (package 08's table)
    name: str  # short and unique within the case, e.g. "four-states"
    check: Check  # raises AssertionError with a message that names what differs
    lines: frozenset[str] = LINES  # the release lines it holds for; never an exact build (T3)

    @property
    def id(self) -> str:
        return f"{self.case}:{self.topic}:{self.name}"


_FACTS: list[Fact] = []


def add(case: str, topic: str, name: str, check: Check, lines: frozenset[str] = LINES) -> None:
    """Register one fact."""
    if topic not in TOPICS:
        msg = f"unknown topic {topic!r} for {case}:{name}"
        raise ValueError(msg)
    _FACTS.append(Fact(case, topic, name, check, lines))


def fact(case: str, topic: str, name: str, lines: frozenset[str] = LINES) -> Callable[[Check], Check]:
    """Register the decorated function as a fact."""

    def register(check: Check) -> Check:
        add(case, topic, name, check, lines)
        return check

    return register


# --- Assertion helpers ------------------------------------------------------------------------------------------


def _same(what: str, actual: object, expected: object) -> None:
    if actual != expected:
        msg = f"{what}: expected {expected!r}, got {actual!r}"
        raise AssertionError(msg)


def _holds(what: str, condition: bool, actual: object) -> None:
    if not condition:
        msg = f"{what}: got {actual!r}"
        raise AssertionError(msg)


def _name(member: object) -> str:
    """An enum member's name (Status, Verdict, Phase); anything that is not an enum member fails."""
    if not isinstance(member, Enum):
        msg = f"expected an enum member, got {member!r}"
        raise AssertionError(msg)  # noqa: TRY004 - a fact reports a mismatch as AssertionError
    return member.name


def _kind(error: TlcError) -> str:
    """An error's kind as its dictionary value (package 09), e.g. ``"invariant"``."""
    return str(error.to_dict()["kind"])


def _loc(location: Location | None) -> Loc | None:
    if location is None:
        return None
    return (location.module, location.line, location.column, location.end_line, location.end_column)


def _error(result: RunResult, index: int) -> TlcError:
    _holds(f"error {index + 1} exists", len(result.errors) > index, len(result.errors))
    return result.errors[index]


def _trace(result: RunResult, index: int) -> Trace:
    trace = _error(result, index).trace
    if trace is None:
        msg = f"error {index + 1}: expected a trace, got none"
        raise AssertionError(msg)
    return trace


def _int(what: str, variable: Variable, value: int) -> None:
    _same(f"{what}: value kind", variable.value.kind, "int")
    _same(f"{what}: value", variable.value.scalar, value)
    _same(f"{what}: printed", variable.printed, True)


def _body_shape(message: TlcMessage) -> list[str | int]:
    """The body as ``"line"`` for a line and the code for a nested message, in order."""
    return ["line" if isinstance(item, str) else item.code for item in message.body]


# --- Builders for the facts every case has ----------------------------------------------------------------------


def _status(word: str) -> Check:
    return lambda r: _same("status", _name(r.status), word)


def _verdict(word: str) -> Check:
    return lambda r: _same("verdict", _name(r.verdict), word)


def _phase(word: str) -> Check:
    return lambda r: _same("phase at the end", _name(r.phase), word)


def _mode(mode: str | None, workers: int | None) -> Check:
    return lambda r: _same("mode and workers", (r.mode, r.workers), (mode, workers))


def _resumed(resumed: bool) -> Check:
    return lambda r: _same("resumed", r.resumed, resumed)


def _no_tool(result: RunResult) -> None:
    _same("tool (no 2262)", result.tool, None)


def _times(started: bool, finished: bool) -> Check:
    """That the start (2185) and the finish (2186: time and duration) are set or not; never their values."""
    # Inventory row R30: start time, finish time and duration read from TLC's messages.

    def check(r: RunResult) -> None:
        _same("started is set", r.started is not None, started)
        _same("finished is set", r.finished is not None, finished)
        _same("duration_ms is set", r.duration_ms is not None, finished)

    return check


def _progress(read: bool) -> Check:
    """That progress (2200, 2209) was read or not; never its counts."""
    # Inventory row R30: progress read from TLC's messages.
    return lambda r: _same("progress was read", len(r.progress) > 0, read)


def _tool_stable(result: RunResult) -> None:
    tool = result.tool
    _holds("a ToolInfo from 2262", tool is not None, tool)
    assert tool is not None  # for the type checker
    _same("tool line", tool.line, "stable")
    _holds("tool version is a numbered release", re.fullmatch(r"\d+\.\d+(\.\d+)?", tool.version) is not None, tool)
    _holds("tool revision", tool.revision is not None and re.fullmatch(r"[0-9a-f]{7,}", tool.revision), tool)
    _holds("tool date is set on a numbered release", tool.date is not None, tool)
    _holds("tool raw line", tool.raw.startswith(f"TLC2 Version {tool.version} of "), tool)
    _same("tool raw line", tool.raw, f"TLC2 Version {tool.version} of {tool.date} (rev: {tool.revision})")


def _tool_rolling(result: RunResult) -> None:
    tool = result.tool
    _holds("a ToolInfo from 2262", tool is not None, tool)
    assert tool is not None  # for the type checker
    _same("tool line", tool.line, "rolling")
    _holds("tool version is a CalVer", re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.\d{6}", tool.version) is not None, tool)
    _holds("tool revision", tool.revision is not None and re.fullmatch(r"[0-9a-f]{7,}", tool.revision), tool)
    _same("tool date", tool.date, None)
    _holds("tool raw line", tool.raw.startswith(f"TLC2 Version {tool.version} (rev: "), tool)
    _same("tool raw line", tool.raw, f"TLC2 Version {tool.version} (rev: {tool.revision})")


def _errors(expected: Sequence[tuple[int, str, str | None]]) -> Check:
    """The errors in order, each as (code of the message that opened it, kind, name)."""
    return lambda r: _same(
        "errors (code, kind, name)", [(e.message.code, _kind(e), e.name) for e in r.errors], list(expected)
    )


def _related(expected: Sequence[Sequence[int]]) -> Check:
    """The codes of each error's related messages, in arrival order."""
    return lambda r: _same(
        "related message codes per error", [[m.code for m in e.related] for e in r.errors], [list(c) for c in expected]
    )


def _shapes(expected: Sequence[tuple[int, int | None, bool] | None]) -> Check:
    """Each error's trace as (number of states, loop_to, stuttering), or None for an error with no trace."""

    def shape(e: TlcError) -> tuple[int, int | None, bool] | None:
        return None if e.trace is None else (len(e.trace.states), e.trace.loop_to, e.trace.stuttering)

    return lambda r: _same("traces (states, loop_to, stuttering)", [shape(e) for e in r.errors], list(expected))


def _diagnostics(count: int) -> Check:
    return lambda r: _same("number of SANY diagnostics", len(r.sany), count)


def _output(lines: Sequence[str]) -> Check:
    return lambda r: _same("output", list(r.output), list(lines))


def _info(codes: Sequence[int]) -> Check:
    return lambda r: _same("info codes", [m.code for m in r.info], list(codes))


def _no_unknown(result: RunResult) -> None:
    _same("unknown message codes", [m.code for m in result.unknown_messages], [])


GC_HINT = 2401  # "Please run the Java VM ... -XX:+UseParallelGC": present or not depending on the JVM options


def _warnings(codes: Sequence[int]) -> Check:
    """The warnings' codes, leaving out the GC hint 2401, which a live run with other JVM options may not print."""
    return lambda r: _same(
        "warning codes (2401 left out)", [m.code for m in r.warnings if m.code != GC_HINT], list(codes)
    )


def _overrides(expected: Sequence[str]) -> Check:
    """The operators of the overrides loaded (2168), by the end of each entry of ``overrides_loaded``.

    An entry is ``"<java_class>.<operator>"`` (10 P3); the class can be a path, which a fact must not assert.
    """

    def check(r: RunResult) -> None:
        _same("number of overrides loaded", len(r.overrides_loaded), len(expected))
        for entry, end in zip(r.overrides_loaded, expected, strict=False):
            _holds(f"override loaded ends with {end!r}", entry.endswith(end), entry)

    return check


def _no_coverage(result: RunResult) -> None:
    _same("coverage rows", list(result.coverage), [])


def _stats(total: int, distinct: int, queue: int, depth: int) -> Check:
    """The final statistics of a complete exhaustive search (2199, 2194)."""

    def check(r: RunResult) -> None:
        s = r.stats
        _holds("final statistics are set", s is not None, s)
        assert s is not None  # for the type checker
        _same(
            "final statistics (total, distinct, queue, depth)",
            (s.total_states, s.distinct_states, s.queue, s.state_depth),
            (total, distinct, queue, depth),
        )

    return check


def basics(
    case: str,
    *,
    lines: frozenset[str] = LINES,
    suffix: str = "",
    status: str,
    verdict: str,
    phase: str = "FINISHED",
    mode: str | None = "exhaustive search",
    workers: int | None = 1,  # relies on package 52 pinning one worker when a case names none
    resumed: bool = False,
    tool: bool = True,
    started: bool = True,
    finished: bool = True,
    progress: bool,
    errors: Sequence[tuple[int, str, str | None]],
    related: Sequence[Sequence[int]],
    traces: Sequence[tuple[int, int | None, bool] | None],
    diagnostics: int = 0,
    output: Sequence[str] | None = (),
    info: Sequence[int] = (),
    warnings: Sequence[int] = (),
    overrides: Sequence[str] = (),
    coverage: bool = False,
    stats: tuple[int, int, int, int] | None = None,
) -> None:
    """Register the facts every case gets (package 08): run, errors, SANY and trace shape, plus the version.

    ``suffix`` keeps the names unique when a case is registered once per line. ``coverage`` true leaves the
    coverage rows to the case's own fact; ``stats`` None asserts no final counts (not a complete search).
    ``output`` None leaves the output to the case's own fact; ``tool`` false asserts there is no 2262.
    """
    run: list[tuple[str, Check]] = [
        ("status", _status(status)),
        ("verdict", _verdict(verdict)),
        ("phase", _phase(phase)),
        ("mode", _mode(mode, workers)),
        ("resumed" if resumed else "not-resumed", _resumed(resumed)),
        ("times", _times(started, finished)),
        ("progress", _progress(progress)),
        ("info", _info(info)),
        ("no-unknown-messages", _no_unknown),
        ("warnings", _warnings(warnings)),
        ("overrides", _overrides(overrides)),
    ]
    if output is not None:
        run.append(("output", _output(output)))
    if not coverage:
        run.append(("no-coverage", _no_coverage))
    if stats is not None:
        run.append(("final-counts", _stats(*stats)))
    for name, check in run:
        add(case, "run", name + suffix, check, lines)
    if not tool:
        add(case, "run", "no-tool" + suffix, _no_tool, lines)
    elif "stable" in lines:
        add(case, "run", "tool-stable", _tool_stable, STABLE)
    if tool and "rolling" in lines:
        add(case, "run", "tool-rolling", _tool_rolling, ROLLING)
    add(case, "errors", "errors" + suffix, _errors(errors), lines)
    add(case, "errors", "related" + suffix, _related(related), lines)
    add(case, "sany", "diagnostics" + suffix, _diagnostics(diagnostics), lines)
    add(case, "traces", "shape" + suffix, _shapes(traces), lines)


def states(
    case: str,
    error: int,
    var: str,
    rows: Sequence[tuple[str | None, Loc | None, int]],
    lines: frozenset[str] = LINES,
    suffix: str = "",
) -> None:
    """Register a fact on the states of error ``error`` (from 0) of a one-variable spec.

    Each row is (action, location, the integer value of ``var``); indexes run from 1.
    """

    def check(r: RunResult) -> None:
        trace = _trace(r, error)
        _same(f"error {error + 1}: number of states", len(trace.states), len(rows))
        for n, (state, (action, location, value)) in enumerate(zip(trace.states, rows, strict=True), 1):
            where = f"error {error + 1}, state {n}"
            _same(f"{where}: index", state.index, n)
            _same(f"{where}: action", state.action, action)
            _same(f"{where}: location", _loc(state.location), location)
            _same(f"{where}: variables", [v.name for v in state.variables], [var])
            _int(f"{where}: {var}", state.variables[0], value)

    add(case, "traces", f"states-{error + 1}{suffix}", check, lines)


def _counting(action: str, location: Loc, values: Iterable[int]) -> list[tuple[str | None, Loc | None, int]]:
    """Rows for a trace whose first state is the initial predicate and every later one the same action."""
    return [(None, None, value) if n == 0 else (action, location, value) for n, value in enumerate(values)]


# --- Values, for the traces of several variables -----------------------------------------------------------------
# A value is compared in a plain form: (kind, payload), with the items, fields or pairs in the order printed.
# ``ANY`` in an expected value matches whatever is there (a value the fact does not assert).

ANY = ...


def _plain(value: Value) -> tuple[object, ...]:
    """A ``Value`` (P7) as nested tuples: ``("int", 1)``, ``("seq", (...))``, ``("record", (("a", ...), ...))``."""
    kind = value.kind
    if kind in ("set", "seq"):
        return (kind, tuple(_plain(item) for item in value.items))
    if kind == "record":
        return (kind, tuple((name, _plain(item)) for name, item in value.fields))
    if kind == "function":
        return (kind, tuple((_plain(key), _plain(item)) for key, item in value.pairs))
    if kind == "interval":
        return (kind, value.bounds)
    return (kind, value.scalar)


def _fits(actual: object, expected: object) -> bool:
    if expected is ANY:
        return True
    if isinstance(expected, tuple):
        return (
            isinstance(actual, tuple)
            and len(actual) == len(expected)
            and all(_fits(a, e) for a, e in zip(actual, expected, strict=True))
        )
    return type(actual) is type(expected) and actual == expected


def vint(n: int) -> tuple[object, ...]:
    return ("int", n)


def vstr(text: str) -> tuple[object, ...]:
    return ("string", text)


def vseq(*items: object) -> tuple[object, ...]:
    return ("seq", items)


def vset(*items: object) -> tuple[object, ...]:
    return ("set", items)


def vrec(**fields: object) -> tuple[object, ...]:
    return ("record", tuple(fields.items()))


def trace_states(case: str, error: int, rows: Sequence[Row], lines: frozenset[str] = LINES, suffix: str = "") -> None:
    """Register a fact on every state of error ``error`` (from 0): index, action, location and each variable."""

    def check(r: RunResult) -> None:
        trace = _trace(r, error)
        _same(f"error {error + 1}: number of states", len(trace.states), len(rows))
        for n, (state, (action, location, variables)) in enumerate(zip(trace.states, rows, strict=True), 1):
            where = f"error {error + 1}, state {n}"
            _same(f"{where}: index", state.index, n)
            _same(f"{where}: action", state.action, action)
            _same(f"{where}: location", _loc(state.location), location)
            _same(f"{where}: variables", [v.name for v in state.variables], [name for name, _, _ in variables])
            for variable, (name, value, printed) in zip(state.variables, variables, strict=True):
                plain = _plain(variable.value)
                _holds(f"{where}: {name} is {value!r}", _fits(plain, value), plain)
                _same(f"{where}: {name} printed", variable.printed, printed)

    add(case, "traces", f"states-{error + 1}{suffix}", check, lines)


def _capture(case: str, line: str) -> list[str]:
    """The lines, without their endings, of the capture of ``case`` in the build folder of release line ``line``.

    Multi-line tool text a fact expects is read from here, never typed (01 T12 rule 3).
    """
    folder = next(f for f in build_folders("tlc") if line_of(f) == line)
    return [text.rstrip("\r\n") for text in read_lines(folder / f"{case}.out")]


def facts_for(case: str, line: str) -> tuple[Fact, ...]:
    """The facts of one case that hold for one release line."""
    return tuple(f for f in FACTS if f.case == case and line in f.lines)


# =================================================================================================================
# Research 1: the twenty cases of each build (tlc/<build>/<case>.out).
# =================================================================================================================

# --- success: Success.tla, no options ---------------------------------------------------------------------------
basics(
    "success",
    status="SUCCESS",  # 2186 and no error: v1.7.4:47, rolling:48
    verdict="NO_ERROR",  # breadth-first (2187 v1.7.4:8, rolling:8), 2186, no error
    progress=True,  # 2200: v1.7.4:35, rolling:36
    errors=[],
    related=[],
    traces=[],
    stats=(26, 16, 0, 7),  # 2199 v1.7.4:39 rolling:40; 2194 v1.7.4:42 rolling:43
)

# --- workers-4: Success.tla, -workers 4 -------------------------------------------------------------------------
basics(
    "workers-4",
    status="SUCCESS",  # 2186: v1.7.4:47, rolling:48
    verdict="NO_ERROR",
    workers=4,  # "with 4 workers": v1.7.4:8, rolling:8
    progress=True,  # 2200: v1.7.4:35, rolling:36
    errors=[],
    related=[],
    traces=[],
    stats=(26, 16, 0, 7),  # 2199 v1.7.4:39 rolling:40; 2194 v1.7.4:42 rolling:43
)

# --- big-states: Big.tla, -workers 4 ----------------------------------------------------------------------------
basics(
    "big-states",
    status="SUCCESS",  # 2186: v1.7.4:51, rolling:52
    verdict="NO_ERROR",
    workers=4,  # v1.7.4:8, rolling:8
    progress=True,  # 2200: v1.7.4:29, rolling:30
    errors=[],
    related=[],
    traces=[],
    stats=(6692791, 2248091, 0, 391),  # 2199 v1.7.4:43 rolling:44; 2194 v1.7.4:46 rolling:47
)

# --- simulate: Success.tla, -simulate num=3 -depth 20 -seed 7 --------------------------------------------------
basics(
    "simulate",
    status="SUCCESS",  # 2186 with no 2193 (P3): v1.7.4:29, rolling:40
    verdict="NO_ERROR_BOUNDED",  # 2188 "Random Simulation": v1.7.4:7, rolling:7
    mode="simulate",
    workers=1,  # "with 1 worker" in 2188 (package 13: 2187, 2188 and 2271 all set workers)
    progress=True,  # 2209: v1.7.4:26, rolling:30 and 33
    info=[2269],  # "Computed 1 initial states...": v1.7.4:23, rolling:24 (P4 rule 3)
    errors=[],
    related=[],
    traces=[],
)

# --- coverage: Success.tla, -coverage 1 -------------------------------------------------------------------------
basics(
    "coverage",
    status="SUCCESS",  # 2186: v1.7.4:119, rolling:126
    verdict="NO_ERROR",
    progress=True,  # 2200: v1.7.4:107, rolling:114
    info=[2201, 2202],  # the coverage frame (P3): v1.7.4:35 and 104, rolling:36 and 111
    errors=[],
    related=[],
    traces=[],
    coverage=True,
    stats=(26, 16, 0, 7),  # 2199 v1.7.4:110 rolling:117; 2194 v1.7.4:113 rolling:120
)

# (kind, name, (line, col, end line, end col), sub_location or None, count, distinct, depth); module Success.
_COVERAGE_COMMON = [
    ("init", "Init", (5, 1, 5, 4), None, 1, 1, 0),  # v1.7.4:39, rolling:46
    ("expression", None, (5, 9, 5, 22), None, 1, None, 0),  # v1.7.4:42, rolling:49
    ("action", "Next", (6, 1, 6, 4), (6, 12, 6, 40), 12, 3, 0),  # v1.7.4:45, rolling:52
    ("expression", None, (6, 12, 6, 16), None, 12, None, 0),  # v1.7.4:48, rolling:55
    ("expression", None, (6, 12, 6, 12), None, 16, None, 1),  # v1.7.4:51, rolling:58
    ("expression", None, (6, 21, 6, 30), None, 12, None, 0),  # v1.7.4:54, rolling:61
    ("expression", None, (6, 35, 6, 40), None, 12, None, 0),  # v1.7.4:57, rolling:64
    ("action", "Next", (6, 1, 6, 4), (7, 12, 7, 40), 12, 12, 0),  # v1.7.4:60, rolling:67
    ("expression", None, (7, 12, 7, 16), None, 12, None, 0),  # v1.7.4:63, rolling:70
    ("expression", None, (7, 12, 7, 12), None, 16, None, 1),  # v1.7.4:66, rolling:73
    ("expression", None, (7, 21, 7, 30), None, 12, None, 0),  # v1.7.4:69, rolling:76
    ("expression", None, (7, 35, 7, 40), None, 12, None, 0),  # v1.7.4:72, rolling:79
    ("action", "Next", (6, 1, 6, 4), (8, 12, 8, 47), 1, 0, 0),  # v1.7.4:75, rolling:82
    ("expression", None, (8, 12, 8, 16), None, 17, None, 0),  # v1.7.4:78, rolling:85
    ("expression", None, (8, 12, 8, 12), None, 16, None, 1),  # v1.7.4:81, rolling:88
    ("expression", None, (8, 21, 8, 25), None, 5, None, 0),  # v1.7.4:84, rolling:91
    ("expression", None, (8, 21, 8, 21), None, 4, None, 1),  # v1.7.4:87, rolling:94
    ("expression", None, (8, 30, 8, 47), None, 1, None, 0),  # v1.7.4:90, rolling:97
    ("property", "TypeOK", (4, 1, 4, 6), None, None, None, 0),  # v1.7.4:93, rolling:100
    ("expression", None, (4, 11, 4, 34), None, 16, None, 0),  # v1.7.4:96, rolling:103
    ("property", "Inv", (10, 1, 10, 3), None, None, None, 0),  # v1.7.4:99, rolling:106
    ("expression", None, (10, 8, 10, 17), None, 16, None, 0),  # v1.7.4:102, rolling:109
]
# 2779, rolling only, before the rest.
_COVERAGE_VARIABLES = [
    ("variable", "x", (3, 11, 3, 11), None, 4, None, 0),  # rolling:40
    ("variable", "y", (3, 14, 3, 14), None, 4, None, 0),  # rolling:43
]


def _coverage_rows(expected: Sequence[tuple[object, ...]]) -> Check:
    def row(item: CoverageItem) -> tuple[object, ...]:
        loc = item.location
        sub = item.sub_location
        return (
            item.kind,
            item.name,
            (loc.line, loc.column, loc.end_line, loc.end_column),
            None if sub is None else (sub.line, sub.column, sub.end_line, sub.end_column),
            item.count,
            item.distinct,
            item.depth,
        )

    def check(r: RunResult) -> None:
        _same("number of coverage rows", len(r.coverage), len(expected))
        for n, (item, want) in enumerate(zip(r.coverage, expected, strict=True), 1):
            _same(f"coverage row {n}", row(item), want)
            _same(f"coverage row {n}: module", item.location.module, "Success")

    return check


# Inventory row R30: coverage read from TLC's messages, on both lines.
add("coverage", "run", "rows-stable", _coverage_rows(_COVERAGE_COMMON), STABLE)
add("coverage", "run", "rows-rolling", _coverage_rows(_COVERAGE_VARIABLES + _COVERAGE_COMMON), ROLLING)


@fact("coverage", "run", "next-rows-differ-in-sub-location")
def _coverage_next_rows(r: RunResult) -> None:
    # The three 2772 rows of Next: v1.7.4:45, 60, 75; rolling:52, 67, 82 (P3: what tells them apart).
    rows = [item for item in r.coverage if item.kind == "action" and item.name == "Next"]
    _same("number of Next rows", len(rows), 3)
    subs = {_loc(item.sub_location) for item in rows}
    _same("distinct sub_locations of the Next rows", len(subs), 3)
    _same("one location for the three Next rows", len({_loc(item.location) for item in rows}), 1)


# --- violation: Violation.tla -----------------------------------------------------------------------------------
basics(
    "violation",
    status="FAILURE",  # error 2110: v1.7.4:33, rolling:34
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:94, rolling:95
    errors=[(2110, "invariant", "Small")],  # "Invariant Small is violated.": v1.7.4:34, rolling:35
    related=[[2121]],  # v1.7.4:36, rolling:37
    traces=[(4, None, False)],  # four 2217: v1.7.4:39-93, rolling:40-92; no 2122, no 2218
)


@fact("violation", "traces", "states")
def _violation_states(r: RunResult) -> None:
    trace = _trace(r, 0)
    loc = ("Violation", 10, 59, 10, 76)
    # Headers: v1.7.4:40, 47, 58, 74; rolling:41, 48, 59, 75.
    expected = [(1, None, None), (2, "Next", loc), (3, "Next", loc), (4, "Next", loc)]
    _same("states (index, action, location)", [(s.index, s.action, _loc(s.location)) for s in trace.states], expected)
    for state in trace.states:
        _same(f"state {state.index}: variables", [v.name for v in state.variables], ["store", "n", "log"])


@fact("violation", "traces", "values")
def _violation_values(r: RunResult) -> None:
    trace = _trace(r, 0)
    _same("number of states", len(trace.states), 4)
    first, second, _, fourth = trace.states
    # State 1, v1.7.4:41-43, rolling:42-44: store = [alpha |-> {}, beta |-> {}, gamma |-> {}], n = 0, log = <<>>.
    store, log = first.variables[0].value, first.variables[2].value
    _same("state 1: store kind", store.kind, "record")
    _same("state 1: store fields", [k for k, _ in store.fields], ["alpha", "beta", "gamma"])
    _same("state 1: store field kinds", [(v.kind, len(v.items)) for _, v in store.fields], [("set", 0)] * 3)
    _int("state 1: n", first.variables[1], 0)
    _same("state 1: log", (log.kind, len(log.items)), ("seq", 0))
    # State 2, v1.7.4:48-54, rolling:49-55: store.alpha = {1}, n = 1, log one record over five lines.
    store, log = second.variables[0].value, second.variables[2].value
    alpha = dict(store.fields)["alpha"]
    _same("state 2: store.alpha", (alpha.kind, [i.scalar for i in alpha.items]), ("set", [1]))
    _int("state 2: n", second.variables[1], 1)
    _same("state 2: log", (log.kind, len(log.items)), ("seq", 1))
    record = log.items[0]
    _same("state 2: log[1] kind", record.kind, "record")
    _same("state 2: log[1] fields", [k for k, _ in record.fields], ["op", "key", "val", "note"])
    fields = dict(record.fields)
    _same("state 2: log[1].op", (fields["op"].kind, fields["op"].scalar), ("string", "add"))
    _same("state 2: log[1].key", (fields["key"].kind, fields["key"].scalar), ("string", "alpha"))
    _same("state 2: log[1].val", (fields["val"].kind, fields["val"].scalar), ("int", 1))
    _same("state 2: log[1].note kind", fields["note"].kind, "string")
    _same("state 2: log raw has its five lines", second.variables[2].raw.count("\n"), 4)
    # State 4, v1.7.4:75-91, rolling:76-92: n = 3, log a sequence of 3 records.
    _int("state 4: n", fourth.variables[1], 3)
    log = fourth.variables[2].value
    _same("state 4: log", (log.kind, [i.kind for i in log.items]), ("seq", ["record"] * 3))


# --- deadlock: Deadlock.tla -------------------------------------------------------------------------------------
basics(
    "deadlock",
    status="FAILURE",  # 2114: v1.7.4:29, rolling:30
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:50, rolling:51
    errors=[(2114, "deadlock", None)],  # "Deadlock reached.": v1.7.4:30, rolling:31
    related=[[2121]],  # v1.7.4:32, rolling:33
    traces=[(3, None, False)],  # v1.7.4:35-48, rolling:36-49
)
# Headers v1.7.4:36, 41, 46; rolling:37, 42, 47.
states("deadlock", 0, "x", _counting("Next", ("Deadlock", 5, 9, 5, 27), [0, 1, 2]))

# --- assertion-failure: Assertion.tla ---------------------------------------------------------------------------
basics(
    "assertion-failure",
    status="FAILURE",  # 2132: v1.7.4:35, rolling:36
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:65, rolling:66
    errors=[(2132, "assertion", None)],
    related=[[2121, 2103]],  # 2121 before the states (v1.7.4:39, rolling:40), 2103 after (v1.7.4:57, rolling:58)
    traces=[(3, None, False)],  # v1.7.4:42-55, rolling:43-56
)
# Headers v1.7.4:43, 48, 53; rolling:44, 49, 54.
states("assertion-failure", 0, "x", _counting("Next", ("Assertion", 5, 9, 6, 21), [0, 1, 2]))

# --- multi-error-continue: MultiError.tla, -continue ------------------------------------------------------------
basics(
    "multi-error-continue",
    status="FAILURE",
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:122, rolling:123
    errors=[
        (2110, "invariant", "InvA"),  # v1.7.4:29-30, rolling:30-31
        (2110, "invariant", "InvB"),  # v1.7.4:50-51, rolling:51-52
        (2114, "deadlock", None),  # v1.7.4:81-82, rolling:82-83
    ],
    related=[[2121], [2121], [2121]],  # v1.7.4:32, 53, 84; rolling:33, 54, 85
    traces=[(3, None, False), (5, None, False), (7, None, False)],  # each error its own trace (P5)
)
_MULTI = ("MultiError", 5, 9, 5, 27)
states("multi-error-continue", 0, "x", _counting("Next", _MULTI, range(3)))  # v1.7.4:35-48, rolling:36-49
states("multi-error-continue", 1, "x", _counting("Next", _MULTI, range(5)))  # v1.7.4:56-79, rolling:57-80
states("multi-error-continue", 2, "x", _counting("Next", _MULTI, range(7)))  # v1.7.4:87-120, rolling:88-121

# --- liveness-back-to-state: LiveBack.tla -----------------------------------------------------------------------
# The two lines differ only in the error's name: v1.7.4 "Temporal properties were violated." (v1.7.4:39),
# rolling "Temporal property Reach was violated." (rolling:40).
for _lines, _suffix, _name_ in ((STABLE, "-stable", None), (ROLLING, "-rolling", "Reach")):
    basics(
        "liveness-back-to-state",
        lines=_lines,
        suffix=_suffix,
        status="FAILURE",  # 2116: v1.7.4:38, rolling:39
        verdict="ERRORS",
        progress=True,  # 2200: v1.7.4:32, rolling:33
        info=[2212],  # v1.7.4:23, rolling:24 (P4: 2212 in info)
        errors=[(2116, "property", _name_)],
        related=[[2264]],  # v1.7.4:42, rolling:43
        traces=[(3, 1, False)],  # three 2217 and 2122 "1: Back to state": v1.7.4:61, rolling:62
    )
# Headers v1.7.4:47, 52, 57; rolling:48, 53, 58.
states("liveness-back-to-state", 0, "x", _counting("Next", ("LiveBack", 5, 9, 5, 24), [0, 1, 2]))

# --- liveness-stuttering: LiveStutter.tla -----------------------------------------------------------------------
for _lines, _suffix, _name_ in ((STABLE, "-stable", None), (ROLLING, "-rolling", "Reach")):
    basics(
        "liveness-stuttering",
        lines=_lines,
        suffix=_suffix,
        status="FAILURE",  # 2116: v1.7.4:38, rolling:39 (name: v1.7.4:39 none, rolling:40 "Reach")
        verdict="ERRORS",
        progress=True,  # 2200: v1.7.4:32, rolling:33
        info=[2212],  # v1.7.4:23, rolling:24
        errors=[(2116, "property", _name_)],
        related=[[2264]],  # v1.7.4:42, rolling:43
        traces=[(2, None, True)],  # two 2217 and 2218 "3: Stuttering": v1.7.4:56, rolling:57
    )
# Headers v1.7.4:47, 52; rolling:48, 53.
states("liveness-stuttering", 0, "x", _counting("Next", ("LiveStutter", 5, 9, 5, 24), [0, 1]))

# --- print-marker: PrintMarker.tla, a spec that prints marker text inside quotes --------------------------------
# The marker text is put together here so that no test file holds it literally (01 T12 rule 3 and its hook);
# these are lines the spec prints (PrintT), not framed TLC output.
_AT = "@!@!@"
_BEFORE = f'"before {_AT}STARTMSG 2185:0 {_AT} after"'
_FAKE = f'"{_AT}STARTMSG 9999:1 {_AT}"'
basics(
    "print-marker",
    lines=STABLE,
    suffix="-stable",
    status="FAILURE",  # 2114: v1.7.4:38
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:62
    output=[_BEFORE, _FAKE, _FAKE, _BEFORE, _FAKE, _FAKE],  # v1.7.4:32, 36, 37, 41, 42, 56
    errors=[(2114, "deadlock", None)],  # v1.7.4:39
    related=[[2121]],  # v1.7.4:43
    traces=[(3, None, False)],  # v1.7.4:46-60
)
basics(
    "print-marker",
    lines=ROLLING,
    suffix="-rolling",
    status="FAILURE",  # 2114: rolling:39
    verdict="ERRORS",
    progress=True,  # 2200: rolling:66
    output=[_BEFORE, _FAKE, _FAKE, _BEFORE, _FAKE, _FAKE, _BEFORE, _FAKE, _FAKE],  # rolling:33 ... 65
    errors=[(2114, "deadlock", None)],  # rolling:40
    related=[[2121]],  # rolling:44
    traces=[(3, None, False)],  # rolling:47-61
)
# Headers v1.7.4:47, 52, 58; rolling:48, 53, 59.
states("print-marker", 0, "x", _counting("Next", ("PrintMarker", 5, 9, 5, 67), [0, 1, 2]))


@fact("print-marker", "run", "two-quoted-lines-and-no-message-9999")
def _print_marker_no_9999(r: RunResult) -> None:
    # P4: the quoted Print lines are output (v1.7.4:32 ..., rolling:33 ...), and no message 9999 exists.
    _same("distinct output lines", set(r.output), {_BEFORE, _FAKE})
    messages = [e.message for e in r.errors] + list(r.warnings) + list(r.info) + list(r.unknown_messages)
    _same("messages with code 9999", [m.code for m in messages if m.code == 9999], [])


# --- print-output: Print.tla, -continue: the spec's own printed lines -------------------------------------------
_INIT, _INV = '"init-print"', '"inv-print"  TRUE'
_S0, _S1, _S2 = '<<"step", 0>>', '<<"step", 1>>', '<<"step", 2>>'
_PRINT_OUT_STABLE = [_INIT, _S0, _S1, _INV, _S2, _INV, _INIT, _S0, _S1, _S2, _INIT, _S0, _S1, _S2]
for _lines, _suffix, _out in (
    # v1.7.4:32, 36, 37, 38, 39, 40, 44, 45, 59, 65, 74, 75, 76, 95
    (STABLE, "-stable", _PRINT_OUT_STABLE),
    # rolling:33, 37, 38, 39, 40, 41, 45, 46, 60, 66, 75, 76, 77, 96, then 102, 103, 104, 105
    (ROLLING, "-rolling", [*_PRINT_OUT_STABLE, _INIT, _S0, _S1, _S2]),
):
    basics(
        "print-output",
        lines=_lines,
        suffix=_suffix,
        status="FAILURE",
        verdict="ERRORS",
        progress=True,  # 2200: v1.7.4:101, rolling:106
        output=_out,
        errors=[(2110, "invariant", "Bad"), (2114, "deadlock", None)],  # v1.7.4:41-42, 71-72; rolling:42-43, 72-73
        related=[[2121], [2121]],  # v1.7.4:46, 77; rolling:47, 78
        traces=[(4, None, False), (4, None, False)],  # printed lines between states are not states (P5)
    )
_PRINT = ("Print", 5, 9, 5, 52)
states("print-output", 0, "x", _counting("Next", _PRINT, range(4)))  # v1.7.4:50-68, rolling:51-69
states("print-output", 1, "x", _counting("Next", _PRINT, range(4)))  # v1.7.4:81-99, rolling:82-100

# --- postcondition-false: Post.tla, a POSTCONDITION v1.7.4 does not know -----------------------------------------
basics(
    "postcondition-false",
    lines=STABLE,
    suffix="-stable",
    status="FAILURE",  # 1000: v1.7.4:10
    verdict="NOT_CHECKED",  # a cfg error before SANY ran
    started=False,  # no 2185
    progress=False,
    errors=[(1000, "config", None)],  # a 1000 holding one 5006 (v1.7.4:15) takes its kind (P5)
    related=[[]],
    traces=[None],
)
basics(
    "postcondition-false",
    lines=ROLLING,
    suffix="-rolling",
    status="FAILURE",  # 2404: rolling:36
    verdict="ERRORS",
    progress=True,  # 2200: rolling:39
    errors=[(2404, "postcondition", "Post")],  # "Postcondition Post at line 8, ... is false.": rolling:37
    related=[[]],
    traces=[None],
)


@fact("postcondition-false", "errors", "config-message-shape", STABLE)
def _postcondition_stable_shape(r: RunResult) -> None:
    # v1.7.4:10-19: 1000 with four lines, then ": " and a nested 5006 of two lines.
    message = _error(r, 0).message
    _same("message (code, severity)", (message.code, message.severity), (1000, 1))
    _same("body", _body_shape(message), ["line"] * 4 + [5006])
    nested = message.nested[0]
    _same("nested 5006 (severity, before, lines)", (nested.severity, nested.before, len(nested.lines)), (0, ": ", 2))


# --- stack-overflow: Stack.tla ----------------------------------------------------------------------------------
basics(
    "stack-overflow",
    lines=STABLE,
    suffix="-stable",
    status="FAILURE",  # 1000: v1.7.4:29
    verdict="ERRORS",  # an exception after the initial states (2189 v1.7.4:23)
    progress=True,  # 2200: v1.7.4:1067
    errors=[(1000, "exception", None)],  # the raw Java stack inside it, v1.7.4:34-1059
    related=[[2103]],  # v1.7.4:1061
    traces=[None],
)
basics(
    "stack-overflow",
    lines=ROLLING,
    suffix="-rolling",
    status="FAILURE",  # 1005: rolling:30
    verdict="ERRORS",  # after the initial states (2189 rolling:24)
    progress=True,  # 2200: rolling:44
    errors=[(1005, "exception", None)],
    related=[[2121]],  # rolling:36
    traces=[(1, None, False)],  # one 2217: rolling:39-43
)
states("stack-overflow", 0, "x", [(None, None, 0)], ROLLING)  # rolling:40-41


@fact("stack-overflow", "errors", "no-nested-message", STABLE)
def _stack_overflow_stable_shape(r: RunResult) -> None:
    # v1.7.4:29-1060: a 1000 whose body is lines only (the Java stack), no nested message.
    message = _error(r, 0).message
    _same("nested messages", list(message.nested), [])
    _same("first line", message.lines[0], "TLC threw an unexpected exception.")
    _same("the exception line", message.lines[3], "The exception was a java.lang.StackOverflowError")


# --- java-override-exception: Boom.tla with a Java override that throws -----------------------------------------
basics(
    "java-override-exception",
    status="FAILURE",  # 1000: v1.7.4:32, rolling:33
    verdict="ERRORS",  # after the initial states (2189 v1.7.4:26, rolling:27)
    progress=True,  # 2200: v1.7.4:65, rolling:66
    overrides=[".Boom"],  # 2168 "Loading Boom operator override": v1.7.4:24, rolling:25
    errors=[(1000, "exception", None)],
    related=[[2121, 2103]],  # v1.7.4:44, 57; rolling:45, 58
    traces=[(2, None, False)],  # v1.7.4:47-55, rolling:48-56
)
states("java-override-exception", 0, "x", _counting("Next", ("Boom", 6, 9, 6, 24), [0, 1]))


@fact("java-override-exception", "errors", "message-shape")
def _java_override_exception_shape(r: RunResult) -> None:
    # P4: the 1000 (v1.7.4:32-43, rolling:33-44) has four lines, then the 2154 nested after ": ".
    message = _error(r, 0).message
    _same("message (code, severity)", (message.code, message.severity), (1000, 1))
    _same("body", _body_shape(message), ["line", "line", "line", "line", 2154])
    nested = message.nested[0]
    _same("nested 2154 (severity, before, after)", (nested.severity, nested.before, nested.after), (0, ": ", ""))
    _same("nested 2154 lines", len(nested.lines), 4)  # v1.7.4:38-41, rolling:39-42
    _same("nested 2154 last line", nested.lines[-1], "boom from Java override")
    # P4: text_lines() equal the error's lines in plain/java-override-exception.out of every TLC build folder,
    # read from the capture (01 T12 rule 3): the eight lines from its first "Error: " line, v1.7.4:13-20 and
    # rolling:28-35. Plain mode puts "Error: " in front of the first line, which -tool mode does not print.
    for folder in build_folders("tlc"):
        lines = [line.rstrip("\r\n") for line in read_lines(folder / "plain" / "java-override-exception.out")]
        start = next(n for n, line in enumerate(lines) if line.startswith("Error: "))
        plain = [lines[start].removeprefix("Error: "), *lines[start + 1 : start + 8]]
        _same(f"text lines against {folder.name}/plain", list(message.text_lines()), plain)


# --- java-override-stack-trace: BoomTrace.tla, an override whose error is a Java stack ----------------------------
basics(
    "java-override-stack-trace",
    status="FAILURE",  # 1000: v1.7.4:32, rolling:33
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:80, rolling:82
    overrides=[".BoomTrace"],  # 2168: v1.7.4:24, rolling:25
    errors=[(1000, "exception", None)],
    related=[[2121, 2103]],  # v1.7.4:59, 72; rolling:61, 74
    traces=[(2, None, False)],  # v1.7.4:62-70, rolling:64-72
)
states("java-override-stack-trace", 0, "x", _counting("Next", ("BoomTrace", 6, 9, 6, 29), [0, 1]))


@fact("java-override-stack-trace", "errors", "message-shape")
def _java_override_stack_trace_shape(r: RunResult) -> None:
    # The 1000 (v1.7.4:32-58, rolling:33-60): four lines, then the 2154 after ": " holding the Java stack.
    message = _error(r, 0).message
    _same("body", _body_shape(message), ["line", "line", "line", "line", 2154])
    nested = message.nested[0]
    _same("nested 2154 (severity, before)", (nested.severity, nested.before), (0, ": "))
    _same("nested 2154 line 4", nested.lines[3], "java.lang.StackOverflowError")  # v1.7.4:41, rolling:42


# --- parse-error: ParseError.tla --------------------------------------------------------------------------------
basics(
    "parse-error",
    status="FAILURE",
    verdict="NOT_CHECKED",
    progress=False,
    diagnostics=1,  # the ***Parse Error*** block: v1.7.4:14-32, rolling:14-34
    errors=[(3002, "parse", None)],  # 3002 is a TLC error, not a diagnostic (P8): v1.7.4:41, rolling:44
    related=[[]],
    traces=[None],
)


@fact("parse-error", "sany", "diagnostic")
def _parse_error_diagnostic(r: RunResult) -> None:
    # P8: "Encountered ... at line 6, column 1" (v1.7.4:15, rolling:15); module from "Could not parse module
    # ParseError" (v1.7.4:32, rolling:29); the file from "Parsing file .../ParseError.tla" (v1.7.4:13, rolling:13).
    _same("number of diagnostics", len(r.sany), 1)
    d = r.sany[0]
    _same("(tool, severity, module)", (d.tool, d.severity, d.module), ("sany", "error", "ParseError"))
    _holds("a location", d.location is not None, d.location)
    assert d.location is not None  # for the type checker
    _same("location (line, column)", (d.location.line, d.location.column), (6, 1))
    _holds("file ends in ParseError.tla", d.file is not None and d.file.endswith("ParseError.tla"), d.file)


# --- sany-semantic-error: SanyError.tla -------------------------------------------------------------------------
basics(
    "sany-semantic-error",
    status="FAILURE",  # P3: FAILURE
    verdict="NOT_CHECKED",
    progress=False,
    diagnostics=1,  # v1.7.4:17-26, rolling:17-25
    errors=[(3002, "parse", None)],  # v1.7.4:33, rolling:32
    related=[[]],
    traces=[None],
)


@fact("sany-semantic-error", "sany", "diagnostic")
def _sany_semantic_error_diagnostic(r: RunResult) -> None:
    # P8: v1.7.4:21 and 23, rolling:21 and 23; the file from "Parsing file" v1.7.4:13, rolling:13.
    _same("number of diagnostics", len(r.sany), 1)
    d = r.sany[0]
    _same("(tool, severity, module)", (d.tool, d.severity, d.module), ("sany", "error", "SanyError"))
    _same("location", _loc(d.location), ("SanyError", 5, 18, 5, 31))
    _same("message", d.message, "Unknown operator: `undefinedThing'.")
    _holds("file ends in SanyError.tla", d.file is not None and d.file.endswith("SanyError.tla"), d.file)


# --- version-bad-option: -version, which TLC does not know ------------------------------------------------------
basics(
    "version-bad-option",
    status="FAILURE",  # 1102: v1.7.4:4, rolling:4
    verdict="NOT_CHECKED",
    phase="NOT_STARTED",  # only 2262 comes before the error
    mode=None,
    workers=None,
    started=False,
    finished=False,  # no 2186
    progress=False,
    errors=[(1102, "usage", None)],  # "Error: unrecognized option: -version": v1.7.4:5, rolling:5
    related=[[]],
    traces=[None],
)

# =================================================================================================================
# Research 2: liveness traces; json-live and json-stut on v1.7.4, dump-trace-live on rolling.
# =================================================================================================================

basics(
    "json-live",
    lines=STABLE,
    status="FAILURE",  # 2116: v1.7.4:38
    verdict="ERRORS",
    workers=4,  # v1.7.4:8
    progress=True,  # 2200: v1.7.4:32
    info=[2212],  # v1.7.4:23
    errors=[(2116, "property", None)],  # "Temporal properties were violated.": v1.7.4:39
    related=[[2264]],  # v1.7.4:42
    traces=[(3, 1, False)],  # 2122 "1: Back to state": v1.7.4:61
)
# Headers v1.7.4:47, 52, 57.
states("json-live", 0, "x", _counting("Next", ("Live", 5, 9, 5, 22), [0, 1, 2]), STABLE)

basics(
    "json-stut",
    lines=STABLE,
    status="FAILURE",  # 2116: v1.7.4:38
    verdict="ERRORS",
    workers=4,  # v1.7.4:8
    progress=True,  # 2200: v1.7.4:32
    info=[2212],  # v1.7.4:23
    errors=[(2116, "property", None)],  # v1.7.4:39
    related=[[2264]],  # v1.7.4:42
    traces=[(3, None, True)],  # 2218 "4: Stuttering": v1.7.4:61
)
# Headers v1.7.4:47, 52, 57.
states("json-stut", 0, "x", _counting("Next", ("Stut", 5, 9, 5, 25), [0, 1, 2]), STABLE)

basics(
    "dump-trace-live",
    lines=ROLLING,
    status="FAILURE",  # 2116: rolling:53
    verdict="ERRORS",
    workers=4,  # rolling:5
    progress=True,  # 2200: rolling:47
    info=[2212],  # rolling:38
    output=['"CounterExample written: LiveW.json"'],  # unframed, rolling:80 (P6: kept as output)
    errors=[(2116, "property", "Bad")],  # "Temporal property Bad was violated.": rolling:54
    related=[[2264]],  # rolling:57
    traces=[(3, 1, False)],  # still parsed from the text (P6); 2122: rolling:76
)
# Headers rolling:62, 67, 72.
states("dump-trace-live", 0, "x", _counting("Next", ("Live", 5, 9, 5, 22), [0, 1, 2]), ROLLING)

# =================================================================================================================
# Research 13: override loading (tlc/<build>/override-<case>.out). The spec prints <<"Inv sees", a, b>>: 3 and 30
# when the override was used, 1003 and 1030 when TLC evaluated the TLA+ definition instead.
# =================================================================================================================

_USED = ['<<"Inv sees", 3, 30>>']  # v1.7.4:34, rolling:36
_NOT_USED = ['<<"Inv sees", 1003, 1030>>']  # v1.7.4:34, rolling:36

basics(
    "override-ok_warn_true",
    status="SUCCESS",  # 2186: v1.7.4:56, rolling:58
    verdict="NO_ERROR",
    progress=True,  # 2200: v1.7.4:44, rolling:46
    overrides=["tlc2.overrides.TLCOverrides.Add2"],  # 2168 "from tlc2.overrides.TLCOverrides": v1.7.4:29, rolling:31
    output=_USED,
    errors=[],
    related=[],
    traces=[],
    stats=(2, 1, 0, 1),  # 2199 v1.7.4:48 rolling:50; 2194 v1.7.4:51 rolling:53
)

basics(
    "override-legacy_ok",
    status="SUCCESS",  # 2186: v1.7.4:56, rolling:58
    verdict="NO_ERROR",
    progress=True,  # 2200: v1.7.4:44, rolling:46
    overrides=[".Add2"],  # 2168 from a class file named by its path: v1.7.4:29, rolling:31
    output=_USED,
    errors=[],
    related=[],
    traces=[],
    stats=(2, 1, 0, 1),  # 2199 v1.7.4:48 rolling:50; 2194 v1.7.4:51 rolling:53
)

basics(
    "override-annot_op_missing",
    status="SUCCESS",  # 2186: v1.7.4:56, rolling:58
    verdict="NO_ERROR",
    progress=True,  # 2200: v1.7.4:44, rolling:46
    warnings=[2403],  # "Failed to match NoSuchOp ... (no such operator).": v1.7.4:28, rolling:30
    output=_NOT_USED,
    errors=[],
    related=[],
    traces=[],
    stats=(2, 1, 0, 1),  # 2199 v1.7.4:48 rolling:50; 2194 v1.7.4:51 rolling:53
)

basics(
    "override-annot_module_missing",
    status="SUCCESS",  # 2186: v1.7.4:56, rolling:58
    verdict="NO_ERROR",
    progress=True,  # 2200: v1.7.4:44, rolling:46
    warnings=[2402],  # "Failed to match Add2 ... (no such module).": v1.7.4:28, rolling:30
    output=_NOT_USED,
    errors=[],
    related=[],
    traces=[],
    stats=(2, 1, 0, 1),  # 2199 v1.7.4:48 rolling:50; 2194 v1.7.4:51 rolling:53
)

basics(
    "override-arity_java_fewer",
    status="SUCCESS",  # 2186: v1.7.4:56, rolling:58
    verdict="NO_ERROR",
    progress=True,  # 2200: v1.7.4:44, rolling:46
    warnings=[2400],  # "Failed to match Add2 operator override ...": v1.7.4:28, rolling:30
    output=_NOT_USED,
    errors=[],
    related=[],
    traces=[],
    stats=(2, 1, 0, 1),  # 2199 v1.7.4:48 rolling:50; 2194 v1.7.4:51 rolling:53
)

basics(
    "override-static_init_throws",
    status="FAILURE",  # 1000: v1.7.4:28, rolling:30
    verdict="NOT_CHECKED",  # before the initial states: no 2189
    progress=False,
    errors=[(1000, "exception", None)],  # ExceptionInInitializerError, a Java stack: v1.7.4:32-56, rolling:34-59
    related=[[]],
    traces=[None],
)


@fact("override-static_init_throws", "errors", "no-nested-message")
def _static_init_shape(r: RunResult) -> None:
    # v1.7.4:28-57, rolling:30-60: lines only.
    message = _error(r, 0).message
    _same("nested messages", list(message.nested), [])
    _same("the exception line", message.lines[3], "The exception was a java.lang.ExceptionInInitializerError")


basics(
    "override-ctor_throws",
    status="FAILURE",  # 1000: v1.7.4:28, rolling:30
    verdict="NOT_CHECKED",  # no 2189
    progress=False,
    errors=[(1000, "exception", None)],
    related=[[]],
    traces=[None],
)


@fact("override-ctor_throws", "errors", "message-shape")
def _ctor_throws_shape(r: RunResult) -> None:
    # v1.7.4:28-34, rolling:30-36: five lines, the last ": boom in constructor"; no nested message.
    message = _error(r, 0).message
    _same("body", _body_shape(message), ["line"] * 5)
    _same("last line", message.lines[-1], ": boom in constructor")


basics(
    "override-ctor_private",
    status="FAILURE",  # 1000:1: v1.7.4:28, rolling:30
    verdict="NOT_CHECKED",  # no 2189
    progress=False,
    errors=[(1000, "exception", None)],  # one error, not two (P4): the inner 1000 is nested
    related=[[]],
    traces=[None],
)


@fact("override-ctor_private", "errors", "message-shape")
def _ctor_private_shape(r: RunResult) -> None:
    # P4: 1000 nested in 1000. v1.7.4:28-36 (inner 33-35), rolling:30-38 (inner 35-37).
    message = _error(r, 0).message
    _same("message (code, severity)", (message.code, message.severity), (1000, 1))
    _same("body", _body_shape(message), ["line", "line", "line", "line", 1000])
    nested = message.nested[0]
    _same("nested 1000 (severity, before, lines)", (nested.severity, nested.before, nested.lines), (0, ": ", ("",)))
    _same("truncated", (message.truncated, nested.truncated), (False, False))


basics(
    "override-eval_throws_runtime",
    status="FAILURE",  # 1000: v1.7.4:34, rolling:36
    verdict="ERRORS",  # after 2189 (v1.7.4:31, rolling:33): the initial states were being computed
    progress=True,  # 2200: v1.7.4:50, rolling:52
    overrides=["tlc2.overrides.TLCOverrides.Add2"],  # 2168: v1.7.4:29, rolling:31
    errors=[(1000, "exception", None)],  # its one nested 2154 has kind exception, so the kind stays (P5)
    related=[[2103]],  # v1.7.4:42, rolling:44
    traces=[None],
)


@fact("override-eval_throws_runtime", "errors", "message-shape")
def _eval_throws_shape(r: RunResult) -> None:
    # v1.7.4:34-41, rolling:36-43: the 1000's body is the nested 2154 alone, with nothing before it.
    message = _error(r, 0).message
    _same("body", _body_shape(message), [2154])
    nested = message.nested[0]
    _same("nested 2154 (severity, before, after)", (nested.severity, nested.before, nested.after), (0, "", ""))
    _same("nested 2154 last line", nested.lines[-1], "boom in override body")


basics(
    "override-method_not_public",
    status="FAILURE",  # 2154:1: v1.7.4:28, rolling:30
    verdict="NOT_CHECKED",  # no 2189
    progress=False,
    finished=True,  # P4: the finish time from the 2186 after the nested messages, v1.7.4:39, rolling:41
    errors=[(2154, "exception", None)],
    related=[[]],
    traces=[None],
)


@fact("override-method_not_public", "errors", "message-shape")
def _method_not_public_shape(r: RunResult) -> None:
    # P4: v1.7.4:28-38, rolling:30-40. One line, the nested 2154 ended by "ENDMSG 2154" with "," after it
    # (v1.7.4:35, rolling:37), then two more lines.
    message = _error(r, 0).message
    _same("message (code, severity, truncated)", (message.code, message.severity, message.truncated), (2154, 1, False))
    _same("body", _body_shape(message), ["line", 2154, "line", "line"])
    nested = message.nested[0]
    _same(
        "nested 2154 (severity, before, after, truncated)",
        (nested.severity, nested.before, nested.after, nested.truncated),
        (0, "", ",", False),
    )
    _same("nested 2154 lines", len(nested.lines), 4)
    _same("lines after the nested 2154", len(message.body) - message.body.index(nested) - 1, 2)


# =================================================================================================================
# Research 28: override classes too new for Java 11 (tlc/<build>/override-class-too-new-*.out).
# =================================================================================================================

basics(
    "override-class-too-new-index",
    status="FAILURE",  # 2173: v1.7.4:28, rolling:30
    verdict="NOT_CHECKED",  # no 2189
    progress=False,
    errors=[(2173, "exception", None)],  # "Found a Java class ... but unable to read it": v1.7.4:29, rolling:31
    related=[[]],
    traces=[None],
)

basics(
    "override-class-too-new-listed",
    status="FAILURE",  # 1000: v1.7.4:28, rolling:30
    verdict="NOT_CHECKED",  # no 2189
    progress=False,
    errors=[(1000, "exception", None)],  # UnsupportedClassVersionError: v1.7.4:32, rolling:34
    related=[[]],
    traces=[None],
)


@fact("override-class-too-new-listed", "errors", "message-shape")
def _class_too_new_listed_shape(r: RunResult) -> None:
    # v1.7.4:28-34, rolling:30-36: five lines, no nested message.
    message = _error(r, 0).message
    _same("body", _body_shape(message), ["line"] * 5)
    _same("the exception line", message.lines[3], "The exception was a java.lang.UnsupportedClassVersionError")


# =================================================================================================================
# Research 22: the top-up captures (tlc/<build>/<case>.out), 58 cases on each build.
# =================================================================================================================


def _refused(case: str, *, lines: frozenset[str] = LINES, suffix: str = "") -> None:
    """A command line TLC refuses with 1102 right after 2262: no mode, no run (like ``version-bad-option``)."""
    basics(
        case,
        lines=lines,
        suffix=suffix,
        status="FAILURE",
        verdict="NOT_CHECKED",
        phase="NOT_STARTED",
        mode=None,
        workers=None,
        started=False,
        finished=False,
        progress=False,
        errors=[(1102, "usage", None)],
        related=[[]],
        traces=[None],
    )


def _diagnostic(result: RunResult, index: int) -> Diagnostic:
    _holds(f"diagnostic {index + 1} exists", len(result.sany) > index, len(result.sany))
    return result.sany[index]


def _file_ends(what: str, file: str | None, name: str | None) -> None:
    if name is None:
        _same(f"{what}: file", file, None)
    else:
        _holds(f"{what}: file ends in {name}", file is not None and file.endswith(name), file)


def _output_is_capture(case: str, line: str) -> Check:
    """The output is every line of the capture (a run with no message at all, such as ``-help``)."""
    return lambda r: _same("output", list(r.output), _capture(case, line))


# The states of Violation.tla's breadth-first counterexample, the same in every exhaustive capture of it
# (research 1's violation and research 22's -difftrace, -generateSpecTE and -noGenerateSpecTE runs).
_V_NEXT = ("Violation", 10, 59, 10, 76)
_V_INIT = ("Violation", 4, 9, 6, 16)  # the Init header of -simulate and -generate on rolling
_NOTE = ("string", ANY)  # the spec's long note, a string the facts do not spell


def _vstore(alpha: Sequence[int] = (), beta: Sequence[int] = (), gamma: Sequence[int] = ()) -> tuple[object, ...]:
    return vrec(alpha=vset(*map(vint, alpha)), beta=vset(*map(vint, beta)), gamma=vset(*map(vint, gamma)))


def _vlog(*entries: tuple[str, int]) -> tuple[object, ...]:
    return vseq(*(vrec(op=vstr("add"), key=vstr(k), val=vint(v), note=_NOTE) for k, v in entries))


def _violation_rows(carried_store_in_3: bool = False) -> list[Row]:
    """The four states; with ``-difftrace`` state 3 leaves out ``store``, which did not change."""
    one = ("alpha", 1)
    return [
        (None, None, [("store", _vstore(), True), ("n", vint(0), True), ("log", vseq(), True)]),
        ("Next", _V_NEXT, [("store", _vstore([1]), True), ("n", vint(1), True), ("log", _vlog(one), True)]),
        (
            "Next",
            _V_NEXT,
            [("store", _vstore([1]), not carried_store_in_3), ("n", vint(2), True), ("log", _vlog(one, one), True)],
        ),
        ("Next", _V_NEXT, [("store", _vstore([1]), True), ("n", vint(3), True), ("log", _vlog(one, one, one), True)]),
    ]


def _violation_unknown_rows(first: tuple[str | None, Loc | None], rest: tuple[str | None, Loc | None]) -> list[Row]:
    """Four states of Violation.tla whose store and log depend on a random choice: only ``n`` is asserted."""
    rows: list[Row] = []
    for n in range(4):
        action, location = first if n == 0 else rest
        rows.append(
            (action, location, [("store", ("record", ANY), True), ("n", vint(n), True), ("log", ("seq", ANY), True)])
        )
    return rows


# --- alias-violation, alias-violation-difftrace: Alias.tla with an ALIAS (rolling only) --------------------------
# v1.7.4 reads ALIAS as an invariant name: 2229 "The invariant ALIAS ... is not defined" (v1.7.4:23-26, both cases).
_ALIAS = ("Alias", 5, 9, 5, 32)
for _case in ("alias-violation", "alias-violation-difftrace"):
    basics(
        _case,
        lines=STABLE,
        suffix="-stable",
        status="FAILURE",  # 2229: v1.7.4:23
        verdict="NOT_CHECKED",  # a config error after 2185 (v1.7.4:20), no 2189
        progress=False,
        errors=[(2229, "config", None)],
        related=[[]],
        traces=[None],
    )
basics(
    "alias-violation",
    lines=ROLLING,
    suffix="-rolling",
    status="FAILURE",  # 2110: rolling:30
    verdict="ERRORS",
    progress=True,  # 2200: rolling:64
    errors=[(2110, "invariant", "Inv")],  # rolling:31
    related=[[2121]],  # rolling:33
    traces=[(4, None, False)],  # rolling:36-63
)
# The alias record's fields are the variables (P5). Headers rolling:37, 44, 51, 58.
trace_states(
    "alias-violation",
    0,
    [
        (None, None, [("x", vint(0), True), ("sum", vint(0), True), ("label", vstr("step"), True)]),
        ("Next", _ALIAS, [("x", vint(1), True), ("sum", vint(3), True), ("label", vstr("step"), True)]),
        ("Next", _ALIAS, [("x", vint(2), True), ("sum", vint(6), True), ("label", vstr("step"), True)]),
        ("Next", _ALIAS, [("x", vint(3), True), ("sum", vint(9), True), ("label", vstr("step"), True)]),
    ],
    ROLLING,
)
basics(
    "alias-violation-difftrace",
    lines=ROLLING,
    suffix="-rolling",
    status="FAILURE",  # 2110: rolling:30
    verdict="ERRORS",
    progress=True,  # 2200: rolling:62
    errors=[(2110, "invariant", "Inv")],  # rolling:31
    related=[[2121]],  # rolling:33
    traces=[(4, None, False)],  # rolling:36-61
)
# States 2 and 3 leave out label (rolling:43-48, 49-54); state 4 is printed in full (rolling:55-61).
trace_states(
    "alias-violation-difftrace",
    0,
    [
        (None, None, [("x", vint(0), True), ("sum", vint(0), True), ("label", vstr("step"), True)]),
        ("Next", _ALIAS, [("x", vint(1), True), ("sum", vint(3), True), ("label", vstr("step"), False)]),
        ("Next", _ALIAS, [("x", vint(2), True), ("sum", vint(6), True), ("label", vstr("step"), False)]),
        ("Next", _ALIAS, [("x", vint(3), True), ("sum", vint(9), True), ("label", vstr("step"), True)]),
    ],
    ROLLING,
)

# --- checkpoint-run: Slow.tla, -checkpoint 1, stopped by SIGTERM after 80 s --------------------------------------
basics(
    "checkpoint-run",
    status="RUNNING",  # no 2186: the output ends at v1.7.4:44, rolling:45
    verdict="INCOMPLETE",
    phase="CHECKING",  # 2190: v1.7.4:30, rolling:31
    finished=False,
    progress=True,  # 2200: v1.7.4:33, rolling:34
    errors=[],  # 2195 and 2196 (v1.7.4:36 and 39, rolling:37 and 40) are typed: not info
    related=[],
    traces=[],
)

# --- checkpoint-recover: Slow.tla, -recover from checkpoint-run's folder -----------------------------------------
# A resumed run: no final counts (D54). Rolling warns that the seed and fp differ from the checkpoint's (2285).
for _lines, _suffix, _warns in ((STABLE, "-stable", []), (ROLLING, "-rolling", [2285])):
    basics(
        "checkpoint-recover",
        lines=_lines,
        suffix=_suffix,
        status="SUCCESS",  # 2186: v1.7.4:63, rolling:72
        verdict="NO_ERROR",
        resumed=True,  # 2197 and 2198: v1.7.4:27 and 30, rolling:28 and 39
        progress=True,  # 2200: v1.7.4:33, rolling:42
        warnings=_warns,  # 2285:3: rolling:31-38
        errors=[],
        related=[],
        traces=[],
    )

# --- checkpoint-recover-missing: Slow.tla, -recover from a folder that does not exist ----------------------------
basics(
    "checkpoint-recover-missing",
    status="FAILURE",  # 1000: v1.7.4:7, rolling:7
    verdict="NOT_CHECKED",  # an exception before 2185: no initial states
    mode=None,  # no 2187: the error comes right after 2262 and 2401
    workers=None,
    started=False,
    progress=False,
    errors=[(1000, "exception", None)],
    related=[[]],
    traces=[None],
)


@fact("checkpoint-recover-missing", "errors", "message-shape")
def _recover_missing_shape(r: RunResult) -> None:
    # v1.7.4:7-13, rolling:7-13: five lines, no nested message; the fifth names the missing file under <tmp>.
    message = _error(r, 0).message
    _same("body", _body_shape(message), ["line"] * 5)
    _same("the exception line", message.lines[3], "The exception was a java.io.FileNotFoundException")


# --- deadlock-flag: Deadlock.tla, -deadlock (deadlock is not checked) --------------------------------------------
basics(
    "deadlock-flag",
    status="SUCCESS",  # 2186: v1.7.4:47, rolling:48
    verdict="NO_ERROR",
    progress=True,  # 2200: v1.7.4:35, rolling:36
    errors=[],
    related=[],
    traces=[],
    stats=(3, 3, 0, 3),  # 2199 v1.7.4:38 rolling:39; 2194 v1.7.4:41 rolling:42
)

# --- deadlock-flag-multierror: MultiError.tla, -deadlock -continue: exit 0 with two errors (D54) -----------------
basics(
    "deadlock-flag-multierror",
    status="FAILURE",
    verdict="ERRORS",  # two invariant errors although TLC exits 0 (P3)
    progress=True,  # 2200: v1.7.4:87, rolling:88
    errors=[
        (2110, "invariant", "InvA"),  # v1.7.4:29-30, rolling:30-31
        (2110, "invariant", "InvB"),  # v1.7.4:50-51, rolling:51-52
    ],
    related=[[2121], [2121]],  # v1.7.4:32, 53; rolling:33, 54
    traces=[(3, None, False), (5, None, False)],
    stats=(7, 7, 0, 7),  # the search completes: 2199 v1.7.4:90 rolling:91; 2194 v1.7.4:93 rolling:94
)
states("deadlock-flag-multierror", 0, "x", _counting("Next", _MULTI, range(3)))  # v1.7.4:35-49, rolling:36-50
states("deadlock-flag-multierror", 1, "x", _counting("Next", _MULTI, range(5)))  # v1.7.4:56-80, rolling:57-81

# --- dfid-*: -dfid N, a depth-first run: 2271 sets the mode (v1.7.4:7, rolling:7) -------------------------------
# 2208, 2205 (one per level) and 2206 are information (P5), 2204 the statistics; there is no 2200 progress.
for _case, _levels in (
    ("dfid-deadlock", 1),  # 2208 v1.7.4:23 rolling:24; 2206 v1.7.4:29 rolling:30; 2186 v1.7.4:35 rolling:36
    ("dfid-success", 4),  # 2208 v1.7.4:23 rolling:24; 2205 v1.7.4:26-35 rolling:27-36; 2186 v1.7.4:44 rolling:45
    ("dfid-success-deep", 7),  # 2205 v1.7.4:26-44 rolling:27-45; 2206 v1.7.4:54 rolling:55; 2186 v1.7.4:60 rolling:61
    # -dfid 2 stops before the violation that exists (D54): no error, exit 0.
    ("dfid-violation", 1),  # 2208 v1.7.4:27 rolling:28; 2206 v1.7.4:33 rolling:34; 2186 v1.7.4:39 rolling:40
):
    basics(
        _case,
        status="SUCCESS",  # 2186 and no error
        verdict="NO_ERROR_BOUNDED",  # depth-first (P3)
        mode="depth-first",
        progress=False,
        info=[2208, *[2205] * _levels, 2206],
        errors=[],
        related=[],
        traces=[],
    )

# --- dfid-violation-deep: Violation.tla, -dfid 10 ----------------------------------------------------------------
basics(
    "dfid-violation-deep",
    status="FAILURE",  # 2110: v1.7.4:39, rolling:40
    verdict="ERRORS",
    mode="depth-first",
    progress=False,
    info=[2208, 2205, 2205, 2205, 2206],  # v1.7.4:27, 30, 33, 36, 100; rolling:28, 31, 34, 37, 101
    errors=[(2110, "invariant", "Small")],  # v1.7.4:40, rolling:41
    related=[[2121]],  # v1.7.4:42, rolling:43
    traces=[(4, None, False)],  # 2216 v1.7.4:45-99; 2217 rolling:46-100
)
# The -dfid states have no action and no location (P5). Which keys and values the search took differs between
# the two captures (v1.7.4:46 and 53, rolling:47 and 54), so only n is asserted.
trace_states("dfid-violation-deep", 0, _violation_unknown_rows((None, None), (None, None)))

# The header line is "1:" on v1.7.4 (2216, v1.7.4:46) and "1: " on rolling (2217, rolling:47).
for _lines, _suffix, _end in ((STABLE, "-stable", ":"), (ROLLING, "-rolling", ": ")):

    def _dfid_headers(r: RunResult, end: str = _end) -> None:
        trace = _trace(r, 0)
        _same("header lines", [s.lines[0] for s in trace.states], [f"{n}{end}" for n in range(1, 5)])

    add("dfid-violation-deep", "traces", "header-lines" + _suffix, _dfid_headers, _lines)

# --- -difftrace and its twins (P5): a state leaves out what did not change, the parser carries it forward --------
# verify-difftrace.txt of research 22 pairs each -difftrace capture with its plain twin; the facts of a pair
# assert the same variables and values, with printed false exactly where TLC left a variable out.

# difftrace-deadlock: Deadlock.tla; x changes in every step, so every state prints it (as in deadlock).
basics(
    "difftrace-deadlock",
    status="FAILURE",  # 2114: v1.7.4:29, rolling:30
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:50, rolling:51
    errors=[(2114, "deadlock", None)],
    related=[[2121]],  # v1.7.4:32, rolling:33
    traces=[(3, None, False)],  # v1.7.4:35-49, rolling:36-50
)
# Headers v1.7.4:36, 41, 46; rolling:37, 42, 47.
states("difftrace-deadlock", 0, "x", _counting("Next", ("Deadlock", 5, 9, 5, 27), [0, 1, 2]))

# difftrace-liveness-q1-back-to-state and -stuttering: research 1's two liveness specs with -difftrace.
for _lines, _suffix, _name_ in ((STABLE, "-stable", None), (ROLLING, "-rolling", "Reach")):
    basics(
        "difftrace-liveness-q1-back-to-state",
        lines=_lines,
        suffix=_suffix,
        status="FAILURE",  # 2116: v1.7.4:38, rolling:39 (no name on v1.7.4:39, "Reach" on rolling:40)
        verdict="ERRORS",
        progress=True,  # 2200: v1.7.4:32, rolling:33
        info=[2212],  # v1.7.4:23, rolling:24
        errors=[(2116, "property", _name_)],
        related=[[2264]],  # v1.7.4:42, rolling:43
        traces=[(3, 1, False)],  # 2122 "1: Back to state": v1.7.4:61, rolling:62
    )
    basics(
        "difftrace-liveness-q1-stuttering",
        lines=_lines,
        suffix=_suffix,
        status="FAILURE",  # 2116: v1.7.4:38, rolling:39
        verdict="ERRORS",
        progress=True,  # 2200: v1.7.4:32, rolling:33
        info=[2212],  # v1.7.4:23, rolling:24
        errors=[(2116, "property", _name_)],
        related=[[2264]],  # v1.7.4:42, rolling:43
        traces=[(2, None, True)],  # 2218 "3: Stuttering": v1.7.4:56, rolling:57
    )
# Headers v1.7.4:47, 52, 57; rolling:48, 53, 58.
states("difftrace-liveness-q1-back-to-state", 0, "x", _counting("Next", ("LiveBack", 5, 9, 5, 24), [0, 1, 2]))
# Headers v1.7.4:47, 52; rolling:48, 53.
states("difftrace-liveness-q1-stuttering", 0, "x", _counting("Next", ("LiveStutter", 5, 9, 5, 24), [0, 1]))

# difftrace-q1-violation: Violation.tla with -difftrace, the twin of research 1's violation.
basics(
    "difftrace-q1-violation",
    status="FAILURE",  # 2110: v1.7.4:33, rolling:34
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:93, rolling:94
    errors=[(2110, "invariant", "Small")],  # v1.7.4:34, rolling:35
    related=[[2121]],  # v1.7.4:36, rolling:37
    traces=[(4, None, False)],  # v1.7.4:39-92, rolling:40-93
)
# State 3 leaves out store (v1.7.4:57-71, rolling:58-72); state 4 is printed in full (v1.7.4:72-92, rolling:73-93).
trace_states("difftrace-q1-violation", 0, _violation_rows(carried_store_in_3=True))

# difftrace-violation, difftrace-violation-nodiff, difftrace-workers-4: Diff.tla, Inv == a + b < 4.
_DIFF_A = ("Diff", 5, 12, 5, 52)  # the disjunct that moves a
_DIFF_B = ("Diff", 6, 12, 6, 77)  # the disjunct that moves b and c
_C0 = vseq(vint(0), vint(0), vint(0))


def _diff_rows(difftrace: bool) -> list[Row]:
    """a counts from 0 to 4 while b and c stay; with -difftrace states 2 to 4 print only a, state 5 all."""
    rows: list[Row] = [(None, None, [("a", vint(0), True), ("b", vint(0), True), ("c", _C0, True)])]
    for a in range(1, 5):
        printed = not difftrace or a == 4
        rows.append(("Next", _DIFF_A, [("a", vint(a), True), ("b", vint(0), printed), ("c", _C0, printed)]))
    return rows


for _case, _difftrace in (
    ("difftrace-violation", True),  # 2200: v1.7.4:64, rolling:65
    ("difftrace-violation-nodiff", False),  # 2200: v1.7.4:70, rolling:71
):
    basics(
        _case,
        status="FAILURE",  # 2110: v1.7.4:29, rolling:30
        verdict="ERRORS",
        progress=True,  # 2200 at the line named above
        errors=[(2110, "invariant", "Inv")],  # v1.7.4:30, rolling:31
        related=[[2121]],  # v1.7.4:32, rolling:33
        traces=[(5, None, False)],
    )
    trace_states(_case, 0, _diff_rows(_difftrace))
# difftrace-violation states: v1.7.4:35-63, rolling:36-64 (state 5 in full at v1.7.4:57, rolling:58).
# difftrace-violation-nodiff states: v1.7.4:35-69, rolling:36-70.

basics(
    "difftrace-workers-4",
    status="FAILURE",  # 2110: v1.7.4:29, rolling:30
    verdict="ERRORS",
    workers=4,  # "with 4 workers": v1.7.4:8, rolling:8
    progress=True,  # 2200: v1.7.4:64, rolling:65
    errors=[(2110, "invariant", "Inv")],  # v1.7.4:30, rolling:31
    related=[[2121]],  # v1.7.4:32, rolling:33
    traces=[(5, None, False)],  # v1.7.4:35-63, rolling:36-64
)


@fact("difftrace-workers-4", "traces", "carried-forward")
def _workers_4_carried(r: RunResult) -> None:
    # With four workers which state of a + b = 4 is found first may differ between runs, so this fact asserts
    # the carrying, not the values: state 1 and state 5 in full (v1.7.4:35 and 57, rolling:36 and 58), and every
    # variable a state leaves out equal to the state before. Every step moves a, or b and c, so states 2 to 4
    # each leave one out.
    trace = _trace(r, 0)
    _same("number of states", len(trace.states), 5)
    first, *middle, last = trace.states
    for state in trace.states:
        _same(f"state {state.index}: variables", [v.name for v in state.variables], ["a", "b", "c"])
    _same(
        "state 1",
        [(_plain(v.value), v.printed) for v in first.variables],
        [(vint(0), True), (vint(0), True), (_C0, True)],
    )
    _same("state 5: printed", [v.printed for v in last.variables], [True, True, True])
    a, b = (_plain(v.value) for v in last.variables[:2])
    _holds("state 5: a + b = 4", a[0] == b[0] == "int" and int(a[1]) + int(b[1]) == 4, (a, b))
    for before, state in zip(trace.states, trace.states[1:], strict=False):
        for old, new in zip(before.variables, state.variables, strict=True):
            if not new.printed:
                _same(f"state {state.index}: {new.name} carried", _plain(new.value), _plain(old.value))
    for state in middle:
        _holds(f"state {state.index} leaves a variable out", not all(v.printed for v in state.variables), state)


# difftrace-liveness, difftrace-liveness-nodiff: DiffLive.tla, a loop back to state 2.
_DIFFLIVE = ("DiffLive", 5, 9, 6, 48)


def _difflive_rows(difftrace: bool) -> list[Row]:
    """p goes 0, 1, 2, 0; q stays "idle" until state 4. With -difftrace states 2 and 3 leave out q."""
    return [
        (None, None, [("p", vint(0), True), ("q", vstr("idle"), True)]),
        ("Next", _DIFFLIVE, [("p", vint(1), True), ("q", vstr("idle"), not difftrace)]),
        ("Next", _DIFFLIVE, [("p", vint(2), True), ("q", vstr("idle"), not difftrace)]),
        ("Next", _DIFFLIVE, [("p", vint(0), True), ("q", vstr("busy"), True)]),
    ]


for _case, _difftrace in (("difftrace-liveness", True), ("difftrace-liveness-nodiff", False)):
    for _lines, _suffix, _name_ in ((STABLE, "-stable", None), (ROLLING, "-rolling", "Reach")):
        basics(
            _case,
            lines=_lines,
            suffix=_suffix,
            status="FAILURE",  # 2116: v1.7.4:38, rolling:39 (no name on v1.7.4:39, "Reach" on rolling:40)
            verdict="ERRORS",
            progress=True,  # 2200: v1.7.4:32, rolling:33
            info=[2212],  # v1.7.4:23, rolling:24
            errors=[(2116, "property", _name_)],
            related=[[2264]],  # v1.7.4:42, rolling:43
            traces=[(4, 2, False)],  # 2122 "2: Back to state": v1.7.4:68 and 70, rolling:69 and 71
        )
    trace_states(_case, 0, _difflive_rows(_difftrace))
# difftrace-liveness headers v1.7.4:47, 53, 58, 63, rolling:48, 54, 59, 64;
# difftrace-liveness-nodiff headers v1.7.4:47, 53, 59, 65, rolling:48, 54, 60, 66.

# --- params-*: Params.tla, actions with parameters and through an INSTANCE ---------------------------------------
_PARAMS_VIAZ = ("Params", 8, 9, 8, 39)
_PARAMS_VIAQ = ("Params", 14, 9, 14, 57)
_PARAMS_STEP = ("Params", 6, 12, 6, 52)


def _xyz(x: int, y: int, z: int, printed: Sequence[bool] = (True, True, True)) -> list[Var]:
    return [("x", vint(x), printed[0]), ("y", vint(y), printed[1]), ("z", vint(z), printed[2])]


for _case, _inv in (
    ("params-violation", "Inv"),  # 2200: v1.7.4:58, rolling:60
    ("params-violation-difftrace", "Inv"),  # 2200: v1.7.4:56, rolling:58
    ("params-instance-exists-violation", "Inv"),  # 2200: v1.7.4:58, rolling:60
    ("params-instance-exists-violation-difftrace", "Inv"),  # 2200: v1.7.4:56, rolling:58
    ("params-step-violation", "InvX"),  # 2200: v1.7.4:58, rolling:60
    ("params-step-violation-difftrace", "InvX"),  # 2200: v1.7.4:56, rolling:58
):
    basics(
        _case,
        status="FAILURE",  # 2110: v1.7.4:31, rolling:33
        verdict="ERRORS",
        progress=True,  # 2200 at the line named above
        errors=[(2110, "invariant", _inv)],  # v1.7.4:32, rolling:34
        related=[[2121]],  # v1.7.4:34, rolling:36
        traces=[(3, None, False)],  # three 2217 from v1.7.4:37, rolling:39
    )

# Viaz is I!Bump(2) through the INSTANCE: z goes 0, 2, 4 (v1.7.4:37-57, rolling:39-59). With -difftrace state 2
# prints only z (v1.7.4:44-48, rolling:46-50) and state 3 all.
_NO_XY = (False, False, True)
for _case, _action, _location, _diff in (
    ("params-violation", "Viaz", _PARAMS_VIAZ, False),
    ("params-violation-difftrace", "Viaz", _PARAMS_VIAZ, True),
    ("params-instance-exists-violation", "Viaq", _PARAMS_VIAQ, False),
    ("params-instance-exists-violation-difftrace", "Viaq", _PARAMS_VIAQ, True),
):
    trace_states(
        _case,
        0,
        [
            (None, None, _xyz(0, 0, 0)),
            (_action, _location, _xyz(0, 0, 2, _NO_XY if _diff else (True, True, True))),
            (_action, _location, _xyz(0, 0, 4)),
        ],
    )

# Step(i) under the existential of Pick: v1.7.4 names the action "Step" (v1.7.4:45, 52), rolling with its
# argument, "Step(1)" and "Step(2)" (rolling:47, 54; P5). x goes 0, 1, 3; with -difftrace state 2 prints only x.
_ONLY_X = (True, False, False)
for _case, _diff in (("params-step-violation", False), ("params-step-violation-difftrace", True)):
    for _lines, _suffix, _first, _second in (
        (STABLE, "-stable", "Step", "Step"),
        (ROLLING, "-rolling", "Step(1)", "Step(2)"),
    ):
        trace_states(
            _case,
            0,
            [
                (None, None, _xyz(0, 0, 0)),
                (_first, _PARAMS_STEP, _xyz(1, 0, 0, _ONLY_X if _diff else (True, True, True))),
                (_second, _PARAMS_STEP, _xyz(3, 0, 0)),
            ],
            _lines,
            _suffix,
        )

# --- -generate (rolling only; v1.7.4 refuses the flag) ----------------------------------------------------------
# v1.7.4: 1102 "Error: unrecognized option: -generate" right after 2262 (v1.7.4:4-7, all five cases).
for _case in (
    "generate-deadlock",
    "generate-success",
    "generate-success-num",
    "generate-violation",
    "generate-violation-num",
):
    _refused(_case, lines=STABLE, suffix="-stable")

# On rolling -generate is a simulation (2188 "Running Random Simulation", rolling:7) with a random seed: the
# facts assert no value that depends on it. The first state names Init with a location (P5).
basics(
    "generate-deadlock",
    lines=ROLLING,
    suffix="-rolling",
    status="FAILURE",  # 2114: rolling:30
    verdict="ERRORS",
    mode="simulate",
    progress=True,  # 2209: rolling:51
    info=[2269],  # rolling:24
    errors=[(2114, "deadlock", None)],  # rolling:31
    related=[[2121]],  # rolling:33
    traces=[(3, None, False)],  # rolling:36-50
)
_DEADLOCK_INIT = ("Init", ("Deadlock", 4, 9, 4, 13))
_DEADLOCK_NEXT = ("Deadlock", 5, 9, 5, 27)
# Headers rolling:37, 42, 47. Deadlock.tla has one behaviour, so the values do not depend on the seed.
states(
    "generate-deadlock",
    0,
    "x",
    [(*_DEADLOCK_INIT, 0), ("Next", _DEADLOCK_NEXT, 1), ("Next", _DEADLOCK_NEXT, 2)],
    ROLLING,
)

basics(
    "generate-success",
    lines=ROLLING,
    suffix="-rolling",
    status="RUNNING",  # killed by the driver after 120 s: no 2186, the output ends at rolling:32
    verdict="INCOMPLETE",
    phase="CHECKING",  # 2190: rolling:27
    mode="simulate",
    finished=False,
    progress=True,  # 2209: rolling:30
    info=[2269],  # rolling:24
    errors=[],
    related=[],
    traces=[],
)

basics(
    "generate-success-num",
    lines=ROLLING,
    suffix="-rolling",
    status="SUCCESS",  # 2186: rolling:40
    verdict="NO_ERROR_BOUNDED",  # a simulation (P3)
    mode="simulate",
    progress=True,  # 2209: rolling:30
    info=[2269],  # rolling:24
    errors=[],
    related=[],
    traces=[],
)

for _case in ("generate-violation", "generate-violation-num"):
    basics(
        _case,
        lines=ROLLING,
        suffix="-rolling",
        status="FAILURE",  # 2110: rolling:34
        verdict="ERRORS",
        mode="simulate",
        progress=True,  # 2209: rolling:95
        info=[2269],  # rolling:28
        errors=[(2110, "invariant", "Small")],  # rolling:35
        related=[[2121]],  # rolling:37
        traces=[(4, None, False)],  # rolling:40-94
    )
    # Headers rolling:41, 48, 59, 75; the store and log differ between the two captures (random seeds).
    trace_states(_case, 0, _violation_unknown_rows(("Init", _V_INIT), ("Next", _V_NEXT)), ROLLING)

# --- generateSpecTE-violation: Violation.tla, -generateSpecTE --------------------------------------------------
# v1.7.4 prints four 1000:0 messages about the SpecTE files (v1.7.4:1, 109, 112, 115): severity 0, so
# information (P4 rule 1); rolling prints 2501, the path of the trace spec, after 2186 (rolling:117).
for _lines, _suffix, _info_codes in ((STABLE, "-stable", [1000, 1000, 1000, 1000]), (ROLLING, "-rolling", [2501])):
    basics(
        "generateSpecTE-violation",
        lines=_lines,
        suffix=_suffix,
        status="FAILURE",  # 2110: v1.7.4:36, rolling:44
        verdict="ERRORS",
        progress=True,  # 2200: v1.7.4:97, rolling:105
        info=_info_codes,
        errors=[(2110, "invariant", "Small")],  # v1.7.4:37, rolling:45
        related=[[2121]],  # v1.7.4:39, rolling:47
        traces=[(4, None, False)],  # v1.7.4:42-96, rolling:50-104
    )
# Headers v1.7.4:43, 50, 61, 77; rolling:51, 58, 69, 85.
trace_states("generateSpecTE-violation", 0, _violation_rows())

# --- noGenerateSpecTE-violation: Violation.tla, -noGenerateSpecTE (rolling only) ---------------------------------
_refused("noGenerateSpecTE-violation", lines=STABLE, suffix="-stable")  # 1102: v1.7.4:4-7
basics(
    "noGenerateSpecTE-violation",
    lines=ROLLING,
    suffix="-rolling",
    status="FAILURE",  # 2110: rolling:34
    verdict="ERRORS",
    progress=True,  # 2200: rolling:95
    errors=[(2110, "invariant", "Small")],  # rolling:35
    related=[[2121]],  # rolling:37
    traces=[(4, None, False)],  # rolling:40-94
)
# Headers rolling:41, 48, 59, 75.
trace_states("noGenerateSpecTE-violation", 0, _violation_rows(), ROLLING)

# --- simulate-*: -simulate num=N -depth 20 -seed 7 ---------------------------------------------------------------
# 2188 with 1 worker (v1.7.4:7, rolling:7); 2269 is information. v1.7.4 prints no 2190 in a simulation; rolling
# does, and names Init with a location in the first state (P5). The seed is fixed, and both builds took the same
# behaviours, so the values are asserted.
basics(
    "simulate-deadlock",
    status="FAILURE",  # 2114: v1.7.4:26, rolling:30
    verdict="ERRORS",
    mode="simulate",
    progress=True,  # 2209: v1.7.4:47, rolling:51
    info=[2269],  # v1.7.4:23, rolling:24
    errors=[(2114, "deadlock", None)],  # v1.7.4:27, rolling:31
    related=[[2121]],  # v1.7.4:29, rolling:33
    traces=[(3, None, False)],  # v1.7.4:32-46, rolling:36-50
)
# Headers v1.7.4:33, 38, 43; rolling:37, 42, 47.
states("simulate-deadlock", 0, "x", _counting("Next", _DEADLOCK_NEXT, [0, 1, 2]), STABLE, "-stable")
states(
    "simulate-deadlock",
    0,
    "x",
    [(*_DEADLOCK_INIT, 0), ("Next", _DEADLOCK_NEXT, 1), ("Next", _DEADLOCK_NEXT, 2)],
    ROLLING,
    "-rolling",
)

for _lines, _suffix, _name_ in ((STABLE, "-stable", None), (ROLLING, "-rolling", "Reach")):
    basics(
        "simulate-liveness",
        lines=_lines,
        suffix=_suffix,
        status="FAILURE",  # 2116: v1.7.4:29, rolling:33 (no name on v1.7.4:30, "Reach" on rolling:34)
        verdict="ERRORS",
        mode="simulate",
        progress=True,  # 2209: v1.7.4:56, rolling:60
        info=[2212, 2269],  # v1.7.4:23 and 26, rolling:24 and 27
        errors=[(2116, "property", _name_)],
        related=[[2264]],  # v1.7.4:33, rolling:37
        traces=[(3, 1, False)],  # 2122 "1: Back to state": v1.7.4:52, rolling:56
    )
_LIVEBACK = ("LiveBack", 5, 9, 5, 24)
# Headers v1.7.4:38, 43, 48; rolling:42, 47, 52.
states("simulate-liveness", 0, "x", _counting("Next", _LIVEBACK, [0, 1, 2]), STABLE, "-stable")
states(
    "simulate-liveness",
    0,
    "x",
    [("Init", ("LiveBack", 4, 9, 4, 13), 0), ("Next", _LIVEBACK, 1), ("Next", _LIVEBACK, 2)],
    ROLLING,
    "-rolling",
)

basics(
    "simulate-violation",
    status="FAILURE",  # 2110: v1.7.4:30, rolling:34
    verdict="ERRORS",
    mode="simulate",
    progress=True,  # 2209: v1.7.4:91, rolling:95
    info=[2269],  # v1.7.4:27, rolling:28
    errors=[(2110, "invariant", "Small")],  # v1.7.4:31, rolling:35
    related=[[2121]],  # v1.7.4:33, rolling:37
    traces=[(4, None, False)],  # v1.7.4:36-90, rolling:40-94
)


def _simulate_violation_rows(first: tuple[str | None, Loc | None]) -> list[Row]:
    # v1.7.4:37-90, rolling:41-94: alpha 1, then gamma 2, then beta 2.
    a1, g2, b2 = ("alpha", 1), ("gamma", 2), ("beta", 2)
    return [
        (*first, [("store", _vstore(), True), ("n", vint(0), True), ("log", vseq(), True)]),
        ("Next", _V_NEXT, [("store", _vstore([1]), True), ("n", vint(1), True), ("log", _vlog(a1), True)]),
        ("Next", _V_NEXT, [("store", _vstore([1], [], [2]), True), ("n", vint(2), True), ("log", _vlog(a1, g2), True)]),
        (
            "Next",
            _V_NEXT,
            [("store", _vstore([1], [2], [2]), True), ("n", vint(3), True), ("log", _vlog(a1, g2, b2), True)],
        ),
    ]


trace_states("simulate-violation", 0, _simulate_violation_rows((None, None)), STABLE, "-stable")
trace_states("simulate-violation", 0, _simulate_violation_rows(("Init", _V_INIT)), ROLLING, "-rolling")

basics(
    "simulate-violation-diff",
    status="FAILURE",  # 2110: v1.7.4:26, rolling:30
    verdict="ERRORS",
    mode="simulate",
    progress=True,  # 2209: v1.7.4:62, rolling:66
    info=[2269],  # v1.7.4:23, rolling:24
    errors=[(2110, "invariant", "Inv")],  # v1.7.4:27, rolling:31
    related=[[2121]],  # v1.7.4:29, rolling:33
    traces=[(5, None, False)],  # v1.7.4:32-61, rolling:36-65
)


def _simulate_diff_rows(first: tuple[str | None, Loc | None]) -> list[Row]:
    # v1.7.4:32-61, rolling:36-65: a moves once, then b and c three times; in a simulation the last state is not
    # printed in full, so a is carried into states 3 to 5.
    rows: list[Row] = [
        (*first, [("a", vint(0), True), ("b", vint(0), True), ("c", _C0, True)]),
        ("Next", _DIFF_A, [("a", vint(1), True), ("b", vint(0), False), ("c", _C0, False)]),
    ]
    for b in range(1, 4):
        c = vseq(vint(0), vint(b), vint(0))
        rows.append(("Next", _DIFF_B, [("a", vint(1), False), ("b", vint(b), True), ("c", c, True)]))
    return rows


trace_states("simulate-violation-diff", 0, _simulate_diff_rows((None, None)), STABLE, "-stable")
trace_states("simulate-violation-diff", 0, _simulate_diff_rows(("Init", ("Diff", 4, 9, 4, 48))), ROLLING, "-rolling")

# --- stale-*-tool: a PlusCal spec changed since its translation (research 22, P8) --------------------------------
# One SANY warning, and the model is checked: no error, exit 0. v1.7.4 prints "!! WARNING: <text>" under the
# Parsing line (v1.7.4:14); rolling a warning block, "In module M" and the text (rolling:15-20).
for _case, _module in (
    ("stale-alg-tool", "PcalStaleAlg"),
    ("stale-both-tool", "PcalStaleBoth"),
    ("stale-tla-tool", "PcalStaleTla"),
):
    basics(
        _case,
        status="SUCCESS",  # a SANY warning is not a failure (P3); 2186: v1.7.4:48, rolling:57
        verdict="NO_ERROR",
        progress=True,  # 2200: v1.7.4:36, rolling:45
        diagnostics=1,
        errors=[],
        related=[],
        traces=[],
        stats=(4, 3, 0, 3),  # 2199 v1.7.4:39 rolling:48; 2194 v1.7.4:42 rolling:51
    )
    for _line in ("stable", "rolling"):

        def _stale_warning(r: RunResult, case: str = _case, module: str = _module, line: str = _line) -> None:
            # The text is kept as printed (v1.7.4's text for "both" is misspelt), so it is read from the capture.
            d = _diagnostic(r, 0)
            _same(
                "(tool, severity, module, location)",
                (d.tool, d.severity, d.module, d.location),
                ("sany", "warning", module, None),
            )
            _file_ends("diagnostic", d.file, f"{module}.tla")
            text = _capture(case, line)
            if line == "stable":
                expected = next(t.removeprefix("!! WARNING: ") for t in text if t.startswith("!! WARNING: "))
            else:
                expected = next(t for t in text[text.index(f"In module {module}") + 1 :] if t)
            _same("message as printed", d.message, expected)

        add(_case, "sany", f"warning-{_line}", _stale_warning, frozenset({_line}))

# --- tool-act: Act.tla, an action property violated ---------------------------------------------------------------
basics(
    "tool-act",
    status="FAILURE",  # 2112: v1.7.4:29, rolling:30
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:45, rolling:46
    errors=[(2112, "property", None)],  # "Action property Dec is violated.": P5 reads names of 2110, 2116, 2404 only
    related=[[2121]],  # v1.7.4:32, rolling:33
    traces=[(2, None, False)],  # no loop line: v1.7.4:35-44, rolling:36-45
)
# Headers v1.7.4:36, 41; rolling:37, 42.
states("tool-act", 0, "x", _counting("Next", ("Act", 5, 9, 5, 27), [0, 1]))

# --- tool-asrt: Asrt.tla, an Assert that fails -------------------------------------------------------------------
basics(
    "tool-asrt",
    status="FAILURE",  # 2132: v1.7.4:35, rolling:36
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:63, rolling:64
    errors=[(2132, "assertion", None)],
    related=[[2121, 2103]],  # 2121 before the states (v1.7.4:39, rolling:40), 2103 after (v1.7.4:52, rolling:53)
    traces=[(2, None, False)],  # v1.7.4:42-51, rolling:43-52
)
# Headers v1.7.4:43, 48; rolling:44, 49.
states("tool-asrt", 0, "x", _counting("Next", ("Asrt", 5, 9, 5, 52), [0, 1]))

# --- tool-assum: Assum.tla, a false ASSUME -----------------------------------------------------------------------
basics(
    "tool-assum",
    status="FAILURE",  # 2104: v1.7.4:23, rolling:24
    verdict="ERRORS",  # an assumption is a finding about the model (P3)
    progress=False,
    errors=[(2104, "assumption", None)],
    related=[[]],
    traces=[None],
)

# --- tool-badcfg: BadCfg.tla, a cfg naming an operator the spec does not define ------------------------------------
basics(
    "tool-badcfg",
    status="FAILURE",  # 2229: v1.7.4:23, rolling:24
    verdict="NOT_CHECKED",
    progress=False,
    errors=[(2229, "config", None)],
    related=[[]],
    traces=[None],
)

# --- tool-cfg-missing, tool-nocfg, tool-nospecfile (5001) and tool-cfgsyn (5003): cfg errors -----------------------
# v1.7.4: a 1000 holding the 5001 or 5003 at severity 0 (v1.7.4:10-19), which gives it the kind config (P5), then
# 2186 (v1.7.4:20). Rolling: the 5001 or 5003 at the top level (rolling:10-13); after a 5001 the output ends with
# no 2186, after the 5003 a 2186 follows (rolling:14). No 2185 in any of them.
for _case, _code, _rolling_finished in (
    ("tool-cfg-missing", 5001, False),
    ("tool-nocfg", 5001, False),
    ("tool-nospecfile", 5001, False),
    ("tool-cfgsyn", 5003, True),
):
    basics(
        _case,
        lines=STABLE,
        suffix="-stable",
        status="FAILURE",
        verdict="NOT_CHECKED",
        started=False,
        progress=False,
        errors=[(1000, "config", None)],
        related=[[]],
        traces=[None],
    )
    basics(
        _case,
        lines=ROLLING,
        suffix="-rolling",
        status="FAILURE",
        verdict="NOT_CHECKED",
        phase="FINISHED" if _rolling_finished else "NOT_STARTED",
        started=False,
        finished=_rolling_finished,
        progress=False,
        errors=[(_code, "config", None)],
        related=[[]],
        traces=[None],
    )

    def _cfg_stable_shape(r: RunResult, code: int = _code) -> None:
        # v1.7.4:10-19: four lines, then ": " and the nested message of two lines.
        message = _error(r, 0).message
        _same("body", _body_shape(message), ["line"] * 4 + [code])
        nested = message.nested[0]
        _same("nested (severity, before, lines)", (nested.severity, nested.before, len(nested.lines)), (0, ": ", 2))

    def _cfg_rolling_shape(r: RunResult) -> None:
        # rolling:10-13: severity 1, two lines, nothing nested.
        message = _error(r, 0).message
        _same("(severity, body)", (message.severity, _body_shape(message)), (1, ["line", "line"]))

    add(_case, "errors", "config-message-shape-stable", _cfg_stable_shape, STABLE)
    add(_case, "errors", "config-message-shape-rolling", _cfg_rolling_shape, ROLLING)

# --- tool-eval: Eval.tla, an invariant that divides by zero ------------------------------------------------------
basics(
    "tool-eval",
    status="FAILURE",  # 1000: v1.7.4:26, rolling:27
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:40, rolling:41
    errors=[(1000, "evaluation", None)],  # it holds one 2179 (v1.7.4:27-29, rolling:28-30), whose kind it takes (P5)
    related=[[2103]],  # v1.7.4:31, rolling:32
    traces=[None],
)


@fact("tool-eval", "errors", "message-shape")
def _eval_shape(r: RunResult) -> None:
    # v1.7.4:26-30, rolling:27-31: the 1000's body is the 2179 alone, with nothing before it. Both builds nest it.
    message = _error(r, 0).message
    _same("body", _body_shape(message), [2179])
    nested = message.nested[0]
    _same(
        "nested 2179 (severity, before, after, lines)",
        (nested.severity, nested.before, nested.after, len(nested.lines)),
        (0, "", "", 1),
    )


# --- tool-help: -help, TLC's manual page and no message at all ----------------------------------------------------
basics(
    "tool-help",
    status="RUNNING",  # no message, so no 2186 (v1.7.4:1-134, rolling:1-210)
    verdict="INCOMPLETE",
    phase="NOT_STARTED",
    mode=None,
    workers=None,
    tool=False,
    started=False,
    finished=False,
    progress=False,
    output=None,
    errors=[],
    related=[],
    traces=[],
)
# Every line is output, as printed (D9), ANSI codes included; the text is read from the capture.
add("tool-help", "run", "output-stable", _output_is_capture("tool-help", "stable"), STABLE)
add("tool-help", "run", "output-rolling", _output_is_capture("tool-help", "rolling"), ROLLING)

# --- tool-missing-module, tool-name-mismatch: SANY abort blocks inside TLC (P8) ----------------------------------
basics(
    "tool-missing-module",
    status="FAILURE",  # 3002: v1.7.4:32, rolling:35
    verdict="NOT_CHECKED",
    progress=False,
    diagnostics=1,  # the abort block: v1.7.4:16-23, rolling:16-25 (its second copy dropped, P8)
    errors=[(3002, "parse", None)],
    related=[[]],
    traces=[None],
)
basics(
    "tool-name-mismatch",
    status="FAILURE",  # 3002: v1.7.4:31, rolling:34
    verdict="NOT_CHECKED",
    progress=False,
    diagnostics=1,  # v1.7.4:15-22, rolling:15-24
    errors=[(3002, "parse", None)],
    related=[[]],
    traces=[None],
)

# v1.7.4 says "Unknown location" (v1.7.4:21), rolling "In module MissMod" (rolling:18): a module, and so a file.
for _lines, _suffix, _module, _file in (
    (STABLE, "-stable", None, None),
    (ROLLING, "-rolling", "MissMod", "MissMod.tla"),
):

    def _missing_module(r: RunResult, module: str | None = _module, file: str | None = _file) -> None:
        d = _diagnostic(r, 0)
        _same(
            "(tool, severity, module, location)",
            (d.tool, d.severity, d.module, d.location),
            ("sany", "error", module, None),
        )
        _file_ends("diagnostic", d.file, file)
        _holds("message names the missing module", "NoSuchModule" in d.message, d.message)  # v1.7.4:23, rolling:20

    add("tool-missing-module", "sany", "diagnostic" + _suffix, _missing_module, _lines)


@fact("tool-name-mismatch", "sany", "diagnostic")
def _name_mismatch(r: RunResult) -> None:
    # "Unknown location" on both (v1.7.4:20, rolling:17): no module, no file; the message names both names
    # (v1.7.4:22, rolling:19).
    d = _diagnostic(r, 0)
    _same(
        "(tool, severity, module, location, file)",
        (d.tool, d.severity, d.module, d.location, d.file),
        ("sany", "error", None, None, None),
    )
    _holds("message names the file and the module", "Mismatch" in d.message and "Other" in d.message, d.message)


# --- tool-nexteval: NextEval.tla, Next divides by zero -----------------------------------------------------------
basics(
    "tool-nexteval",
    status="FAILURE",  # 2179: v1.7.4:29, rolling:30
    verdict="ERRORS",
    progress=True,  # 2200: v1.7.4:48, rolling:49
    errors=[(2179, "evaluation", None)],  # at the top level, with a trace (P5)
    related=[[2121, 2103]],  # v1.7.4:32 and 40, rolling:33 and 41
    traces=[(1, None, False)],  # v1.7.4:35-39, rolling:36-40
)
states("tool-nexteval", 0, "x", [(None, None, 0)])  # v1.7.4:36-37, rolling:37-38

# --- tool-noargs, tool-workers-bad: command lines TLC refuses (1102 at v1.7.4:4, rolling:4) -----------------------
_refused("tool-noargs")
_refused("tool-workers-bad")

# --- tool-oom: Oom.tla with -Xmx64m ------------------------------------------------------------------------------
basics(
    "tool-oom",
    status="FAILURE",  # 1000: v1.7.4:26, rolling:27
    verdict="ERRORS",  # exceptions after 2189 (v1.7.4:23, rolling:24)
    progress=True,  # 2200: v1.7.4:38, rolling:41
    errors=[
        (1000, "exception", None),  # "Java heap space": v1.7.4:26-28, rolling:27-29
        (2147, "exception", None),  # not a continuation code, so an error of its own: v1.7.4:29, rolling:30
    ],
    related=[[], []],
    traces=[None, None],
)


@fact("tool-oom", "errors", "heap-message")
def _oom_shape(r: RunResult) -> None:
    # v1.7.4:27, rolling:28: the 1000 is the one line the JVM gave.
    _same("1000 lines", _error(r, 0).message.lines, ("Java heap space",))


# --- warn4802-tool, warnstutter-tool: SANY errors that TLC refuses with 3002 (D55) --------------------------------
basics(
    "warn4802-tool",
    status="FAILURE",  # 3002: v1.7.4:33, rolling:32
    verdict="NOT_CHECKED",
    progress=False,
    diagnostics=1,  # "Semantic errors:" v1.7.4:17-23, rolling:17-23
    errors=[(3002, "parse", None)],
    related=[[]],
    traces=[None],
)


@fact("warn4802-tool", "sany", "diagnostic")
def _warn4802(r: RunResult) -> None:
    # v1.7.4:21 and 23, rolling:21 and 23: an error, not a warning (D55).
    d = _diagnostic(r, 0)
    _same("(tool, severity, module)", (d.tool, d.severity, d.module), ("sany", "error", "Warn4802"))
    _same("location", _loc(d.location), ("Warn4802", 4, 16, 4, 16))
    _same("message", d.message, "Non-unique fields in constructor.")
    _file_ends("diagnostic", d.file, "Warn4802.tla")


basics(
    "warnstutter-tool",
    status="FAILURE",  # 3002: v1.7.4:38, rolling:37
    verdict="NOT_CHECKED",
    progress=False,
    diagnostics=2,  # "*** Errors: 2": v1.7.4:19, rolling:19
    errors=[(3002, "parse", None)],
    related=[[]],
    traces=[None],
)


@fact("warnstutter-tool", "sany", "two-lints")
def _warnstutter(r: RunResult) -> None:
    # The two stuttering lints, v1.7.4:21 and 26, rolling:21 and 26: errors (D55).
    _same("number of diagnostics", len(r.sany), 2)
    _same("(severity, module) of each", [(d.severity, d.module) for d in r.sany], [("error", "WarnStutter")] * 2)
    _same(
        "locations", [_loc(d.location) for d in r.sany], [("WarnStutter", 7, 9, 7, 22), ("WarnStutter", 8, 10, 8, 19)]
    )
    for n, d in enumerate(r.sany, 1):
        _file_ends(f"diagnostic {n}", d.file, "WarnStutter.tla")


FACTS: tuple[Fact, ...] = tuple(_FACTS)
