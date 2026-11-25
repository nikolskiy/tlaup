# 41. The `sany` command and the shared shape of the other tools

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup sany SPEC [-- SANY arguments]` runs SANY on the pinned build in the spec's folder, with the classpath and library path a TLC run of that spec gets, prints each diagnostic once on stdout as `path:line:col: severity: message`, followed by the lines of the spec around it with `^` under the columns (decision D66), and exits 150 when the spec has an error. `tlaup/tools/` holds what `pcal` and `repl` ([42](42-pcal-command.md), [43](43-repl-command.md)) will share: `ENTRY_POINTS`, `ToolInvocation`, `resolve_tool_invocation` with the capability check before Java, and `build_tool_command`.

## Covers

- Roadmap items ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)):
  - "`sany` command: parse a spec and report diagnostics with file, line and column. Reuses the fixed SANY parser." (line 293), in full apart from its integration tests ([52](52-integration-tests.md)).
  - "Keep all three thin (note 15): no logic beyond reading their output, everything through the shared launcher. Check which jar build is running, so the tool can switch to upstream's own entry point when it exists and fall back for older jars." (line 304), in part: the table of entry points, the capability check, the shared invocation and its unit tests. 42 and 43 keep their commands to the same rules.
  - "Golden-file tests for SANY and PlusCal output per TLC version; passthrough after `--` for each." (line 306), in part: passthrough for `sany` in `sany.feature`. The golden tests are [12](12-sany-parser.md) and [14](14-pcal-parser.md); `pcal`'s passthrough is 42's, `repl`'s 43's.
- Design sections:
  - [21](../design/21-other-tools.md), the head: `ToolInvocation`, `resolve_tool_invocation`, `build_tool_command`, the order of the preflight with the capability check, signals for `sany` (`signals_held` entered plainly, held until the command has printed), `--java-opt` and `--auto-install`, the tool's arguments after `--`. The `pcal` and `repl` uses of the same pieces are 42 and 43.
  - [21 S1](../design/21-other-tools.md#s1-sany): all of it except its integration tests (52), and except `source_excerpt` itself and its unit test, which [38](38-terminal-reporter.md) builds beside `format_diagnostic`; this package calls it and has the excerpt's feature scenarios (D66).
  - Inventory row R21 (the SANY source excerpt, decided by D66), for `sany`: owner this package, with 38 for `tlc`.
  - [21 S4](../design/21-other-tools.md#s4-keeping-them-thin): `ENTRY_POINTS`, the capability check as the way to tell what a build can run, and its unit test with the recorded class lists.
  - [11 R11](../design/11-runner.md#r11-preflight), the paragraph on `sany`, `pcal` and `repl`: one resolving function on the same steps as `tlc`, step 0 holding the Java option check and the refusal of `-d`.
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes) rule 2, second exception (150 from `sany`), and rule 5's `sany -- -d`; [02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr) for `sany`: diagnostics on stdout, banner and progress on stderr, two streams through one pipe.
  - [01 T5](../design/01-testing.md#t5-feature-files-and-steps): `sany.feature`.

## Depends on

- [32](32-spec-resolution.md): `resolve_spec`, `find_project_root`.
- [33](33-tlc-invocation.md): `jvm_options` in `java/opts.py`; the way `resolve_tlc_invocation` computes `classpath` and `tla_library`, which this package moves into one function both call (Files); the main class constant in `tlc/command.py`, which `ENTRY_POINTS` replaces.
- [21](21-java-launcher.md): `JavaInvocation`, `signals_held`, `run_streaming(..., merge_stderr=True)`, `ProcessOutcome`.
- [12](12-sany-parser.md): `SanyParser`, `SanyStep`, `SanyLineClass`, `SanyResult`.
- [28](28-first-run.md): `ensure_tools`, `read_auto_install`.
- [38](38-terminal-reporter.md): `format_diagnostic`, which writes a `Diagnostic` in the editor form, and `source_excerpt`, which makes the excerpt under it, both in `reporters/text.py` and shared with the terminal reporter ([22 O3](../design/22-reporters.md#o3-terminal-reporter): "Diagnostics in the editor form of 21 S1, each followed by the source excerpt ... made by the same function as for `tlaup sany`").
- [18](18-feature-harness.md): `tests/test_features.py`, the steps of T5, the fake `java` that logs its working folder ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)).
- [39](39-tlc-command.md): the command conventions of the new `tlc`: the `get_build` wrapper round `ensure_tools`, reading `--auto-install` before the preflight, printing the preflight's warnings, `raise typer.Exit(code)`, imports inside the function; the registration line in `cli.py`.
- [20](20-java-location.md): `require_java`, `JavaRuntime`. [23](23-tool-store.md): `Build.capabilities`, `Build.jar`, `format_build`. [22](22-version-spec-and-jarinfo.md): the `repl` capability as `read_jar` decides it.
- [07](07-golden-files.md): the SANY captures under `tests/parse/golden/sany/<build>/` and their specs under `golden/specs/`, which the fake `java` replays.

Changed from the draft (39, 12): 32, 33, 21, 28, 38 and 18 are named for what is used from each, as the stage 4 agent settled; 20, 23, 22 and 07 are added because the preflight and the features use them directly. 39 stays: this package reuses its wrapper and conventions rather than writing them twice.

## Files

Creates:

- `src/tlaup/tools/__init__.py`: `ENTRY_POINTS` only, so that `tlc/command.py` can import it without loading the rest.
- `src/tlaup/tools/invocation.py`: `ToolInvocation`, `REQUIRED_CAPABILITY`, `resolve_tool_invocation`, `build_tool_command`.
- `src/tlaup/tools/sany.py`: `run_sany`, `SanySink`, `SanyOutcome`, `sany_exit_code`.
- `src/tlaup/cmd/sany.py`: the command.
- `src/tlaup/cmd/common.py` (stage 4's name): the run `get_build` wrapper of [39](39-tlc-command.md), moved here from `cmd/tlc.py` so that the four run commands share one. If 39 already put it in a module of its own, use that and create nothing.
- `tests/features/sany.feature`.
- `tests/unit/tools/test_invocation.py`, `tests/unit/tools/test_sany.py`, `tests/unit/tools/test_entry_points.py`.
- `tests/unit/data/jar-classes/v1.7.4.txt` and `rolling.txt` (stage 4's names under T4's `tests/unit/data/`): the class names in each jar, one per line, sorted, with a first comment line naming the build (tag or CalVer, commit, SHA-256 of the jar) they were read from.

Changes:

- `src/tlaup/java/classpath.py`: one function, written by stage 4, that returns the classpath and the TLA-Library folders of a run from the arguments `resolve_tlc_invocation` passes to `ClasspathResolver` today (the settings, the project root, the build's jar, and whatever else 33's call takes). `resolve_tlc_invocation` calls it instead of the resolver, and so does `resolve_tool_invocation`: "the same classpath and `-DTLA-Library` a TLC run of that spec would get" (S1, step 2) is then one call, not two copies.
- `src/tlaup/tlc/invocation.py`: those lines replaced by the call. Nothing else.
- `src/tlaup/tlc/command.py`: the constant `tlc2.TLC` replaced by `ENTRY_POINTS["tlc"]` (S4: "Nothing else names a main class").
- `src/tlaup/cmd/tlc.py`: imports the wrapper from `cmd/common.py`. Nothing else.
- `src/tlaup/cli.py`: one line registering `sany`.
- `CHANGELOG.md`: the entry under Changelog.
- `docs/contributing/development.md`: a line in the code map for `src/tlaup/tools/`.

Deletes: nothing. The old `tlaup.tlc.sany` went with [39](39-tlc-command.md).

Files another package of the same period touches: `src/tlaup/cli.py` (one line each for 40 to 47); `src/tlaup/cmd/tlc.py` with [40](40-live-display.md), which adds two options there (this package changes one import line); `CHANGELOG.md`; `tests/steps/*.py`, if a step is added (none is planned). 42 and 43 come after this package and add their own files beside these.

## Interfaces

Provides, from the head of [21](../design/21-other-tools.md); what stage 4 added is marked.

```python
# tlaup/tools/__init__.py
ENTRY_POINTS: Mapping[str, str] = {"tlc": "tlc2.TLC", "sany": "tla2sany.SANY", "pcal": "pcal.trans", "repl": "tlc2.REPL"}

# tlaup/tools/invocation.py
Tool = Literal["sany", "pcal", "repl"]
REQUIRED_CAPABILITY: Mapping[Tool, str] = {"repl": "repl"}     # written by stage 4: a tool missing here needs none

@dataclass(frozen=True)
class ToolInvocation:
    build: Build; java: JavaRuntime
    main_class: str
    spec: Path | None                  # resolve_spec's result; None for repl
    cwd: Path | None                   # the spec's folder for sany and pcal; None (do not change folder) for repl
    classpath: tuple[Path, ...]; tla_library: tuple[Path, ...]; jvm_options: tuple[str, ...]
    args: tuple[str, ...]              # the tool's own arguments, after `--`, as typed; the spec is not among them
    warnings: tuple[str, ...]          # from finding Java (13 J2, J3)

def resolve_tool_invocation(tool: Tool, spec: str | None, *,
                            java_opts: Sequence[str], extra_args: Sequence[str],
                            paths: AppPaths, settings: Settings, env: Mapping[str, str], cwd: Path,
                            home: Path,                       # written by stage 4, as 33 added it: find_project_root needs it
                            get_build: Callable[[], Build]) -> ToolInvocation
def build_tool_command(inv: ToolInvocation) -> JavaInvocation      # pure
```

**The order of `resolve_tool_invocation`** ([21](../design/21-other-tools.md), head; [11 R11](../design/11-runner.md#r11-preflight); D45). Each step raises and stops:

| Step | What | Failure |
| --- | --- | --- |
| 0 | `jvm_options(settings.java.opts, env, java_opts)` (33's function); for `sany`, an argument in `extra_args` that is exactly `-d` | `UsageError` (2) |
| 1 | `sany`, `pcal`: `resolve_spec(spec, cwd)`; then `find_project_root(spec, home)` for `sany` | `SpecNotFound` (4), `UsageError` (2) |
| 3 | `get_build()` | what `ensure_tools` raises (3, or an install's error) |
| 3b | `REQUIRED_CAPABILITY[tool]`, when there is one, is in `build.capabilities` | `ToolNotInBuild` (3); Java is not started, not even for its version |
| 4 | `require_java(env, min_version=settings.java.min_version, cache_file=paths.java_cache)` | `JavaNotFound`, `JavaTooOld` (3), `Failed` (5) |
| after | classpath and library folders, `cwd`, `args`, `warnings` | nothing |

There is no step 2: these tools take no cfg. `--auto-install` is read by the command with `read_auto_install` before this function is called, as 39 does, so a bad value is a usage error before the spec is looked at.

**What each tool gets** (21's table of how each tool is started, [00](../design/00-overview.md#the-run-pipeline)):

| Tool | `cwd` | `classpath`, `tla_library` | Arguments built |
| --- | --- | --- | --- |
| `sany` | `spec.parent`: the spec's folder as the user named it, links not resolved | what a TLC run of the spec gets (the function in `java/classpath.py`, with the spec's project root) | `<args> <spec file name>` |
| `pcal` | `spec.parent` | the build's jar alone; no library folders | `<args> <spec file name>` |
| `repl` | `None` | what a TLC run without a spec gets: project root `None` (the registered modules and the config paths) | `<args>` |

**`build_tool_command`**, pure: `JavaInvocation(java=inv.java.tool.path, jvm_options=inv.jvm_options, system_properties=(("TLA-Library", os.pathsep.join(...)),) when tla_library is not empty, else (), classpath=inv.classpath, main_class=inv.main_class, args=inv.args + (inv.spec.name,) when there is a spec, cwd=inv.cwd)`. The lifeline and the encoding options are added by `argv()` ([21](21-java-launcher.md)); the override property of `tlc` is not set for these tools, which load no overrides.

**The refusal of `-d`** (S1, step 7). Exactly the argument `-d`, nothing looser: a dash group holding a `d` would refuse `-error-codes`, and SANY refuses grouped flags such as `-dl` and `-ls` itself, with exit 255 and without starting its explorer. `UsageError`, message along the lines of "`-d` starts SANY's interactive explorer, which waits for input that tlaup does not give it", hint: run it with Java directly on the jar that `tlaup tool path` prints. The hint names no command this release does not have (S1, index "Clerical"): milestone 4's generic exec command, once it exists, is named from then on. `-D` was not tried and is not refused.

**`ToolNotInBuild`** (S3, step 1): "the pinned build v1.7.4@5a47802 has no REPL" / hint "install a rolling build: `tlaup tool install rolling`", the build written by `format_build`. Built here, because the check is here; 43 has the scenario.

```python
# tlaup/tools/sany.py, written by stage 4: domain code returns values and does not print (00), so the command
# gives the run a sink to print through, as the runner gives the reporter its events.
class SanySink(Protocol):
    def chatter(self, line: str) -> None          # BANNER, PROGRESS: stderr, as SANY wrote it
    def other(self, line: str) -> None            # OTHER: stdout, as SANY wrote it
    def diagnostic(self, diagnostic: Diagnostic) -> None   # one completed diagnostic, file already filled in

@dataclass(frozen=True)
class SanyOutcome:
    result: SanyResult
    process: ProcessOutcome
    exit_code: int

def run_sany(inv: ToolInvocation, java_inv: JavaInvocation, sink: SanySink,
             finish: Callable[[SanyOutcome], None]) -> SanyOutcome
def sany_exit_code(process: ProcessOutcome, result: SanyResult) -> int      # pure
```

`run_sany`: `with signals_held() as signals:` run `run_streaming(java_inv, on_stdout=..., on_stderr=..., signals=signals, merge_stderr=True)`; each line goes to one `SanyParser.feed`, and the step is routed by its class, with the command deciding nothing about a line itself (S1, step 3):

| `SanyStep.line_class` | Goes to |
| --- | --- |
| `HEADER`, `STRUCTURE`, `POSITION`, `MESSAGE` | nowhere: the diagnostic stands for the line |
| `BANNER`, `PROGRESS` | `sink.chatter` (D30: progress) |
| `BLANK` | nowhere |
| `OTHER`, and any class P8 adds later | `sink.other` (D9) |

and each diagnostic in `SanyStep.diagnostics` to `sink.diagnostic`, with `file` set to the spec's path when the parser left it `None` (the module was never announced). `on_stderr` is never called with `merge_stderr=True`; pass a function that raises `InternalError`. The line handed to the sink is the line as received with its line ending removed, not the stripped one. When the child has ended and no signal stopped it, `parser.close()` and its diagnostics, then `finish(outcome)` (the summary), still inside the block: the handlers are held "until the command has printed what it prints". After a signal the parser is not closed and `finish` is not called: "the diagnostics the parser had completed by then are printed; no summary line is".

`sany_exit_code` (S1, step 6, D29, D55): the launcher's code when a signal or a closed pipe stopped the run (`process.stopped_by` set, or `process.stopped_for_closed_pipe`); else 150 when any diagnostic of `result` has severity `error`; else `process.exit_code`, SANY's own. A warning alone changes nothing. No `-error-codes` is added, on either build.

**The editor form and the excerpt** (S1, step 4, D66), from [38](38-terminal-reporter.md), which owns both in `reporters/text.py`. This package and the terminal reporter call the same functions, so the two commands print a diagnostic the same way; the signatures are 38's (38 adds `spec`, the path written when the parser left `file` as `None`, so the fallback above can also be left to it):

```python
def format_diagnostic(d: Diagnostic, *, cwd: Path, spec: Path) -> list[str]
    # first line: "<path>:<line>:<col>: <severity>: <message>", or "<path>: <severity>: <message>" with no location;
    # <path> is diagnostic.file written relative to cwd when it lies beneath cwd, else as given (absolute);
    # the message's lines joined with "; "; then each line of `details`, indented
def source_excerpt(text: str, location: Location) -> list[str]
    # S1: two lines before, the line, the ^ marks, "Error here: line L, col A to B", two lines after
```

The sink's `diagnostic` prints the editor-form line, then, for a diagnostic with a location, the excerpt, then the details the parser kept apart (a parse error's residual stack), indented, all on stdout. The command reads the file the editor-form line names (the file SANY announced for the module, absolute), as UTF-8 with undecodable bytes replaced, and gives its text to `source_excerpt`; no location, a file that cannot be read, or a line not in it give the editor-form line alone, with no note. The excerpt is text from outside tlaup, printed as text, never as markup ([10 P11](../design/10-parser.md#p11-tlc-text-and-rich-markup)). For research 12's `SemErr.tla` S1 gives:

```
SemErr.tla:4:13: error: Unknown operator: `y'.
     2 | EXTENDS Naturals
     3 | VARIABLE x
     4 | Init == x = y
       |             ^
       | Error here: line 4, col 13 to 13
     5 | Next == x' = x + 1 + Foo(2)
     6 | ====
SemErr.tla:5:22: error: Unknown operator: `Foo'.
     3 | VARIABLE x
     4 | Init == x = y
     5 | Next == x' = x + 1 + Foo(2)
       |                      ^^^
       | Error here: line 5, col 22 to 24
     6 | ====
```

Other examples from S1: `MissingMod.tla: error: Cannot find source file for module NoSuchModule imported in module MissingMod.` and `Pcal.tla: warning: The PlusCal algorithm in module Pcal has changed since its last translation.`, which have no location and so no excerpt.

```python
# tlaup/cmd/sany.py
def sany(ctx: typer.Context,
         spec: str,                                   # required (C1)
         sany_args: list[str] | None = None,          # everything after `--`
         java_opt: list[str] | None = None,           # --java-opt OPT, repeatable
         auto_install: str | None = None) -> None     # --auto-install stable|rolling, else TLAUP_AUTO_INSTALL
```

The command function, on 39's shape: `read_auto_install`; `resolve_tool_invocation("sany", ...)` with the run wrapper as `get_build`; `build_tool_command`; each warning with `ui.warning`; `run_sany` with a sink that prints through `ctx.ui` (`chatter` and the summary on `ui.err`, `other` and the diagnostics with their excerpts on `ui.out`, as text, never as markup, not wrapped: [10 P11](../design/10-parser.md#p11-tlc-text-and-rich-markup)); `raise typer.Exit(outcome.exit_code)`. The summary on stderr (S1, step 5), wording by stage 4 from S1's two examples: `no errors` when there is no diagnostic at all, else `<n> error(s), <m> warning(s)` with the plural as English needs (`1 error, 0 warnings`, `2 errors, 1 warning`, `0 errors, 1 warning`).

Help of `sany`, one line each, which [50](50-help-and-messages.md) may reword and not drop: it reads the spec from the spec's own folder; modules are searched in the spec's folder, then the library folders, then the standard modules, then the classpath; `-d` is refused and how to run it instead. SANY's own synopsis `SANY [-dls] ...` is not copied: SANY refuses grouped flags.

Consumes: `resolve_spec`, `find_project_root` (32); `jvm_options`, the classpath call of `resolve_tlc_invocation` (33); `ClasspathResolver` (30, through 33); `JavaInvocation`, `signals_held`, `run_streaming`, `ProcessOutcome` (21); `SanyParser` and its types (12); `ensure_tools`, `read_auto_install` (28); `require_java`, `JavaRuntime` (20); `Build`, `format_build` (23); `format_diagnostic`, `source_excerpt` (38); `AppContext`, `AppPaths`, the errors (02); `Ui` (16); `Settings` (19).

Used by: [42](42-pcal-command.md) and [43](43-repl-command.md) (`resolve_tool_invocation`, `build_tool_command`, `cmd/common.py`, the conventions of `cmd/sany.py`).

## Tests that must pass

`tests/features/sany.feature`, in-process (the fake `java` gets pipes under `run_streaming`, so no situation of T5 applies), with the fake replaying the SANY golden captures of 07 and a spec of the same name from the golden specs. On each build where the case exists:

- A good spec (`sany-good`): exit 0, `stdout is empty`, `stderr contains "no errors"`.
- Two semantic errors (`sany-semerr`, replayed with exit code 0): exit 150; `stdout contains ": error: " 2 times`; `stdout contains "SemErr.tla:4:13: error: Unknown operator: `y'."`.
- A parse error (`sany-parseerr`, exit 255): one `: error: ` line and exit 150.
- A missing module (`sany-missingmod`) on the replay of each build: one line with no position (`MissingMod.tla: error: Cannot find source file for module NoSuchModule`), exit 150; on v1.7.4 `stdout contains "File does not exist"` (the line that comes from SANY's stderr, through the one pipe), and on rolling the message once although SANY printed it twice.
- 4802 (`sany-warn4802`, replayed with exit code 0): `stdout contains ": error: " 1 times` and exit 150 (D55).
- The stale-PlusCal warning alone (`sany-stale-alg`, both forms): `stdout contains ": warning: " 1 times`, exit 0.
- `-- -xy` (`sany-grouped-unknown`, exit 255): `java was started with "-xy"`; SANY's own text (`Illegal switch: -xy` on v1.7.4, `Invalid option: -xy` on rolling) is on stdout; exit 255.
- The source excerpt (D66; inventory row R21): the `sany-semerr` replay with the fake's `replace` mapping the capture's folder to the scenario's folder, where the scenario writes research 12's `SemErr.tla` (`a file "SemErr.tla" containing:`), gives on stdout exactly the two editor-form lines, each followed by its excerpt as above (the two lines after included), and exit 150. The same replay without the file there gives the two editor-form lines alone, exit 150, and no `error:` line of tlaup's own. The pull request names row R21.
- `-- -d`: exit 2, one `error:` line, `java was not started`; the same with `no build is installed`, and then `0 requests were sent to GitHub` and nothing installed (no prompt, D45).
- The banner and progress of a replay: `stderr contains "SANY2 Version"` and `stderr contains "Semantic processing of module"`; `stdout does not contain "Parsing file"`.
- The working folder: `java was started with "SemErr.tla"` (the bare file name), and `java was started in the folder` the spec's folder, in a scenario where tlaup is started in another folder and the spec is named by a relative path from there.
- The preflight: a missing spec exits 4 and `java was not started`; nothing installed exits 3 (`CannotAsk` in-process); `java is not installed` exits 3 and `java did not run "tla2sany.SANY"`; `--java-opt=-Xss8m` is in the logged command.

`tests/unit/tools/test_invocation.py`, plain pytest, real files in a temporary folder, a stand-in `get_build` that counts its calls and returns a `Build` made with chosen capabilities, and `require_java`'s `ask_version` parameter where Java is reached:

- The order: `-d` with nothing else valid gives `UsageError` with `get_build` not called; a missing spec gives `SpecNotFound` with `get_build` not called; an unbalanced quote in `TLAUP_JAVA_OPTS` gives `UsageError` before the spec is looked at.
- `-d` is refused exactly: `-d` refused; `-dl`, `-error-codes`, `-D` and `-d2` not.
- `repl` with a build whose capabilities lack `repl`: `ToolNotInBuild`, and `ask_version` was not called (Java not started); with `repl` in the capabilities, the invocation is built. `sany` and `pcal` need no capability.
- `sany`: `cwd` is the spec's folder as named, also when that folder is reached through a symbolic link (the link is kept; skipped where links cannot be made); `classpath` and `tla_library` equal those of `resolve_tlc_invocation` for the same spec and settings, with a registered module and a project `modules/` folder present.
- `pcal`: `classpath` is the jar alone and `tla_library` empty. `repl`: `cwd` is `None`, `spec` is `None`, the paths are those of a run with no project root.
- `build_tool_command`: the spec's file name is the last argument for `sany` and `pcal`, after the tool's arguments in the order given; `repl` has no spec argument; no `TLA-Library` property when the folders are empty; `main_class` is `ENTRY_POINTS[tool]`.

`tests/unit/tools/test_sany.py`, plain pytest:

- `sany_exit_code` on hand-built outcomes and results: 150 with an `error` diagnostic and SANY's 0; 150 with SANY's 255; SANY's 0 with a `warning` only; SANY's 255 with no diagnostic; 130, 143 and 129 after a signal whatever the diagnostics; 141 after a closed pipe.
- S1's unit tests of the path rule and of `source_excerpt` are 38's (`tests/unit/reporters/test_text.py`), beside the functions; this package adds none.

`tests/unit/tools/test_entry_points.py` (S4): every value of `ENTRY_POINTS` is a class in `jar-classes/rolling.txt` (as `tlc2/REPL.class` and so on); `tlc2.REPL` is absent from `jar-classes/v1.7.4.txt`, and the other three are present there (the last half is stage 4's: `tlc`, `sany` and `pcal` run on both builds).

Old tests: none; the old suite went in [03](03-test-foundation.md) (decision D62). No stateful test applies.

## Changelog

Added (S1, word for word): "`tlaup sany SPEC` runs the SANY parser and prints its findings as `path:line:col: severity: message`, each followed by the lines of the spec around it with `^` under the columns. It exits 150 when the spec has errors."

S4 has none. V9's entry, which names `sany`, `pcal` and `repl` among the commands that ask on a first run, was written by [39](39-tlc-command.md).

## Context for the worker

**State of `main`.** `tlaup tlc` runs on the new chain ([39](39-tlc-command.md)); the launcher, `tlaup_parse` with `SanyParser`, the store, `ensure_tools`, `resolve_spec`, `jvm_options` and the plain terminal reporter exist. 40, 42 to 47 may be in flight beside this package. Nothing named `tools/` exists directly under `src/tlaup/`; the old command group `cmd/tools/` was replaced by [29](29-tool-commands.md), and the new package is `tlaup/tools/`, not under `cmd/`.

**Decisions this rests on.**

- D5: the commands stay thin. S4 says what that forbids: no tool flags of tlaup's own beyond `--java-opt` and `--auto-install`; no reinterpretation of the result except `sany`'s exit code; no look at the tool's arguments except to refuse `-d`; no files written; no retry.
- D29, D55: 150 for an error, SANY's own code otherwise. SANY says 0 for semantic errors and 255 for parse errors, so its code cannot be used; 4802 and the two stuttering lints are errors because TLC refuses such a spec with 150.
- D30, D22: diagnostics on stdout in the editor form, banner and progress on stderr.
- D66: the excerpt under each diagnostic with a location, in terminal output only; milestone 4's JSON carries the file, line and column and never the excerpt. 0.8 printed such an excerpt in a `tlc` run only, with `▲` marks and box characters; both commands now print it with `^` and `|`.
- D9: every line SANY printed and the parser did not use is shown, on stdout.
- D45: command line, spec, build, Java; the capability belongs to the build step and needs no Java.
- D56 and D51: the encoding options and the lifeline come with `argv()`, for SANY too. D60: SANY stays in tlaup's process group; `run_streaming` decides that from `merge_stderr=True`.

**Facts a worker could miss** (S1, restated from research 12, 22, 27 and 32):

- SANY looks for the modules a spec extends in its working folder, then the library folders, then the standard modules in the jar, then the classpath, and not beside the spec. Started elsewhere with an absolute spec path it does not find the modules beside the spec, and a module of the same name in the starting folder wins. That is why `sany` departs from D34 and runs in the spec's folder with the bare file name. TLC inside a run searches the spec's folder first, so the two commands see the same modules.
- Standalone SANY honours `-DTLA-Library` and the classpath as TLC does, on both builds: registered modules, a project's `modules/` and a CommunityModules jar on the classpath are all found. A jar named as a library folder is useless; jars go on the classpath, which is where tlaup puts them.
- SANY writes everything to stdout except one line, `File does not exist: ...` (v1.7.4: for a missing module and a missing file; rolling: for a missing file). One pipe keeps it in its place; the diagnostic itself is on stdout. A JVM warning about an option also arrives through the pipe, is not recognised and is printed on stdout with SANY's other unrecognised lines (S1, Risks).
- With `-d` and no input SANY prints its prompt in a loop for ever (143 MB before research 12 killed it).
- One spec per invocation: SANY takes several files, but they can be in different folders and the working folder depends on the folder.
- The rolling `-help` page has ANSI bold codes; they are shown as printed.

**Traps.**

- The replays carry `<tmp>` where the captures had real folders, so a diagnostic's file from a `Parsing file` line is a path outside the test's folder and is printed as given, and no file can be read there, so no excerpt is printed. The features assert the message, the position and the file name; the relative-path rule is the unit test. The fake's `replace` field maps `<tmp>/...` onto the scenario's folder in the excerpt scenario, which needs the file to exist; elsewhere use it only if needed.
- The stale-PlusCal specs may live under `golden/specs/<build>/` (an open choice of 07). Check where 07 put them; the Given step must find the spec for the preflight to pass.
- `java was not started` counts the version check; use `java did not run "tla2sany.SANY"` where Java's check may run.
- A spec reached through a link to its folder: the working folder is the folder as named, links not resolved (as R4 does for TLC). Running SANY there through the link was not tried (S1, Risks).
- Keep `import tlaup.cli` light: imports other than `typer`, `tlaup.errors` and `tlaup.context` go inside the command function ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)).

**Known gaps the design postpones; do not close them here.**

- **v1.7.4's shared temporary module copies** ([13 J1](../design/13-modules-and-java.md#j1-java-options), question 27). v1.7.4 copies every module it reads from a jar or the classpath to `<java.io.tmpdir>/<Module>.tla`, a fixed name, so two v1.7.4 runs at once, of `sany` or `tlc`, write the same files (read from the source, not tried). A per-run `-Djava.io.tmpdir` would remove it; the maintainer postponed it until after the first implementation. Add no such option.
- SANY leaves an empty temporary folder per run on rolling builds (research 12); tlaup does not clean the system's temporary folder.
- Several specs per call; `-error-codes`; the XML exporter: rejected by S1.
- The hint for non-ASCII file names under a non-UTF-8 locale ([11 R3](../design/11-runner.md#r3-non-utf-8-output)) is designed for `tlc`'s preflight; S1 does not ask for it here.

**Windows (D15).** `os.pathsep` for the library property and the classpath; paths with `pathlib`; `relpath` on two different drives raises, so "beneath the starting folder" is decided first and an absolute path printed otherwise. No Windows CI.

## Done when

- `sany.feature` and the three unit test files pass on Linux and macOS in CI; `uv run poe lint` and `uv run poe test` pass.
- `ENTRY_POINTS` is the only place a main class is named in `src/` (a search for the four names finds no other use outside comments); `tlc/command.py` uses it; the classpath of a TLC run and of `sany` come from one function.
- The two class lists are committed with the build they were read from, and the pull request says how they were made (from the jars' file lists, for example with `zipfile`; class names only).
- The changelog entry is under `## [Unreleased]`; the code map names `tools/`.
- The pull request shows `sany.feature` failing before the command existed (T12 rule 6), says which `get_build` module it used, and names the inventory row it covers (R21, for `sany`).

## Out of scope

- `tlaup pcal`, `pcal.feature`, the notes for the files the translator writes: [42](42-pcal-command.md). `tlaup repl`, `repl.feature`, `leave_interrupt`, the scenario for `ToolNotInBuild`: [43](43-repl-command.md).
- `SanyParser` and the SANY golden tests: [12](12-sany-parser.md). The expected SANY results: [15](15-golden-expected-results.md) (15e).
- The terminal reporter's use of the editor form inside a `tlc` run: [38](38-terminal-reporter.md).
- Integration tests ([01 T9](../design/01-testing.md#t9-integration-tests)), all in [52](52-integration-tests.md): the T9 row "`sany` on a good and a bad spec; `pcal` on a copy of a PlusCal spec" (its `sany` half: diagnostics with file, line and column, the exit codes of D29), and S1's integration list: real SANY on both builds, the missing module on v1.7.4 (the run that shows the stderr line is not lost), a spec that extends a registered module, and a spec beside which a module lies while a module of the same name lies in the starting folder (the spec's own is used). The weekly run that catches an upstream rename of a main class: [54](54-integration-job.md).
- The command-tree test and the removed names: [48](48-command-tree.md). Help wording beyond the lines named above: [50](50-help-and-messages.md).
- The hand-off to an upstream entry point: nothing to design until upstream ships one (S4, research 3).

## Risks

- From S1: a JVM warning about an option reaches the parser through the one pipe and is printed on stdout as an unrecognised line. Two v1.7.4 runs at once share the temporary module copies (the gap above). SANY's empty temporary folder per run on rolling. A spec reached through a link to its folder was not tried with SANY alone.
- From S4: an upstream rename of a main class breaks the command for builds after it; the unit test catches it only when the class list is refreshed, and the weekly integration run catches it on the live rolling build.
- From the cut: the rolling jar of the golden captures (2026.11.15.002146) may no longer be downloadable, since `rolling` moves. A current rolling jar's class list serves the test equally; its first line then names that build, which differs from the golden folder's.
- From the cut: this package changes three files of earlier packages (`tlc/invocation.py`, `tlc/command.py`, `cmd/tlc.py`) by a few lines each, to keep one classpath function, one table of main classes and one `get_build` wrapper. A reviewer should see those three diffs as moves, with 33's and 39's tests still green.
- From the cut: `format_diagnostic` and `source_excerpt` are 38's (`reporters/text.py`); this package imports them and adds no second copy.
- From S1: SANY's columns were read as counting characters, a tab as one; if SANY counts a tab otherwise, the marks of an excerpt on a line with tabs stand in the wrong place, and the editor-form line is still right.
