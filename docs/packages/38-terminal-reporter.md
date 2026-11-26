# 38. The terminal reporter, plain output

Size: L. Suggested model: most capable. Status: 38a built, 38b ready.

## Goal

`TerminalReporter` in plain mode turns the events and the outcome of a run into the output of [22 O3](../design/22-reporters.md#o3-terminal-reporter): the header and progress on stderr, the result text on stdout as it arrives, errors with their full traces and changed variables marked, SANY diagnostics in editor form each followed by the source excerpt (decision D66), the statistics and the result line with the verdict and the meaning of TLC's code; and the waiting line of a held signal (`notice`) on stderr at once. Every golden case of both builds has expected stdout and stderr files. It is built beside the old formatter; no command uses it until [39](39-tlc-command.md).

## Covers

- Roadmap items:
  - [Milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), "Live terminal reporter: render the layout on a terminal; fall back to plain streamed output when stdout is not a terminal or `--raw` is given." (line 324). In part: the plain streamed output. The layout is [40](40-live-display.md); the command that uses it, [39](39-tlc-command.md).
  - Milestone 1b, "Snapshot tests through a fixed-width, colourless console with an injected clock, replacing assertions on Rich internals." (line 330). In part: the plain-output half (the helper, the expected files of every golden case, colour on, width 40, the markup test in plain mode). The layout half is 40's.
  - Milestone 1b, "Fix the per-line re-rendering cost, which grows with the square of the output, and the unbounded list of output lines kept in memory." (line 329). In part: the two plain-mode tests of O7. The layout-mode test and the changelog entry are 40's.
  - [Milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust), "Show the violated-invariant text together with the trace." (line 173) and "Print TLC text without Rich markup interpretation ..." (line 174). In part: the reporter that does both and their tests; the user sees it, and the changelog says so, at 39.
  - [Milestone 4](../roadmap.md#milestone-4-automation-surface), "Editor-style diagnostics in plain output: SANY and parse errors as `path:line:col: severity: message`, replacing the `file://...#L` links (decision D22)." (line 478), done in milestone 1b (a departure the design README lists). In part: inside a TLC run, and the formatting function; `tlaup sany` is [41](41-sany-command.md).
  - Milestone 4, "Results on stdout, diagnostics and progress on stderr ..." (line 479). In part: the stream rule as the reporter applies it. The options `--quiet`, `--verbose`, `--color` stay in milestone 4.
- Design sections:
  - [22 O3](../design/22-reporters.md#o3-terminal-reporter): all of it except the layout mode (O4, package 40). The "Checkpoint kept" note and the disagreement warning are not the reporter's (39).
  - [10 P10](../design/10-parser.md#p10-error-text-with-the-trace), [10 P11](../design/10-parser.md#p11-tlc-text-and-rich-markup): the reporter's side and both tests (P11's in plain mode; its layout-mode twin is 40's).
  - [02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr): which stream each piece goes to, in plain mode.
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes), "The meaning of a code": printing it in the result line.
  - [22 O6](../design/22-reporters.md#o6-snapshot-tests): the helper, "Plain mode", the colour and width cases, the markup test in plain mode. Everything about layout mode, the two streams and `close` in layout mode is 40's.
  - [22 O7](../design/22-reporters.md#o7-rendering-cost-and-memory): the two plain-mode tests.
  - [22 O2](../design/22-reporters.md#o2-delete-dead-display-code): the rows marked O3, as replacements built here (`diff_values` and `render_value_diff` rewritten against `Value`, the coverage renderers against `CoverageItem`; the one `format_elapsed` is 35's, imported here). The old ones are deleted at the switch (39).
  - [11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load), part 4: when the reporter shows the hint (the texts are [34](34-override-check.md)'s).
  - [21 S1](../design/21-other-tools.md#s1-sany), step 4: the editor form of a diagnostic and the source excerpt under it (D66, `source_excerpt` with its unit test), as functions [41](41-sany-command.md) reuses. The `tlaup sany` scenarios of the excerpt are 41's.
  - [22 O1](../design/22-reporters.md#o1-reporter-interface), `notice` in plain mode: the waiting line on stderr at once (question Q12).
- Rows of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) this package owns: R9 (coverage), R15 (lines outside TLC's messages), R16 (progress with thousands separators), R18 (a counterexample's states with their changes marked), R19 (an error with no trace), R20 (SANY errors in a run with file and line) and R21 (the source excerpt, decided by D66), each for `tlc`; [41](41-sany-command.md) writes R20 and R21 for `sany`. Under Tests each row names the case or test that holds it (finding G1).

## Depends on

- [03](03-test-foundation.md): the isolation fixture, `assert_matches` and `--update-expected`.
- [07](07-golden-files.md): the golden captures, specs and `cases.toml` of both builds.
- [09](09-parse-package-and-model.md): the model, the twenty events, `describe_exit_status`. [11](11-values.md): `Value`, `parse_value` (the value diff, P11's trace-state case).
- [13](13-tlc-parser.md): `TlcParser`, which the test helper replays each case through. [15](15-golden-expected-results.md): the golden tests pass (see Context: the roadmap's rule).
- [16](16-ui-messages.md): `Ui` with `color`, `terminal` and `size`; `ui.out`, `ui.err`.
- [20](20-java-location.md): `JavaRuntime`. [23](23-tool-store.md): `Build` and `format_build`.
- [34](34-override-check.md): `class_version_hint`, `load_failure_hint`.
- [36](36-reporter-interface.md): `Reporter` (with `notice`), `RunInfo` (with `cwd`).
- [37](37-run-tlc.md): `RunOutcome`, which `finish` reads. [35](35-run-folders.md) (through 37): `format_elapsed` in `tlaup/durations.py`.

Change from the draft (36, 13, 16): added 37, because `finish` takes a `RunOutcome` and reads its fields, so 38 cannot be built before it (37 and 38 are therefore not parallel; the report says how they could be); 34, for the two hint texts (34's own Risks named this); 15, for the roadmap's rule; 03, 07, 09, 11, 20 and 23 for what the tests and the header use.

## Files

Creates:

- `src/tlaup/reporters/terminal.py`: `TerminalReporter` (plain mode), `render_event`, `render_status`, `header_lines`, `render_summary`, the coverage renderers.
- `src/tlaup/reporters/text.py` (00's tree now lists it): the pure text functions `format_count`, `format_path`, `format_diagnostic`, `source_excerpt`, `progress_line`, `stats_line`, `result_line`, and the value diff (`ValueDiff`, `diff_values`). They take values and return strings or Rich `Text`, read nothing, and are unit-tested one by one. `format_diagnostic` and `source_excerpt` are here rather than in `terminal.py` so that [41](41-sany-command.md) can print SANY's diagnostics in the same form without importing the reporter; S1 puts `source_excerpt` "beside the function that writes the editor-form line".
- `tests/unit/reporters/replay.py`: the replay helper of O6 (below), which [40](40-live-display.md) reuses.
- `tests/unit/reporters/test_terminal.py`, `tests/unit/reporters/test_text.py`.
- `tests/unit/reporters/expected/terminal/<build>/<case>.stdout.txt` and `.stderr.txt` for every golden TLC case of both builds (`<build>` is the golden folder's name, `v1.7.4` and `2026.11.15.002146`), and the colour and width files of `violation` (named `violation.color.stdout.txt` and `violation.w40.stdout.txt`; the names are stage 4's).

Changes: none. Deletes: none. The old `tlc/formatter.py` and `tlc/components.py` are untouched: until 39 they are what `tlaup tlc` prints with, and 39 and 40 delete them. Their tests went with the old suite in [03](03-test-foundation.md) (decision D62).

Shared with packages of the same period: `tests/unit/reporters/` with [40](40-live-display.md), which adds `test_layout.py` and its own expected files beside these.

## Interfaces

Provides. O4 gives the constructor as `TerminalReporter(ui, *, mode, interval, clock, refresh_thread=True)`; this package builds the plain mode only, so it takes `ui` and `clock`, and [40](40-live-display.md) adds `mode`, `interval` and `refresh_thread` with the layout, with defaults (`mode="plain"`) so that this package's helper and tests construct it as they do here. Everything marked was written by stage 4 from O3's words.

```python
# tlaup/reporters/terminal.py
class TerminalReporter:                                  # a Reporter (36)
    def __init__(self, ui: Ui, *, clock: Callable[[], float]): ...
    write_error: OSError | None
    def start(self, run: RunInfo) -> None                # header_lines on ui.err
    def handle(self, event: Event, result: RunResult) -> None
    def stderr_line(self, line: str) -> None             # TLC's stderr line, unchanged, on ui.err at once
    def notice(self, line: str) -> None                  # tlaup's own line during the run (O1), on ui.err at once
    def finish(self, outcome: RunOutcome) -> None        # render_summary on ui.out, then close()
    def close(self) -> None                              # plain mode: nothing to release; idempotent; never raises

def render_event(event: Event, result: RunResult, run: RunInfo) -> list[Text]       # O3; the result text an event adds
def render_status(event: Event, result: RunResult, run: RunInfo) -> list[Text]      # stage 4: stderr lines other than progress
def header_lines(run: RunInfo) -> list[Text]                                        # stage 4
def render_summary(outcome: RunOutcome, run: RunInfo, elapsed: float) -> list[Text]  # stage 4: statistics, coverage, result line

# tlaup/reporters/text.py (stage 4)
def format_count(n: int, *, approximate: bool = False) -> str     # "1,771,600", "about 1,771,600"
def format_path(path: Path | str, cwd: Path) -> str     # relative to cwd when beneath it, else absolute (S1)
def format_diagnostic(d: Diagnostic, *, cwd: Path, spec: Path, source_text: str | None) -> list[str]
    # 21 S1 step 4 (signature from S1): the editor-form line, then the excerpt (source_excerpt, when
    # source_text is given and d has a location the text holds), then the details, indented (finding H4)
def source_excerpt(text: str, location: Location) -> list[str]                # 21 S1 (D66); signature from S1
def progress_line(p: Progress) -> str                   # "44 states generated, 44 distinct, 35 on queue, diameter 4"
def stats_line(s: FinalStats, *, approximate: bool) -> str      # "44 states generated, 44 distinct, 35 left on queue; depth 4"
def result_line(outcome: RunOutcome, result: RunResult, elapsed: float) -> str  # the table of O3
def diff_values(old: Value | None, new: Value) -> ValueDiff     # O2: kept, rewritten against Value
```

`render_event` is the one renderer of the result text (O3): plain mode writes its lines to `ui.out` at once; layout mode (40) writes the same lines to the stdout spool, so the two modes give one text. `render_status` gives the reporter's own stderr lines that an event causes, apart from progress, which has its own function because the layout shows progress in panels and not as lines: TLC's version line when it differs from the store's, and the override hint. Both are pure apart from one read: they read the event, the live result and the `RunInfo`, and keep no state; for a `DiagnosticFound` with a location, `render_event` reads the file its editor-form line names to make the excerpt (below). The previous state of a trace, which the changed-variable marks need, is `error.trace.states[-2]` of the live result at `TraceStateAdded`.

**What goes where in plain mode** (O3, X2), in the order it happens:

| Call | Stream | What |
| --- | --- | --- |
| `start` | stderr | `header_lines`: `TLC <format_build(run.build)> (<calver>), Java <version>, workers <w>`, then `<spec>  cfg: <cfg>`, spec and cfg written with `format_path`. A part that is not known is left out, with no placeholder (O3): no `--cfg`, the spec alone; `run.workers` `None` (the user passed `-workers` after `--`), no workers part; `run.java.version` `None`, no version; a build with no CalVer, no parenthesis. |
| `handle(VersionSeen)` | stderr | `ToolInfo.raw`, only when it differs from the store's build: when `ToolInfo.revision` is not a prefix of `build.commit`, or the build has a CalVer and `ToolInfo.version` is not it (O3). |
| `handle(OutputLine)` | stdout | The line, exactly as TLC printed it. |
| `handle(ProgressMade)` | stderr | `progress_line`, at once; nothing held back or rate-limited; a count TLC gives as `-1` (the queue in a simulation, P3) is left out. |
| `handle(DiagnosticFound)` | stdout | `format_diagnostic`'s lines, as the diagnostic completes: the editor-form line, then the source excerpt (below), then the details the parser kept apart (a parse error's residual stack), indented. The reporter reads the file and passes its text as `source_text` (`None` when it cannot be read); it prints the list as it comes and splices nothing, as [41](41-sany-command.md) does (S1). |
| `handle(ErrorOpened)` | stdout | `Error: ` and the first line of `message.text_lines()`, further lines indented by two; a nested message's lines in their place. stderr: the override hint when it applies (below). |
| `handle(ErrorExtended)` | stdout | The related message's `text_lines()`, indented under the error (TLC's lead-in, 2121 or 2264, is the trace's heading; tlaup adds none). |
| `handle(TraceStateAdded)` | stdout | The state (below). |
| `handle(TraceClosed)` | stdout | A liveness trace's last line, `Back to state <n>` or `Stuttering`; for any other trace nothing. |
| `handle(WarningFound)` | stdout | `Warning: ` and the text, further lines indented. |
| `handle(UnknownMessage)` | stdout | `TLC message <code>: ` and the text as TLC printed it. |
| `stderr_line` | stderr | The line, unchanged. |
| `notice` | stderr | The line, at once (O1): the waiting line while a first signal is held during a checkpoint. Nothing of it on stdout. |
| `finish` | stdout | `render_summary`: the statistics line, the coverage table and the inline coverage of the spec when the result has coverage, then the result line. |

An error or warning whose code is not in the code table (`message.name is None`) gets the `TLC message <code>: ` prefix after `Error: ` or `Warning: `. Events that print nothing: `Information`, `PhaseChanged`, `ModeSeen`, `OverrideLoaded`, `CoverageAdded`, `StatsUpdated`, and `CheckpointStarted`, `CheckpointWritten`, `Recovered`, `Finished` (O3; the last four settled by the stage 4 review, question Q11: `Finished` gives the result line its duration, `Recovered` its `resumed from a checkpoint`, the two checkpoint messages are TLC's information, hidden as other chatter is, and the waiting line says what matters when a signal is held). The dispatch is a `match` with a case for every member of `Event` and `assert_never` in the default, so mypy fails the build when 09 adds an event without a case.

**A trace state** (O3, "Traces"; the mock-up of O3 is the reference): numbered as TLC numbered it; the action and its location as `File.tla:line:col`, the file from `result.module_files[location.module]` written with `format_path`, none for the initial state; each variable on its own line, `Variable.raw` as TLC printed and wrapped it, continuation lines kept; a variable whose value differs from the previous state's (`Value` equality; a `raw` value compares as text, P7) is marked with `*`, and on a colour console the changed part is highlighted with `diff_values`. A `-difftrace` run needs nothing special: the parser has carried the left-out variables forward ([10 P5](../design/10-parser.md#p5-error-traces)), they compare equal and get no mark.

**The source excerpt** ([21 S1](../design/21-other-tools.md#s1-sany), decision D66; inventory row R21). Under the editor-form line of a diagnostic that has a location, the lines of the spec it points to, made by `source_excerpt` (the same function `tlaup sany` uses, [41](41-sany-command.md)), as S1 gives them: the two lines before the location's first line (fewer at the top of the file), that line, a line of `^` marks, the `Error here: line L, col A to B` line (`line L, col A to line L2, col B` over several lines, `line L, col A` with no end), the rest of the location's lines when it spans several, and the two lines after its last line (fewer at the end); each indented by two spaces, the line number right-aligned in four columns and ` | ` before the text; the marks from the column to the end column on the first line (to the end of the line when the location ends later; one mark with no end), the space in front of them copying each tab of the source line. The caller reads the file the editor-form line names (the file SANY announced for the module, absolute), as UTF-8 with undecodable bytes replaced; no location, a file that cannot be read, or a line not in it give no excerpt and no note (0.8's "(Source code unavailable)" is dropped). The excerpt is text from outside tlaup, printed as text (P11), on stdout with its diagnostic, in the result text of both modes; it is never part of milestone 4's JSON. S1's example (research 12's `SemErr.tla`) is the reference:

```
SemErr.tla:4:13: error: Unknown operator: `y'.
     2 | EXTENDS Naturals
     3 | VARIABLE x
     4 | Init == x = y
       |             ^
       | Error here: line 4, col 13 to 13
     5 | Next == x' = x + 1 + Foo(2)
     6 | ====
```

**The result line** (O3's table, decision D54), from `outcome` and `outcome.result`:

- The verdict's words lead; TLC's code (`outcome.tool_exit_code`) and its meaning from `describe_exit_status(code)` ([02 X1](../design/02-cross-cutting.md#x1-exit-codes)'s table, decision D63) stand beside them in parentheses, `(TLC exit code 12: an invariant was violated)`, or `(TLC exit code 0)` for 0. X1 writes each meaning as a sentence (`An invariant was violated.`); the line shows it without its full stop and with its first letter in lower case, unless the first word is an acronym (`TLC`, `JVM`), which stays as it is (X1's rule as revised; finding G5). A code X1 does not document has the meaning `TLC returned a code it does not document` (its word, for milestone 4's JSON, is `error`); the reporter prints the meaning, never the word; then ` in <format_elapsed>` for `errors`, `no-error` and `no-error-bounded`. The duration is TLC's own (`result.duration_ms`), else the reporter's clock from `start` to `finish`.
- `no-error-bounded` names the search: `(simulation)` for mode `simulate`, `(depth-first)` for `depth-first`.
- `not-checked`, by the first error's kind: `parse`, or no error and a SANY diagnostic of severity `error`: `the spec has errors`; `config`: `the configuration has errors`; `usage`: `TLC refused its arguments`; `exception` or `other` opened before the initial states: `TLC failed before computing the initial states` (O3, settled by the stage 4 review, question Q11), so the line reads `Result: not checked: TLC failed before computing the initial states (TLC exit code N: ...)`.
- `incomplete`: `interrupted after <elapsed>` when `outcome.stopped_by` is set (reporter's clock); `stopped because the output was closed` when `outcome.stopped_for_closed_pipe`; else `TLC stopped without finishing (TLC exit code N: ...)`.
- Suffixes: `; resumed from a checkpoint` when `result.resumed`, with `, state counts approximate` when `result.counts_approximate` (and then the statistics line writes `about` before each count); `; a checkpoint was not kept (use --keep to keep one)`, `; the checkpoint was incomplete, nothing to resume` or `; a -dfid run cannot be resumed` for `outcome.dropped_checkpoint` of `"not-asked"`, `"incomplete"`, `"depth-first"`.
- The one exception: TLC's code 10 with the first error of kind `postcondition` reads `(TLC exit code 10: a postcondition was false)`.
- The disagreement warning (P3) is not here: [39](39-tlc-command.md)'s `print_run_notes` prints it after `close`.

**The override hint** ([11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load), part 4, as O3 states the condition), on `ErrorOpened`, written to stderr as a `hint:` line when the error opens (O3; X2: tlaup's own hints are on stderr): an error with code 2173 always gets one, `class_version_hint(text)` when its text holds the class-file sentence, else `load_failure_hint(run.override_classes)`. An error of kind `exception` with `result.phase` still `STARTING` when it opened, `run.override_classes` not empty, and no nested message whose code has kind `config` in the code table, gets `load_failure_hint`, or `class_version_hint` when its text holds `java.lang.UnsupportedClassVersionError` and the sentence. The functions are [34](34-override-check.md)'s; "the text" is the message's `text_lines()` joined.

**Text from outside tlaup is never markup** (P11): every line built from TLC, SANY, a value, a path or a class name is a `rich.text.Text` built by one helper that takes a `str`; printing uses `markup=False, highlight=False`. Only literals of tlaup's own may carry style. **Nothing in the result text is wrapped or cut by tlaup** (O3, "Widths"): print with Rich's `soft_wrap=True` (or the equivalent `overflow` and `no_wrap` settings), so a long value at width 40 comes out as TLC wrapped it; the width-40 expected file shows it.

Consumes: `Reporter`, `RunInfo` (36); `RunOutcome` (37); `Ui` (16); the model, events and `describe_exit_status` (09); `Value` (11); `Build`, `format_build` (23); `JavaRuntime` (20); the two hints (34). The tests also use `TlcParser` (13).

Consumed by: `make_reporter` (39); the layout mode (40), which reuses `render_event`, `render_status`, `header_lines`, `render_summary` and the helper; `tlaup sany` (41), which uses `format_diagnostic` the same way.

### What the stage 4 review settled here

Stage 4 had built three readings into this package (question Q11 of the index); the maintainer confirmed them on 2026-11-24 and O3 now states each: the four checkpoint, recovery and finish events print nothing; the header leaves out what is not known, the version line is `ToolInfo.raw`, the hint is a `hint:` line on stderr when the error opens, and a `-1` count is left out of the progress line; `not-checked` after an early `exception` or `other` error reads `TLC failed before computing the initial states`. The meaning of every TLC code is X1's table (question Q4, decision D63). The excerpt under each diagnostic is decision D66, and the waiting line through `notice` is question Q12. Nothing here waits.

## Tests that must pass

Plain pytest, a reporter driven directly with events ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 1). No feature file: no command reaches the reporter until 39, whose `tlc_run.feature` then checks the same output end to end.

**The helper** (`tests/unit/reporters/replay.py`, O6): reads a golden case as the runner reads it (binary, lines that keep their newline, decoded as the launcher decodes), maps the capture's folder in SANY's `Parsing file` lines to the case's folder under `golden/specs/` (O6, D66), so that the reporter reads the spec for the excerpt as in a real run (a flag turns the mapping off), feeds each line to a real `TlcParser`, hands each event to a `TerminalReporter` with the result, then `close()`'s events, then `finish` with a `RunOutcome` built from the case's `cases.toml` (exit code; nothing stopped; nothing kept or dropped), and `close`. The reporter gets a `Ui` on two `StringIO` streams at width 100 with colour off (`Ui(stdout, stderr, stdin, color=False, env={}, size=(100, 30))`), a clock that advances one second per call, and a fixed `RunInfo`: a hand-built `Build` matching the golden folder, a `JavaRuntime` of version `25.0.5`, `workers="auto"`, and `spec`, `cfg` and `cwd` chosen so that the paths the captures hold (`<tmp>/...` placeholders) come out relative; check one capture's `Parsing file` line for the exact form. Where a case has a captured stderr file, its lines go through `stderr_line` before `finish`.

`tests/unit/reporters/test_terminal.py`:

- **Plain mode** (O6): for every golden TLC case of both builds, the two streams equal `expected/terminal/<build>/<case>.stdout.txt` and `.stderr.txt` (`assert_matches`). The files are generated with `--update-expected` and reviewed as what a user sees. These files are the test of inventory rows R9 (the `coverage` case: the table, and the spec's lines with their counts; whether an unreached line keeps a mark is what the reviewed file shows, as the row's note says), R15 (a case whose spec prints with `Print`, and an unknown message), R16 (the progress lines on stderr, with thousands separators), R18 (`violation`: every state with its action and location, `*` on each changed variable), R19 (an error with no trace, such as a false `ASSUME`) and R20 (`sany-semantic-error`: the editor-form line with file, line and column); the pull request names the case that holds each row.
- **P10**: in the `violation` file the line `Error: Invariant Small is violated.` stands directly above the trace's lead-in and states, and no line is followed by a blank line TLC did not print. Covered by the expected file; also asserted as two facts on the captured text, so that a regeneration that loses it fails.
- **P11**, in plain mode: `OutputLine` events with `[a |-> 1]`, `[/]`, `[bold]x[/bold]` and `\[` through a `Ui` built with `terminal=True, size=(100, 30), color=True` (and `TERM=xterm-256color` set with `monkeypatch`, since the isolation fixture's `TERM=dumb` can switch Rich's colour off; check), and the plain text of the output (escape sequences removed) equals the input; the same four strings as record values of a hand-built trace state (`parse_value` gives a `raw` value for those that do not parse, which is fine: the test is about printing). Short strings for this test are allowed by rule 3.
- `violation` with colour on (`TERM=xterm-256color`, `color=True`, `terminal=True`): `violation.color.stdout.txt`, which holds the escape sequences and is reviewed as a file; and at width 40: `violation.w40.stdout.txt`, where a value longer than 40 columns is not wrapped by tlaup.
- **The streams**: for `violation`, stdout holds the result text and stderr only the header, progress lines and nothing else (the X2 assertion of 39's feature, at this level).
- **The source excerpt** (O6, D66; inventory row R21): the plain expected stdout of `sany-semantic-error` and `parse-error`, on both builds, holds the excerpt under each editor-form line, the two lines after included. The same replays with the folder not mapped give the editor-form lines alone, with nothing in place of the excerpt. The pull request names row R21.
- **The waiting line** (O6, O1): in plain mode a `notice("waiting for TLC to finish writing its checkpoint; press Ctrl-C again to stop now")` between two events is on stderr at once, in order with the header and progress lines, and stdout has nothing of it.
- **The override hint**: `override-*` cases and research 28's two captures (2173, and 1000 with `UnsupportedClassVersionError`) replayed with `override_classes` set give the hint on stderr, the specific form with the right two Java versions; v1.7.4's `postcondition-false` (a 1000 holding a 5006, kind `config`) gives none; the same `override-*` case with `override_classes` empty gives none, apart from 2173, which always gets one.
- **The result line**, hand-built outcomes on a replayed result where no golden case reaches the row: `stopped_by="int"` gives `Result: incomplete, interrupted after ...`; `stopped_for_closed_pipe`; each of the three `dropped_checkpoint` words; a `recover` capture gives `; resumed from a checkpoint`, and with `counts_approximate` set also `, state counts approximate` and `about` in the statistics line; code 10 with a `postcondition` error; `deadlock-flag-multierror` (exit 0, two errors) gives `Result: errors found (TLC exit code 0) in ...`.
- `close` before `start`, twice after `finish`, and after a `handle` that raised: returns, writes nothing, `write_error` stays `None`. A `ui.out` whose stream raises `BrokenPipeError` makes `handle` raise it (it passes, O1).
- **O7, plain mode**: 300,000 numbered lines (`line 1` to `line 300000`, the form T12 rule 3 allows for a spec's own output) fed through a `TlcParser` into a `TerminalReporter` writing to a null stream: the result's `output` has 10,000 entries and `output_dropped` is 290,000. A second test counts the write calls of the stdout stream for 1,000 and for 10,000 lines: the ratio is 10 within a small constant, so the cost is linear. No test measures time.

`tests/unit/reporters/test_text.py`: `format_count`; `format_path` beneath and outside the folder; `format_diagnostic` for S1's four examples (a location, a parse error with details, no location, a warning), each with `source_text=None` (the editor-form line, then the details) and the first with the spec's text (the line, the excerpt, then the details: S1's order), and for a module that was not announced (the spec's path); `result_line` for each row of O3's table, the meaning of a code X1 does not document (99: `TLC returned a code it does not document`) and the `not-checked` words after an early exception; `diff_values` on sets, sequences, records, functions and two `raw` values with different text.

`source_excerpt`, S1's unit test on hand-written text: for a location on line 4, lines 2 to 4, the marks, the `Error here` line and lines 5 and 6, exactly as S1's example; on line 1, that line alone before the marks; over two lines, marks to the end of the first and `line 4, col 13 to line 5, col 2`; with no end, one mark and `line 4, col 13`; a tab in front of the column, a tab in the mark line; a location at the last line, no lines after; a line past the end of the text, nothing.

Old tests: none (the old suite went in [03](03-test-foundation.md), decision D62). No stateful test applies.

## Changelog

None in this package. O3's Changed entry, P10's and P11's Fixed entries and X2's Breaking entry describe what a user sees at the switch and are written there, by [39](39-tlc-command.md), whose file lists them word for word. O6 has no entry. O7's entry is [40](40-live-display.md)'s.

## Context for the worker

**Decisions.**

- D8: the reporter never parses and never decides the exit code. If it needs something the result lacks, the result is extended in `tlaup_parse` (a change to 09 or 13, said in the pull request), not worked out from text here.
- D9: nothing is lost. Every `OutputLine` is printed, also beyond the result's 10,000-line cap (that is what the events are for); an unknown message is shown with its code.
- D22: diagnostics in editor form, replacing the `file://` links of `render_sany_error`.
- D66: `render_sany_error`'s source excerpt is kept, under the editor-form line, with `^` marks and a `|` gutter instead of 0.8's `▲` and box characters, which read the same in a CI log and on a console without those glyphs; never in JSON, which carries file, line and column.
- D29, D54: the result line leads with the verdict and shows TLC's code beside it; tlaup's own exit code stays TLC's and is not the reporter's to set. Research 22 captured TLC exiting 0 after two violations, which is why the verdict and not the code leads.
- D30: results on stdout, everything about getting there on stderr; the test is "would it be in milestone 4's JSON result".

**The roadmap's rule.** Milestone 1b says reporter work does not start before the golden-file tests of milestone 1 pass, since reporters render what the parser produces. That is why 15 is a dependency: the expected files here are the parser's output rendered, and a parser still changing would churn hundreds of them.

**What O3 rejected, so as not to rebuild it**: the tree widgets of today's `render_error_trace` (box characters, re-indented values that fight TLC's wrapping); printing a trace only at the end or the related messages before the states (everything is printed in arrival order: the `assertion-failure` captures have 2103 after the states, and that is where it goes); a heading of tlaup's own with the state count; hiding progress in plain mode; spacing or rate-limiting progress lines (TLC spaces them itself, about 3 seconds after the initial states and then every 60 seconds, research 31; a line that depended on the clock would make expected files depend on timing). By the same reasoning keep the coverage table and the inline coverage in plain characters rather than box drawing, since they go to files and pipes; the expected files show the choice.

**The changed-part highlight** is the least certain part (O3, Risks). `Value` keeps each node's source text but no offsets into the printed line, so highlighting a part means finding a changed child's text in the line. If that reads badly on the real traces, cut it down to the `*` mark, as O3 allows, and say so in the pull request. Do not add offsets to `tlaup_parse` for it: `Value` is part of milestone 4's JSON.

**The two places the reporter reads a file.** Coverage: the inline view reads `RunInfo.spec` and shows the rows whose `location.module` is the spec's module, as today's `render_inline_coverage` does; in the helper's tests `RunInfo.spec` must then point at the real golden spec for the `coverage` case. The excerpt: the file of a diagnostic's module, read when the diagnostic completes; a read that fails gives no excerpt and never an error.

**One duration form.** The result line's duration is written by `format_elapsed` from `tlaup/durations.py`, which [35](35-run-folders.md) creates for its "Checkpoint kept" note; import it, do not write a second one (O2's one function; settled with the maintainer at the stage 4 sign-off, 2026-11-24). Its rule and tests are 35's.

**Traps.**

- Rich interprets `[...]` as markup and wraps lines at the console's width unless told not to; both are wrong here (P11, O3 "Widths"). The width-40 and markup tests catch both.
- `TERM=dumb` from the isolation fixture can switch colour off even on a console forced to terminal mode; the colour-on tests set `TERM=xterm-256color` with `monkeypatch` (as O6 says for the layout; for plain colour it was not tried).
- `result` handed to `handle` is the same live object every time; read what you need when the event arrives (the phase at `ErrorOpened`, the previous state at `TraceStateAdded`), since it changes after.
- `finish` calls `close` itself; `close` is then called again from the frame's `finally`, and does nothing.
- Expected files show exactly what a user sees: nothing is normalised in the helper (T8); the fixed `RunInfo` and the injected clock are what keep them stable.
- `format_build` without the list of other installed builds gives the shortest form among none, `rolling@bc1b506`; the header does not look at the store.

**State of `main` when this starts.** `tlaup tlc` still runs on release 0.8.x's `cmd/tlc.py`, `tlc/runner.py` and `tlc/formatter.py`. Beside them: `tlaup_parse` complete with its golden tests, the launcher, the invocation, the run folders, `tlc/run.py` with `RunOutcome` (37), `reporters/base.py` and `collecting.py` (36). Nothing imports `reporters/terminal.py` when this package merges.

**Known gaps the design postpones.** `--verbose` (SANY's own chatter, the list of loaded overrides in a verbose header, the project root in the run header of [11 R10](../design/11-runner.md#r10-project-root)), `--quiet`, `--color`: milestone 4. The JSON reporter: milestone 4. SANY's columns were read as counting characters, a tab as one (S1, Risks); if SANY counts a tab otherwise, the marks stand in the wrong place on such a line and the editor-form line is still right.

## Done when

- The tests above pass; `uv run poe lint` (mypy strict, the exhaustive `match` included) and `uv run poe test` pass; CI is green.
- Every golden TLC case of both builds has its two expected files, and the pull request says a reviewer read them as user output (the index may let them be reviewed per build).
- The pull request lists every signature that differs from this file, whether the changed-part highlight stayed or was cut to the `*` mark, and the inventory rows it owns (R9, R15, R16, R18, R19, R20, R21, for `tlc`), each with the case that holds it.
- No changelog entry.

## Out of scope

- The layout mode, the spools, `refresh()`, the `atexit` hook, `--plain`, `--refresh-interval`, the layout's expected frames and the "two modes give one text" test: [40](40-live-display.md).
- `make_reporter`, the command, `print_run_notes` (the note, the dropped checkpoint of a raw run, the disagreement warning), the changelog entries and deleting the old formatter, components and their five tests: [39](39-tlc-command.md).
- The hint texts and the override check: [34](34-override-check.md). The run frame and `RunOutcome`: [37](37-run-tlc.md).
- `tlaup sany`'s own output (stderr progress, the count line, its exit code): [41](41-sany-command.md).

## Risks

- From O3: the layout of the text is taste; the expected files make every change to it visible in review. The diff highlight may be cut to the `*` mark. The postcondition exception is one special case in a table-driven line; a second would mean the word should come from the error, not the code.
- From O6: the expected files change whenever the output is adjusted; that is their purpose.
- From the cut: hundreds of expected files (both builds, research 1's and research 22's cases, the override cases) in one pull request. Generating them is one command; reviewing them is the work. If the index finds that too large, the files of the second build can follow in a second pull request of the same package, after the first build's are reviewed.
- From the cut: `finish` needs 37's `RunOutcome`, which serialises 37 and 38.

## Pull requests (decided by stage 4)

This package is delivered as two pull requests; the index lists them as 38a and 38b. Most of its size is expected files, which a reviewer reads one by one.

- **38a**: `reporters/text.py` (with `source_excerpt`), `reporters/terminal.py`, the replay helper, all the unit tests, and the expected files of `v1.7.4`. Depends on everything this file lists.
- **38b**: the expected files of the rolling build, reviewed partly as differences from 38a. Depends on 38a.

A package that names 38 as a dependency waits for 38b.
