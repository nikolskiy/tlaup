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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence
    from types import EllipsisType

    from tlaup_parse import CoverageItem, Location, RunResult, TlcError, TlcMessage, Trace, Variable

    Check = Callable[[RunResult], None]
    Loc = tuple[str, int, int, int | None, int | None]

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
    """An enum member's name (Status, Verdict, Phase)."""
    return str(getattr(member, "name", member))


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


def _mode(mode: str | None, workers: int | EllipsisType | None) -> Check:
    """The mode, and the workers unless ``workers`` is ``...`` (not asserted)."""
    if workers is ...:
        return lambda r: _same("mode", r.mode, mode)
    return lambda r: _same("mode and workers", (r.mode, r.workers), (mode, workers))


def _not_resumed(result: RunResult) -> None:
    _same("resumed", result.resumed, False)


def _times(started: bool, finished: bool) -> Check:
    """That the start (2185) and the finish (2186: time and duration) are set or not; never their values."""

    def check(r: RunResult) -> None:
        _same("started is set", r.started is not None, started)
        _same("finished is set", r.finished is not None, finished)
        _same("duration_ms is set", r.duration_ms is not None, finished)

    return check


def _progress(read: bool) -> Check:
    """That progress (2200, 2209) was read or not; never its counts."""
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


def _tool_rolling(result: RunResult) -> None:
    tool = result.tool
    _holds("a ToolInfo from 2262", tool is not None, tool)
    assert tool is not None  # for the type checker
    _same("tool line", tool.line, "rolling")
    _holds("tool version is a CalVer", re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.\d{6}", tool.version) is not None, tool)
    _holds("tool revision", tool.revision is not None and re.fullmatch(r"[0-9a-f]{7,}", tool.revision), tool)
    _same("tool date", tool.date, None)
    _holds("tool raw line", tool.raw.startswith(f"TLC2 Version {tool.version} (rev: "), tool)


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
    workers: int | EllipsisType | None = 1,
    started: bool = True,
    finished: bool = True,
    progress: bool,
    errors: Sequence[tuple[int, str, str | None]],
    related: Sequence[Sequence[int]],
    traces: Sequence[tuple[int, int | None, bool] | None],
    diagnostics: int = 0,
    output: Sequence[str] = (),
    info: Sequence[int] = (),
    warnings: Sequence[int] = (),
    overrides: Sequence[str] = (),
    coverage: bool = False,
    stats: tuple[int, int, int, int] | None = None,
) -> None:
    """Register the facts every case gets (package 08): run, errors, SANY and trace shape, plus the version.

    ``suffix`` keeps the names unique when a case is registered once per line. ``coverage`` true leaves the
    coverage rows to the case's own fact; ``stats`` None asserts no final counts (not a complete search).
    """
    run: list[tuple[str, Check]] = [
        ("status", _status(status)),
        ("verdict", _verdict(verdict)),
        ("phase", _phase(phase)),
        ("mode", _mode(mode, workers)),
        ("not-resumed", _not_resumed),
        ("times", _times(started, finished)),
        ("progress", _progress(progress)),
        ("output", _output(output)),
        ("info", _info(info)),
        ("no-unknown-messages", _no_unknown),
        ("warnings", _warnings(warnings)),
        ("overrides", _overrides(overrides)),
    ]
    if not coverage:
        run.append(("no-coverage", _no_coverage))
    if stats is not None:
        run.append(("final-counts", _stats(*stats)))
    for name, check in run:
        add(case, "run", name + suffix, check, lines)
    if "stable" in lines:
        add(case, "run", "tool-stable", _tool_stable, STABLE)
    if "rolling" in lines:
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

    add(case, "traces", f"states-{error + 1}", check, lines)


def _counting(action: str, location: Loc, values: Iterable[int]) -> list[tuple[str | None, Loc | None, int]]:
    """Rows for a trace whose first state is the initial predicate and every later one the same action."""
    return [(None, None, value) if n == 0 else (action, location, value) for n, value in enumerate(values)]


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
    workers=...,  # P3 reads workers from 2187; this run has 2188, so they are not asserted
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
    text = message.text_lines()
    _same("text lines", len(text), 8)
    _same("text line 5", text[4], ": Attempted to apply the operator overridden by the Java method")


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
    _same("last two lines", list(message.lines[-2:]), ["but it produced the following error:", "%2%"])


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


FACTS: tuple[Fact, ...] = tuple(_FACTS)
