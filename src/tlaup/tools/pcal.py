"""Running the PlusCal translator and routing what it prints (design 21 S2, decisions D9, D29, D30 and D67).

Domain code returns values and does not print (00): the command gives the run a sink to print through. The run reads
the translator's two streams through one pipe, feeds each line to one `PcalParser` and hands on what the parser
recognised in the translator's order; nothing here matches the translator's text.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol

from tlaup.errors import InternalError
from tlaup.java.launcher import run_streaming, signals_held
from tlaup.reporters.text import format_path
from tlaup_parse import PcalParser

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

    from tlaup.java.launcher import JavaInvocation, ProcessOutcome
    from tlaup.tools.invocation import ToolInvocation
    from tlaup_parse import Diagnostic, PcalResult


class PcalSink(Protocol):
    def other(self, line: str) -> None:
        """A line the parser did not recognise: stdout, as the translator wrote it (D9)."""

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        """One completed diagnostic, its file set to the spec and the doubled full stop trimmed."""

    def label(self, name: str, line: int, column: int) -> None:
        """A label the translator added (D67)."""


@dataclass(frozen=True)
class PcalOutcome:
    result: PcalResult
    process: ProcessOutcome
    exit_code: int  # process.exit_code: the translator's own (D29), or a signal's


def trim_full_stop(message: str) -> str:
    """The translator ends its errors in two full stops; a message that ends in ``..`` loses one."""
    return message[:-1] if message.endswith("..") else message


def written_notes(files_written: Sequence[str], spec: Path, cwd: Path) -> list[str]:
    """One note per file the translator wrote, in order; the spec's own file was rewritten and its old version kept."""
    notes = []
    for name in files_written:
        path = format_path(spec.parent / name, cwd)
        if name == spec.name:
            notes.append(f"{path} translated (previous version saved as {spec.with_suffix('.old').name})")
        else:
            notes.append(f"{path} written")
    return notes


def label_line(name: str, line: int, column: int, spec: Path, cwd: Path) -> str:
    """``PcalNoLabel.tla:7:3: label Lbl_1 added``: the position form lets an editor jump to the label (D67)."""
    return f"{format_path(spec, cwd)}:{line}:{column}: label {name} added"


def _never(line: str) -> None:
    message = f"the translator's stderr was read apart from its stdout: {line!r}"
    raise InternalError(message)


def run_pcal(
    inv: ToolInvocation,
    java_inv: JavaInvocation,
    sink: PcalSink,
    finish: Callable[[PcalOutcome], None],
) -> PcalOutcome:
    """Run the translator, give the sink each diagnostic, label and unrecognised line as it comes, then ``finish``.

    The signals are held until ``finish`` has printed what it prints. After a signal, or a closed pipe, the parser is
    not closed and ``finish`` is not called: the diagnostics completed by then are printed, no notes are.
    """
    parser = PcalParser()
    result = parser.result
    seen = {"labels": 0, "other": 0}

    def give(diagnostics: list[Diagnostic]) -> None:
        for found in diagnostics:
            message = trim_full_stop(found.message)
            file = str(inv.spec) if inv.spec is not None else found.file
            sink.diagnostic(replace(found, message=message, file=file))
        for name, line, column in result.labels_added[seen["labels"] :]:
            sink.label(name, line, column)
        for text in result.other[seen["other"] :]:
            sink.other(text)
        seen["labels"] = len(result.labels_added)
        seen["other"] = len(result.other)

    def on_stdout(text: str) -> None:
        give(parser.feed(text.rstrip("\r\n")))

    with signals_held() as signals:
        process = run_streaming(java_inv, on_stdout=on_stdout, on_stderr=_never, signals=signals, merge_stderr=True)
        stopped = process.stopped_by is not None or process.stopped_for_closed_pipe
        if not stopped:
            give(parser.close())
        outcome = PcalOutcome(result, process, process.exit_code)
        if not stopped:
            finish(outcome)
    return outcome
