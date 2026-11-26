"""The run functions: `run_tlc` (launcher, parser, reporter) and `run_tlc_raw` (passthrough) (design 11, the frame).

Both hold the signal handlers and the run folder for the whole run, in one ``with``: the handlers first, then the
folder (20 G3, 11 R6). Inside it, a ``try`` whose ``except BaseException`` settles the folder as tlaup failing and
puts the "Checkpoint kept" note on the exception, and whose ``finally`` closes the reporter. A write error the
reporter's ``close`` held back is raised after the block, when nothing else is passing (22 O1). Nothing here catches
an exception to change it (11 R1), and the run functions print nothing but the kept-folders reminder, through
``notice``; the waiting line of a held signal goes to ``reporter.notice`` (11 R2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tlaup.java.launcher import run_passthrough, run_streaming, signals_held
from tlaup.reporters.base import RunInfo
from tlaup.tlc.rundirs import kept_note, reminder, run_folder
from tlaup_parse import CheckpointStarted, CheckpointWritten, Status, TlcParser, Verdict

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path

    from tlaup.java.launcher import JavaInvocation, ProcessOutcome, SignalName, Signals
    from tlaup.paths import AppPaths
    from tlaup.reporters.base import Reporter
    from tlaup.tlc.invocation import TlcInvocation
    from tlaup.tlc.rundirs import Kept, RunFolder, Settled
    from tlaup_parse import Event, RunResult


@dataclass(frozen=True)
class RunOutcome:
    result: RunResult | None  # 10 P3; None for a raw run, where nothing is parsed
    exit_code: int  # what tlaup exits with (02 X1)
    tool_exit_code: int | None
    stopped_by: str | None  # "int", "term", "hup"
    stderr_tail: tuple[str, ...]
    warnings: tuple[str, ...]  # the preflight's warnings (R7, J2, J3), for the JSON reporter of milestone 4
    run_folder_kept: Path | None  # R6; the run folder that was kept (the recovered one after -recover)
    resume_command: str | None  # R6; set when run_folder_kept is
    dropped_checkpoint: str | None  # R6; "not-asked", "incomplete" or "depth-first" when a checkpoint was not kept
    stopped_for_closed_pipe: bool  # R1; the reader of stdout went away and TLC was stopped (D58)
    kept: Kept | None  # R6; the whole kept value, for the note that 39's print_run_notes prints (kept_note)


_WAITING = "waiting for TLC to finish writing its checkpoint"


def waiting_line(signal_name: Literal["int", "term", "hup"]) -> str:
    """The line shown when a first signal is held while TLC writes a checkpoint (20 G3, 11 R2)."""
    if signal_name == "int":
        return f"{_WAITING}; press Ctrl-C again to stop now"
    prefix = "SIGTERM" if signal_name == "term" else "SIGHUP"
    return f"{prefix} received: {_WAITING}; send it again to stop now"


def _outcome(process: ProcessOutcome, settled: Settled, inv: TlcInvocation, result: RunResult | None) -> RunOutcome:
    kept = settled.kept
    return RunOutcome(
        result=result,
        exit_code=process.exit_code,
        tool_exit_code=process.tool_exit_code,
        stopped_by=process.stopped_by,
        stderr_tail=process.stderr_tail if result is not None else (),
        warnings=inv.warnings,
        run_folder_kept=None if kept is None else kept.path,
        resume_command=None if kept is None else kept.resume_command,
        dropped_checkpoint=settled.dropped,
        stopped_for_closed_pipe=process.stopped_for_closed_pipe,
        kept=kept,
    )


def _add_note(error: BaseException, settled: Settled) -> None:
    if settled.kept is not None:
        for line in kept_note(settled.kept):
            error.add_note(line)


def _remind(folder: RunFolder, notice: Callable[[str], None]) -> None:
    if folder.kept_summary.count:
        notice(reminder(folder.kept_summary))  # R6: before reporter.start, above the run's own output


def _run_info(inv: TlcInvocation, java_inv: JavaInvocation) -> RunInfo:
    return RunInfo(
        tool="tlc",
        spec=inv.spec,
        cfg=inv.cfg,
        build=inv.build,
        java=inv.java,
        workers=inv.workers,
        project_root=inv.project_root,
        override_classes=inv.override_classes,
        command=tuple(java_inv.argv()),
        cwd=inv.cwd,
    )


def _finish_result(result: RunResult, process: ProcessOutcome, folder: RunFolder) -> None:
    """What the runner sets on the parser's result (10 P3, D54)."""
    if process.stopped_by is not None:
        result.status = Status.INTERRUPTED
    stopped = process.stopped_by is not None or process.stopped_for_closed_pipe
    if stopped and result.verdict not in (Verdict.ERRORS, Verdict.NOT_CHECKED):
        result.verdict = Verdict.INCOMPLETE
    result.counts_approximate = result.resumed and not folder.resumes_exactly


class _Feed:
    """The parser and the reporter on the main thread: the launcher's mark first, then the reporter (D52)."""

    def __init__(self, parser: TlcParser, reporter: Reporter, signals: Signals) -> None:
        self.parser = parser
        self.reporter = reporter
        self.signals = signals

    def deliver(self, events: list[Event]) -> None:
        for event in events:
            if isinstance(event, CheckpointStarted):
                self.signals.checkpoint_started()
            elif isinstance(event, CheckpointWritten):
                self.signals.checkpoint_written()
            self.reporter.handle(event, self.parser.result)

    def stdout_line(self, line: str) -> None:
        self.deliver(self.parser.feed(line))

    def held(self, name: SignalName) -> None:
        self.reporter.notice(waiting_line(name))


def run_tlc(  # noqa: PLR0913 - the design's signature (11)
    inv: TlcInvocation,
    java_inv: JavaInvocation,
    reporter: Reporter,
    *,
    paths: AppPaths,
    now: Callable[[], datetime],
    notice: Callable[[str], None],
) -> RunOutcome:
    """Runs TLC with its output parsed and reported; the one process loop and the one `TlcParser` (20 G1)."""
    parser = TlcParser()
    with signals_held() as signals, run_folder(inv, paths, now) as folder:
        try:
            _remind(folder, notice)
            reporter.start(_run_info(inv, java_inv))  # the last thing before the child
            feed = _Feed(parser, reporter, signals)
            process = run_streaming(
                java_inv,
                on_stdout=feed.stdout_line,
                on_stderr=reporter.stderr_line,
                signals=signals,
                pass_fds=folder.lock_fds,
                on_held=feed.held,
            )
            feed.deliver(parser.close())
            result = parser.result
            _finish_result(result, process, folder)
            settled = folder.settle(process, workers_reported=result.workers)  # before anything is printed
            outcome = _outcome(process, settled, inv, result)
            reporter.finish(outcome)
        except BaseException as error:
            settled = folder.settle(None)  # the first decision stands if there is one
            _add_note(error, settled)
            raise
        finally:
            reporter.close()  # never raises (22 O1)
    # leaving the block deleted or kept the folder, released the lock and restored the handlers
    if reporter.write_error is not None:
        _add_note(reporter.write_error, settled)
        raise reporter.write_error
    return outcome


def run_tlc_raw(
    inv: TlcInvocation,
    java_inv: JavaInvocation,
    *,
    paths: AppPaths,
    now: Callable[[], datetime],
    notice: Callable[[str], None],
) -> RunOutcome:
    """Runs TLC on tlaup's own streams; nothing is read, and no signal waits for a checkpoint (D52)."""
    with signals_held() as signals, run_folder(inv, paths, now) as folder:
        try:
            _remind(folder, notice)
            process = run_passthrough(
                java_inv,
                signals=signals,
                forward_interrupt=True,
                pass_fds=folder.lock_fds,
                stop_when_reader_gone=True,
            )
            settled = folder.settle(process, workers_reported=None)
            outcome = _outcome(process, settled, inv, None)
        except BaseException as error:
            settled = folder.settle(None)
            _add_note(error, settled)
            raise
    return outcome
