# 33. The TLC invocation: preflight and command builder

Size: M. Suggested model: most capable. Status: ready.

## Goal

`resolve_tlc_invocation` turns a `TlcRequest` into a frozen `TlcInvocation` in the order of decision D45, having created and started nothing, and `build_tlc_command` turns that into a `JavaInvocation` as a pure function. Both are unit-tested; no command calls them yet, so `tlaup tlc` still runs through the old runner.

## Covers

- Roadmap items:
  - "A single TLC invocation value (spec, cfg, project root, working folder, jar, run folder, flags) resolved once per run and shared by the show-command, raw and formatted paths ... Building the command from it is a pure function and the only place flags are assembled." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)). In part: the value, the preflight and the builder. "One process loop instead of two copies" and the typed SANY errors are [37](37-run-tlc.md); the command that shares the value between the three paths is [39](39-tlc-command.md).
  - "One preflight used by every `tlaup tlc` path, checking jar, Java, spec and cfg in that order ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)). In part: the function, in the order of D45 (spec, cfg, tool build, Java; a departure the design README lists). The feature file that shows every path uses it is [39](39-tlc-command.md).
  - "Pass everything after `--` to TLC. Add `--workers`, defaulting to `auto`, as the only first-class TLC option (decision D24)." In part: the rules. The option declarations and the scenarios are [39](39-tlc-command.md).
  - "Java options: a `TLAUP_`-prefixed variable and a repeatable flag, both adding to the configured options instead of replacing them; quoted values split correctly; `JAVA_OPTS` is no longer read (decision D20)." In part: how the three sources combine, for `tlc`. The flag on `tlc` and the removal of what reads `JAVA_OPTS` today are [39](39-tlc-command.md); the flag on `sany`, `pcal` and `repl` is [41](41-sany-command.md) to [43](43-repl-command.md).
- Design sections:
  - [20 G1](../design/20-groundwork.md#g1-tlc-invocation): `TlcRequest`, `TlcInvocation`, `resolve_tlc_invocation`, `build_tlc_command` and the builder's unit tests. The short command function and `print_run_notes` are [39](39-tlc-command.md).
  - [11 R11](../design/11-runner.md#r11-preflight): the function and its order. `tlc_errors.feature` is [39](39-tlc-command.md).
  - [11 R8](../design/11-runner.md#r8-passthrough-and-workers): the table and its unit test. The feature scenarios and the integration test are [39](39-tlc-command.md) and [52](52-integration-tests.md).
  - [13 J1](../design/13-modules-and-java.md#j1-java-options): the order of the three sources and the unit test.
  - [11 R4](../design/11-runner.md#r4-spec-cfg-and-working-folder), steps 1, 2 and 6: the spec is passed as an absolute path, no working folder is set, and nothing is checked without `--cfg`. Steps 3 to 5 are [32](32-spec-resolution.md).
  - [11 R3](../design/11-runner.md#r3-non-utf-8-output), one sentence: the preflight's warning for a spec or cfg path with a character outside ASCII under a locale that is not UTF-8, with its unit test. The rest of R3 is the launcher's ([21](21-java-launcher.md)) and the runner's ([37](37-run-tlc.md)). The draft cut had all of R3 in 37; the warning is produced here, because `TlcInvocation.warnings` is.
  - [11 R6](../design/11-runner.md#r6-run-folders), the values the preflight decides: `run_id`, `metadir`, `keep`, `fp`, `seed`, `suppress_te_spec` ("Keeping is asked for at the start", "The fingerprint and the seed", "Trace specs (D36)"). Everything that creates, locks, settles or sweeps is [35](35-run-folders.md).
  - [11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load): only the place where the builder puts the overrides property. Collecting and checking the classes is [34](34-override-check.md), which adds its call to the preflight.

## Depends on

- [02](02-errors-and-paths.md): `UsageError`, `ConflictingOptions` and the errors the called functions raise; `AppPaths` (`paths.runs`, `paths.java_cache`).
- [03](03-test-foundation.md): the isolation fixture, the fake `java` on `PATH` (the preflight's Java step runs `java -version` against it), `assert_matches` and `--update-expected` ([01 T8](../design/01-testing.md#t8-expected-output-files)).
- [19](19-layered-config.md): `Settings` with `java.opts`, `java.min_version`, `tlc.workers`, `tlc.keep`, `module_path`, `module_lib_path`.
- [20](20-java-location.md): `require_java` and `JavaRuntime` ([13 J2](../design/13-modules-and-java.md#j2-finding-java)).
- [21](21-java-launcher.md): `JavaInvocation` ([20 G3](../design/20-groundwork.md#g3-java-launcher)). Only the dataclass and `argv()`; nothing is started here.
- [23](23-tool-store.md): `Build` with `jar` and `capabilities` ([12 V1](../design/12-tools-and-downloads.md#v1-version-store)). Not `ensure_tools` ([28](28-first-run.md)): the build arrives through the injected `get_build`.
- [30](30-module-build.md): `ClasspathResolver` as that package leaves it, with its `module_dirs` parameter, and the modules `Registry`, whose `list()` gives the registered modules in name order ([13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder)); and the classpath test file 30 writes, which this package extends.
- [32](32-spec-resolution.md): `resolve_spec`, `resolve_cfg`, `config_arg`, `find_project_root`.

Change from the draft: 02 and 03 are named (the draft had them through 32). The rest is the draft's list. No change from the stage 4 review: the classpath test file is 30's now (decision D62), which 30 already gives.

## Files

Creates:

- `src/tlaup/tlc/invocation.py`: `TlcRequest`, `TlcInvocation`, `resolve_tlc_invocation`, the passthrough table, `new_run_id`, `RecoveredRun`, `find_recovered_run`.
- `src/tlaup/tlc/command.py`: `build_tlc_command`, and the main class name `tlc2.TLC` as one constant until [41](41-sany-command.md) creates `tlaup.tools.ENTRY_POINTS` and replaces it ([21 S4](../design/21-other-tools.md#s4-keeping-them-thin)).
- `src/tlaup/java/opts.py`: `jvm_options` (J1). A file 00's tree does not list; it sits under `java/` so that `tools/` ([41](41-sany-command.md)) can import it without importing `tlc/`.
- `tests/unit/tlc/test_invocation.py`, `tests/unit/tlc/test_command.py`, `tests/unit/tlc/expected/command/*.txt`, `tests/unit/java/test_opts.py`.

Changes:

- `src/tlaup/java/classpath.py`, only as far as the preflight needs paths back: the runtime classpath as `list[Path]` and the TLA-Library folders as a list, not a joined string, in the order [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder) writes out under "The classpath of a run" (below). Added beside the existing methods, not in their place: the old runner joins `resolver.resolve(...)` with `os.pathsep` and uses `get_tla_library_property()` as a string, and it has to type-check until [39](39-tlc-command.md) deletes it, so the string-returning methods stay and 39 deletes them with it.
- `tests/unit/java/test_classpath.py`, the new file [30](30-module-build.md) writes with its whole-list test (the old file of that name went with the old suite in [03](03-test-foundation.md), decision D62): 30's whole-list test adapted to the path-returning methods, and C6's case added (see Tests). No second whole-list test.

Deletes: nothing. The old classpath tests (`tests/unit/java/test_classpath.py`, `tests/unit/spec/test_classpath.py`, `tests/unit/test_tlc_modules_path.py`) are gone already (D62).

Does not touch (which is why the old string-returning methods of `classpath.py` stay): `src/tlaup/tlc/runner.py` (the old `build_tlc_command`, `resolve_spec_file`, `get_override_classes`), `src/tlaup/cmd/tlc.py`, `src/tlaup/config/schema.py`. The old and the new `build_tlc_command` live in different modules until [39](39-tlc-command.md).

Files another package also touches: `src/tlaup/java/classpath.py` with [30](30-module-build.md) (a dependency, so no conflict) and perhaps [31](31-module-commands.md); `src/tlaup/tlc/invocation.py` is edited next by [34](34-override-check.md) (a few lines at one marked place) and read by [35](35-run-folders.md).

## Interfaces

Provides. Copied from [20 G1](../design/20-groundwork.md#g1-tlc-invocation); what stage 4 added is marked.

```python
# tlaup/tlc/invocation.py
@dataclass(frozen=True)
class TlcRequest:                     # what the user typed, nothing looked up
    spec: str
    cfg: str | None = None
    workers: str | None = None        # "auto" or a positive integer, as text; None = take the setting
    coverage: bool = False
    raw: bool = False
    keep: bool | None = None          # --keep; None = take the setting tlc.keep (11 R6, D53)
    java_opts: tuple[str, ...] = ()
    extra_args: tuple[str, ...] = ()  # TLC's own arguments (11 R8)

@dataclass(frozen=True)
class TlcInvocation:                  # everything decided; no run folder created, nothing started
    request: TlcRequest               # kept whole: the resume command is built from it (11 R6)
    build: Build
    java: JavaRuntime
    spec: Path                        # absolute, exists, ends in .tla; symbolic links not resolved
    cfg: Path | None                  # absolute, exists; None = --cfg was not given
    config_arg: str | None            # what -config is given (11 R4, step 4)
    project_root: Path | None
    cwd: Path                         # where tlaup was started (D34)
    classpath: tuple[Path, ...]
    tla_library: tuple[Path, ...]
    override_classes: tuple[str, ...] # empty until package 34 fills it
    warnings: tuple[str, ...]
    jvm_options: tuple[str, ...]      # settings, then TLAUP_JAVA_OPTS, then --java-opt
    workers: str | None               # None = pass no -workers
    coverage: bool
    tool_mode: bool                   # not raw
    suppress_te_spec: bool
    keep: bool
    fp: int | None                    # what tlaup passes as -fp; None = the user passed one
    seed: int | None                  # the same for -seed
    extra_args: tuple[str, ...]
    run_id: str                       # the run folder is paths.runs / run_id
    metadir: Path | None              # None when the user passed -metadir

def resolve_tlc_invocation(request: TlcRequest, *, paths: AppPaths, settings: Settings,
                           env: Mapping[str, str], cwd: Path, home: Path,
                           get_build: Callable[[], Build],
                           now: Callable[[], datetime], rng: random.Random) -> TlcInvocation
    # the preflight (11 R11); raises TlaupError.
    # `home`, `now` and `rng` are written by stage 4: G1's signature has none of them, and the function needs
    # the home folder for R10, the clock for the run id, and a random source for the run id, -fp and -seed.

def new_run_id(now: Callable[[], datetime], rng: random.Random) -> str      # written by stage 4
    # "20261115T100000Z-3fa9c1d2": the UTC start time and eight random hex digits (11 R6)

@dataclass(frozen=True)
class RecoveredRun:                   # written by stage 4; the run folder a -recover PATH points into
    run_id: str
    folder: Path                      # paths.runs / run_id
    keep: bool                        # its run.json says "keep": true or "kept": true
    fp: int | None                    # from its run.json, when it has them
    seed: int | None

def find_recovered_run(extra_args: Sequence[str], cwd: Path, runs: Path) -> RecoveredRun | None   # written by stage 4

# tlaup/tlc/command.py
def build_tlc_command(inv: TlcInvocation) -> JavaInvocation      # pure: reads no disk and no environment

# tlaup/java/opts.py
def jvm_options(setting: Sequence[str], env: Mapping[str, str], flags: Sequence[str]) -> tuple[str, ...]
    # written by stage 4 from 13 J1; raises UsageError naming TLAUP_JAVA_OPTS for an unbalanced quote
```

**The order of the preflight** ([R11](../design/11-runner.md#r11-preflight), decision D45). Each step raises the error named and stops.

| Step | What | Failure |
| --- | --- | --- |
| 0 | What needs only the command line and the environment: the table below; the value of `request.workers`; `jvm_options` | `ConflictingOptions` or `UsageError`, code 2 |
| 1 | `resolve_spec(request.spec, cwd)` | `SpecNotFound` (4) or `UsageError` (2) |
| 1b | `find_project_root(spec, home)` | cannot fail |
| 2 | With `request.cfg`: `resolve_cfg(...)`, then `config_arg(cfg, spec)`. Without: nothing is checked | `CfgNotFound` (4) |
| 3 | `get_build()` | whatever it raises: `NoToolsInstalled`, `NoPinnedBuild`, `PinnedBuildMissing`, `CannotAsk` (3), or an install's error |
| 4 | `require_java(env, min_version=settings.java.min_version, cache_file=paths.java_cache)` | `JavaNotFound`, `JavaTooOld` (3), `Failed` (5) |
| after | The classpath and TLA-Library folders; the override collection and check (34); the path warning of R3; `workers`; the values that depend on the build (`suppress_te_spec`) or are chosen per run (`run_id`, `metadir`, `keep`, `fp`, `seed`) | nothing here can fail for a reason the user caused on the command line |

`get_build` is called at step 3 and not before: a missing spec or two conflicting options are reported with nothing installed and nothing asked.

**The table of R8**, the only place such rules live. Flags are found by exact match among `request.extra_args`.

| Among TLC's arguments | With the tlaup option | Without it |
| --- | --- | --- |
| `-workers` | `--workers` given: `ConflictingOptions` (2) | `TlcInvocation.workers` is `None`; the user's is used |
| `-coverage` | `--coverage` given: 2 | passed through |
| `-config` | `--cfg` given: 2 | passed through; not validated |
| `-metadir` | n/a | `metadir` is `None`; the user's is used |
| `-tool` | n/a | passed through |
| `-generateSpecTE`, `-noGenerateSpecTE`, `-teSpecOutDir` | n/a | `suppress_te_spec` is false |
| `-recover PATH` | n/a | passed through; see `find_recovered_run` |
| `-difftrace` | n/a | passed through |
| `-fp`, `-seed` | n/a | the user's are used; tlaup passes the one that is missing |

**`workers`.** `request.workers`, when given, must be `auto` or a positive integer written in digits: `0`, `x`, `+3`, `AUTO` and a value with spaces are `UsageError`, although TLC itself would take the last three. Otherwise the value is the setting `tlc.workers`, as text. `-workers auto` is passed unchanged on both builds.

**`jvm_options`** ([J1](../design/13-modules-and-java.md#j1-java-options)): the setting `java.opts`; then `TLAUP_JAVA_OPTS` split with `shlex.split`, so `-Dname="a b"` is one option; then each `--java-opt` as given. Nothing is de-duplicated. `JAVA_OPTS` is not read.

**The per-run values.**

- `run_id`: `new_run_id(now, rng)`. `metadir`: `paths.runs / run_id`, or `None` with `-metadir` among TLC's arguments. Neither the folder nor its lock is made here.
- `keep`: `request.keep` when it is not `None`, else the setting `tlc.keep` (which already carries `TLAUP_TLC_KEEP`); and true whatever those say when `find_recovered_run` returns a run whose `keep` is true.
- `fp` and `seed`, each decided on its own: `None` when TLC's arguments hold the flag; else the recovered run's recorded value when there is one; else random, `-fp` from 0 to 130 inclusive and `-seed` a random integer (see "Traps" for its range).
- `suppress_te_spec`: the build has the capability `no_generate_spec_te` and TLC's arguments hold none of the three trace-spec flags.

**`find_recovered_run`** ([R6](../design/11-runner.md#r6-run-folders), "`-recover PATH` among TLC's arguments"). The word after `-recover`; a relative `PATH` is read against `cwd`, as TLC reads it; links are resolved as far as the path exists; when the result lies under `runs/<id>/` and that run folder exists, the function returns that run with what its `run.json` says, whether or not `PATH` itself exists (a `-recover <runs>/<id>/states` whose `states/` is missing still names the run, question Q9 as settled); and `None` otherwise (a path outside `runs/`, or under a `runs/<id>/` that has no folder). A `run.json` that is missing or cannot be read gives `keep=False` and no values; the run is still returned, because [35](35-run-folders.md) takes its lock whatever the file says. The function reads only; it takes no lock.

**The classpath of a run** ([13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder), "The classpath of a run"; inventory rows S10 to S12). The preflight builds the resolver with `module_dirs=[m.path for m in Registry(paths.modules).list()]`, so the registered modules come in name order, and takes the lists back from the new path-returning methods. The order, most specific layer first (command line, project, config, registered modules; the command-line layer is empty in the first wave and is kept first in steps 2 and 5 for when a command passes folders):

1. the project's `classes/`, ahead of the tools jar, so that its classes win over the jar's;
2. the folders of TLA+ modules: the project's `modules/`, the folder `module_path` names, then each registered module's `modules/`;
3. each registered module's `classes/`;
4. the build's `tla2tools.jar`;
5. the jars directly in the project's `lib/`, in the folder `module_lib_path` names, and in each registered module's `lib/`, in that order, each folder's `*.jar` sorted by name.

An entry that appears twice, compared as an absolute path, keeps its first place only. `tla_library` holds the folders of step 2 in the same order. A relative `module_path` or `module_lib_path` is read against `cwd`, as 0.8.x reads it against the working folder (inventory row C6; [14 F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay) now writes the rule down).

**The argument order `build_tlc_command` produces**, and the only place it is written (G1):

```
<java> [-javaagent:<lifeline jar>=pid=<tlaup's pid>] -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8
       -Dstderr.encoding=UTF-8 <jvm options> -DTLA-Library=<dirs> [-Dtlc2.overrides.TLCOverrides=<classes>]
       -cp <classpath> tlc2.TLC
       [-tool] [-metadir <dir>] [-noGenerateSpecTE] [-workers <w>] [-coverage 1] [-fp <n>] [-seed <n>]
       [-config <cfg>] <extra args> <absolute spec>
```

The lifeline and the three encoding options are added by `JavaInvocation.argv()` ([21](21-java-launcher.md)), not by the builder. The builder fills `java` (the runtime's path), `jvm_options`, `system_properties`, `classpath`, `main_class`, `args`, leaves `cwd` as `None` (D34) and `lifeline` at its default. A system property is left out when its list is empty. `-DTLA-Library` is joined with `os.pathsep`; the override class names are joined with `os.pathsep` too, as today's code does (`tlc/runner.py`, `build_tlc_command`).

Consumes: `resolve_spec`, `resolve_cfg`, `config_arg`, `find_project_root` (32); `require_java`, `JavaRuntime` (20); `Build` (23); `JavaInvocation` (21); `Settings` (19); `AppPaths` and the errors (02); `ClasspathResolver` and `Registry` (30).

## Tests that must pass

Plain pytest. The builder's tests need no fixture; the preflight's use real files in `tmp_path`, a hand-made `Build`, the fake `java` of the isolation fixture for step 4, a fixed `now` and a seeded `random.Random`.

`tests/unit/tlc/test_command.py` (G1): `build_tlc_command` on hand-built `TlcInvocation` values, compared with expected files under `tests/unit/tlc/expected/command/`, one per combination that changes the output:

- the plain parsed run; `raw` (no `-tool`); `coverage` (`-coverage 1` before the spec, not after it); a cfg (`-config` with the relative value); `workers` present and absent; override classes (the property is there, and absent with an empty tuple); an extra `-metadir` among TLC's arguments (no `-metadir` of tlaup's); `suppress_te_spec`; `fp` and `seed` present, and only `seed`; an empty TLA-Library list (no property); extra arguments placed before the spec, unchanged.
- The expected file holds `replace(java_inv, lifeline=False).argv()`, one argument per line, so it does not depend on a process id. Paths in the hand-built values are invented absolute paths; nothing is read.
- A test that the function reads nothing: it is called with paths that do not exist.

`tests/unit/tlc/test_invocation.py`:

- R8: the table, row by row: each conflict raises `ConflictingOptions`; each "without" cell gives the field value named above.
- `workers`: `auto`, `4`, the setting when the request has none; `0`, `x`, `+3`, `AUTO` raise `UsageError`.
- The order. With a `get_build` that fails the test when called: a missing spec raises `SpecNotFound`; two conflicting options raise `ConflictingOptions` although the spec is also missing; a `--cfg` that does not exist raises `CfgNotFound`. With a `get_build` that raises `NoPinnedBuild` and the fake `java` on `PATH`: `NoPinnedBuild` comes out, and the fake `java`'s log is empty (step 4 was not reached). These are stage 4's unit forms of R11's order; the design's own tests of the order are the scenarios of `tlc_errors.feature` in [39](39-tlc-command.md).
- R4: the spec in the invocation is absolute; `config_arg` is the value of [32](32-spec-resolution.md) for a cfg outside the project with a decoy of the same name in the project root; with no `--cfg`, `cfg` and `config_arg` are `None` and a missing default `Spec.cfg` raises nothing.
- R3: a spec path with `é` and an environment that says `LC_ALL=C` gives the warning; the same with `C.UTF-8` gives none; a cfg path with `é` likewise.
- The per-run values: with a seeded `rng` and a fixed `now`, `run_id` has the form `20261115T100000Z-` plus eight hex digits and `metadir` is `paths.runs / run_id`; nothing exists under `paths.runs` afterwards; `fp` is in 0 to 130 and `seed` is set when TLC's arguments have neither; with `-fp 3` among them `fp` is `None` and `seed` is set; `-metadir X` gives `metadir=None`.
- `keep`: the request wins over the setting; the setting is used when the request has none.
- `find_recovered_run` and its use: a run folder written by the test under `paths.runs` with a `run.json` holding `"keep": true`, `"fp": 58`, `"seed": 7`; `-recover <a folder inside it>` gives `keep=True`, `fp=58` and `seed=7`, also with `request.keep=False`; a `run.json` with `"kept": true` and `"keep": false` counts as keep (review finding FC1); a relative `PATH` is read against `cwd`; a `PATH` through a link into the run folder is found; `-recover <that folder>/states` where `states/` does not exist still gives the run (Q9); a `PATH` outside `runs/`, one that does not exist outside `runs/`, and `<runs>/<an id with no folder>/states` give `None` and fresh random values; an unreadable `run.json` gives `keep=False`.
- `suppress_te_spec`: true for a build with the capability, false without it, false with each of the three flags.
- The warnings of `require_java` (a `JAVA_HOME` that holds no `java`, built with a fake JDK folder) are in `TlcInvocation.warnings`.
- The classpath through the preflight: with two modules registered under `paths.modules` in the reverse of their name order, `classpath` and `tla_library` follow `Registry.list()`'s name order. With `module_path` set to a relative folder, `classpath` and `tla_library` hold its absolute path under `cwd`, and the built command (`build_tlc_command`) has it in `-cp` and in `-DTLA-Library` (inventory row C6, whose owner this package is; written as a unit test on the preflight and the builder, since no command calls them until [39](39-tlc-command.md)).

`tests/unit/java/test_opts.py` (J1): the three sources combine in order; `-Dx="a b"` in the variable is one option; an unbalanced quote raises `UsageError` naming `TLAUP_JAVA_OPTS`; `JAVA_OPTS` in the environment changes nothing.

`tests/unit/java/test_classpath.py`, extended (M2's unit test of `ClasspathResolver`; inventory row S11, whose owner this package is, and rows S10 and S12, whose order test is this one). [30](30-module-build.md) wrote the file with the one whole-list test of the runtime order (a project with `classes/`, `modules/` and two jars in `lib/`, `module_path` and `module_lib_path` set, two registered modules in the reverse of their name order, a tool jar; one expected list written out in the test). This package adapts that test to the path-returning methods it adds (the expected list as `list[Path]`, the TLA-Library folders as a list, still entry for entry and each jar once in its first place) and writes no second whole-list test. It adds C6's case on the resolver: a relative `module_path` and `module_lib_path` are read against `cwd`, and appear as absolute paths in both lists. The preflight as the resolver's caller is tested above (the name order of the registered modules, C6 through `build_tlc_command`). An empty TLA-Library list leaves the property out (G1's builder test above).

Old tests: none. The old suite went in [03](03-test-foundation.md) (D62); `test_opts.py` is J1's test. No stateful test applies.

## Changelog

None. No command reaches this code. The entries that describe it are written by [39](39-tlc-command.md): R11's Fixed, R8's two Added and one Breaking, J1's Breaking and Added, R4's and R3's.

## Context for the worker

**State of `main` when this starts.** `tlaup tlc` still runs through `src/tlaup/tlc/runner.py` and `src/tlaup/cmd/tlc.py`. Beside them exist: `tlaup/errors.py`, `tlaup/paths.py`, the new settings loader, `java/locate.py`, `java/launcher.py`, `versioning/store.py`, `modules/registry.py`, `project/spec.py`. Nothing under `tlc/` is new yet except what this package adds, so `tlc/invocation.py` and `tlc/command.py` sit beside the old `runner.py`, which has an old function also named `build_tlc_command`. Import the new one from `tlaup.tlc.command` everywhere.

**Decisions this rests on.**

- D45: spec, cfg, tool build, Java. A mistyped spec is reported before any first-run prompt or download, and milestone 3 can pick the build from a project file found from the spec without moving a step.
- The design agent's decision that checks needing only the command line come first: a usage error does not wait behind a prompt.
- D24: `--workers` is the only first-class TLC option; only the flags in the table are looked at, by exact match, and the list is short on purpose.
- D34: no working folder is set; the spec is absolute.
- D52: tlaup draws `-fp` and `-seed` itself, so that it knows them in a raw run as well, and repeats them on a resume.
- D53: keeping is asked for at the start; a resume from a folder that asked, or was kept, is a kept run.
- D36: `-noGenerateSpecTE` on builds that have it. v1.7.4 rejects the flag, so it is decided from the stored capability, never from a version string ([00](../design/00-overview.md#what-a-build-can-do)).
- D20: `JAVA_OPTS` is not read.
- D51 and D56 are the launcher's: do not add the lifeline or the encoding options in the builder.

**What the preflight may touch.** It writes nothing in the run cache and nothing beside the spec. Two writes can happen through the functions it calls, both outside a run: the remembered Java version check (`<cache>/java.json`, inside `require_java`) and, on a first run, an installed build (inside `get_build`). It starts no JVM except `java -version` when that answer is not remembered. It prints nothing: warnings come back in `TlcInvocation.warnings`.

**The two packages around the run folder, and their order.** This package lands first and stubs nothing. It owns the three values a run folder is made from (`run_id`, `metadir`, `keep`) and the one piece of reading that the preflight needs from an old run folder, `find_recovered_run`. [35](35-run-folders.md) lands after it: `run_folder(inv, paths, now)` takes the invocation, and it reuses `find_recovered_run` to know which second lock to take, so the rule "is this path inside a run folder" is written once. The keys of `run.json` this function reads (`keep`, `kept`, `fp`, `seed`) are fixed by R6's text; 35 writes the file. If 35 would rather own the reading of `run.json`, it moves the function into `rundirs.py` and `invocation.py` imports it from there; the behaviour and the tests here stay.

**What [34](34-override-check.md) adds.** `override_classes` is `()` when this package is merged, and the preflight has one marked place, after the classpath is known, where 34 puts two calls. The builder already writes the property when the tuple is not empty, and its expected file proves it with a hand-built value. Do not port `get_override_classes` from the old runner.

**Points the design leaves open, and what is built** (stage 4's choices, listed in the index as readings and taken; each is internal or follows the design's words, so none is a user-visible decision of its own).

- *The locale of R3.* The design says the warning is given "while the locale tlaup runs under is not UTF-8" and that the test injects `LC_ALL=C`. Built so: the locale is taken from the `env` argument, the first of `LC_ALL`, `LC_CTYPE`, `LANG` that is set and not empty; it counts as UTF-8 when its value names UTF-8 in any spelling (`C.UTF-8`, `en_US.utf8`); with none set it is the C locale. On Windows these variables do not say what the JVM does and the warning is not given. The hint is `TLC cannot open a file whose name has non-ASCII characters under the C locale; run with LC_ALL=C.UTF-8`.
- *A warning with a hint.* `TlcInvocation.warnings` is a tuple of strings and `Ui.warning` takes one message ([14 F6](../design/14-config-and-cli.md#f6-messages)). R3 wants a hint with this one warning. The hint sentence is part of the warning's text.
- *`-recover` with one of `-fp` and `-seed` given.* R6 says the recorded values are passed "when the user gave neither", and R8 that each of the two is decided on its own. The rule above (each missing one comes from the recovered folder when it has it) is both at once when neither is given, and is what is built when one is.
- *`-recover` naming the run folder itself* (`runs/<id>`, not a folder inside it): TLC cannot resume from it. It still counts as under the run folder, so the lock is taken; TLC reports the rest.

**Traps.**

- *The range of `-seed`.* R6 says "a random 64-bit integer" and its example is below 2^63. From memory of TLC's source, not checked here, TLC reads `-seed` as a Java `long`, which is signed; a value of 2^63 or more would be refused. Draw from 0 to 2^63 - 1. The integration test of [52](52-integration-tests.md) is what proves the range on both builds; R6 names the same check for `-fp` on v1.7.4.
- *`-fp` is an index*, 0 to 130 inclusive: `tlc2.util.FP64.Polys` has 131 entries on the rolling build, and v1.7.4 is assumed the same.
- *The flags layer of the settings.* [14 F1](../design/14-config-and-cli.md#f1-layered-configuration) names `--workers` among the options a command may hand to the loader as an override. For `tlc` it must not go that way: the resume command of R6 has to know whether the worker count came from the command line or from the settings, and a bad `--workers` has to be a usage error (2), not an invalid setting (3). `--workers` and `--keep` travel in the request only; `settings` here is what the file and the environment gave.
- *Exact match.* `-workers=4` is not `-workers`; TLC does not take that form, and tlaup does not interpret it.
- *A repeated flag.* Which of two TLC honours was not checked, which is why a conflict is an error and not "last one wins".
- `-tool` among TLC's arguments is passed through as well as tlaup's own: two `-tool` in a parsed run are harmless and are not de-duplicated.
- `shlex.split` raises `ValueError` for an unbalanced quote; that is the one place it becomes `UsageError`.
- No `Path.cwd()`, `Path.home()`, `os.environ`, `datetime.now()` or module-level `random` inside these functions: every one is an argument, which is what lets the tests be exact (T12 rule 5).
- `build_tlc_command` must not call `Path.exists`, `resolve` or anything else that touches the disk. `config_arg` was computed by the preflight for exactly this reason.

**Known gaps the design postpones.** A per-run `-Djava.io.tmpdir` inside the run folder, for v1.7.4's shared temporary module copies ([J1](../design/13-modules-and-java.md#j1-java-options), "A known gap"): postponed by the maintainer; do not add it. A check of the newest class-file version under the project's `classes/` against the running Java: named as possible later in R7; not here.

## Done when

- The four test files pass; every expected file under `tests/unit/tlc/expected/command/` was read by the worker against the order above before it was committed (T8: an updated expected file is a change to review).
- `uv run poe lint` (mypy strict on `src`) and `uv run poe test` pass; CI is green.
- The old `tlaup tlc` still type-checks; nothing in it is changed.
- The pull request names every signature it adjusted, any choice listed under Context that it did not follow, and the inventory rows it covers (S10, S11, S12, C6).

## Out of scope

- `collect_override_classes`, `check_overrides` and the two calls in the preflight: [34](34-override-check.md).
- Creating, locking, settling and sweeping run folders; `run.json`; the resume command: [35](35-run-folders.md).
- `run_tlc`, `run_tlc_raw`, `RunOutcome`: [37](37-run-tlc.md).
- The command function, `--show-command`, the `get_build` wrappers round `ensure_tools`, `print_run_notes`, every feature file and changelog entry, deleting the old runner: [39](39-tlc-command.md).
- `resolve_tool_invocation` for `sany`, `pcal` and `repl`, and `ENTRY_POINTS`: [41](41-sany-command.md).
- The project file as one more input of the preflight: milestone 3.

## Risks

- From G1: the value has many fields; it is the price of deciding everything once.
- From R11: the spec is looked up before tlaup knows it can run anything, so a user with nothing installed and a mistyped spec fixes the spec first and meets the install prompt on the second try.
- From R8: several workers change the order of `Print` output and can change which counterexample is found first; that is TLC's behaviour.
- From J1: an option given twice is resolved by the JVM; a bad option makes the JVM exit 1 before TLC starts.
- From R6: that the original `-fp` and `-seed` make a resumed run's counts exact rests on one run on one build.
- From the cut: three parameters and three helper signatures are stage 4's, not the design's. The functions are called from two places only (39 and the tests), so a change of shape is cheap until 39 lands.
- From the cut: `ClasspathResolver` has no written signature in the design. This package takes it as [30](30-module-build.md) left it and changes only the types it returns; if 30 did not move it to the registry, that is 30's to finish, not this package's.
