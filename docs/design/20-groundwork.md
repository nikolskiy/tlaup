# 20. Milestone 1b: shared groundwork

Three pieces everything else stands on: the TLC invocation value, the domain errors, and the generic Java launcher. Although the roadmap files them under milestone 1b, the milestone 1 runner items are built inside them, so they come early ([00, order of work](00-overview.md#order-of-work)).

## G1 TLC invocation

Roadmap: "A single TLC invocation value ... resolved once per run and shared by the show-command, raw and formatted paths ... Building the command from it is a pure function and the only place flags are assembled. One process loop instead of two copies. SANY errors in the result are typed and are filled in on the Ctrl-C path too."

**Problem.** `cmd/tlc.py` resolves the spec, then `build_tlc_command` resolves it again, then `run_tlc` again; the config is loaded four times. `run_tlc` inserts `-tool` and `-coverage 1` into the list after it was built, so `--show-command` prints a command that is not the one that runs, and creates a run folder (and deletes others) on the way. The process loop is written twice (`tlc/runner.py:194-219` and `:224-267`). `sany_errors` is `list[Any]` and is not filled in on the Ctrl-C path.

**Design.** Three steps with a value between each.

```python
# tlaup/tlc/invocation.py
@dataclass(frozen=True)
class TlcRequest:                     # what the user typed, nothing looked up
    spec: str
    cfg: str | None = None
    workers: str | None = None        # "auto" or a positive integer, as text; None = take the setting
    coverage: bool = False
    raw: bool = False
    keep: bool | None = None          # --keep; None = take the setting tlc.keep (11 R6, D53; replaces no_keep)
    java_opts: tuple[str, ...] = ()
    extra_args: tuple[str, ...] = ()  # TLC's own arguments (11 R8)

@dataclass(frozen=True)
class TlcInvocation:                  # everything decided; no run folder created, nothing started
    request: TlcRequest               # kept whole: the resume command is built from it (11 R6)
    build: Build                      # 12 V1
    java: JavaRuntime                 # 13 J2
    spec: Path                        # absolute, exists, ends in .tla; symbolic links not resolved (11 R4)
    cfg: Path | None                  # absolute, exists; None = --cfg was not given, TLC picks its default
    config_arg: str | None            # what -config is given: the cfg relative to the spec's folder (11 R4, step 4)
    project_root: Path | None         # 11 R10
    cwd: Path                         # where tlaup was started (D34)
    classpath: tuple[Path, ...]
    tla_library: tuple[Path, ...]
    override_classes: tuple[str, ...] # 11 R7 says how they are collected
    warnings: tuple[str, ...]         # preflight warnings: overrides (11 R7), Java (13 J2, J3), a path TLC cannot open (11 R3)
    jvm_options: tuple[str, ...]      # settings, then TLAUP_JAVA_OPTS, then --java-opt (13 J1)
    workers: str | None               # None = pass no -workers (the user passed one among TLC's arguments)
    coverage: bool
    tool_mode: bool                   # not raw
    suppress_te_spec: bool            # 11 R6
    keep: bool                        # 11 R6, D53: from --keep, the setting or a kept folder -recover names
    fp: int | None                    # 11 R6, D52: what tlaup passes as -fp; None = the user passed one
    seed: int | None                  # 11 R6, D52: the same for -seed
    extra_args: tuple[str, ...]
    run_id: str                       # 11 R6; the run folder is paths.runs / run_id
    metadir: Path | None              # None when the user passed -metadir among TLC's arguments

def resolve_tlc_invocation(request: TlcRequest, *, paths: AppPaths, settings: Settings,
                           env: Mapping[str, str], cwd: Path,
                           get_build: Callable[[], Build]) -> TlcInvocation
    # the preflight (11 R11); raises TlaupError

# tlaup/tlc/command.py
def build_tlc_command(inv: TlcInvocation) -> JavaInvocation      # pure: reads no disk and no environment
```

The preflight takes the pieces it needs, not the whole context ([00](00-overview.md#packages-after-the-first-wave): only commands reach for the context). `get_build` is how the command supplies the tool build: for a run it wraps `ensure_tools` ([12 V9](12-tools-and-downloads.md#v9-first-run-prompt)), which is where the first-run prompt and `--auto-install` live; for `--show-command` it is the store's pinned build with no prompt and no install ([11 R9](11-runner.md#r9-show-command)).

What the preflight writes: nothing in the run cache and nothing beside the spec. It can write in two places, both outside a run: the remembered Java version check, `<cache>/java.json` ([13 J3](13-modules-and-java.md#j3-one-java-start)), and, on a first run when the user agrees, an installed build (V9). It starts no JVM except `java -version` when that answer is not remembered.

The argument order `build_tlc_command` produces, and the only place it is written:

```
<java> [-javaagent:<lifeline jar>=pid=<tlaup's pid>] -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8
       -Dstderr.encoding=UTF-8 <jvm options> -DTLA-Library=<dirs> [-Dtlc2.overrides.TLCOverrides=<classes>]
       -cp <classpath> tlc2.TLC
       [-tool] [-metadir <dir>] [-noGenerateSpecTE] [-workers <w>] [-coverage 1] [-fp <n>] [-seed <n>]
       [-config <cfg>] <extra args> <absolute spec>
```

The lifeline and the three encoding options are added by `JavaInvocation.argv()` for every Java tool (G3, decisions D51 and D56), not by this builder; they are shown here because this is where the whole order is written. The random `-fp` and `-seed` are drawn by the preflight and stored in the invocation, so the builder stays pure and `--show-command` prints the values the run would use (top-up, D52). `-config` is given relative to the spec's folder ([11 R4](11-runner.md#r4-spec-cfg-and-working-folder)). Working that path out follows links on disk, so the preflight does it and stores the text in `config_arg`; the builder only places it, which is what lets it be pure. `-DTLA-Library` and the classpath are joined with `os.pathsep`. A system property is left out when its list is empty.

The command function is then short:

```python
inv = resolve_tlc_invocation(request, paths=..., settings=..., env=..., cwd=..., get_build=...)
java_inv = build_tlc_command(inv)
if show_command:
    ui.out.print(shlex.join(replace(java_inv, lifeline=False).argv()),           # 11 R9: no lifeline; one line,
                 markup=False, highlight=False, soft_wrap=True); return 0      # never wrapped or read as markup (10 P11)
for text in inv.warnings: ui.warning(text)
if request.raw:
    outcome = run_tlc_raw(inv, java_inv, paths=paths, now=now, notice=ui.note)              # 11
else:
    outcome = run_tlc(inv, java_inv, reporter, paths=paths, now=now, notice=ui.note)        # 11
print_run_notes(outcome, ui)        # 11 R6: "Checkpoint kept" and the resume command, or the dropped checkpoint, on stderr, both modes
return outcome.exit_code
```

`ui.out` is a console and `ui.note` the method for a line of tlaup's own on stderr ([14 F6](14-config-and-cli.md#f6-messages)); the run functions use `notice` only for the kept-folders reminder, before the reporter starts ([11](11-runner.md)). (Stage 4 review, 2026-11-24: the sketch used `ui.out(...)` and `ui.notice`, names `Ui` does not have; index, "Clerical".)

`print_run_notes` lives in `cmd/tlc.py` and is the only place that prints the note for a run that returned; neither the runner nor a reporter prints it. By the time it is called `run_tlc` has closed the reporter, so the live layout is gone ([22 O4](22-reporters.md#o4-live-display)). For a run that ends in an exception the note travels on the exception (G2, [11 R6](11-runner.md#r6-run-folders)).

Both run functions enter the run folder ([11 R6](11-runner.md#r6-run-folders)) and hold the signal handlers (G3) for the whole run; a raw run is not a way round either. `run_tlc` owns the one process loop. It feeds stdout lines to one `TlcParser`, which routes SANY's unframed text to its `SanyParser` itself ([10 P8](10-parser.md#p8-sany-output)); so SANY diagnostics are typed (`list[Diagnostic]`) and are in the result however the run ends.

**Rejected.** A mutable builder object: the bug today is exactly that the list is edited after it was "built". Resolving lazily inside the runner: the preflight must finish before anything is printed. Passing the whole application context to the preflight and the runner: it hides which settings a run depends on and makes the functions harder to call from a test.

**Tests.** Unit: `build_tlc_command` on hand-built `TlcInvocation` values, compared with expected files, one per combination that changes the output (raw, coverage, cfg, workers present or absent, overrides, an extra `-metadir`). The function is pure, so these need no fixture. Feature, in-process: `tlc_show_command.feature` and the "java was started with ..." assertions check the same command end to end; one plain pytest test, with two in-process runs, asserts the command printed by `--show-command` equals the command the fake `java` logged for the same arguments, apart from the run id and the lifeline agent ([01 T5](01-testing.md#t5-feature-files-and-steps)).

**Changelog.** None of its own; behaviour changes are listed with the items of [11](11-runner.md).

**Depends on.** G2, G3, V1 (`Build`), V9 (`ensure_tools`), J2 (`JavaRuntime`). **Risks.** The value has many fields; it is the price of deciding everything once. Milestone 3 adds the project file as one more input to `resolve_tlc_invocation` and no new field; the preflight already resolves the spec before the build ([11 R11](11-runner.md#r11-preflight)), which is the order a project file found beside the spec needs.

## G2 Domain errors

Roadmap: "A small family of domain errors (spec not found, tool not installed, Java missing or too old) mapped to exit codes in one place." Relies on D29.

**Problem.** Errors are `FileNotFoundError`, `RuntimeError` and `typer.Exit(1)` raised wherever something goes wrong; every `OSError` in a run becomes "'java' not found"; 21 places print an error by hand.

**Design.** `tlaup/errors.py`:

```python
class TlaupError(Exception):
    exit_code: ClassVar[int]
    def __init__(self, message: str, *, hint: str | None = None, details: str | None = None): ...

class UsageError(TlaupError):   exit_code = 2
class NotSetUp(TlaupError):     exit_code = 3
class NotFound(TlaupError):     exit_code = 4
class Failed(TlaupError):       exit_code = 5
```

`message` is one line with no trailing full stop and no "Error:" prefix. `hint` is one line that names the next command. `details` is optional longer text (compiler output, the list of folders searched), printed after the message.

Text that must follow an error whatever its class is attached with `add_note`, which every exception has from Python 3.11 on. The one use in the first wave is the run frame saying that a run folder with a checkpoint was kept while an error passes through it ([11 R6](11-runner.md#r6-run-folders)); the error can be a `TlaupError`, a closed pipe or an unexpected exception, which is why it is not a field of `TlaupError`. The handler prints an exception's notes on stderr after the `error:` line and hint, and for a closed pipe prints the notes alone ([14 F10](14-config-and-cli.md#f10-no-tracebacks)).

Named subclasses exist where a caller or a test needs to tell them apart:

| Family | Subclasses |
| --- | --- |
| `NotSetUp` | `NoToolsInstalled`, `NoPinnedBuild`, `PinnedBuildMissing`, `JavaNotFound`, `JavaTooOld`, `JavacNotFound`, `ConfigInvalid`, `ToolNotInBuild`, `CannotAsk` |
| `NotFound` | `SpecNotFound`, `CfgNotFound`, `VersionNotFound`, `ModuleNotFound`, `PathNotFound`, `ConfigKeyNotFound` |
| `Failed` | `NetworkError`, `RateLimited`, `RemoteDataError`, `DownloadVerificationError`, `ModuleBuildError`, `StoreLocked`, `FileOperationError`, `ToolStartError`, `InternalError` |
| `UsageError` | `AmbiguousVersion`, `InvalidName`, `ConflictingOptions` |

The mapping to an exit code is the class attribute and nothing else; the one handler, inside the application so that the in-process test runner sees the same codes, reads it ([14 F10](14-config-and-cli.md#f10-no-tracebacks)). Signal exits (130, 143, 129, 141) are not errors; the launcher and the handler return them directly.

A flag-level mistake (an unknown option, a missing argument) stays Typer's own usage error, which already exits 2 and prints the usage text in Typer's form; it is not a `TlaupError` and tlaup does not reformat it (F10 says what was tried on the locked Typer). tlaup's `UsageError` is for mistakes Typer cannot see (a module name with a slash, two options that conflict) and prints one `error:` line. The hand-written "Missing argument" check in `cmd/tlc.py:104` goes, because `SPEC` becomes a required argument. The one in `cmd/tools/uninstall.py:85` stays as a `UsageError`: `uninstall` takes versions or `--all`, which a required argument cannot express ([23 C1](23-command-layout.md#c1-command-tree)).

**Rejected.** One exception class carrying a code: tests and callers would compare numbers. An enum of error kinds: the same thing with more words. A separate class per message: about sixty classes.

**Tests.** A unit test collects every subclass of `TlaupError` and asserts its `exit_code` is in `{2, 3, 4, 5}` and equals its family's. `errors.feature` (in-process) has one scenario per subclass that a command can reach, asserting code, stream and the absence of a traceback.

**Changelog.** With [02 X1](02-cross-cutting.md#x1-exit-codes).

**Depends on.** Nothing. **Risks.** Catching too broadly: only `TlaupError` is turned into a message; a bare `except Exception` anywhere else is a lint error once the BLE rules are on ([30 I8](30-ci-and-release.md#i8-lint-rules)).

## G3 Java launcher

Roadmap: "A generic Java tool invocation (jar, classpath, JVM options, main class, arguments, working folder) with a streaming runner, used by TLC and every other tool." Also carries three milestone 1 runner items, designed in [11](11-runner.md): run errors (R1), signals (R2), non-UTF-8 output (R3). Revised 2026-11-20 for the top-up answers ([research 21](../research/21-output-encoding.md), [33](../research/33-inherited-lock.md), [35](../research/35-jvm-ends-with-tlaup.md)) and decisions D51, D52 and D56: the lifeline agent, inherited lock descriptors, the encoding options and the checkpoint row of the signal table; the changes are marked "top-up".

**Problem.** Today there is no launcher: `tlc/runner.py` starts TLC in two copied loops with `text=True`, one pipe for both streams and `KeyboardInterrupt` as the only signal handling; nothing else in the jar can be started at all.

**Design.** `tlaup/java/launcher.py`:

```python
@dataclass(frozen=True)
class JavaInvocation:
    java: Path
    jvm_options: tuple[str, ...]
    system_properties: tuple[tuple[str, str], ...]
    classpath: tuple[Path, ...]
    main_class: str
    args: tuple[str, ...]
    cwd: Path | None = None            # None = do not change folder
    lifeline: bool = True              # top-up, D51: add the lifeline agent; False for --show-command
    def argv(self) -> list[str]        # java, the lifeline, the encoding options, options, -Dk=v ...,
                                       # -cp, joined classpath, main class, args

@dataclass(frozen=True)
class ProcessOutcome:
    exit_code: int                     # what tlaup should exit with (02 X1)
    tool_exit_code: int | None         # what the process returned; None if it never started
    stopped_by: Literal["int", "term", "hup"] | None
    stderr_tail: tuple[str, ...]       # last 50 lines the tool wrote to stderr; empty for a passthrough run

class Signals:                         # the state the handlers write to
    first: Literal["int", "term", "hup"] | None    # the first signal that arrived and was acted on, if any
    first_at: float | None                         # time.monotonic() when it was sent on to the child; the grace period runs from here
    count: int                                     # signals acted on; an unforwarded SIGINT and SIGQUIT are not counted
    leave_interrupt: bool                          # set at entry and never changed: SIGINT is the child's business (repl)
    checkpointing: bool                            # top-up, D52: the parser has seen 2195 and not yet 2196
    held: bool                                     # top-up, D52: a first signal is recorded and waits for the checkpoint
    def checkpoint_started(self) -> None
    def checkpoint_written(self) -> None           # sends a held first signal on: terminate()

@contextmanager
def signals_held(*, leave_interrupt: bool = False) -> Iterator[Signals]

def run_streaming(inv: JavaInvocation, *,
                  on_stdout: Callable[[str], None],
                  on_stderr: Callable[[str], None],
                  signals: Signals,
                  merge_stderr: bool = False,
                  pass_fds: tuple[int, ...] = (),          # top-up, D51: closed by the launcher once Popen has returned
                  on_held: Callable[[Literal["int", "term", "hup"]], None] | None = None,   # a first signal held for a checkpoint
                  grace_seconds: float = 10.0) -> ProcessOutcome

def run_passthrough(inv: JavaInvocation, *, signals: Signals,
                    forward_interrupt: bool,
                    pass_fds: tuple[int, ...] = (),
                    stop_when_reader_gone: bool = False,   # top-up, D58: tlc --raw
                    grace_seconds: float = 10.0) -> ProcessOutcome
```

**Signals.** `signals_held()` installs handlers for SIGINT, SIGTERM and SIGHUP (where the platform has them) and restores the previous ones on exit. The caller holds it round the whole run, not only round the process loop: from before the child starts until the summary is printed and the run folder is dealt with ([11 R2](11-runner.md#r2-signals)). A handler never raises. It records the signal and, if a child is attached, acts on it. The one choice a handler needs, whether a SIGINT is acted on or left to the child, is given when the block is entered (`leave_interrupt`, kept on `Signals`), because the handlers are installed then and a signal can arrive before any run function is called; only `tlaup repl` passes `True`. `run_passthrough` takes the same choice as `forward_interrupt` so that the call reads plainly, and raises `InternalError` when the two disagree (`forward_interrupt` must be `not signals.leave_interrupt`); `run_streaming` requires `leave_interrupt` to be false.

**The JVM of a parsed run has a process group of its own** (decision D60, settled 2026-11-20 from review finding TU1). On Linux and macOS `run_streaming` starts the TLC child with `process_group=0`, so the signals the terminal sends to its foreground group, Ctrl-C (SIGINT), a closed terminal (SIGHUP) and Ctrl-\ (SIGQUIT), reach tlaup alone, and tlaup acts on them as the table below says, the checkpoint row included, and forwards SIGQUIT (below). Before D60 the JVM was in tlaup's group, so a Ctrl-C typed at the terminal reached TLC directly, at the same moment as tlaup, and the deferral of D52 held only signals sent to tlaup alone (a CI system's SIGTERM, `kill <pid>`). It is safe for a parsed run because its JVM never touches the terminal: stdin is the null device and stdout and stderr are pipes, so a background group is never stopped for reading or writing the terminal. Raw runs, the REPL and the standalone `sany` and `pcal` runs (`run_passthrough`, and `run_streaming` with `merge_stderr=True` for `sany` and `pcal`) keep the child in tlaup's group: there the child reads or writes the terminal itself, or is a short run with no checkpoint, and no checkpoint wait applies. Windows is unchanged and stays best effort (D15): a console Ctrl-C reaches every process attached to the console. **A tlaup that hangs** no longer lets a terminal Ctrl-C reach TLC; it is stopped by a second Ctrl-C, which tlaup's handler turns into `kill()` (Python runs a handler between bytecodes and retries an interrupted system call after it, so a blocked read or wait does not hold it back), and, if tlaup itself has to be killed, by the lifeline, which ends the JVM within about two seconds (D51).

For every other signal, and for SIGINT when it is acted on:

| When the signal arrives | What happens |
| --- | --- |
| Before the child exists | It is recorded. The run function checks `signals.first` immediately before starting the child and, if it is set, starts nothing: the run ends with that signal's code after the usual cleanup. A signal that lands while `Popen` is returning is seen when the child is attached and is treated as the next row. "While `Popen` is returning" is everything after that check, so a signal between the check and `Popen` still finds a child started, and stops it a moment later. The child is attached to `Signals` first and `signals.first` is looked at second; in the other order a signal between the two would be recorded and never reach the child. Two signals in that window count as one for the child, which gets `terminate()`. (Made explicit by the formal check, 2026-11-18, [finding K3-2](../../specs/README.md#findings).) |
| While the child runs, first signal | `terminate()` on the child. |
| While the child runs and writes a checkpoint, first signal (a parsed run only; top-up, D52) | This includes a Ctrl-C at the terminal on Linux and macOS, since the JVM has a group of its own (D60). "Writes a checkpoint" means from the moment tlaup has read 2195; a signal that comes while 2195 is still in the pipe or the queue is the row above and is sent on at once (review finding FC8). Recorded and held: `signals.held` is set, nothing is sent, and on its next turn the main thread calls `on_held` with the signal's name, once, never from the handler. The runner turns the name into one line, so nobody takes the wait for an ignored signal: `waiting for TLC to finish writing its checkpoint; press Ctrl-C again to stop now` for SIGINT, and `SIGTERM received: waiting for TLC to finish writing its checkpoint; send it again to stop now` for SIGTERM (SIGHUP likewise); the reporter shows it ([11 R2](11-runner.md#r2-signals) says where). When the parser sees 2196, the runner calls `signals.checkpoint_written()`, which sends `terminate()` and starts the grace period from then. A second signal meanwhile is the next row. The runner marks the checkpoint with `checkpoint_started()` and `checkpoint_written()` from the parser's events for 2195 and 2196 ([10 P3](10-parser.md#p3-result-model)); a raw run never marks one. A child that ends while the mark is set ends the run as usual. |
| While the child runs, a second signal, or the grace period running out | `kill()` on the child. The second signal is acted on in the handler; the grace period is watched by the main thread, which never waits for the child or for a line for more than a fifth of a second at a time and compares the clock with `signals.first_at`. |
| After the child has exited | Recorded only. The summary and the cleanup finish; nothing is interrupted and no traceback is possible. The exit code is the first signal's if it was recorded by the time the launcher saw the child gone (both pipes closed and the wait returned), else the run's own; `ProcessOutcome.stopped_by` is taken at that moment, once. tlaup cannot see more than that: a signal that arrives after the child has ended by itself and before the launcher has noticed counts as having stopped the run. The run is then reported as interrupted, and its folder is settled as an interrupted run's (R6: kept only when the run asked to be kept and its checkpoint is complete), although the run finished. (Formal check, 2026-11-18, [finding K3-1](../../specs/README.md#findings): the first wording, "if it arrived before the child exited", cannot be built.) |

**Formal check, 2026-11-18.** This table and R2 were written as `specs/Signals.tla` and checked with TLC; [the specs' README](../../specs/README.md#signals) says what was modelled and what was found. The check found no flaw in the design and two sentences that said more than can be built, both corrected in the table above. On 2026-11-20 the spec gained the checkpoint row (`Defer`) and a tlaup that dies at any moment with the lifeline ending its child (`TlaupDies`, `ChildEndsWithTlaup`), and was checked again.

*Why the deferral* (top-up, D52; [research 35](../research/35-jvm-ends-with-tlaup.md)). A checkpoint is not atomic: TLC writes `.tmp` files and commits them one by one, and a stop in between, by tlaup's own SIGTERM too, can leave a checkpoint that fails to recover, or one that recovers with exit 0 and silently misses states. Holding the first signal for the few seconds a checkpoint takes keeps tlaup's own signal from causing that; the user who wants out at once presses Ctrl-C again. With D60 the terminal's Ctrl-C is among the signals held, not only those sent to tlaup alone. What the deferral cannot cover, beyond the cases below: a first signal that arrives after TLC has printed 2195 and begun writing `.tmp` files, while the line is still in the pipe or the queue, finds no mark yet and is sent on at once (review finding FC8). It is rare, because TLC prints 2195 just before it writes, and the completeness test then drops the checkpoint, so the cost is a lost checkpoint, not a wrong result. It applies to every first signal tlaup acts on, SIGTERM and SIGHUP as well as SIGINT, because every other row of this table treats the three alike. The check that a kept checkpoint is complete ([11 R6](11-runner.md#r6-run-folders)) covers what the deferral cannot: raw runs, crashes, kills and second signals.

*The steps, one call each* (decision D46). `run_streaming` and `run_passthrough` are loops over these, and the stateful test calls them one at a time, sending signals in between ([03](03-run-stages-and-specs.md#specs-and-their-tests)). `signals_held` takes the clock that stamps `first_at`, so the test can run the grace period out without waiting.

```python
@contextmanager
def signals_held(*, leave_interrupt: bool = False, clock=time.monotonic) -> Iterator[Signals]

class ChildRun:                                    # one child under signals_held
    def __init__(self, inv: JavaInvocation, signals: Signals, *, on_stdout=None, on_stderr=None,
                 on_held=None, merge_stderr: bool = False, passthrough: bool = False,
                 grace_seconds: float = 10.0, clock=time.monotonic): ...
    pid: int | None
    def may_start(self) -> bool                    # looks at signals.first; False: nothing is started
    def spawn(self) -> None                        # Popen; raises ToolStartError
    def attach(self) -> None                       # attach to signals, then look at signals.first: terminate()
    def turn(self, timeout: float = 0.2) -> bool   # one turn of the loop; True when the child is gone and its pipes are closed
    def stop(self) -> None                         # the finally round the loop: stop the child, empty the queue
    def outcome(self) -> ProcessOutcome            # takes stopped_by from signals.first; the same answer every time
```

Why the last row matters: research 15 measured the JVM exiting in under a second after the first signal, so a second Ctrl-C from an impatient user usually arrives after the process loop has ended. With handlers held only for the loop it would hit Python's default handler during the summary.

Three rules about which signals get a handler:

- **A signal that is ignored when `signals_held` is entered is left ignored**: no handler is installed for it and nothing is restored for it. `nohup tlaup tlc Spec &` starts tlaup with SIGHUP ignored, and a shell script that starts tlaup in the background starts it with SIGINT ignored; a handler installed regardless would undo what the caller asked for and stop TLC at the hangup `nohup` exists to survive. The child inherits the ignore as it would have from the caller directly. Tried on Linux with a sketch of this function: under `nohup` the SIGHUP handler was not installed, a SIGHUP sent to the process changed nothing, and a child started inside the block had SIGHUP ignored; started as a background job of `sh -c`, the same for SIGINT.
- **The handlers tlaup does install are Python functions, never `SIG_IGN`.** A disposition of "ignore" set before the child starts is inherited by it, and a JVM started that way does not install its own handler (research 17, "A caveat on SIGINT"); a Python handler is reset to the default in the child when it is started.
- **SIGQUIT gets a handler that does nothing**, or, in a parsed run whose JVM has a group of its own (D60), **a handler that forwards it to the JVM** (`os.kill(child.pid, SIGQUIT)`), so that Ctrl-\ still gives a thread dump; either way it is not recorded and counts as no signal. The rest of this paragraph is about the runs whose child shares tlaup's group. `Ctrl-\` in a terminal sends SIGQUIT to the whole foreground group. The JVM answers it with a thread dump on its stdout and carries on, which is the usual way to see what a long TLC run is doing; Python's default is to die, which would leave the JVM running with nobody reading its pipes. With the handler tlaup survives and the JVM, which gets the default disposition and installs its own handler, prints its dump. SIGQUIT is not recorded in `Signals`, does not count as a first or second signal, and is not forwarded: sent to tlaup alone it does nothing, and the dump is asked of the JVM's own process. Tried on Linux with Java 25 and a class that sleeps: with the do-nothing handler in the parent, a SIGQUIT to both processes left the parent alive, the JVM printed "Full thread dump" and ended normally with 0. The same run with `SIG_IGN` in the parent gave the same result on that Java, so the choice of a handler over "ignore" rests on the rule above, not on a difference seen. Not tried: other Java versions, a real terminal, TLC itself. In a parsed run the dump arrives on TLC's stdout between or inside `-tool` messages and is shown as text the parser does not recognise ([10 P4](10-parser.md#p4-framing-and-never-losing-output)); how it reads when it lands inside a message was not tried.

**`run_streaming`.**

- Starts the process with `subprocess.Popen(argv, cwd=..., stdin=DEVNULL, stdout=PIPE, stderr=PIPE, pass_fds=pass_fds, process_group=0)` in binary mode, then closes the descriptors in `pass_fds` (they are duplicates the caller made for the child, [11 R6](11-runner.md#r6-run-folders)), then attaches the child to `signals`. `process_group=0` (Python 3.11 and later) on Linux and macOS for a TLC run (D60); not on Windows, and not with `merge_stderr=True` (`sany`, `pcal`). Never with `preexec_fn` (see "The lifeline"); `process_group` is done by `subprocess` itself, with no Python code between `fork` and `exec`.
- **A closed stdout** (top-up, D58; review finding TU2). At each turn of the loop, every fifth of a second, the main thread also asks `reader_gone(1)` ([14 F10](14-config-and-cli.md#f10-no-tracebacks)). tlaup's own write to stdout would show a closed pipe too, but in plain mode a clean run writes nearly nothing to stdout until its result, and progress goes to stderr (D30), so without the poll `tlaup tlc Spec | head` on a long run would run TLC to its end unseen. When the reader has gone, the child is stopped as for a closed pipe in `run_passthrough` (below), and the run ends with 141.
- Two reader threads split each pipe into lines (on `\n`, keeping the line ending) and put `(stream, bytes)` on a queue, and an end marker when their pipe closes. The queue is bounded (10,000 lines): when the main thread falls behind, the readers block, the pipe fills and the JVM waits, so a slow reporter cannot make memory grow without limit. The main thread takes from the queue with a timeout of a fifth of a second (so it can watch the grace period, see the table), decodes each line with `decode("utf-8", errors="replace")`, and calls `on_stdout` or `on_stderr`. Decoding cannot raise (R3). All parsing and printing happens on the main thread, so the parser and reporter need no locks.
- **Leaving the loop early.** `on_stdout` or `on_stderr` can raise (a closed pipe while the reporter prints, an error in the parser). The main thread then stops taking from the queue while a reader may be blocked putting into it, and a blocked thread that is not a daemon keeps the interpreter from exiting: tlaup would hang for ever with TLC already stopped. So a `finally` round the loop does three things in order: it stops the child if it is still running (`terminate()`, then `kill()` after the grace period); it empties the queue, throwing the lines away, until both readers have delivered their end marker or two seconds have passed; and it lets the exception go on. The reader threads are daemon threads as well, so a pipe that some other process still holds open after the child has gone cannot keep tlaup alive past those two seconds. Tried with a sketch of this loop, a bound of 10 and a child printing 5,000 lines on each stream and then sleeping: with the consumer raising at the fifth line the process ended at once with both readers finished; the same shape with ordinary threads and no emptying, which was the first revision of this section, hung until killed. With a consumer that does not raise all 10,000 lines arrived and the queue never held more than the bound.
- Lines keep their line ending (`\n` or `\r\n`) when handed to `on_stdout`; the parser strips it. This is the form the golden tests feed ([01 T3](01-testing.md#t3-golden-files)).
- With `merge_stderr=True` the child's stderr is the same pipe as its stdout (`stderr=STDOUT`), one reader thread runs, and every line arrives through `on_stdout` in the order the tool wrote it. Only `sany` and `pcal` use it ([21 S1](21-other-tools.md#s1-sany)): SANY splits one diagnostic across the two streams on v1.7.4, and the research captured both tools this way. TLC is always read with two pipes.
- The loop keeps draining until both pipes close, so the reporter sees everything the tool managed to print (R2).
- The outcome's `exit_code` is 130, 143 or 129 when a signal stopped the run; otherwise the tool's return code; a negative return code `-n` (killed by a signal tlaup did not send) becomes `128 + n`.
- Errors starting the process become `ToolStartError` with the operating system's own message (R1).

**`run_passthrough`.** For `tlc --raw`, `repl` and, in milestone 4, the generic exec command. The child inherits tlaup's stdin, stdout and stderr; nothing is read or decoded. SIGTERM and SIGHUP are always forwarded as in the table above. SIGINT depends on `forward_interrupt`:

- `True` (`tlc --raw`): SIGINT is treated as in the table: the first terminates the child, the second kills it. A SIGINT sent to tlaup alone (a CI system, a test) therefore stops TLC. In a terminal the child also receives the Ctrl-C itself; getting both signals is what the parsed path does too.
- `False` (`repl`, whose block was entered with `leave_interrupt=True`): the handler does nothing at all with a SIGINT, from the moment the block is entered, so also in the instant before the child exists. It does not touch the child, does not set `signals.first` and does not count it. In a terminal the child receives Ctrl-C itself and decides what it means (the REPL may only cancel the line). Because nothing is recorded, a REPL that is later quit normally exits with its own code, not 130, and a later SIGTERM is the first signal, not the second, so it terminates the child and does not kill it. If the Ctrl-C does end the child, tlaup returns what the child returned (research 15: a JVM stopped by SIGINT returns 130). A SIGINT sent to tlaup alone is not passed on; SIGTERM is the way to stop it from outside.

The main thread waits for the child in steps of a fifth of a second, for the same reason as the queue's timeout. With `stop_when_reader_gone` (only `tlc --raw` passes it; top-up, D58) each step also asks `reader_gone(1)` ([14 F10](14-config-and-cli.md#f10-no-tracebacks)): when tlaup's stdout is a pipe whose reader has gone, the child is stopped as for a first signal (`terminate()`, then `kill()` after the grace period) and the outcome's code is 141 ([11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are)). On Windows `reader_gone` is always false and the child runs on. `run_passthrough` takes `pass_fds` as `run_streaming` does, and always leaves the child in tlaup's process group (D60).

*A stop for a closed pipe, and the signals* (review finding FC9), the same in both functions. It is not a signal: `Signals.first` stays unset, `ProcessOutcome.stopped_by` is `None`, and the outcome records `stopped_for_closed_pipe`. It sends `terminate()` and starts the grace period from then, as a first signal does, so a signal that comes after it is acted on as a second one: `kill()` at once. The exit code is the first stop's: 141 when the closed pipe was seen first, the signal's (130, 143, 129) when a signal was recorded before it. A closed pipe seen while a first signal is held for a checkpoint does not wait: the reader is gone, nobody can use the result, and `terminate()` is sent at once. Returns a `ProcessOutcome` with an empty `stderr_tail`; the exit code is mapped as for `run_streaming`.

**The lifeline** (decision D51, top-up; [research 35](../research/35-jvm-ends-with-tlaup.md)). Every JVM the launcher starts, for `tlc`, `sany`, `pcal` and `repl`, carries a small Java agent, `-javaagent:<lifeline jar>=pid=<tlaup's pid>`, first among the JVM options. Its premain starts a daemon thread that looks up tlaup's process with `ProcessHandle.of(pid)` and polls `isAlive()` every 500 milliseconds; when tlaup is gone, or was already gone when the agent started, it calls `System.exit(143)`. So the JVM ends within about two seconds of tlaup however tlaup ended, SIGKILL and crashes included (0.1 to 1.6 seconds were measured on Linux, macOS and Windows, both builds: with Java 25 and 11 on Linux and Java 21 on the three CI runners, also with `-Xrs` among the user's options; Java 11 on macOS and Windows was tried for the kill check alone; `tlaup repl` on a terminal was driven on Linux and macOS, not on Windows; review finding TU9). `isAlive` compares the process's start time as well as its id, so a reused process id is not taken for tlaup. The agent touches no stream, no descriptor and no signal disposition, so the REPL's stdin, the inherited lock descriptors of R6 and the signal table above are unchanged; its exit code 143 is never seen by anyone, since tlaup is gone. A `-javaagent` or a `-metadir` of the user's does not disturb it. Its cost was 19 to 43 milliseconds at start-up and a poll every half second.

- *The jar.* `tlaup/java/lifeline.jar`, package data in the wheel, a few kilobytes; its Java source is in the repository beside it, compiled with `--release 11`. It is never compiled on the user's machine, which may have only a JRE: the jar is checked in (settled 2026-11-24 with package 06, a low-impact choice the first design left to the package), and a CI test, the lifeline job of [30 I2](30-ci-and-release.md#i2-unit-job), compiles the source and compares the class files with those in the jar on every push, so a binary nobody can read is never shipped and every test run and every wheel has the same bytes. Building it in the release workflow instead was the other option; it would have needed a JDK in every job that builds a wheel. (Stage 4 review, 2026-11-24: the choice recorded here, finding F7.)
- *`--show-command` leaves it out* (`lifeline=False`): a pasted command would carry the process id of a tlaup that has exited, and its JVM would stop at once ([11 R9](11-runner.md#r9-show-command)).
- *No `preexec_fn`.* Nothing in the launcher runs Python code between `fork` and `exec`: the lifeline needs none, and with it Python runs `filelock`'s at-fork hooks, which close the descriptors the child is meant to inherit ([research 33](../research/33-inherited-lock.md)).

**Encoding** (decision D56, top-up; [research 21](../research/21-output-encoding.md)). `argv()` always puts `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` after the lifeline and before the JVM options of the setting `java.opts`, `TLAUP_JAVA_OPTS` and `--java-opt`, for every Java tool tlaup starts: `tlc`, `sany`, `pcal` and `repl`. Each of the three is needed: Java 11 honours only `file.encoding`, which is also what makes v1.7.4 read a UTF-8 spec correctly on Java 11 and keeps the PlusCal translator from writing `?` into the user's file; Java 18 and later read the two stream properties. Unknown `-D` properties are not an error on any supported Java, so no version check is needed. Before the user's options, so that a user can still override one (the JVM takes the last value); not in the default of `java.opts`, because a user who sets that setting would lose them without noticing. With them TLC writes UTF-8 on every system and locale tried, and the launcher's decoding as UTF-8 with replacement is the guard for what they do not reach. Non-ASCII file names under a C locale are not fixed by any JVM option; [11 R3](11-runner.md#r3-non-utf-8-output) gives a hint for them.

**Rejected.**

- *`text=True` on `Popen`* (today): raises `UnicodeDecodeError` on a byte that is not UTF-8.
- *One pipe with `stderr=STDOUT` for TLC* (today): see [02 X2](02-cross-cutting.md#x2-stdout-and-stderr). It is kept as an option for SANY and the PlusCal translator only, for the reason above.
- *`KeyboardInterrupt` for control flow* (today): a second Ctrl-C lands in the drain loop and escapes; SIGTERM is not an exception at all, so the JVM is orphaned (research 15, reproduced twice).
- *Handlers installed inside `run_streaming` only*: see the last row of the table.
- *Ignoring SIGINT with `SIG_IGN` during a passthrough run*: inherited by the JVM, which then cannot be stopped with Ctrl-C.
- *Keeping the JVM of a parsed run in tlaup's process group* (the first design, until D60): the terminal's Ctrl-C reached TLC directly, so the checkpoint deferral could not hold it. The first design's reasons for one group were that tlaup would be the only way to stop the JVM, and that a tlaup killed with SIGKILL would leave it running with no terminal attached; the lifeline answers the second, and a second Ctrl-C and the lifeline answer the first.
- *A process group of its own for every child*: a raw run's child and the REPL use the terminal themselves, and a background group is stopped (SIGTTIN, SIGTTOU) when it reads or writes the terminal; the REPL also wants the terminal's Ctrl-C (D60).
- *Narrowing D52 to signals sent to tlaup alone*: the other option the review gave for TU1; the interactive Ctrl-C is the case D52 was settled for.
- *Other ways to end the JVM with tlaup* (research 35, all tried). The parent-death signal (`prctl(PR_SET_PDEATHSIG)`): Linux only, needs `preexec_fn` or `setpriv`, and fires when the *thread* that started the child ends, which killed a JVM while tlaup lived on. An agent that waits for end of file on a pipe or on stdin: every JVM exit takes 0.35 to 1.7 seconds longer, and stdin collides with the REPL. A watcher process: a second process to start and keep alive, and on Linux uv's Python lacks the pidfd calls. A Windows job object that kills on close: Windows only, a second code path for what the agent does. `ProcessHandle.onExit()` instead of polling: up to five seconds late after a long run.
- *The encoding options in the default of `java.opts`*: lost by anyone who sets the setting. *Only `-Dsun.stdout.encoding` and `-Dsun.stderr.encoding`*: undocumented, and they do not fix reading the spec or the translator's file. *Setting `LC_ALL=C.UTF-8` in the child's environment*: see R3.
- *An unbounded queue*: moves the memory problem of [22 O7](22-reporters.md#o7-rendering-cost-and-memory) into the launcher.
- *A bounded queue with ordinary reader threads and no emptying on the way out*: hangs when the consumer raises (tried, see above).
- *Installing the handlers whatever the disposition on entry*: breaks `nohup` and background jobs (tried, see above).
- *Recording a SIGINT that is left to the child*: a REPL quit normally after one Ctrl-C would exit 130, and a later SIGTERM would kill instead of terminate.
- *Forwarding SIGQUIT to a child in tlaup's process group*: in a terminal the JVM already gets it, and would print two dumps. A parsed run's JVM, in a group of its own (D60), gets it only by forwarding.
- *`asyncio`*: two threads and a queue are simpler and the rest of the program is synchronous.

**Tests.**

- Feature, real processes (`tlc_signals.feature`; tlaup started with `sys.executable -m tlaup`, the fake `java` hanging after a given line; the signal is sent to the tlaup process only, not to its process group, so the scenario proves forwarding): SIGTERM gives 143 and the fake has exited; one SIGINT gives 130; two SIGINTs one after the other give 130 with no traceback and the fake has exited; the output printed before the signal is on stdout; the final line says the run was interrupted. These scenarios do not say where the second signal lands; from outside the process that cannot be arranged.
- The two cases that need a signal at an exact moment are plain pytest tests in the test process's main thread, which drive `run_tlc` with the fake `java` and a reporter that sends the signal to its own process from a callback (the handler runs before the callback returns). A reporter whose `start` sends SIGTERM: the fake's log stays empty, the outcome's code is 143 and no run folder is left. A reporter that sends SIGINT on the first event and again from `finish`: the second signal lands during the summary, which is the case that used to lose it; `finish` returns normally, the code is 130 and the fake has exited.
- Unit, `signals_held`, each in a child Python process so the test runner's own dispositions are not touched: started with SIGHUP ignored, the block installs no SIGHUP handler and leaves it ignored afterwards; SIGQUIT sent inside the block does not end the process and leaves `Signals` unchanged; a SIGINT inside a block entered with `leave_interrupt=True`, before any child exists and again while one runs with `forward_interrupt=False`, leaves `first` unset and `count` at 0, and a SIGTERM after it terminates the child and gives 143. `run_passthrough` called with a `forward_interrupt` that disagrees with the block raises `InternalError`.
- The same three signals for `tlc --raw`, real processes: the codes are the same and the fake has exited.
- Unit, with the fake `java` as a real child of the test process: invalid UTF-8 bytes in stdout arrive as replacement characters and the run completes; 100,000 lines (ten times the bound) arrive in order with a slow `on_stdout` and the queue never holds more than its bound; an `on_stdout` that raises at the fifth of 100,000 lines makes `run_streaming` raise that exception within a few seconds, with the fake exited and no reader thread alive; a fake that ignores SIGTERM is killed when the grace period (set to half a second) runs out; text on stderr arrives through `on_stderr` only; a missing executable raises `ToolStartError` whose message does not say "not found" unless the file is missing; a file without execute permission says "permission denied"; a `Signals` with `first` already set starts nothing. The two start failures can only be shown here, by calling the launcher with a path: through the command line a `java` that is missing or not executable is never found, and the result is `JavaNotFound`, code 3 ([13 J2](13-modules-and-java.md#j2-finding-java)).
- Feature, real process (`tlc_raw.feature`): passthrough keeps the two streams apart, byte for byte, and returns the fake's code. This cannot run in-process: the child inherits the real file descriptors, which the in-process runner does not capture ([01 T5](01-testing.md#t5-feature-files-and-steps)).
- Stateful (`tests/stateful/test_signals.py`): the Hypothesis state machine that mirrors [the spec](../../specs/README.md#signals) on the steps above. The test process is the tlaup of the spec: it enters `signals_held`, runs a real child a step at a time and sends itself real signals in between, never where Python's default handler would get them. One plain test confirms with a second Python process that a signal from outside is recorded as one the process sends itself. Written before the code and marked `pending` ([03](03-run-stages-and-specs.md#specs-and-their-tests)). Its fake child has a SIGQUIT handler that notes the signal and carries on, and in a streaming run, whose child the launcher forwards SIGQUIT to (D60), the machine asserts the note; without the handler a launcher that follows this section would kill the fake.
- Integration (T9): the same signal scenarios with the real JVM, including "no `java` process is left".
- Unit, `argv()` (top-up): the lifeline comes first and names `os.getpid()`; the three encoding options come next, before the setting's options, `TLAUP_JAVA_OPTS` and `--java-opt`, so that a user's `-Dfile.encoding=ISO-8859-1` comes last; `lifeline=False` leaves the agent out and keeps the encoding options; the same order for `tlc`, `sany`, `pcal` and `repl`.
- The lifeline, with a real JVM (Temurin 11 in the lifeline job of [30 I2](30-ci-and-release.md#i2-unit-job), Linux and macOS; the shipped jar): a parent Python process starts `java -javaagent:<jar>=pid=<parent> <a class that sleeps>` and is killed with SIGKILL (on Windows, ended with `TerminateProcess`); the JVM is gone within three seconds. Started with the id of a process that has already exited, the JVM exits at once. A reused process id, on Java 11, since the agent rests on `isAlive` comparing start times: a stand-in in a small process-id namespace (`unshare --pid --fork`, where ids come round quickly) takes a handle as the agent does, ends that process, starts processes until one has the same id, and asserts that the handle's `isAlive()` is false (Linux only; the idea is to confirm the JDK's behaviour, not to test tlaup). With `-Xrs` the same. Under a pseudo-terminal with `tlaup repl`'s arguments, the REPL still reads a line from stdin.
- Unit, `pass_fds` (Linux and macOS): a descriptor passed is open in the child and closed in the parent after `Popen`; with R6's lock tests this shows the inherited lock.
- Unit, the checkpoint row: a fake `java` that prints 2195, sleeps, prints 2196 and then waits; a SIGINT between the two sets `held` and sends nothing until 2196, after which the fake gets SIGTERM; a second SIGINT before 2196 kills it at once; the grace period starts at 2196, not at the signal; `on_held` is called once, from the main thread, with the signal's name, and the runner's line names it (a SIGTERM gets its own wording).
- Feature, real processes on a pseudo-terminal (D60; review finding TU1), Linux and macOS: tlaup runs `tlaup tlc Spec` as the terminal's foreground job (`in a terminal`, [01 T5](01-testing.md#t5-feature-files-and-steps)), and the fake `java` logs every signal it receives ([01 T4](01-testing.md#t4-fakes-at-the-edges)), prints 2195, writes `.tmp` files and waits for its release (T4's `checkpoint` with a `release_file`), and hangs after 2196. `press Ctrl-C once java has begun its checkpoint` (the step of [01 T5](01-testing.md#t5-feature-files-and-steps) that waits for the fake's marker, and gives the release once the terminal shows the waiting line) makes the terminal send SIGINT to its foreground process group: the fake logs nothing, its process group differs from tlaup's, and the terminal shows the waiting line; when the fake, released, then commits and prints 2196 it gets SIGTERM, and the run ends with 130 and a complete checkpoint. `press Ctrl-\` logs SIGQUIT in the fake and changes nothing else. The same with `--raw`: the fake logs the SIGINT itself, in tlaup's group.
- Feature, real process with a real pipe (TU2): `tlaup tlc Spec | <a reader that exits after one line>`, with a fake that prints its banner and then nothing on stdout for a minute: tlaup exits 141 within a few seconds and the fake got SIGTERM. Unit: a closed pipe seen first and then a SIGINT gives 141 and a `kill()`; a SIGINT and then a closed pipe gives 130 (FC9).

**Changelog.** Fixed: "Stopping `tlaup tlc` with SIGTERM (for example a CI timeout) now stops TLC too; it used to keep running." "A second Ctrl-C no longer loses the summary." "Output that is not valid UTF-8 no longer crashes tlaup." "If tlaup is killed, the Java tool it started stops within about two seconds." "TLC, SANY, PlusCal and the REPL now always write UTF-8; under a C locale non-ASCII characters were printed as `?`, and with Java 11 and v1.7.4 the PlusCal translator wrote them as `?` into the spec." Changed: "Ctrl-C exits with 130." The entry for a first Ctrl-C during a checkpoint is [11 R6](11-runner.md#r6-run-folders)'s. (Stage 4 review, 2026-11-24: a held first signal reaches the runner through `on_held`, and its line goes through the reporter, question Q12; the signals machine's fake child survives SIGQUIT, question Q5; the pseudo-terminal scenario waits for the fake's checkpoint marker, question Q10, and the fake waits for the step's release and hangs only after 2196, finding E1, settled with the maintainer on 2026-11-24; the second entry for the checkpoint wait was dropped, index "Clerical".)

**Depends on.** G2. **Risks.** (D60) Ctrl-Z stops tlaup alone; the JVM of a parsed run runs on until its pipes fill and then waits, and `fg` resumes both. Forwarding SIGTSTP is not designed. A process that signals tlaup's group from outside (`kill -INT -<pgid>`) no longer reaches the JVM of a parsed run directly; tlaup forwards. (Top-up) The lifeline costs 20 to 40 milliseconds per Java start and needs the agent jar in the wheel; a broken or missing jar would stop every Java start, which the package's own test of the jar catches. On Windows the lifeline is the only thing that ends an orphan JVM, and the run's lock does not follow it (R6). Through the macOS `/usr/bin/java` stub the JVM keeps the stub's process id ([research 28](../research/28-java-11-and-macos-java.md)), so signals reach it directly and nothing here changes. A user option that overrides an encoding property wins, by design. A checkpoint that takes long holds a first signal as long; a CI system that sends SIGKILL a few seconds after SIGTERM then kills tlaup, and the lifeline ends TLC, in the middle of the checkpoint, which the completeness test of R6 then catches. The rest, from the first wave: The handlers do not raise, so a main thread that is blocked writing tlaup's own output into a pipe whose reader is alive and not reading (`tlaup tlc Spec | less`, with the pager's screen full) stays blocked after Ctrl-C: the child is stopped, but tlaup ends only when the reader reads or quits, and then with 141 rather than 130. Not tried; found by reasoning in the third revision. It is how the write behaves under Python's retry of an interrupted call, and it is accepted for the first wave; [14 F10](14-config-and-cli.md#f10-no-tracebacks) covers only the last flush. Signal handlers can only be set on the main thread; `signals_held` is only entered there, and it raises `InternalError` otherwise. A caller that starts tlaup with SIGINT or SIGTERM ignored gets a run tlaup cannot stop on that signal, and a JVM that inherits the ignore; that is what the caller set up, and it is how `java` itself would behave there. The two seconds allowed for emptying the queue on the way out are a guess; they bound how long an error takes to show when another process holds TLC's pipe open. On Windows there is no SIGTERM or SIGHUP to receive, and `terminate()` kills at once; decision D15 accepts this. The grace period delays exit by up to 10 seconds if the JVM ignores SIGTERM; research 15 measured under one second. What a JVM does when it gets SIGINT from the terminal and SIGTERM from tlaup almost together is the race research 15 saw (130 or 143 from the JVM); tlaup sets its own code, so the race does not show. Not run on macOS or with a real terminal (research 15 lists both as untested).
