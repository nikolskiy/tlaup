"""The reporter protocol and the facts known before a tool starts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from tlaup.java.locate import JavaRuntime
    from tlaup.versioning.store import Build
    from tlaup_parse import Event, RunResult


@dataclass(frozen=True)
class RunInfo:
    """What is known before the tool starts."""

    tool: str  # "tlc"
    spec: Path
    cfg: Path | None
    build: Build
    java: JavaRuntime
    workers: str | None
    project_root: Path | None
    override_classes: tuple[str, ...]
    command: tuple[str, ...]
    cwd: Path  # the folder tlaup was started in


class Reporter(Protocol):
    """What `run_tlc` feeds: typed events and the result so far.

    Rules for every reporter:

    - `run_tlc` is the only caller. `start` once, immediately before the child starts; `handle`,
      `stderr_line` and `notice` any number of times, from the main thread; `finish` once when the run
      has an outcome; `close` from a `finally`. `finish` may call `close` itself.
    - `close` is idempotent, safe before `start`, safe after a `start` that raised half way (it releases
      exactly what `start` recorded), and never raises. A write that fails in it is kept in
      `write_error` (the first one only); `run_tlc` raises it after its frame.
    - `handle`, `stderr_line` and `finish` let a write error pass. Only `close` holds one back.
    - A reporter never parses: what it needs that the result does not carry is added to `tlaup_parse`.
      It never decides the exit code and never raises for a failed run. It holds its own state.
    - TLC's stderr goes through `stderr_line`, and a line of tlaup's own during the run through
      `notice`, never straight to a console.
    - A reporter prints only through `ui.out` and `ui.err` of the `Ui` it was given and never builds a
      console on a real stream.
    - A reporter says nothing about the run folder: the "Checkpoint kept" note is the command's.
    """

    write_error: OSError | None  # set by close when a write failed in it

    def start(self, run: RunInfo) -> None: ...
    def handle(self, event: Event, result: RunResult) -> None: ...
    def stderr_line(self, line: str) -> None: ...  # a line the tool wrote to stderr
    def notice(self, line: str) -> None: ...  # a line of tlaup's own during the run
    # `object` until run_tlc's package creates RunOutcome and narrows it (under TYPE_CHECKING).
    def finish(self, outcome: object) -> None: ...
    def close(self) -> None: ...  # always called last; never raises
