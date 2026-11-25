# 46. `tlaup doctor`, replacing `check-java`

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup doctor` prints one line per check of [23 C1](../design/23-command-layout.md#c1-command-tree) with `ok`, `warning` or `error`, re-runs the Java and `javac` version checks and rewrites their remembered answers, and exits 0 when nothing is an error and 3 otherwise. `check-java`, `java/inspector.py` and their tests are gone.

## Covers

- Roadmap items:
  - "Review the layout of every command so it follows the most common CLI patterns ... a `doctor` command that checks Java, `javac`, the pinned jar, config and folders and absorbs `check-java` ..." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 325), in part: `doctor`. The tree as a whole is [48](48-command-tree.md).
  - "Use `JAVA_HOME` when set, falling back to `PATH`, for both `java` and `javac`." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: "`tlaup doctor` prints both tools with their source" ([13 J2](../design/13-modules-and-java.md#j2-finding-java)). The functions are [20](20-java-location.md).
- Design sections:
  - [23 C1](../design/23-command-layout.md#c1-command-tree): the row "`check-java` becomes `doctor`" in full, with the rule for the levels C1 now states (question Q15, confirmed as this package built it), `doctor.feature` of the Tests, and that row's changelog line.
  - [13 J3](../design/13-modules-and-java.md#j3-one-java-start), Risks: "`tlaup doctor` always re-runs the check and rewrites the entry".
  - [12 V1](../design/12-tools-and-downloads.md#v1-version-store): "`tlaup doctor` reports such folders as leftovers" (twice in V1), with the store method it needs (Interfaces).
  - [14 F2](../design/14-config-and-cli.md#f2-folder-overrides): "`tlaup doctor` ... print the folders in effect".
  - [23 C1](../design/23-command-layout.md#c1-command-tree), the row "`modules path` is removed ... the folders are shown by `doctor`": the module folder is one of the folders shown.
  - The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md), row M15 (changed on purpose): a module folder with no or damaged `module.json` is no longer listed by `module list`; [31](31-module-commands.md) hands showing such folders to `doctor`. Row O1 (`check-java`) is changed on purpose by C1 and needs no test of its own.

## Depends on

- [20](20-java-location.md): `locate`, `require_java`, `require_javac` with `refresh: bool = False` (20 added it for this command), `JavaRuntime`, `JavaTool.source`, `Located.warning`; the errors they raise.
- [23](23-tool-store.md): `ToolStore`, `Build` (`sha256`, `jar`, `path`), `pinned()` and `PinnedBuildMissing`, `builds()`. [22](22-version-spec-and-jarinfo.md): `format_build`.
- [19](19-layered-config.md): `load_settings` (its `LoadedSettings.warnings` for unknown and removed keys; `ConfigInvalid` for a file that does not parse); the default of `java.min_version`.
- [24](24-github-client.md): `token_from_env`, to say whether a token is set and from which variable, never its value.
- [39](39-tlc-command.md): the old runner is gone. `tlc/runner.py` of release 0.8.x is the last caller of `java/inspector.py` other than `check-java` ([20](20-java-location.md), Context); this package deletes `inspector.py` and cannot before 39.
- [16](16-ui-messages.md), [17](17-error-handler.md), [18](18-feature-harness.md): `Ui`, the root group that maps a raised error to its code, the steps and `doctor.feature`'s home.
- [29](29-tool-commands.md): the store steps of the scenarios (`the build ... is installed and pinned`, `no build is installed`, `the jar of the build ... is truncated`).
- [30](30-module-build.md): `Registry.list()` and what makes a folder a module (a valid name and a readable `module.json`), for the `module folder` check's leftovers (row M15).

Changes from the draft (20, 23, 19, 30, 17, 18): 39 is added for the reason above; 16, 22, 24 and 29 are named because the command and the scenarios use them directly. 30 stays, for the module folder's leftovers (an earlier revision of this file dropped it; inventory row M15 brings it back).

## Files

Creates:

- `src/tlaup/cmd/doctor.py`: the command, thin: it calls `run_checks` and prints its lines.
- `src/tlaup/doctor.py`: `run_checks` and `Check` (Interfaces): the checks as domain code that returns values and prints nothing ([00](../design/00-overview.md#packages-after-the-first-wave): only commands print), so they can be tested as plain pytest with real files.
- `tests/features/doctor.feature`.
- `tests/unit/test_doctor.py`.

Changes:

- `src/tlaup/versioning/store.py`: `ToolStore.leftovers()` (Interfaces). [23](23-tool-store.md) left it to this package ("not to be added on a guess ... Package 46 adds what it needs").
- `src/tlaup/cli.py`: register `doctor` with `app.command(name="doctor")`; remove the `check-java` import and registration. One block; [48](48-command-tree.md) rewrites the registration block as a whole.
- `src/tlaup/java/__init__.py`: the re-exports of `inspector.py`'s three functions go; the file keeps only its docstring.
- `CHANGELOG.md`: see Changelog.

Deletes:

- `src/tlaup/cmd/check_java.py`.
- `src/tlaup/java/inspector.py` (`get_java_version`, `validate_java_version` and the rest). If a module other than `cmd/check_java.py` still imports it when this starts, that module's switch package has not been merged; stop and say so.

The old tests of `check-java` went in 03b with the rest of the old suite (decision D62).

Shared with packages that may run beside it (40 to 47 after 39): `src/tlaup/cli.py` (one registration block each), `CHANGELOG.md`. `src/tlaup/versioning/store.py` is 23's; no other package of the period touches it.

## Interfaces

The command, from [23 C1](../design/23-command-layout.md#c1-command-tree): `tlaup doctor`, no arguments, no options. No network, never prompts, never installs. The one thing it writes is the remembered Java check, `<cache>/java.json` ([13 J3](../design/13-modules-and-java.md#j3-one-java-start)), which `refresh=True` rewrites for a plain `java` or `javac` binary; on a fresh home that also creates the cache folder. It writes nothing else: no config file, no run folder, no store file.

**Written by stage 4** (C1 gives the checks and the three words, not the form):

```python
# tlaup/doctor.py
Level = Literal["ok", "warning", "error"]

@dataclass(frozen=True)
class Check:
    name: str                 # "java", "javac", "pinned build", "tool folder", "config file",
                              # "module folder", "config folder", "cache folder", "data folder", "run folder",
                              # "GitHub token"
    level: Level
    detail: str               # one line: what was found
    hint: str | None = None   # the next command, for a warning or an error

def run_checks(paths: AppPaths, env: Mapping[str, str], *,
               ask_version=ask_version) -> list[Check]
    # every check below, in this order; never raises a TlaupError: each failure becomes a Check.
    # ask_version is passed on to require_java and require_javac (the tests give a counting one)

# tlaup/versioning/store.py
class ToolStore:
    def leftovers(self) -> list[Path]
        # every entry directly under the tool folder that is not a build (V1: "a folder is a build only if
        # it holds a jar and a readable build.json with a known schema"), other than the store's own files
        # (.lock, pin, .tmp); sorted by name. Reads only; takes no lock.
```

**The checks**, with C1's words and the level of each finding. The rule behind the levels is C1's (question Q15, confirmed as this package built it): **an error is what makes `tlaup tlc Spec` stop with code 3 ("not set up", [02 X1](../design/02-cross-cutting.md#x1-exit-codes)) or what a run cannot do without (a damaged pinned jar, a cache folder that cannot be written); a warning is what a run survives, but something else will trip on or is off.**

| Check | What it does | ok | warning | error |
| --- | --- | --- | --- | --- |
| `java` | `locate("java", env)`, then `require_java(env, min_version=..., cache_file=paths.java_cache, refresh=True)`. Shows the path, the version and the source (`JAVA_HOME` or `PATH`). | Found, version at least the minimum. | Found and usable, with a warning from J2 or J3: a `JAVA_HOME` with no `java` (fell back to `PATH`), or an answer that is not a version. | `JavaNotFound`, `JavaTooOld`, a `-version` that did not answer (`Failed`), `ToolStartError`. |
| `javac` | The same with `require_javac`. | Found, version at least the minimum. | Not found, too old, or any of `java`'s warnings: only `module add` with Java sources needs it ([13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder)). | Never. |
| `pinned build` | `ToolStore.pinned()`; for a build, the jar's SHA-256 against `Build.sha256`. Shows the build with `format_build(build, store.builds())` and its jar's path. | Present, the jar matches. | Never. | Nothing pinned (hint `tlaup tool install` when no build is installed, else `tlaup tool pin`); `PinnedBuildMissing`; the jar missing, or its SHA-256 differs (hint `tlaup tool install --force <its printed form>`, [12 V12](../design/12-tools-and-downloads.md#v12-install)). |
| `tool folder` | `AppPaths.tools` with the writable test of the folders row, then `ToolStore.leftovers()`. | Writable (or not there yet), no leftovers. | Each leftover named (V1: a folder tlaup cannot read may belong to a newer tlaup, so it is reported, never removed). | Not writable: `tool install` cannot add a build. |
| `config file` | `load_settings(paths, env)`. Shows the path, and "not present (defaults in use)" when there is none. | Loads with no warning. | Loads with warnings: each unknown or removed key, as the loader words them ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration), [F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay)). | `ConfigInvalid`: the file, the line and column or the key (hint `tlaup config edit`). |
| `module folder` | `AppPaths.modules` with the writable test of the folders row, then every entry directly under it that `Registry.list()` does not return: a folder whose name is not a valid module name, or whose `module.json` is missing or unreadable (inventory row M15). Reads only. | Writable (or not there yet), every entry a module. | Each such entry named ("not a module: no readable module.json", "not a valid module name"); never removed. | Not writable: `module add` cannot register a module. |
| `config folder`, `cache folder`, `data folder`, `run folder` | `AppPaths.config`, `cache`, `data`, `runs` (the tool and module folders' paths are the details of their own checks, which apply this row's writable test too): the path, whether it exists, and whether it is writable (for a folder that does not exist yet, whether its nearest existing parent is). A missing folder is not a fault: tlaup makes each when it first needs it. | Writable, or not there yet with a writable parent. | `config folder` or `data folder` not writable (only `config set` and `config edit` write the first; the data folder is unused in the first wave). | `cache folder` or `run folder` not writable: a run writes its run folder there, and `tool install` and `module add` write under the cache. |
| `GitHub token` | `token_from_env(env)`: whether a token is set, and from which variable (`GITHUB_TOKEN` or `GH_TOKEN`). Never the value (C1: "yes or no, never the value"). | Set, or not set ("not set; GitHub allows 60 requests an hour without one"). | Never. | Never. |

With an invalid config file the Java checks use the packaged default of `java.min_version` (11) and say so in the detail; the config's own line is the error.

**What it prints and how it exits.** One line per `Check` on stdout, in the order above, in the form `<name>: <level>, <detail>`, for example `java: ok, 25.0.5 at /usr/lib/jvm/.../bin/java (from JAVA_HOME)` and `pinned build: error, nothing is pinned`; a hint, when there is one, follows on the next line indented by two spaces. stdout, because the report is what was asked for ([02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr): "for other commands, what was asked for"). The words `ok`, `warning`, `error` are C1's; the form `<name>: <level>, ...` is stage 4's, chosen so a scenario can assert one check's level with one `contains` step ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 4). When at least one check is an error, the command then raises `NotSetUp` naming how many checks failed ("2 checks failed"), so stderr has exactly one `error:` line and the code, 3, comes from the error's family through the one mapping ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks), [20 G2](../design/20-groundwork.md#g2-domain-errors)); otherwise it exits 0. Warnings never change the code. Colour, if any, through `Ui`'s policy (`NO_COLOR` honoured, [14 F6](../design/14-config-and-cli.md#f6-messages)).

Consumes: `locate`, `require_java`, `require_javac`, `ask_version` (20); `ToolStore`, `Build` (23); `format_build` (22); `load_settings` (19); `token_from_env` (24); `AppPaths`, `NotSetUp` (02); `Ui` (16).

## Tests that must pass

**`tests/features/doctor.feature`**, in-process (none of T5's five situations applies; the fake `java` started for `-version` is read through a pipe), per [01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 10. Each scenario asserts the exit code; each that exits 3 also asserts `stderr contains "error:" 1 times` and `stderr does not contain "Traceback"`.

- Everything set up: `the build "v1.7.4" is installed and pinned`, `JAVA_HOME is a JDK of version "25.0.5"`: exit 0; `stdout contains` `java: ok`, `javac: ok`, `pinned build: ok`, `config file: ok`, `GitHub token: ok`; `stdout contains "JAVA_HOME"`; `stderr is empty`; `java was started with "-version"` (the check is re-run). `java did not run "tlc2.TLC"`.
- `java is not installed`: exit 3, `stdout contains "java: error"`.
- `java is version "1.8.0_202"` on `PATH`: exit 3, `stdout contains "java: error"`.
- `JAVA_HOME is an empty folder` with a good `java` on `PATH`: exit 0 if nothing else fails, `stdout contains "java: warning"`, `stdout contains "JAVA_HOME"`.
- `javac is not installed`, everything else set up: exit 0, `stdout contains "javac: warning"`.
- `java is version "21.0.1"`, `tlaup doctor`, then `java is replaced by version "25.0.5"`, `tlaup doctor`: the second stdout contains `25.0.5` (two runs in one scenario; the check is re-run, [01 T5](../design/01-testing.md#t5-feature-files-and-steps)).
- `no build is installed`: exit 3, `stdout contains "pinned build: error"`, `stdout contains "tlaup tool install"`.
- Builds installed and none pinned: exit 3, `stdout contains "tlaup tool pin"`.
- `the jar of the build "v1.7.4" is truncated` with it pinned: exit 3, `pinned build: error`, `stdout contains "--force"`.
- A pin naming a build that is gone (`a file "{tools}/pin" containing:` an id with no folder): exit 3, `pinned build: error`.
- A leftover: `a file "{tools}/old-build/tla2tools.jar" containing:` some text, everything else set up: exit 0, `stdout contains "tool folder: warning"`, `stdout contains "old-build"`, and the folder still exists afterwards.
- A module folder that is not a module: `a file "{modules}/broken/module.json" containing:` text that is not JSON, everything else set up: exit 0, `stdout contains "module folder: warning"`, `stdout contains "broken"`, and the folder still exists (row M15).
- `the config file contains:` a file with an unknown key: exit 0 when everything else is set up, `stdout contains "config file: warning"`. With invalid YAML: exit 3, `config file: error`, `stdout contains "tlaup config edit"`, and the `java` line still present.
- `the environment variable "GITHUB_TOKEN" is "doctor-secret-value"`: `stdout contains "GITHUB_TOKEN"`, and neither stream contains `doctor-secret-value`.
- `the folder "{runs}" is read-only` (the folder made first with `a file "{runs}/x" containing:`; skipped as root, T5): exit 3, `stdout contains "run folder: error"`.
- The macOS stub with no JDK ([13 J3](../design/13-modules-and-java.md#j3-one-java-start)): `java answers its version check with "Unable to locate a Java Runtime." on stderr and exit code 1` (T5's step for T4's object form of `version`): exit 3, `stdout contains "java: error"`, `stdout contains "Unable to locate a Java Runtime."`.
- An answer that is not a version: `java answers its version check with "not a version" on stdout and exit code 0`, everything else set up: exit 0, `stdout contains "java: warning"` (J3: the run goes on).
- Nothing but the Java check is written: on a fresh home with `java is version "25.0.5"`, after `tlaup doctor`, `the file "{config}/config.yaml" does not exist` and `the cache holds no run folders`. (The fake `java` is a script, so here not even `java.json` is written; the unit test below covers a remembered binary.)
- `tlaup doctor` makes no request: the isolation fixture's closed-port repository address would change the outcome if it did (T4); and it is in-process with no `GitHub answers` step, so a request would be stopped by the socket block and fail the scenario.

`tests/features/errors.feature`: none new; `doctor`'s only error is `NotSetUp` with its count, covered above.

**`tests/unit/test_doctor.py`**, plain pytest with real files in a temporary `AppPaths`:

- The re-run (J3, Risks): with a real file named `java` that does not start with `#!` (a small executable the test writes; `ask_version` passed as a counting function returning a `25.0.5` banner), `require_java` without `refresh` asks once across two calls, and `run_checks` twice asks twice and leaves `java.json` holding the entry. This is the test the feature cannot be, since the fake `java` is a script and never remembered ([20](20-java-location.md), Context).
- `ToolStore.leftovers()`: a folder with a jar and no `build.json`, one with `"schema": 99`, a stray file, and a real build (through `ToolStore.add` with [05](05-github-recordings.md)'s `make_tools_jar`): the first three are leftovers, the build, `.lock`, `pin` and `.tmp` are not.
- `run_checks` never raises: with no `java`, an invalid config, nothing pinned and a read-only cache folder (skipped as root), it returns one `Check` per name with the levels of the table.
- `run_checks` on a home where only the cache folder's parent exists, with a remembered binary as above: afterwards the cache folder holds `java.json` and nothing else, and no other folder of `AppPaths` was made.
- The SHA-256 comparison: a pinned build whose jar was rewritten with other bytes of the same length is an error; an unchanged one is ok.
- No check's `detail` holds the token's value.

No stateful test applies.

## Changelog

Under `## [Unreleased]`, word for word from [23 C1](../design/23-command-layout.md#c1-command-tree) ("Under Breaking and Removed, one line per row"):

- Breaking: "`tlaup check-java` is now `tlaup doctor`, which also checks the pinned build, the config and the folders."

J2's and J3's entries are [39](39-tlc-command.md)'s and say nothing about `doctor`.

## Context for the worker

**Decisions this rests on.** D38 and C1's row: one command name, `doctor`, the name `brew`, `flutter` and `mise` use; no `check-java` alias (D14). D29: exit 3 for "not set up", never 1. D30: the report on stdout, the one `error:` line on stderr. D41: the token's value is never printed. D15: `shutil.which` adds `.exe`; folders through `pathlib`; the writable test uses `os.access` and does not assume POSIX permission bits beyond it.

**Why `run_checks` raises nothing.** Every check reports what it found, so one failure does not hide the next: a user with no Java and a broken config learns both at once. The errors the Java and config functions raise are caught by their type (`JavaNotFound`, `JavaTooOld`, `Failed`, `ToolStartError`, `JavacNotFound`, `ConfigInvalid`, `PinnedBuildMissing`, `FileOperationError`) and turned into a `Check`; anything else is a bug and passes up to the handler as an internal error (5), and no blind `except` is written ([30 I8](../design/30-ci-and-release.md#i8-lint-rules)).

**The re-run and the remembered answer.** `refresh=True` makes `require_java` and `require_javac` ask the tool even when `java.json` has a matching entry, and rewrite the entry under the usual rules: only a plain binary named `java` or `javac` is remembered; a `#!` script, a link to a file of another name, and the macOS `/usr/bin` stubs never are ([13 J3](../design/13-modules-and-java.md#j3-one-java-start)). So on most machines `doctor` is the way out of a stale answer, as J3's Risks say, and it is what a user is told to run when Java changed in a way the size and time did not show.

**The fake `java` in the scenarios** is a script, so it is never remembered and is started for `-version` on every run; `java was started with "-version"` therefore holds whether or not `refresh` works, which is why the re-run is also a unit test.

**What `check-java` did**, for the pull request's description: it loaded the old config, ran `java -version` through `PATH` only, printed "Detected Java version" and exited 1 with `Error:` for a Java that was missing or too old. `doctor` covers that line as its `java` check, with `JAVA_HOME` first.

**The levels.** C1 gives the rule above and places the two findings a reader could place otherwise: a missing or too old `javac` is a warning, since only `module add` with Java sources needs it, and nothing pinned is an error, since `tlaup tlc Spec` with nothing pinned stops with 3 wherever it cannot ask. The maintainer confirmed both as this package built them (question Q15). Warnings never change the code.

**The module folder's leftovers** (inventory row M15). `module list` shows only what `Registry.list()` returns ([31](31-module-commands.md)), so a folder with a damaged `module.json` would otherwise be seen nowhere; 31 hands it to `doctor`. C1's list of checks does not name it (reported to the index); it is a warning, like the tool folder's leftovers, because a run skips such a folder and nothing breaks.

**State of `main` when this starts.** `tlaup tlc` on the new runner (39); the old runner is gone, so `inspector.py`'s only caller is `cmd/check_java.py`; the store and the `tool` commands (29); the registry and the `module` commands (30, 31); the new loader (19, and the `config` commands if 44 is merged); `locate.py` with `refresh` (20). `check-java` is still registered, with no tests (03b). Packages 40 to 47 may be in flight beside this one.

## Done when

- The scenarios and unit tests above pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- `tlaup doctor` exists; `tlaup check-java` does not (the scenario that it exits 2 is [48](48-command-tree.md)'s); nothing under `src/` imports `tlaup.java.inspector`, and the file is gone, as is `cmd/check_java.py`.
- The changelog entry is written.
- The pull request pastes one `tlaup doctor` output with everything set up and one with two errors.

## Out of scope

- Finding and checking Java (`locate`, `require_java`, `require_javac`, `refresh`): [20](20-java-location.md).
- Repairing anything: `doctor` reports; `tool install --force`, `tool pin` and `config edit` repair, and the hints name them.
- Removing leftover folders: never by tlaup (V1).
- The tree test and the `check-java` removed-name scenario: [48](48-command-tree.md).
- Checking registered modules (whether their classes load on the pinned build): not asked for by C1; the override check of [11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load) runs at each `tlc` start. `doctor` names only folders under the module folder that are not modules (row M15).
- A `--json` form of the report: milestone 4.

## Risks

- From J3: a compiled launcher named `java` that picks its JVM from the environment is remembered and can go stale; `doctor` rewrites the entry, which is the way out, but only when the user runs it.
- From C1: the report's form and its levels are first seen by users in 0.9.0; scripts should use the exit code, not the text.
- From the cut: hashing the pinned jar reads about 4 MB on each run of `doctor`; fine for a command run by hand.
- From the cut: until [48](48-command-tree.md) checks the whole tree, a mistyped registration of `doctor` would show only as a missing command; the scenarios above are the guard.
