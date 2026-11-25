# 02. Errors, paths and the context skeleton

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

Three small modules exist that everything later is built on: `tlaup/errors.py` (the error families and their exit codes), `tlaup/paths.py` (`AppPaths`, the only code that asks the platform or the environment where tlaup's folders are) and `tlaup/context.py` (the application context with `get_context` and `reset`). The old code takes its two root folders from `AppPaths`, so `TLAUP_HOME` and the three folder variables move everything tlaup reads and writes.

## Covers

- Roadmap items:
  - "Environment overrides for the tool's folders (decision D25). Lands early, with the test isolation work in milestone 2." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)). Closed here as far as the variables go; the commands that print the folders in effect (`doctor`, `cache dir`, `config path`, `tool dir`, `module dir`) come with their command packages (29, 31, 44, 45, 46).
  - "A small family of domain errors (spec not found, tool not installed, Java missing or too old) mapped to exit codes in one place." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)), in part: the classes and the code each carries. The one handler that turns them into a message and an exit code is package 17; each error is first raised by the package that builds the code that can fail.
- Design sections:
  - [20 G2](../design/20-groundwork.md#g2-domain-errors): `errors.py` with the four families and every named subclass, and the unit test over subclasses. Not here: the handler and the printing of notes (14 F10, package 17), the `errors.feature` scenarios (packages 17 and 18 and the switch packages 29, 31, 39, 44), the removal of the hand-written "Missing argument" check in `cmd/tlc.py` (package 39).
  - [14 F2](../design/14-config-and-cli.md#f2-folder-overrides): `AppPaths`, the four variables, the unit tests, the changelog entry. Of the sentence "`config/loader.py` and `versioning/paths.py` lose their path functions" this package does the first step only; "Context for the worker" says exactly which and who does the rest.
  - [00, application context](../design/00-overview.md#application-context): `AppContext`, `get_context`, `reset`, with the fields that can exist now (`paths`, `env`, `debug`). `ui` is added by package 16 and `settings` by package 19; the root callback that builds the context from the root options is package 17.
- The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md): row C1 (settings in `config.yaml` in the platform's config folder named `tlaup`, tools and modules in its cache folder named `tlaup`), whose owner this package is; its test is the fallback case of `test_paths.py`.

## Depends on

- [01](01-ruff-format.md): the formatted tree and the enforced format check. Nothing else.

## Files

Creates:

- `src/tlaup/errors.py`
- `src/tlaup/paths.py`
- `src/tlaup/context.py`
- `tests/unit/test_errors.py`, `tests/unit/test_paths.py`, `tests/unit/test_context.py`

Changes:

- `src/tlaup/config/loader.py`: the bodies of `config_dir()` and `cache_dir()` return `get_context().paths.config` and `get_context().paths.cache`. The `platformdirs` import and `_APP_NAME` leave this file; the name `tlaup` is given to `platformdirs` in `paths.py` only. Nothing else in the file changes: `config_path()`, `ensure_config()`, `load_config()`, `save_config()` and `workspace_root()` stay as they are.
- `tests/unit/test_config.py`: `test_config_paths` is deleted. It replaces `platformdirs.user_config_dir` and asserts the three old functions, which after this package read the cached context, so whether it passes depends on what ran before it; `tests/unit/test_paths.py` tests the same thing on `AppPaths` without a patch. The rest of the old suite stays as it is until 03b deletes all of it ([01 T11](../design/01-testing.md#t11-the-existing-tests), decision D62).
- `CHANGELOG.md`: one entry, see Changelog.
- `docs/contributing/development.md`: the section "Where tlaup keeps its files" names `src/tlaup/paths.py` instead of `_APP_NAME` in the loader, and the section "Running tlaup without touching your own folders" gives `TLAUP_HOME=<tmp>/tlaup uv run tlaup tools list` in place of the two `XDG_*` variables (its warning about `gh`, `git` and `uv` reading those variables no longer applies to the new form; say that the variable is tlaup's own).

Deletes: nothing.

`src/tlaup/versioning/paths.py` is **not** changed. `pyproject.toml` is not changed (`platformdirs` is a dependency already, and its mypy override stays).

Shared with later packages: `src/tlaup/errors.py` (a package may add a field to one class, for example the reset time of `RateLimited` in package 24; one class each), `src/tlaup/context.py` (package 16 adds `ui`, package 19 adds `settings`, package 17 the builder for the root options; one field or one function each), `CHANGELOG.md`.

## Interfaces

Provides.

`src/tlaup/errors.py`, copied from [20 G2](../design/20-groundwork.md#g2-domain-errors):

```python
class TlaupError(Exception):
    exit_code: ClassVar[int]
    def __init__(self, message: str, *, hint: str | None = None, details: str | None = None): ...

class UsageError(TlaupError):   exit_code = 2
class NotSetUp(TlaupError):     exit_code = 3
class NotFound(TlaupError):     exit_code = 4
class Failed(TlaupError):       exit_code = 5
```

`message`, `hint` and `details` are readable attributes of the same names (package 17's handler prints them); `str(error)` is the message.

| Family | Subclasses, all defined here |
| --- | --- |
| `NotSetUp` | `NoToolsInstalled`, `NoPinnedBuild`, `PinnedBuildMissing`, `JavaNotFound`, `JavaTooOld`, `JavacNotFound`, `ConfigInvalid`, `ToolNotInBuild`, `CannotAsk` |
| `NotFound` | `SpecNotFound`, `CfgNotFound`, `VersionNotFound`, `ModuleNotFound`, `PathNotFound`, `ConfigKeyNotFound` |
| `Failed` | `NetworkError`, `RateLimited`, `RemoteDataError`, `DownloadVerificationError`, `ModuleBuildError`, `StoreLocked`, `FileOperationError`, `ToolStartError`, `InternalError` |
| `UsageError` | `AmbiguousVersion`, `InvalidName`, `ConflictingOptions` |

27 named subclasses. Each is an empty class under its family; none sets `exit_code` itself.

`src/tlaup/paths.py`, copied from [14 F2](../design/14-config-and-cli.md#f2-folder-overrides):

```python
@dataclass(frozen=True)
class AppPaths:
    config: Path; cache: Path; data: Path
    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppPaths"
    # derived, as properties:
    config_file; tools; pin; modules; runs; remote; java_cache
```

| Variable | Effect |
| --- | --- |
| `TLAUP_HOME` | `config = $TLAUP_HOME/config`, `cache = $TLAUP_HOME/cache`, `data = $TLAUP_HOME/data`. |
| `TLAUP_CONFIG_DIR`, `TLAUP_CACHE_DIR`, `TLAUP_DATA_DIR` | Each sets one folder and wins over `TLAUP_HOME`. |
| none | `platformdirs` with the name `tlaup`: `user_config_dir`, `user_cache_dir`, `user_data_dir`. |

The derived properties, from [00, where state lives](../design/00-overview.md#where-state-lives-first-wave) (F2 names them and 00 gives the paths):

| Property | Path | First used by |
| --- | --- | --- |
| `config_file` | `<config>/config.yaml` | package 19 |
| `tools` | `<cache>/tool` | package 23 |
| `pin` | `<cache>/tool/pin` | package 23 |
| `modules` | `<cache>/module` | package 30 |
| `runs` | `<cache>/runs` | package 35 |
| `remote` | `<cache>/remote` | package 25 |
| `java_cache` | `<cache>/java.json` | package 20's callers |

`src/tlaup/context.py`, from [00](../design/00-overview.md#application-context), with the fields that can exist before packages 16 and 19:

```python
@dataclass(frozen=True)
class AppContext:
    paths: AppPaths
    env: Mapping[str, str]
    debug: bool
    # ui: Ui              added by package 16 (14 F6)
    # settings: Settings  added by package 19 (14 F1); loaded on first use, not at start

def get_context() -> AppContext     # built once per process, from os.environ on first call
def reset() -> None                 # forgets the cached context; for tests (01 T2)
```

Consumes: nothing from other packages.

## Tests that must pass

Plain pytest, new:

- `tests/unit/test_errors.py`
  - The test G2 and [02 X1](../design/02-cross-cutting.md#x1-exit-codes) name: collect every subclass of `TlaupError`, at any depth, and assert that its `exit_code` is one of 2, 3, 4, 5 and equals its family's.
  - Every name in the table above exists and is a subclass of the family in its row (the table is written out in the test, so a class moved to another family fails).
  - An error keeps its message, hint and details; `str()` gives the message.
- `tests/unit/test_paths.py`, the cases of F2 (with the fallback case below, the test of [preserved-behaviour row](../design/preserved-behaviour-2026-11-22.md) C1, which this package owns):
  - `TLAUP_HOME` alone; each of the three folder variables alone; each of them together with `TLAUP_HOME` (the single one wins for its folder, the other two follow `TLAUP_HOME`).
  - A relative value in any of the four is `ConfigInvalid`.
  - A value starting with `~` is expanded.
  - The fallback (row C1): with none of the four set, the three folders are what `platformdirs` gives for the name `tlaup`, `config_file` is `config.yaml` in the first, and `tools` and `modules` lie in the second. On Linux the test sets `XDG_CONFIG_HOME`, `XDG_CACHE_HOME` and `XDG_DATA_HOME` to folders under `tmp_path` with `monkeypatch.setenv` and asserts the folders lie there.
  - The seven derived properties have the paths of the table.
  - `from_env` and the properties create nothing on disk.
- `tests/unit/test_context.py`
  - `get_context()` returns the same object twice; after `reset()` and a changed environment it returns a new one with the new folders.
  - The old code follows the variables: with `TLAUP_HOME` set and the context reset, `tlaup.config.loader.config_dir()` is `$TLAUP_HOME/config`, `cache_dir()` is `$TLAUP_HOME/cache`, and `tlaup.versioning.paths.get_tools_dir()` is `$TLAUP_HOME/cache/tools` (the old name, on purpose; see Context). Each of these assertions goes in the pull request that deletes its function: [44](44-config-commands.md) the `config_dir` one (it deletes `config_dir()` with its only caller, `config_path()`), [39](39-tlc-command.md) the `cache_dir` one (it deletes `cache_dir()` with the last of `versioning/paths.py`, its last caller once 04 has removed the legacy fallbacks), [29](29-tool-commands.md) `get_tools_dir` (finding F2 of the [second review](review-2026-11-24.md); [19](19-layered-config.md) leaves both loader functions in place).

These tests set the environment with `monkeypatch.setenv` and call `tlaup.context.reset()` before and after themselves, because the autouse isolation fixture does not exist yet (package [03](03-test-foundation.md)). Under the fixture the extra calls are harmless, and they stay.

Old tests: `test_config_paths` in `tests/unit/test_config.py` is deleted, as said under Files. Every other old test must pass unchanged until 03b deletes the old suite; they replace `tlaup.config.loader.config_dir` and `cache_dir` by name, and both names still exist.

No feature file: the step vocabulary and the error handler do not exist yet. G2's `errors.feature` scenarios ("one scenario per subclass that a command can reach") are written by packages 17 and 18 for what exists then, and by each switch package for the errors its commands can reach.

No stateful test applies.

## Changelog

Under `## [Unreleased]`, heading Added, word for word from [14 F2](../design/14-config-and-cli.md#f2-folder-overrides):

- "`TLAUP_HOME` moves all of tlaup's folders; `TLAUP_CONFIG_DIR`, `TLAUP_CACHE_DIR` and `TLAUP_DATA_DIR` move one each."

G2 has no entry of its own ("With 02 X1"): the exit-code entry describes what a user sees once the handler and the commands use the classes, and is written by package 17 and the switch packages.

## Context for the worker

Decisions this rests on:

- D25: one variable moves all of tlaup's folders and one each moves a single folder, so tests and CI redirect all state without patching.
- D29 ([02 X1](../design/02-cross-cutting.md#x1-exit-codes)): tlaup's own errors are 2 (usage), 3 (not set up), 4 (not found), 5 (failed) and never 1. The class attribute is the whole mapping.
- D47: the folders of the new store and the new module registry are `tool/` and `module/`, singular like the command groups.
- D14: no migration and no shim for old folders or names.
- D10: nothing is written until the user changes a setting. `AppPaths` computes paths; it creates no folder and no file.
- D15: `pathlib` throughout; no `:` in a folder name.

**What this package rewires in the old code, and what the old code reads afterwards.** Only the two functions that ask `platformdirs`: `config_dir()` and `cache_dir()` in `config/loader.py`. Everything else in the old code is built on those two, so after this package:

| The old code reads and writes | Where |
| --- | --- |
| The config file | `<config>/config.yaml`, the same file as `AppPaths.config_file` |
| Installed jars | `<cache>/tools/<name>-<sha7>/`, with `meta-tla2tools.json` |
| The pin | `<cache>/tools/tools-pinned-version.txt` |
| Modules | `<cache>/modules/<name>/` |
| The run cache | `<cache>/run/tlc/` |
| The release list cache | `<cache>/github_cache_<asset>.json` |

with `<config>` and `<cache>` now taken from `AppPaths`, so the four variables move them. With no variable set the two roots are the same folders as in 0.8.2.

The old sub-folder names stay because the code that uses them is the old code: `AppPaths.tools`, `pin`, `modules`, `runs` and `remote` name the **new** layout of D47 and of [00](../design/00-overview.md#where-state-lives-first-wave), and nothing reads them until packages 20, 23, 25, 30 and 35 build the code that owns them. Do not point the old path functions at the new properties, for two reasons. The old install layout (`<name>-<sha7>` folders with `meta-tla2tools.json`) must never land in the folder the new store owns, where it would be a folder the store cannot read and never removes ([12 V1](../design/12-tools-and-downloads.md#v1-version-store)). And each old name disappears with its module: the switch packages delete `versioning/paths.py` piece by piece (package 04 the legacy pieces, 29 the tools and pin functions, 31 the modules function, 39 the run-cache functions), and package 19 replaces the loader but leaves its path helpers to their last callers (`config_dir()` and `config_path()` to 44, `cache_dir()` to 39). F2's sentence "`AppPaths` is the only place that knows any folder" is true for the roots after this package and for every folder after the last of those.

So for a while two names exist for "where builds are": `<cache>/tools` (old code) and `AppPaths.tools`, which is `<cache>/tool` (new code). A test of old code that needs the old folder writes `paths.cache / "tools"`, never `paths.tools`.

**Rules of `from_env` a worker could miss.**

- A value must be an absolute path or start with `~`; a relative path raises `ConfigInvalid`. The message names the variable.
- The design does not say what an empty value means. By the rule as written it is not an absolute path, so it is `ConfigInvalid`. Keep to that, pin it with a test, and say so in the pull request.
- `from_env` takes the environment as an argument, but `platformdirs` reads the process environment itself (`XDG_*` on Linux) and `Path.expanduser` reads `HOME`. That is fine: production passes `os.environ`. A test of the fallback therefore sets the variables with `monkeypatch.setenv`, not in a dictionary of its own.
- On macOS and Windows `platformdirs` does not follow `XDG_*`. The fallback test asserts "equal to what `platformdirs` returns for `tlaup`" everywhere and "under the `XDG_*` folders" on Linux only. Nobody has checked the fallback on macOS; CI's macOS job (package 53) is the first run there.
- The data folder is unused in the first wave. It exists so that one variable moves everything now and after milestone 3 moves tools and modules there.

**The context skeleton.**

- `get_context()` builds the context on its first call from `os.environ` and keeps it; `reset()` forgets it. It is the only process-wide cache the design allows ([01 T2](../design/01-testing.md#t2-isolation)).
- The old loader has a second one today: `load_config` is wrapped in `lru_cache`. `reset()` leaves it alone: it mattered only for old tests run under the isolation fixture, and 03b deletes the old tests in the pull request that brings the fixture in (decision D62). Package 19 replaces the loader and its cache. The context module must stay cheap to import ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)), so it imports nothing of the old code.
- `debug` is true when `TLAUP_DEBUG` is `1`, the one form [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks) names. How `--debug` reaches the context is package 17's: the design says the root callback builds the context "from the environment and the root options" and gives `get_context()` no parameter for them, so 17 adds the builder. Note that F10's handler does not read the flag from the context at all.
- Only commands reach for the context; domain functions take the paths they need as arguments ([00](../design/00-overview.md#packages-after-the-first-wave)). The two old loader functions are the one exception, and they go with the old loader.
- Nothing stores the context on Typer's context object yet; that is the root callback of package 17.

**Errors.**

- `message` is one line with no trailing full stop and no "Error:" prefix; `hint` is one line that names the next command; `details` is optional longer text. Nothing enforces this in the class; it is the rule for everyone who raises one.
- Text that must follow an error whatever its class is attached with `add_note` (Python 3.11 and later). It is not a field of `TlaupError`, and nothing in this package uses it.
- Signal exits (129, 130, 141, 143) are not errors and get no class.
- Nothing raises these classes yet except `AppPaths.from_env` (`ConfigInvalid`). Until package 17 the old command line has no handler for them, so `TLAUP_HOME=relative/path tlaup ...` ends in a traceback. That is the accepted state between packages; do not add a handler here.
- The old `tlaup/ui.py` has a function called `error`. It is unrelated, and package 16 replaces the module.
- `ModuleNotFound` is tlaup's "no such registered module"; do not confuse it with Python's `ModuleNotFoundError`.

State of `main` when this starts: release 0.8.x code, formatted by package 01. `tests/conftest.py` still has `mock_cache`, `mock_load_config` and the other old fixtures, and the old tests still write to the developer's real config folder where they do not use `mock_cache`; 03b ends that by deleting them.

## Done when

- The three modules exist with the interfaces above; `mypy` in strict mode passes on them.
- The new tests pass; every old test except `test_config_paths` passes unchanged.
- No file under `src/` other than `paths.py` imports `platformdirs`.
- `TLAUP_HOME=<tmp>/x uv run tlaup tools dir` prints a folder under `<tmp>/x/cache` (tried by hand once and said in the pull request).
- The changelog entry is written and the two sections of the development guide are updated.
- The pull request names inventory row C1 and its test (the fallback case of `test_paths.py`).
- `uv run poe lint`, `uv run ruff format --check .` and `uv run poe test` pass; CI is green.

## Out of scope

- The isolation fixture that sets `TLAUP_HOME` for every test, and the port of the old tests: package [03](03-test-foundation.md).
- `Ui` and the `ui` field: package 16. The error handler, `--debug`, `__main__.py`: package 17. Settings and the `settings` field: package 19.
- Removing the old path functions and their modules: packages 04, 19, 29, 31, 39. Between packages the old commands are not promised to keep working (decision D62); they keep working after this package because the rewiring changes two function bodies and nothing else.
- Moving the old code to the folder names of D47: never; the old code is deleted instead.
- Commands that print the folders in effect: packages 29, 31, 44, 45, 46.
- Raising the new errors from the old commands or changing any exit code.

## Risks

- From F2: none stated.
- From G2: catching too broadly. Only `TlaupError` is ever turned into a message; a bare `except Exception` elsewhere becomes a lint error when the BLE rules come on (package 58, its part 58a).
- From the cut: the old and the new folder names live side by side until the switch packages; the table above and the test in `test_context.py` are what keeps a worker from mixing them.
- From the cut: `get_context()` caches for the life of the process, and until 03b nothing resets it between tests. The old tests do not set the four variables, so they see the same folders as before; a new test that sets one must reset the context before and after itself.
- A developer who has `TLAUP_HOME` set in their shell now runs the old commands against that folder. That is the intended effect, and the changelog entry says so.
