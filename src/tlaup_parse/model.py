"""The result of one TLC run and the events a parser emits while it reads one (design 10 P3).

``to_dict()`` gives only JSON types and is what the expected files hold and what the JSON of milestone 4 will
publish, so the field names here are that schema. Every field is written, also when it is empty or ``None``.
``from_dict()`` reads that form back: ``RunResult.from_dict(r.to_dict()) == r``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, TypeVar

from tlaup_parse.values import JSONObject, Value

if TYPE_CHECKING:
    from collections.abc import Callable

_T = TypeVar("_T")


class Phase(Enum):
    """Where the run is; the values are the dictionary words."""

    NOT_STARTED = "not-started"
    PARSING = "parsing"
    STARTING = "starting"
    INITIAL_STATES = "initial-states"
    CHECKING = "checking"
    LIVENESS = "liveness"
    FINISHED = "finished"


class Status(Enum):
    """What the text shows so far; the runner may set ``INTERRUPTED``."""

    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    INTERRUPTED = "interrupted"


class Verdict(Enum):
    """What the run found, from TLC's messages (decision D54)."""

    ERRORS = "errors"
    NO_ERROR = "no-error"
    NO_ERROR_BOUNDED = "no-error-bounded"
    INCOMPLETE = "incomplete"
    NOT_CHECKED = "not-checked"


class ErrorKind(Enum):
    """The kind of an error; the table from code to kind is in P5."""

    INVARIANT = "invariant"
    DEADLOCK = "deadlock"
    PROPERTY = "property"
    ASSERTION = "assertion"
    ASSUMPTION = "assumption"
    POSTCONDITION = "postcondition"
    EVALUATION = "evaluation"
    CONFIG = "config"
    PARSE = "parse"
    EXCEPTION = "exception"
    USAGE = "usage"
    OTHER = "other"


def _optional(data: JSONObject | None, read: Callable[[JSONObject], _T]) -> _T | None:
    return None if data is None else read(data)


@dataclass(frozen=True)
class ToolInfo:
    version: str  # "2.19" or "2026.11.15.002146"
    revision: str | None  # "5a47802"
    date: str | None  # "08 August 2024" on 2.x builds, as printed; None on rolling builds
    line: str  # "stable" (a numbered version) or "rolling" (a CalVer): the two words
    # `build.toml` uses for a golden folder (01 T3)
    raw: str  # the whole line

    def to_dict(self) -> JSONObject:
        return {
            "version": self.version,
            "revision": self.revision,
            "date": self.date,
            "line": self.line,
            "raw": self.raw,
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> ToolInfo:
        return cls(
            version=data["version"],
            revision=data["revision"],
            date=data["date"],
            line=data["line"],
            raw=data["raw"],
        )


@dataclass(frozen=True)
class TlcMessage:
    code: int
    severity: int  # the number in the marker: 0 info, 1 error, 2 TLC bug, 3 warning, 4 state
    name: str | None  # from codes.py, None if the code is not in the table
    body: tuple[str | TlcMessage, ...]  # in input order: a line exactly as printed, without its newline,
    # or a message that started inside this one (research 1)
    before: str = ""  # text on the start marker's line in front of the marker (": " in the captures)
    after: str = ""  # text on the end marker's line behind the marker ("," in one capture)
    truncated: bool = False  # closed without an end marker of its own: by an outer end marker,
    # or by the end of the input (P4)

    @property
    def lines(self) -> tuple[str, ...]:
        """The message's own lines: the ``str`` items of ``body``, in order."""
        return tuple(item for item in self.body if isinstance(item, str))

    @property
    def nested(self) -> tuple[TlcMessage, ...]:
        """The messages that started inside this one, in order."""
        return tuple(item for item in self.body if isinstance(item, TlcMessage))

    def text_lines(self) -> tuple[str, ...]:
        """The whole text as it reads with the markers taken out (P4).

        A nested message contributes its own text with its ``before`` in front of its first line and its
        ``after`` behind its last; with no lines it contributes ``before + after`` as one line, or nothing when
        both are empty. This message's own ``before`` and ``after`` are not part of it.
        """
        text: list[str] = []
        for item in self.body:
            if isinstance(item, str):
                text.append(item)
            else:
                text.extend(item._framed_text())
        return tuple(text)

    def _framed_text(self) -> list[str]:
        text = list(self.text_lines())
        if not text:
            return [self.before + self.after] if self.before or self.after else []
        text[0] = self.before + text[0]
        text[-1] += self.after
        return text

    def to_dict(self) -> JSONObject:
        return {
            "code": self.code,
            "severity": self.severity,
            "name": self.name,
            "body": [item if isinstance(item, str) else item.to_dict() for item in self.body],
            "before": self.before,
            "after": self.after,
            "truncated": self.truncated,
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> TlcMessage:
        return cls(
            code=data["code"],
            severity=data["severity"],
            name=data["name"],
            body=tuple(item if isinstance(item, str) else cls.from_dict(item) for item in data["body"]),
            before=data["before"],
            after=data["after"],
            truncated=data["truncated"],
        )


@dataclass(frozen=True)
class Location:
    module: str
    line: int
    column: int
    end_line: int | None
    end_column: int | None

    def to_dict(self) -> JSONObject:
        return {
            "module": self.module,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> Location:
        return cls(
            module=data["module"],
            line=data["line"],
            column=data["column"],
            end_line=data["end_line"],
            end_column=data["end_column"],
        )


@dataclass(frozen=True)
class Variable:
    name: str
    value: Value  # P7
    raw: str  # the text TLC printed, lines joined with "\n"; for a variable carried
    # forward (P5, -difftrace), the text of the state it came from
    printed: bool = True  # False when TLC left it out of this state and the parser carried it

    def to_dict(self) -> JSONObject:
        return {"name": self.name, "value": self.value.to_dict(), "raw": self.raw, "printed": self.printed}

    @classmethod
    def from_dict(cls, data: JSONObject) -> Variable:
        return cls(name=data["name"], value=Value.from_dict(data["value"]), raw=data["raw"], printed=data["printed"])


@dataclass(frozen=True)
class TraceState:
    index: int
    action: str | None  # "Next"; None for the initial state
    location: Location | None  # where the action is defined; None for the initial state
    header: str  # the header line as printed
    variables: tuple[Variable, ...]
    lines: tuple[str, ...]  # the whole message body as printed, blank lines included

    def to_dict(self) -> JSONObject:
        return {
            "index": self.index,
            "action": self.action,
            "location": None if self.location is None else self.location.to_dict(),
            "header": self.header,
            "variables": [variable.to_dict() for variable in self.variables],
            "lines": list(self.lines),
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> TraceState:
        return cls(
            index=data["index"],
            action=data["action"],
            location=_optional(data["location"], Location.from_dict),
            header=data["header"],
            variables=tuple(Variable.from_dict(variable) for variable in data["variables"]),
            lines=tuple(data["lines"]),
        )


@dataclass
class Trace:
    states: list[TraceState]
    loop_to: int | None  # state index the behaviour returns to (2122)
    stuttering: bool  # the behaviour ends by stuttering (2218)

    def to_dict(self) -> JSONObject:
        return {
            "states": [state.to_dict() for state in self.states],
            "loop_to": self.loop_to,
            "stuttering": self.stuttering,
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> Trace:
        return cls(
            states=[TraceState.from_dict(state) for state in data["states"]],
            loop_to=data["loop_to"],
            stuttering=data["stuttering"],
        )


@dataclass
class TlcError:
    kind: ErrorKind
    name: str | None  # the invariant or property name, where the message has one
    message: TlcMessage  # the message that opened the error
    related: list[TlcMessage]  # later error-severity messages that belong to it (2103, 2121, 2264),
    # in the order they arrived
    trace: Trace | None

    def to_dict(self) -> JSONObject:
        return {
            "kind": self.kind.value,
            "name": self.name,
            "message": self.message.to_dict(),
            "related": [message.to_dict() for message in self.related],
            "trace": None if self.trace is None else self.trace.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> TlcError:
        return cls(
            kind=ErrorKind(data["kind"]),
            name=data["name"],
            message=TlcMessage.from_dict(data["message"]),
            related=[TlcMessage.from_dict(message) for message in data["related"]],
            trace=_optional(data["trace"], Trace.from_dict),
        )


@dataclass(frozen=True)
class Progress:
    diameter: int
    generated: int
    distinct: int
    queue: int  # -1 kept as -1 (simulation, research 1)
    at: str

    def to_dict(self) -> JSONObject:
        return {
            "diameter": self.diameter,
            "generated": self.generated,
            "distinct": self.distinct,
            "queue": self.queue,
            "at": self.at,
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> Progress:
        return cls(
            diameter=data["diameter"],
            generated=data["generated"],
            distinct=data["distinct"],
            queue=data["queue"],
            at=data["at"],
        )


@dataclass(frozen=True)
class FinalStats:
    total_states: int | None
    distinct_states: int | None
    queue: int | None
    state_depth: int | None
    collision_probability: str | None
    outdegree: str | None  # the 2268 line as printed ("The average outdegree ... is 1 (minimum is 0, ...)")
    # dictionary keys: totalStates, distinctStates, stateDepth, as in the Examples manifest

    def to_dict(self) -> JSONObject:
        return {
            "totalStates": self.total_states,
            "distinctStates": self.distinct_states,
            "queue": self.queue,
            "stateDepth": self.state_depth,
            "collision_probability": self.collision_probability,
            "outdegree": self.outdegree,
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> FinalStats:
        return cls(
            total_states=data["totalStates"],
            distinct_states=data["distinctStates"],
            queue=data["queue"],
            state_depth=data["stateDepth"],
            collision_probability=data["collision_probability"],
            outdegree=data["outdegree"],
        )


@dataclass(frozen=True)
class CoverageItem:
    kind: str  # by code: 2773 "init", 2772 "action", 2774 "property", 2779 "variable"
    # (rolling only), 2221 "expression"
    name: str | None  # the name inside the angle brackets; None for an expression
    location: Location
    sub_location: Location | None  # 2772 only: the second span, printed as "(6 12 6 40)"; it is what tells
    # several rows of one action apart
    count: int | None  # after the colon; for "D:G" forms this is G; None for 2774, which has none
    distinct: int | None  # D of "D:G" (2772, 2773); None otherwise
    depth: int  # 2221 only: the number of "|" before "line"; 0 otherwise

    def to_dict(self) -> JSONObject:
        return {
            "kind": self.kind,
            "name": self.name,
            "location": self.location.to_dict(),
            "sub_location": None if self.sub_location is None else self.sub_location.to_dict(),
            "count": self.count,
            "distinct": self.distinct,
            "depth": self.depth,
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> CoverageItem:
        return cls(
            kind=data["kind"],
            name=data["name"],
            location=Location.from_dict(data["location"]),
            sub_location=_optional(data["sub_location"], Location.from_dict),
            count=data["count"],
            distinct=data["distinct"],
            depth=data["depth"],
        )


@dataclass(frozen=True)
class Diagnostic:
    tool: str  # "sany" or "pcal"
    severity: str  # "error" or "warning"
    message: str
    module: str | None
    file: str | None  # from the "Parsing file" lines; None if not seen
    location: Location | None
    details: tuple[str, ...] = ()  # lines that belong to the diagnostic but are not its message
    # (the residual stack of a parse error, P8)

    def to_dict(self) -> JSONObject:
        return {
            "tool": self.tool,
            "severity": self.severity,
            "message": self.message,
            "module": self.module,
            "file": self.file,
            "location": None if self.location is None else self.location.to_dict(),
            "details": list(self.details),
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> Diagnostic:
        return cls(
            tool=data["tool"],
            severity=data["severity"],
            message=data["message"],
            module=data["module"],
            file=data["file"],
            location=_optional(data["location"], Location.from_dict),
            details=tuple(data["details"]),
        )


@dataclass
class RunResult:
    tool: ToolInfo | None = None  # from message 2262 (P9)
    mode: str | None = None  # "exhaustive search" (2187), "simulate" (2188, also -generate): the Examples
    # manifest's words (research 10); "depth-first" (2271, -dfid), tlaup's word. None for another shape.
    workers: int | None = None  # from 2187, 2188 or 2271 "with N worker(s)"
    phase: Phase = Phase.NOT_STARTED  # where the run is
    status: Status = Status.RUNNING  # "running", "success", "failure"; the runner may set "interrupted"
    verdict: Verdict = Verdict.INCOMPLETE  # D54: what the run found, from TLC's messages; decided at close()
    resumed: bool = False  # D54: TLC recovered from a checkpoint (2197, 2198)
    counts_approximate: bool = False  # D54: resumed, and not with the original -fp and -seed (set by the runner)
    errors: list[TlcError] = field(default_factory=list)
    warnings: list[TlcMessage] = field(default_factory=list)
    sany: list[Diagnostic] = field(default_factory=list)  # P8
    module_files: dict[str, str] = field(default_factory=dict)  # module name -> path, from "Parsing file" lines
    overrides_loaded: list[str] = field(default_factory=list)  # from 2168 (11 R7)
    progress: list[Progress] = field(default_factory=list)  # one per 2200 / 2209 message
    stats: FinalStats | None = None  # 2199, 2194, 2268, 2193
    coverage: list[CoverageItem] = field(default_factory=list)
    output: list[str] = field(default_factory=list)  # the spec's own output and unrecognised text, newest
    # max_output_lines
    output_dropped: int = 0  # how many older lines are no longer in `output`
    unframed_lines: int = 0  # text found outside messages: `Unframed` items plus non-empty top-level
    # `before`/`after` (P4)
    sany_lines_used: int = 0  # `SanyResult.lines_used`, or 0 when there was no SANY window (P4)
    unknown_messages: list[TlcMessage] = field(default_factory=list)  # codes that are not in codes.py
    info: list[TlcMessage] = field(default_factory=list)  # severity 0, in codes.py, with no typed meaning (P4)
    started: str | None = None  # as TLC printed it, "2026-11-14 22:26:52"; local time, no zone
    finished: str | None = None
    duration_ms: int | None = None

    def to_dict(self) -> JSONObject:
        return {
            "tool": None if self.tool is None else self.tool.to_dict(),
            "mode": self.mode,
            "workers": self.workers,
            "phase": self.phase.value,
            "status": self.status.value,
            "verdict": self.verdict.value,
            "resumed": self.resumed,
            "counts_approximate": self.counts_approximate,
            "errors": [error.to_dict() for error in self.errors],
            "warnings": [message.to_dict() for message in self.warnings],
            "sany": [diagnostic.to_dict() for diagnostic in self.sany],
            "module_files": dict(self.module_files),
            "overrides_loaded": list(self.overrides_loaded),
            "progress": [progress.to_dict() for progress in self.progress],
            "stats": None if self.stats is None else self.stats.to_dict(),
            "coverage": [item.to_dict() for item in self.coverage],
            "output": list(self.output),
            "output_dropped": self.output_dropped,
            "unframed_lines": self.unframed_lines,
            "sany_lines_used": self.sany_lines_used,
            "unknown_messages": [message.to_dict() for message in self.unknown_messages],
            "info": [message.to_dict() for message in self.info],
            "started": self.started,
            "finished": self.finished,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: JSONObject) -> RunResult:
        return cls(
            tool=_optional(data["tool"], ToolInfo.from_dict),
            mode=data["mode"],
            workers=data["workers"],
            phase=Phase(data["phase"]),
            status=Status(data["status"]),
            verdict=Verdict(data["verdict"]),
            resumed=data["resumed"],
            counts_approximate=data["counts_approximate"],
            errors=[TlcError.from_dict(error) for error in data["errors"]],
            warnings=[TlcMessage.from_dict(message) for message in data["warnings"]],
            sany=[Diagnostic.from_dict(diagnostic) for diagnostic in data["sany"]],
            module_files=dict(data["module_files"]),
            overrides_loaded=list(data["overrides_loaded"]),
            progress=[Progress.from_dict(progress) for progress in data["progress"]],
            stats=_optional(data["stats"], FinalStats.from_dict),
            coverage=[CoverageItem.from_dict(item) for item in data["coverage"]],
            output=list(data["output"]),
            output_dropped=data["output_dropped"],
            unframed_lines=data["unframed_lines"],
            sany_lines_used=data["sany_lines_used"],
            unknown_messages=[TlcMessage.from_dict(message) for message in data["unknown_messages"]],
            info=[TlcMessage.from_dict(message) for message in data["info"]],
            started=data["started"],
            finished=data["finished"],
            duration_ms=data["duration_ms"],
        )


# --- Events -----------------------------------------------------------------------------------------------------
# What a reporter receives as the run goes (P3, the table under "Events"). `message` is always the top-level
# message, with its nested messages inside it. Events that hold a TlcError or a Trace hold the live object of
# the result, not a copy. Events have no to_dict(): the JSON result is the RunResult.


@dataclass(frozen=True)
class VersionSeen:
    message: TlcMessage
    tool: ToolInfo


@dataclass(frozen=True)
class ModeSeen:
    message: TlcMessage
    mode: str | None
    workers: int | None


@dataclass(frozen=True)
class PhaseChanged:
    message: TlcMessage
    phase: Phase


@dataclass(frozen=True)
class ProgressMade:
    message: TlcMessage
    progress: Progress


@dataclass(frozen=True)
class OutputLine:
    line: str  # no message


@dataclass(frozen=True)
class DiagnosticFound:
    diagnostic: Diagnostic  # no message: SANY's text is unframed


@dataclass(frozen=True)
class ErrorOpened:
    message: TlcMessage
    error: TlcError


@dataclass(frozen=True)
class ErrorExtended:
    message: TlcMessage
    error: TlcError


@dataclass(frozen=True)
class TraceStateAdded:
    message: TlcMessage
    error: TlcError
    state: TraceState


@dataclass(frozen=True)
class TraceClosed:
    message: TlcMessage | None  # the 2122 or 2218 that closed the trace; None when another message or
    # close() did (that message has its own event)
    error: TlcError
    trace: Trace


@dataclass(frozen=True)
class WarningFound:
    message: TlcMessage


@dataclass(frozen=True)
class OverrideLoaded:
    message: TlcMessage
    operator: str
    java_class: str


@dataclass(frozen=True)
class CoverageAdded:
    message: TlcMessage
    item: CoverageItem


@dataclass(frozen=True)
class StatsUpdated:
    message: TlcMessage
    stats: FinalStats  # the whole record so far


@dataclass(frozen=True)
class CheckpointStarted:
    message: TlcMessage
    folder: str


@dataclass(frozen=True)
class CheckpointWritten:
    message: TlcMessage


@dataclass(frozen=True)
class Recovered:
    message: TlcMessage
    examined: int | None
    queued: int | None


@dataclass(frozen=True)
class Information:
    message: TlcMessage


@dataclass(frozen=True)
class UnknownMessage:
    message: TlcMessage


@dataclass(frozen=True)
class Finished:
    message: TlcMessage
    duration_ms: int | None
    finished: str | None


Event = (
    VersionSeen
    | ModeSeen
    | PhaseChanged
    | ProgressMade
    | OutputLine
    | DiagnosticFound
    | ErrorOpened
    | ErrorExtended
    | TraceStateAdded
    | TraceClosed
    | WarningFound
    | OverrideLoaded
    | CoverageAdded
    | StatsUpdated
    | CheckpointStarted
    | CheckpointWritten
    | Recovered
    | Information
    | UnknownMessage
    | Finished
)
