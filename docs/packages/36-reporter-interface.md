# 36. The reporter interface

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup.reporters` exists with the `Reporter` protocol, `RunInfo` and a `CollectingReporter` that keeps what it is given and prints nothing, so that [37](37-run-tlc.md) can write `run_tlc` against the protocol and test it, and [38](38-terminal-reporter.md) can write the terminal reporter behind it. No command uses any of it yet.

## Covers

- Roadmap items, [milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout):
  - "A reporter interface fed by the parsed result and run events. Move the streaming state and the final summary out of the command into it; the command shrinks to option parsing, error mapping and the exit code. Terminal and non-terminal output differ only in where they write and in the footer." (line 322). In part: the interface. The order of calls and O1's unit test of it are [37](37-run-tlc.md)'s; the terminal reporter [38](38-terminal-reporter.md)'s; the command that shrinks, and `make_reporter`, [39](39-tlc-command.md)'s.
- Design sections:
  - [22 O1](../design/22-reporters.md#o1-reporter-interface): `RunInfo`, the `Reporter` protocol with its rules for `start`, `handle`, `stderr_line`, `notice`, `finish`, `close` and `write_error` (`notice` added by the stage 4 review, question Q12), the `CollectingReporter` of the reporters table, which also records the notices, and the signature of `make_reporter` (written here, created in 39). Not this package: the order of the calls as `run_tlc` makes them and O1's Tests paragraph (37); the command sketch (39); the `TerminalReporter`'s own `close` (O6, packages 38 and 40).

## Depends on

- [03](03-test-foundation.md): the isolation fixture and the pytest settings.
- [09](09-parse-package-and-model.md): `Event` (the union of twenty classes) and `RunResult`, imported from `tlaup_parse`.
- [20](20-java-location.md): `JavaRuntime`, the type of `RunInfo.java`.
- [23](23-tool-store.md): `Build`, the type of `RunInfo.build`.

Change from the draft (09, 33): 33 is dropped and 20 and 23 are named. `RunInfo` holds a `Build` and a `JavaRuntime`, not the invocation; 37 builds the `RunInfo` from the invocation. 33 is earlier than this package in the order anyway, so the change moves nothing.

## Files

Creates:

- `src/tlaup/reporters/__init__.py`: a module docstring and nothing else. It is the home of `make_reporter`, which [39](39-tlc-command.md) adds (see Interfaces). It must stay free of module-level imports of `rich` and of the reporter modules, so that `import tlaup.cli` does not load them ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)).
- `src/tlaup/reporters/base.py`: `RunInfo`, `Reporter`.
- `src/tlaup/reporters/collecting.py`: `CollectingReporter`.
- `tests/unit/reporters/__init__.py` if the other test folders have one, and `tests/unit/reporters/test_collecting.py`.

Changes and deletes: none. The old display code under `src/tlaup/tlc/` is untouched; [39](39-tlc-command.md) and [40](40-live-display.md) delete it.

Shared with packages of the same period: none. `tests/unit/reporters/` is shared later with 38 and 40, which add files beside this one.

## Interfaces

Provides, from [22 O1](../design/22-reporters.md#o1-reporter-interface). Marks say what stage 4 wrote or changed.

```python
# tlaup/reporters/base.py
from __future__ import annotations


@dataclass(frozen=True)
class RunInfo:  # known before the tool starts
    tool: str  # "tlc"
    spec: Path
    cfg: Path | None
    build: Build  # 23
    java: JavaRuntime  # 20
    workers: str | None
    project_root: Path | None
    override_classes: tuple[str, ...]
    command: tuple[str, ...]
    cwd: Path  # written by stage 4: the folder tlaup was started in (TlcInvocation.cwd)


class Reporter(Protocol):
    write_error: OSError | None  # set by close when a write failed in it

    def start(self, run: RunInfo) -> None: ...
    def handle(self, event: Event, result: RunResult) -> None: ...  # events of 10 P3
    def stderr_line(self, line: str) -> None: ...  # a line the tool wrote to stderr
    def notice(self, line: str) -> None: ...  # a line of tlaup's own during the run (Q12)
    def finish(self, outcome: RunOutcome) -> None: ...  # 11; the run ended and has an outcome
    def close(self) -> None: ...  # always called last; never raises
```

**`RunInfo.cwd`** (stage 4). O3 asks for the spec and the cfg "relative to the working folder" in the header, and [21 S1](../design/21-other-tools.md#s1-sany)'s editor form, which O3 uses for diagnostics, writes a path "relative to the folder tlaup was started from when it is beneath it". The reporter could read `Path.cwd()`, but then its expected files would depend on the temporary folder a test runs in, and a reporter test with a fixed `RunInfo` could not fix it. So the folder travels in `RunInfo`, and 37 fills it from `inv.cwd`. That is one more field for 37 to fill, and 37's file fills it.

**`RunOutcome` without a circular import.** `RunOutcome` is [37](37-run-tlc.md)'s, in `tlaup/tlc/run.py` (renamed `tlc/runner.py` by [39](39-tlc-command.md)), and `run.py` imports `Reporter` and `RunInfo` from here at run time. So `base.py` names `RunOutcome` only for the type checker: `from __future__ import annotations` at the top, and the import inside `if TYPE_CHECKING:`. At run time `base.py` imports nothing from `tlaup.tlc`, and there is no cycle.

When this package merges, `tlaup/tlc/run.py` does not exist yet, and mypy strict fails on an import it cannot resolve. So this package writes the annotation of `finish` as `outcome: object`, with a comment that 37 narrows it; and 37, in the pull request that creates `RunOutcome`, changes that annotation and `CollectingReporter.outcome` to `RunOutcome` under `TYPE_CHECKING` (two lines here, one in `collecting.py`). It cannot stay `object`: a `TerminalReporter.finish(self, outcome: RunOutcome)` does not satisfy a protocol whose parameter is `object` (parameters are contravariant), so 38 would fail mypy. 37's file lists these three lines among its changes.

**The rules of O1, stated once for every reporter** (put them in the protocol's docstring):

- The order of calls is fixed by `run_tlc`, the only caller in tlaup: `start` once, immediately before the child starts; `handle`, `stderr_line` and `notice` any number of times, from the main thread; `finish` once when the run has an outcome; `close` from a `finally`. `finish` may call `close` itself, so `close` must be idempotent.
- `close` is idempotent, safe before `start`, safe after a `start` that raised half way (it releases exactly what `start` recorded), and never raises. A write that fails inside it is kept in `write_error` (the first one only); `run_tlc` raises it after its frame.
- `handle`, `stderr_line` and `finish` let a write error pass. Only `close` holds one back.
- A reporter never parses: what it needs that the result does not carry is added to `tlaup_parse`. It never decides the exit code and never raises for a failed run. It holds its own state.
- TLC's stderr goes through `stderr_line`, never straight to a console.
- A line of tlaup's own during the run goes through `notice`, for the same reason: nothing between `start` and `close` prints through `ui` ([14 F6](../design/14-config-and-cli.md#f6-messages)). The one such line in the first wave is the waiting line while a first signal is held during a checkpoint ([11 R2](../design/11-runner.md#r2-signals)); `run_tlc`'s `on_held` hook hands it to `notice` ([37](37-run-tlc.md)). A plain reporter writes it on stderr at once ([38](38-terminal-reporter.md)); the layout shows it in its Status panel and copies it to stderr when it closes ([40](40-live-display.md)). A raw run has no reporter and holds no signal for a checkpoint.
- A reporter prints only through `ui.out` and `ui.err` of the `Ui` it was given ([14 F6](../design/14-config-and-cli.md#f6-messages)) and never builds a console on a real stream. (The spools of [40](40-live-display.md) are consoles on temporary files, which is allowed.)
- A reporter says nothing about the run folder: the "Checkpoint kept" note is the command's ([39](39-tlc-command.md)).

```python
# tlaup/reporters/collecting.py
class CollectingReporter:  # tests and the Python API; prints nothing
    def __init__(self, calls: list[str] | None = None): ...  # written by stage 4: a list to share with a test

    run: RunInfo | None
    events: list[Event]
    results: list[RunResult]  # the result object handed with each event (the same object each time)
    stderr_lines: list[str]
    notices: list[str]  # the lines given to notice, in order (22 O1)
    outcome: RunOutcome | None  # `object | None` until 37 narrows it
    calls: list[str]  # "start", "handle", "stderr_line", "notice", "finish", "close", in order
    write_error: OSError | None  # always None here; a test subclass may set it in close
```

What O1 leaves to the class, as built (stage 4's choices, all internal to tests):

- `calls` records the name of each method as it is called, `notice` included. A test that also wants the runner's `notice` argument (the kept-folders reminder, printed through `ui.note` before `start`) in the same order passes its own list as `calls` and appends `"note: <line>"` to it from its `notice` function, so the two kinds of entry stay apart: `"notice"` is the reporter's method, `"note: ..."` the runner's argument; [37](37-run-tlc.md) does that (finding G9).
- `finish` records the outcome and does not call `close`: it holds nothing. `close` appends `"close"` the first time it is called and does nothing on a later call, so O1's sequence "`start`, events, `finish`, `close`" is what a test reads. A test that needs to count every call can count them in a subclass.
- The methods are plain and do nothing else, so a test may subclass the reporter to act from a callback: send a signal from `start` or `handle` ([37](37-run-tlc.md)'s exact-moment tests), raise from `handle`, or set `write_error` in `close`.

`make_reporter` (design 03 lists it among the joints with no written signature; written by stage 4, the same as [39](39-tlc-command.md) gives it):

```python
# tlaup/reporters/__init__.py, created by package 39
def make_reporter(ctx: AppContext, options: ReporterOptions) -> Reporter

@dataclass(frozen=True)
class ReporterOptions:               # what the command line says about output; created by 39
    ...                              # 40 adds plain and refresh_interval
```

The one function in which a command chooses a reporter ([22 O1](../design/22-reporters.md#o1-reporter-interface)); milestone 4's `--json` attaches there. This package does not create it, because what it returns, the `TerminalReporter`, is [38](38-terminal-reporter.md)'s, and a function that can return nothing is half built. [39](39-tlc-command.md) creates it returning the plain terminal reporter on `ctx.ui` with the real clock; [40](40-live-display.md) adds the fields of `ReporterOptions` and the rule that picks the layout (streams, `TERM`, `--plain`, `tlc.plain`). The import of the reporter module goes inside the function body (F9).

Consumes: `Event`, `RunResult` (09); `Build` (23); `JavaRuntime` (20); `RunOutcome` (37, for the type checker only).

Used by: `run_tlc` and its tests (37); `TerminalReporter` (38, 40); `make_reporter` (39); the integration tests, which drive `run_tlc` with a `CollectingReporter` ([01 T9](../design/01-testing.md#t9-integration-tests), package 52).

## Tests that must pass

Plain pytest in `tests/unit/reporters/test_collecting.py`, a reporter driven directly with events ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 1). Events are built by hand from 09's classes with values that are not TLC output (an `OutputLine("line 1")`, a `PhaseChanged` with a hand-built `TlcMessage` of one plain line); no framed text is typed (rule 3).

- A `CollectingReporter` given `start`, two events, a `stderr_line`, a `notice` and `finish` keeps the `RunInfo`, the events in order, the result handed with each, the stderr line, the notice and the outcome; `calls` is `["start", "handle", "handle", "stderr_line", "notice", "finish"]`, and `close` adds `"close"` once however often it is called.
- `close` before `start` returns, records `"close"` and leaves everything empty; `write_error` is `None` throughout.
- A list passed as `calls` is the list the reporter appends to.
- A type check that `CollectingReporter` is a `Reporter`: an assignment `reporter: Reporter = CollectingReporter()` in the test module, which mypy checks when it runs on the tests (if the project's mypy run covers `src` only, the same line goes in `collecting.py` under `TYPE_CHECKING`).
- `RunInfo` is frozen (assigning a field raises `FrozenInstanceError`).

O1's Tests paragraph is not here: every test it names drives `run_tlc` with the fake `java`, and is [37](37-run-tlc.md)'s, the waiting line arriving as one `notice` included; the `TerminalReporter`'s `close` is O6's (38, 40).

Old tests: none (the old suite went in [03](03-test-foundation.md), decision D62). No stateful test applies.

## Changelog

None. O1 has no entry of its own, and no command reaches this code.

## Context for the worker

- **D8.** Reporters are one protocol fed by typed events and the result; the terminal reporter, the collecting reporter, and later JSON and other reporters are classes behind it. The protocol is the contract between the runner (37) and every reporter: adding an event is cheap, changing one touches every reporter (O1, Risks).
- **D9.** Nothing TLC printed is lost: that is why `close` exists and never raises; it runs before the application prints an `error:` line.
- **D30, D40.** Why `stderr_line` and `notice` go through the reporter: a reporter that owns the terminal (the layout of 40) decides where the line appears; under the alternate screen a line printed through `ui` would be lost (question Q12).
- **Why `close` keeps a write error instead of raising it.** It runs in a `finally`, while another exception may be passing; raising there would replace it. `run_tlc` raises the kept error after the frame when nothing else is passing, so a closed pipe still ends in 141 ([02 X1](../design/02-cross-cutting.md#x1-exit-codes)).
- **Why the consoles of `Ui` only.** tlaup's console class hands a closed pipe back as `BrokenPipeError`; a plain Rich console exits with 1 instead ([14 F6](../design/14-config-and-cli.md#f6-messages), F10).
- `RunInfo` is not `RunRecord` ([11 R6](../design/11-runner.md#r6-run-folders) says so): `RunRecord` is what `tlaup cache list` shows for one folder ([35](35-run-folders.md)).
- `Event` is a plain union of classes ([09](09-parse-package-and-model.md)), which is what lets a reporter's `match` be checked for exhaustiveness by mypy (38). Keep the annotation `Event`, not a base class.
- Startup cost: `tlaup.reporters` is imported by `cmd/tlc.py` inside the command function (39); `base.py` and `collecting.py` import only the standard library, `tlaup_parse` and, under `TYPE_CHECKING`, the types of 20, 23 and 37.
- **State of `main` when this starts.** `tlaup_parse` has its model and events (09) and possibly its parsers (10 to 13, in parallel); the store (23) and Java location (20) exist beside the old code; `tlaup tlc` runs on release 0.8.x's runner and formatter, which this package does not touch.
- Windows (D15): nothing here is system-specific.

## Done when

- `uv run poe lint` (mypy strict on `src/tlaup/reporters/`) and `uv run poe test` pass; CI is green.
- `src/tlaup/reporters/__init__.py` imports nothing at module level.
- The pull request lists what differs from O1's sketch: `RunInfo.cwd`, the `calls` argument, `results`, and `finish(outcome: object)` until 37.
- No changelog entry.

## Out of scope

- `run_tlc`, the order of calls in practice, `RunOutcome`, O1's unit tests: [37](37-run-tlc.md).
- `TerminalReporter`, plain output, the result line: [38](38-terminal-reporter.md). The layout, spools and the layout's `close`: [40](40-live-display.md).
- `make_reporter` and `ReporterOptions` as code, and the command: [39](39-tlc-command.md); the layout rule inside `make_reporter`: [40](40-live-display.md).
- The JSON reporter and any other reporter: milestone 4 and later ([40 of the design](../design/40-later-milestones.md#milestone-4-automation-surface)).

## Risks

- From O1: the event set is a contract between two packages; adding an event is cheap, changing one touches every reporter.
- From the cut: the protocol exists before its caller (37) and its main implementation (38). If either finds the protocol short, it changes `base.py` in its own pull request and says so; the protocol has no other user then.
- From the cut: the annotation of `finish` is `object` for one package's time and needs 37 to narrow it; forgetting it would make 38 fail mypy, which is where it would show.
