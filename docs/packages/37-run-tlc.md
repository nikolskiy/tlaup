# 37. The run functions: `run_tlc` and `run_tlc_raw`

Size: M. Suggested model: most capable. Status: ready. Two points are open in the index and do not hold this package back: the real-process deferral scenarios (question "checkpoint signal steps", 39's), and where the waiting line goes once the live layout exists (question "waiting line under the layout", 40's).

## Goal

The frame at the top of [11](../design/11-runner.md) exists as two functions, `run_tlc` (launcher, parser, reporter) and `run_tlc_raw` (passthrough), with `RunOutcome`, beside the old runner. They hold the signal handlers and the run folder for the whole run, settle the folder on every way out, carry the "Checkpoint kept" note on the outcome or on the exception, and are tested with the fake `java` and a `CollectingReporter`. [39](39-tlc-command.md) receives them working and switches `tlaup tlc` onto them.

## Covers

- Roadmap items:
  - "Report run errors as what they are. Today every `OSError` during a run, including a broken pipe from `--raw | head`, becomes \"'java' not found\"." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust), line 169). In part: the frame's way out for every error (settle, close the reporter, the note, the reporter's write error) and `stopped_for_closed_pipe` on the outcome. The launcher's part is [21](21-java-launcher.md), the handler's [17](17-error-handler.md), the command and its scenarios [39](39-tlc-command.md).
  - "Forward SIGTERM to the JVM so a CI timeout does not leave TLC running; exit 130 on Ctrl-C; survive a second Ctrl-C while draining output." (line 173). In part: the handlers held round the whole run, a signal before the child, `INTERRUPTED`, telling the launcher about 2195 and 2196, the waiting line, the two exact-moment tests. The mechanism is 21's, the scenarios 39's.
  - "Do not crash on non-UTF-8 bytes in TLC output." (line 175). In part: a run with invalid bytes completes and its result is intact. Decoding is 21's, the path warning [33](33-tlc-invocation.md)'s, tlaup's own streams [16](16-ui-messages.md)'s, the scenarios 39's.
  - "A single TLC invocation value ... One process loop instead of two copies. SANY errors in the result are typed and are filled in on the Ctrl-C path too." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 283). In part: the one process loop, and the parser closed on every run that has an outcome, so SANY's diagnostics are in the result after a signal too. The value is 33's.
- Design sections:
  - [11](../design/11-runner.md), the frame and the three rules under it: all of it, and `RunOutcome`.
  - [11 R1](../design/11-runner.md#r1-run-errors-reported-as-what-they-are), [R2](../design/11-runner.md#r2-signals), [R3](../design/11-runner.md#r3-non-utf-8-output): the runner's side; the line to the launcher is drawn under Context, as 21 draws it.
  - [11 R6](../design/11-runner.md#r6-run-folders): "Unit, the frame" and the frame's parts of "The note", "Kept folders are visible" (the reminder) and "A resumed run's counts" (`counts_approximate`). Everything else of R6 is [35](35-run-folders.md).
  - [20 G1](../design/20-groundwork.md#g1-tlc-invocation): `run_tlc` owns the one process loop and the one `TlcParser`. [20 G3](../design/20-groundwork.md#g3-java-launcher), Tests: the two tests that drive `run_tlc` with a signal at an exact moment, and the waiting line's two wordings.
  - [22 O1](../design/22-reporters.md#o1-reporter-interface): the order of the reporter calls the frame makes, and O1's unit test of it.
  - [10 P3](../design/10-parser.md#p3-result-model): the parts of the result the runner sets (`status = INTERRUPTED`, `verdict = incomplete` after a stop, `counts_approximate`).

## Depends on

- [02](02-errors-and-paths.md): `AppPaths`, `ToolStartError` (raised by the launcher, passed through), `InternalError`.
- [03](03-test-foundation.md): the isolation fixture, the fake `java` with `stdout`, `stderr`, `exit`, `hang_after_line`, `on_sigint`, `on_sigterm`, `on_sigint: "ignore"`, `write_into_metadir`, `checkpoint` and its log ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)).
- [07](07-golden-files.md): the golden captures the fake replays: `violation`, the synthetic `invalid-utf8`, and research 22's checkpoint and `-recover` captures (2195, 2196, 2197, 2198).
- [09](09-parse-package-and-model.md) and [13](13-tlc-parser.md): `RunResult`, `Status`, `Verdict`, the events (`CheckpointStarted`, `CheckpointWritten`), `TlcParser.feed`, `close`, `result`.
- [21](21-java-launcher.md): `signals_held`, `Signals.checkpoint_started` and `checkpoint_written`, `run_streaming` (with `pass_fds` and `on_held`), `run_passthrough` (with `forward_interrupt`, `pass_fds`, `stop_when_reader_gone`), `ProcessOutcome` with `stopped_for_closed_pipe`, `JavaInvocation`.
- [33](33-tlc-invocation.md): `TlcInvocation`, and `resolve_tlc_invocation` with `build_tlc_command` to make the invocations the tests run (or hand-built values).
- [35](35-run-folders.md): `run_folder`, `RunFolder` (`kept_summary`, `lock_fds`, `settle`, `resumes_exactly`), `Settled`, `Kept`, `kept_note`, `reminder`.
- [36](36-reporter-interface.md): `Reporter`, `RunInfo`, `CollectingReporter`.

Change from the draft (21, 35, 36, 13): 02, 03, 07, 09 and 33 are named. 09 and 13 give the result and the parser; 07 the captures the tests replay; 33 the invocation every call takes.

## Files

Creates:

- `src/tlaup/tlc/run.py`: `RunOutcome`, `run_tlc`, `run_tlc_raw`, `waiting_line`.
- `tests/unit/tlc/test_run.py`, and if the closed-pipe tests need one, a small helper script under `tests/unit/tlc/` that a test starts as a child Python process (see Tests).

**Why a new module name.** 00's tree names the file `tlc/runner.py`, which is today's file. It holds an old `run_tlc` with another signature, `cmd/tlc.py` imports five names from it, and about twenty old tests replace names in it by their dotted path (`tlaup.tlc.runner.load_config`, `...subprocess.Popen`). Putting the new functions in the same file means two `run_tlc` or a rename of the old one, and edits to every one of those tests for a pull request that changes no behaviour. A new module leaves the old code and its tests untouched, and the review sees only new lines. [39](39-tlc-command.md) deletes the old `runner.py` and renames `run.py` to `runner.py` (and `test_run.py` to `test_runner.py`, after deleting the old one), which its file already says it does.

Changes, outside the two new files (set by stage 4 when the packages were reconciled): `src/tlaup/reporters/base.py` and `src/tlaup/reporters/collecting.py`, where [36](36-reporter-interface.md) types `finish(outcome: object)` and `outcome: object | None` because `RunOutcome` does not exist when 36 merges; this package narrows the three annotations to `RunOutcome` (imported under `TYPE_CHECKING`, so there is no import cycle). It also fills `RunInfo.cwd`, which 36 added, from `inv.cwd`. Deletes: none; the old runner and its tests go in 39.

Shared files under `src/`: the two reporter files above, three lines.

## Interfaces

Provides, from [11](../design/11-runner.md), the frame. What stage 4 wrote or changed is marked; a worker may adjust a name if the behaviour and the tests stay, and says so.

```python
# tlaup/tlc/run.py (tlaup/tlc/runner.py after 39)
@dataclass(frozen=True)
class RunOutcome:
    result: RunResult | None          # 10 P3; None for a raw run, where nothing is parsed
    exit_code: int                    # what tlaup exits with (02 X1)
    tool_exit_code: int | None
    stopped_by: str | None            # "int", "term", "hup"
    stderr_tail: tuple[str, ...]
    warnings: tuple[str, ...]         # the preflight's warnings (R7, J2, J3), for the JSON reporter of milestone 4
    run_folder_kept: Path | None      # R6; the run folder that was kept (the recovered one after -recover)
    resume_command: str | None        # R6; set when run_folder_kept is
    dropped_checkpoint: str | None    # R6; "not-asked", "incomplete" or "depth-first" when a checkpoint was not kept
    stopped_for_closed_pipe: bool     # R1; the reader of stdout went away and TLC was stopped (D58)
    kept: Kept | None                 # written by stage 4 (a gap between packages, settled by stage 4): rundirs' whole Kept value

def run_tlc(inv: TlcInvocation, java_inv: JavaInvocation, reporter: Reporter, *,
            paths: AppPaths, now: Callable[[], datetime], notice: Callable[[str], None]) -> RunOutcome
def run_tlc_raw(inv: TlcInvocation, java_inv: JavaInvocation, *, paths: AppPaths,
                now: Callable[[], datetime], notice: Callable[[str], None]) -> RunOutcome

def waiting_line(signal_name: Literal["int", "term", "hup"]) -> str    # written by stage 4: the text of G3's line
```

**`RunOutcome.kept`** (a gap between packages, settled by stage 4). The note's first line needs the folder's size, the reason and the checkpoint's time, which `run_folder_kept` and `resume_command` do not hold. The outcome carries `Settled.kept` whole; `run_folder_kept` and `resume_command` stay, as the design names them, filled from it (`kept.path`, `kept.resume_command`), for the JSON reporter of milestone 4. [39](39-tlc-command.md)'s `print_run_notes` prints `kept_note(outcome.kept)` ([35](35-run-folders.md)), the same function the frame uses for `add_note`, so the two ways out print one text.

**The frame**, as [11](../design/11-runner.md) writes it, with the names of the packages around it:

```python
with signals_held() as signals, run_folder(inv, paths, now) as folder:      # 21, 35
    try:
        if folder.kept_summary.count: notice(reminder(folder.kept_summary))  # 35; before reporter.start
        reporter.start(run_info)                                             # run_tlc only; the last thing before the child
        process = run_streaming(java_inv, on_stdout=..., on_stderr=reporter.stderr_line, signals=signals,
                                pass_fds=folder.lock_fds, on_held=lambda name: notice(waiting_line(name)))
        # run_tlc_raw instead: run_passthrough(java_inv, signals=signals, forward_interrupt=True,
        #                                      pass_fds=folder.lock_fds, stop_when_reader_gone=True)
        for event in parser.close(): ...                                     # run_tlc only; then the result fields below
        settled = folder.settle(process, workers_reported=result.workers)    # 35: decided before anything is printed
        outcome = RunOutcome(...)
        reporter.finish(outcome)                                             # run_tlc only
    except BaseException as error:
        settled = folder.settle(None)                                        # the first decision stands if there is one
        if settled.kept: for line in kept_note(settled.kept): error.add_note(line)
        raise
    finally:
        reporter.close()                                                     # run_tlc only; never raises (22 O1)
# leaving the block deletes or keeps the folder, releases the lock, restores the handlers
if reporter.write_error:                                                     # run_tlc only
    if settled.kept: add the two lines to reporter.write_error
    raise reporter.write_error
return outcome
```

- **`on_stdout`**: `parser.feed(line)`; for each event in order, first the launcher's mark (`CheckpointStarted` calls `signals.checkpoint_started()`, `CheckpointWritten` calls `signals.checkpoint_written()`), then `reporter.handle(event, parser.result)`. The mark comes before the reporter sees the event, so a signal sent from inside `handle` is already held; the deferral test depends on it.
- **After the loop** (`run_tlc`): `parser.close()`, each of its events to the reporter, then on `parser.result`: `status = INTERRUPTED` when `process.stopped_by` is set; `verdict = INCOMPLETE` when a signal or a closed-pipe stop ended the run, unless it is `ERRORS` or `NOT_CHECKED`; `counts_approximate = result.resumed and not folder.resumes_exactly`. The SANY diagnostics and any error and trace already parsed stay as the parser left them.
- **`RunInfo`** ([22 O1](../design/22-reporters.md#o1-reporter-interface)): `tool="tlc"`, `spec`, `cfg`, `build`, `java`, `workers`, `project_root`, `override_classes` from `inv`, `command=tuple(java_inv.argv())`.
- **The outcome**: `exit_code`, `tool_exit_code`, `stopped_by`, `stderr_tail`, `stopped_for_closed_pipe` from the `ProcessOutcome`; `warnings` from `inv.warnings`; `kept`, `run_folder_kept`, `resume_command`, `dropped_checkpoint` from `Settled`. `run_tlc_raw`: `result=None`, `stderr_tail=()`, and `workers_reported=None` to `settle`.
- **`notice`** is the command's way to write one line on stderr ([39](39-tlc-command.md) passes `ui.note`; G1's sketch says `ui.notice`, a clerical difference the index lists). The run functions print nothing else.
- **`waiting_line`** gives G3's words: `"int"`: `waiting for TLC to finish writing its checkpoint; press Ctrl-C again to stop now`; `"term"`: `SIGTERM received: waiting for TLC to finish writing its checkpoint; send it again to stop now`; `"hup"`: `SIGHUP received: waiting for TLC to finish writing its checkpoint; send it again to stop now` (G3: "SIGHUP likewise"; the exact text is stage 4's). 21 calls `on_held` once per held signal, from the main thread, on the next turn; this package turns the name into the line, as [21](21-java-launcher.md) hands over.

Consumes: listed under Depends on. Consumed by: [39](39-tlc-command.md) (both functions, `RunOutcome`), [40](40-live-display.md) (the frame's order, unchanged, with the terminal reporter in layout mode), [52](52-integration-tests.md) (`run_tlc` with a `CollectingReporter` and a real JVM, [01 T9](../design/01-testing.md#t9-integration-tests)).

## Tests that must pass

Plain pytest in `tests/unit/tlc/test_run.py`, the fake `java` as a real child of the test process, a `CollectingReporter` that also records the calls it gets (and the `notice` calls, in one shared list, so the order between them is visible), invocations from 33 under the isolation fixture, `now` injected. Each test drives the function on the main thread of the test process. No feature scenario is this package's (below).

The frame and the reporter ([22 O1](../design/22-reporters.md#o1-reporter-interface), Tests):

- The `violation` capture: the sequence of event types; a line the fake writes to stderr arrives through `stderr_line`; the calls are `start`, events, `finish`, `close`, in that order; `RunInfo.command` is the argument list the fake logged.
- After an interrupt (a fake that hangs and a SIGINT sent from a reporter callback), `finish` is still called, then `close`; `result.status` is `INTERRUPTED` and `verdict` `INCOMPLETE`; the code is 130.
- A `java` path that cannot be started: the calls are `start`, `close` and no `finish`, and the error that leaves `run_tlc` is the launcher's `ToolStartError`; no run folder and no lock file is left.
- A reporter whose `close` sets `write_error` to a `BrokenPipeError` makes `run_tlc` raise it after a run that otherwise succeeded, and not when the middle raised something else (that error comes out).

Settle on every way out, and the note ([11 R6](../design/11-runner.md#r6-run-folders), "Unit, the frame"):

- After a successful run and after a failing one, `paths.runs` holds no folder and no lock file.
- A reporter whose `handle` raises, with the checkpoint-writing fake (`write_into_metadir: ["queue.chkpt", "vars.chkpt"]`) under `keep`: `close` was called, the exception that comes out carries the two lines of `kept_note` as notes, and the folder is kept. The same with a fake that writes no checkpoint: no note, no folder.
- The same kept folder when `close` sets a write error: the raised `BrokenPipeError` carries the two lines (written by stage 4 from the frame's last lines).
- A run that returns with a kept folder: `outcome.kept` is the `Kept`, `run_folder_kept` and `resume_command` agree with it, `dropped_checkpoint` is `None`; without `keep`, nothing is kept and `dropped_checkpoint` is `"not-asked"`.
- The reminder: with two kept folders left in `paths.runs` (made with 35's steps), `notice` is called once with `reminder(...)`, before `reporter.start`; with none, it is not called.
- A resumed run (a `-recover` capture, into a kept folder whose `run.json` holds this run's `fp` and `seed`): `counts_approximate` is false; with a user's `-fp` that differs from the recorded one it is true.

Signals at an exact moment ([20 G3](../design/20-groundwork.md#g3-java-launcher), Tests; handed over by [21](21-java-launcher.md)). The reporter sends the signal to the test's own process from a callback; the handler has run when `os.kill` returns.

- A reporter whose `start` sends SIGTERM: the fake's log has no `tlc2.TLC` start, the outcome's code is 143, `tool_exit_code` is `None`, and no run folder and no lock file is left.
- A reporter that sends SIGINT on the first event and again from `finish`: the second lands during the summary; `finish` returns normally, `close` is called, the code is 130 and the fake has exited.

The checkpoint deferral, through `run_tlc` (the plain pytest form of R6's and G3's real-process deferral scenarios, which wait on question "checkpoint signal steps" in 39). The fake replays a capture with 2195 and 2196, uses `checkpoint` to write `queue.tmp` and `vars.tmp` at 2195 and commit them at 2196, and hangs after 2196. The reporter sends the signal from `handle` of `CheckpointStarted`; the deferral then holds whatever the fake has written meanwhile, because the mark is what tlaup has read.

- One SIGINT: `notice` gets `waiting_line("int")` exactly once; when `handle` of `CheckpointWritten` runs, the fake's log has no `signal` line; afterwards it has SIGTERM; the code is 130; under `keep` the folder is kept with a complete checkpoint.
- One SIGTERM: the same with `waiting_line("term")` and 143.
- Two SIGINTs from the same `handle`: the second kills at once; the fake's log shows no SIGTERM before it was killed; the checkpoint is incomplete, so under `keep` nothing is kept and `dropped_checkpoint` is `"incomplete"`.
- `waiting_line` gives the three texts above (the wording test 21 hands over).

Closed stdout (D58) and the stderr tail:

- Parsed run, `reporter.handle` raising `BrokenPipeError` (tlaup's own write failing): the exception passes through `run_tlc`, the fake has exited, `close` was called, the folder is settled as tlaup failing (kept under `keep` with a complete checkpoint, with the note on the exception).
- Parsed and raw runs whose stdout is a pipe the reader has left: a child Python process started by the test runs `run_tlc` (with a `CollectingReporter`) or `run_tlc_raw` with the fake `java` and its stdout on a pipe whose read end the test closed first; it prints the outcome's fields as JSON on stderr. The outcome's code is 141, `stopped_for_closed_pipe` is true, `stopped_by` is `None`, the fake got SIGTERM, and under `keep` with a complete checkpoint the folder is kept as for an interrupted run. This needs a real pipe, which the test process's own stdout is not under pytest's capture; the helper is test code and adds no seam to the product. On Windows the raw form is skipped with the reason (D58: no `poll`).
- `stderr_tail` holds the last 50 lines the fake wrote to stderr; a raw run's is empty.

Non-UTF-8 output (R3, the runner's side): the synthetic `invalid-utf8` capture replayed: the run completes with the case's code, the lines around the bytes are intact in the result, and the bad bytes are U+FFFD.

Raw runs:

- `run_tlc_raw` with a fake that writes to both streams and exits 12: the outcome's code is 12, `result` is `None`, no folder and no lock file is left afterwards; the fake's logged arguments hold `-metadir <paths.runs>/<run id>` and no `-tool`.
- In-process the child inherits the test process's descriptors; under pytest's default capture that is a file, so nothing reaches the terminal and the run ends normally.

Old tests: none deleted or rewritten here; `tests/unit/tlc/test_runner.py` and `test_raw.py` test the old runner and go in 39. No stateful test applies: the signals machine is 21's, the run-folder machine 35's.

**Handed to [39](39-tlc-command.md)**, which lists each of them in its own file (checked against `docs/packages/39-tlc-command.md`):

| Scenario | 39's file |
| --- | --- |
| `tlc_signals.feature`: SIGTERM, one SIGINT, two SIGINTs, parsed and raw, real processes | yes |
| R6's checkpoint-writing fake under `--keep` interrupted with SIGINT, parsed and raw | yes |
| D60 on a pseudo-terminal: Ctrl-C reaches tlaup and not the fake; Ctrl-\; `--raw` | yes |
| The real-process deferral scenarios (a SIGINT between 2195 and 2196; a second before 2196) | yes, waiting on question "checkpoint signal steps" |
| `tlc_raw.feature`: the two streams apart; a plain capture byte for byte; R6 leaves nothing; R11's raw rows; R1 and D58 `--raw` whose reader closes after one line | yes |
| The 141 scenarios: 100,000 lines whose reader closes after one line; TU2's silent fake | yes |
| R3: `invalid-utf8` in-process; `PYTHONIOENCODING=ascii` as a real process | yes |
| R1's in-process scenario for a `java` that is not executable (code 3) | yes, in `tlc_errors.feature` |
| R6's feature scenarios of `tlc_run.feature` (keep, incomplete, `-fp` and `-seed`, `Foo` and `Foo_bar`, the reminder, resuming with `{kept}`) | yes |
| The integration runs with a real JVM ([01 T9](../design/01-testing.md#t9-integration-tests)) | no: [52](52-integration-tests.md) |

## Changelog

None in this package: no command reaches the code. [39](39-tlc-command.md) writes R1's two entries and G3's entries (which R2 and R3 point to) word for word when `tlaup tlc` moves onto these functions.

## Context for the worker

Read the frame at the top of [11](../design/11-runner.md) and its three rules, then R1, R2 and R3, then [22 O1](../design/22-reporters.md#o1-reporter-interface) for the reporter's side of the same order, then [20 G3](../design/20-groundwork.md#g3-java-launcher)'s signal table. [21](21-java-launcher.md)'s "Where the launcher ends and the runner begins" is the line from the other side.

### The decisions, with the reason for each

- **D9.** Nothing TLC printed is lost: `close` runs in a `finally` before the application prints an `error:` line, so the output shown before a failure is on the ordinary screen.
- **D15.** Code that should work on Windows, untested there (below).
- **D29.** tlaup sets 130, 143 and 129 after a signal (the JVM's own code is a race between 130 and 143); TLC's code otherwise passes through, a 1 included; 141 for a reader that went away.
- **D34.** TLC runs where tlaup was started; the run functions change no folder.
- **D36, D53.** The run folder is deleted at the end unless the run asked to be kept and holds a complete checkpoint; 35 decides, the frame only calls `settle` once before printing and once more on an exception.
- **D49.** Not the frame's; the sweep and `cache clean` follow it (35, 45).
- **D51.** The JVM gets duplicates of the run's lock descriptors (`folder.lock_fds` into `pass_fds`), and the lock is released only after the launcher has seen the child gone: the frame leaves `run_folder` only after the run function has returned or raised, and the launcher's `finally` stops the child on every way out.
- **D52.** In a parsed run the runner tells the launcher when the parser sees 2195 and 2196, so a first signal between them waits; a raw run reads nothing and never marks a checkpoint.
- **D54.** The verdict and `resumed` come from the parser; the runner adds `INCOMPLETE` after a stop and `counts_approximate`.
- **D58.** A closed stdout stops TLC in both modes: in a parsed run through the launcher's poll or tlaup's own failed write, in a raw run through `stop_when_reader_gone=True`. Nobody can read the result of such a run.
- **D60.** The JVM of a parsed run has a process group of its own; that is the launcher's (`run_streaming` without `merge_stderr`), and `run_tlc_raw` keeps the child in tlaup's group by using `run_passthrough`.

### Where the runner ends and the launcher begins

| Section | This package | The launcher ([21](21-java-launcher.md)) and others |
| --- | --- | --- |
| R1 | The frame's way out: settle, `close`, the note on any exception, `write_error` raised after the frame when nothing else passes, `stopped_for_closed_pipe` copied to the outcome, `stop_when_reader_gone=True` for a raw run. No catch-all: nothing here catches an exception to change it. | `ToolStartError` from `Popen`; the `finally` round the loop; the `reader_gone` poll and code 141 (21). The handler that turns `BrokenPipeError` into 141 and prints the notes ([17](17-error-handler.md)). `JavaNotFound` before the run (33). |
| R2 | `signals_held()` entered before `run_folder` and left after `close` and the end steps; the parser's 2195 and 2196 to `checkpoint_started` and `checkpoint_written`; the waiting line's text through `notice`; `INTERRUPTED`; settle as an interrupted run; `forward_interrupt=True` for raw. | Everything in G3's signal table: handlers, ignored signals, grace period, `terminate()` and `kill()`, the codes, a signal before the child (`may_start`), `held`, the process group, SIGQUIT (21). |
| R3 | A run with invalid bytes completes and the result keeps the surrounding lines; nothing else to build. | Binary pipes and `decode("utf-8", errors="replace")`, nothing decoded in passthrough, the three encoding options (21); the path warning (33); `errors="replace"` on tlaup's own streams (16). |

### Rules a worker could miss

- **`reporter.start` is the last thing before the child.** The lock, the folder, `run.json`, the sweep and the reminder all come before it, so a run that cannot start never opens the live layout of [40](40-live-display.md). A signal that came before the child: `run_streaming` starts nothing, and the run ends with that signal's code after the usual cleanup; `start` has been called by then and `finish` is still called, since the run has an outcome.
- **`settle` before anything is printed**, so the outcome and `finish` can say what happened. On an exception it is called again with `None`; its first answer stands, so a run that had finished when a closed pipe hit the summary stays finished.
- **`close` never raises**; `run_tlc` raises `reporter.write_error` after the frame, only when no other exception is passing. Raising it loses the outcome and with it `print_run_notes`, which is why the note goes onto that error too.
- **The note travels with the exception**: `error.add_note(line)` for each of `kept_note`'s two lines, for any exception, `KeyboardInterrupt` and `BrokenPipeError` included; the handler prints notes after the `error:` line, or alone for a closed pipe (14 F10).
- **Neither the runner nor the reporter prints the "Checkpoint kept" note** for a run that returns; the outcome carries it and the command prints it. The runner prints only through `notice`: the reminder and the waiting line.
- **Mark the checkpoint before `handle`**, and only in `run_tlc`. A child that ends while the mark is set ends the run as usual; nothing has to be cleared.
- **Parse on the main thread.** `on_stdout` and `on_stderr` run on it (G3), so the parser and the reporter need no locks; do not start threads here.
- **`parser.close()` on every run that has an outcome**, a stopped one included, so the verdict is decided, an open trace is closed and SANY's diagnostics are in the result (the roadmap's "filled in on the Ctrl-C path too"). On an exception the result is not returned and nothing more is fed.
- **`folder.lock_fds` is read once** and goes to `pass_fds`; each read makes new duplicates, which the launcher closes after `Popen` (35, 21).
- **Signal tests run on the main thread** of the test process and send the signal from inside the reporter, never from a timer. `signals_held` restores the test runner's handlers afterwards. No test waits for an amount of time ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 5): the grace period is never run out here, and the fake's `hang_after_line` plus a signal ends every run.
- **The fake's commit at 2196.** [01 T4](../design/01-testing.md#t4-fakes-at-the-edges) says the `checkpoint` field renames the `.tmp` files "after line m", where TLC commits before it prints 2196. If package 03's fake renames after writing line `m`, tlaup's SIGTERM can reach it between the line and the rename, and the "kept" assertion of the one-signal deferral test races. Check the fake; if it writes the line first, change it to commit before line `m` (one field's behaviour, with the reason in the pull request) rather than weaken the test. The index has this as a clerical point on T4.

### Windows (D15) and what is not tested there

Nothing here runs on Windows in CI. There is no SIGHUP and `terminate()` kills at once (21); `lock_fds` is empty, so the lock does not follow the JVM (35); `reader_gone` is always false, so a raw run whose reader goes runs on, as `--raw`'s help says (39); a console Ctrl-C reaches every process. The closed-pipe raw test is skipped there; everything else would run but is not run.

### Known gaps; do not close them

- **A pager that does not read.** A main thread blocked writing tlaup's own output into a pipe whose reader is alive and not reading (`tlaup tlc Spec | less`, screen full) stays blocked after Ctrl-C: the child is stopped, but tlaup ends only when the reader reads or quits, then with 141 rather than 130. Found by reasoning, not tried; accepted for the first wave (G3, Risks).
- **A SIGKILL of tlaup** runs none of the frame. The lifeline ends TLC within about two seconds; on Linux and macOS the lock stays held until then; the next sweep settles the folder. On Windows the lock is free in those seconds, and finding K1-8 (a resume in that window deleting a checkpoint the orphan commits) is accepted (D51, D15). Nothing in this package can see it.
- **A first signal while 2195 is still in the pipe** is sent on at once (finding FC8); the completeness test then drops the checkpoint.
- **The waiting line under the live layout.** [14 F6](../design/14-config-and-cli.md#f6-messages) says nothing else prints through `ui` while a reporter is between `start` and `close`; the waiting line is printed through `notice` in that interval. In plain mode, the only mode until [40](40-live-display.md), that is harmless. Under the layout it would be drawn into the alternate screen and lost. The index has the question for 40 (the recommendation there: route it through the reporter, which shows it in the Status panel and copies it to stderr on close); do not build a reporter method for it here.
- Ctrl-Z, SIGTSTP forwarding, a per-run `java.io.tmpdir`: postponed by the design.

### Guessed waits

None of the frame's own. The ones it inherits: the launcher's grace period of ten seconds (a choice; a JVM was measured to exit in under a second), the two seconds for emptying the queue (a guess), a turn of a fifth of a second (21); the five-second wait for a lock (a guess, 35).

### State of `main` when this starts

`tlaup tlc` runs through the old `tlc/runner.py` and `cmd/tlc.py`, with the old parser stack and `tlc/run_cache.py`. Beside them: `tlaup_parse` with the TLC parser, `java/launcher.py`, `tlc/invocation.py`, `tlc/command.py`, `tlc/overrides.py`, `tlc/rundirs.py`, `tlaup/reporters/base.py` with `CollectingReporter`. The terminal reporter ([38](38-terminal-reporter.md)) may not exist yet; this package does not need it. Nothing imports `tlc/run.py` when this package merges.

## Done when

- The tests above pass on Linux and on the macOS job; `uv run poe lint` (mypy strict on `run.py`) and `uv run poe test` pass; CI is green.
- The frame reads as the design's: one `with` for `signals_held` and `run_folder`, the `try` with its `except BaseException` and `finally`, the write error after it; no other `except` in the module.
- The old `tlaup tlc` and its tests are untouched.
- The pull request lists every signature that differs from this file (`RunOutcome.kept`, `waiting_line`), what it did about the fake's commit order, and which tests ran on which system.
- No changelog entry (none is due).

## Out of scope

- The launcher, its loop, the signal table and their unit and stateful tests: [21](21-java-launcher.md).
- The invocation, the path warning of R3, `-fp`, `-seed` and the run id: [33](33-tlc-invocation.md).
- Everything inside `run_folder`, `settle`, the sweep, the resume command and the note's text: [35](35-run-folders.md).
- `Reporter`, `RunInfo`, `CollectingReporter`: [36](36-reporter-interface.md). The terminal reporter, its result line with the dropped-checkpoint words: [38](38-terminal-reporter.md). The live layout: [40](40-live-display.md).
- The command, `print_run_notes`, `make_reporter`, every feature scenario listed above, deleting the old runner and renaming `run.py`: [39](39-tlc-command.md).
- `sany`, `pcal`, `repl`, which use the launcher without this frame: [41](41-sany-command.md) to [43](43-repl-command.md).
- Integration with a real JVM: [52](52-integration-tests.md).

## Risks

From the sections:

- R1: the 141 path rests on Typer and Rich behaving as research 23 and 30 found up to Typer 0.29.2 and Rich 15.0.0; the newest-dependencies job guards later versions. A raw run that stops TLC for a closed pipe reacts within a fifth of a second plus TLC's own exit.
- R2: not run on macOS or with a real terminal by the research; the macOS CI job is the first. A checkpoint that takes minutes holds a first Ctrl-C for minutes; the line says how to stop at once.
- R3: a replaced character in a trace value shows as U+FFFD, so the value printed is not the value TLC computed.

From the cut:

- No command reaches these functions until 39, so the real-process proof of forwarding, of the deferral from outside and of 141 comes one package later; a fault found there is fixed here.
- `RunOutcome.kept` and `waiting_line` are stage 4's; 39's `print_run_notes` is cut against the first.
- The module name `run.py` lives only until 39 renames it.
