# 43. The `repl` command

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup repl [-- arguments]` starts the TLA+ REPL of the pinned build with the terminal passed straight through, leaves Ctrl-C to the REPL, forwards SIGTERM and SIGHUP, and exits with the REPL's own code. On a build without the REPL (v1.7.4) it stops with code 3 before Java is started.

## Covers

- Roadmap items ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)):
  - "`repl` command: interactive, so no output parsing; the terminal is passed straight through." (line 302), in full apart from its integration test ([52](52-integration-tests.md)).
  - "Keep all three thin ... Check which jar build is running, so the tool can switch to upstream's own entry point when it exists and fall back for older jars." (line 304), in part: the one tool whose availability depends on the build, refused from the stored capability. The check itself is [41](41-sany-command.md)'s.
  - "Golden-file tests for SANY and PlusCal output per TLC version; passthrough after `--` for each." (line 306), in part: passthrough for `repl` in `repl.feature`. The REPL has no golden files (S5).
- Design sections:
  - [21 S3](../design/21-other-tools.md#s3-repl): all of it except its integration test (52).
  - [21](../design/21-other-tools.md), the head, for `repl`: `signals_held(leave_interrupt=True)`, the instant between entering the block and the REPL's start, `--java-opt`, `--auto-install`, the arguments after `--`.
  - [12 V1](../design/12-tools-and-downloads.md#v1-version-store) and [V5](../design/12-tools-and-downloads.md#v5-download-and-verify), as used: the `repl` capability stored with the build ([00](../design/00-overview.md#what-a-build-can-do)), read here and never decided again.
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes): rule 2's note on a Ctrl-C left to the child, rule 4 (`repl` passes its code through), and "the pinned build has no REPL" in row 3.

## Depends on

- [41](41-sany-command.md): `resolve_tool_invocation("repl", ...)` with the capability check before Java and `ToolNotInBuild`'s message, `build_tool_command`, `ENTRY_POINTS["repl"]`, the shared `get_build` wrapper in `cmd/common.py`, the conventions of `cmd/sany.py`.
- [21](21-java-launcher.md): `signals_held(leave_interrupt=True)`, `run_passthrough(..., forward_interrupt=False)`, `ProcessOutcome`.
- [18](18-feature-harness.md): the real-process steps (`as a process with input:`, `I start ... and send <signal> once java is running`), the in-process check of T12 rule 10, and the fake `java`'s `echo_stdin` ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)).
- [22](22-version-spec-and-jarinfo.md) and [23](23-tool-store.md): `Build.capabilities`, with `repl` when the jar has `tlc2/REPL.class`, as the store's Given step installs a build.

Unchanged from the draft (41) in substance; 21, 18, 22 and 23 are named for what is used directly. Runs beside [42](42-pcal-command.md) and the other packages after 41.

## Files

Creates:

- `src/tlaup/tools/repl.py`: `run_repl`.
- `src/tlaup/cmd/repl.py`: the command.
- `tests/features/repl.feature`.
- `tests/unit/tools/test_repl.py`.

Changes:

- `src/tlaup/cli.py`: one line registering `repl`.
- `CHANGELOG.md`: the entry under Changelog.
- `tests/steps/given.py`, only if the store's Given step does not already put `tlc2/REPL.class` into the small jar it builds for a rolling build (see Traps): that one entry, with the reason in the pull request.

Deletes: nothing.

Files another package of the same period touches: `src/tlaup/cli.py` (one line each for 42 and the others after 41); `CHANGELOG.md`; `src/tlaup/tools/` gets `pcal.py` from 42 beside this package's `repl.py`, with no shared line.

## Interfaces

Provides, written by stage 4 from S3 and the head of 21:

```python
# tlaup/tools/repl.py
def run_repl(java_inv: JavaInvocation) -> ProcessOutcome
    # with signals_held(leave_interrupt=True) as signals:
    #     return run_passthrough(java_inv, signals=signals, forward_interrupt=False)

# tlaup/cmd/repl.py
def repl(ctx: typer.Context,
         repl_args: list[str] | None = None,          # everything after `--`; no SPEC (C1)
         java_opt: list[str] | None = None,           # --java-opt OPT, repeatable
         auto_install: str | None = None) -> None     # --auto-install stable|rolling, else TLAUP_AUTO_INSTALL
```

**The command**, on 41's shape: `read_auto_install`; `resolve_tool_invocation("repl", None, ...)` with the run wrapper as `get_build` (steps 0, 3, the capability, 4 of [11 R11](../design/11-runner.md#r11-preflight): there is no spec); `build_tool_command`; each warning with `ui.warning`; `run_repl`; `raise typer.Exit(outcome.exit_code)`. Nothing is read or parsed.

What the pieces give, so that the worker does not rebuild them here:

- From 41: `cwd` is `None` (the REPL runs where tlaup was started); the classpath and `-DTLA-Library` are those of a TLC run without a spec, the registered modules and the config paths (S3, step 2); `args` is what came after `--`, unchanged. A build whose capabilities lack `repl` raises `ToolNotInBuild` (3), "the pinned build v1.7.4@5a47802 has no REPL" / "install a rolling build: `tlaup tool install rolling`", and Java is not started, not even for its version.
- From 21: the child inherits tlaup's stdin, stdout and stderr and stays in tlaup's process group (D60), so in a terminal the REPL receives Ctrl-C itself. With the block entered with `leave_interrupt=True`, tlaup's SIGINT handler does nothing at all from the moment the block is entered: it does not touch the child, does not set `signals.first`, does not count. So after any number of Ctrl-C a REPL that is quit normally exits with its own code, not 130, and a later SIGTERM is the first signal (terminate, not kill). In the instant between entering the block and the REPL's start a Ctrl-C is simply dropped and the REPL starts; SIGTERM and SIGHUP there are recorded and the REPL is not started. SIGTERM and SIGHUP during the run are forwarded as for any run (130, 143, 129 from the table of [02 X1](../design/02-cross-cutting.md#x1-exit-codes)). `run_passthrough` raises `InternalError` if `forward_interrupt` disagrees with the block, which is why the two are written together in `run_repl`. Neither `pass_fds` nor `stop_when_reader_gone` is passed: there is no run folder, and only `tlc --raw` stops for a closed pipe (D58).

Help of `repl`, which [50](50-help-and-messages.md) may reword and not drop: rolling builds only; Ctrl-C belongs to the REPL, and SIGTERM stops it from outside; the REPL keeps its history in `~/.tlaplus/history.repl`, where upstream puts it (S3).

Consumes: `resolve_tool_invocation`, `build_tool_command`, `cmd/common.py` (41); `signals_held`, `run_passthrough`, `ProcessOutcome`, `JavaInvocation` (21); `read_auto_install` (28); `Ui` (16); `AppContext` (02).

## Tests that must pass

`tests/features/repl.feature` (S3, T5):

- In-process: with `the build "v1.7.4" is installed and pinned`, `tlaup repl` exits 3, `stdout is empty`, `stderr contains "error:" 1 times`, stderr names `tlaup tool install rolling`, and `java was not started`. In-process is right here: the refusal comes before Java, so there is no passthrough to see (T12 rule 10, the REPL on v1.7.4 is the example it gives).
- In-process, added by stage 4 for the order of the capability check: the same with `java is not installed` gives the same error (the REPL message, code 3), not `JavaNotFound`.
- Real process (situation 1 of T5: the child inherits the real file descriptors): with a rolling build installed and pinned and `java echoes its input`, `I run "tlaup repl" as a process with input:` `1+1`; `stdout contains "1+1"` and the exit code is the fake's own (0 at end of input).
- Real process: the same fake, `I start "tlaup repl" and send SIGTERM once java is running` (the step holds stdin open, so the echoing fake waits); the exit code is 143 and `the java process has exited`.
- Real process, added by stage 4 for passthrough (S5: an argument after `--` appears in the logged Java command unchanged): `tlaup repl --java-opt=-Xss8m -- -x` with input; `java was started with "-x"` and `java was started with "-Xss8m"`; `java ran "tlc2.REPL" 1 time`.

`tests/unit/tools/test_repl.py`, plain pytest (S3: "That a Ctrl-C left to the REPL is not recorded is a unit test"; T5 lists it among the plain pytest tests). Each case runs `run_repl` in a child Python process started by the test with stdin on the null device, so the test runner's own signal dispositions are not touched, as [21](21-java-launcher.md)'s `signals_held` tests do; the fake `java` is the child's child, and the test waits for its `start` line in the log before it signals:

- A SIGINT sent to the Python process alone while the fake runs reaches nobody: the fake logs no signal, and when the fake then ends by itself with a code of its own (a paced replay that exits 7) the outcome's code is 7, not 130.
- A SIGINT and then a SIGTERM: the fake gets SIGTERM, not SIGKILL (it logs the signal and exits with its `on_sigterm` code), and the outcome's code is 143. This is the wiring of `run_repl`; the launcher's own test of the same rule, with `forward_interrupt=False` given directly, is 21's.

Old tests: none. No stateful test applies (21 removed the `pending` markers of `test_signals.py`).

## Changelog

Added (S3, word for word): "`tlaup repl` starts the TLA+ REPL of the pinned build (rolling builds only)."

## Context for the worker

**State of `main`.** 41 is in: `tlaup/tools/` with `ENTRY_POINTS`, `resolve_tool_invocation` with the capability check, `cmd/common.py`, `cmd/sany.py`. The launcher's `run_passthrough` is used by `tlc --raw` already ([39](39-tlc-command.md)). [42](42-pcal-command.md) may be in flight beside this package.

**Decisions this rests on.** D5 and S4: thin; nothing is read or parsed, no flag of tlaup's own beyond `--java-opt` and `--auto-install`. D29: the REPL's code passes through; only a signal tlaup acts on gives 143 or 129. D45: the capability is a fact about the build, checked at the build step, so Java is not started on v1.7.4. D60: the REPL stays in tlaup's process group, because it uses the terminal itself and a background group is stopped when it reads the terminal. D51: the lifeline agent is in the REPL's JVM too; it touches no stream, so the REPL still reads stdin (06 and 53 test that with a real JVM under a pseudo-terminal). D56: the encoding options are added to the REPL's JVM as to every other.

**Facts a worker could miss** (S3, restated from research 3 and 12): `tlc2.REPL` is in rolling builds and absent from v1.7.4, where starting it ends with the JVM's "Could not find or load main class" and exit 1; that is why the capability is checked first. The REPL works with piped input and exits 0 at end of input. It writes its history to `~/.tlaplus/history.repl`; the JVM takes the home folder from `user.home`, not from `HOME`, so the isolation fixture does not move it and only the integration test, with `--java-opt=-Duser.home=<a temporary folder>`, keeps it off the real home folder. The feature scenarios never start a real JVM.

**Why a handler and not "ignore"** ([20 G3](../design/20-groundwork.md#g3-java-launcher)): a disposition of "ignore" set before the child starts is inherited by it, and a JVM started that way installs no handler of its own; the REPL could then not be interrupted at all. tlaup's handler is a Python function, reset to the default in the child.

**Traps.**

- The in-process step refuses a command that reaches `run_passthrough` (T12 rule 10): every scenario that starts the REPL is a real process. The v1.7.4 refusal stays in-process.
- The store's Given step builds a small jar for an installed build ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges): a zip with a recorded manifest and an empty `tlc2/TLC.class`). For a rolling build it must also hold an entry `tlc2/REPL.class`, or `read_jar` records no `repl` capability and every real-process scenario here ends with exit 3. Check what [18](18-feature-harness.md) or [29](29-tool-commands.md) built, and add the entry with a reason in the pull request if it is missing.
- Real-process scenarios cannot be served GitHub recordings; start from a store that already holds the build.
- A SIGINT sent to tlaup alone, not from the terminal, does not reach the REPL; SIGTERM is the way to stop it from outside. The tests send signals to the tlaup process alone, never to its group, so they show exactly that.

**Known gaps; do not close them here.** How the REPL behaves on a real terminal (prompt, history keys, Ctrl-C) was not tested by the research; tlaup passes the terminal through and adds nothing, so it is upstream's behaviour. "SIGINT, then end of input" from outside the process would need a step that signals and then closes stdin, which T5's list does not have; the unit test above covers the rule instead. Forwarding SIGTSTP is not designed.

**Windows (D15).** No SIGTERM or SIGHUP to receive; `terminate()` kills at once; a console Ctrl-C reaches every process attached to the console, the REPL included. The real-process signal scenario and the unit tests skip where the platform lacks the signal. No Windows CI.

## Done when

- `repl.feature` and `tests/unit/tools/test_repl.py` pass on Linux and macOS in CI; `uv run poe lint` and `uv run poe test` pass.
- The changelog entry is under `## [Unreleased]`.
- The pull request shows `repl.feature` failing before the command existed (T12 rule 6), and says whether the store's Given step needed the `tlc2/REPL.class` entry.

## Out of scope

- The capability check, `ToolNotInBuild`'s message, `ENTRY_POINTS`: [41](41-sany-command.md). The capability decided at install: [22](22-version-spec-and-jarinfo.md), [23](23-tool-store.md).
- The launcher's own test of a SIGINT with `forward_interrupt=False`: [21](21-java-launcher.md). The lifeline with the REPL on a pseudo-terminal, which needs a real `tla2tools.jar`: [52](52-integration-tests.md), as [06](06-lifeline-agent.md) assigns it (reconciled by stage 4).
- Integration tests ([01 T9](../design/01-testing.md#t9-integration-tests)), in [52](52-integration-tests.md): the T9 row "`repl` with piped input (builds that have it)", exit 0 and the value `2` for `1+1`, with `--java-opt=-Duser.home=<a temporary folder>` so that the history file is not written to the real home folder (S3, Tests).
- The command-tree test: [48](48-command-tree.md). Help wording beyond the lines above: [50](50-help-and-messages.md).

## Risks

- From S3: the REPL's behaviour on a real terminal was not tested; whatever it does is upstream's. A SIGINT sent to tlaup alone does not reach the REPL.
- From the cut: the real-process scenarios depend on the store's test jar carrying `tlc2/REPL.class` for a rolling build (Traps); without it they fail with code 3, which is a loud failure, not a silent one.
