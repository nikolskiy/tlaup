"""TLC's ``-tool`` output to events and a ``RunResult`` (design 10 P2 to P5, P8 and P9; package 13).

``TlcParser`` owns one ``Framer`` and one ``SanyParser``. Every line goes to the framer; an ``Unframed`` line
between messages 2220 and 2219 goes to the SANY parser, and any other becomes an ``OutputLine``; a top-level
message is interpreted, severity first (P4, rules 1 to 4). Every top-level message gives at least one event that
carries it, and every unframed line no parser used gives one ``OutputLine`` (decision D9). The result is one
object for the parser's life, filled as lines arrive; the verdict is decided in ``close()`` (P3, D54).

A state message (2217, and 2216 for ``-dfid`` on v1.7.4) whose header parses is a ``TraceState`` of the current
error's trace; 2122 and 2218 end that trace with a loop or stuttering (P5). A state that leaves a variable out
(``-difftrace``) has it carried forward from the state before, marked as not printed.
"""

from __future__ import annotations

import re
from dataclasses import replace
from enum import Enum
from typing import TYPE_CHECKING

from tlaup_parse.codes import CODES
from tlaup_parse.framing import Framer, Unframed
from tlaup_parse.model import (
    CheckpointStarted,
    CheckpointWritten,
    CoverageAdded,
    CoverageItem,
    Diagnostic,
    DiagnosticFound,
    ErrorExtended,
    ErrorKind,
    ErrorOpened,
    FinalStats,
    Finished,
    Information,
    Location,
    ModeSeen,
    OutputLine,
    OverrideLoaded,
    Phase,
    PhaseChanged,
    Progress,
    ProgressMade,
    Recovered,
    RunResult,
    StatsUpdated,
    Status,
    TlcError,
    ToolInfo,
    Trace,
    TraceClosed,
    TraceState,
    TraceStateAdded,
    UnknownMessage,
    Variable,
    Verdict,
    VersionSeen,
    WarningFound,
)
from tlaup_parse.sany import SanyLineClass, SanyParser
from tlaup_parse.values import parse_value

if TYPE_CHECKING:
    from collections.abc import Callable

    from tlaup_parse.model import Event, TlcMessage

# --- Patterns (P3, P5, P9 and package 13's "Shapes in the captures") ------------------------------------------------

_NUMBER = r"-?[0-9][0-9,]*"
_SPAN = r"line ([0-9]+), col ([0-9]+) to line ([0-9]+), col ([0-9]+) of module (\S+?)"

_VERSION = re.compile(r"TLC2 Version (?P<version>\S+)(?: of (?P<date>.+?))? \(rev: (?P<rev>\w+)\)")
_CALVER = re.compile(r"[0-9]{4}\.")
_WORKERS = re.compile(r"\bwith (?P<n>[0-9]+) workers?\b")
_STARTED = re.compile(r"Starting\.\.\. \((?P<at>.+)\)")
_FINISHED = re.compile(r"Finished in (?P<ms>[0-9]+)ms at \((?P<at>.+)\)")
_PROGRESS = re.compile(
    rf"Progress\((?P<diameter>{_NUMBER})\) at (?P<at>.+?): (?P<generated>{_NUMBER}) states generated"
    rf"(?: \([^)]*\))?, (?P<distinct>{_NUMBER}) distinct states found(?: \([^)]*\))?, "
    rf"(?P<queue>{_NUMBER}) states left on queue\."
)
_STATES_FOUND = re.compile(
    rf"(?P<generated>{_NUMBER}) states generated, (?P<distinct>{_NUMBER}) distinct states found"
    rf"(?:, (?P<queue>{_NUMBER}) states left on queue)?\."
)
_DEPTH = re.compile(rf"The depth of the complete state graph search is (?P<depth>{_NUMBER})\.")
_OUTDEGREE = re.compile(r"The average outdegree of the complete state graph is .*")
_SIMULATED = re.compile(rf"The number of states generated: (?P<generated>{_NUMBER})")
_COLLISION = re.compile(r"\s*calculated \(optimistic\):\s+val = (?P<val>\S+)")
_OVERRIDE = re.compile(r"Loading (?P<operator>\S+) operator override from (?P<java_class>\S+) with signature: ")
_CHECKPOINT = re.compile(r"Checkpointing of run (?P<folder>.+)")
_RECOVERED = re.compile(
    rf"Recovery completed\. (?P<examined>{_NUMBER}) states examined\. (?P<queued>{_NUMBER}) states on queue\."
)
_COVERAGE_ROW = re.compile(
    rf"<(?P<name>.+?) {_SPAN}(?: \(([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+)\))?>"
    r"(?:: (?P<first>[0-9]+)(?::(?P<second>[0-9]+))?)?"
)
_COVERAGE_EXPRESSION = re.compile(rf" *(?P<bars>\|*){_SPAN}: (?P<count>[0-9]+)")
# Trace states (P5): the header of a state, its action and location, the -dfid header, a loop and stuttering.
_STATE_HEADER = re.compile(r"(?P<n>[0-9]+): <(?P<inner>.*)>")
_STATE_ACTION = re.compile(
    r"(?P<action>.+?) line ([0-9]+), col ([0-9]+) to line ([0-9]+), col ([0-9]+) of module (?P<module>\S+)"
    r"(?: \(.*\))?"
)
_DFID_HEADER = re.compile(r"(?P<n>[0-9]+): ?")
_BACK_TO_STATE = re.compile(r"(?P<n>[0-9]+): Back to state: <(?P<inner>.*)>")
_STUTTERING = re.compile(r"(?P<n>[0-9]+): Stuttering")
_VARIABLE = re.compile(r"/\\ (?P<name>\S+) = (?P<rest>.*)")
_ONLY_VARIABLE = re.compile(r"(?P<name>\S+) = (?P<rest>.*)")
_ERROR_NAMES = {
    2110: re.compile(r"Invariant (?P<name>\S+) is violated\."),
    2116: re.compile(r"Temporal property (?P<name>\S+) was violated\."),
    2404: re.compile(r"Postcondition (?P<name>\S+) "),
}

# --- Tables ----------------------------------------------------------------------------------------------------------

_CONTINUATIONS = frozenset({2103, 2121, 2264})  # related messages of the current error (P5)
_STATE_CODES = frozenset({2216, 2217})  # a state; 2216 is -dfid's on v1.7.4 (P5)
_LOOP, _STUTTER = 2122, 2218
_MODES = {2187: "exhaustive search", 2188: "simulate", 2271: "depth-first"}
_PHASES = {
    2220: Phase.PARSING,
    2219: Phase.STARTING,
    2185: Phase.STARTING,
    2189: Phase.INITIAL_STATES,
    2190: Phase.CHECKING,
    2192: Phase.LIVENESS,
    2267: Phase.CHECKING,
}
_COVERAGE_KINDS = {2773: "init", 2772: "action", 2774: "property", 2779: "variable"}
_SANY_WINDOW_OPEN, _SANY_WINDOW_CLOSE = 2220, 2219
_GENERAL = 1000
# Kinds that are a finding about the model; ``exception`` and ``other`` count once the initial states began (P3).
_FINDINGS = frozenset(
    {
        ErrorKind.INVARIANT,
        ErrorKind.DEADLOCK,
        ErrorKind.PROPERTY,
        ErrorKind.ASSERTION,
        ErrorKind.ASSUMPTION,
        ErrorKind.POSTCONDITION,
        ErrorKind.EVALUATION,
    }
)
_LATE_KINDS = frozenset({ErrorKind.EXCEPTION, ErrorKind.OTHER})
_PHASE_ORDER = list(Phase)
_BOUNDED_MODES = frozenset({"simulate", "depth-first"})


class _Class(Enum):
    """What a top-level message is, decided by severity (P4, rule 1)."""

    ERROR = "error"
    WARNING = "warning"
    STATE = "state"
    INFORMATION = "information"


def _severities(message: TlcMessage) -> set[int]:
    """The severities of every message nested in ``message``, at any depth."""
    found: set[int] = set()
    for inner in message.nested:
        found.add(inner.severity)
        found |= _severities(inner)
    return found


def _class_of(message: TlcMessage) -> _Class:
    nested = _severities(message)
    if message.severity in (1, 2) or nested & {1, 2}:
        return _Class.ERROR
    if message.severity == 3 or 3 in nested:
        return _Class.WARNING
    if message.severity == 4:
        return _Class.STATE
    return _Class.INFORMATION


def _number(text: str) -> int:
    return int(text.replace(",", ""))


def _optional_number(text: str | None) -> int | None:
    return None if text is None else _number(text)


def _text(message: TlcMessage) -> str:
    """The message's own lines joined; a pattern is matched against the whole of it with ``fullmatch``."""
    return "\n".join(message.lines)


def _first_line(message: TlcMessage) -> str:
    return message.lines[0] if message.lines else ""


def _location(match: re.Match[str], first: int) -> Location:
    """The span ``line L, col C to line L2, col C2 of module M`` whose five groups start at group ``first``."""
    return Location(
        module=match.group(first + 4),
        line=int(match.group(first)),
        column=int(match.group(first + 1)),
        end_line=int(match.group(first + 2)),
        end_column=int(match.group(first + 3)),
    )


def _kind_of(message: TlcMessage) -> ErrorKind:
    """The code's kind in ``CODES``, or ``other``; a 1000 holding one message of a kind of its own takes it (P5)."""
    info = CODES.get(message.code)
    kind = ErrorKind.OTHER if info is None or info.kind is None else info.kind
    if message.code == _GENERAL and len(message.nested) == 1:
        inner = CODES.get(message.nested[0].code)
        if inner is not None and inner.kind is not None and inner.kind not in _LATE_KINDS:
            return inner.kind
    return kind


def _variables(body: tuple[str, ...]) -> list[Variable]:
    """The variables of a state's body, the header left out (P5).

    A line ``/\\ <name> = `` begins a variable; when no line starts with ``/\\ ``, the first line ``<name> = ``
    begins the only one. A variable runs to the next start or the end, trailing blank lines dropped.
    """
    prefixed = any(line.startswith("/\\ ") for line in body)
    starts: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(body):
        match = (_VARIABLE if prefixed else _ONLY_VARIABLE).fullmatch(line)
        if match is not None:
            starts.append((index, match))
            if not prefixed:
                break
    variables: list[Variable] = []
    for number, (index, match) in enumerate(starts):
        end = starts[number + 1][0] if number + 1 < len(starts) else len(body)
        text = [match["rest"], *body[index + 1 : end]]
        while len(text) > 1 and not text[-1].strip():
            text.pop()
        raw = "\n".join(text)
        variables.append(Variable(name=match["name"], value=parse_value(raw), raw=raw))
    return variables


def _carried(variables: list[Variable], previous: TraceState | None) -> tuple[Variable, ...]:
    """The previous state's variables in its order, each replaced by this state's where printed (-difftrace, P5).

    A variable the previous state did not have is taken as printed, after the others.
    """
    if previous is None:
        return tuple(variables)
    printed = {variable.name: variable for variable in variables}
    known = {variable.name for variable in previous.variables}
    merged = [printed.get(old.name, replace(old, printed=False)) for old in previous.variables]
    merged.extend(variable for variable in variables if variable.name not in known)
    return tuple(merged)


def _state(message: TlcMessage, previous: TraceState | None) -> TraceState | None:
    """The state a state message holds, or None when its header matches no pattern (P5)."""
    lines = message.lines
    first = lines[0] if lines else ""
    action: str | None = None
    location: Location | None = None
    match = _STATE_HEADER.fullmatch(first) or _DFID_HEADER.fullmatch(first)
    if match is None:
        return None
    # header is the text inside the brackets (P5), or "" for a -dfid header, which has none; reporters never
    # parse TLC text (D8).
    inner = match.groupdict().get("inner") or ""
    acting = _STATE_ACTION.fullmatch(inner)
    if acting is not None:
        action, location = acting["action"], _location(acting, 2)
    return TraceState(
        index=int(match["n"]),
        action=action,
        location=location,
        header=inner,
        variables=_carried(_variables(lines[1:]), previous),
        lines=lines,
    )


def _name_of(message: TlcMessage) -> str | None:
    pattern = _ERROR_NAMES.get(message.code)
    match = None if pattern is None else pattern.match(_first_line(message))
    return None if match is None else match["name"]


class TlcParser:
    """Turns the lines of a ``-tool`` run into events and one ``RunResult``; see the module docstring."""

    def __init__(self, *, max_output_lines: int = 10_000) -> None:
        self._max_output_lines = max_output_lines
        self._result = RunResult()
        self._framer = Framer()
        self._sany = SanyParser()
        self._sany_window = "before"  # "before", "open", then "shut" for good (P8)
        self._current: TlcError | None = None
        self._tracing: TlcError | None = None  # the error whose trace is open: it has a state and is not closed
        self._closed: set[int] = set()  # id() of every error whose trace was closed
        self._errors_late: list[bool] = []  # per error: the phase had reached INITIAL_STATES when it opened
        self._reached = Phase.NOT_STARTED  # the furthest phase reached so far
        self._finished = False  # a 2186 arrived
        self._typed: dict[int, Callable[[TlcMessage], list[Event] | None]] = {
            2262: self._version,
            2186: self._finish,
            2168: self._override,
            2195: self._checkpoint_started,
            2196: self._checkpoint_written,
            2197: self._recovered,
            2198: self._recovered,
            2200: self._progress,
            2209: self._progress,
            2199: self._stats_found,
            2204: self._stats_found,
            2194: self._stats_depth,
            2268: self._stats_outdegree,
            2193: self._stats_collision,
            2210: self._stats_simulated,
            **dict.fromkeys(_MODES, self._mode),
            **dict.fromkeys(_PHASES, self._phase),
            **dict.fromkeys(_COVERAGE_KINDS, self._coverage_row),
            2221: self._coverage_expression,
        }

    @property
    def result(self) -> RunResult:
        return self._result

    def feed(self, line: str) -> list[Event]:
        """Take one line, with or without its newline; return the events it produced, in order."""
        events: list[Event] = []
        for item in self._framer.feed(line):
            events.extend(self._item(item))
        return events

    def close(self) -> list[Event]:
        """End of input: flush the framer and the SANY parser, decide the verdict; return the events."""
        events: list[Event] = []
        for item in self._framer.close():
            events.extend(self._item(item))
        if self._sany_window == "open":
            events.extend(self._close_sany())
        events.extend(self._close_trace(None))
        self._result.verdict = self._verdict()
        return events

    # --- The path of a line ----------------------------------------------------------------------------------------

    def _item(self, item: Unframed | TlcMessage) -> list[Event]:
        if isinstance(item, Unframed):
            self._result.unframed_lines += 1
            if self._sany_window == "open":
                return self._sany_line(item.line)
            return [self._output(item.line)]
        events: list[Event] = []
        if item.before:
            self._result.unframed_lines += 1
            events.append(self._output(item.before))
        events.extend(self._message(item))
        if item.after:
            self._result.unframed_lines += 1
            events.append(self._output(item.after))
        return events

    def _output(self, line: str) -> OutputLine:
        output = self._result.output
        output.append(line)
        if len(output) > self._max_output_lines:
            excess = len(output) - self._max_output_lines
            del output[:excess]
            self._result.output_dropped += excess
        return OutputLine(line)

    def _sany_line(self, line: str) -> list[Event]:
        step = self._sany.feed(line)
        events: list[Event] = self._diagnostics(step.diagnostics)
        if step.line_class is SanyLineClass.OTHER:
            events.append(self._output(line))
        return events

    def _diagnostics(self, diagnostics: tuple[Diagnostic, ...]) -> list[Event]:
        events: list[Event] = []
        for diagnostic in diagnostics:
            self._result.sany.append(diagnostic)
            if diagnostic.severity == "error":
                self._result.status = Status.FAILURE
            events.append(DiagnosticFound(diagnostic))
        return events

    def _close_sany(self) -> list[Event]:
        events = self._diagnostics(self._sany.close().diagnostics)
        sany = self._sany.result
        self._result.module_files.update(sany.module_files)
        self._result.sany_lines_used = sany.lines_used
        self._sany_window = "shut"
        return events

    # --- Interpreting a top-level message (P4, rules 1 to 4) ---------------------------------------------------

    def _message(self, message: TlcMessage) -> list[Event]:
        cls = _class_of(message)
        if cls is _Class.STATE and message.code in _STATE_CODES | {_LOOP, _STUTTER}:
            return self._trace_message(message)
        return [*self._close_trace(None), *self._classified(message, cls)]

    def _classified(self, message: TlcMessage, cls: _Class) -> list[Event]:
        known = message.code in CODES
        match cls:
            case _Class.ERROR:
                if not known:
                    self._result.unknown_messages.append(message)
                return [self._error(message)]
            case _Class.WARNING:
                if not known:
                    self._result.unknown_messages.append(message)
                self._result.warnings.append(message)
                return [WarningFound(message)]
            case _Class.STATE:
                # A severity-4 message that is no state, loop or stuttering message, shown as printed.
                if not known:
                    self._result.unknown_messages.append(message)
                return [UnknownMessage(message)]
            case _Class.INFORMATION:
                return self._information(message, known=known)

    def _error(self, message: TlcMessage) -> Event:
        if message.code in _CONTINUATIONS and self._current is not None:
            self._current.related.append(message)
            return ErrorExtended(message, self._current)
        kind = ErrorKind.OTHER if message.code in _CONTINUATIONS else _kind_of(message)
        return self._open(TlcError(kind=kind, name=_name_of(message), message=message, related=[], trace=None))

    def _open(self, error: TlcError) -> ErrorOpened:
        self._result.status = Status.FAILURE
        self._result.errors.append(error)
        self._errors_late.append(_PHASE_ORDER.index(self._reached) >= _PHASE_ORDER.index(Phase.INITIAL_STATES))
        self._current = error
        return ErrorOpened(error.message, error)

    # --- Trace states (P5) -------------------------------------------------------------------------------------

    def _trace_message(self, message: TlcMessage) -> list[Event]:
        """A state (2216, 2217), a loop (2122) or stuttering (2218); one that cannot be placed is shown as printed."""
        events = self._trace_state(message) if message.code in _STATE_CODES else self._trace_end(message)
        return [UnknownMessage(message)] if events is None else events

    def _trace_state(self, message: TlcMessage) -> list[Event] | None:
        events: list[Event] = []
        error = self._current
        if error is None:  # a state before any error (not seen) opens an error of kind other (P5)
            if _state(message, None) is None:
                return None
            error = TlcError(kind=ErrorKind.OTHER, name=None, message=message, related=[], trace=None)
            events.append(self._open(error))
        elif id(error) in self._closed:  # its trace was closed, by 2122, 2218 or another message (not seen)
            return None
        trace = error.trace
        state = _state(message, None if trace is None else trace.states[-1])
        if state is None:
            return None
        if trace is None:
            trace = error.trace = Trace(states=[], loop_to=None, stuttering=False)
        trace.states.append(state)
        self._tracing = error
        events.append(TraceStateAdded(message, error, state))
        return events

    def _trace_end(self, message: TlcMessage) -> list[Event] | None:
        error = self._tracing
        if error is None or error.trace is None:  # a loop or stuttering with no open trace (not seen)
            return None
        pattern = _BACK_TO_STATE if message.code == _LOOP else _STUTTERING
        match = pattern.fullmatch(message.lines[0] if message.lines else "")
        if match is None:
            return None
        if message.code == _LOOP:
            error.trace.loop_to = int(match["n"])
        else:
            error.trace.stuttering = True
        return self._close_trace(message)

    def _close_trace(self, message: TlcMessage | None) -> list[Event]:
        """``TraceClosed`` for the open trace, if any (P5)."""
        error = self._tracing
        if error is None or error.trace is None:
            return []
        self._tracing = None
        self._closed.add(id(error))
        return [TraceClosed(message, error, error.trace)]

    def _information(self, message: TlcMessage, *, known: bool) -> list[Event]:
        if not known:
            self._result.unknown_messages.append(message)
            return [UnknownMessage(message)]
        handler = self._typed.get(message.code)
        events = None if handler is None else handler(message)
        if events is None:  # no typed meaning, or a typed code whose text does not match its pattern
            self._result.info.append(message)
            return [Information(message)]
        return events

    # --- Typed information ----------------------------------------------------------------------------------------

    def _version(self, message: TlcMessage) -> list[Event] | None:
        raw = _text(message)
        match = _VERSION.fullmatch(raw)
        if match is None:
            return None
        version = match["version"]
        line = "rolling" if _CALVER.match(version) else "stable"
        tool = ToolInfo(version=version, revision=match["rev"], date=match["date"], line=line, raw=raw)
        self._result.tool = tool
        return [VersionSeen(message, tool)]

    def _mode(self, message: TlcMessage) -> list[Event] | None:
        result = self._result
        result.mode = _MODES[message.code]
        workers = _WORKERS.search(_text(message))
        if workers is not None:
            result.workers = int(workers["n"])
        return [ModeSeen(message, result.mode, result.workers)]

    def _phase(self, message: TlcMessage) -> list[Event] | None:
        events: list[Event] = []
        if message.code == _SANY_WINDOW_OPEN and self._sany_window == "before":
            self._sany_window = "open"
        elif message.code == _SANY_WINDOW_CLOSE and self._sany_window == "open":
            events.extend(self._close_sany())
        elif message.code == _SANY_WINDOW_CLOSE:
            self._sany_window = "shut"
        if message.code == 2185:
            started = _STARTED.fullmatch(_text(message))
            if started is not None:
                self._result.started = started["at"]
        events.append(PhaseChanged(message, self._enter(_PHASES[message.code])))
        return events

    def _enter(self, phase: Phase) -> Phase:
        self._result.phase = phase
        if _PHASE_ORDER.index(phase) > _PHASE_ORDER.index(self._reached):
            self._reached = phase
        return phase

    def _finish(self, message: TlcMessage) -> list[Event] | None:
        result = self._result
        match = _FINISHED.fullmatch(_text(message))
        result.duration_ms = None if match is None else int(match["ms"])
        result.finished = None if match is None else match["at"]
        self._enter(Phase.FINISHED)
        self._finished = True
        if result.status is Status.RUNNING:
            result.status = Status.SUCCESS
        return [Finished(message, result.duration_ms, result.finished)]

    def _override(self, message: TlcMessage) -> list[Event] | None:
        match = _OVERRIDE.match(_first_line(message))
        if match is None:
            return None
        # java_class is kept as printed: a class name or a file: address (package 13, OverrideLoaded).
        self._result.overrides_loaded.append(f"{match['java_class']}.{match['operator']}")
        return [OverrideLoaded(message, match["operator"], match["java_class"])]

    def _checkpoint_started(self, message: TlcMessage) -> list[Event] | None:
        match = _CHECKPOINT.fullmatch(_text(message))
        return None if match is None else [CheckpointStarted(message, match["folder"])]

    def _checkpoint_written(self, message: TlcMessage) -> list[Event] | None:
        return [CheckpointWritten(message)]

    def _recovered(self, message: TlcMessage) -> list[Event] | None:
        self._result.resumed = True
        match = _RECOVERED.fullmatch(_text(message))
        if match is None:
            return [Recovered(message, None, None)]
        return [Recovered(message, _number(match["examined"]), _number(match["queued"]))]

    def _progress(self, message: TlcMessage) -> list[Event] | None:
        match = _PROGRESS.fullmatch(_text(message))
        if match is None:
            return None
        progress = Progress(
            diameter=_number(match["diameter"]),
            generated=_number(match["generated"]),
            distinct=_number(match["distinct"]),
            queue=_number(match["queue"]),
            at=match["at"],
        )
        self._result.progress.append(progress)
        return [ProgressMade(message, progress)]

    def _stats(self, message: TlcMessage, stats: FinalStats) -> list[Event]:
        self._result.stats = stats
        return [StatsUpdated(message, stats)]

    def _stats_so_far(self) -> FinalStats:
        return self._result.stats or FinalStats(None, None, None, None, None, None)

    def _stats_found(self, message: TlcMessage) -> list[Event] | None:
        match = _STATES_FOUND.fullmatch(_text(message))
        if match is None:
            return None
        so_far = self._stats_so_far()
        queue = so_far.queue if match["queue"] is None else _number(match["queue"])
        stats = replace(
            so_far, total_states=_number(match["generated"]), distinct_states=_number(match["distinct"]), queue=queue
        )
        return self._stats(message, stats)

    def _stats_depth(self, message: TlcMessage) -> list[Event] | None:
        match = _DEPTH.fullmatch(_text(message))
        return (
            None
            if match is None
            else self._stats(message, replace(self._stats_so_far(), state_depth=_number(match["depth"])))
        )

    def _stats_outdegree(self, message: TlcMessage) -> list[Event] | None:
        text = _text(message)
        return (
            None
            if _OUTDEGREE.fullmatch(text) is None
            else self._stats(message, replace(self._stats_so_far(), outdegree=text))
        )

    def _stats_collision(self, message: TlcMessage) -> list[Event] | None:
        for line in message.lines:
            match = _COLLISION.fullmatch(line)
            if match is not None:
                return self._stats(message, replace(self._stats_so_far(), collision_probability=match["val"]))
        return None

    def _stats_simulated(self, message: TlcMessage) -> list[Event] | None:
        match = _SIMULATED.fullmatch(_first_line(message))
        if match is None:
            return None
        return self._stats(message, replace(self._stats_so_far(), total_states=_number(match["generated"])))

    def _coverage_row(self, message: TlcMessage) -> list[Event] | None:
        match = _COVERAGE_ROW.fullmatch(_text(message))
        if match is None:
            return None
        location = _location(match, 2)
        sub_location = None
        if match.group(7) is not None:
            sub_location = Location(
                module=location.module,
                line=int(match.group(7)),
                column=int(match.group(8)),
                end_line=int(match.group(9)),
                end_column=int(match.group(10)),
            )
        first, second = _optional_number(match["first"]), _optional_number(match["second"])
        count, distinct = (first, None) if second is None else (second, first)
        item = CoverageItem(
            kind=_COVERAGE_KINDS[message.code],
            name=match["name"],
            location=location,
            sub_location=sub_location,
            count=count,
            distinct=distinct,
            depth=0,
        )
        self._result.coverage.append(item)
        return [CoverageAdded(message, item)]

    def _coverage_expression(self, message: TlcMessage) -> list[Event] | None:
        match = _COVERAGE_EXPRESSION.fullmatch(_text(message))
        if match is None:
            return None
        item = CoverageItem(
            kind="expression",
            name=None,
            location=_location(match, 2),
            sub_location=None,
            count=int(match["count"]),
            distinct=None,
            depth=len(match["bars"]),
        )
        self._result.coverage.append(item)
        return [CoverageAdded(message, item)]

    # --- The verdict (P3, D54) -----------------------------------------------------------------------------------

    def _verdict(self) -> Verdict:
        result = self._result
        for error, late in zip(result.errors, self._errors_late, strict=True):
            if error.kind in _FINDINGS or (error.kind in _LATE_KINDS and late):
                return Verdict.ERRORS
        if result.errors or any(d.severity == "error" for d in result.sany):
            return Verdict.NOT_CHECKED
        if not self._finished:
            return Verdict.INCOMPLETE
        if result.mode in _BOUNDED_MODES:
            return Verdict.NO_ERROR_BOUNDED
        return Verdict.NO_ERROR
