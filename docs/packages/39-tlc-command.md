# 39. The `tlc` command: switch to the new runner

Size: L. Suggested model: most capable. Status: built.

## Goal

`tlaup tlc` runs through the new chain: request, preflight, pure command builder, run folder, launcher, parser, reporter. The old runner and the old parser stack are gone (their tests went with the old suite in [03](03-test-foundation.md), decision D62), the `tlc` feature files exist, and the changelog says what a user now sees. On this `main` output is plain on every stream; the live layout, `--plain` and `--refresh-interval` come with [40](40-live-display.md).

## Covers

- Roadmap items. This package is where each becomes true for a user; "in part" names who built the piece underneath.
  - [Milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust):
    - "Report run errors as what they are." In part: the command path and its scenarios; mechanism in [21](21-java-launcher.md), [37](37-run-tlc.md), [17](17-error-handler.md).
    - "Forward SIGTERM to the JVM so a CI timeout does not leave TLC running; exit 130 on Ctrl-C; survive a second Ctrl-C while draining output." In part: `tlc_signals.feature`; mechanism in 21 and 37.
    - "Do not crash on non-UTF-8 bytes in TLC output." In part: the two scenarios; mechanism in 21, the warning in [33](33-tlc-invocation.md).
    - "Pass a `--cfg` file outside the project root to TLC so that TLC reads the file that was validated ..." In part: the scenario and the changelog; functions in [32](32-spec-resolution.md), preflight in 33.
    - "Spec names: a dot in the name is mangled by `with_suffix` ..." In part: the command and the changelog; function in 32.
    - "Stop run-cache cleanup from deleting other specs' directories ..." In part: `--keep`, the run-folder scenarios of `tlc_run.feature`, the removal of `--cleanup` and of the old run cache; run folders in [35](35-run-folders.md); `cache list` and `cache clean` in [45](45-cache-commands.md).
    - "The run-cache fingerprint covers the default `.cfg` only ..." In part: `compute_spec_hash`, `_cleanup_stale_spec_dirs` and `get_spec_run_dir` are deleted here (R12; their three tests went in 03); settled by 35.
    - "Report clearly when an override module fails to load (raised list)." In part: the two scenarios and the changelog; check in [34](34-override-check.md).
    - "Pass everything after `--` to TLC. Add `--workers`, defaulting to `auto` ..." In part: the declarations and the scenarios; rules in 33.
    - "Make `--show-command` print the exact command that would run, including `-tool`, shell-quoted, without creating or deleting anything in the run cache." In full, apart from the `rundirs` unit test R9 names, which is 35's.
    - "One preflight used by every `tlaup tlc` path ..." In part: `tlc_errors.feature`; function in 33.
    - "First-run prompt (decision D4) ..." In part: the wrappers round `ensure_tools`, `--auto-install` on `tlc`, `first_run.feature`; functions in [28](28-first-run.md).
    - "Java options: a `TLAUP_`-prefixed variable and a repeatable flag ..." In part: `--java-opt` on `tlc`, the scenario, J1's entries; rule in 33. Nothing reads `JAVA_OPTS` since [19](19-layered-config.md) dropped the old validator.
    - "Use `JAVA_HOME` when set, falling back to `PATH`, for both `java` and `javac`." and "One Java start per run ..." In part: the scenarios through `tlaup tlc`, the removal of `get_tlc_version` and `tlc --version`; functions in [20](20-java-location.md).
  - [Milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout):
    - "A single TLC invocation value ... shared by the show-command, raw and formatted paths ... One process loop instead of two copies." In part: the short command function and `print_run_notes`; value in 33, loop in 37.
    - "A reporter interface fed by the parsed result and run events ... the command shrinks to option parsing, error mapping and the exit code." In part: the shrinking, and `make_reporter`; interface in [36](36-reporter-interface.md).
    - "Delete display code that nothing in `src/` references ... Remove the duplicated callback (`cmd/tlc.py:157-238`) and the three copies of the elapsed-time logic." In part: the callback and the copies go with the old `cmd/tlc.py`.
    - "Review the layout of every command ..." In part: the `tlc` row of the tree, without `--plain` and `--refresh-interval` (40); the tree test is [48](48-command-tree.md).
  - [Milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this):
    - "The `tlaup tlc` command path is tested end to end: exit codes, raw mode, missing Java and Ctrl-C." In full, apart from `tlc_live.feature` (40).
- Design sections:
  - [20 G1](../design/20-groundwork.md#g1-tlc-invocation): the command function, `print_run_notes`, and the plain pytest test of the two commands.
  - [11 R9](../design/11-runner.md#r9-show-command): all of it but the `rundirs` unit test.
  - [23 C1](../design/23-command-layout.md#c1-command-tree): the `tlc` row; `SPEC` required; `--version` and `--cleanup` gone.
  - [14 F4](../design/14-config-and-cli.md#f4-config-commands-with-a-broken-file): its scenario for the new `tlc` ("with a broken file, `tlaup tlc Spec` exits 3, names the key and prints no traceback"); the rest is [44](44-config-commands.md)'s.
  - [22 O1](../design/22-reporters.md#o1-reporter-interface): `make_reporter` and the command sketch. [22 O2](../design/22-reporters.md#o2-delete-dead-display-code): the rows of its table marked O3, as deletions (see Files).
  - The command-level tests of [11 R1 to R8, R11](../design/11-runner.md), [20 G3](../design/20-groundwork.md#g3-java-launcher), [02 X1 and X2](../design/02-cross-cutting.md#x1-exit-codes), [12 V9](../design/12-tools-and-downloads.md#v9-first-run-prompt), [13 J1 to J3](../design/13-modules-and-java.md#j1-java-options), and [01 T5](../design/01-testing.md#t5-feature-files-and-steps) "What the `tlc` features cover", the checkpoint steps that question Q10 added included.
  - The changelog entries listed under Changelog.
- Rows of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) this package owns: R1, R2, R10, R11, R12, R14, M20, J2 and J3; under Tests each is named beside its scenario. It also writes the scenarios of two rows other packages own: R7 (owner [35](35-run-folders.md)) and C6's relative `module_path` through `tlaup tlc` (owner [33](33-tlc-invocation.md); finding G8). R14 with a real JVM is [52](52-integration-tests.md)'s (finding G1).

## Depends on

- [02](02-errors-and-paths.md), [16](16-ui-messages.md), [17](17-error-handler.md): `AppContext`, `Ui`, the root group that maps errors and prints an exception's notes, `python -m tlaup`.
- [18](18-feature-harness.md): `tests/test_features.py`, the steps (the checkpoint forms `once java has begun its checkpoint` and `java answers its version check with ...` included), the real-process and terminal helpers, the placeholders.
- [19](19-layered-config.md): `ctx.settings` (`tlc.workers`, `tlc.keep`, `java.*`).
- [28](28-first-run.md): `ensure_tools`. [29](29-tool-commands.md): the store, the remote listing and the client as the `tool` commands build them, and the store steps of the features.
- [31](31-module-commands.md): the old `cmd/modules` is gone. It imports `tlc/run_cache.py` and `tlc/compiler.py`, which this package deletes; the scenarios with a registered module need `tlaup module add` or its Given step.
- [33](33-tlc-invocation.md): `TlcRequest`, `resolve_tlc_invocation`, `build_tlc_command`. [34](34-override-check.md): the override warnings inside the invocation.
- [35](35-run-folders.md): the run folders the scenarios assert on (`run.json`, the lock files, the kept note's lines).
- [37](37-run-tlc.md): `run_tlc`, `run_tlc_raw`, `RunOutcome`. [38](38-terminal-reporter.md): `TerminalReporter` in plain mode.
- [05](05-github-recordings.md) and [07](07-golden-files.md): the recordings `first_run.feature` is served from; the golden captures and specs the fake `java` replays.

Changes from the draft (37, 38, 34, 28, 29, 18): 31 is added, for the reason above. 33 and 35 are named because the command and the scenarios use them directly. The others are the foundation the draft had through its entries.

## Files

Creates:

- `tests/features/tlc_run.feature`, `tlc_errors.feature`, `tlc_signals.feature`, `tlc_raw.feature`, `tlc_show_command.feature`, `first_run.feature`, and their expected files under `tests/features/expected/`.
- `tests/unit/cmd/test_tlc_command.py` (the plain pytest tests named under Tests).
- In `tests/steps/`: the steps of T5's table that these scenarios use and no earlier package wrote.

Rewrites:

- `src/tlaup/cmd/tlc.py`: the command function, `print_run_notes`, the two `get_build` wrappers. Nothing of today's file stays.

Changes:

- `src/tlaup/reporters/__init__.py`: `make_reporter` (see Interfaces). If [36](36-reporter-interface.md) or [38](38-terminal-reporter.md) already created it, this package only calls it.
- `src/tlaup/cli.py`: the line that registers `tlc`. Every switch package edits one such line.
- `src/tlaup/java/classpath.py`: the string-returning methods the old runner used (`os.pathsep.join(resolver.resolve(...))` and `get_tla_library_property()`), which [33](33-tlc-invocation.md) left beside its path-returning ones, are deleted with the old runner (reconciled by stage 4).
- `src/tlaup/tlc/formatter.py` and `src/tlaup/tlc/components.py`: cut down to what [40](40-live-display.md) owns (see "What stays for 40"), and their imports of names this package deletes go (`formatter.py` imports `SanyMessage` from `tlaup.tlc.sany` at the top; finding C11).
- `src/tlaup/tlc/run.py` becomes `src/tlaup/tlc/runner.py`, the name of 00's tree, once the old `runner.py` is deleted; `tests/unit/tlc/test_run.py` becomes `tests/unit/tlc/test_runner.py`; the two `TYPE_CHECKING` imports of `tlaup.tlc.run` that [37](37-run-tlc.md) put into `src/tlaup/reporters/base.py` and `collecting.py` follow (finding C12).
- `CHANGELOG.md`; `docs/contributing/development.md`, where its code map names files this package creates or deletes.

Deletes:

- `src/tlaup/tlc/runner.py` as release 0.8.x has it (`resolve_spec_file`, `resolve_cfg_file`, `get_override_classes`, the old `build_tlc_command` and `run_tlc`, `get_tlc_version`); the new one takes its name (above).
- `src/tlaup/tlc/run_cache.py`, `parser.py`, `codes.py`, `values.py`, `sany.py`, `compiler.py`.
- From `tlc/formatter.py`: `ValueDiff`, `render_sany_error`, `diff_values`, `render_value_diff`, `render_error_trace`, `render_coverage_table`, `render_inline_coverage`. From `tlc/components.py`: `StatsTableFormatter`, `StatusFooterRenderable`. These are the rows of O2's table that O3 replaces; they are what users saw until this switch.
- What is left of `src/tlaup/versioning/paths.py` (`get_run_dir`, `get_tlc_run_dir`, after [29](29-tool-commands.md) and [31](31-module-commands.md) took the rest): the file whole once nothing is left in it; `run_cache.py` was the last caller.
- `cache_dir()` in `src/tlaup/config/loader.py`: `versioning/paths.py` was its last caller once [04](04-delete-dead-code.md) removed the legacy fallbacks; and in `tests/unit/test_context.py` (02's test) the assertion that `cache_dir()` follows `TLAUP_HOME`, which [02](02-errors-and-paths.md) and [19](19-layered-config.md) hand here. `config_dir()` and its assertion are [44](44-config-commands.md)'s (finding F2). If a grep finds another caller of `cache_dir()`, the pull request names it and leaves the function for that caller's package.
- No old test: every old test file, the integration ones included, went with the old suite in [03](03-test-foundation.md) (D62).

**What stays for 40.** O2 says the layout is unfinished code, not dead code, and puts the removal of `TlcDisplay` and its pieces in the pull request that lands O4 (40). So this package leaves, unused by any command and with no test:

- `src/tlaup/tlc/formatter.py`: `_Section`, `TlcDisplay`, and of `TlcFormatter` the constructor, `create_layout`, `update`, `_has_child`, `_ensure_layout_structure`, `update_header`, `update_stats`, `update_logs`, `update_clock`; `StatusInfoRenderable`.
- `src/tlaup/tlc/components.py`: `LogDeduplicator`, `HeaderComponent`, `StatusInfoComponent`, `LogsComponent`, `StatsTableComponent`.
- `src/tlaup/tlc/models.py`, whole: the two files above import `CheckState`, `InitialStateStatItem` and `ModelCheckResult` from it.

40 deletes all three when `render_layout` and its frame files arrive. Not left: `java/inspector.py` and `cmd/check_java.py` are not this package's either way; `check-java` uses them until [46](46-doctor.md).

Files another package of the same period touches: `src/tlaup/cli.py` (one line per switch package); `CHANGELOG.md`; `tests/steps/*.py` with every package that adds steps after this one (40 to 47), each adding functions, none editing these; `src/tlaup/reporters/base.py` and `collecting.py` (one import line each).

## Interfaces

Provides.

```python
# tlaup/cmd/tlc.py
def tlc(ctx: typer.Context,
        spec: str,                                   # required (C1); Typer reports a missing one itself, exit 2
        tlc_args: list[str] | None = None,           # variadic; everything after `--` (R8)
        cfg: str | None = None,                      # --cfg FILE
        workers: str | None = None,                  # --workers N|auto
        coverage: bool = False,                      # --coverage
        raw: bool = False,                           # --raw
        keep: bool = False,                          # --keep; there is no --no-keep (D53)
        show_command: bool = False,                  # --show-command
        java_opt: list[str] | None = None,           # --java-opt OPT, repeatable
        auto_install: str | None = None) -> None     # --auto-install stable|rolling, else TLAUP_AUTO_INSTALL

def print_run_notes(outcome: RunOutcome, ui: Ui) -> None     # 20 G1, 11 R6; everything it prints goes to stderr

# tlaup/reporters/__init__.py
def make_reporter(ctx: AppContext, options: ReporterOptions) -> Reporter     # written by stage 4 from 22 O1 and O4
```

The command function is G1's sketch; nothing else belongs in it:

```python
inv = resolve_tlc_invocation(
    request, paths=..., settings=..., env=..., cwd=..., home=..., get_build=..., now=..., rng=...
)
java_inv = build_tlc_command(inv)
if show_command:
    ui.out.print(
        join(replace(java_inv, lifeline=False).argv()),  # 11 R9: no lifeline; one line,
        markup=False,
        highlight=False,
        soft_wrap=True,
    )
    return  # never wrapped or read as markup; exit 0
for text in inv.warnings:
    ui.warning(text)
if request.raw:
    outcome = run_tlc_raw(inv, java_inv, paths=paths, now=now, notice=ui.note)
else:
    outcome = run_tlc(inv, java_inv, make_reporter(ctx, options), paths=paths, now=now, notice=ui.note)
print_run_notes(outcome, ui)
raise typer.Exit(outcome.exit_code)
```

- `request`: `TlcRequest(spec, cfg, workers, coverage, raw, keep=True if --keep else None, java_opts, extra_args)`. `--workers` and `--keep` travel in the request and are not merged into the settings ([33](33-tlc-invocation.md), Traps).
- `get_build`, the two wrappers (G1, R9, V9). For a run: `ensure_tools(store, remote, client, ui, auto_install=..., may_install=True)`. For `--show-command`: the same call with `may_install=False`, which returns the pinned build or raises `NoToolsInstalled`, `NoPinnedBuild` or `PinnedBuildMissing`, never asks, never installs and sends no request, whatever `--auto-install` and `TLAUP_AUTO_INSTALL` say.
- `--auto-install`: `stable` or `rolling`; any other value, from the option or the variable, is a usage error (2), and it is found before the preflight is called, so it does not wait behind the spec check or a prompt ([02 X1](../design/02-cross-cutting.md#x1-exit-codes), rule 5).
- `join`: `shlex.join` on Linux and macOS, `subprocess.list2cmdline` on Windows (R9). One line on stdout, printed as text and never wrapped (G1's sketch, [10 P11](../design/10-parser.md#p11-tlc-text-and-rich-markup)): a path with `[` in it is not markup.
- `--show-command` prints no warnings, does not sweep and makes no folder or lock: it stops before either run function.
- `print_run_notes` prints, in this order and only what applies: for a kept run folder, the two note lines of [R6](../design/11-runner.md#r6-run-folders) ("Checkpoint kept (...): <folder>" and "Resume with: ..."), built by 35's one function and carried by the outcome; for a raw run whose checkpoint was not kept, the words of `outcome.dropped_checkpoint` as one line (in a parsed run the reporter's result line already has them, [22 O3](../design/22-reporters.md#o3-terminal-reporter)); for a parsed run whose exit code and verdict disagree, the warning of [10 P3](../design/10-parser.md#p3-result-model): `warning: TLC exited with 0, but its output reports 2 errors` (code 0 and the verdict `errors`, `not-checked` or `incomplete`), or `warning: TLC exited with 255, but its output reports no error` (code not 0 and the verdict `no-error` or `no-error-bounded`). A raw run has no verdict and gets no such warning.
- `make_reporter`: the one function in which a command chooses a reporter; milestone 4's `--json` attaches there. In this package it returns the plain `TerminalReporter` of 38 on `ctx.ui`, with the real clock. `ReporterOptions` is a small frozen value of what the command line says about output; it has no field this package reads, and 40 adds `plain` and the rule about streams, `TERM` and size. A worker may start with `make_reporter(ctx)` and let 40 add the parameter.

Help strings the R sections ask for, one line each; [50](50-help-and-messages.md) may reword them, not drop them:

- `--raw`: prints TLC's own output unchanged; on Windows a closed output pipe does not stop TLC (R1).
- `--show-command`: the printed command does not stop TLC when the terminal that pasted it is killed; for a long run pasted by hand, replace the `-metadir` value with a folder of your own (R9).
- The arguments after `--`: shown only in the `--` form; relative paths after `--` are read from the folder you run tlaup in, `-config` from the spec's folder; absolute paths are advised (R4, R8). TLC's own help sentence for `-dumpTrace` ("relative to the same directory as the main spec") is wrong with an absolute spec and is not copied.
- `--java-opt`: shown in the `=` form, `--java-opt=-Xmx8g` (J1).

Consumes: `resolve_tlc_invocation`, `build_tlc_command`, `TlcRequest` (33); `run_tlc`, `run_tlc_raw`, `RunOutcome` (37); `TerminalReporter` (38); `ensure_tools` (28); `ToolStore` and what `ensure_tools` needs (23, 25, 24, as 29 builds them); `AppContext` (02); `Ui` (16); `JavaInvocation` (21).

## Tests that must pass

Scenarios run in-process unless one of T5's five situations applies ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 10); the lists say which. Every `--raw` scenario that starts Java is a real process. TLC output is always a golden capture replayed by the fake `java`, never typed (rule 3). Real-process scenarios start from a store that already holds what they need.

### A. In-process scenarios and plain pytest

`tests/features/tlc_run.feature`:

- X1 (inventory row R1): each golden case is replayed and its exit code passes through (an outline over the cases of `cases.toml`, both builds). One of them is `violation`: `stdout matches the expected file "tlc_run/violation.txt"` and `java was started with "-tool"`.
- X2: for `violation`, the verdict, the error text and the trace are on stdout, and stderr holds nothing but the header and progress.
- P3: the case that exits 0 with two errors (`deadlock-flag-multierror`) prints the disagreement warning on stderr and exits 0.
- R3: the synthetic case `invalid-utf8` (bytes `FF FE` in an output line, a Latin-1 `é` in a value) is replayed; the exit code is the case's and the surrounding lines are intact.
- R4: `--cfg ../outside/out.cfg` with a decoy `out.cfg` in the project root; the logged Java command names the outside file, relative to the spec's folder; the spec in the logged command is absolute; `java was started in the folder` is the folder the command ran in.
- R6: after a successful run and after a failing run, `the cache holds no run folders` and `the cache holds no lock files`.
- R6, keeping. The fake writes a complete checkpoint (`java writes "queue.chkpt, vars.chkpt" into its metadir`):
  - exit 255 under `--keep`: one run folder is kept, stderr names it with its size and the reason, and the resume command on stderr holds the absolute spec, the absolute `--cfg`, `--keep`, the TLC arguments of the run and the `-fp` and `-seed` of `run.json`;
  - exit 12 under `--keep` (a violation): nothing is left;
  - exit 255 without `--keep`: nothing is left, and the result line says a checkpoint was not kept and names `--keep`;
  - exit 255 with `TLAUP_TLC_KEEP=1` and no flag: kept.
- R6, an incomplete checkpoint under `--keep` (`queue.chkpt, queue.tmp`, and separately `settings.tmp.chkpt` without `vars.chkpt`): nothing is left, and the output says the checkpoint was incomplete.
- R6, `-fp` and `-seed`: the logged Java command has both when the arguments had neither, and only `-seed` of tlaup's when they had `-fp 3`.
- R6: two runs of specs `Foo` and `Foo_bar` do not disturb each other.
- R6, the reminder: with a kept folder in the cache, a second `tlaup tlc` prints the reminder line once on stderr (`1 kept run folder holds ... (tlaup cache list)`); `--show-command` does not.
- R6, resuming, two runs in one scenario with `{kept}`: a second run with `-- -recover {kept}/<TLC's folder>` passes the kept folder's `-fp` and `-seed` and deletes that folder when the fake exits 0; when the fake exits 255 again the folder is kept and the resume command printed has one `-recover`. The same with `-- -metadir <a folder of the test's> -recover {kept}/...`: the kept folder is still deleted after exit 0 and no folder is made under `{runs}`.
- R6: `tlaup module add` leaves a kept run folder alone.
- R7, the run folder (inventory row R7, with [35](35-run-folders.md)) and C6 (inventory row C6, with [33](33-tlc-invocation.md); finding G8): with `the config file contains:` `module_path: mods` and `module_lib_path: jars`, relative, and the folders `{work}/mods` and `{work}/jars` holding a module file and a jar, `tlaup tlc Spec` gives a logged command where `the java command matches the expected file "tlc_run/module-path-relative.txt"`: the file shows `{work}/mods` in `-cp` and in `-DTLA-Library`, the jar of `{work}/jars` in `-cp`, and `-metadir {runs}/<run-id>`, under tlaup's cache and not beside the spec. 33's unit tests hold the rule; this scenario is the feature the row's note asks for.
- R7: with a registered module whose class is `QueueOverrides` and v1.7.4 pinned, `tlaup tlc Spec` prints the warning on stderr and still starts Java; with a rolling build pinned there is no warning and the property in the logged command names both that class and a project's `TLCOverrides`.
- M20 (inventory row M20): with two registered modules, each with its own override class, and a rolling build pinned, the logged command has one `-Dtlc2.overrides.TLCOverrides` property naming both classes, joined with `os.pathsep`, in `Registry.list()`'s order.
- R8: `tlaup tlc Spec -- -workers 4 -deadlock` logs a Java command ending `-workers 4 -deadlock <spec>` with one `-workers` (the roadmap's exit criterion); `--workers auto` logs `-workers auto`; with nothing given the command has `-workers auto` from the setting.
- J1: `TLAUP_JAVA_OPTS='-Xmx2g -Dx="a b"'` with `--java-opt=-Xss8m` logs the default options first, then `-Xmx2g`, `-Dx=a b` as one argument, then `-Xss8m`; `--java-opt -Xss8m` without `=` gives the same command; with `JAVA_OPTS=-Xmx1g` set, the command does not contain it.
- J2 (handed over by [20](20-java-location.md); the inventory's row J2 is J3's warning below): `JAVA_HOME is a JDK of version ...` is used although another `java` is on `PATH` (`java ran from JAVA_HOME`); `JAVA_HOME is an empty folder` gives one `warning:` line and `java ran from PATH`.
- J3 (handed over by 20): on `tlaup tlc Spec` the fake is started twice, once with `-version` and once as `tlc2.TLC`, and never with `tlc2.TLC -version`; `java answers its version check with "<text that is not a version>" on stderr and exit code 0` gives a warning and the run goes on (inventory row J2). Inventory row R2 (the version is checked before every run) is the first half: the `-version` start comes before the `tlc2.TLC` start on every run.
- F4 (handed over by [44](44-config-commands.md)): with `the config file contains:` a wrong type (`tlc:` / `refresh_interval: fast`), `tlaup tlc Spec` exits 3, stderr names the key `tlc.refresh_interval` and holds no `Traceback`, and `java was not started`.

`tests/features/tlc_errors.feature`. Each error scenario asserts the code, `stdout is empty` and `stderr contains "error:" 1 times`.

- R11, one scenario per row:
  - step 0: `--workers 2 -- -workers 4`, `--coverage -- -coverage 1` and `--cfg a -- -config b` exit 2; `--workers 0`, `--workers x` and `--workers +3` exit 2; an unbalanced quote in `TLAUP_JAVA_OPTS` exits 2 and names the variable;
  - spec: a missing spec exits 4 and stderr holds a path that was tried; `tlaup tlc .` exits 2; `tlaup tlc Spec.cfg` exits 4; a folder alone exits 2;
  - cfg: `--cfg` not found exits 4 with the paths tried; with no `--cfg` and no `Spec.cfg`, TLC is started (the code is the replayed case's);
  - build: nothing installed exits 3 (`CannotAsk`, since in-process nothing can be asked); builds installed and none pinned exits 3 and the hint names `tlaup tool pin`; a pin that names a build that is gone (`a file "{tools}/pin" containing:` an id with no folder) exits 3 and the hint names a command;
  - Java (inventory row J3): `java is not installed`, `java is not executable` (code 3, the same error), `java is version "1.8.0_202"`, and `java answers its version check with "Unable to locate a Java Runtime." on stderr and exit code 1` (the macOS stub), each exit 3. The check that timed out has no scenario: R11 now says so, since its timeout is ten seconds of real clock, which [01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 5 allows for one test only; the unit test of `ask_version` with a timeout of half a second ([20](20-java-location.md), [13 J3](../design/13-modules-and-java.md#j3-one-java-start)) stands in for the row (finding C4, settled).
  - For the spec, cfg and build rows: `java was not started`. For the Java rows: `java did not run "tlc2.TLC"`.
- R11, the order: nothing installed and a missing spec exits 4 and `0 requests were sent to GitHub`; nothing installed and conflicting `-workers` exits 2 and nothing was asked.
- R11, an outline that runs the spec, cfg, pinned-build and Java rows for the parsed path and for `--show-command` (inventory row R12: `--show-command` and a run check the spec and a named `--cfg` first, with one message).
- T5 and X1 rule 7: a mistyped `--coverge` and a missing `SPEC` exit 2 with Typer's own usage text on stderr, not an `error:` line, and start nothing.
- C1: `tlaup tlc --cleanup` and `tlaup tlc --version` exit 2, which is all that is left of them.

`tests/features/tlc_show_command.feature` (R9; inventory row R11):

- The output is one line on stdout; it holds no `-javaagent`; it holds the three encoding options, `-fp` and `-seed`; `the java command matches the expected file` for one fixed set of arguments given with `-- -fp 3 -seed 7 -metadir {work}/m`, so that nothing in it is random.
- `the cache holds no run folders` and `the cache holds no lock files`; `java did not run "tlc2.TLC"` (the fake is started once, for its version).
- With `--raw` the line has no `-tool`; with `--coverage`, `-coverage 1` stands before the spec.
- With no build pinned it exits 3 with one `error:` line and nothing is asked, also with `--auto-install rolling`.

`tests/features/first_run.feature` (V9), in-process, where the streams are not terminals and nothing is ever asked:

- `TLAUP_AUTO_INSTALL=rolling tlaup tlc Spec`, with `GitHub answers from "releases"`: the build is installed and pinned, and the fake `java` is started for the original command.
- `--auto-install nightly` exits 2.
- Nothing installed and a spec that does not exist exits 4 with no request to GitHub and nothing installed, also with `TLAUP_AUTO_INSTALL` set.
- `tlc Spec --show-command` with nothing installed exits 3 with no request, also with `TLAUP_AUTO_INSTALL` set.
- Nothing installed and no variable exits 3 (`CannotAsk`).
- Builds installed and none pinned exits 3 with the names to pin, and no request.

`tests/unit/cmd/test_tlc_command.py`, plain pytest:

- R9 and G1, two in-process runs in one test (T5, "Two results compared with each other"): the line `--show-command` prints equals the command the fake `java` logged for a real run with the same arguments, apart from the run id and the lifeline agent. The two runs draw their own `-fp` and `-seed`, which the design's sentence does not mention: give both after `--`, or replace the two values as the run id is replaced.
- P3: `print_run_notes` on a `Ui` built on in-memory streams, with hand-built outcomes: exit 0 with the verdict `errors` gives the first warning, exit 12 with `no-error` the second, exit 0 with `no-error-bounded` none; stdout stays empty in each. (P3 lists this as a unit test; packages 09 and 13 hand it here.)

### B. Real-process scenarios

`tests/features/tlc_signals.feature` (R2, G3; inventory row R14). tlaup is started with `sys.executable -m tlaup`; the signal goes to the tlaup process alone, so each scenario proves forwarding.

- Six scenarios: SIGTERM (143), one SIGINT (130), two SIGINTs (`send SIGINT twice` with `java ignores SIGTERM` (corrected while building 39b: tlaup passes a first signal on as SIGTERM, so a fake that ignored SIGINT would die on it); 130, no `Traceback`), each in parsed mode and with `--raw`. In each, `the java process has exited`. In parsed mode stdout holds what was printed before the signal and the result line says the run was interrupted.
- R6: the checkpoint-writing fake under `--keep`, interrupted with SIGINT, in parsed and in raw mode: one run folder is kept and the note is on stderr.
- D60, on a pseudo-terminal, Linux and macOS (`in a terminal`; skipped with the reason where there is no pty): a Ctrl-C typed at the terminal during a parsed run reaches tlaup and not the fake, whose process group differs from tlaup's, and the run ends with 130; Ctrl-\ is logged as SIGQUIT by the fake and changes nothing else; with `--raw` the fake logs the SIGINT itself, in tlaup's group.
- R6 and G3, the checkpoint deferral as real processes (question Q10, settled), with a fake that replays 2195 at line `n`, begins its checkpoint after it and commits it before it writes 2196 at line `m` (`java begins a checkpoint after line <n> and commits it before line <m>`, which also gives the fake a release file, [01 T4](../design/01-testing.md#t4-fakes-at-the-edges)), and `java hangs after line <m>`, after 2196 and never between the two (T4; finding E1). The When step is T5's, as [18](18-feature-harness.md) builds it: it sends the signal once the fake has logged its `checkpoint` line, waits until tlaup has shown the waiting line, and only then gives the release, so the fake commits and prints 2196 only after tlaup has shown that it holds the signal. `I start "tlaup tlc Spec --keep" and send SIGINT once java has begun its checkpoint`: stderr holds the waiting line (`waiting for TLC to finish writing its checkpoint; press Ctrl-C again to stop now`), the fake gets its SIGTERM only after 2196, which ends its hang (`java received SIGTERM`, and no SIGINT), the exit code is 130 and one run folder is kept with a complete checkpoint. The same ending `, and again once stderr contains "waiting for TLC"`: the step gives no release, the second SIGINT kills at once while the fake waits, before 2196, and nothing is kept (the `.tmp` files were never renamed).
- D60's part during a checkpoint, on a pseudo-terminal: `I start "tlaup tlc Spec --keep" in a terminal 100 by 30 and press Ctrl-C once java has begun its checkpoint`: the fake logs no SIGINT, its process group differs from tlaup's, the terminal shows the waiting line (at 100 columns it is shown whole, as T5's terminal form needs), the step then gives the release, and when the fake commits and prints 2196 it gets SIGTERM; the run ends with 130 and a complete checkpoint. The fake's lines are as in the scenario above, its hang after line `m`.

`tests/features/tlc_raw.feature` (X2, G3, T5; inventory row R10):

- `java writes "to-out" to stdout and "to-err" to stderr`: `stdout is exactly "to-out"`, `stderr is exactly "to-err"`, the exit code is the fake's, `java was started without "-tool"`.
- A plain capture (`tlc/<build>/plain/`) replayed with exit code 12: stdout equals the capture byte for byte and the code is 12.
- R6: a raw run that ends normally leaves no run folder and no lock file.
- R11: the raw path for the spec row (exit 4) and the Java row (exit 3), which is enough to show it goes through the same preflight.
- R1 and D58, Linux and macOS: `tlaup tlc --raw Spec` `whose reader closes after 1 line`, with a fake that prints a line and then a line a second for a minute: the exit code is 141, and the fake got SIGTERM.

Real-process scenarios in `tlc_errors.feature` and `tlc_run.feature`:

- R1, X1 rule 8: `java prints 100000 lines` and `java hangs after line 100000`; `tlaup tlc Spec` whose reader closes after 1 line: 141, `stderr does not contain "Traceback"`, `the java process has exited`. The count is ten times the launcher's queue bound on purpose.
- G3 (review finding TU2): the same reader with a fake that replays its banner and then writes nothing on stdout for a minute: 141, and the fake got SIGTERM.
- R3: with `the environment variable "PYTHONIOENCODING" is "ascii"`, a replayed trace that holds `é` exits with the case's code and no `Traceback`.
- V9 and D45, on a pty: nothing installed and a spec that does not exist exits 4 and `the terminal does not contain` the question.

"Within a few seconds" in the design's wording is the timeout of the step that waits for the process; no scenario measures time.

### Steps

The scenarios use T5's table as it stands, with `{kept}`, `{runs}`, `{tools}`, `{work}`, and the checkpoint and version-answer steps [18](18-feature-harness.md) built. Three assertions above have no step in the table: that the fake `java` received a given signal, or none; which process group the fake ran in; and pressing Ctrl-\. The fake's log already records all three ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges): the `signal` lines and the process group id of the `start` line). T5 allows a new step with a reason in the pull request; add `java received <signal>`, `java received no signal`, `java ran in its own process group` and `in tlaup's process group`, and a `press Ctrl-\` form of the terminal step, and give that reason.

### Old tests

None: the old suite went in [03](03-test-foundation.md) (D62). No stateful test applies to this package; [21](21-java-launcher.md) and [35](35-run-folders.md) removed their `pending` markers.

Coverage: the roadmap's target for the command module is above 80 percent; with the reporters moved out it is small, and the features should cover all of it. The real-process scenarios are counted through coverage's subprocess patch ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)).

T12 rule 6: the pull request shows red runs for the defects it fixes that have a scenario here: `Foo.v2` (R5), the decoy `out.cfg` (R4), `--show-command` creating a run folder (R9), SIGTERM leaving the fake alive (R2). A scenario file run against the old command before the switch commit is enough.

## Changelog

This is the package in which most of milestone 1 becomes visible. Each entry below is word for word from its section. Write every one that is not already under `## [Unreleased]`; the packages that built the pieces deferred them here.

Breaking:

- X2: "Output streams are now consistent: results go to stdout; progress, the live display and tlaup's own messages go to stderr. The verdict line moved from stderr to stdout. `--raw` no longer merges TLC's stderr into stdout."
- R4: "TLC now runs in the folder where `tlaup` was started (was the project root, or the spec's folder). TLA+ modules in the project root but outside `modules/` are no longer found; move them beside the spec or into `modules/`. A relative `-config` given after `--` is read relative to the spec's folder, as TLC does with an absolute spec path; use `--cfg` instead. Every other relative path after `--` (`-dump`, `-userFile`, `-dumpTrace` and the rest) is read from the folder you run tlaup in. `--cfg NAME` looks only for a file ending in `.cfg`."
- R8: "TLC now runs with `-workers auto` by default (was TLC's default of one worker). Set `tlc.workers: 1` or pass `--workers 1` for the old behaviour."
- J1: "`JAVA_OPTS` is no longer read. Use `TLAUP_JAVA_OPTS` or `--java-opt`; both add to the configured options instead of replacing them."

Added:

- R8: "Arguments after `--` are passed to TLC: `tlaup tlc Spec -- -deadlock -simulate num=10`."
- R8: "`--workers N|auto`."
- J1: "`--java-opt`."
- R6: "tlaup passes `-fp` and `-seed` to TLC when you do not, and repeats them when you resume, so a resumed run warns less and counts correctly."
- R7: "tlaup warns before a run when a registered Java override class will not be loaded by the pinned TLC build. On v1.7.4 only a class named `tlc2.overrides.TLCOverrides` is loaded." (Already there if [34](34-override-check.md) wrote it.)
- R3: "A hint when a spec or cfg name has non-ASCII characters and the locale is not UTF-8, which TLC cannot open."
- V9: "With no tools installed, `tlaup tlc` (and `sany`, `pcal`, `repl`) asks whether to install the stable release or the rolling build, installs it and carries on. `--auto-install stable|rolling` or `TLAUP_AUTO_INSTALL` answers the question for scripts. The spec is checked first, and `--show-command` never asks or installs."

Changed:

- O3: "The output of `tlaup tlc` is reorganised: a header naming the build and Java; the spec's own output; each error with its message and full trace, changed variables marked; SANY and parse errors as `path:line:col: error: message` (was a `file://` link), still followed by the lines of the spec around the error, now with `^` under the columns; a final result line with the meaning of TLC's exit code. Results are on stdout, progress on stderr."
- P2: "The TLC output parser is now the import package `tlaup_parse`, shipped with tlaup. `tlaup.tlc.parser`, `tlaup.tlc.models`, `tlaup.tlc.values`, `tlaup.tlc.codes` and `tlaup.tlc.sany` are gone."
- R1: "When the program reading tlaup's output goes away (`tlaup tlc --raw Spec | head`), TLC is stopped instead of running on unseen; not on Windows for `--raw`."
- R6: "Each run has its own run folder, removed when the run ends, however it ends. `tlaup tlc --keep` (or the setting `tlc.keep`) keeps it when the run is interrupted or crashes and TLC has written a complete checkpoint; the size and the command to resume are printed, every `tlaup tlc` reminds you of kept folders, and `tlaup cache clean <run-id>` or `--all` removes them. tlaup never removes a kept folder on its own."
- R6: "A first Ctrl-C while TLC is writing a checkpoint waits for the checkpoint to finish, also one typed at the terminal (Linux and macOS, not with `--raw`); a second stops at once."
- R6: "On rolling builds tlaup passes `-noGenerateSpecTE`, so TLC no longer writes `_TTrace_` files next to the spec. Pass `-generateSpecTE` after `--` to get them."
- G3: "Ctrl-C exits with 130."
- J2: "`JAVA_HOME` is used to find `java` and `javac` when it is set; `PATH` is the fallback."
- J3: "A run starts Java once instead of three times; the Java version check is remembered until the Java installation changes."

Fixed:

- R1: "Errors while running TLC were all reported as \"'java' not found\". Each is now reported as what it is."
- R4: "`--cfg` pointing at a file outside the project could make TLC read a different file with the same name."
- R5: "A spec name containing a dot (`Foo.v2`) was looked up as `Foo.tla`; `tlaup tlc .` failed with a traceback; an existing file that is not a spec (such as `Spec.cfg`) was passed to TLC."
- R6: "Running a spec could delete the run data of another spec whose name starts the same way, or of a run in progress; `tlaup module add` and `remove` deleted all run data."
- R7: "On rolling builds an override class named `tlc2.overrides.TLCOverrides` inside a jar on the classpath stopped loading when another override module was registered."
- R9: "`--show-command` printed a command without `-tool` and with `-coverage 1` in the wrong place, and created (and could delete) run data. It now prints exactly what would run and creates nothing in the run cache."
- R11: "Missing Java, a missing jar, or a missing spec could print 'Starting TLC' and then a traceback. Every `tlaup tlc` path now checks the spec, the cfg, the tools and Java first and reports the first problem in one line with the command to run next."
- G3: "Stopping `tlaup tlc` with SIGTERM (for example a CI timeout) now stops TLC too; it used to keep running."
- G3: "A second Ctrl-C no longer loses the summary."
- G3: "Output that is not valid UTF-8 no longer crashes tlaup."
- G3: "If tlaup is killed, the Java tool it started stops within about two seconds."
- G3: "TLC, SANY, PlusCal and the REPL now always write UTF-8; under a C locale non-ASCII characters were printed as `?`, and with Java 11 and v1.7.4 the PlusCal translator wrote them as `?` into the spec."
- J3: "A Java that did not answer was reported as 'not installed'."
- P4: "Errors with a TLC message code tlaup did not know (for example a false POSTCONDITION, code 2404) were not shown at all. Every message TLC marks as an error is now shown, and output tlaup does not recognise is printed as TLC wrote it."
- P5: "Counterexample traces were not shown: real TLC output parsed to zero states. Traces now show every state, the action and its location, the loop-back state of a liveness counterexample, and stuttering."
- P7: "Function values such as `(a :> 1 @@ b :> 2)` were shown as their first key; values TLC wraps over several lines were shown as one raw string."
- P8: "A SANY error was reported twice, and TLC messages printed after it were shown as part of it."
- P10: "The message of a violated invariant or property was hidden when a trace was shown."
- P11: "On a terminal, TLC output containing square brackets (every TLA+ record) was printed as an empty line or made tlaup fail."

Removed:

- J3: "`tlaup tlc --version`; use `tlaup tool current`."

Notes on the list. The design's duplicate entries are gone (index "Clerical", settled): a killed tlaup is G3's Fixed entry only, the Ctrl-C that waits for a checkpoint is R6's Changed entry only, and the removal of `tlc --cleanup` is in C1's Breaking line, which [45](45-cache-commands.md) writes with `tlaup cache clean`. R10's Breaking entry was written by [32](32-spec-resolution.md). X1's Breaking entry on exit codes belongs to [48](48-command-tree.md) (finding G7). The entry for the live view (O4), `--plain` and `--refresh-interval` (O5) is 40's. The P2 entry names `tlaup.tlc.models` as gone; the file itself goes one package later, with the layout code that still imports it (see Files), as P2 now says, and nothing is released in between (D6). The R7 Changed entry about listing loaded overrides was dropped from the design (finding C1); nothing in the first wave prints that list.

## Context for the worker

**From 37** (noted at its merge, 2026-11-25). The checkpoint mark comes before `reporter.handle`, so when the reporter sees `CheckpointWritten` the held signal may already be on its way: a real-process deferral scenario must not assert that nothing was signalled yet at that moment; prove the deferral by the one waiting line and the kept, complete checkpoint, as 37's unit test does.

**From 35b** (noted at its merge, 2026-11-25). The kept note, the reminder and the resume command come from `tlaup/tlc/rundirs.py` (`kept_note`, `reminder`, `resume_command`); `Kept` has a required `ended` field.

**State of `main` when this starts.** Everything new exists and is tested from below: `tlaup_parse`, the launcher, the store and the `tool` commands, the module build and the `module` commands, `tlc/invocation.py`, `tlc/command.py`, `tlc/overrides.py`, `tlc/rundirs.py`, the run functions, the reporter interface and the plain terminal reporter. `tlaup tlc` is the last command on the old code: `cmd/tlc.py` calls the old `tlc/runner.py`, which uses the old parser, `run_cache.py`, `compiler.py` (edited by [04](04-delete-dead-code.md) and [29](29-tool-commands.md) so that it finds the pinned jar in the new store), `java/inspector.py` and the old formatter. Check what really imports what before deleting: `uv run mypy` and `ruff` name every dangling import.

**What `main` looks like after this package, before 40 to 48.** Nothing is released in between (D6), and each of these is intended:

- Output is plain on a terminal too. The footer and table rows of release 0.8.x are gone and the full-screen layout is not there yet.
- `--refresh-interval` is not declared. Today it is declared and never read; declaring it again before it has an effect would rebuild the defect O5 removes. 40 adds it with its range check, and adds `--plain`. Neither is needed here: with one mode there is nothing for `--plain` to choose.
- `tlc --cleanup` is gone and `tlaup cache clean` does not exist until [45](45-cache-commands.md). The sweep at every run does the cleaning meanwhile.
- `check-java`, `fetch-cache` and the old `config` commands may still be the old ones; they do not touch what this package deletes.

**Decisions this rests on.**

- D45: spec, cfg, build, Java; `--show-command` never prompts or installs.
- D29 and D30: tlaup never exits 1 itself, the tool's code passes through, signals give 130, 143, 129, a closed pipe 141; results on stdout, everything about getting there on stderr.
- D34: TLC runs where tlaup was started.
- D53: keeping is asked for with `--keep`; there is no `--no-keep`.
- D51: the printed command has no lifeline agent, since a pasted command would carry the process id of a tlaup that has exited and its JVM would stop at once. This is a departure from the roadmap's "the exact command", listed in the design README.
- D52 and D60: the checkpoint deferral and the JVM's own process group in a parsed run, which the signal scenarios show from outside.
- D14: no alias for `--cleanup`, `--version` or anything else removed.
- D9: nothing TLC printed is lost; the reporter's `close` runs before the application prints an `error:` line.

**The command stays thin.** It parses options, builds the request, calls the five functions of the sketch, and exits. It does not enter `run_folder` (the run functions do, each for itself; entering it here as well would take the lock twice), does not parse, does not decide the exit code, and prints only the preflight's warnings and `print_run_notes`. Nothing is printed before the preflight returns; the reporter is created after it. Imports other than `typer`, `tlaup.errors` and `tlaup.context` go inside the function ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)); `import tlaup.cli` must not load `rich.live`, `requests` or the settings schema.

**Typer facts the design tried** (0.29.1, and every version from 0.22.0 to 0.29.2 in research 23): everything after `--` reaches the variadic argument; an unknown option before `--` is an error; a word after the spec that does not start with a dash also lands in the list without `--`. `--java-opt=-Xmx8g` and `--java-opt -Xmx8g` both work. A root option such as `--debug` goes before the command.

**The exit path.** `raise typer.Exit(outcome.exit_code)`; the root group lets a `typer.Exit` through unchanged ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)). An exception from a run function already carries the kept-folder note as notes (`add_note`), and the handler prints them after the `error:` line, or alone for a closed pipe. So `print_run_notes` handles only a run that returned.

**What the outcome carries for the note.** The first note line holds the folder's size, why it was kept and when the checkpoint was written. `RunOutcome.kept` carries rundirs' whole `Kept` ([37](37-run-tlc.md)), and `kept_note` ([35](35-run-folders.md)) makes the two lines; `print_run_notes` prints `kept_note(outcome.kept)`, the same text the frame puts on an exception. Do not rebuild the lines here from `run.json`.

**The checkpoint deferral from outside** (question Q10, settled). A signal has to land after tlaup has read message 2195 and before 2196. T5's step `once java has begun its checkpoint` waits for the fake's `checkpoint` log line, which it writes once the 2195 line is flushed and the `.tmp` files exist, and the fake hangs there until it commits and prints 2196 ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)). The window between the fake's marker and tlaup's read of the line is small, and T5 names it as a risk with its remedy (the fake waits for its stdout pipe to be empty before it logs the marker); if a scenario turns out flaky, that is the fix, in 03's fake, never a sleep or a product seam. The waiting line is on stderr in plain mode, at once ([38](38-terminal-reporter.md), `notice`), which is what `once stderr contains` waits for.

**Traps.**

- The in-process step refuses a command that reaches `run_passthrough` and a scenario that sets a `PYTHON*` or locale variable (T12 rule 10). A `--raw` scenario that fails before Java starts (a missing spec) has no such log line; the design still asks for the raw rows of R11 as real processes.
- `java was not started` counts the version check too. The fake is a script, so its version is never remembered and every run starts it twice; use `java did not run "tlc2.TLC"` where the version check is allowed.
- A real-process scenario cannot be served recordings. Anything that downloads is in-process; a real process that asks GitHub by mistake is refused at the closed port the isolation fixture sets.
- The pipe scenarios make the pipe themselves and close its read end; no shell and no `head`. With short output `| head -1` is a race.
- A real-process child must start with SIGINT at its default disposition; the helper of 18 does that. The launcher itself never uses `preexec_fn`.
- Run ids are random. A scenario names a kept folder only through `{kept}`, and an expected file never holds a run id.
- `-fp` and `-seed` are random too; an expected command file gives both after `--`.
- Expected files show what a user sees. Paths in replayed output come from the fake's `replace` field, never from normalising in the helper (T8).
- The `tlc` function loses its `# noqa: PLR0912, PLR0913, PLR0915, PLR0917` only in part: a command with ten options still has many parameters. Keep the suppression that is still true and drop the rest.

**Known gaps the design postpones.** The per-run `java.io.tmpdir` for v1.7.4. A JSON reporter and `--json`. `--quiet`, `--verbose`, `--color`. Whether the exit code should follow the verdict (milestone 4). Forwarding SIGTSTP. None is built here.

## Done when

- The six feature files and `tests/unit/cmd/test_tlc_command.py` pass on Linux and macOS in CI, the pty scenarios included.
- The old modules listed under Files are gone; nothing under `src/` imports `tlaup.tlc.parser`, `codes`, `values`, `sany`, `run_cache` or `compiler`; what stays for 40 is exactly the list above; `tlc/runner.py` is the new runner.
- `uv run poe lint` and `uv run poe test` pass; `uv run poe test-clean` leaves the home folder empty. There is no coverage threshold until [59](59-closing.md) ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)).
- Every changelog entry of the Changelog section is under `## [Unreleased]`, once.
- `docs/contributing/development.md` names no deleted file.
- The pull request shows the red runs of T12 rule 6, gives the reason for each added step, names what it left for 40, and names the inventory rows it owns (R1, R2, R10, R11, R12, R14, M20, J2, J3) and the parts it writes of R7 and C6.
- `versioning/paths.py` and `cache_dir()` are gone, and `tests/unit/test_context.py` no longer asserts `cache_dir()`.
- A reviewer can read every expected file under `tests/features/expected/` for this package as the output a user gets.

## Out of scope

- The live layout, `--plain`, `--refresh-interval`, `tlc_live.feature`, the rule in `make_reporter`, deleting the old layout code and `tlc/models.py`: [40](40-live-display.md).
- `sany`, `pcal`, `repl` and `ENTRY_POINTS`: [41](41-sany-command.md) to [43](43-repl-command.md).
- `cache dir`, `cache list`, `cache clean` and `cache.feature`: [45](45-cache-commands.md). `doctor`, and deleting `java/inspector.py`: [46](46-doctor.md).
- The tree test, the scenarios for the other removed names, explicit registration as a whole: [48](48-command-tree.md).
- Help wording beyond the lines named above, and the generated CLI reference: [50](50-help-and-messages.md), [51](51-cli-reference.md).
- Integration tests with a real JVM, including the six signal scenarios, R4's link rows, `--workers auto` under `taskset`, and the kept-and-resumed run: [52](52-integration-tests.md).
- The two exact-moment signal tests on `run_tlc`, the frame tests, the reporter's expected files: [37](37-run-tlc.md), [38](38-terminal-reporter.md).

## Risks

- From the cut: this is the first time the pieces of about twenty packages run as one command. A fault found here is fixed in the module that owns it, in this pull request if small, and the pull request says so.
- From the cut: the package is large (six feature files, about ninety scenarios, a long deletion of code). It is split along the line between parts A and B of the Tests section (below); with the old tests gone in 03, 39a deletes code only.
- From G3 and R2: the signal scenarios were not run on macOS or with a real terminal by the research; the macOS CI job runs them here for the first time. D60 was worked in after the last review.
- From R1: the 141 path rests on how Typer and Rich handle a closed pipe; the newest-dependencies job guards later versions.
- From R9: a user who pastes the printed command twice at once shares one `-metadir` between two runs.
- From R11: a user with nothing installed and a mistyped spec meets the install prompt on the second try.
- From R8: `-workers auto` by default changes the order of `Print` output and can change which counterexample is found first.
- From T5: real-process scenarios take a few hundred milliseconds each; this package adds a few dozen.
- From the cut: between this package and 40 the old layout code and `tlc/models.py` lie unused and untested under `src/tlaup/tlc/`, because O2 puts their removal with O4. Nothing is released in between (D6).

## Pull requests (decided by stage 4)

This package is delivered as two pull requests, along the line between parts A and B of its Tests section; the index lists them as 39a and 39b.

- **39a**: the new `cmd/tlc.py`, `make_reporter`, the deletions, the changelog, and part A of the tests (`tlc_run`, `tlc_errors` in-process, `tlc_show_command`, `first_run`, the plain pytest tests). It does the whole switch.
- **39b**: part B (`tlc_signals` with the checkpoint deferral scenarios, `tlc_raw`, the real-pipe, `PYTHONIOENCODING` and pseudo-terminal scenarios) and the steps they add. It only adds tests. Depends on 39a.

A package that names 39 as a dependency waits for 39b.
