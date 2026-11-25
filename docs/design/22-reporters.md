# 22. Milestone 1b: reporters

Covers "Reporters (decisions D3 and D8)". Relies on decisions D3, D8, D9, D22, D29, D30, D40. The roadmap's rule stands: reporter work does not start before the golden tests of milestone 1 pass, since reporters render what the parser produces.

Revised 2026-11-15 after the review of the first design wave. The first version designed the live display as a one-line footer; the maintainer chose the roadmap's full-screen layout instead (decision D40), and O2, O4, O5, O6 and O7 are rewritten for it. Revised again on 2026-11-15 and 2026-11-16 after the second check of the revision: the reporter gets a `close` (O1), the "Checkpoint kept" note has one owner, which is the command (O3, O4), nested messages have a printing rule (O3), and the layout's tests can now fail when the live display is broken (O4 to O6).

What was tried, on 2026-11-15, on the locked Rich 13.9.4 and Linux only, with a console writing to memory and forced to terminal mode: a `Live` with `screen=True` writes the enter and leave sequences of the alternate screen and the frame between them; its refresh thread redraws a changed `get_renderable` value with no call from outside; `Live.stop` does not refresh on the alternate screen (read in the source); the console takes its size from `COLUMNS` and `LINES` when they are set; `Live.refresh_per_second` holds the constructor's value. Not tried then: any of it on a real terminal or a pty, another Rich version, `pyte`, resizing. Research 30 (top-up, 2026-11-20; [result](../research/30-library-behaviours.md)) tried the first three on a real pseudo-terminal with Rich 13.8.0, 13.9.4, 14.0.0, 14.3.4 and 15.0.0 on Linux, and with all but 14.0.0 on macOS: every version wrote the two sequences, redrew from its refresh thread with no call from outside, and did not refresh on stop; `pyte` 0.8.2 followed what each drew. Resizing and a Windows console were not tried.

## O1 Reporter interface

Roadmap: "A reporter interface fed by the parsed result and run events. Move the streaming state and the final summary out of the command into it; the command shrinks to option parsing, error mapping and the exit code. Terminal and non-terminal output differ only in where they write and in the footer."

**Problem.** `cmd/tlc.py` holds two copies of a callback that re-scans `res.output_lines` and `res.initial_states_stat` by index on every line, prints as it goes, and then prints the summary itself. The "formatter" it also updates is never rendered; the call is there to keep tests passing.

**Design.**

```python
# tlaup/reporters/base.py
@dataclass(frozen=True)
class RunInfo:  # known before the tool starts
    tool: str  # "tlc"
    spec: Path
    cfg: Path | None
    build: Build
    java: JavaRuntime
    workers: str | None
    project_root: Path | None
    override_classes: tuple[str, ...]
    command: tuple[str, ...]


class Reporter(Protocol):
    def start(self, run: RunInfo) -> None: ...
    def handle(self, event: Event, result: RunResult) -> None: ...  # events of 10 P3
    def stderr_line(self, line: str) -> None: ...  # a line the tool wrote to stderr
    def notice(self, line: str) -> None: ...  # a line of tlaup's own during the run (below)
    def finish(self, outcome: RunOutcome) -> None: ...  # 11; the run ended and has an outcome
    def close(self) -> None: ...  # always called last; never raises

    write_error: OSError | None  # set by close when a write failed in it
```

The order of calls is fixed by `run_tlc` ([11](11-runner.md)), which is the only caller in tlaup:

1. `start(run)`, once, after the run folder is entered and immediately before the child is started. The preflight is over by then, so a run that cannot start never opens the live layout.
2. `handle`, `stderr_line` and `notice`, any number of times, from the main thread.
3. `finish(outcome)`, once, when the run ended in any way that has an outcome: normally, with a failure, or after one or two signals. It writes what closes the result (the statistics, the coverage, the result line) and then calls `close` itself.
4. `close()`, from a `finally` in `run_tlc`. It is the reporter's way out and has three properties. It is **idempotent**: after `finish` it has nothing left to do, and a second call does nothing. It is **safe before `start`**: it does nothing. It is **safe after a `start` that raised half way**: `start` records each thing it takes as it takes it (the spools, then the live display), and `close` releases exactly what is recorded, so a `start` that failed between the two leaves no spool file behind and never stops a display that was not started. And it **never raises**, because it runs while another exception may be passing and must not replace it: if a write to stdout or stderr fails inside it (a closed pipe, a full disk under a redirect), it stops writing to that stream, still releases what it holds, and keeps the first such error in `write_error`. `run_tlc` raises `write_error` after its frame when no other exception is passing, so a closed pipe still ends in 141 ([02 X1](02-cross-cutting.md#x1-exit-codes)). Raising it means the outcome is not returned and the command's `print_run_notes` does not run, so before raising `run_tlc` adds the "Checkpoint kept" note to the error with `add_note` when the folder was kept, the same way it does for an exception from the middle ([11 R6](11-runner.md#r6-run-folders)); the handler prints it on stderr.

**When `finish` was never reached** (the middle of `run_tlc` raised: the child could not be started, a write failed, an internal error), `close` still makes the terminal usable and loses nothing that was shown (D9): it leaves the live layout if it is up, and writes out the result text and the tool's stderr lines received so far (O4). It writes no statistics and no result line, since there is no outcome; the `error:` line the application prints afterwards says what happened, and it is printed on the ordinary screen because `close` ran first. In plain mode everything was already written when it arrived and `close` does nothing.

Rules (decision D8):

- A reporter **never parses**. It receives typed events and the result so far. If it needs something the result does not carry, the result is extended, in `tlaup_parse`.
- A reporter **never decides the exit code** and never raises for a failed run; it reports.
- A reporter holds its own state (what it has printed), not the command.
- **TLC's stderr goes through the reporter** (`stderr_line`), not straight to the console, because a reporter that owns the terminal (O4) has to decide where the line appears. This is the one path; [00](00-overview.md#the-run-pipeline) shows the same.
- **A line of tlaup's own during the run goes through the reporter too** (`notice`), for the same reason. There is one such line in the first wave: the waiting line printed when a first signal is held while TLC writes a checkpoint ([20 G3](20-groundwork.md#g3-java-launcher), [11 R2](11-runner.md#r2-signals)). `run_tlc`'s hook for a held signal calls `reporter.notice(line)`; nothing between `start` and `close` prints through `ui` ([14 F6](14-config-and-cli.md#f6-messages)). A plain reporter writes the line to stderr at once; the layout shows it in the Status panel and copies it to stderr when it closes (O4). A raw run has no reporter and never holds a signal for a checkpoint, so it needs no such path.
- A reporter **prints only through the two consoles of the `Ui` it was given** ([14 F6](14-config-and-cli.md#f6-messages)) and never builds a console on a real stream itself. Those consoles hand a closed pipe back as `BrokenPipeError` instead of exiting, which is what lets the application answer it with 141; a console of the reporter's own would exit with 1 (found by the second check of 2026-11-15). The spools of O4 are consoles on temporary files, which is not a real stream. `handle`, `stderr_line` and `finish` let such an error pass; only `close` holds it back, as above.
- A reporter **says nothing about the run folder**. Whether a folder was kept, and the command to resume, are printed by the command after the reporter is closed (O3, under the mock-up).

Reporters in the first wave:

| Reporter | Used for |
| --- | --- |
| `TerminalReporter` (O3, O4) | Every `tlaup tlc` run without `--raw`. Plain, or the live layout, depending on the streams. |
| `CollectingReporter` | Tests and the Python API: keeps the events, the stderr lines, the notices and the outcome in lists and prints nothing. |

`--raw` uses no reporter. The JSON reporter is milestone 4 and is one more class behind the same protocol; the command chooses a reporter in one function, `make_reporter(ctx, options)`, which is where `--json` will attach. An AI-facing or file reporter (decision D8, after the roadmap) is the same.

The command, after this (signatures as [20 G1](20-groundwork.md#g1-tlc-invocation) and [11](11-runner.md) give them; this sketch shows only where the reporter enters):

```python
def tlc(...):
    request = TlcRequest(...)
    inv = resolve_tlc_invocation(request, ...)      # spec and cfg, then the build, then Java (11 R11)
    java_inv = build_tlc_command(inv)
    if show_command: ...                            # prints the command; no prompt, no install, no folder
    if raw:
        outcome = run_tlc_raw(inv, java_inv, ...)   # 11: passthrough; no reporter
    else:
        outcome = run_tlc(inv, java_inv, make_reporter(ctx, options), ...)
    print_run_notes(outcome, ctx.ui)                # "Checkpoint kept" and the resume command, on stderr (11 R6)
    raise typer.Exit(outcome.exit_code)
```

The command does not enter `run_folder`: `run_tlc` and `run_tlc_raw` do, each for itself ([11 R6](11-runner.md#r6-run-folders), [20 G1](20-groundwork.md#g1-tlc-invocation)). The first revision of this sketch entered it here as well, which would have taken the lock twice.

**Rejected.** A callback taking the whole result on every line (today): the reporter has to work out what is new by comparing lengths, which is the quadratic cost of O7. Reporters as generators or async consumers: nothing here is concurrent. Writing TLC's stderr directly from the launcher: it would draw over the layout.

**Tests.** A unit test drives `run_tlc` with the fake `java` and a `CollectingReporter`, which also records the calls it gets, and asserts the sequence of event types for the `violation` case, that a line the fake writes to stderr arrives through `stderr_line`, and that the calls are `start`, events, `finish`, `close` in that order, `finish` also after an interrupt. With a `java` path that cannot be started, the calls are `start`, `close` and no `finish`, and the error that leaves `run_tlc` is the start error. A test reporter whose `close` sets `write_error` to a `BrokenPipeError` makes `run_tlc` raise it after a run that otherwise succeeded, and not when the middle raised something else. The `TerminalReporter`'s own `close` is tested in O6. With a fake `java` that prints 2195 and waits, a SIGINT sent between 2195 and 2196 makes the waiting line arrive at the `CollectingReporter` as one `notice` call, after the event of 2195, and nothing is written to the `Ui`'s streams while the reporter is open.

**Changelog.** None of its own.

**Depends on.** P3, G1. **Risks.** The event set is a contract between two packages; adding an event is cheap, changing one touches every reporter (two, then three). (Stage 4 review, 2026-11-24: `notice` added for the waiting line, which goes through the reporter, question Q12.)

## O2 Delete dead display code

Roadmap: "Delete display code that nothing in `src/` references (`StatusFooterComponent`, `TlcDisplayComposer`, the `TlcComponent` protocol, `info_dedup`, `_show_diagnostic_info`) and the tests that pin it. Remove the duplicated callback (`cmd/tlc.py:157-238`) and the three copies of the elapsed-time logic."

**Problem.** Display code is in three states today, and only the first is this item's:

1. Referenced by nothing: the roadmap's list.
2. Built but never shown: the layout. `formatter.update(layout, res)` fills a `TlcDisplay` on every line and nothing ever prints it (the triage of 2026-11-15). Decision D40 finishes this layout, so it is not dead code; it is unfinished code, and O4 owns it.
3. Shown today: the trace tree, the SANY error link, the plain statistics rows and the footer line. O3 replaces these.

**Design.** Deleted outright, early ([00, order of work](00-overview.md#order-of-work)), exactly the roadmap's list:

- `tlc/components.py`: `StatusFooterComponent`, `TlcDisplayComposer`, `TlcComponent`.
- `tlc/formatter.py`: the attribute `info_dedup`, which is assigned and never read.
- `cmd/tlc.py`: `_show_diagnostic_info`.

Their tests have gone already, with the rest of the old suite, in the first testing package (decision D62, [01 T11](01-testing.md#t11-the-existing-tests)).

Not deleted here, and where each goes:

| Code | Fate | Where |
| --- | --- | --- |
| `HeaderComponent`, `StatusInfoComponent`, `LogsComponent`, `StatsTableComponent`, `StatusInfoRenderable` | Finished: rewritten against `RunResult` as the four panels of the layout. | O4 |
| `TlcDisplay`, `_Section`, `create_layout`, `update`, `_ensure_layout_structure`, `update_header`, `update_stats`, `update_logs`, `update_clock`, and the two "keep tests happy" calls in `cmd/tlc.py` | Replaced by `render_layout`, built on Rich's own `Layout`. `TlcDisplay` is a hand-made stand-in that grows as sections appear; a full-screen layout has a fixed frame. The nine tests that asserted on the never-rendered structure went with the old suite (D62); the layout's tests are the snapshots of O6. | O4 |
| `LogDeduplicator` | Goes with the rewrite of the log panel: the finished panel shows the same lines plain mode prints, without folding repeats, so that the two modes show one text. | O4 |
| `diff_values`, `render_value_diff` | Kept, rewritten against `Value` and `TraceState`; first real tests. | O3 |
| `render_error_trace` (a Rich tree), `render_sany_error` (a `file://` link and the source excerpt), `StatsTableFormatter` (plain table rows), `StatusFooterRenderable` | Replaced by the plain output of O3, which prints traces as text, diagnostics in editor form and progress as lines. The source excerpt of `render_sany_error` is kept, as the excerpt under the editor-form line ([21 S1](21-other-tools.md#s1-sany), decision D66); only the link and the glyphs go. Deleted in the pull request that lands O3, not earlier, because they are what users see until then. | O3 |
| `render_coverage_table`, `render_inline_coverage` | Kept, rewritten against `CoverageItem`. | O3 |
| `tlc --version` and its callback | A user-visible command. It goes with its replacement, not here. | [13 J3](13-modules-and-java.md#j3-one-java-start), [23 C1](23-command-layout.md#c1-command-tree) |

The duplicated callback and the three copies of the elapsed-time code disappear with O1 and O3: there is one reporter and one function `format_elapsed(seconds)`, in `tlaup/durations.py`, which the "Checkpoint kept" note of [11 R6](11-runner.md#r6-run-folders) uses too, so a duration is written the same way everywhere. (Stage 4 sign-off, 2026-11-24: one function for both, settled with the maintainer at the stage 4 sign-off, 2026-11-24; it is in its own module because the run folders are built before the reporter.)

**Rejected.** Deleting the layout as dead code (the first version of this design): the roadmap item names five things, D3 says to finish the display, and the maintainer confirmed it (D40). Deleting the code users see today (the trace tree, the statistics rows) in the early clean-up step: output would get worse before it gets better.

**Tests.** The suite passes after the deletion. No new test: the item only removes.

**Changelog.** None. Nothing a user can see changes.

**Depends on.** Nothing; it is step 3 of the order of work. **Risks.** A name on the list is referenced after all; mypy and the suite fail in that case, since the project runs mypy in strict mode on `src`. (Stage 4 review, 2026-11-24: the old tests are gone before this item, decision D62; `render_sany_error`'s source excerpt is kept, decision D66.)

## O3 Terminal reporter

Roadmap: "Live terminal reporter: render the layout on a terminal; fall back to plain streamed output when stdout is not a terminal or `--raw` is given." This item is what the reporter says; O4 is the layout. Also carries the milestone 4 item "Editor-style diagnostics in plain output" (decision D22), done here because the reporter is written once; listed as a departure in the README.

**Design.** One class, `TerminalReporter`, with one renderer: `render_event(event, result) -> list[Text]` gives the lines an event adds to the result text, and both modes use it. In plain mode the lines are written to stdout at once. In layout mode (O4) the same lines go to a spool that is copied to stdout when the layout closes, so the result text of a run is the same in both modes. That is the roadmap's "differ only in where they write".

Where each piece goes follows [02 X2](02-cross-cutting.md#x2-stdout-and-stderr) (decision D30). Plain mode, in order of appearance:

```
(stderr)  TLC rolling@bc1b506 (2026.11.15.002146), Java 25.0.5, workers auto
(stderr)  Violation.tla  cfg: Violation.cfg
(stdout)  <the spec's own output lines, as printed, as they arrive>
(stderr)  44 states generated, 44 distinct, 35 on queue, diameter 4          one line per TLC progress message
(stdout)  SanyError.tla:5:18: error: Unknown operator: `undefinedThing'.     SANY and parse diagnostics (D22)
(stdout)       3 | ...                                                       and the source excerpt (D66)
(stdout)  Error: Invariant Small is violated.
(stdout)    The behavior up to this point is:
(stdout)    1: Initial predicate
(stdout)         store = [alpha |-> {}, beta |-> {}, gamma |-> {}]
(stdout)         n = 0
(stdout)         log = <<>>
(stdout)    2: Next  (Violation.tla:10:59)
(stdout)       * store = [alpha |-> {1}, beta |-> {}, gamma |-> {}]
(stdout)       * n = 1
(stdout)       * log = << [ op |-> "add", ...
(stdout)  Warning: ...                                                       TLC warnings
(stdout)  44 states generated, 44 distinct, 35 left on queue; depth 4
(stdout)  Result: errors found (TLC exit code 12: an invariant was violated) in 0.7 s
(stderr)  Checkpoint kept: ...                                               not the reporter's: printed by the command
```

The last line is shown because it is what the user sees next, but no reporter prints it. After the run function has returned, and so after `close`, the command calls `print_run_notes(outcome, ui)`, which writes the note and the resume command to stderr from `outcome.run_folder_kept` and `outcome.resume_command`; a raw run goes through the same call ([11 R6](11-runner.md#r6-run-folders)). When the run ends in an error instead of an outcome, the note travels on the exception (`add_note`) and the application's error handler prints it under the `error:` line ([14 F10](14-config-and-cli.md#f10-no-tracebacks)). The first revision gave the note to the runner in this document and to the reporter in 11; it now has this one owner.

Rules for the content:

- **Header** (stderr): the build from the store, Java's version, workers; then the spec and cfg relative to the working folder. A part that is not known is left out, with no placeholder: with no `--cfg` the second line names the spec alone, because tlaup does not look for `Spec.cfg` ([02 X1](02-cross-cutting.md#x1-exit-codes)) and a rolling build can read a cfg embedded in the spec, so naming one could be wrong; with `-workers` given after `--` (`RunInfo.workers` is `None`) the workers part is left out, and so is Java's version when the Java check did not give one. When TLC's own version line arrives (`VersionSeen`) and differs from what the store says, it is added, as TLC printed it (`ToolInfo.raw`), on stderr. It differs when its revision is not a prefix of the build's commit, or when the build has a CalVer and TLC's version is not that CalVer.
- **The spec's output and unrecognised text** (`OutputLine`) go to stdout exactly as TLC printed them, at once (D9). This includes lines of SANY output the SANY parser did not use ([10 P8](10-parser.md#p8-sany-output)). SANY's own chatter that the parser did use (`Parsing file`, `Semantic processing of module`) produces no event and is not shown in the first wave; milestone 4's `--verbose` is where it would return.
- **A message "as TLC printed it"** means `message.text_lines()` ([10 P4](10-parser.md#p4-framing-and-never-losing-output)) wherever this list says so: the message's lines in order, a nested message's lines in their place among them, with no heading or extra indent of their own. For the nested cases in the captures this is line for line what TLC prints without `-tool`. A message that was cut off (`truncated`) is printed the same way with the lines it has.
- **Unknown messages** (`UnknownMessage`: a code that is not in the table) are printed on stdout as TLC printed them, prefixed by `TLC message <code>:` so the user can report it. A message with an unknown code and severity error or warning arrives as `ErrorOpened` or `WarningFound` and is printed as an error or a warning, with the same prefix.
- **Events that print nothing** in plain mode: `Information` (known information with no typed meaning, for example 2212), `PhaseChanged`, `ModeSeen`, `OverrideLoaded`, `CoverageAdded` and `StatsUpdated` (their content is printed after the run, below), and `CheckpointStarted`, `CheckpointWritten`, `Recovered` and `Finished`. The content of the last four reaches the user elsewhere: `Finished` gives the result line its duration, `Recovered` its `resumed from a checkpoint`, and the two checkpoint messages are TLC's information, hidden as other chatter is (P4, rule 3); the one time a checkpoint matters to the user, a first signal held while it is written, the waiting line says so (O1, `notice`). The layout uses the first three for its status panel (O4). No event is passed over by accident: the reporter's dispatch has a case for every member of `Event`, and mypy's exhaustiveness check fails the build when one is added without a case.
- **Errors, in arrival order.** `ErrorOpened`: `Error: ` and the first line of the message as TLC printed it, further lines indented; the lines of a nested message are among them, in place. Then whatever belongs to the error is printed as it arrives, indented under it: a related message (`ErrorExtended`) as TLC printed its lines, a state (`TraceStateAdded`) as below. TLC's own lead-in ("The behavior up to this point is:", 2121; "The following behavior constitutes a counter-example:", 2264) is such a related message and serves as the heading of the trace; tlaup adds none of its own. In the `assertion-failure` captures the nested-expression positions (2103) arrive after the states, and that is where they are printed. Message and trace are both always shown (P10).
- **Traces**: every state, numbered as TLC numbered them, printed when it arrives. The action name and its location as `File.tla:line:col`, the file taken from `result.module_files`. Each variable on its own line; a variable whose value differs from the previous state is marked with `*`, and on a colour terminal the changed part is highlighted using the value diff. A value that is `raw` is printed as TLC printed it and compared as text. A multi-line value is printed as TLC wrapped it. On `TraceClosed` a liveness trace gets its last line, `Back to state <n>` or `Stuttering`; for any other trace the event prints nothing.
  A `-difftrace` run is printed the same way (top-up): the parser has filled in the variables TLC left out ([10 P5](10-parser.md#p5-error-traces)), so every state is shown whole and the marks are right; the first design's `show_states_as_printed` goes.
- **Diagnostics** in the editor form of [21 S1](21-other-tools.md#s1-sany), each followed by the source excerpt S1 describes, made by the same function as for `tlaup sany` (decision D66): the two lines before, the line with `^` under the columns, `Error here: line L, col A to B`, and the two lines after. The file is the one the editor-form line names; when it cannot be read there is no excerpt. This replaces the `file://...#L` links of `render_sany_error` and keeps its excerpt. The excerpt is in the result text of both modes and never in the JSON of milestone 4, which carries the file, line and column ([40](40-later-milestones.md#milestone-4-automation-surface)).
- **Warnings**: `Warning: ` and the text. The garbage-collector advice (2401) is shown like any other; with the default JVM options it does not occur.
- **Progress** (stderr, plain mode): one line per TLC progress message, as it arrives, numbers with thousands separators; a count TLC gives as -1 (the queue in a simulation, [10 P3](10-parser.md#p3-result-model)) is left out of the line. Nothing is held back or rate-limited: a line that depends on the clock would make expected files depend on timing. TLC spaces them itself (top-up, [research 31](../research/31-progress-and-closed-stdout.md)): one about 3 seconds after the initial states, then one every 60 seconds, measured on both builds, plain and `-tool`; in simulation one every 60 seconds from the start. A checkpoint or a slow state can delay a line (research 34 saw 12 minutes), never bring it forward. Only a user who passes `-Dtlc2.TLC.progressInterval=N` on rolling gets them faster, which is their choice. So no spacing of tlaup's own is added.
- **Statistics and coverage** after the run: the final counts; the coverage table and the inline coverage of the spec when `--coverage` was given.
- **Result line** (top-up, decision D54): the words of the verdict ([10 P3](10-parser.md#p3-result-model)), then TLC's code and its meaning from `describe_exit_status` ([02 X1](02-cross-cutting.md#x1-exit-codes)) beside them, not in their place, and the duration from TLC's own "Finished in" (falling back to the reporter's clock) written by `format_elapsed` (O2): below ten seconds with one decimal (`0.7 s`, `4.2 s`), below a minute in whole seconds (`45 s`), below an hour as minutes and two-digit seconds (`1 min 00 s`, `2 min 13 s`), and from an hour on as hours and two-digit minutes (`1 h 02 min`, `2 h 13 min`):

  | Verdict | Result line |
  | --- | --- |
  | `errors` | `Result: errors found (TLC exit code 12: an invariant was violated) in 0.7 s` |
  | `no-error` | `Result: no error found, every state checked (TLC exit code 0) in 4.2 s` |
  | `no-error-bounded` | `Result: no error found in a bounded search (simulation) (TLC exit code 0) in 1 min 00 s`; `depth-first` for a `-dfid` run |
  | `not-checked` | `Result: not checked: the spec has errors (TLC exit code 150: ...)`, by the first error's kind: `parse`, or no error and a SANY diagnostic of severity `error`, `the spec has errors`; `config`, `the configuration has errors`; `usage`, `TLC refused its arguments`; `exception` or `other` opened before the initial states, `TLC failed before computing the initial states` |
  | `incomplete` | `Result: incomplete, interrupted after 2 min 13 s`; `incomplete, TLC stopped without finishing (TLC exit code 255: ...)`; `incomplete, stopped because the output was closed` |

  A resumed run adds `; resumed from a checkpoint`, and `, state counts approximate` when `counts_approximate` is set; the statistics line then writes its numbers as `about 1,771,600`. A checkpoint that was not kept (`RunOutcome.dropped_checkpoint`, [11 R6](11-runner.md#r6-run-folders)) adds `; a checkpoint was not kept (use --keep to keep one)`, `; the checkpoint was incomplete, nothing to resume`, or `; a -dfid run cannot be resumed` (its checkpoint holds no queue; review finding TU7). One exception about the code's meaning: rolling returns 10 for a false postcondition (research 15), the manifest's meaning for 10 is "assumption failure", and that would be wrong here, so when the code is 10 and the first error's kind is `postcondition` the parenthesis reads `(TLC exit code 10: a postcondition was false)`. Why the verdict and not the code: research 22 captured TLC exiting 0 after two invariant violations (`-deadlock -continue`), so a result line built from the code would print a success for a run that found errors. When the code and the verdict disagree, the warning that names both (P3) is printed on stderr by `print_run_notes` after the reporter has closed, not by the reporter.
- **Override hint** ([11 R7](11-runner.md#r7-override-modules-that-do-not-load)), a `hint:` line on stderr, as tlaup's own hints are ([02 X2](02-cross-cutting.md#x2-stdout-and-stderr)), written when the error opens, only when the run has override classes (`RunInfo.override_classes` is not empty), after an error of kind `exception` that happened before the initial states and has no nested message whose code has kind `config` in the code table (5006). The last condition is there because v1.7.4's `postcondition-false` capture has the same outer shape (1000 before the initial states) and is a cfg error, not an override problem; since the top-up rule of P5 such an error already has kind `config`, and the condition stays as a second guard. "Before the initial states" means the phase was still `STARTING` when the error opened. An error with code 2173 always gets the hint, in the specific form R7 gives when its text names the class-file versions.
- **TLC's stderr** (`stderr_line`) goes to stderr unchanged, at once in plain mode. In layout mode it is shown in the Output panel when it arrives and reaches the real stderr when the layout closes (O4).
- Everything from outside tlaup is printed as text, never as markup (P11).
- Widths: nothing in the result text is truncated or wrapped by tlaup; a long value is TLC's to wrap. Only the panels of the layout cut lines to fit (O4).

**Rejected.** The tree widgets of the current `render_error_trace`: they draw box characters and re-indent values, which fights TLC's own wrapping and reads badly when piped. Printing the trace only at the end, or the related messages before the states regardless of arrival (the first version of this design): a long trace would appear after a delay, and the reporter would have to hold an error back until it knew nothing more belonged to it. A heading of tlaup's own with the state count (`Trace (4 states):`): the count is not known when the first state arrives. Hiding progress in plain mode: a CI log is where it is wanted.

**Tests.** O6.

**Changelog.** Changed: "The output of `tlaup tlc` is reorganised: a header naming the build and Java; the spec's own output; each error with its message and full trace, changed variables marked; SANY and parse errors as `path:line:col: error: message` (was a `file://` link), still followed by the lines of the spec around the error, now with `^` under the columns; a final result line with the meaning of TLC's exit code. Results are on stdout, progress on stderr." This is one of the two large user-visible changes of the release, with the command layout.

**Depends on.** O1, P3 to P11, X1, X2. **Risks.** Layout of the text is taste; the expected files make every change to it visible in review. The diff highlight inside a changed value is the least certain part: if it reads badly on real traces it is cut down to the `*` mark. The postcondition exception to the result word is one special case in a table-driven line; a second such case would be a sign the word should come from the error, not the code. (Stage 4 review, 2026-11-24: the four checkpoint, recovery and finish events print nothing, the header leaves out what is not known, the hint's stream and the words for `not-checked` after an early exception, question Q11; the source excerpt under the editor-form line, decision D66.)

## O4 Live display

Roadmap: "Live terminal reporter: render the layout on a terminal; fall back to plain streamed output when stdout is not a terminal or `--raw` is given", and the exit criterion "a long TLC run shows a live status on a terminal and clean line output when piped". Decision D3: finish it, as one reporter among several. Decision D40 (2026-11-15): the full-screen layout, not a footer.

**Problem.** The layout exists in pieces and is never shown. `cmd/tlc.py` builds it, updates it on every line, and renders only a one-line footer through `Live`; the header, status, log and statistics panels are computed and thrown away. What is on screen during a run today is the footer plus plain table rows printed above it.

**Design.**

*When it is on.* Both stdout and stderr are terminals, `TERM` is not `dumb`, the terminal has at least 60 columns and 15 lines, `--raw` was not given, and plain output was not asked for (below). In every other case output is plain (O3). This is the roadmap's condition with D30 applied: the layout is a live status, so it is drawn on **stderr**, but it also takes over the screen the result would scroll on, so it needs stdout to be the terminal too. With stdout redirected, `tlaup tlc Spec > out.txt` shows plain progress lines on the terminal and writes the result to the file. The size is the stderr console's, read once, at `start`; a terminal that is too small gets plain output for the whole run. Rich takes `COLUMNS` and `LINES` over the terminal's own size when they are set (tried), which is the user's way to override it and the reason the pty steps of the tests remove both variables.

*Asking for plain output.* `tlaup tlc --plain` gives plain output on a terminal, as if a stream were redirected: no alternate screen, every line written when it arrives, the full text of a long trace in the scrollback as it is printed. The default comes from the setting `tlc.plain` (false), so `TLAUP_TLC_PLAIN=1` or `tlc.plain: true` in the user's file makes it the habit ([14 F1](14-config-and-cli.md#f1-layered-configuration)); there is no `--no-plain`, since the setting is the way to change the default and a flag that turns the layout on where the rule above says no would draw it where it does not fit. With `--raw` it has no effect, as no reporter runs; the help says so. Added at the stage 3 sign-off, 2026-11-18, which settled the question this design had left for the review of the command tree.

*What it shows.* The terminal's alternate screen, filled by four panels, the ones the existing code sketched:

```
 TLC rolling@bc1b506 (2026.11.15.002146), Java 25.0.5, workers auto            header, 2 lines
 Violation.tla  cfg: Violation.cfg
 ── Status ────────────────────────────────────────────────────────────────    status, 4 lines
 Checking            elapsed 00:02:13            errors 0   warnings 1
 1,581,826 states generated, 537,890 distinct, 10,473 on queue, diameter 148
 Ctrl-C to interrupt
 ── State space progress ───────────────────────────────────────────────────    progress, up to a third of the height
 Time                  Diameter      Generated       Distinct        Queue
 2026-11-14 22:26:59         96        912,004        301,220       18,113
 2026-11-14 22:27:59        148      1,581,826        537,890       10,473
 ── Output ─────────────────────────────────────────────────────────────────    output, the rest of the screen
 <the newest lines of the result text: the spec's output, diagnostics, errors, traces>
```

- **Header**: the two header lines of plain mode.
- **Status**: the phase (`Starting` before TLC has reported a phase, for `NOT_STARTED` and `STARTING` of [10 P3](10-parser.md#p3-result-model), settled with the maintainer on 2026-11-24; then `Parsing`, `Computing initial states`, `Checking`, `Checking liveness`, `Finished`, or `Interrupted` when `finish` gets an outcome whose run was stopped by a signal), the time since `start` from the reporter's clock as `HH:MM:SS`, the number of errors and warnings so far, the latest progress numbers, and the hint. While a first signal is held for a checkpoint, the waiting line that arrives through `notice` (O1), in the wording [20 G3](20-groundwork.md#g3-java-launcher) gives for each signal, stands in the hint's place.
- **State space progress**: one row per TLC progress message, the newest that fit.
- **Output**: the newest lines of the result text, the same lines plain mode writes to stdout, produced by the same `render_event`; and TLC's stderr lines, marked `stderr:`. Lines longer than the panel are cut with an ellipsis here, and only here; the full line is in the spool.

*How it is built.*

```python
# tlaup/reporters/layout.py
@dataclass(frozen=True)
class LayoutView:                       # everything a frame needs; replaced whole on each event
    run: RunInfo
    phase: Phase
    started_at: float                   # reporter's clock
    errors: int
    warnings: int
    progress: tuple[Progress, ...]      # newest 50
    tail: tuple[Text, ...]              # newest 200 lines of the result text and of TLC's stderr
    notice: str | None = None           # the waiting line (O1), shown in place of the hint

def render_layout(view: LayoutView, now: float, width: int, height: int) -> RenderableType
```

- `render_layout` is a pure function that returns a Rich `Layout` with the four panels. It is what the snapshot tests call (O6).
- The reporter holds one `LayoutView` and replaces it on each event. A Rich `Live(console=<stderr console>, screen=True, get_renderable=..., refresh_per_second=1 / interval)` redraws from its own refresh thread; the thread only reads the current view and the clock, so the elapsed time ticks when TLC is silent and no lock is needed. `interval` is O5's.
- `Live` is created with `redirect_stdout=False` and `redirect_stderr=False`: nothing prints to either stream while the layout is up (next point), so there is nothing to redirect.

*Where the result text goes meanwhile* (decision D9: nothing is lost). While the layout is up the reporter writes the result text into a spool instead of stdout: a console with stdout's width and colour setting that writes to a `tempfile.SpooledTemporaryFile` (held in memory up to 1 MiB, then on disk). TLC's stderr lines go to a second spool. Both also feed the `tail` of the view. So every line, including every line the spec printed with `Print`, is on screen in the Output panel when it arrives and is kept in full.

*What goes to which stream while the layout is up.* Nothing reaches the real stdout or stderr between the opening of the layout and its closing, apart from the frames themselves, which `Live` draws on stderr:

| Text | During the run | When the layout closes |
| --- | --- | --- |
| The header (two lines) | Written to stderr by `start`, before the layout opens; also the header panel. | Already in the scrollback. |
| The result text | Output panel, and the stdout spool. | Copied to stdout. |
| TLC's stderr lines | Output panel, marked `stderr:`, and the stderr spool. | Copied to stderr, unmarked, before the result text. |
| A line of the reporter's own that plain mode writes to stderr after the header (TLC's version when it differs from the store's) | Header panel, and the stderr spool, in arrival order with TLC's stderr lines. | Copied to stderr with them. |
| The waiting line (`notice`, O1) | Status panel, in place of the hint, and the stderr spool, in arrival order with the lines above. | Copied to stderr with them. |
| Progress | Status and progress panels. | Not printed; the final counts are in the statistics. |

So in the scrollback TLC's stderr lines stand together above the result text, not at the places where they arrived; the two streams cannot be interleaved again once they are two spools, and a user who redirects one of them gets plain mode, where each line is written when it arrives.

*When the run ends.* `finish` writes the statistics, the coverage and the result line into the stdout spool, like the rest of the result text, refreshes once (so the last frame is complete and shows the phase `Finished`, or `Interrupted` for a run a signal stopped; Rich does not refresh on stop when it is on the alternate screen), and calls `close`. `close` stops `Live`, which leaves the alternate screen, then copies the stderr spool to stderr and the stdout spool to stdout, and deletes the spools. What stays in the scrollback is therefore the header, TLC's stderr lines if any, and the complete result text: byte for byte what `tlaup tlc Spec > out.txt` would have put in the file.

*When the run does not end* (`close` without `finish`, O1): the same three steps of `close`, with whatever the spools hold. The layout is gone before anything else is printed, so the `error:` line that follows is on the ordinary screen under the output received so far. This was the gap the second check of 2026-11-15 found: with only `finish`, an error raised while the layout was up was drawn into the alternate screen and lost with it, and the spooled text was never printed.

*Who may print.* Between `start` and `close` the reporter owns the terminal, and nothing else prints through `tlaup.ui` in that time. The preflight's warnings come before `start`. The one line tlaup itself has to say during the run, the waiting line of a held signal, goes through the reporter's `notice` (O1). The command's notes ("Checkpoint kept", O3) and the application's `error:` line come after `close`, because `run_tlc` calls `close` in a `finally` before it returns or lets an exception out ([11](11-runner.md)).

*Leaving the alternate screen in every case.* `close` runs on every path out of `run_tlc`: a normal end, one or two Ctrl-Cs, SIGTERM ([11 R2](11-runner.md#r2-signals)), and any exception. It stops `Live` first and only then writes, and a failed write in it is held back (O1), so nothing in `close` can leave the terminal on the alternate screen. As a second line of defence the reporter registers an `atexit` hook at `start` that stops `Live` if it is still running, for a caller other than `run_tlc` that forgets `close`; `close` removes the hook.

**Interfaces.** `TerminalReporter(ui, *, mode: Literal["plain", "layout"], interval: float, clock: Callable[[], float], refresh_thread: bool = True)`. `make_reporter` picks `mode` by the rule above, with `settings.tlc.plain` (the flag already merged into it) as one of its inputs. The `Live` is built on `ui`'s stderr console and the result text is written to `ui`'s stdout console; the reporter has no other way to reach a stream. `refresh_thread=False` is for tests: they call `reporter.refresh()` themselves.

**Rejected.**

- *A one-line footer on stderr with everything else scrolling above it* (the first version of this design). It keeps the scrollback during the run and works with stdout redirected. The maintainer chose the roadmap's full-screen layout (D40); the spool gives back the scrollback at the end, and plain progress lines cover the redirected case.
- *Drawing the layout on stdout.* Decision D30 puts the live status on stderr.
- *The layout without the alternate screen*, redrawn in place: it would scroll the scrollback away as panels grow and leave a half-drawn frame behind on an interrupt.
- *Printing the result text only from `RunResult` at the end* instead of a spool: the result keeps the newest 10,000 output lines (O7) and does not keep the order between output lines and errors, so the text would differ from a redirected run.
- *Keys for scrolling the Output panel*: needs stdin in raw mode, which fights Ctrl-C handling and piped input. The scrollback after the run is where the full text is read.
- *A progress bar*: TLC does not know the total.

**Tests.** Three kinds, and each catches something the others cannot.

*What a frame looks like* is snapshot-tested without a terminal (O6).

*Which stream gets what* is tested in-process (O6, "the two streams"): a reporter in layout mode on two in-memory consoles forced to terminal mode. How a test forces that is in O6 ("Drawing without a terminal"): two arguments of `Ui` and `TERM` set by the test. One pty cannot show it, since both streams end on the same screen.

*That the display is really drawn, live, on a real terminal* is tested through a pty, as real processes ([01 T5](01-testing.md#t5-feature-files-and-steps)). The pty steps set `TERM=xterm-256color` and the window size, and remove `COLUMNS` and `LINES` from the child's environment: the isolation fixture sets `TERM=dumb`, which would switch the layout off, and `COLUMNS=100` and `LINES=40`, which Rich would take instead of the pty's size, so that the "too small" scenario below would draw the layout and pass or fail for the wrong reason. `tlc_live.feature`:

- **The last frame and the scrollback.** Both streams on a pty of 100 by 30: the bytes written to the terminal contain the enter-alternate-screen sequence, then frames, then the leave sequence. The step `the terminal showed the layout` replays the bytes between the two sequences through a terminal emulator (`pyte`, a new development dependency; it does not model the alternate screen, which is why the stream is cut at the two sequences) and asserts three things only: the enter sequence was written, at least one screen between the two sequences had the four panel titles, and the leave sequence was written. It says nothing about how the run ended, so it holds for an interrupted run too. This scenario then asserts the end separately, with `the last layout frame contains "Finished"` and the same step for the final counts; that step reads the last screen before the leave sequence. The step `the terminal ends with the expected file` replays the bytes after the leave sequence and compares the screen text with the plain expected output.
- **The display updates while TLC is silent.** This is the scenario that fails when the refresh thread is dead, which no other test notices, because every other test either calls `refresh()` itself or looks only at the last frame, which `finish` draws. The fake `java` replays the v1.7.4 `big-states` case (53 lines) with `java pauses 20 ms between lines` and `java hangs after line 31`: line 26 starts message 2190, which ends the initial states and sets the phase `Checking`, and lines 29 to 31 are the first progress message, so the fake falls silent about 0.6 seconds in, with the phase `Checking` and one progress row on the screen. The When step starts `tlaup tlc Big --refresh-interval 0.2` on a pty of 100 by 30, feeds the emulator as bytes arrive, waits until the screen has shown `Checking` (a frame from the middle of the run), remembers the `elapsed` value on that screen, waits until a screen shows `Checking` with an `elapsed` value at least two seconds later (a later frame, which only the refresh thread can have drawn: the fake has been silent since it hung, so no event caused it), and then presses Ctrl-C. The step is `press Ctrl-C once the terminal has shown "Checking" and then an elapsed time 2 seconds later` ([01 T5](01-testing.md#t5-feature-files-and-steps)); comparing two values read from the screen, not a literal `00:00:02`, is what keeps it true on a slow runner where `Checking` first appears late. Then: the exit code is 130, the terminal showed the layout, the last layout frame contains `Interrupted` (`finish` is reached after a signal, and draws the last frame with that phase), and the terminal ends with the result line of an interrupted run, which starts `Result: incomplete, interrupted after` (O3's table). Each wait has a timeout of ten seconds and fails with the last screen it saw. The scenario runs for about three seconds of real time and is the one test in the suite that depends on the real clock ([01 T12](01-testing.md#t12-rules-for-writing-tests), rule 5 names it as the exception); the interval it passes is 0.2 seconds so that a display stuck at one frame per event cannot pass by luck.
- **Stdout redirected.** The same run on a pty with stdout redirected to a file: no alternate-screen sequence appears, the terminal has the header and plain progress lines, and the file equals the plain expected stdout and holds no escape sequences.
- **Too small.** A pty of 50 by 10: plain output, `the terminal stayed on the main screen`.
- **Plain asked for.** A pty of 100 by 30 with `--plain`: `the terminal stayed on the main screen`, and the terminal has the header and plain progress lines. The same with `TLAUP_TLC_PLAIN=1` and no flag. With `--raw --plain` the run is a raw run (exit code and the raw stdout). That `make_reporter` picks plain mode for each way of asking is also a unit test, with no pty.

An error raised while the layout is up has no pty scenario: with the fake `java` every way to make `run_tlc` fail after `start` fails the preflight first, and a step that reached into the process would be a seam. It is a unit test (O6, `close`), where `run_tlc` is given a command that cannot be started.

`pyte` follows what Rich draws (top-up, [research 30](../research/30-library-behaviours.md)): `pyte` 0.8.2 on a 100 by 30 pty showed the four panel titles on one screen, 12 to 14 distinct frames from the refresh thread in 1.5 seconds, the last frame, the `…` of a cut line and the plain text after the leave sequence, with Rich 13.8.0 to 15.0.0, on Linux and on macOS. Cutting the stream at the two sequences works as these steps assume, and the fallback the first design held in reserve is not needed. Colours are compared with `pyte`'s names in mind: bold green is `brightgreen`. Windows has no pty, as [01 T5](01-testing.md#t5-feature-files-and-steps) says.

**Changelog.** Added: "On a terminal `tlaup tlc` shows a full-screen live view while TLC runs: the build and spec, the current phase and elapsed time, the state-space progress table and the newest output. When the run ends the view closes and the complete result is printed, so it stays in the scrollback. When output is redirected or piped, output is plain as before; `--plain`, or the setting `tlc.plain`, gives plain output on a terminal too."

**Depends on.** O1, O3, X2, R2. **Risks.**

- A process killed with SIGKILL, or a crash of the interpreter, leaves the terminal on the alternate screen and loses the spools; the lines were on screen when they arrived, and `reset` restores the terminal. Not avoidable from inside the process.
- A run that prints gigabytes writes them twice, once to the spool and once to stdout at the end. Accepted: such a run is normally redirected, which is plain mode.
- During the run the full text of a long trace is only visible as the tail that fits the Output panel. A user who wants the whole text as it arrives asks for plain output with `--plain` (above).
- The refresh thread reads a value another thread replaces. Replacing one reference to a frozen value is safe in CPython; the code must not mutate a view in place.
- Rich's behaviour on the alternate screen was tried on a real pty with five versions from 13.8.0 to 15.0.0 on Linux and four of them on macOS (research 30); resizing while the layout is up and a Windows console were not. The cap below 14 is gone ([30 B2](30-ci-and-release.md#b2-build-fixes)); the newest-dependencies job and the pty scenarios guard a later change.
- The layout can be idle for up to a minute between progress rows (research 31), and longer while TLC writes a checkpoint or computes a slow state. The elapsed time ticks from the refresh thread, so a silence never reads as a hang.
- The stderr lines of the tool lose their place among the output lines in the scrollback (the table above). During the run the Output panel shows them where they arrived. (Stage 4 review, 2026-11-24: the waiting line is shown in the Status panel and copied to stderr on close, question Q12; the interrupted scenario asserts O3's wording of the result line, index Clerical; the phase word `Starting`, finding E4, settled with the maintainer on 2026-11-24.)

## O5 Refresh interval

Roadmap: "Make `--refresh-interval` and the matching config key take effect."

**Problem.** The option is declared and never read (`cmd/tlc.py:85`); `Live` is created with `refresh_per_second=4`.

**Design.** `--refresh-interval SECONDS`, default from `tlc.refresh_interval` (1.0), is how often the layout is redrawn, which is also how often the elapsed time ticks. A value below 0.1 or above 60 is a usage error. It has no effect in plain mode, where each progress line is printed when TLC sends it, and none with `--raw`; the help says so.

**Rejected.** Using it also as a minimum time between progress lines in plain mode (the first version of this design): the lines would then depend on the real clock in feature runs, and TLC spaces them itself (a minute apart, measured by research 31; O3). Changing how often TLC itself reports: that is a TLC setting, not tlaup's; whoever wants it passes it through `--java-opt` or after `--`.

**Tests.** Today's defect is that the value never reaches `Live`, so the test has to look at the `Live` object and not at a copy the reporter keeps (the first revision asserted on the reporter's own attribute, which passes with the defect in place). A reporter unit test in layout mode, on in-memory consoles, started with `interval=0.5` and then with `interval=2`: `reporter.live.refresh_per_second` is 2 and then 0.5 (the reporter keeps its `Live` in a public attribute for this). That is a public attribute of Rich's `Live` holding the constructor's argument (tried on the locked Rich), and this is the one place a test reads a Rich object; O6's rule against Rich internals stands for everything else. With `refresh_thread=False` and an injected clock, two calls of `refresh()` one clock-second apart show elapsed times one second apart. That the thread really redraws at an interval is the pty scenario of O4. A feature (in-process) asserts that `--refresh-interval 0` and `--refresh-interval 100` each exit 2, and that the same two values exit 2 when they come from the environment variable and from the config key with no option given, which shows that each source reaches the option.

**Changelog.** Fixed: "`--refresh-interval` and `tlc.refresh_interval` had no effect. They now set how often the live view is redrawn."

**Depends on.** O4, F1. **Risks.** None of its own.

## O6 Snapshot tests

Roadmap: "Snapshot tests through a fixed-width, colourless console with an injected clock, replacing assertions on Rich internals."

**Design.** `tests/unit/reporters/test_terminal.py` and `test_layout.py`. These drive a reporter directly with events, which [01 T12](01-testing.md#t12-rules-for-writing-tests) rule 1 lists as a boundary of its own.

- A helper replays a golden case through the real `TlcParser` into a `TerminalReporter` given a `Ui` built on two `StringIO` streams, at width 100 with colour off, with a clock that advances one second per event, and a fixed `RunInfo`. The two captured streams are compared with expected files ([01 T8](01-testing.md#t8-expected-output-files)): `expected/terminal/<build>/<case>.stdout.txt` and `.stderr.txt`.
- **Drawing without a terminal.** The layout tests below need consoles that behave as terminals of a known size although their streams are `StringIO`. `Ui` takes two keyword arguments for this, `terminal: bool | None = None` and `size: tuple[int, int] | None = None`, which it passes to both consoles as Rich's public `force_terminal`, `width` and `height` ([14 F6](14-config-and-cli.md#f6-messages)); the helper builds its `Ui` with `terminal=True, size=(100, 30)`. That is not enough by itself: the isolation fixture sets `TERM=dumb` ([01 T2](01-testing.md#t2-isolation)), and under it Rich's `Live` on such a console writes no alternate-screen sequence and no frame at all, so these tests also set `TERM=xterm-256color` with `monkeypatch.setenv`. Tried on the locked Rich 13.9.4, in memory, by the third reviewer and again by the design agent: a console with `force_terminal=True, width=100, height=30` and a `Live` on the alternate screen wrote 1 enter sequence, 1 leave sequence and 4 frames with `TERM=xterm-256color`, and 0, 0 and 0 with `TERM=dumb`. The tests named "layout mode" below, and the layout test of O7, all do both things; the plain-mode tests do neither.
- **Plain mode**: every golden case of both builds.
- **Layout frames**: for `success`, `violation` and `big-states`, `render_layout` is called on the reporter's view at three points (after `start`, after half the events, after the last event) and each frame is printed to a `StringIO` console of 100 by 30, colour off, and compared with `expected/layout/<case>-<n>.txt`. One frame at 60 by 15, the smallest size the layout accepts.
- **The two modes give one text**: for the same three cases a reporter in layout mode (`refresh_thread=False`, consoles on `StringIO` forced to terminal mode) is run to `finish`, and what it wrote to stdout is compared with the *plain* expected stdout file of that case. No second expected file exists for it.
- **The two streams** (decisions D30 and D40: the layout on stderr, the result on stdout). In the same runs: the stdout stream holds no escape sequence at all and nothing before `close`; the stderr stream holds the enter and leave sequences of the alternate screen, each once, with the panel titles between them, and after the leave sequence the tool's stderr lines and nothing of the result text. With a case whose fake stderr has two lines, they stand in the stderr stream after the leave sequence, in order, unmarked.
- **`close`**, in layout mode on the same consoles: called after `start` and a few events with no `finish`, it writes the leave sequence, then the result text received so far to stdout, and no result line; called a second time, and called on a reporter that was never started, it writes nothing. With a `start` made to fail after the spools exist and before the display starts (the stderr console's stream raises on the first write of the enter sequence), `close` returns, no spool file is left in the temporary folder, and no leave sequence is written. With a stdout console whose stream raises `BrokenPipeError` on write, `close` returns, the leave sequence is in the stderr stream, and `write_error` is that error. Through `run_tlc`, with a Java command whose executable does not exist: the leave sequence is in the stderr stream when the start error leaves `run_tlc`, which is the order that puts the `error:` line on the ordinary screen.
- One plain case with colour on and one at width 40, for `violation`.
- The markup test of [10 P11](10-parser.md#p11-tlc-text-and-rich-markup), in both modes: the Output panel must not interpret markup either.
- **The source excerpt** (D66): the replay helper maps the capture's folder in SANY's `Parsing file` lines to the case's folder under `golden/specs/`, so the reporter reads the spec as in a real run, and the plain expected stdout of `sany-semantic-error` and `parse-error` holds the excerpt under the editor-form line, on both builds. The same replay with the folder not mapped gives the editor-form line alone. The excerpt's own rules are the unit test of [21 S1](21-other-tools.md#s1-sany).
- **The waiting line** (O1): in layout mode a `notice` shows the line in the Status panel of the next frame, in place of the hint, and after the leave sequence it is in the stderr stream with the tool's stderr lines; in plain mode it is on stderr at once and stdout has nothing of it.

No test reads `_cells`, `renderables` or any other Rich attribute, with the one exception O5 names. The expected files are what a reviewer reads to judge the output. The nine tests that asserted on the structure of the never-rendered `TlcDisplay` went with the old suite (D62).

**Rejected.** Comparing the bytes `Live` writes in the unit tests: they hold cursor movement that changes with Rich's version; the pty scenarios of O4 look at real terminal output, a few times, and the frames are compared as text here.

**Changelog.** None. **Depends on.** O3, O4, T8. **Risks.** Frame files change whenever the layout is adjusted; that is their purpose. (Stage 4 review, 2026-11-24: tests for the source excerpt, decision D66, and for the waiting line, question Q12; the old layout tests went with the old suite, decision D62.)

## O7 Rendering cost and memory

Roadmap: "Fix the per-line re-rendering cost, which grows with the square of the output, and the unbounded list of output lines kept in memory."

**Problem.** For every output line the callback slices `res.output_lines[printed:]`; the parser appends every line to a list that is never trimmed; the layout's log panel walks the whole list on every update to fold repeats.

**Design.** Both are removed by the shape, not tuned:

- The reporter is driven by events. Each line is handled once, when it arrives; nothing is re-scanned.
- `RunResult.output` keeps the newest `max_output_lines` (10,000) and counts the rest in `output_dropped` ([10 P3](10-parser.md#p3-result-model)). In plain mode the reporter has already printed every line from the `OutputLine` events; in layout mode it has written every line to the spool, which holds at most 1 MiB in memory and the rest in a temporary file. So nothing is lost (D9) and memory stays bounded in both modes. `progress` keeps one entry per TLC progress message. At one a minute, measured by research 31, that is small; only a user who passes `-Dtlc2.TLC.progressInterval` on rolling gets more, and if that ever matters the list gets the same cap-and-count treatment as `output`.
- The layout is redrawn at the refresh interval, from a view that holds the newest 200 lines and 50 progress rows, so a frame costs the same whatever the amount of output.

**Rejected.** Raising or removing the cap on `RunResult.output` so the layout could reprint from it: unbounded again. Redrawing the layout on every event: the cost per line would be a whole frame.

**Tests.** A unit test replays a synthetic stream of 300,000 `OutputLine` events through a `TerminalReporter` in plain mode writing to a null stream and asserts the result's `output` has 10,000 entries and `output_dropped` 290,000. A second test counts calls: the number of write calls is linear in the number of lines (checked for 1,000 and 10,000). In layout mode with `refresh_thread=False` (a `Ui` with `terminal=True, size=(100, 30)` and `TERM=xterm-256color` set by the test, as O6 says under "Drawing without a terminal"), the same stream leaves a view whose `tail` has 200 lines, `render_layout` is called only by the test's own two `refresh()` calls, and the stdout written when the reporter closes has 300,000 lines. No test measures time.

**Changelog.** Fixed: "Runs with a lot of printed output became slower and slower and used more and more memory."

**Depends on.** O1, O4, P3. **Risks.** The temporary file of a very long run can fill the temporary folder; the write error is reported like any other failed write ([14 F10](14-config-and-cli.md#f10-no-tracebacks)) and the run's own exit code is kept.
