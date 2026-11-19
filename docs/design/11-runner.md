# 11. Milestone 1: the runner

Covers milestone 1's runner items, "Reaching TLC", the preflight, and two of the problems the roadmap records without a solution. Relies on decisions D9, D24, D29, D34, D35, D36, D45 and research [13](../research/13-override-loading.md), [15](../research/15-exit-codes-and-signals.md), [16](../research/16-config-path.md), [17](../research/17-metadir.md). Built on the invocation value and the launcher of [20](20-groundwork.md).

```python
# tlaup/tlc/runner.py
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

def run_tlc(inv: TlcInvocation, java_inv: JavaInvocation, reporter: Reporter, *,
            paths: AppPaths, now) -> RunOutcome
def run_tlc_raw(inv: TlcInvocation, java_inv: JavaInvocation, *, paths: AppPaths, now) -> RunOutcome
```

Both functions have the same frame, and only the middle differs:

```python
with signals_held() as signals, run_folder(inv, paths, now) as folder:    # 20 G3, R6
    try:
        reporter.start(run_info)                                           # run_tlc only; the last thing before the child
        process = run_streaming(...) or run_passthrough(...)               # the middle; starts nothing if a signal came first
        kept = folder.settle(process)                                      # R6: decided before anything is printed
        outcome = RunOutcome(...)
        reporter.finish(outcome)                                           # run_tlc only
    except BaseException as error:
        kept = folder.settle(None)                                         # R6: the first decision stands if there is one
        if kept: error.add_note(...)                                       # R6, "The note"
        raise
    finally:
        reporter.close()                                                   # run_tlc only; 22 O1
# leaving the block deletes or keeps the folder, releases the lock, restores the handlers
if reporter.write_error:                                                   # run_tlc only; 22 O1: close() never raises
    if kept: reporter.write_error.add_note(...)                            # R6, "The note": the outcome is lost, the note is not
    raise reporter.write_error
return outcome
```

Three things the frame fixes in place:

- **`reporter.start` is called once, after the run folder is entered and immediately before the child is started.** Nothing that can fail for an ordinary reason (the lock, the folder, `run.json`, the sweep) happens after it, so the live layout ([22 O4](22-reporters.md#o4-live-display)) is never opened for a run that then cannot start.
- **`reporter.close()` runs in a `finally` inside the frame.** `close` is the reporter's own way out: it leaves the live layout and copies the text it held back to stdout, is safe to call twice, and is safe when `start` was never reached ([22 O1](22-reporters.md#o1-reporter-interface)). After a normal run it has nothing left to do. It never raises: a write that fails inside it (a closed pipe) is kept in `reporter.write_error`, and `run_tlc` raises that after the frame when nothing else is passing, so the pipe still ends in 141. Raising it loses the outcome, and with it the command's `print_run_notes`; so when the folder was kept, the same two note lines are first added to the write error with `add_note`, as the `except` branch does for any other error, and the handler prints them on stderr (R6). A kept folder is announced on every way out of the frame. When the middle raises, it runs before the exception leaves `run_tlc`, so the `error:` line the application's handler prints afterwards is written to the ordinary screen and the output that was shown before the failure is still printed (D9).
- **Neither the runner nor the reporter prints the "Checkpoint kept" note.** The outcome carries it and the command prints it after the run function has returned; an exception carries it as a note (R6).

## R1 Run errors reported as what they are

Roadmap: "Today every `OSError` during a run, including a broken pipe from `--raw | head`, becomes \"'java' not found\"."

**Problem.** `tlc/runner.py:217` and `:265` catch `(SubprocessError, OSError)` around the whole run and raise `FileNotFoundError("'java' not found")`.

**Design.** The catch-all goes. Each failure has its own place:

| What happens | Where it is caught | Result |
| --- | --- | --- |
| `java` is not on the system | The preflight ([13 J2](13-modules-and-java.md#j2-finding-java)), before the run | `JavaNotFound`, code 3 |
| The executable cannot be started (`FileNotFoundError`, `PermissionError`, other `OSError` from `Popen`) | The launcher | `ToolStartError`, code 5, with the path and the operating system's message |
| tlaup's own stdout is closed (`BrokenPipeError` while printing) | The application's error handler ([14 F10](14-config-and-cli.md#f10-no-tracebacks)), after the launcher's `finally` has stopped the child and emptied its queue ([20 G3](20-groundwork.md#g3-java-launcher)), the reporter has been closed and the run folder has been settled | Exit 141, no message ([02 X1](02-cross-cutting.md#x1-exit-codes)) |
| The run folder cannot be created or locked | `run_folder` (R6) | `FileOperationError`, code 5 |
| Anything else | The application's error handler | `internal error`, code 5 |

The `BrokenPipeError` reaches the handler only because tlaup prints through consoles of its own class: a plain Rich console catches the error itself and exits 1 ([14 F6](14-config-and-cli.md#f6-messages) has the class, X1 the rule and what was tried). Everything the runner and the reporters print goes through those consoles.

With `--raw` tlaup writes nothing to stdout itself, so `--raw | head` behaves as `java ... | head` does: TLC gets the closed pipe. What TLC then does was not run: from memory the JVM does not stop on a closed stdout, so the run may go on to its end with nobody reading it. **Waiting on question 31**; if that is what happens, the help text of `--raw` says so, and nothing in the design changes.

**Rejected.** Keeping one catch and inspecting the exception inside it: the place an error is raised is what says what it means, and a single catch loses that. Reporting a closed pipe as an error: `head` closing the pipe is the user's intent, and 141 with no message is what other tools do.

**Tests.** Unit, on the launcher ([20 G3](20-groundwork.md#g3-java-launcher)): a path that does not exist and a file without the execute bit each raise `ToolStartError`, code 5, with the path and the system's message ("permission" for the second). These are unit tests because the command line cannot reach them: a `java` that is missing or not executable is never found, so `tlaup tlc` answers `JavaNotFound`, code 3, and the in-process scenario of `tlc_errors.feature` for "a `java` on `PATH` that is not executable" asserts exactly that. Feature, real process with a real pipe (it cannot be shown in-process, where there is no pipe to close): tlaup's stdout is piped to a reader that takes one line and exits, the fake `java` prints 100,000 lines and then waits; tlaup exits 141 within a few seconds, stderr has no traceback, and the fake has exited. The line count is ten times the launcher's queue bound on purpose: with exactly the bound the test would pass even if a full queue could hang tlaup (G3).

**Changelog.** Fixed: "Errors while running TLC were all reported as \"'java' not found\". Each is now reported as what it is."

**Depends on.** G2, G3, F6, F10. **Risks.** The 141 path was tried on the locked Typer and Rich only (F10, X1; questions 23 and 30 ask about the other versions allowed); Python may print "Exception ignored ... BrokenPipeError" at interpreter exit unless stdout is pointed at the null device first, which F10's handler does.

## R2 Signals

Roadmap: "Forward SIGTERM to the JVM so a CI timeout does not leave TLC running; exit 130 on Ctrl-C; survive a second Ctrl-C while draining output."

**Problem.** Today the only signal handling is `except KeyboardInterrupt`. SIGTERM is not an exception, so tlaup dies and the JVM lives on; a second Ctrl-C escapes the drain loop.

**Facts (research 15, run twice).** SIGTERM to tlaup kills tlaup and leaves the JVM running under PID 1. One Ctrl-C ends with 143, or 130, depending on a race. A second Ctrl-C ends silently with 130 through Typer. TLC prints nothing when signalled. The JVM exits in under a second after a signal.

**Design.** The mechanism is the launcher's ([20 G3](20-groundwork.md#g3-java-launcher)): handlers instead of exceptions; first signal terminates the child, a second kills it, the loop drains until the pipes close. What the runner adds:

- **The handlers are held for the whole run**, by the `signals_held()` block shown at the top of this document: from before the run folder is made and the child is started, through the process loop, until `reporter.finish` has printed the summary, the reporter has been closed and the run folder has been deleted or kept. A signal that was already ignored when tlaup started stays ignored, and SIGQUIT is survived so the JVM can print a thread dump (G3). A second Ctrl-C that arrives after the JVM has gone, which is the usual case since the JVM exits within a second, is recorded and changes nothing: the summary is printed in full.
- **A signal before the child exists** (while the run folder is being made) is recorded; the runner starts nothing, cleans up the folder and exits with that signal's code.
- After the loop, if a signal stopped the run, `result.status` becomes `INTERRUPTED`; the SANY diagnostics and any error and trace already parsed are in the result as usual.
- The exit code is 130 for SIGINT, 143 for SIGTERM, 129 for SIGHUP, set by tlaup.
- The run folder is settled as R6 says: an interrupted run's folder is kept if it holds a checkpoint.
- **Raw runs** use `run_passthrough(..., forward_interrupt=True)`: all three signals are forwarded to TLC and the exit codes are the same. Nothing is printed to stdout by tlaup; the "Checkpoint kept" note, if any, is printed on stderr by the command, as for a parsed run (R6).

**Rejected.** Handlers scoped to the process loop: loses the summary to a quick second Ctrl-C (G3 has the reasoning). Leaving Ctrl-C to the terminal in raw mode: a SIGINT sent to tlaup alone, as a CI system does, would then not reach TLC.

**Tests.** `tlc_signals.feature`, six scenarios with real processes (tlaup started with `sys.executable -m tlaup`; the signal is sent to the tlaup process only): SIGTERM, one SIGINT, two SIGINTs, each in parsed and raw mode. Assertions: the exit code; that the fake `java` exited; and, in parsed mode, that stdout holds what was printed before the signal plus an "interrupted" line. The two cases that depend on the exact moment a signal arrives cannot be arranged from outside the process and are plain pytest tests that drive `run_tlc` and send the signal from a reporter callback ([20 G3](20-groundwork.md#g3-java-launcher), Tests): a SIGTERM before the child is started (the fake `java` log stays empty, code 143, no run folder left), and a second SIGINT during the summary. Integration: the same six with the real JVM.

**Changelog.** With G3.

**Depends on.** G3, R6. **Risks.** Not run on macOS or with a real terminal (research 15 lists both as untested); the macOS CI job runs the signal scenarios.

## R3 Non-UTF-8 output

Roadmap: "Do not crash on non-UTF-8 bytes in TLC output."

**Problem.** `Popen(..., text=True)` decodes with the locale's encoding and raises `UnicodeDecodeError` on a byte that does not fit; printing a character the terminal's encoding lacks raises `UnicodeEncodeError`.

**Design.** The launcher reads bytes and decodes each line with `errors="replace"` ([20 G3](20-groundwork.md#g3-java-launcher)); with `--raw` nothing is decoded at all. When tlaup writes to a stream whose encoding cannot represent a character, the two consoles are created with `errors="replace"` on the underlying stream (`sys.stdout.reconfigure(errors="replace")` at start), so printing cannot raise either; this also closes the milestone 4 point "no crash when the output encoding cannot represent a glyph".

**Rejected.** Decoding with the locale's encoding: what TLC writes does not follow the locale tlaup sees in any way that was checked (question 21). `surrogateescape`: keeps the bytes but produces strings Rich and JSON cannot print.

**Tests.** Feature, in-process: the fake `java` replays a file containing the bytes `FF FE` and a Latin-1 `é` inside a trace; the scenario asserts the exit code and that the surrounding lines are intact. Feature, real process (the variable is read when the interpreter starts, so it has no effect in-process): tlaup started with `PYTHONIOENCODING=ascii` and a trace holding `é` exits with the run's code and no traceback.

**Changelog.** With G3.

**Depends on.** G3. **Risks.** A replaced character in a trace value is shown as U+FFFD, so the value printed is not the value TLC computed; the line is otherwise intact. **Waiting on question 21** for whether a JVM option avoids this.

## R4 Spec, cfg and working folder

Roadmap: "Pass a `--cfg` file outside the project root to TLC so that TLC reads the file that was validated; today only its name is passed." Decision D34.

Row labels in this section (B6, D3, E2, F12 and so on) are the rows of research 16's tables, not items of these design documents.

**Problem (research 16, real runs).** `resolve_cfg_file` validates the right file and then passes TLC only its name unless it is under the project root. TLC then read a *different* file of the same name (rows F5, F7, F8, F12) or none (F11, F13, F14). tlaup and TLC also search in different orders. Separately: with a relative spec path that has a folder part, TLC ignores `-DTLA-Library` (E3, E4), and a file in the working folder shadows the module beside the spec (D3).

**Design.**

1. **tlaup does not change folder.** TLC runs where tlaup was started.
2. **The spec is passed as an absolute path.** TLC then takes the spec's folder as its own base folder: modules beside the spec are found (D6), `-DTLA-Library` is honoured (E2), and nothing in the working folder can shadow them. The default cfg is `Spec.cfg` beside the spec (B1).
3. **Symbolic links in the spec's path are not resolved.** The path is made absolute as the user gave it, so TLC looks for modules beside the path the user named, not beside the link's target. `..` is removed textually (`os.path.abspath`, which fixes row F10) when the result is the same file (`os.path.samefile`), which it always is unless a `..` follows a link; otherwise the path is passed with its `..` in place. Research 16 did not test links. **Waiting on question 24** for what TLC does with a spec reached through a linked folder; the rule above stands either way, because it passes TLC what the user typed.
4. **The cfg tlaup validated is the cfg TLC gets**, written relative to the spec's folder. The relative path is computed from the resolved forms of both, `os.path.relpath(realpath(cfg), realpath(spec.parent))`, because the operating system follows links when it walks `..`; computed this way the path names the validated file with or without links, provided TLC joins it to the spec's folder and lets the operating system walk it. The preflight computes it and stores the text (`TlcInvocation.config_arg`), so the function that builds the command reads no disk ([20 G1](20-groundwork.md#g1-tlc-invocation)). Rows B2, B3, B5 and B8 show a relative `-config` is read against the spec's folder on both builds, including with spaces, and B4 shows `..` works for a cfg under the spec's folder. An absolute `-config` would also work on rolling but fails on v1.7.4 when the spec is absolute too and the cfg is outside the spec's folder (B6, B9), so it is not used. On Windows, when spec and cfg are on different drives, `relpath` raises and the absolute path is passed; from rows B6 and B9 that should fail on v1.7.4, but research 16 did not run Windows.

   **Waiting on question 24.** The case the roadmap item names, a cfg *outside* the spec's folder reached with `..` from an absolute spec on v1.7.4, is listed by research 16 as not tested beyond B4. The source reading (the path is joined to the spec's folder) says it works. The same case with the spec's folder behind a symbolic link was not run either: the spec is passed with the link in its path (step 3) while the `..` steps were counted from the link's target, and whether the two meet depends on TLC handing the joined path to the operating system unchanged and not tidying the `..` away as text first. Until both are run, the integration test below is the only check, and it is the first thing a worker runs for this item.
5. **How `--cfg` is found** (unchanged order, roadmap "Keep"): if absolute, that file; otherwise beside the spec, then in the working folder, then in the project root, which the preflight finds from the spec immediately before this step (R11). In each place only a name ending in `.cfg` is tried: `--cfg foo` looks for `foo.cfg`, never for a file named `foo`. TLC strips a trailing `.cfg` from `-config` and adds it again (research 16, source notes), so a file without the suffix could be validated by tlaup and then not be the file TLC opens. The first that exists wins. `CfgNotFound` lists the paths tried.
6. **With no `--cfg`, tlaup checks nothing.** TLC looks for `Spec.cfg` beside the spec and reports its absence itself (255 on v1.7.4, 151 on rolling, research 15). tlaup does not pre-check the default, because rolling builds can also take the configuration from inside the spec, a path research 16 lists as untested, and a check could refuse a spec TLC accepts.

**What changes for users.** TLC used to run in the project root, or the spec's folder; it now runs where tlaup was started. A TLA+ module lying loose in the project root, outside `modules/`, was found only because TLC ran there; it is no longer found. Where a relative path among TLC's own arguments resolves is TLC's rule, not tlaup's:

- `-config` (when given to TLC directly instead of through `--cfg`): against the spec's folder, not the working folder (row B2).
- `-dump`, `-dumpTrace` and other path-taking flags: research 17 saw `-dumpTrace json rel.json` land in the working folder, but with a relative spec; with the absolute spec tlaup now passes, it was not run. **Waiting on question 24.** Until then the changelog entry promises nothing about them and the help text advises absolute paths.

**Rejected.** Running in the spec's folder with the bare name: the most tested arrangement and independent of where tlaup is started, but the maintainer chose the invoking folder (D34). Keeping the project root: keeps both defects unless the spec is made absolute anyway, at which point the root buys only the loose-module lookup. Resolving links in the spec's path: TLC would then search beside the link's target, and a spec linked into a project would lose the project's modules. Accepting a cfg name without `.cfg` as typed: see step 5.

**Tests.** Unit, on `resolve_spec`, `resolve_cfg` and the preflight's `config_arg` with real files in a temporary tree shaped like research 16's layout: for each of rows F1 to F14 the `-config` value, when joined to the spec's folder, is the same file (`samefile`) as the one validated; the same with the spec's folder reached through a symbolic link, including a cfg outside it reached with `..`; `--cfg foo` with a file `foo` and no `foo.cfg` is `CfgNotFound`. Feature, in-process: `--cfg ../outside/out.cfg` with a decoy `out.cfg` in the project root; the logged Java command names the outside file. Integration: the same with real TLC on both builds, asserting the constant value TLC printed; this is the run that covers the untested v1.7.4 case.

**Changelog.** Fixed: "`--cfg` pointing at a file outside the project could make TLC read a different file with the same name." Breaking: "TLC now runs in the folder where `tlaup` was started (was the project root, or the spec's folder). TLA+ modules in the project root but outside `modules/` are no longer found; move them beside the spec or into `modules/`. A relative `-config` given after `--` is read relative to the spec's folder, as TLC does with an absolute spec path; use `--cfg` instead. `--cfg NAME` looks only for a file ending in `.cfg`."

**Depends on.** G1. **Risks.** A spec that reads files by relative path through a Java module now depends on where tlaup is started, as it does with plain Java. The Windows cross-drive case is inferred, not run.

## R5 Spec names

Roadmap: "A dot in the name is mangled by `with_suffix` (`Foo.v2` becomes `Foo.tla`), `.` raises an error, and any existing file such as a `.cfg` is accepted as the spec."

**Problem.** `resolve_spec_file` builds the candidate with `with_suffix(".tla")`, which replaces whatever follows the last dot; it accepts any path that exists; and `.` reaches `with_suffix` and raises `ValueError`.

**Design.** `resolve_spec(text: str, cwd: Path) -> Path`:

1. Empty, `.` or `..`: `UsageError` ("SPEC must be a TLA+ file or its name").
2. If `text` ends in `.tla`: that path must be a file.
3. Otherwise try, in order, `text + ".tla"` (appended, never replacing a suffix, so `Foo.v2` looks for `Foo.v2.tla`) and `<parent>/spec/<name>.tla` (the documented `spec/` layout).
4. A path that exists but does not end in `.tla` is never accepted: `tlaup tlc Spec.cfg` is `SpecNotFound` with the hint "did you mean Spec.tla?" when that exists. A folder is refused only here, when no candidate of step 3 exists: with both a folder `Foo/` and a file `Foo.tla`, `tlaup tlc Foo` runs `Foo.tla`; with only the folder it is a `UsageError` saying SPEC is a folder.
5. `SpecNotFound` carries the list of paths tried, printed as details (roadmap, error messages).

The result is absolute; links are not resolved (R4, step 3). The `spec` folder name is a constant ([14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay)).

**Rejected.** Accepting any existing file and letting TLC complain: TLC's message for `Spec.cfg` as a spec is a parse error in a file the user did not mean. Searching more folders than `spec/`: the search order would need documenting and nobody asked for it.

**Tests.** A parametrised unit test: `Foo`, `Foo.tla`, `Foo.v2`, `dir/Foo`, `Foo` found under `spec/`, `.`, `""`, `Foo.cfg`, a folder name alone, a folder name with a `.tla` file of the same name beside it. The existing seven cases of `test_resolution_scenarios.py` move here.

**Changelog.** Fixed: "A spec name containing a dot (`Foo.v2`) was looked up as `Foo.tla`; `tlaup tlc .` failed with a traceback; an existing file that is not a spec (such as `Spec.cfg`) was passed to TLC."

**Depends on.** G2. **Risks.** A user who relied on passing a spec file with another suffix can no longer do so; TLC itself requires `.tla`, so no working use is lost.

## R6 Run folders

Roadmap: "Stop run-cache cleanup from deleting other specs' directories ... TLC also adds a timestamped folder per run that is never removed; define when those are cleaned up." Also settles the recorded problem "The run-cache fingerprint covers the default `.cfg` only", and decision D36.

**Facts (research 17).** TLC makes one timestamped folder under `-metadir` per run. It deletes that folder after a clean finish; after a violation (rolling builds), a signal or a crash it stays. Two v1.7.4 runs started in the same second in one `-metadir` collide and one fails. Deleting the folder of a running TLC makes it crash at the next checkpoint or queue spill. tlaup's cleanup matches `<stem>_` as a prefix, so running `Foo` deletes the folder of `Foo_bar`; `module add` and `remove` delete every run folder, including those of runs in progress. `-recover` needs the timestamped folder of a checkpointed run and reuses it. With `-checkpoint N` the folder holds `queue.chkpt`, `vars.chkpt` and others after the first interval; the research runs without `-checkpoint` left no `.chkpt` files, and none of them was a long run. Rolling builds also write `<Spec>_TTrace_<n>.tla` and `.bin` beside the spec on every error.

**Design.**

*One folder per run, for parsed and raw runs alike.* No per-spec folder, no fingerprint, no matching by name.

```
<cache>/runs/<run-id>.lock      held by tlaup for the whole run (filelock)
<cache>/runs/<run-id>/
    run.json      {"schema": 1, "spec": "<abs path>", "cfg": ..., "build": "rolling@bc1b506",
                   "pid": 12345, "started": "2026-11-15T10:00:00Z", "tlaup": "0.9.0",
                   "ended": null, "kept": false}
    <TLC's timestamped folder>
```

`run-id` is the UTC start time and eight random hex digits, `20261115T100000Z-3fa9c1d2`. `-metadir` is this folder. The lock file sits beside the folder, not in it, so the lock is taken before the folder exists and there is no moment when another tlaup can see an unlocked new folder.

`RunRecord` below is what `tlaup cache` lists for one folder (its id, the fields of `run.json`, its size, whether its lock is held). It is not the `RunInfo` a reporter is given at the start of a run ([22 O1](22-reporters.md#o1-reporter-interface)).

```python
# tlaup/tlc/rundirs.py
class RunFolder:
    path: Path | None                                       # None when the user passed their own -metadir
    def settle(self, process: ProcessOutcome | None) -> Kept | None    # decides once; deletes nothing yet

@dataclass(frozen=True)
class Kept:
    path: Path                                              # the run folder; after -recover, the recovered run's folder
    checkpoint_dir: Path                                    # TLC's timestamped folder in it, where the *.chkpt files are
    resume_command: str

@contextmanager
def run_folder(inv: TlcInvocation, paths: AppPaths, now) -> Iterator[RunFolder]
def sweep(paths: AppPaths, now) -> None
def list_runs(paths: AppPaths) -> list[RunRecord]          # for `tlaup cache`
def clean_runs(paths: AppPaths, *, include_kept: bool) -> CleanReport
```

- **Start**, in this order: create the lock file and take its lock, waiting up to five seconds; if TLC's arguments hold `-recover PATH` and `PATH` is inside another run folder, take that folder's lock too, the same way (see below); create the folder; write `run.json`; then `sweep`. The wait is there because a sweep or a `cache clean` of another tlaup may hold any lock for the instant it takes to look at the entry. A lock that cannot be had in five seconds is `FileOperationError`, code 5 (R1).
- **Settle** (called by the runner after the process loop and before anything is printed, so the outcome and the summary can say what happened): the folder is **kept** when both hold:
  1. the run did not finish: a signal stopped it, or tlaup itself is failing (an exception is passing through, `process` is `None`), or TLC's exit code is neither 0 nor one of its violation codes 10 to 14 (research 15);
  2. something under the folder is named `*.chkpt`.

  A run that finished, with or without a violation, has nothing to resume, and its folder is deleted even if it holds checkpoint files (research 17: with `-checkpoint` TLC leaves them after a violation). When the folder is kept, `run.json` gets `ended` and `"kept": true`. `settle` decides once: a second call returns the first answer. The frame calls it again when an exception passes, and a run that had already finished when the exception came (a closed pipe while the summary was printed) stays "finished".
- **End** (leaving the block, also after a signal or an error): a kept folder is left and its lock released; any other folder is deleted, the lock file removed while the lock is still held, and the lock released.
- **The note.** For a kept folder the user is told on stderr:

  ```
  Checkpoint kept: <the run folder>
  Resume with: tlaup tlc <absolute spec> --cfg <absolute cfg> ... -- ... -recover <TLC's timestamped folder in it>
  ```

  The first line names what `tlaup cache` lists and `tlaup cache clean --all` removes; the second names the folder TLC needs, the one under it that holds the `*.chkpt` files.

  One function builds the two lines from a `Kept`, and there are two ways they reach the user, neither of which is the runner or a reporter printing:
  - A run function that returns puts them in the outcome (`run_folder_kept`, `resume_command`), and the command prints them with `print_run_notes(outcome, ui)`, the same call for a parsed and a raw run ([20 G1](20-groundwork.md#g1-tlc-invocation)). `reporter.finish(outcome)` receives the same outcome, so the JSON reporter of milestone 4 can put the folder in its result; the terminal reporter prints nothing about it ([22 O3](22-reporters.md#o3-terminal-reporter)).
  - A run function that is left by an exception has no outcome to return. The frame adds the two lines to the exception with `add_note`, and the application's handler prints an exception's notes on stderr after its `error:` line, or alone when the exception is a closed pipe ([20 G2](20-groundwork.md#g2-domain-errors), [14 F10](14-config-and-cli.md#f10-no-tracebacks)). So a folder kept because tlaup itself failed is announced as well.
- **The resume command** is built from the whole request ([20 G1](20-groundwork.md#g1-tlc-invocation), `TlcInvocation.request`) and the resolved paths, never from the text the user typed:
  - `tlaup tlc`, then the spec as the absolute path the preflight resolved, then `--cfg` with the absolute path of the validated file when `--cfg` was given. Absolute, so the command finds the same two files from any folder (research 17: recovery needs the same spec and cfg).
  - Each option the request carried, in a fixed order: `--workers` when it was given on the command line (a value that came from the settings is not repeated; the settings still apply), `--coverage`, `--raw`, each `--java-opt=VALUE`. `--auto-install` is left out: the build is installed.
  - `--`, then TLC's arguments as given, with every `-recover` and the word after it taken out, then `-recover` and `Kept.checkpoint_dir`. A run that was itself started with `-recover PATH` therefore prints one `-recover`, naming `PATH`, which is where TLC went on writing.
  - Joined with `shlex.join` (`subprocess.list2cmdline` on Windows, as R9).

  What it does not carry: the environment (`TLAUP_JAVA_OPTS`, `TLAUP_CONFIG`) and the folder the run was started in. A relative path among TLC's own arguments (`-dump out.dot`) means the same only when the command is run from the folder the first run was started in; the spec and the cfg do not depend on it. The build is whatever is pinned when the command is run; `run.json` records the build the checkpoint was written by, and `tlaup cache` shows it.
- **Why keep checkpoints.** An interrupted run can be resumed only from that folder (research 17: `-recover` worked on both builds). Deleting it would be destroying data nobody asked to destroy, which is milestone 1's goal to stop. **Waiting on question 25**: whether and when TLC writes checkpoints when `-checkpoint` is not given was not observed. The rule keys on the files being there, so it holds either way; the answer only says how often it fires, and so how much disk kept folders can take.
- **`sweep`** looks at each entry of `<cache>/runs/` whose lock it can take at once; an entry whose lock is held belongs to a live run and is never touched, and that includes the locks its own process holds (a second lock object on the same file in one process is refused like any other, tried with the locked `filelock`). Ages are measured from the times in `run.json` (`ended` for a kept folder, else `started`), falling back to the folder's modification time when `run.json` is missing or unreadable.
  - A kept folder is removed after 30 days.
  - A folder with a `run.json` that was never settled (its tlaup was killed) is treated as kept if it holds a checkpoint, and otherwise removed when older than one day.
  - A folder with no `run.json` was not made by the runner (see R9: a command pasted from `--show-command`). It is removed after 30 days.
  - A lock file whose folder is gone is removed only when the file is more than one hour old, and while the sweep holds its lock. The age matters: a run that is starting has made its lock file and not yet its folder, and between making the file and locking it there is an instant in which a sweep can take the lock first. A file that young is left alone, and the starting run gets the lock a moment later through its five-second wait. The age is the file's modification time, which creating the file sets and taking or releasing the lock does not change (tried).

  Errors while deleting are ignored (another sweep may be deleting the same folder).
- **`-recover PATH` among TLC's arguments**: TLC resumes in the folder `PATH` names and writes its checkpoints there, not in the new run's folder. If `PATH`, with links resolved, is inside `<cache>/runs/<id>/`, three rules apply:
  1. The old run's lock, `<cache>/runs/<id>.lock`, is taken at the start, after the new run's own lock and before the sweep (see "Start"), and held to the end. No sweep, this run's own or another tlaup's, can then remove the folder while TLC works in it.
  2. If that lock is not free after the five-second wait, another tlaup is running in that folder or resuming from it, and two TLCs writing one checkpoint would destroy it. The run stops before anything is started: `FileOperationError`, code 5, "the run folder <path> is in use by another tlaup run".
  3. At the end the old folder is settled by the same rule as any other, with the checkpoint looked for in it: deleted if the resumed run finished, kept (with a fresh `ended`, so its 30 days start again, and the same note) if it was interrupted again. The new run's own folder holds no checkpoint and is deleted.

  A `PATH` that does not exist, or is outside `<cache>/runs/`, is TLC's to judge; tlaup takes no second lock, settles only its own run folder, and prints no note for a folder it does not manage.
- **`-metadir` among TLC's arguments**: the user's wins; `run_folder` makes no folder and no lock of its own and cleans nothing in the user's folder. The signal handling is the same. **With `-recover PATH` as well**, the three `-recover` rules above still apply whenever `PATH` is inside `<cache>/runs/<id>/`: that folder's lock is taken and held for the run, and the folder is settled at the end. They key on where `PATH` points, not on whether tlaup made a folder for this run; without this a sweep could delete the recovered folder under TLC.
- `module add` and `module remove` no longer touch run folders. `tlc --cleanup` goes; `tlaup cache clean` replaces it ([23 C1](23-command-layout.md#c1-command-tree)): by default it removes every run folder that has a `run.json`, is not kept, and whose lock is free; with `--all` also the kept ones and those without a `run.json`. It takes each lock before it looks, as the sweep does, and removes a lock file with its folder.

*What this settles.* The prefix-match deletion and the deletion of running runs cannot happen: nothing is deleted by name, and a held lock protects a live run, raw or parsed. The v1.7.4 same-second collision cannot happen: no two runs share a `-metadir`. The fingerprint question disappears: there is no fingerprint, because nothing is reused between runs.

*Trace specs (D36).* On a build with the capability `no_generate_spec_te` ([00](00-overview.md#what-a-build-can-do)), tlaup adds `-noGenerateSpecTE`, unless TLC's arguments contain `-generateSpecTE`, `-noGenerateSpecTE` or `-teSpecOutDir`. v1.7.4 does not write these files and rejects the flag (research 17), so it is never passed there.

**Rejected.** *Keeping one folder per spec with an exact-name match and a pid file*: fixes the prefix bug but keeps the same-second collision on v1.7.4 and needs a rule for "the spec changed". *Always deleting at the end*: loses checkpoints. *Keeping every folder that holds a checkpoint*: a long run that ended in a violation would leave a folder, possibly gigabytes, for 30 days with nothing to resume. *Never deleting; a `cache clean` command only*: one large violation left 29 MB in the research run; folders would grow without limit. *A pid file instead of a lock*: pids are reused, and a lock is released by the operating system when the process dies. *The lock file inside the folder*: leaves a gap between making the folder and locking it. *A run folder for parsed runs only*: a raw run would get an unlocked folder that cleanup could delete under it, the defect this item removes. *Removing every lock file whose folder is gone* (the first revision): can remove the lock file of a run that is starting, after which a `cache clean` finds its folder unlocked. *The resume command "as typed"*: the typed words are gone once resolved, a relative spec breaks from another folder, and a run started with `-recover` would print the flag twice. *The reporter printing the note*: a raw run has no reporter, and a run that fails has no `finish`.

**Tests.**

- Feature, in-process (`tlc_run.feature`, `cache.feature`): after a successful and after a failing run the cache holds no run folders and no lock files (the steps `the cache holds no run folders` and `the cache holds no lock files`). With a fake `java` that writes a `queue.chkpt` into its `-metadir` and exits with 255, the folder is kept, stderr names it, and the resume command printed holds the absolute spec, the absolute `--cfg` and the TLC arguments of the run; the same fake exiting with 12 (a violation) leaves nothing. Two runs of specs `Foo` and `Foo_bar` do not disturb each other. `module add` leaves a kept run folder alone. `cache clean` removes unlocked folders. A second run in the same scenario with `-- -recover {kept}`, where the placeholder `{kept}` stands for the run folder the previous run kept ([01 T5](01-testing.md#t5-feature-files-and-steps); the run id is random, so the scenario cannot spell it), deletes that folder when the fake exits 0; when the fake exits 255 again the folder is kept and the resume command printed has one `-recover`. The same with `-- -metadir <a folder of the test's> -recover {kept}`: the kept folder is still deleted after exit 0, and no folder is made under `runs/`.
- Feature, real processes: the same checkpoint-writing fake, interrupted with SIGINT, in parsed and in raw mode: the folder is kept and the note is on stderr; a raw run that ends normally leaves nothing.
- Unit (`rundirs`), plain pytest: `settle` for each exit code class, with and without a checkpoint, and that a second call returns the first answer; `sweep` with an injected clock at 23 hours, 25 hours and 31 days, for kept, unsettled and `run.json`-less folders, with and without a held lock; a lock file with no folder survives a sweep at 59 minutes and is removed at 61; `sweep` and `clean_runs` leave a folder whose lock is held, once by a lock object of the test itself and once by a second Python process started by the test (this replaces a feature scenario that would have needed a second tlaup command during a run); `run_folder` with `-recover` into a folder whose lock the test holds raises `FileOperationError` after the wait (the wait is a parameter, set short), and starts nothing.
- Unit, the resume command, from hand-built `TlcInvocation` and `Kept` values: a relative spec and `--cfg` come out absolute; `--raw`, `--coverage`, `--workers 4` and two `--java-opt` are carried and a `workers` that came from the settings is not; an existing `-recover X` among TLC's arguments is replaced, not doubled; the result parses back (`shlex.split`) to the expected list.
- Unit, the frame: `run_tlc` with a reporter whose `handle` raises, and the checkpoint-writing fake: the reporter's `close` was called, the exception that comes out carries the two note lines, and the folder is kept. The same with a fake that writes no checkpoint: no note, no folder.
- Integration: a real violation on a rolling build leaves nothing in `<cache>/runs` and no `_TTrace_` file beside the spec; on v1.7.4 the command has no `-noGenerateSpecTE`; a real run with `-checkpoint 1`, interrupted after the first checkpoint, is kept and the printed resume command completes it.

**Changelog.** Fixed: "Running a spec could delete the run data of another spec whose name starts the same way, or of a run in progress; `tlaup module add` and `remove` deleted all run data." Changed: "Each run has its own run folder, removed when the run ends. If a run is interrupted or crashes and TLC had written a checkpoint, the folder is kept and the command to resume it is printed; kept folders are removed after 30 days or by `tlaup cache clean --all`." Changed: "On rolling builds tlaup passes `-noGenerateSpecTE`, so TLC no longer writes `_TTrace_` files next to the spec. Pass `-generateSpecTE` after `--` to get them." Removed: "`tlaup tlc --cleanup`; use `tlaup cache clean`."

**Depends on.** G1, G3, F2, `filelock`. **Risks.**

- A tlaup killed with SIGKILL leaves its JVM running and its lock free. `tlaup cache clean` at that moment, or a sweep a day later when there is no checkpoint, deletes the folder under it. Accepted: it needs a forced kill.
- Kept folders can be large (the checkpoint of a long run is the size of its state queue and fingerprint set) and stay for 30 days. `tlaup cache` lists them with their sizes; how often this happens depends on question 25.
- On Windows open files cannot be deleted; errors are ignored and the next sweep retries.
- Whether TLC writes its checkpoint files directly in the timestamped folder on every build was read from research 17's listings for the two supported builds only.
- The lock rules were tried with the locked `filelock` only (4.2.10, Linux): a second process waiting with a timeout gets the lock when the holder releases it; when the holder removes the file while holding the lock and then releases, the waiter ends up holding a lock on a file that exists at the path, and a third process is refused. The reviewer of the first revision found that this version re-checks for a removed file and that older ones were not looked at, so the lower bound of `filelock` is the checked version until **question 30** finds the earliest one that behaves the same ([30 B2](30-ci-and-release.md#b2-build-fixes)). Not tried on macOS or Windows.
- The five-second wait for a lock is a guess at "longer than any sweep holds one".
- The resume command does not carry the environment or the starting folder, and uses whatever build is pinned when it is run (see "The resume command").

## R7 Override modules that do not load

Roadmap: "Report clearly when an override module fails to load." Decision D35.

**Facts (research 13, 35 cases per build, Java 25 only).** Most failures are silent: a class that is missing, not on the classpath, or not an `ITLCOverrides` gives no output and exit 0, and the plain TLA+ definition runs. v1.7.4 ignores the `tlc2.overrides.TLCOverrides` property and loads only a class with exactly that name, so a module whose class is named otherwise never loads there (checked with `docs/examples/QueueModule`). On rolling builds the property, when set, *replaces* the default: a real `tlc2.overrides.TLCOverrides` on the classpath is not loaded unless the property names it (case `prop_class_not_found`). A class that breaks while loading gives message 1000, exit 255, before any state is computed, without naming the class. A mismatch of module, operator or arity gives warnings 2402, 2403, 2400, but only if the annotation has `warn = true`. A successful load prints 2168, also only with `warn = true`.

So TLC's output can report only part of the failures. The rest must be checked by tlaup before the run.

**Design.** Four parts.

1. **Which classes are passed** (`tlaup/tlc/overrides.py`, part of resolving the invocation). Today's `get_override_classes` (`tlc/runner.py:85-109`) is replaced by:

   ```python
   @dataclass(frozen=True)
   class OverrideClass:
       name: str                    # "tlc2.overrides.QueueOverrides"
       declared_in: Path            # the classpath entry
       module: str | None           # the registered module's name, if the entry is one

   def collect_override_classes(classpath: Sequence[Path]) -> list[OverrideClass]
   ```

   For each classpath entry in order, folder or jar: the lines of its `META-INF/services/tlc2.overrides.ITLCOverrides` file, if it has one (comments and blank lines skipped). Then, for every entry that holds `tlc2/overrides/TLCOverrides.class` and whose service file did not already name it, the default name `tlc2.overrides.TLCOverrides`. Duplicates are dropped, first wins. `TlcInvocation.override_classes` is the list of names, and the property is passed only when the list is not empty.

   The second rule is the fallback today's code has for folders, kept and extended to jars. Without it a project's own `classes/tlc2/overrides/TLCOverrides.class`, or one inside a jar in `lib/`, would silently stop loading on a rolling build the moment any registered module made tlaup set the property.

2. **Before the run**:

   ```python
   def check_overrides(classes: Sequence[OverrideClass], classpath: Sequence[Path], build: Build) -> list[str]
   ```

   For each class:
   - If no classpath entry holds its `.class` file: warning "override class X (module M) is not on the classpath and will not load".
   - If the build lacks the capability `overrides_property` and the name is not `tlc2.overrides.TLCOverrides`: warning "TLC <build> loads Java overrides only from a class named tlc2.overrides.TLCOverrides; X (module M) will not load, and the TLA+ definitions of its operators will be used".
   - If two classpath entries hold a class named `tlc2.overrides.TLCOverrides`: warning that only the first is used.
   - If its `.class` file is found and does not implement `tlc2.overrides.ITLCOverrides`: warning "X (module M) is not an override class (it does not implement tlc2.overrides.ITLCOverrides) and TLC will ignore it". Research 13: TLC says nothing in this case and runs the TLA+ definitions. The file is read with the class-file reader of [13 M3](13-modules-and-java.md#m3-module-build-details), which gives the interface list exactly. A class that reaches the interface through a superclass is followed as far as the superclass can be found on the classpath outside the tools jar; when the chain leaves what can be read, or the file is not a readable class file, nothing is said. This row matters for names that come from a hand-written service file; a name that tlaup's own module build wrote was found by the same test.

   The warnings are returned in `TlcInvocation.warnings`; the command prints them on stderr before TLC starts and the run goes ahead (D35). They are copied to `RunOutcome.warnings` so the JSON reporter of milestone 4 can include them. `module add` runs the same check against the pinned build and prints the same warning at the moment the module is added.

3. **From TLC's output.** Message 2168 is parsed into `RunResult.overrides_loaded` ([10 P3](10-parser.md#p3-result-model)), one entry per override in the form `"<java_class>.<operator>"`. Warnings 2400, 2402, 2403 are ordinary warnings (severity 3) and are shown. The verbose header of the terminal reporter lists the loaded overrides.

4. **When TLC fails before starting.** If the result has an error of kind `exception` (message 1000) with no nested message of kind `config`, and the phase never reached `INITIAL_STATES`, and override classes were passed, the reporter adds one hint: "TLC failed while loading the spec. If the error comes from a Java override, one of these classes failed to load: ...". It is a hint, not a diagnosis: TLC does not name the class (research 13). The condition about the nested message is the reporter's, stated in [22 O3](22-reporters.md#o3-terminal-reporter): v1.7.4 reports a false `POSTCONDITION` with the same outer shape, and that capture has a nested configuration message, so the hint is not shown beside it.

**Rejected.** *Making overrides load on v1.7.4* by generating one collecting `TLCOverrides` class: a real feature, about a week, redone when milestone 3 makes modules per project. *Refusing to run*: blocks specs whose TLA+ definitions are correct fallbacks. *Inferring a failed load from a missing 2168 line*: the line is absent for every `warn = false` override, which is what the examples use. *Passing only the classes named in service files*: drops the default class on rolling builds, see part 1.

**Tests.** Unit, `collect_override_classes` with real folders and jars from the fakes: a service file; a bare `TLCOverrides.class` in a folder and in a jar; both in one entry; a registered module's service file together with a project's own `TLCOverrides.class`, where the list holds both names. Unit, `check_overrides` with real class files: each of the four warnings and the clean case; for the fourth, a class that implements the interface only through a superclass in the same folder is not warned about, and neither is one whose superclass cannot be found. Feature, in-process: a registered module with class `QueueOverrides`, v1.7.4 pinned, `tlaup tlc Spec` prints the warning on stderr and still starts Java; with a rolling build pinned there is no warning and the logged command's property names both that class and a project `TLCOverrides`. Golden: the override cases added to the corpus ([01 T3](01-testing.md#t3-golden-files)) parse to the loaded list, the three warnings, and the exception error. Integration: `docs/examples/QueueModule` on both builds ([01 T9](01-testing.md#t9-integration-tests)).

**Changelog.** Added: "tlaup warns before a run when a registered Java override class will not be loaded by the pinned TLC build. On v1.7.4 only a class named `tlc2.overrides.TLCOverrides` is loaded." Changed: "The run output lists the operator overrides TLC reports loading." Fixed: "On rolling builds an override class named `tlc2.overrides.TLCOverrides` inside a jar on the classpath stopped loading when another override module was registered."

**Depends on.** G1, V1 (capabilities), M2, M3 (the class-file reader). **Risks.** The capability rule is exact only for the two supported builds ([00](00-overview.md#what-a-build-can-do)). Reading the file list of every jar on the classpath costs a zip directory read per jar, once per run. The hint of part 4 is added for any early message 1000 when override classes were passed, so it can stand beside an exception that has another cause; its wording is conditional for that reason, and the one such case in the captures (v1.7.4's false `POSTCONDITION`) is excluded by the nested-message condition. Research 13 ran Java 25 only.

## R8 Passthrough and workers

Roadmap: "Pass everything after `--` to TLC. Add `--workers`, defaulting to `auto`, as the only first-class TLC option (decision D24). The existing `--cfg` and `--coverage` stay; `--coverage` remains hard-coded to `-coverage 1`."

**Problem.** Today nothing the user types reaches TLC except the spec and the cfg name; a TLC option such as `-deadlock` or `-simulate` cannot be used without leaving tlaup.

**Design.** The command declares the spec and then a variadic argument for TLC's own arguments. Typer treats everything after `--` as arguments, so `-deadlock` after `--` reaches that list, while an unknown option before `--` is still an error (unknown options are not ignored). A word after the spec that does not start with a dash also lands in the list without `--`; `--` is needed as soon as one of TLC's arguments starts with a dash, which is nearly always, and the help text shows only the `--` form. All three behaviours were tried on the locked Typer 0.29.1 (question 23 asks about the rest of the allowed range). The arguments become `TlcRequest.extra_args` and are placed before the spec in the command, unchanged.

`--workers TEXT`: `auto` or a positive integer; the default comes from the setting `tlc.workers`, whose default is `auto`. tlaup passes `-workers <value>`. A value that is neither is a `UsageError`, raised by the first step of the preflight with the table below (R11), before the spec is looked at and before any prompt.

Because both tlaup and the user can now give the same TLC flag, one table decides, and it is the only place such rules live (`tlaup/tlc/invocation.py`):

| Among TLC's arguments | With the tlaup option | Without it |
| --- | --- | --- |
| `-workers` | `--workers` given: `ConflictingOptions` (2) | tlaup passes no `-workers`; the user's is used |
| `-coverage` | `--coverage` given: 2 | passed through |
| `-config` | `--cfg` given: 2 | passed through; tlaup does not validate it. TLC reads a relative value against the spec's folder, not the working folder (R4) |
| `-metadir` | n/a | the user's is used; no run folder (R6) |
| `-tool` | n/a | passed through; harmless in parsed mode; in `--raw` mode it is the user's choice |
| `-generateSpecTE`, `-noGenerateSpecTE`, `-teSpecOutDir` | n/a | tlaup adds no `-noGenerateSpecTE` (R6) |
| `-recover PATH` | n/a | passed through; the recovered run's lock is held (R6) |
| `-difftrace` | n/a | passed through; traces shown as printed (P5) |

**Waiting on question 19.** `-workers auto` was run on neither supported build; the string `auto` is present in `tlc2/TLC.class` of two other jars a reviewer looked at, which is a hint and no more. If both builds accept it, the design is as above. If one does not, tlaup replaces `auto` with a number on builds that lack it: `os.process_cpu_count()` where Python has it (3.13 and later), else `len(os.sched_getaffinity(0))` where the platform has it, else `os.cpu_count()`. That is worse than TLC's own choice inside a container with a CPU quota, which is why TLC's `auto` is preferred where it exists. Everything else in this item does not wait.

**Rejected.** Scanning all extra arguments to "understand" them: only the flags in the table are looked at, by exact match, and the list is short on purpose (D24: fewer options to keep in step with TLC). Turning a conflict into "last one wins": which one TLC honours for a repeated flag was not checked.

**Tests.** Feature, in-process: `tlaup tlc Spec -- -workers 4 -deadlock` (the roadmap's exit criterion) logs a Java command ending `-workers 4 -deadlock <spec>` with one `-workers`; `--workers 2 -- -workers 4` exits 2; `--workers auto` logs `-workers auto`; `--workers 0` and `--workers x` exit 2; a mistyped `--coverge` exits 2 and starts nothing. Unit: the table, row by row.

**Changelog.** Added: "Arguments after `--` are passed to TLC: `tlaup tlc Spec -- -deadlock -simulate num=10`." Added: "`--workers N|auto`." Breaking: "TLC now runs with `-workers auto` by default (was TLC's default of one worker). Set `tlc.workers: 1` or pass `--workers 1` for the old behaviour."

**Depends on.** G1. **Risks.** Several workers change the order of `Print` output and can change which counterexample is found first; this is TLC's behaviour and is named in the changelog entry.

## R9 Show command

Roadmap: "Make `--show-command` print the exact command that would run, including `-tool`, shell-quoted, without creating or deleting anything in the run cache."

**Problem.** `--show-command` builds the command with one function while the run edits the list afterwards (`-tool` is inserted later, `-coverage 1` is appended after the spec instead of before it), and building it creates a run folder and deletes others.

**Design.** `--show-command` runs the preflight, builds the `JavaInvocation` with the same function the run uses, prints `shlex.join(argv)` on stdout (one line), and exits 0. With `--raw` the printed command has no `-tool`. A GitHub token is never part of a Java command, so nothing needs hiding here; the rule that it is never printed is tested in [12 V7](12-tools-and-downloads.md#v7-github-client).

- **It never prompts and never installs** (D45). Its `get_build` is the store's pinned build; with nothing installed or nothing pinned it stops with code 3 and the hint, whatever `--auto-install` says. It does not sweep either.
- **Nothing is created in the run cache**: the run id is generated; the folder and its lock are not.
- **What `-metadir` a pasted command uses.** The printed command names `<cache>/runs/<run-id>`, the folder a real run with that id would have used. Run by hand, that folder is not tlaup's to manage: it has no lock and no `run.json`. tlaup therefore leaves it alone unless asked: the sweep removes such a folder only after 30 days, and `tlaup cache clean` only with `--all` (R6). TLC's own timestamped folder inside it is deleted by TLC after a clean finish, as always. The help text of `--show-command` says in one line that for a long run pasted by hand the `-metadir` value should be replaced with a folder of the user's own.

On Windows `shlex.join` produces POSIX quoting; `subprocess.list2cmdline` is used there instead.

**Waiting on question 20.** The printed `-metadir` names a folder that does not exist yet. Whether TLC creates a missing `-metadir` folder was not checked (research 17 read the code: v1.7.4 uses `mkdirs`; rolling uses `createDirectory` for the timestamped folder, and its parent handling was not traced). If TLC does not create it, the pasted command fails until the folder is made; then `--show-command` prints a `mkdir -p` line before the command, or the wording of the help says so. The rest of the item does not wait.

**Rejected.** Printing the command without `-metadir`: it would not be the command that runs, and a pasted run would write `states/` beside the spec. Creating and locking the folder for the printed command: the roadmap says nothing is created, and nothing would ever release the lock.

**Tests.** Feature, in-process: output is one line; the cache holds no run folders and no lock files; `java` was started for nothing but the remembered version check; with no build pinned it exits 3 with one error line and no prompt, also with `--auto-install rolling`. Plain pytest, two in-process runs in one test ([01 T5](01-testing.md#t5-feature-files-and-steps)): the line equals the command logged by a real run with the same arguments apart from the run id (compared after replacing the id). Unit (`rundirs`): a folder under `runs/` with no `run.json` survives a sweep and a plain `cache clean`.

**Changelog.** Fixed: "`--show-command` printed a command without `-tool` and with `-coverage 1` in the wrong place, and created (and could delete) run data. It now prints exactly what would run and creates nothing in the run cache."

**Depends on.** G1, R6, R11. **Risks.** A user who pastes the command twice at once shares one `-metadir` between two runs, which collides on v1.7.4 in the same second (research 17); the help line about replacing `-metadir` covers it.

## R10 Project root

Roadmap (recorded without a solution): "The project-root rule counts a parent folder that has `lib/`, `modules/` or `classes/`, so a spec under `~/work` with `~/lib` present runs with `~` as its root and every jar in `~/lib` on the classpath."

**Design.** `find_project_root(spec: Path, home: Path) -> Path | None`:

1. The spec's own folder is the root if it contains `modules/`, `classes/` or `lib/`.
2. Otherwise the spec's parent folder is the root if it contains one of the three **and the spec's folder is named `spec`, `specs`, `test` or `tests`**. This is the documented layout (`project/spec/Spec.tla`) and nothing wider.
3. A folder is never the root if it is the user's home folder or a filesystem root.
4. Otherwise there is no root.

The run header in verbose mode names the root and every classpath entry it added, so a surprising root is visible.

This is a stopgap by design: milestone 3 makes the project file the marker and walks up to find it ([40](40-later-milestones.md#milestone-3-reproducibility)). The function keeps its signature then; only its body changes.

**Rejected.** Waiting for the project file: the `~/lib` case puts arbitrary jars on TLC's classpath today. Dropping the parent rule: breaks the documented `spec/` layout and the examples. Walking further up: without a marker file, more folders would qualify by accident, not fewer.

**Tests.** `tests/unit/spec/test_project.py` has five cases today. The two where the spec's own folder holds the marker, or nothing does, are kept as they are. The three that put the spec in a folder named `subdir` and expect the parent as root (`parent_has_classes`, `detected_by_lib`, `detected_by_modules`) contradict rule 2 and are rewritten with the folder named `spec`. New cases: spec in `work/` with `lib/` in the parent (no root); spec in `tests/` with `modules/` in the parent (root); the parent is the home folder (no root); the spec's folder is the home folder and has `lib/` (no root).

**Changelog.** Breaking: "A folder is treated as the project root of a spec only if it is the spec's own folder, or its parent when the spec is in a folder named `spec`, `specs`, `test` or `tests`. The home folder is never a project root. A project that keeps specs in a differently named subfolder must move `modules/`, `classes/` or `lib/` beside the specs or rename the subfolder."

**Depends on.** Nothing. **Risks.** Layouts such as `project/models/Spec.tla` with `project/lib/` stop finding the root; the changelog says what to do.

## R11 Preflight

Roadmap: "One preflight used by every `tlaup tlc` path, checking jar, Java, spec and cfg in that order, each failure a one-line error naming the next command. Print nothing, including 'Starting TLC', until the checks pass."

**Problem.** The three paths of `tlaup tlc` check different things in different orders; a missing jar or Java can print "Starting TLC" and then a traceback.

**Design.** The preflight is `resolve_tlc_invocation` ([20 G1](20-groundwork.md#g1-tlc-invocation)); there is no other way to get a `TlcInvocation`, so `--show-command`, `--raw` and the parsed run cannot skip it.

**The order is spec, cfg, tool build, Java** (decision D45), not the roadmap's jar, Java, spec, cfg. Two reasons: a mistyped spec name is reported before any first-run prompt or download; and milestone 3 chooses the build from a project file found by walking up from the spec, which needs the spec first. With this order milestone 3 adds a step and moves none.

Before those four comes a step that reads nothing from the disk: the checks that need only the command line and the environment. A mistake of that kind is a usage error whatever is installed, and reporting it first means nobody answers the first-run prompt, or waits for a download, and is then told that two of their options conflict.

| Step | Failure | Message and hint |
| --- | --- | --- |
| 0. The command line | Two options that conflict (the table of R8); `--workers` that is neither `auto` nor a positive integer; an unbalanced quote in `TLAUP_JAVA_OPTS` ([13 J1](13-modules-and-java.md#j1-java-options)) | `ConflictingOptions` or `UsageError`, code 2 |
| 1. Spec | Not found; not a spec | `SpecNotFound` with the paths tried, or `UsageError` (R5) |
| 1b. Project root | Cannot fail | `find_project_root(spec, home)` (R10). It needs only the spec, and step 2 searches the root for the cfg |
| 2. Cfg | `--cfg` given and not found | `CfgNotFound` with the paths tried (R4). With no `--cfg` nothing is checked (R4, step 6) |
| 3. Tool build | Nothing installed | The first-run prompt ([12 V9](12-tools-and-downloads.md#v9-first-run-prompt)), or `NoToolsInstalled`: "no TLA+ tools installed" / "run `tlaup tool install stable` or `tlaup tool install rolling`". With `--show-command`: always the error (R9) |
| | Builds installed, none pinned | `NoPinnedBuild`: "no version pinned" / "run `tlaup tool pin <one of: ...>`" |
| | The pin names a build that is gone or damaged | `PinnedBuildMissing`: "the pinned build rolling@bc1b506 is missing" / "run `tlaup tool install rolling` or `tlaup tool pin ...`" |
| 4. Java | Not found; too old; the check timed out | `JavaNotFound`, `JavaTooOld`, `Failed` ([13 J2, J3](13-modules-and-java.md#j2-finding-java)) |

Then the classpath and the override collection and check (warnings only, R7), which need the build, and the values that depend on it (`-noGenerateSpecTE`, R6). Nothing after step 4 can fail for a reason the user caused on the command line.

So with no build installed and a missing spec, the spec is reported and the code is 4; no prompt is shown. With no build installed and `--workers 2 -- -workers 4`, the conflict is reported and the code is 2; no prompt is shown.

`sany` and `pcal` use the same steps in the same order, and `repl` steps 0, 3 and 4, through the same functions (`resolve_spec`, the command's `get_build`, `require_java`); [21](21-other-tools.md) has their one resolving function. Their step 0 holds the Java option check and, for `sany`, the refusal of `-d` ([21 S1](21-other-tools.md#s1-sany)).

Nothing is printed before the preflight returns: the reporter is created after it, the preflight's warnings come back in `TlcInvocation.warnings` and are printed by the command, and the first-run prompt is the one thing that may write (to stderr) during it.

**Rejected.** The roadmap's order: see above; the maintainer chose spec first (D45). Checking the command line where the first revision did, after Java: the conflict of two options would be reported after a prompt and a download. Checking the default `Spec.cfg` when no `--cfg` is given: R4, step 6. A separate "check" function beside the function that builds the invocation: two lists of checks that drift.

**Tests.** `tlc_errors.feature`, in-process: one scenario per row, each asserting the code, an empty stdout and exactly one `error:` line; for the spec, cfg and build rows that `java` was not started at all; for the Java rows that it was started for `-version` only and TLC was not started; for the build rows that the hint names a command. One scenario has no build and a missing spec and asserts code 4 and that nothing was asked; one has no build and conflicting `-workers` and asserts code 2 and that nothing was asked. The spec, cfg, pinned-build and Java rows are run for the parsed and `--show-command` paths with a scenario outline; the raw path is run as a real process for the spec row and the Java row, which is enough to show it goes through the same function.

**Changelog.** Fixed: "Missing Java, a missing jar, or a missing spec could print 'Starting TLC' and then a traceback. Every `tlaup tlc` path now checks the spec, the cfg, the tools and Java first and reports the first problem in one line with the command to run next."

**Depends on.** G1, G2, R4, R5, R8, R10, V9, J2, J3. **Risks.** The spec is now looked up before tlaup knows it can run anything, so a user with nothing installed and a mistyped spec fixes the spec first and meets the install prompt on the second try.

## R12 Run-cache fingerprint

Roadmap (recorded without a solution): "The run-cache fingerprint covers the default `.cfg` only, not a `--cfg` file or extended modules."

**Settled by R6**: there is no fingerprint. The fingerprint existed to throw away a spec's run folder when the spec changed; with one folder per run nothing is reused, so nothing needs to be invalidated. `compute_spec_hash`, `_cleanup_stale_spec_dirs` and `get_spec_run_dir` are deleted with their three tests.
