# 03. One TLC run through the components, and where TLA+ specs check the design

Written 2026-11-16, after the first wave's third revision. Not reviewed by a fresh agent yet. It adds no behaviour of its own: the first part restates, as one walk-through, what [00](00-overview.md), [11](11-runner.md), [12](12-tools-and-downloads.md), [20](20-groundwork.md) and [22](22-reporters.md) already design, and where it and those documents differ, they are right. The second part plans a check of the design that comes before stage 4 (decision D46): small TLA+ specs of the parts where several processes share files, checked with TLC, and stateful property tests that mirror them.

**Carried out on 2026-11-18**, by one agent, and not reviewed by a fresh agent yet. The specs, their bounds, the results and the findings are in [`specs/README.md`](../../specs/README.md); the fixes are in the design sections each spec models, marked "formal check"; the step functions are in [11 R6](11-runner.md#r6-run-folders), [12 V1](12-tools-and-downloads.md#v1-version-store) and [20 G3](20-groundwork.md#g3-java-launcher); the stateful tests are in `tests/stateful/`, marked `pending`. Part 2 below is the plan as it was written, with the property statements corrected where the check showed that they said more than the design can do; each correction is marked. It left three points to the maintainer. Two were settled on 2026-11-18 (decisions D49 and D50); the third, what a SIGKILL of tlaup reaches, waits on investigation question 35, with 33 and 34 as fall-backs. The specs' README lists them.

## Part 1. The components and one TLC run

### The layers

```
+--------------------------------------------------------------------------+
| Commands and CLI          Typer app, root group and error handler, cmd/  |
+------------------------+------------------------+------------------------+
| App context            | UI and messages        | Errors                 |
| paths, settings, ui    | two consoles           | four families -> codes |
+------------------------+------------------------+------------------------+
| Runner and tools       | Reporters              | Modules                |
| preflight, run folders | events to output       | registry, javac build  |
+------------------------+------------------------+------------------------+
| Tools store            | Java layer             | Config and paths       |
| builds, pin, GitHub    | locate, classpath, run | layered settings       |
+------------------------+------------------------+------------------------+
| Parser package (tlaup_parse): no I/O, imports nothing from tlaup         |
+--------------------------------------------------------------------------+
```

Each row may use the rows below it; nothing uses the commands ([00](00-overview.md#packages-after-the-first-wave), its rules). Two things the picture does not show: the runner calls a reporter, which sits in the same row; and the app context reaches domain code only as arguments the commands pass down, never as a global.

| Component | Purpose | Main interface | Design |
| --- | --- | --- | --- |
| Parser package | Turn TLC, SANY and PlusCal output lines into events and a result; know what a TLC exit code means. | `TlcParser.feed`, `close`, `result`; `SanyParser`; `PcalParser`; `describe_exit_status` | [10](10-parser.md) |
| Paths | Every folder tlaup uses, from the platform and the environment. | `AppPaths.from_env` | [14 F2](14-config-and-cli.md#f2-folder-overrides) |
| Config | Settings in layers, with where each value came from; a project layer cannot set the two security keys. | `load_settings`, `LoadedSettings`, `write_user_setting` | [14 F1](14-config-and-cli.md#f1-layered-configuration) |
| App context | Paths, lazily loaded settings and the UI, built once per process. | `AppContext`, `get_context` | [00](00-overview.md#application-context) |
| Errors | One error type in four families, each with its exit code. | `TlaupError`, `UsageError`, `NotSetUp`, `NotFound`, `Failed` | [20 G2](20-groundwork.md#g2-domain-errors), [02 X1](02-cross-cutting.md#x1-exit-codes) |
| UI and messages | The two consoles; errors, warnings, hints, notes, prompts. The only printer apart from reporters and commands. | `Ui` | [14 F6](14-config-and-cli.md#f6-messages) |
| Tools store | Installed builds, the pin and the lock; version syntax and order; GitHub client, release list and its cache; download and verify; what a build can do. | `ToolStore`, `Build`, `VersionSpec`, `GitHubClient`, `fetch_build`, `read_jar`, `install` | [12](12-tools-and-downloads.md), [02 X3, X4](02-cross-cutting.md#x3-version-syntax) |
| Java layer | Find `java` and `javac`, check and remember the version; build the classpath; start every Java process and handle signals. | `require_java`, `require_javac`, `ClasspathResolver`, `JavaInvocation`, `run_streaming`, `run_passthrough`, `signals_held` | [13](13-modules-and-java.md), [20 G3](20-groundwork.md#g3-java-launcher) |
| Modules | Registered override modules; build one in a temporary folder and move it into place. | `Registry`, `build_module`, `BuiltModule` | [13 M1 to M3](13-modules-and-java.md) |
| Runner and tools | The preflight, the pure command builder, run folders and their locks, the override check, the run itself; `sany`, `pcal`, `repl` on the same chain. | `resolve_tlc_invocation`, `build_tlc_command`, `run_folder`, `run_tlc`, `run_tlc_raw`, `resolve_tool_invocation` | [11](11-runner.md), [20 G1](20-groundwork.md#g1-tlc-invocation), [21](21-other-tools.md) |
| Reporters | Present events and the final outcome: terminal, live layout, collecting (tests); JSON later. | `Reporter`, `RunInfo`, `make_reporter` | [22](22-reporters.md) |
| Commands and CLI | Parse the command line, build requests, call domain code, print notes, map errors to exit codes. | `app`, `TlaupGroup`, `mapped`, one module per command | [14 F10](14-config-and-cli.md#f10-no-tracebacks), [23](23-command-layout.md) |

Joints that are named but have no written signature yet: `resolve_spec`, `resolve_cfg`, `find_project_root`, `make_reporter`, `upgrade` and `uninstall` as functions, `ClasspathResolver` after its change (described in [12 V10](12-tools-and-downloads.md#v10-remove-old-layouts) and [13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder) in words), and the members of `Event` one by one ([10 P3](10-parser.md#p3-result-model) lists them). Stage 4 writes them into the packages; none changes the structure.

### One `tlaup tlc` run, stage by stage

The labels on the arrows are what one stage hands to the next. Every value is frozen; no stage edits what an earlier one built.

```
+-----------------------------+
| tlc command                 |
| what the user typed         |
+-----------------------------+
              |
              | TlcRequest
              v
+-----------------------------+         +------------------------+
| Preflight                   | <------ | Store, Java, config    |
| spec, cfg, build, Java      |         | build, runtime,        |
+-----------------------------+         | settings               |
              |                         +------------------------+
              | TlcInvocation
              v
+-----------------------------+         +------------------------+
| Command builder             | ------> | Show-command           |
| pure function               |         | prints argv, exits 0   |
+-----------------------------+         +------------------------+
              |
              | JavaInvocation
              v
+-----------------------------+
| Runner and launcher         | ------------------+
| locked run folder, signals  |    stderr lines   |
+-----------------------------+                   |
              |                                   |
              | stdout lines                      v
              v                         +------------------------+
+-----------------------------+ events  | Reporter               |
| TLC parser                  | ------> | start, handle, finish  |
| lines to events and result  |         +------------------------+
+-----------------------------+                   ^
              |                                   |
              | RunResult                         |
              v                                   |
+-----------------------------+                   |
| RunOutcome                  | ------------------+
| exit code, result, kept     |       finish
| folder                      |
+-----------------------------+
```

1. **The command reads the command line.** `cmd/tlc.py` builds a `TlcRequest`: what the user typed, nothing looked up. Checks that need only the command line (options that conflict, the `--workers` value, Java option quoting) run here, so a usage error (2) never waits behind a prompt ([11 R11](11-runner.md#r11-preflight)).
2. **The preflight resolves everything** (`resolve_tlc_invocation`, decision D45), in this order: the spec (`NotFound`, 4); the cfg if one was named (4); the tool build through `get_build`, the pinned build from the store or the first-run prompt ([12 V9](12-tools-and-downloads.md#v9-first-run-prompt); `NotSetUp`, 3); Java (3); then the project root, classpath from the modules registry and settings, override check, workers, JVM options. It returns a `TlcInvocation`. Nothing has been created or started; warnings are collected in it, not printed.
3. **The command builder makes the command** (`build_tlc_command`), a pure function: `TlcInvocation` to `JavaInvocation` (java, JVM options, system properties, classpath, main class, arguments). Nothing edits the list afterwards, so `--show-command` prints exactly what runs.
4. **Show-command stops here.** It prints the argument list on stdout and exits 0. It never prompts, installs, creates a folder or sweeps.
5. **The command prints the preflight's warnings** and calls a run function.
6. **The runner enters its frame** ([11](11-runner.md), the frame before R1): `signals_held()` first, so a signal at any later moment is recorded and never reaches Python's default handler; then `run_folder()`, which takes the run's lock, makes `<cache>/runs/<run-id>/`, writes `run.json` and sweeps old folders ([11 R6](11-runner.md#r6-run-folders)). `reporter.start(run_info)` is the last thing before the child starts.
7. **The launcher runs Java** (`run_streaming`): two reader threads, a bounded queue, the main thread calling `on_stdout` and `on_stderr`. Stdout lines go to `TlcParser.feed`, whose events go to `reporter.handle(event, result)`; stderr lines go to `reporter.stderr_line`. A first signal terminates the child, a second or the end of the grace period kills it ([20 G3](20-groundwork.md#g3-java-launcher)). It returns a `ProcessOutcome`.
8. **The runner settles and finishes.** `folder.settle(process)` decides once whether the folder is kept (the run did not finish and a checkpoint is there). The runner builds the `RunOutcome` (the parser's `RunResult`, exit code, tool exit code, the signal, stderr tail, warnings, kept folder and resume command) and calls `reporter.finish(outcome)`, then `reporter.close()` in a `finally`. Leaving the frame deletes or keeps the folder, releases the lock and restores the signal handlers.
9. **The command prints the notes** ("Checkpoint kept" and the resume command, on stderr, `print_run_notes`) and exits with `outcome.exit_code`.

Paths the list leaves out:

- **`--raw`** (`run_tlc_raw`): the same frame and the same run folder with its lock, but `run_passthrough` gives the child the terminal; there is no parser and no reporter, and the outcome has no result.
- **`sany`, `pcal`, `repl`** take a shorter chain: `resolve_tool_invocation` to `ToolInvocation`, `build_tool_command` to `JavaInvocation`, the launcher. SANY and PlusCal read both streams through one pipe into their own parser; the REPL is passed through and leaves Ctrl-C to the child ([21](21-other-tools.md)).
- **Errors.** Any stage can raise a `TlaupError`. It passes up through the frame, which settles the folder and attaches the "Checkpoint kept" note to the exception if one was kept, to the root group's handler, which prints `error:` and the notes and exits with the family's code ([14 F10](14-config-and-cli.md#f10-no-tracebacks)).
- **A closed stdout** ends in 141 after the frame has stopped the child, closed the reporter and settled the folder ([11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are)).

## Part 2. TLA+ specs of the design

### Where a spec earns its place

Most of tlaup is a sequence of functions over frozen values in one process. TLC adds little there; the tests of [01](01-testing.md) (golden files, property tests, feature files) check it more directly. A spec is worth writing where several actors change shared state in steps that can interleave: several tlaup processes, TLC itself, a sweep, the user's signals. Those are the places where the design argues its safety in prose, and where a missed interleaving loses data.

| # | Component | Why a spec | Priority |
| --- | --- | --- | --- |
| K1 | Run folders and their locks ([11 R6](11-runner.md#r6-run-folders)) | Starting runs, sweeps of other tlaups, `cache clean`, `-recover` into another run's folder and a killed tlaup all act on `<cache>/runs/`. The design's safety rests on lock order, a five-second wait, a one-hour age rule for lock files and removing a lock file while its lock is held. | First |
| K2 | Tools store: install, upgrade, uninstall, pin, readers ([12 V1](12-tools-and-downloads.md#v1-version-store), [V3](12-tools-and-downloads.md#v3-uninstall), [V4](12-tools-and-downloads.md#v4-upgrade-and-pin), [V11](12-tools-and-downloads.md#v11-concurrent-installs), [V12](12-tools-and-downloads.md#v12-install)) | Downloads run outside the lock, moves and pin writes under it; readers (the preflight, `tool path`) never lock; `.tmp/` is cleaned by whoever holds the lock next. | Second |
| K3 | Signals in the launcher ([20 G3](20-groundwork.md#g3-java-launcher), [11 R2](11-runner.md#r2-signals)) | A small state machine with a measured race: a signal before the child exists, while `Popen` returns, during the run, after it; the grace period; the exit code chosen. | Third |

Not specs, and why: the parser, the command builder, the preflight order, config merging, version syntax and sorting are sequential and have direct tests. The modules registry ([13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder)) uses the store's pattern (build in `.tmp/`, one rename, a lock); it gets a spec only if K2 finds a flaw in that pattern.

### K1 Run folders

**What is modelled.** A few tlaup processes, each running the steps of R6 as separate actions: create the lock file; take its lock (waiting, with a timeout); for `-recover` into a run folder, take that folder's lock; make the folder; write `run.json`; sweep; start TLC; TLC writes a checkpoint; the run finishes, is interrupted or tlaup fails; settle; end (delete the folder, remove the lock file while holding the lock, release). Also `cache clean` with and without `--all`, a tlaup killed with SIGKILL (its locks are released, its TLC runs on), and time passing in coarse steps (young, older than an hour, older than a day, older than 30 days).

A lock belongs to the file, not to its name, as `flock` and `fcntl` locks do: removing a lock file and creating a new one under the same name gives a second lock. The spec models names and files apart so that TLC can see what that does.

**Properties.**

- `NoDeleteUnderTLC`: no folder is deleted while a TLC process works in it, unless the tlaup that owns it was killed (the case R6 accepts under "Risks"); the spec states the exception as a separate property so its reach is visible.
- `OneTLCPerFolder`: at most one TLC process writes a given run folder (the `-recover` rule 2).
- `KeptSurvives`: a kept folder with a checkpoint is not removed before it is 30 days old, except by `cache clean --all`, and by the end of a run that resumed from it and finished (R6, `-recover` rule 3; the first wording left this out, corrected 2026-11-18). Since decision D49 the same holds for a folder that was never settled and holds a checkpoint (`CheckpointSurvives` in the spec).
- `LockExclusive`: no two processes hold the lock of one name at the same moment, counting a process until it has removed the lock file; from then on it only releases. (The first wording, "hold a lock on files that have the same name", is false in the instant between removing a lock file and releasing its lock; corrected 2026-11-18, finding K1-1.)
- `NothingLeft` (liveness, under fairness of the end and sweep steps): every folder that was not kept, and every lock file with no folder, is eventually removed.

**Questions the check must answer.** Whether removing a lock file while holding its lock, at the end of a run and in the sweep, can let a process that opened the old file earlier and a process that creates the new one both believe they hold the lock. Whether the one-hour rule closes the gap between creating a lock file and locking it, for every order of sweep and start. Neither has been checked.

**Answered 2026-11-18** ([details](../../specs/README.md#runfolders)). The first: not with a lock library that looks at the file again once it has the lock, which the locked `filelock` does; without that second look, yes (question 30 decides which versions qualify). The second: with the second look the gap is closed with or without the rule; without it the rule closes the gap unless an hour passes while a run is starting.

### K2 Tools store

**What is modelled.** Installers (download to their own `.tmp/` folder outside the lock, take the store lock, find a build with the same name and SHA-256 or move theirs into place, pin if nothing is pinned, release), upgrade (install the new build, move the pin only if it named the replaced build, remove the old), uninstall (rename into `.tmp/`, delete; clear the pin if the pinned build went), pin, readers (read the pin, then open the jar, without the lock), a killed process leaving a `.tmp/` folder, and the `.tmp/` cleanup by the next mutation.

**Properties.**

- `PinConsistent`: whenever the store lock is free, the pin is absent or names an installed build, unless a tlaup was killed while it held the lock. (The exception was added 2026-11-18: as V3 orders its steps, an uninstall killed between removing the pinned build and clearing the pin leaves such a pin. Finding K2-2; the maintainer kept the order and accepted that state, decision D50.)
- `NoPartialBuild`: a reader never sees a build folder that is half moved in or half deleted.
- `ReaderOutcome`: a reader ends with a jar it opened or with `PinnedBuildMissing`; never with another build than the one the pin named when it read it. (Corrected 2026-11-18, finding K2-3: there is a third ending. When the build is removed between the preflight's look and Java opening the jar, Java fails with its own message and exit code 1.)
- `NoDuplicate`: no two installed builds have the same name and SHA-256.
- `TmpOwnerSafe`: a `.tmp/` folder whose owner is alive is never removed.
- `PinNeverMovesSilently`: the pin changes only by `pin`, by `uninstall` of the pinned build (to absent), by `upgrade` of the pinned build, or by the first install.

### K3 Signals

**What is modelled.** The launcher's phases (handlers installed, child not started, `Popen` returning, child attached, child exited, summary printed, handlers restored), signals INT, TERM and HUP arriving at any phase, each either ignored at entry or not, the grace period running out, and the REPL's choice to leave Ctrl-C to the child.

**Properties.**

- `NoDefaultHandler`: between entering and leaving `signals_held`, no signal reaches Python's default handler.
- `ChildNeverOrphaned`: when tlaup exits, the child has exited (SIGKILL of tlaup is outside the model).
- `ExitCode`: the exit code is the first signal's code if it was recorded by the time the launcher saw the child gone, otherwise the run's own (G3's table). (Corrected 2026-11-18, finding K3-1: the first wording, "if it arrived before the child exited", asks tlaup to know something it cannot see.)
- `IgnoredStaysIgnored`: a signal ignored at entry has no handler and is ignored by the child.
- `NothingStartsAfterSignal`: if a signal was recorded when the run function looked, immediately before the start, no child is started; a signal after that look reaches the child as soon as it is attached. (Corrected 2026-11-18, finding K3-2: the first wording, "recorded before the start", is false for a signal between the look and `Popen`.)

### Specs and their tests

**Where they live.** `specs/` at the repository root: one `.tla` and one `.cfg` per spec (`RunFolders`, `ToolStore`, `Signals`), and a `README.md` that says for each spec what it models, what it leaves out, the bounds of its `.cfg`, the TLC build it was checked with, the number of states and the result. As built (2026-11-18), `specs/variants/` holds more `.cfg` files beside the three: one per answer to an open question, per option the maintainer was asked to choose between, and per property that is expected not to hold; the first line of every `.cfg` says what TLC should report, and `specs/check.sh` runs them all and compares. TLC's own output folders and trace files are ignored in `.gitignore`. The specs are checked with a released TLC through plain `java -cp tla2tools.jar tlc2.TLC` or the released tlaup; the tlaup being designed does not exist yet. Running them in the integration job, with the tlaup they describe, is a later step and not part of this plan.

**Stateful property tests mirror the specs.** For each spec, one Hypothesis `RuleBasedStateMachine`:

- each process of the spec is a Python object holding its own lock objects and its position in the protocol;
- each action of the spec is a rule that advances one process by one step, with the same enabling condition as a precondition;
- each safety property of the spec is an `@invariant`, checked on the real files after every step;
- time is the injected `now`; a lock file's age, which R6 takes from the file's modification time, is set with `os.utime`;
- the real code is used for every step: real `filelock` locks in a temporary cache folder. R6 records that a second lock object on the same file in one process is refused like a lock in another process (tried with the locked `filelock`), which is what lets one test process stand for several tlaups. Each machine also has one plain test that runs a second Python process to confirm that, for the lock and the store.

Hypothesis then explores random interleavings of the same steps TLC checked exhaustively in a small model, on the code instead of the design. The tests run in the default suite with the CI profile of [01 T7](01-testing.md#t7-property-tests-for-values).

As built (2026-11-18, `tests/stateful/`; what each machine covers and how it was tried is in [the specs' README](../../specs/README.md#the-stateful-tests)):

- Each machine can be run against the code it is written for, which does not exist yet (those tests carry the `pending` marker), and against a throwaway model of the same step functions kept beside it (`reference_*.py`), so the machine itself could be tried. The work package that builds the code deletes the throwaway model.
- Random steps reach a race only by chance, and a machine as first written missed most of a set of deliberately broken models. Three things were added for that, and they are part of the pattern: a start-up phase that leaves behind what earlier commands left, made with the same step functions, so that the interleaving starts from a state worth racing in; the same bounds as the spec's model on the steps that end a command early (one kill per example); and, for every counterexample TLC gave for a fix, a plain test that replays its steps in order, so that the fix is tested on every run and not only when the dice fall that way.
- The machine for the signals has no second process to stand for: the test process is the tlaup of the spec and sends itself real signals between the steps.

**What this needs from the code.** The steps must be callable one at a time. `run_folder` today is one context manager and `ToolStore.add` one call. The design therefore adds step-level functions under the public ones, for example `rundirs.RunStart` with `create_lock_file`, `take_lock`, `take_recover_lock`, `make_folder`, `write_run_json` and `sweep`, which `run_folder` calls in order; and the same for install, upgrade and uninstall. Their exact names are written into [11 R6](11-runner.md#r6-run-folders) and [12 V1](12-tools-and-downloads.md#v1-version-store) once the specs fix the steps. (Done 2026-11-18; the launcher's are in [20 G3](20-groundwork.md#g3-java-launcher), which this paragraph had not foreseen: the signals machine needs the check, the start and the attach as separate calls.) The cost: the tests depend on the protocol's steps, so a change to the protocol changes the spec, the machine and the code together. That is the point of the exercise and is accepted.

**Rejected.** *One spec of the whole system*: most of it is sequential and the model would be large without checking more. *Trace validation* (TLC checking a log of a real run against the spec): stronger, but needs logging in the product code for its own sake; worth looking at if a stateful test and the spec disagree in a way that is hard to read. *Tests without a spec*: Hypothesis samples interleavings and can miss the rare one; TLC covers all of them in the bounded model, so the two together check both the design and the code.

### Order

1. Write K1 and check it with TLC. Then K2, then K3.
2. Every counterexample is a finding against the design section it breaks. It goes into that section as a fix, with the trace summarised in the spec's README, and the spec is checked again. A finding that needs a decision goes to the maintainer.
3. Write the stateful property tests from the checked specs. They are written before the code they test exists and fail at first; each is handed to the work package that builds its code as its "test first", and that package is done when they pass. Until then they are kept out of the default run by a marker (`pending`, registered, deselected in the CI configuration); the package removes the marker as its first commit.
4. A fresh agent reviews the specs and the tests against the design sections, and the maintainer signs off. Only then does stage 4 start.

If TLC finds no flaw, the specs and the machines go into stage 4 unchanged. If it finds one, the fix changes the design first, and the sign-off of stage 3 covers the fix.

**Depends on.** Sign-off of the first wave. Java 11 or newer and a released `tla2tools.jar` on the machine that checks the specs. `hypothesis`, already a development dependency in [01](01-testing.md).

**Risks.** A spec says what its writer understood of the design; a gap in both is not found. The bounded model (two or three processes, a few runs) may miss a flaw that needs more; the README states the bounds. The stateful tests interleave at step boundaries only: a race inside one step (two system calls in `os.replace`, the file system's own ordering) is outside both the spec and the tests.
