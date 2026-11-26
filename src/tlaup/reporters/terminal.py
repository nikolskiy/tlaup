"""The terminal reporter in plain mode (design 22 O3): the result text on stdout, the rest on stderr (02 X2).

`render_event` is the one renderer of the result text; the layout mode (O4, package 40) writes the same lines to
its stdout spool. Every line built from text tlaup did not write itself (TLC's, SANY's, a value, a path, a class
name) is a `Text` made from a `str` by `_text`, and is printed with markup and highlighting off (10 P11). Nothing
is wrapped or cut by tlaup (O3, "Widths").
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from rich.text import Text

from tlaup.reporters.text import (
    diff_values,
    format_count,
    format_diagnostic,
    format_path,
    progress_line,
    render_value_diff,
    result_line,
    stats_line,
)
from tlaup.tlc.overrides import class_version_hint, load_failure_hint
from tlaup.versioning.spec import format_build
from tlaup_parse import (
    CODES,
    CheckpointStarted,
    CheckpointWritten,
    CoverageAdded,
    DiagnosticFound,
    ErrorExtended,
    ErrorKind,
    ErrorOpened,
    Finished,
    Information,
    ModeSeen,
    OutputLine,
    OverrideLoaded,
    Phase,
    PhaseChanged,
    ProgressMade,
    Recovered,
    StatsUpdated,
    TraceClosed,
    TraceStateAdded,
    UnknownMessage,
    VersionSeen,
    WarningFound,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from rich.console import Console

    from tlaup.reporters.base import RunInfo
    from tlaup.tlc.run import RunOutcome
    from tlaup.ui import Ui
    from tlaup_parse import CoverageItem, Event, RunResult, TlcError, TlcMessage, ToolInfo, TraceState

# tlaup's own literals are the only text with style (P11).
_ERROR_STYLE = "bold red"
_WARNING_STYLE = "yellow"
_HINT_STYLE = "cyan"
_MARK_STYLE = "bold yellow"
_CHANGED_STYLE = "yellow"
_RESULT_STYLE = "bold"

_INDENT = "  "  # a line that belongs to the error or warning above it
_VARIABLE_INDENT = "     "  # in front of a variable's mark, so the names stand under the state's text (O3)
_UNSUPPORTED_CLASS = "java.lang.UnsupportedClassVersionError"
_HINT_CODE = 2173  # an override index class too new for the running Java (11 R7, part 4)


def _text(line: str, *, prefix: str = "", style: str = "") -> Text:
    """A line of outside text; ``prefix`` is tlaup's own literal, the only part that may carry ``style``."""
    text = Text()
    if prefix:
        text.append(prefix, style=style)
    text.append(line)
    return text


def _message_lines(lines: Sequence[str], *, prefix: str, style: str, indent: str = _INDENT) -> list[Text]:
    """``prefix`` and the first line, the further lines indented; a line TLC left empty stays empty (P10)."""
    if not lines:
        return [_text("", prefix=prefix.rstrip(), style=style)]
    word = prefix.split(" ", 1)[0]  # "Error:" or "Warning:"
    if prefix == f"{word} " and lines[0].startswith(word):  # not with "TLC message <code>: " after it
        prefix, style = "", ""  # TLC's text already says it (1102: "Error: unrecognized option ..."); once is enough
    out = [_text(lines[0], prefix=prefix, style=style)]
    out.extend(_text(indent + line if line else "") for line in lines[1:])
    return out


def _prefix(message: TlcMessage, word: str) -> str:
    """``Error: `` or ``Warning: ``, with ``TLC message <code>: `` after it for a code not in the table (O3)."""
    return f"{word}: " if message.name is not None else f"{word}: TLC message {message.code}: "


def _module_path(module: str, result: RunResult, run: RunInfo) -> str:
    """The file of a module as SANY announced it, written with `format_path`; ``<module>.tla`` when none was."""
    file = result.module_files.get(module)
    return format_path(file, run.cwd) if file is not None else f"{module}.tla"


def _state_title(state: TraceState, result: RunResult, run: RunInfo) -> str:
    """``1: Initial predicate``; ``2: Next  (Violation.tla:10:59)`` (O3's mock-up)."""
    if state.action is None:
        return f"{state.index}: {state.header}".rstrip()
    if state.location is None:
        return f"{state.index}: {state.action}"
    where = f"{_module_path(state.location.module, result, run)}:{state.location.line}:{state.location.column}"
    return f"{state.index}: {state.action}  ({where})"


def _previous(error: TlcError, state: TraceState) -> TraceState | None:
    """The state before ``state`` in its trace, read when the state arrives (the result is live)."""
    if error.trace is None:
        return None
    states = error.trace.states
    for position, candidate in enumerate(states):
        if candidate is state:
            return states[position - 1] if position > 0 else None
    return states[-2] if len(states) > 1 else None


def _state_lines(error: TlcError, state: TraceState, result: RunResult, run: RunInfo) -> list[Text]:
    """The state's title, then each variable on its own line, ``*`` on one whose value changed (O3, "Traces").

    A value's further lines are TLC's own wrapping, kept as printed and shifted to stand under its first line.
    """
    out = [_text(_INDENT + _state_title(state, result, run))]
    before = _previous(error, state)
    earlier = {} if before is None else {variable.name: variable.value for variable in before.variables}
    for variable in state.variables:
        changed = before is not None and earlier.get(variable.name) != variable.value
        line = Text(_VARIABLE_INDENT)
        line.append("* " if changed else "  ", style=_MARK_STYLE if changed else "")
        line.append(f"{variable.name} = ")
        if changed and variable.value.text == variable.raw:
            value = render_value_diff(
                variable.raw, diff_values(earlier.get(variable.name), variable.value), _CHANGED_STYLE
            )
        else:
            value = Text(variable.raw)
        first, *rest = value.split("\n", allow_blank=True) or [Text()]
        shift = " " * len(line.plain)
        out.append(line + first)
        out.extend(Text(shift) + continuation for continuation in rest)
    return out


def _closing_lines(error: TlcError) -> list[Text]:
    """A liveness trace's last line (O3); nothing for any other trace."""
    trace = error.trace
    if trace is None:
        return []
    if trace.loop_to is not None:
        return [_text(f"{_INDENT}Back to state {trace.loop_to}")]
    if trace.stuttering:
        return [_text(f"{_INDENT}Stuttering")]
    return []


def _read(path: str) -> str | None:
    """A spec file as UTF-8 with undecodable bytes replaced; None when it cannot be read (S1)."""
    try:
        return Path(path).read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


def render_event(event: Event, result: RunResult, run: RunInfo) -> list[Text]:  # noqa: PLR0911 - one case per event
    """The lines an event adds to the result text (O3), in the order they are printed.

    Pure apart from one read: for a diagnostic with a location, the file its editor-form line names.
    """
    match event:
        case OutputLine(line=line):
            return [_text(line)]
        case DiagnosticFound(diagnostic=diagnostic):
            path = diagnostic.file if diagnostic.file is not None else str(run.spec)
            source = _read(path) if diagnostic.location is not None else None
            lines = format_diagnostic(diagnostic, cwd=run.cwd, spec=run.spec, source_text=source)
            return [_text(line) for line in lines]
        case ErrorOpened(message=message):
            return _message_lines(message.text_lines(), prefix=_prefix(message, "Error"), style=_ERROR_STYLE)
        case ErrorExtended(message=message):
            return [_text(_INDENT + line if line else "") for line in message.text_lines()]
        case TraceStateAdded(error=error, state=state):
            return _state_lines(error, state, result, run)
        case TraceClosed(error=error):
            return _closing_lines(error)
        case WarningFound(message=message):
            return _message_lines(message.text_lines(), prefix=_prefix(message, "Warning"), style=_WARNING_STYLE)
        case UnknownMessage(message=message):
            return _message_lines(message.text_lines(), prefix=f"TLC message {message.code}: ", style="")
        case (
            VersionSeen()
            | ModeSeen()
            | PhaseChanged()
            | ProgressMade()
            | OverrideLoaded()
            | CoverageAdded()
            | StatsUpdated()
            | CheckpointStarted()
            | CheckpointWritten()
            | Recovered()
            | Information()
            | Finished()
        ):
            return []
        case _:
            assert_never(event)


def _differs(tool: ToolInfo, run: RunInfo) -> bool:
    """TLC's version line says something the store's build does not (O3); a build with no commit is not compared
    by revision, so its version line is not printed on every run."""
    build = run.build
    if tool.revision is not None and build.commit is not None and not build.commit.startswith(tool.revision):
        return True
    return build.calver is not None and tool.version != build.calver


def _has_config_message(message: TlcMessage) -> bool:
    """A message nested at any depth whose code has kind ``config`` in the code table (5006 in the captures)."""
    for nested in message.nested:
        info = CODES.get(nested.code)
        if (info is not None and info.kind is ErrorKind.CONFIG) or _has_config_message(nested):
            return True
    return False


def _hint(error: TlcError, message: TlcMessage, result: RunResult, run: RunInfo) -> str | None:
    """The override hint of 11 R7, part 4, as O3 states when it applies; read when the error opens."""
    text = "\n".join(message.text_lines())
    if message.code == _HINT_CODE:
        return class_version_hint(text) or load_failure_hint(run.override_classes)
    if (
        error.kind is not ErrorKind.EXCEPTION
        or result.phase is not Phase.STARTING
        or not run.override_classes
        or _has_config_message(message)
    ):
        return None
    specific = class_version_hint(text) if _UNSUPPORTED_CLASS in text else None
    return specific or load_failure_hint(run.override_classes)


def render_status(event: Event, result: RunResult, run: RunInfo) -> list[Text]:
    """The reporter's own stderr lines an event causes, apart from progress: TLC's version line when it differs
    from the store's build, and the override hint when an error opens (O3)."""
    if isinstance(event, VersionSeen):
        return [_text(event.tool.raw)] if _differs(event.tool, run) else []
    if isinstance(event, ErrorOpened):
        hint = _hint(event.error, event.message, result, run)
        return [] if hint is None else [_text(hint, prefix="hint: ", style=_HINT_STYLE)]
    return []


def header_lines(run: RunInfo) -> list[Text]:
    """``TLC rolling@bc1b506 (2026.11.15.002146), Java 25.0.5, workers auto``, then the spec and the cfg; a part
    that is not known is left out (O3)."""
    first = f"TLC {format_build(run.build)}"
    if run.build.calver is not None:
        first += f" ({run.build.calver})"
    if run.java.version is not None:
        first += f", Java {run.java.version}"
    if run.workers is not None:
        first += f", workers {run.workers}"
    second = format_path(run.spec, run.cwd)
    if run.cfg is not None:
        second += f"  cfg: {format_path(run.cfg, run.cwd)}"
    return [_text(first), _text(second)]


# --- Coverage (R9; O2: kept, rewritten against CoverageItem) ------------------------------------------------------


def _action_rows(coverage: Iterable[CoverageItem]) -> list[CoverageItem]:
    return [item for item in coverage if item.kind in {"init", "action"}]


def render_coverage_table(coverage: Sequence[CoverageItem], result: RunResult, run: RunInfo) -> list[Text]:
    """The actions with the states each found, in TLC's order, in plain characters (O3: they go to files)."""
    rows = [
        (
            item.name or "",
            _where(item, result, run),
            "" if item.distinct is None else format_count(item.distinct),
            "" if item.count is None else format_count(item.count),
        )
        for item in _action_rows(coverage)
    ]
    if not rows:
        return []
    heading = ("Action", "Location", "Distinct", "Generated")
    widths = [max(len(row[column]) for row in [heading, *rows]) for column in range(4)]
    out = [_text("Coverage of actions:")]
    for name, where, distinct, generated in [heading, *rows]:
        line = f"{_INDENT}{name:<{widths[0]}}  {where:<{widths[1]}}  {distinct:>{widths[2]}}  {generated:>{widths[3]}}"
        out.append(_text(line))
    return out


def _where(item: CoverageItem, result: RunResult, run: RunInfo) -> str:
    """Where an action row is: its second span when TLC gave one, which tells the rows of one action apart."""
    location = item.sub_location or item.location
    return f"{_module_path(location.module, result, run)}:{location.line}:{location.column}"


def render_inline_coverage(coverage: Sequence[CoverageItem], run: RunInfo) -> list[Text]:
    """The spec's lines, each with the distinct states of the actions on it; ``never reached`` where an action
    generated no state. Only rows of the spec's own module; nothing when the spec cannot be read."""
    source = _read(str(run.spec))
    if source is None:
        return []
    module = run.spec.stem
    per_line: dict[int, list[CoverageItem]] = {}
    for item in _action_rows(coverage):
        location = item.sub_location or item.location
        if location.module != module:
            continue
        for number in range(location.line, (location.end_line or location.line) + 1):
            per_line.setdefault(number, []).append(item)
    if not per_line:
        return []
    lines = source.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    counts = {number: format_count(max(item.distinct or 0 for item in items)) for number, items in per_line.items()}
    width = max(len(count) for count in counts.values())
    out = [_text(f"Distinct states by line of {format_path(run.spec, run.cwd)}:")]
    for number, line in enumerate(lines, start=1):
        reached = any((item.count or 0) > 0 for item in per_line.get(number, []))
        mark = "  <-- never reached" if number in per_line and not reached else ""
        out.append(_text(f"{_INDENT}{counts.get(number, ''):>{width}} {number:>4} | {line}{mark}"))
    return out


def render_summary(outcome: RunOutcome, run: RunInfo, elapsed: float) -> list[Text]:
    """What closes the result text: the statistics line, the coverage, then the result line (O3)."""
    result = outcome.result
    if result is None:
        return []
    out: list[Text] = []
    if result.stats is not None:
        line = stats_line(result.stats, approximate=result.counts_approximate)
        if line:
            out.append(_text(line))
    if result.coverage:
        out.extend(render_coverage_table(result.coverage, result, run))
        out.extend(render_inline_coverage(result.coverage, run))
    words = result_line(outcome, result, elapsed).removeprefix("Result: ")
    out.append(_text(words, prefix="Result: ", style=_RESULT_STYLE))
    return out


class TerminalReporter:
    """A `Reporter` (22 O1) that writes as things arrive: the result text to ``ui.out``, the rest to ``ui.err``.

    Plain mode only; the layout mode is package 40's. In plain mode everything is written when it arrives, so
    `close` has nothing to release.
    """

    def __init__(self, ui: Ui, *, clock: Callable[[], float]) -> None:
        self._ui = ui
        self._clock = clock
        self._run: RunInfo | None = None
        self._started_at: float | None = None
        self._closed = False
        self.write_error: OSError | None = None

    def _require_run(self) -> RunInfo:
        if self._run is None:
            msg = "the reporter was given an event before start"
            raise RuntimeError(msg)
        return self._run

    @staticmethod
    def _write(console: Console, lines: Iterable[Text]) -> None:
        for line in lines:
            console.print(line, soft_wrap=True, markup=False, highlight=False, emoji=False)

    def start(self, run: RunInfo) -> None:
        self._run = run
        self._started_at = self._clock()
        self._write(self._ui.err, header_lines(run))

    def handle(self, event: Event, result: RunResult) -> None:
        run = self._require_run()
        if isinstance(event, ProgressMade):
            self._write(self._ui.err, [_text(progress_line(event.progress))])
        self._write(self._ui.err, render_status(event, result, run))
        self._write(self._ui.out, render_event(event, result, run))

    def stderr_line(self, line: str) -> None:
        self._write(self._ui.err, [_text(line)])

    def notice(self, line: str) -> None:
        self._write(self._ui.err, [_text(line)])

    def finish(self, outcome: RunOutcome) -> None:
        run = self._require_run()
        now = self._clock()
        elapsed = 0.0 if self._started_at is None else now - self._started_at
        self._write(self._ui.out, render_summary(outcome, run, elapsed))
        self.close()

    def close(self) -> None:
        """Plain mode: nothing to release; idempotent, safe before `start`, never raises (O1)."""
        self._closed = True
