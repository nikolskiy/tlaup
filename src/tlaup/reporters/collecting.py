"""A reporter that keeps what it is given and prints nothing (tests and the Python API)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tlaup.reporters.base import RunInfo
    from tlaup.tlc.run import RunOutcome
    from tlaup_parse import Event, RunResult


class CollectingReporter:
    def __init__(self, calls: list[str] | None = None) -> None:
        self.run: RunInfo | None = None
        self.events: list[Event] = []
        self.results: list[RunResult] = []  # the result handed with each event
        self.stderr_lines: list[str] = []
        self.notices: list[str] = []
        self.outcome: RunOutcome | None = None
        self.calls: list[str] = [] if calls is None else calls
        self.write_error: OSError | None = None
        self._closed = False

    def start(self, run: RunInfo) -> None:
        self.calls.append("start")
        self.run = run

    def handle(self, event: Event, result: RunResult) -> None:
        self.calls.append("handle")
        self.events.append(event)
        self.results.append(result)

    def stderr_line(self, line: str) -> None:
        self.calls.append("stderr_line")
        self.stderr_lines.append(line)

    def notice(self, line: str) -> None:
        self.calls.append("notice")
        self.notices.append(line)

    def finish(self, outcome: RunOutcome) -> None:
        self.calls.append("finish")
        self.outcome = outcome

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.calls.append("close")
