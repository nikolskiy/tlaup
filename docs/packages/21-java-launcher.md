# 21. The Java launcher

Size: L. Suggested model: most capable. Status: waiting on question "SIGQUIT in the signals machine" for one edit of `tests/stateful/test_signals.py` (see "Context for the worker", "The open question"); everything else is ready.

## Goal

`tlaup/java/launcher.py` exists and can start any Java tool from a `JavaInvocation`: reading its output line by line or passing the terminal through, with the signal handling, the lifeline, the encoding options, the process group and the closed-pipe stop of [20 G3](../design/20-groundwork.md#g3-java-launcher). The stateful test of the Signals spec passes against it. No command uses it yet; `tlaup tlc` still runs through the old runner.

## Covers

- Roadmap items:
  - "A generic Java tool invocation (jar, classpath, JVM options, main class, arguments, working folder) with a streaming runner, used by TLC and every other tool." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)), in part: the launcher. Its use by TLC is [37](37-run-tlc.md) and [39](39-tlc-command.md), by the other tools [41](41-sany-command.md) to [43](43-repl-command.md).
  - "The lifeline agent (decision D51) ... added by the launcher to every Java start ..." (milestone 1b), in part: `argv()` adds it. The agent and its jar are [06](06-lifeline-agent.md), the CI job [53](53-ci-workflows.md).
  - "Forward SIGTERM to the JVM so a CI timeout does not leave TLC running; exit 130 on Ctrl-C; survive a second Ctrl-C while draining output." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the mechanism. Holding the handlers round the whole run is [37](37-run-tlc.md); the scenarios are [39](39-tlc-command.md).
  - "Report run errors as what they are." (milestone 1), in part: `ToolStartError`, and stopping the child when the reader of stdout has gone. The rest is 37, 39 and [17](17-error-handler.md).
  - "Do not crash on non-UTF-8 bytes in TLC output." (milestone 1), in part: reading bytes, decoding with replacement, the three encoding options. The rest is [33](33-tlc-invocation.md) (the hint) and [16](16-ui-messages.md) (tlaup's own streams).
- Design sections:
  - [20 G3](../design/20-groundwork.md#g3-java-launcher): all of it except the agent and its jar ([06](06-lifeline-agent.md)) and the tests listed under "Out of scope".
  - [11 R1](../design/11-runner.md#r1-run-errors-reported-as-what-they-are), [R2](../design/11-runner.md#r2-signals), [R3](../design/11-runner.md#r3-non-utf-8-output): the launcher's side of each; "Context for the worker" draws the line to the runner ([37](37-run-tlc.md)).
  - [03, "Specs and their tests"](../design/03-run-stages-and-specs.md#specs-and-their-tests) and [K3](../design/03-run-stages-and-specs.md#k3-signals): this package is the one that builds the code of `tests/stateful/test_signals.py`.

## Depends on

- [02](02-errors-and-paths.md): `ToolStartError` and `InternalError` (family `Failed`, code 5) from `tlaup/errors.py`.
- [03](03-test-foundation.md): the isolation fixture; the fake `java` of `tests/fakes/` and its log ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)); `hypothesis` as a development dependency and the pytest settings (`pending`, coverage of child processes).
- [06](06-lifeline-agent.md): `src/tlaup/java/lifeline.jar`, whose path `argv()` names.
- [17](17-error-handler.md): `reader_gone(fd) -> bool` ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)). Added to the draft's list by stage 4: G3 and R1 poll it from both run functions. The design does not say which module holds it, and the launcher must not import `tlaup.cli` (it would pull Typer in and point the wrong way). If 17 left it in `cli.py`, move it, with `is_pipe` if it needs it, to a module that imports neither Typer nor Rich, and say so in the pull request.

## Files

Creates:

- `src/tlaup/java/launcher.py`.
- `tests/unit/java/test_launcher.py` (the run functions with the fake `java`), `tests/unit/java/test_launcher_argv.py`, `tests/unit/java/test_signals_held.py` (the tests that run in a child Python process). One file or three is the worker's choice.

Changes:

- `tests/stateful/test_signals.py`: first commit, remove the two `pending` markers; then delete what belonged to the throwaway model (below) and bring the module's docstring up to date.
- `specs/README.md`, "The stateful tests": one sentence that the signals machine now runs against `tlaup.java.launcher` and that `reference_launcher.py` and its tests are gone. The README names the file as present.
- `tests/fakes/java` (the fake of package 03), only if one of the fields checked under "The fake `java`" below is missing; each added field needs its reason in the pull request ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges), Risks).
- The module that holds `reader_gone`, only in the case named under "Depends on".

Deletes:

- `tests/stateful/reference_launcher.py`.
- In `tests/stateful/test_signals.py`: `reference_impl`, `test_signals_machine_against_the_reference_model`, `test_a_signal_from_this_process_stands_for_one_from_outside_reference_model`, `test_child_ends_with_tlaup_reference_model`, `test_without_the_lifeline_the_child_runs_on_reference_model`, and with the last two `STAND_IN`, `tlaup_dies`, `STEPS` and the `LIFELINE_PID` branch of `FAKE_CHILD`, which only the throwaway model sets.

No file of the old suite is deleted: `tests/unit/tlc/test_runner.py` and `test_raw.py` test the old runner and go with it in [39](39-tlc-command.md).

Shared with other packages of the groundwork track: none under `src/`. [20](20-java-location.md) adds `locate.py` to the same folder.

## Interfaces

Provides, from [20 G3](../design/20-groundwork.md#g3-java-launcher):

```python
# tlaup/java/launcher.py
@dataclass(frozen=True)
class JavaInvocation:
    java: Path
    jvm_options: tuple[str, ...]
    system_properties: tuple[tuple[str, str], ...]
    classpath: tuple[Path, ...]
    main_class: str
    args: tuple[str, ...]
    cwd: Path | None = None            # None = do not change folder
    lifeline: bool = True              # D51: add the lifeline agent; False for --show-command
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
    first_at: float | None                         # the clock when it was sent on to the child; the grace period runs from here
    count: int                                     # signals acted on; an unforwarded SIGINT and SIGQUIT are not counted
    leave_interrupt: bool                          # set at entry and never changed: SIGINT is the child's business (repl)
    checkpointing: bool                            # D52: the parser has seen 2195 and not yet 2196
    held: bool                                     # D52: a first signal is recorded and waits for the checkpoint
    def checkpoint_started(self) -> None
    def checkpoint_written(self) -> None           # sends a held first signal on: terminate()

@contextmanager
def signals_held(*, leave_interrupt: bool = False, clock=time.monotonic) -> Iterator[Signals]

class ChildRun:                                    # one child under signals_held
    def __init__(self, inv: JavaInvocation, signals: Signals, *, on_stdout=None, on_stderr=None,
                 merge_stderr: bool = False, passthrough: bool = False,
                 grace_seconds: float = 10.0, clock=time.monotonic): ...
    pid: int | None
    def may_start(self) -> bool                    # looks at signals.first; False: nothing is started
    def spawn(self) -> None                        # Popen; raises ToolStartError
    def attach(self) -> None                       # attach to signals, then look at signals.first: terminate()
    def turn(self, timeout: float = 0.2) -> bool   # one turn of the loop; True when the child is gone and its pipes are closed
    def stop(self) -> None                         # the finally round the loop: stop the child, empty the queue
    def outcome(self) -> ProcessOutcome            # takes stopped_by from signals.first; the same answer every time

def run_streaming(inv: JavaInvocation, *,
                  on_stdout: Callable[[str], None],
                  on_stderr: Callable[[str], None],
                  signals: Signals,
                  merge_stderr: bool = False,
                  pass_fds: tuple[int, ...] = (),          # D51: closed by the launcher once Popen has returned
                  grace_seconds: float = 10.0) -> ProcessOutcome

def run_passthrough(inv: JavaInvocation, *, signals: Signals,
                    forward_interrupt: bool,
                    pass_fds: tuple[int, ...] = (),
                    stop_when_reader_gone: bool = False,   # D58: tlc --raw
                    grace_seconds: float = 10.0) -> ProcessOutcome
```

`run_streaming` and `run_passthrough` are loops over the steps of `ChildRun` (decision D46); the stateful test calls the steps one at a time.

Written by stage 4, each from what the design says in words. They are the intended shape, as the rest is; change a name if a better one shows, and say so.

- **`ProcessOutcome.stopped_for_closed_pipe: bool = False`.** G3: a stop for a closed pipe "is not a signal: `Signals.first` stays unset, `ProcessOutcome.stopped_by` is `None`, and the outcome records `stopped_for_closed_pipe`". The dataclass as written has no such field; `RunOutcome` of [37](37-run-tlc.md) copies it. The design does not say what the field holds when a signal was recorded first and the closed pipe was seen second; the exit code is then the signal's.
- **`pass_fds` and the closed-pipe poll reach `ChildRun`.** The two run functions take `pass_fds` and `stop_when_reader_gone`; `ChildRun.__init__` as written takes neither. Give it both as keyword arguments. `run_streaming` always polls ("at each turn of the loop ... the main thread also asks `reader_gone(1)`"); `run_passthrough` only with `stop_when_reader_gone`.
- **`reader_gone` can be passed in.** [11 R1](../design/11-runner.md#r1-run-errors-reported-as-what-they-are) asks for a unit test of `run_passthrough` "with `reader_gone` injected false (the Windows case)". Both run functions and `ChildRun` take `reader_gone: Callable[[int], bool]` with the real function as the default.
- **`on_held`, for the waiting line.** G3's table says that when a first signal is held, "the main thread prints on its next turn, on stderr, one line that names the signal". [03](../design/03-run-stages-and-specs.md#specs-and-their-tests) and the stateful test say that line is "the runner's, not the launcher's", and only the runner has a way to print (`notice`, [11](../design/11-runner.md)); but the runner gets a turn only when a line arrives, and TLC may be silent while it writes. So `run_streaming` and `ChildRun` take `on_held: Callable[[Literal["int", "term", "hup"]], None] | None = None`, called once per held signal, from the main thread, on the first turn after the handler set `held`, never from the handler. Package 37 passes a function that turns the name into G3's wording and prints it.

Consumes: `ToolStartError`, `InternalError` ([02](02-errors-and-paths.md)); `reader_gone` ([17](17-error-handler.md)); the jar ([06](06-lifeline-agent.md)).

Consumed by: [33](33-tlc-invocation.md) (`build_tlc_command` returns a `JavaInvocation`), [35](35-run-folders.md) (`RunFolder.lock_fds` goes into `pass_fds`), [37](37-run-tlc.md) (`signals_held`, both run functions, `Signals.checkpoint_started` and `checkpoint_written`, `ProcessOutcome`), [39](39-tlc-command.md) (`replace(java_inv, lifeline=False).argv()` for `--show-command`), [41](41-sany-command.md) and [42](42-pcal-command.md) (`run_streaming(..., merge_stderr=True)`), [43](43-repl-command.md) (`signals_held(leave_interrupt=True)` and `run_passthrough(..., forward_interrupt=False)`).

## Tests that must pass

**Stateful, test first.** `tests/stateful/test_signals.py`. The package's first commit removes the `pending` marker from `test_signals_machine` and `test_a_signal_from_this_process_stands_for_one_from_outside`; the pull request shows that run red ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 6). Both pass at the end, with the CI profile (`CI=1`, 200 examples), subject to the open question. The package deletes `reference_launcher.py` and the four `*_reference_model` tests.

What happens to `test_child_ends_with_tlaup`: its two tests run against the throwaway model only and have no `pending` twin, on purpose ([03](../design/03-run-stages-and-specs.md#specs-and-their-tests), "What could not be mirrored"). The real lifeline is a Java agent, which a fake `java` cannot carry; the model stood in for it with an environment variable. So they are deleted with the model, and nothing replaces them in this file. For the real launcher the property `ChildEndsWithTlaup` rests on three other tests: the agent ends a real JVM whose parent was killed ([06](06-lifeline-agent.md), run by the lifeline job of [53](53-ci-workflows.md)); `argv()` puts the agent first with tlaup's process id (unit, below); and tlaup killed with SIGKILL during a real run leaves no `java` process ([52](52-integration-tests.md)).

**Unit, plain pytest, the fake `java` as a real child of the test process** (`tests/unit/java/test_launcher.py`). From G3's Tests unless marked:

- Invalid UTF-8 bytes in stdout arrive as replacement characters and the run completes.
- 100,000 lines (ten times the bound) arrive in order with a slow `on_stdout`, and the queue never holds more than its bound.
- An `on_stdout` that raises at the fifth of 100,000 lines makes `run_streaming` raise that exception within a few seconds, with the fake exited and no reader thread alive.
- A fake that ignores SIGTERM is killed when the grace period (set to half a second) runs out.
- Text on stderr arrives through `on_stderr` only; `stderr_tail` holds the last 50 lines.
- With `merge_stderr=True` every line arrives through `on_stdout`.
- A missing executable raises `ToolStartError` whose message does not say "not found" unless the file is missing; a file without execute permission says "permission denied". Both carry the path (also R1's unit tests; code 5).
- A `Signals` with `first` already set starts nothing: the fake's log stays empty and the outcome has that signal's code and `tool_exit_code` `None`.
- A child killed by a signal tlaup did not send gives `128 + n`; a child's own code passes through.
- `pass_fds` (Linux and macOS): a descriptor passed is open in the child and closed in the parent after `Popen`.
- The checkpoint row: a child that prints one line, pauses, prints a second and then waits, with the test's `on_stdout` calling `checkpoint_started` at the first and `checkpoint_written` at the second, as the runner will at 2195 and 2196. A SIGINT between the two sets `held` and sends nothing until the second line, after which the fake gets SIGTERM; a second SIGINT before it kills at once; the grace period starts at the second line, not at the signal (injected clock); `on_held` is called once, with the signal's name, for SIGINT and for SIGTERM. The two wordings of the line are 37's test.
- A closed pipe and the signals (FC9), with `reader_gone` passed in: a closed pipe seen first and then a SIGINT gives 141 and a `kill()`; a SIGINT and then a closed pipe gives 130; a closed pipe seen while a signal is held sends `terminate()` at once. For the first, `stopped_by` is `None`, `Signals.first` is unset and `stopped_for_closed_pipe` is true.
- `run_passthrough` with `reader_gone` passed in as always false (the Windows case): the child runs to its end ([11 R1](../design/11-runner.md#r1-run-errors-reported-as-what-they-are)).
- `run_passthrough` called with a `forward_interrupt` that disagrees with the block raises `InternalError`. `run_streaming` under a block entered with `leave_interrupt=True` is refused too: G3 says it "requires `leave_interrupt` to be false" and names no error; `InternalError` is the neighbouring rule's.
- Added by the cut, since the terminal scenarios of D60 arrive only with 39 (Linux and macOS): the fake's `start` line shows a process group of its own under `run_streaming`, and tlaup's group under `run_streaming(merge_stderr=True)` and under `run_passthrough`; a SIGQUIT sent to the test process during a parsed run is logged by the fake and changes neither `Signals` nor the outcome; during a passthrough run it is not sent on.

**Unit, `signals_held`, each in a child Python process** so the test runner's own dispositions are not touched (`tests/unit/java/test_signals_held.py`). From G3's Tests:

- Started with SIGHUP ignored, the block installs no SIGHUP handler and leaves it ignored afterwards.
- SIGQUIT sent inside the block does not end the process and leaves `Signals` unchanged.
- A SIGINT inside a block entered with `leave_interrupt=True`, before any child exists and again while one runs with `forward_interrupt=False`, leaves `first` unset and `count` at 0; a child that then ends by itself gives its own code; a SIGTERM after the SIGINT terminates the child and gives 143 (also the unit test [21 S3](../design/21-other-tools.md#s3-repl) names).
- Entering `signals_held` off the main thread raises `InternalError` (G3, Risks).

**Unit, `argv()`** (`tests/unit/java/test_launcher_argv.py`). The lifeline comes first after `java` and names `os.getpid()`; the three encoding options come next, before `jvm_options`, so that a user's `-Dfile.encoding=ISO-8859-1` comes last; then each system property as `-Dk=v`, `-cp` with the classpath joined by `os.pathsep`, the main class, the arguments; `lifeline=False` leaves the agent out and keeps the encoding options; the same order for the main classes of `tlc`, `sany`, `pcal` and `repl`.

Old test files deleted or rewritten: none (01 T11 gives the old runner's tests to the switch).

## Changelog

None in this package: no command uses the launcher until [39](39-tlc-command.md), which writes G3's entries when `tlaup tlc` moves onto it. They are, word for word:

- Fixed: "Stopping `tlaup tlc` with SIGTERM (for example a CI timeout) now stops TLC too; it used to keep running."
- Fixed: "A second Ctrl-C no longer loses the summary."
- Fixed: "Output that is not valid UTF-8 no longer crashes tlaup."
- Fixed: "If tlaup is killed, the Java tool it started stops within about two seconds."
- Fixed: "TLC, SANY, PlusCal and the REPL now always write UTF-8; under a C locale non-ASCII characters were printed as `?`, and with Java 11 and v1.7.4 the PlusCal translator wrote them as `?` into the spec."
- Changed: "Ctrl-C exits with 130."
- Changed: "In a run that is not `--raw`, a first Ctrl-C while TLC writes a checkpoint waits for it to finish, on Linux and macOS."

## Context for the worker

Read [20 G3](../design/20-groundwork.md#g3-java-launcher) from its first line to its last, "Risks" included, then [the Signals part of the specs' README](../../specs/README.md#signals), then `tests/stateful/test_signals.py` and `reference_launcher.py` before you delete it: the throwaway model is about 200 lines and shows the handler, the attach order and the grace period in their smallest form. It is not the design: it has no second pipe, no process group, no closed-pipe stop and no SIGQUIT forwarding.

### The decisions, with the reason for each

- **D51.** Every JVM carries the lifeline agent, and on Linux and macOS inherits the run's lock descriptors (`pass_fds`). A killed tlaup's TLC would otherwise run on unseen, and "the lock is free" would not mean "no TLC runs here".
- **D52.** In a parsed run a first signal that arrives while TLC writes a checkpoint is held until the checkpoint is written. A checkpoint is not atomic; a stop in the middle, tlaup's own SIGTERM included, can leave one that recovers with exit 0 and misses states.
- **D56.** `argv()` always adds `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8`, before the user's options. The JVM's encodings follow its locale (`?` under a C locale); Java 11 honours only the first, Java 18 and later the other two; placed first, a user's own option still wins.
- **D57.** On Windows a closed pipe shows as `OSError` with `EINVAL`. It is the error handler's rule ([17](17-error-handler.md)); here it only means that any exception a callback raises, not only `BrokenPipeError`, must pass through the `finally` unchanged.
- **D58.** A closed stdout stops TLC, in a raw run too (not on Windows for raw). The JVM ignores a closed stdout and would run to its end with nobody reading.
- **D60.** On Linux and macOS the JVM of a parsed TLC run has a process group of its own. Otherwise the terminal's Ctrl-C reaches TLC directly and D52 cannot hold it. Raw runs, the REPL, `sany` and `pcal` stay in tlaup's group, because there the child uses the terminal or is short.
- **D15.** No Windows CI, but write the code so it should work there; the guards are listed below.
- **D46.** The launcher's steps are separate calls so that the stateful test can drive them.
- **D29, D30** ([02 X1](../design/02-cross-cutting.md#x1-exit-codes), [X2](../design/02-cross-cutting.md#x2-stdout-and-stderr)). tlaup sets 130, 143 and 129 itself, since the JVM's own code after a signal is a race between 130 and 143; 141 for a reader that went away; `128 + n` for a child killed by a signal tlaup did not send; the tool's own code otherwise, a 1 included. TLC is read through two pipes; one pipe only for `sany` and `pcal`.
- **D9.** Nothing the tool printed is lost: the loop drains until both pipes close.

### Where the launcher ends and the runner begins

| Section | The launcher (this package) | The runner and others |
| --- | --- | --- |
| R1 | `OSError` from `Popen` becomes `ToolStartError` with the path and the system's own message. The `finally` round the loop stops the child and empties the queue when a callback raises, then lets the exception go on. The poll of `reader_gone(1)`, the stop it causes and the code 141. | The frame that settles the run folder and closes the reporter on the way out, `RunOutcome.stopped_for_closed_pipe`: [37](37-run-tlc.md). `JavaNotFound` before the run: [20](20-java-location.md), [33](33-tlc-invocation.md). The handler that turns `BrokenPipeError` into 141: [17](17-error-handler.md). Removing today's catch-all: [39](39-tlc-command.md). |
| R2 | Everything in G3's signal table: the handlers, what is left ignored, the grace period, `terminate()` and `kill()`, the three codes, the process group, SIGQUIT, `held`, `checkpoint_started` and `checkpoint_written`, `forward_interrupt`. Starting nothing when a signal came first. | Entering `signals_held()` before the run folder is made and leaving it after the summary; calling the two checkpoint methods from the parser's events for 2195 and 2196; `result.status = INTERRUPTED`; settling the folder; the text of the waiting line: [37](37-run-tlc.md). |
| R3 | Pipes in binary mode; `decode("utf-8", errors="replace")` per line, which cannot raise; nothing decoded in a passthrough run; the three options in `argv()`. | The warning for a non-ASCII path under a locale that is not UTF-8: [33](33-tlc-invocation.md). `errors="replace"` on tlaup's own streams: [16](16-ui-messages.md). |

The launcher prints nothing and imports no `Ui`: domain code returns values or raises ([00](../design/00-overview.md#packages-after-the-first-wave)).

### Rules a worker could miss

Signals:

- **Attach first, look second.** `attach()` hands the child to `Signals` and only then looks at `signals.first`. In the other order a signal between the two is recorded and never reaches the child (finding K3-2).
- **`may_start()` is the look before the start.** A signal after it and before `Popen` still finds a child started, and stops it at `attach()`. Two signals in that window count as one for the child: `terminate()`, not `kill()`.
- **A handler never raises and never does I/O.** It records, and if a live child is attached it acts. Everything else is the main thread's.
- **Handlers are Python functions, never `SIG_IGN`.** An ignore set before the child starts is inherited, and a JVM started that way installs no handler of its own.
- **A signal that is ignored when the block is entered is left alone**: no handler is installed for it and nothing is restored for it (`nohup`, a background job of a shell script). The stateful test checks the handlers after the block.
- **`first_at` is stamped when the signal is sent on to the child, not when it arrives** (review finding FC7): at `terminate()` in the handler, at `attach()`, or at `checkpoint_written()` for a held signal. The stateful test lets the clock run past the grace period while a signal is held and expects the child untouched.
- **`held` is set only when the signal is the first, a live child is attached, and `checkpointing` is set.** A second signal clears it and kills. A child that ends while the mark is set ends the run as usual. A raw run never calls the checkpoint methods.
- **The mark is what tlaup has read.** A signal that comes while 2195 is still in the pipe or the queue is sent on at once (FC8). That is accepted: the completeness test of [11 R6](../design/11-runner.md#r6-run-folders) then drops the checkpoint.
- **SIGQUIT is never recorded and never counted.** In a parsed run whose child has its own group the handler forwards it (`os.kill(child.pid, SIGQUIT)`) so that Ctrl-\ still gives a thread dump; in every other run the handler does nothing, because the terminal has already sent it to the child, and forwarding would give two dumps.
- **A SIGINT left to the child** (`leave_interrupt=True`) does nothing at all from the moment the block is entered: `first` stays unset, `count` stays 0, so a later SIGTERM is the first signal and terminates rather than kills.
- **`outcome()` is taken once**, at the moment the launcher saw the child gone (both pipes closed and the wait returned), and gives the same answer ever after. A signal that arrives after the child ended by itself and before the launcher noticed counts as having stopped the run (finding K3-1); one that arrives later changes nothing.
- **The grace period runs on the injected clock**, compared with `first_at` (or with the moment `stop()` or a closed-pipe stop sent `terminate()`). The stateful test runs it out without waiting; in its `loop_fails` rule the clock jumps a whole grace period at every call, so `stop()` must use it for the kill and must not use it for the two seconds allowed for emptying the queue.
- **`signals_held` is entered on the main thread only**, and raises `InternalError` elsewhere.

Starting the child:

- **No `preexec_fn`, anywhere.** Nothing in the launcher runs Python between `fork` and `exec`. With it, Python runs `filelock`'s at-fork hooks, which close the descriptors the child is meant to inherit, and `Popen` fails for a descriptor in `pass_fds`. The process group is asked for with `process_group=0` (Python 3.11 and later), which `subprocess` does itself. A test helper may use `preexec_fn`; the rule is the launcher's.
- **`process_group=0` only for a parsed TLC run on Linux and macOS**: `run_streaming` without `merge_stderr`. Not with `merge_stderr=True`, never in `run_passthrough`, not on Windows.
- **`pass_fds` are duplicates the caller made for the child.** Close them in the parent once `Popen` has returned. The design does not say what happens to them when `Popen` raises or when nothing is started because a signal came first; they have no other owner, so closing them there too leaks nothing. Say what you did.
- **`stdin` is the null device in `run_streaming`**; in `run_passthrough` the child inherits all three streams and nothing is read or decoded.
- **`argv()` is the only place the lifeline and the encoding options are added**, for every tool, and `lifeline=False` exists for `--show-command` alone: a pasted command would carry the process id of a tlaup that has exited, and its JVM would stop at once. The agent's argument is exactly `-javaagent:<absolute path of the jar>=pid=<os.getpid()>`. `argv()` is pure apart from reading the process id and the jar's place; the design does not ask it to check that the jar exists, and the tests with the fake `java` never open it. For an empty classpath the design does not say whether `-cp` is left out; the stateful test builds such an invocation and passes either way.
- **Every subprocess is started from an argument list**, never through a shell.

The loop:

- **Two reader threads, daemon threads, one bounded queue of 10,000 lines.** When the main thread falls behind, the readers block, the pipe fills and the JVM waits; memory does not grow. Lines are split on `\n` and keep their ending (`\n` or `\r\n`); the parser strips it.
- **The main thread never waits more than a fifth of a second** for a line or for the child, so that it can watch the grace period, the closed pipe and a held signal.
- **Leaving early.** A callback may raise. The `finally` then, in this order: stops the child if it runs (`terminate()`, `kill()` after the grace period); empties the queue, throwing the lines away, until both readers have delivered their end marker or two seconds have passed; lets the exception go on. Without the emptying a reader blocked on a full queue hangs tlaup for ever; the design's first revision did, and a sketch showed it.
- **All parsing and printing is on the main thread**, so callbacks need no locks.
- **A stop for a closed pipe is not a signal.** It sends `terminate()` and starts the grace period; a signal after it is a second stop and kills at once; the code is the first stop's (141, or the signal's if a signal was recorded first); seen while a signal is held, it does not wait.

### Windows guards (D15)

Nothing here runs on Windows in CI; write it so that it should work. Install handlers only for signals the platform has (`hasattr(signal, "SIGHUP")`, `"SIGQUIT"`); no `process_group` and no `pass_fds` there (stated from the standard library's documentation, not tried: `subprocess` refuses both on Windows); `reader_gone` is always false there, so a raw run cannot see a closed pipe; `terminate()` kills at once, and there is no SIGTERM or SIGHUP to receive; a console Ctrl-C reaches every process attached to the console. Join the classpath with `os.pathsep`. The stateful test skips itself where there is no SIGHUP.

### The open question: SIGQUIT in the signals machine

`tests/stateful/test_signals.py` was last revised for D51 and D52, before D60 added "forwards SIGQUIT to the JVM of a parsed run". Its fake child (`FAKE_CHILD`) handles SIGTERM and SIGUSR1 and nothing else, so a SIGQUIT ends it, as the default action does for any process that is not a JVM (tried on Linux on 2026-11-21: the script's return code is -3). The machine's rule `signal_arrives` draws `quit` in every phase and expects nothing to change. Against a launcher that follows G3, a `quit` drawn in a streaming run while the child is attached is forwarded, the fake child dies, and the next `turn_with_nothing_to_do` fails. The throwaway model does not forward, which is why the test passes today.

The design is clear and the test is behind it. What waits for the maintainer is the edit of a signed-off test. Recommended: give `FAKE_CHILD` a SIGQUIT handler that notes the signal in a file and carries on, as a JVM does, and let the rule assert that the note appears in a streaming run and does not in a passthrough run. Not recommended: keeping `quit` away from an attached streaming child, which checks less. Not an option: a launcher that does not forward. Until the question is answered, write the launcher as G3 says and leave the machine's first failure in the pull request as it is.

### The fake `java`: what these tests need from package 03

Checked against [01 T4](../design/01-testing.md#t4-fakes-at-the-edges), not against the fake itself, which did not exist when this was written.

| Need | T4 has it? |
| --- | --- |
| Many lines, then wait: `generate_lines`, `hang_after_line` | Yes. |
| A pause between two lines: `line_delay_ms` | Yes. |
| Ignore SIGTERM, or exit with a given code on a signal: `on_sigterm`, `on_sigint` | Yes. |
| Text on stderr: `stderr` | Yes. |
| A log with `start` (process id, process group, whether stdout is a pipe), `signal` (also for a signal it ignores, SIGQUIT among them) and `exit` | Yes. Check that a SIGQUIT is logged and does not end the fake. |
| The main class found when `-javaagent:...` and three `-D` options come first | Not said. It follows if the fake skips options as `java` does; check. |
| A file of bytes that are not valid UTF-8, replayed as they are | Partly. `stdout` names "a golden file ... or literal text", and the one such file, `synthetic/invalid-utf8.out`, comes with [07](07-golden-files.md), which this package does not depend on. A file the test writes itself (plain lines with the bytes `FF FE`; not TLC output, so rule 3 of T12 is untouched) needs the fake to take an absolute path. If it does not, add that and say why. |
| A child that reports which descriptors it has open (`pass_fds`) | No. Use a small script of the test's own as `JavaInvocation.java`, as `tests/stateful/test_signals.py` does: it takes its last arguments and ignores the JVM options before them. |

In the checkpoint-row test the launcher needs no TLC text: the test's own `on_stdout` stands for the runner and marks the checkpoint at two plain lines. The framed 2195 and 2196 captures are for 37 and 39.

### What the design says was not tried

- The SIGQUIT handler was tried on Linux with Java 25 and a class that sleeps; not with other Java versions, not on a real terminal, not with TLC. How a thread dump reads when it lands inside a `-tool` message was not tried.
- The rules for ignored signals were tried on Linux with a sketch (`nohup`; a background job of `sh -c`).
- The bounded queue and the `finally` were tried with a sketch (a bound of 10, 5,000 lines on each stream).
- The two seconds for emptying the queue are a guess. The ten-second grace period is a choice; a JVM was measured to exit in under a second after a signal.
- A main thread blocked writing tlaup's own output into a pipe whose reader is alive and not reading stays blocked after Ctrl-C until the reader reads or quits. Found by reasoning, not tried, and accepted for the first wave. Do not try to close it.
- The signal handling was not run on macOS or with a real terminal; CI's macOS job is the first run there.
- D60 was worked in after the last review and has been read by no agent that did not write it. Its terminal scenarios come with 39; the unit tests here are its first check.
- `process_group=0` together with `pass_fds` was not tried.
- Nothing about the launcher was tried on Windows.

### Gaps the design postpones; do not close them

Forwarding SIGTSTP (Ctrl-Z stops tlaup alone; the JVM of a parsed run runs on until its pipes fill, and `fg` resumes both). A per-run `-Djava.io.tmpdir` for v1.7.4's shared temporary copies ([13 J1](../design/13-modules-and-java.md#j1-java-options), postponed until after the first implementation). Any second way to end the JVM with tlaup.

### State of `main` when this starts

Release 0.8.x code with `tlaup/errors.py`, `tlaup/paths.py`, `tlaup/ui.py` and the error handler beside or in place of the old pieces, the test foundation, and the lifeline jar. `src/tlaup/tlc/runner.py` is the old runner with its two copied loops; leave it and its tests alone. Nothing imports `launcher.py` when this package merges.

## Done when

- The open question is answered and `test_signals_machine` and `test_a_signal_from_this_process_stands_for_one_from_outside` pass without the `pending` marker under `CI=1`; the pull request shows them red after the first commit.
- `reference_launcher.py` and the four `*_reference_model` tests are gone; `tests/stateful/test_signals.py` imports nothing that is gone and its docstring says what it runs against.
- The unit tests above pass on Linux and on the macOS job; `uv run poe lint` (mypy in strict mode covers `launcher.py`) and `uv run poe test` pass; CI is green.
- No test waits for an amount of time ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 5): the grace period is a parameter or the injected clock, and every wait is for a condition with a timeout.
- `specs/README.md` has its sentence.
- The pull request lists every signature that differs from this file, says what was done with `pass_fds` on the two paths the design leaves open, where `reader_gone` lives, and what was run on which system.
- No changelog entry (none is due).

## Out of scope

Tests of G3 that need a command, with their owner:

| G3's test | Owner |
| --- | --- |
| `tlc_signals.feature`, real processes: SIGTERM, one SIGINT, two SIGINTs, in parsed and raw mode (six scenarios with R2) | [39](39-tlc-command.md) |
| The two exact-moment tests that drive `run_tlc` (a SIGTERM from the reporter's `start`; a second SIGINT from `finish`) | [37](37-run-tlc.md) |
| `tlc_raw.feature`, real process: the two streams apart, byte for byte | [39](39-tlc-command.md) |
| The pseudo-terminal scenarios of D60 (`press Ctrl-C` and `press Ctrl-\` in a parsed run; the same with `--raw`) | [39](39-tlc-command.md), on the terminal steps of [18](18-feature-harness.md) |
| The real-pipe scenario of TU2 (`tlaup tlc Spec` whose reader exits after one line, the fake silent on stdout), R1's raw-run twin and the 100,000-line scenario | [39](39-tlc-command.md) |
| R6's real-process checkpoint scenarios (2195, a pause, 2196) and the wording of the waiting line | [39](39-tlc-command.md), [37](37-run-tlc.md) |
| R3's scenarios (invalid bytes replayed in-process; `PYTHONIOENCODING=ascii` as a real process) | [39](39-tlc-command.md) |
| `repl.feature`, `sany.feature`, `pcal.feature` | [43](43-repl-command.md), [41](41-sany-command.md), [42](42-pcal-command.md) |
| Integration: the signal scenarios with the real JVM, "no `java` process is left", the REPL on a pseudo-terminal with the agent | [52](52-integration-tests.md) |
| The lifeline with a real JVM; the jar matches its source | [06](06-lifeline-agent.md), run by [53](53-ci-workflows.md) |

Also not here: `build_tlc_command` and `TlcInvocation` ([33](33-tlc-invocation.md)); run folders, `RunLock` and the inherited-lock tests ([35](35-run-folders.md)); `run_tlc`, `run_tlc_raw`, `RunOutcome` ([37](37-run-tlc.md)); `--show-command` ([39](39-tlc-command.md)); `reader_gone` itself and exit 141 at the top ([17](17-error-handler.md)); finding Java ([20](20-java-location.md)); the help line of `--raw` about Windows ([39](39-tlc-command.md)).

## Risks

From G3:

- (D60) Ctrl-Z stops tlaup alone; the JVM of a parsed run runs on until its pipes fill. A process that signals tlaup's group from outside no longer reaches the JVM of a parsed run directly; tlaup forwards.
- A broken or missing lifeline jar stops every Java start. On Windows the lifeline is the only thing that ends an orphan JVM, and the run's lock does not follow it.
- A user option that overrides an encoding property wins, by design.
- A checkpoint that takes long holds a first signal as long; a CI system that sends SIGKILL a few seconds after SIGTERM then kills tlaup, the lifeline ends TLC in the middle of the checkpoint, and the completeness test of R6 catches it.
- A tlaup blocked in a write to a pager that is not reading stays blocked after Ctrl-C.
- A caller that starts tlaup with SIGINT or SIGTERM ignored gets a run tlaup cannot stop on that signal.
- The grace period delays exit by up to ten seconds if the JVM ignores SIGTERM.
- Not run on macOS or with a real terminal.

From the cut:

- No command reaches the launcher until 37 and 39, so its real-process and terminal scenarios, the ones that prove forwarding from outside the process and D60 on a real terminal, come many packages later. A fault they find then is fixed there, in this module.
- After the throwaway model is deleted, no test kills a process that runs this launcher until [52](52-integration-tests.md). The three tests named under "Tests that must pass" cover the parts; the whole is seen first in the integration job.
- Four joints are written by stage 4 (`stopped_for_closed_pipe`, the arguments of `ChildRun`, `reader_gone` as a parameter, `on_held`). 35 and 37 are cut against them; a change here must reach those packages.
- The stateful test fixes the step functions' names and arguments. If a step needs another argument, the test changes with it, and the specs' README says a worker may find that.
- The package is large for one pull request: one module, three test files and an edited stateful test. It was not split, because the stateful test needs the whole of `ChildRun` and `Signals` before it can pass.
