"""Running SANY and routing what it prints (design 21 S1, decisions D9, D29, D30 and D55).

Domain code returns values and does not print (00): the command gives the run a sink to print through, as the runner
gives the reporter its events. The run reads SANY's two streams through one pipe, feeds each line to one
`SanyParser` and routes it by the class the parser gave it; nothing here matches SANY's text.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from tlaup.errors import InternalError
from tlaup.java.launcher import run_streaming, signals_held
from tlaup_parse import SanyLineClass, SanyParser

if TYPE_CHECKING:
    from collections.abc import Callable

    from tlaup.java.launcher import JavaInvocation, ProcessOutcome
    from tlaup.tools.invocation import ToolInvocation
    from tlaup_parse import Diagnostic, SanyResult, SanyStep

ERROR_CODE = 150  # a spec with an error, the number tlc exits with for the same spec (D29, D55)

_CHATTER = frozenset({SanyLineClass.BANNER, SanyLineClass.PROGRESS})
_NOTHING = frozenset(
    {
        SanyLineClass.HEADER,
        SanyLineClass.STRUCTURE,
        SanyLineClass.POSITION,
        SanyLineClass.MESSAGE,
        SanyLineClass.BLANK,
    }
)


class SanySink(Protocol):
    def chatter(self, line: str) -> None:
        """BANNER and PROGRESS: stderr, as SANY wrote it (D30)."""

    def other(self, line: str) -> None:
        """OTHER: stdout, as SANY wrote it (D9)."""

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        """One completed diagnostic, its file already filled in."""


@dataclass(frozen=True)
class SanyOutcome:
    result: SanyResult
    process: ProcessOutcome
    exit_code: int


def sany_exit_code(process: ProcessOutcome, result: SanyResult) -> int:
    """The launcher's code when a signal or a closed pipe stopped the run; else 150 for any error; else SANY's own.

    SANY says 0 for semantic errors and 255 for parse errors, so its code cannot tell a spec with errors from one
    without (D29). A warning alone changes nothing. No ``-error-codes`` is added, on either build.
    """
    if process.stopped_by is not None or process.stopped_for_closed_pipe:
        return process.exit_code
    if any(d.severity == "error" for d in result.diagnostics):
        return ERROR_CODE
    return process.exit_code


def _never(line: str) -> None:
    message = f"SANY's stderr was read apart from its stdout: {line!r}"
    raise InternalError(message)


def run_sany(
    inv: ToolInvocation,
    java_inv: JavaInvocation,
    sink: SanySink,
    finish: Callable[[SanyOutcome], None],
) -> SanyOutcome:
    """Run SANY, give the sink each line and diagnostic as it comes, then ``finish`` the outcome.

    The signals are held until ``finish`` has printed what it prints. After a signal, or a closed pipe, the parser is
    not closed and ``finish`` is not called: the diagnostics it had completed by then are printed, no summary is.
    """
    parser = SanyParser()

    def give(step: SanyStep) -> None:
        for found in step.diagnostics:
            sink.diagnostic(found if found.file is not None or inv.spec is None else replace(found, file=str(inv.spec)))

    def on_stdout(text: str) -> None:
        line = text.rstrip("\r\n")  # the line as received, not the stripped one
        step = parser.feed(line)
        line_class = step.line_class
        if line_class in _CHATTER:
            sink.chatter(line)
        elif line_class not in _NOTHING:  # OTHER, and any class added later (D9)
            sink.other(line)
        give(step)

    with signals_held() as signals:
        process = run_streaming(java_inv, on_stdout=on_stdout, on_stderr=_never, signals=signals, merge_stderr=True)
        stopped = process.stopped_by is not None or process.stopped_for_closed_pipe
        if not stopped:
            give(parser.close())
        result = parser.result
        outcome = SanyOutcome(result, process, sany_exit_code(process, result))
        if not stopped:
            finish(outcome)
    return outcome
