# 31. The `module` commands: switch to the new module build

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup module add|list|remove|dir` (D47) is a thin command group under `src/tlaup/cmd/module/` over the domain code of [30](30-module-build.md), with checked names, a build that never destroys the working one, `javac` found through `JAVA_HOME` and checked, and the exit codes of [02 X1](../design/02-cross-cutting.md#x1-exit-codes). The old `modules` group, `modules path` and the old module folder `<cache>/modules` are gone (their old tests went in 03b, decision D62); `modules.feature` states the behaviour with the fake `javac`; the changelog says what a user sees. The old `tlaup tlc` still type-checks: its classpath resolver is given the registry's folders.

## Covers

- Roadmap items, [milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust):
  - Line 220: "Reject module names containing path separators or `..`, absolute paths, `.` and an empty name in `modules remove` and `modules add`; `modules remove ../tools` deletes the tools folder today." Closed here: the commands, the scenarios and the changelog. The rule itself was [30](30-module-build.md).
  - Line 221: "`modules add` builds in a temporary folder and swaps it in only when compilation succeeds, so a `javac` error no longer destroys the working build; it says when it replaced a module of the same name (decision D23)." Closed here; the domain function was 30.
  - Line 206 (recorded without a solution): "The module build strips `//` comments with a regex that corrupts string literals; `javac` runs with no `-encoding` and no timeout." Closed here: the scenarios and the changelog. The work was 30 and, for the version check, [20](20-java-location.md).
  - Line 259: "Use `JAVA_HOME` when set, falling back to `PATH`, for both `java` and `javac`.", in part: `module add` finds `javac` through `require_javac`. The function was 20; the `tlc` side and the one changelog line are [39](39-tlc-command.md).
- [Milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 334: "Review the layout of every command so it follows the most common CLI patterns ...", in part: the `module` group; "the different meanings of `tools dir`, `tools path` and `modules path`" for this group. The tree test and the scenarios for removed names are [48](48-command-tree.md); the other groups 29, 39, 44, 45, 46, 47.
- [Milestone 5](../roadmap.md#milestone-5-structure), line 495: "Move the module build pipeline out of `cmd/modules/add.py` into a modules domain package ...; the classpath resolver asks it for folders instead of walking the cache." Closed here: the old command and the resolver's own walk go.
- Design sections:
  - [23 C1](../design/23-command-layout.md#c1-command-tree): the `module` rows of the tree (`add PATH`, `list`, `remove NAME`, `dir`); the rows "`dir` always prints a folder" (for `module dir`), "`modules path` is removed; `module dir` is new", "`tools` becomes `tool` and `modules` becomes `module`" (D47) for this group, "`NAME` of `module remove`" as a required argument, "`uninstall` keeps its name; `remove` stays for modules"; explicit registration for this group. Not here: the tree test, the removed names' "exit 2" scenarios, the root options (48); the rename's changelog line, which [29](29-tool-commands.md) wrote for both groups.
  - [13 M1](../design/13-modules-and-java.md#m1-module-names): the `modules.feature` scenarios and the changelog.
  - [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder): the command ("Added" or "Replaced", then the warnings; no prompt; no run folders cleared), binding `get_build` and `get_javac`, the `modules.feature` scenarios, the changelog. "`ClasspathResolver` asks the registry for the module folders": the old walk goes here.
  - [13 M3](../design/13-modules-and-java.md#m3-module-build-details): the feature scenarios (the logged `javac` command, `javac 1.8.0_202` gives 3, `javac 25.0.5` compiles) and the changelog.
  - [14 F2](../design/14-config-and-cli.md#f2-folder-overrides): `module dir` prints the folder in effect.
  - [14 F8](../design/14-config-and-cli.md#f8-wording), one row: module build times shown in UTC, its `modules.feature` check and its changelog line, because a user first sees it here. The rest of F8 is [50](50-help-and-messages.md).
  - The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md): rows M1, M2, M4, M6, M9, M10, M13, M14 and M16, whose owner this package is, each held by `modules.feature` as the table under Tests says, and M5's command form (the narrow compile classpath, D61; [30](30-module-build.md) owns the row) by the plain test there.

## Depends on

- [30](30-module-build.md): `validate_module_name`, `Registry`, `RegisteredModule`, `build_module`, `BuiltModule`; the `module_dirs` parameter of `ClasspathResolver`; whatever 30 added to the fake `javac` and the fake class files.
- [29](29-tool-commands.md): the new store in use (`tlaup tool install` writes it, so a user can have a pinned build that `module add` compiles against); the store steps of the features (`the build "<spec>" is installed and pinned`, `no build is installed`); `_shared.py`'s `open_store` and `open_remote`. Without 29 first, `module add` would compile against a store nobody can fill.
- [28](28-first-run.md): `ensure_tools(..., auto_install=None, may_install=False)`, which returns the pinned build or raises `NoToolsInstalled`, `NoPinnedBuild` or `PinnedBuildMissing` with their hints, asks nothing and installs nothing.
- [20](20-java-location.md): `require_javac` (with the `javac` pattern and the remembered answer), `JavaRuntime`.
- [19](19-layered-config.md): the setting `java.min_version`, from `ctx.settings`.
- [16](16-ui-messages.md), [17](17-error-handler.md): `Ui` (`note`, `warning`, `result`), the root group that maps `TlaupError` to its code and one `error:` line, and `get_context()`.
- [18](18-feature-harness.md): `tests/test_features.py`, the step modules (`javac is not installed` and `javac is version "<v>"` among them), the in-process runner, the placeholders `{modules}`, `{tools}`, `{work}`.
- [02](02-errors-and-paths.md), [03](03-test-foundation.md): the errors, `AppPaths`, the context; the isolation fixture and the fakes.

Changes from the draft (30, 17, 18): 29, 28, 20, 19 and 16 are added because the command uses them directly; 29 also because of the order of the switches (above). None changes the build order, since all are below 30 or already needed by it.

## Files

Creates:

- `src/tlaup/cmd/module/__init__.py`: the Typer group `module` with `no_args_is_help=True`, each command registered with `app.command(...)`, never by importing a module for its side effect ([23 C1](../design/23-command-layout.md#c1-command-tree), last row).
- `src/tlaup/cmd/module/add.py`, `list.py`, `remove.py`, `dir.py`.
- `tests/features/modules.feature` (the name in [01 T5](../design/01-testing.md#t5-feature-files-and-steps)'s layout).
- `tests/unit/cmd/test_module_command.py`: the plain pytest case named under Tests, for the `-d` and `-cp` facts the steps cannot express.
- In `tests/steps/`: the steps of the list under Tests that [18](18-feature-harness.md) did not write.
- Module sources for the scenarios, if [03](03-test-foundation.md) and [30](30-module-build.md) did not leave them: folders under `tests/fakes/` (for example `tests/fakes/module-src/Queue/`, `TlaOnly/`, `NoIndex/`) holding `modules/*.tla` and `modules/tlc2/overrides/*.java`, whose prepared class files the fake `javac` copies. `Queue` also holds a `lib/` jar and one source under a top-level `tlc2/overrides/sub/`, so that rows M2 and M4 of the inventory are seen on it.

Changes:

- `src/tlaup/cli.py`: the line that registers `modules` becomes the line that registers `module` from `tlaup.cmd.module`. One line; every switch package edits one, and [48](48-command-tree.md) rewrites the block.
- `src/tlaup/java/classpath.py`: `module_dirs` becomes required (keyword-only, `Sequence[Path]`, no `None`); the walk of `<cache>/modules` in `_resolve_paths` and `resolve`, and the import of `get_modules_dir`, are deleted; `ResolveMode.COMPILE` and its branch are deleted (the old `cmd/modules/add.py` was its last caller). `ResolveMode` keeps its one member and `resolve` its parameter, so no call line changes. If [33](33-tlc-invocation.md) is merged first, make the same three changes on its version of the file.
- `src/tlaup/tlc/runner.py`: the one `ClasspathResolver(...)` call in the old `build_tlc_command` gets `module_dirs=[m.path for m in Registry(AppPaths.from_env(os.environ).modules).list()]`, with its imports. Nothing else in the old runner changes. See "The old `tlaup tlc` after this package" under Context.
- `src/tlaup/versioning/paths.py`: delete `get_modules_dir`. What is left (`get_run_dir`, `get_tlc_run_dir`) is [39](39-tlc-command.md)'s.
- `tests/unit/java/test_classpath.py` ([30](30-module-build.md)'s new file): nothing, as long as its cases pass `module_dirs` and use `ResolveMode.RUNTIME`, as 30 writes them; a case that does not is given the folders. The old file of that name, and its `test_cached_modules_resolved` and `test_resolve_compile_order`, went in 03b.
- `README.md`: the section "Custom Java Modules (`tlaup modules`)" names `tlaup module add|list|remove|dir`.
- `CHANGELOG.md`: the entries under Changelog.

Deletes:

- `src/tlaup/cmd/modules/` (`__init__.py`, `add.py`, `list.py`, `remove.py`, `path.py`): the old group and `modules path` with it. Its old tests, `tests/unit/cmd/test_modules.py` and the old `tests/integration/` files that drove `modules add`, went in 03b (decision D62).
- `src/tlaup/tlc/compiler.py` only if [39](39-tlc-command.md) is already merged and nothing else imports it. It cannot be, since 39 depends on this package: after this package its callers are `cmd/tlc.py` and `tlc/runner.py`, and 39 deletes it with them.

Does not touch: `src/tlaup/cmd/tlc.py`. Its one `ClasspathResolver(...)` call was inside `_show_diagnostic_info`, which [04](04-delete-dead-code.md) deleted, and this package waits for 04 through 29, so after 04 `cmd/tlc.py` calls the resolver nowhere and needs no `module_dirs=` (findings F3 and G4 of the [second review](review-2026-11-24.md); finding B2 of the first review was right about today's code, which 04 answers). Nor `src/tlaup/tlc/run_cache.py` (its `clear_tlc_run_cache` loses the module commands as callers and keeps `tlc --cleanup` until 39), `src/tlaup/modules/` beyond what a fault found here needs (see Done when).

Files that packages of the same period also touch: `cli.py` (one registration line each for 29, 39, 44 to 47; 48 rewrites the block), `CHANGELOG.md`, `README.md` (29 and 39 change their own lines), `tests/steps/given.py` and `then.py` (29, 39, 44, 45 add their own functions), `src/tlaup/java/classpath.py` and `tests/unit/java/test_classpath.py` (30 before, 33 in either order; the edits are in different lines), `src/tlaup/tlc/runner.py` (19, 29 and 32 edited other lines before; 39 deletes it), `src/tlaup/versioning/paths.py` (29 before, 39 after), `src/tlaup/modules/build.py` ([34](34-override-check.md) adds its few lines in either order). Each conflict is a few lines.

## Interfaces

Provides, the command tree of the group ([23 C1](../design/23-command-layout.md#c1-command-tree)):

```
tlaup module add PATH       build PATH and register it under the folder's name; "Added module X" or "Replaced module X"
tlaup module list           the registered modules, with their build time in UTC
tlaup module remove NAME    NAME required; "Removed module X"
tlaup module dir            one line: the modules folder in effect, <cache>/module, whether or not it exists
```

Each command module imports only `typer`, `tlaup.errors` and `tlaup.context` at the top and everything else inside the function ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)). Each Typer function parses its arguments and calls one plain function that takes the registry (and for `add` the two bound functions), the `Ui` and the arguments, and returns or raises a `TlaupError`, as the `tool` commands of [29](29-tool-commands.md) do.

**`module add PATH`.**

```python
ctx = get_context()
registry = Registry(ctx.paths.modules)
built = build_module(
    Path(path), registry=registry,
    get_build=lambda: ensure_tools(store, remote, client, ctx.ui, auto_install=None, may_install=False),
    get_javac=lambda: require_javac(ctx.env, min_version=ctx.settings.java.min_version,
                                    cache_file=ctx.paths.java_cache),
    release=ctx.settings.java.min_version, now=lambda: datetime.now(timezone.utc))
ctx.ui.note(f"{'Replaced' if built.replaced else 'Added'} module {built.name}")
for text in built.warnings:
    ctx.ui.warning(text)
```

`get_build` is the same call [39](39-tlc-command.md) makes for `--show-command`: the pinned build or the error, never a question, an install or a request ("`module add` never prompts and never installs: its `get_build` is the store's pinned build", M2). `store`, `remote` and `client` are built as 29's commands build them, inside the lambda, so a module with no Java sources does not import `requests` or read the store at all. Both functions are called only when the module has Java sources (M2, step 3).

Errors a user can meet, all through the handler of 17 as one `error:` line and the code: a name the rule refuses, `InvalidName` (2) with the hint to rename the folder; `PATH` not a folder, `PathNotFound` (4); no build installed, `NoToolsInstalled` (3); builds and no pin, `NoPinnedBuild` (3); the pin names a missing build, `PinnedBuildMissing` (3); no `javac`, `JavacNotFound` (3); a `javac` older than `java.min_version`, `JavaTooOld` naming `javac` and its path (3); a compile error, `ModuleBuildError` (5) whose details (printed after the message) are the compiler's output and the classpath; the timeout, `ModuleBuildError` (5); the modules lock held too long, `StoreLocked` (5).

**`module list`.** On stdout, through `ui.result`, one row per registered module from `Registry.list()`, in its name order: its name and its build time written as `2026-11-15 10:00 UTC` (F8). With no module registered, stdout is empty, so a script reads no rows, stderr holds one note, `no modules are registered` (through `ui.note`; required, not optional), and the exit is 0 ([13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder); inventory row M14, owner this package). The column titles and any further column are the worker's; the help and wording pass of [50](50-help-and-messages.md) may change them.

**`module remove NAME`.** `registry.remove(NAME)`, then `ui.note("Removed module NAME")`. `InvalidName` (2) before the disk is touched; `ModuleNotFound` (4) with the hint `tlaup module list`; `FileOperationError` (5). It no longer clears run folders ([11 R6](../design/11-runner.md#r6-run-folders)).

**`module dir`.** `ui.result(str(ctx.paths.modules))`: one line on stdout, whether or not the folder exists, as `tool dir` and `config path` do ([14 F2](../design/14-config-and-cli.md#f2-folder-overrides)).

Consumes: `Registry`, `build_module`, `BuiltModule` (30); `ensure_tools` (28); the store, remote and client as built in 29; `require_javac` (20); `Ui`, `get_context`, the handler (16, 17); the errors and `AppPaths` (02).

## Tests that must pass

`tests/features/modules.feature`, every scenario **in-process** (`I run "..."`): none passes output through, needs a pipe, a signal or a terminal, or sets a variable the interpreter reads at start, so T12 rule 10 puts them all in-process. The fake `javac` is a real child process, which the in-process run sees through its log.

M1:

- Scenario outline: with the build `v1.7.4` installed and pinned, `tlaup module remove <name>` exits 2 for `../tool`, `../tools`, `..`, `.` and `a/b`, with one `error:` line, and `the file "{tools}/pin" exists` afterwards. `../tool` is the case that matters now: with D47 the store is `<cache>/tool`, the sibling of `<cache>/module`.
- `tlaup module add "my module"` (a folder made with `a file "my module/modules/M.tla" containing:`) exits 2 with an `error:` line and a `hint:` line, and the registered modules are none.
- `tlaup module add nosuch` exits 4. `tlaup module remove Nosuch` exits 4.

M2:

- First add: with `v1.7.4` installed and pinned and `a module source "Queue" from the fake sources`, `tlaup module add Queue` exits 0; `the registered modules are:` a table holding `Queue`; stderr contains `Added module Queue`; `javac was started with "-encoding"`, `"UTF-8"`, `"--release"`, `"11"`; `javac was started with` the source under `modules/tlc2/overrides/` and the one under `tlc2/overrides/sub/` (row M4); the files `{modules}/Queue/lib/<its jar>`, `{modules}/Queue/modules/<its .tla>` and `{modules}/Queue/tlc2/overrides/sub/<its .java>` exist (row M2). The remaining facts of M2's scenario (the folder after `-d` under `{modules}/.tmp/`, and the exact `-cp` value) are asserted in the plain test below, since the values hold a random name and a build id.
- A failing second add: after a first add, `javac fails with "syntax-error"`, a second `tlaup module add Queue` exits 5; stderr contains a line of the recording and `tla2tools.jar` (the classpath is shown); `the file "{modules}/Queue/classes/tlc2/overrides/QueueOverrides.class" exists`.
- A successful second add: stderr contains `Replaced module Queue`, and the registered modules are still one `Queue`.
- No `javac`: with a build pinned, `javac is not installed`, `module add Queue` exits 3, stderr contains `javac`, and nothing is registered.
- No tools jar: `no build is installed`, `module add Queue` exits 3 with one `error:` line and a `hint:` line, `javac` did not compile, and nothing is registered (row M10).
- A module of `.tla` files only: `no build is installed`, `javac is not installed`, `tlaup module add TlaOnly` exits 0 and registers it; `javac was not started`; `java was not started`.
- `tlaup module remove Queue` after an add: exits 0; the registered modules are none; `the file "{modules}/Queue" does not exist`.

M3:

- `javac is version "1.8.0_202"`, with a build pinned: `module add Queue` exits 3, stderr contains `javac`, and `javac` was started once (for `-version`, not to compile).
- `javac is version "25.0.5"`: `module add Queue` exits 0.
- A module whose Java has no override class (`NoIndex`): exits 0; `the file "{modules}/NoIndex/classes/META-INF/services/tlc2.overrides.ITLCOverrides" does not exist`; stderr has one `warning:` line.

C1 and F8:

- `tlaup module list` with `Queue` registered: exits 0; stdout contains `Queue` and `UTC`. With nothing registered: exits 0, stdout is empty, and stderr contains `no modules are registered` (row M14).
- `tlaup module dir`: exits 0 and stdout is exactly `{modules}`.
- `tlaup module` with nothing after it: help on stdout, exit 2 ([02 X1](../design/02-cross-cutting.md#x1-exit-codes), rule 7).

R7, only if [34](34-override-check.md) is merged when this package starts: with `v1.7.4` pinned, `module add Queue` (class `QueueOverrides`) exits 0 and stderr has one `warning:` line naming `QueueOverrides`. If 34 is later, 34 adds this scenario to this file.

**Steps.** The ones these scenarios use, from [01 T5](../design/01-testing.md#t5-feature-files-and-steps)'s list; write those [18](18-feature-harness.md) did not: `the module "<name>" is registered`; `a module source "<name>" from the fake sources` (copies the folder into `{work}`); `javac is not installed`; `javac fails with "<recording>"`; `the registered modules are:` (a table of names, read through `Registry.list()`); and the shared fake steps (`<tool> was started with`, `was not started`, `was started <n> time(s)`), if missing. `the module "<name>" is registered` is best done through `build_module` itself, with the fake `javac` and the scenario's build, so the files are what a real add leaves.

`javac is version "<v>"` is in T5's list now and is 18's (M3's scenarios use it). One need the vocabulary does not meet: an argument that starts with or contains a text. So `tests/unit/cmd/test_module_command.py`, plain pytest, runs `tlaup module add` in-process through the app and reads the fake `javac`'s log (one case, no new step):

- With `v1.7.4` installed and pinned, another module registered, `module_lib_path` set to a folder holding a jar (through `TLAUP_MODULE_LIB_PATH`), and a source `Queue` whose `lib/` holds `b.jar` and `a.jar`: the argument after `-d` is under `{modules}/.tmp/`, and the `-cp` value is exactly the pinned build's jar (`store.pinned().jar`), then the temporary copy's `lib/a.jar`, then `lib/b.jar`, joined with `os.pathsep`: nothing of the other module and nothing of `module_lib_path` (decision D61; M2's Tests; inventory row M5, its command form).

What the fake `javac` must do for these scenarios: answer `-version` with `javac <version>` on stdout ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges), built by 03); copy the prepared class files for each source; print a recording and exit 1; and, for 30's timeout test, wait. [30](30-module-build.md)'s Context lists the four; this package only uses what 30 or 03 built.

**Inventory rows** ([preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md)) this package owns, and the test that holds each (findings F1 and G1 of the [second review](review-2026-11-24.md)); the pull request names each:

| Row | Test |
| --- | --- |
| M1 (registered under the folder's name, replacing one of that name) | M2's "First add" and "A successful second add" |
| M2 (copies `lib/`, `modules/` and `tlc2/`) | "First add", the three files |
| M4 (compiles the sources under both override folders, recursively, against the jar and the module's `lib/*.jar`) | "First add", the two sources; the plain test below, the `-cp` value |
| M6 (no Java sources: no tools jar and no `javac` needed) | "A module of `.tla` files only" |
| M9 (a compile error shows the output, keeps the previous build) | "A failing second add" |
| M10 (Java sources and no jar or no `javac`: stops with what to do) | "No `javac`" and "No tools jar" |
| M13 (`module list` prints names and build times, by name) | C1 and F8's `module list` scenario |
| M14 (`module list` with nothing registered) | the same scenario's second half |
| M16 (`module remove` deletes; an unknown name is an error) | "`tlaup module remove Queue` after an add" and `module remove Nosuch` exits 4 |
| M5, a row changed on purpose by D61: its new behaviour's command form ([30](30-module-build.md) tests the unit form) | the plain test below |

Old tests: none left (03b). No stateful test applies.

## Changelog

The entries of M1, M2 and M3, word for word, and the C1 and F8 lines of this group:

- Fixed (M1): "`tlaup modules remove ../tools` deleted the tools folder. Module names are now checked." (the old command's spelling, as M1 now writes it)
- Breaking (M1): "A module name must start with a letter or digit and hold only letters, digits, `.`, `_` and `-`, at most 64 characters. `module add` refuses a folder whose name does not fit (for example one with a space); rename the folder."
- Breaking (M2): "Modules are stored in the cache's `module` folder (was `modules`), each with a `module.json`. Modules added by earlier versions are not found: run `tlaup module add` again. The old `modules` folder can be deleted."
- Breaking (M2, decision D61; finding B8): "`module add` compiles a module's Java sources against the TLA+ tools jar and the module's own `lib/*.jar` only. Other registered modules and the jars of `module_lib_path` are no longer on the compile classpath (they still take part in runs); a module that needs a jar to compile puts a copy in its own `lib/`."
- Fixed (M2): "A compile error in `tlaup module add` deleted the module's previous, working build."
- Changed (M2): "`module add` says when it replaced a module of the same name; it no longer copies a `test` folder."
- Fixed (M3): "`module add` could misread which classes provide overrides when a source file had `//` inside a string."
- Breaking (M3): "Override classes are compiled with `-encoding UTF-8 --release 11`. A module whose sources use language features or library classes newer than Java 11 no longer compiles; set `java.min_version` higher to raise the release. `javac` must be version 11 or newer."
- Removed (C1): "`tlaup modules path` is removed; `tlaup tlc SPEC --show-command` shows the classpath in use and `tlaup module dir` the folder."
- Changed (F8): "`module list` shows build times in UTC." (written here, where the user first sees it, and not by 50; finding B15)

Not here: C1's rename line ("`tlaup tools` and `tlaup modules` are now `tlaup tool` and `tlaup module`; every subcommand keeps its name."), which [29](29-tool-commands.md) wrote for both groups; J2's line, which [39](39-tlc-command.md) writes for `java` and `javac` together ([20](20-java-location.md)); R6's Fixed line, which names `module add` and `remove` deleting run data and is 39's; R7's Added line, which [34](34-override-check.md) or 39 writes; F7's help text and the rest of F8, which are [50](50-help-and-messages.md)'s. If 50 is cut to write the whole F8 Changed entry, it finds this line there.

## Context for the worker

**State of `main` when this starts.** 29 is merged: `tlaup tool` writes the new store (`<cache>/tool/`), and `tlc/compiler.py`'s `get_tlc_jar_path` reads the pinned jar from it. No old test is left (03b). 30 is merged: `tlaup/modules/` exists and `ClasspathResolver` takes `module_dirs`, with `None` meaning the old walk. The old `tlaup modules add|list|remove|path` (`cmd/modules/`) still copies into `<cache>/modules/<name>/` with a `metadata.json`, imports `tlc/compiler.py`, `tlc/run_cache.py`, `versioning/paths.get_modules_dir` and `java/classpath.ResolveMode.COMPILE`, and runs a bare `javac`. The old `tlaup tlc` (`cmd/tlc.py`, `tlc/runner.py`) builds its classpath with `ClasspathResolver(config, project_root=..., tool_jar=...)`, which walks `<cache>/modules`. [33](33-tlc-invocation.md) and [34](34-override-check.md) may or may not be merged.

**The old `tlaup tlc` after this package.** Nothing promises that the old `tlc` keeps working until [39](39-tlc-command.md) replaces it (decision D62; no CI job runs real TLC through it), but `module_dirs` becomes required, so its resolver calls need an argument for `main` to type-check. The registry's folders are the argument that costs nothing, and with them the old runner reads the new layout, because the new layout keeps the three subfolders the resolver reads:

| The old runner reads | Before this package | After it |
| --- | --- | --- |
| The registered modules | every folder under `<cache>/modules` | `Registry(AppPaths.from_env(os.environ).modules).list()`: the folders under `<cache>/module` with a valid name and a `module.json`; `.tmp/` and leftovers are not modules |
| Each module's classes, on the classpath before the tool jar | `<module>/classes` | the same subfolder |
| Each module's jars | `<module>/lib/*.jar` | the same |
| Each module's TLA+ modules, on the classpath and in `-DTLA-Library` | `<module>/modules` | the same |
| The override classes (`get_override_classes`) | `classes/META-INF/services/tlc2.overrides.ITLCOverrides` of each classpath folder | the same file, now written only when an override class exists (M3) |

So the edit is the one line in `tlc/runner.py` under Files (the call in `cmd/tlc.py` went with `_show_diagnostic_info` in 04): the resolver is given the registry's folders. `AppPaths.from_env(os.environ)` is used because the old code has no context to read, as 29 did in `compiler.py`; it is the same folder the context gives. The old `tlc` therefore runs modules added with `tlaup module add`, and never sees what an earlier release left in `<cache>/modules`, which is what M2's Breaking entry tells users. One difference the old runner shows, and accepts: a module with Java sources but no override class now has no service file, so the old runner passes no property for it where it used to pass the configured default class name. That is M3's fix. No other line of the old runner changes; in particular its `tlc --cleanup` and `get_tlc_version` stay for 39.

**What the old `tlc` keeps importing.** After this package `tlc/compiler.py` is imported by `cmd/tlc.py` and `tlc/runner.py` only, and `tlc/run_cache.py` by `cmd/tlc.py` (`--cleanup`) and the old runner. [39](39-tlc-command.md) deletes both; that is why 39 depends on this package: the old `cmd/modules` would otherwise still import them.

**Decisions this rests on.**

- D47: the group is `module`, the folder `module/`. The rename's changelog line is 29's.
- D14: no alias for `modules`, no shim for `modules path`, no migration of `<cache>/modules`. [48](48-command-tree.md) asserts that `tlaup modules` and `tlaup modules path` exit 2.
- D23: no prompt when a module is replaced; "Replaced module X" says what happened.
- D29: tlaup never returns 1; the old commands' `typer.Exit(1)` goes with them.
- D30: the listing and the folder on stdout; "Added", "Replaced", "Removed", warnings and errors on stderr.
- D38: no `ls` or `rm`.
- D45 does not apply to `module add`, but its spirit does: what the user typed (the name, the path) is checked before the build and Java are asked for, and a module of `.tla` files alone needs neither.
- D15: no Windows CI. `require_javac` finds `javac.exe`; paths with `pathlib`.

**Points a worker could miss.**

- *`module remove ../tool`, not only `../tools`.* The design's text, the roadmap item and the M1 Fixed entry say `../tools` because that was the old store's folder name. After D47 the store is `<cache>/tool`, and `../tool` is the name that would reach it. The scenario outline has both; the changelog keeps the design's words.
- *The name is the resolved folder's.* `tlaup module add .` in a folder named `Queue` registers `Queue`; `tlaup module add /` is `InvalidName`, not an add of the whole cache (today's defect).
- *`get_build` and `get_javac` must stay lazy.* A module of `.tla` files alone is added on a machine with no build and no JDK (M2, step 3); the scenario asserts that neither fake starts. Build the store and the client inside the lambda, not before the call.
- *The warnings come after the "Added" line* (M2: "then any override warnings"). The "no override index class was found" note of M3 is one of them.
- *`module list` never fails on a damaged folder*: `Registry.list()` skips what it cannot read. Showing such folders is [46](46-doctor.md)'s.
- *`module dir` reads no setting*, so it works with a broken config file and does not import the settings schema ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)).
- *The help text.* Give each command a one-line help now; the long description of the layout `module add` expects (`modules/*.tla`, `modules/tlc2/overrides/*.java` or `tlc2/overrides/*.java`, `lib/*.jar`; the folder's name becomes the module's name; a module of that name is replaced) and the examples epilog are [14 F7](../design/14-config-and-cli.md#f7-help-text)'s, package 50. Writing the long description here already is welcome; 50 then reviews it.

**Known gaps the design leaves; do not close them.** Per-project modules and community modules (milestone 3). `--json` for `module list` (milestone 4). `javac`'s warnings on success are shown only with `--verbose` (milestone 4), so nothing shows them now. The R7 check at `module add` time needs a pinned build and is skipped for a module with no Java sources.

## Done when

- `modules.feature` and `tests/unit/cmd/test_module_command.py` pass.
- `uv run poe lint` and `uv run poe test` pass; CI is green.
- Nothing under `src/` imports `tlaup.cmd.modules` or `get_modules_dir`; `ResolveMode.COMPILE` is gone; `tlaup modules` is an unknown command (exit 2, Typer's own message).
- The changelog entries above are written once; `README.md` names the `module` commands.
- A fault in `tlaup/modules/` that the scenarios find is fixed in that module in this pull request if it is small, and the pull request says so.
- The pull request says which steps it added and names the inventory rows of the table under Tests (M1, M2, M4, M6, M9, M10, M13, M14, M16, and M5's command form), each with its test.

## Out of scope

- The domain code (registry, build, class-file reader): [30](30-module-build.md). R7's warnings inside `BuiltModule.warnings`: [34](34-override-check.md).
- J1 (Java options), which `module add` does not use: [33](33-tlc-invocation.md). J2 and J3 (`locate`, `require_java`, `require_javac`, the remembered answers): [20](20-java-location.md); their `tlc` scenarios and changelog lines: [39](39-tlc-command.md).
- The scenarios that `tlaup modules` and `tlaup modules path` exit 2, the test that walks the command tree, explicit registration of the whole tree: [48](48-command-tree.md).
- `tlaup module add` leaving a kept run folder alone (R6's scenario) and R6's changelog line: [39](39-tlc-command.md).
- Deleting `tlc/compiler.py`, `tlc/run_cache.py` and the rest of the old runner: [39](39-tlc-command.md).
- Completion of module names for `module remove`: [47](47-completion.md). `doctor`'s line for the modules folder: [46](46-doctor.md).
- The long help text and the epilog of `module add`, and the rest of F8's wording: [50](50-help-and-messages.md).
- The integration test of `docs/examples/QueueModule` on both builds: [52](52-integration-tests.md).

## Risks

- From M1: a module registered under an older release with a name the rule refuses cannot be removed by name. Here that cannot happen, since earlier modules live in the old `modules` folder, which nothing reads any more; the changelog tells users to delete it.
- From M2: a tlaup killed between the two moves leaves the name unregistered for a day; adding the module again fixes it.
- From M3: sources that need a Java newer than 11 no longer compile; the changelog names the setting that raises the release.
- From C1: this is part of the release's second large user-visible change; it lands once, in 0.9.0 (D6).
- From D61: a module that compiled against another registered module or a jar of `module_lib_path` no longer compiles; the Breaking entry says to copy the jar into the module's own `lib/`.
- From the cut: between this package and [39](39-tlc-command.md), the old `tlaup tlc` builds its module classpath from the new registry through one edited line, untested (D62; [01 T11](../design/01-testing.md#t11-the-existing-tests), Risks). Until [52](52-integration-tests.md) nothing runs a real `javac`.
