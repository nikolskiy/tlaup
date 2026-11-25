# 30. The module build: registry, build in a temporary folder, class files

Size: M. Suggested model: most capable. Status: ready.

## Goal

`tlaup/modules/` exists beside the old code: `registry.py` (module names and the registry of `<cache>/module/`), `build.py` (`build_module`, which builds in `<cache>/module/.tmp/` and moves the result into place under a lock), and `classfile.py` (reading a class file's interfaces to find the override classes). `ClasspathResolver` can be given the module folders instead of walking the cache. No command reaches the new code yet: `tlaup modules add` and `tlaup tlc` behave exactly as before.

## Covers

- Roadmap items:
  - [Milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust), line 220: "Reject module names containing path separators or `..`, absolute paths, `.` and an empty name in `modules remove` and `modules add`; ..." In part: `validate_module_name`, `Registry.path_of` and their unit tests. The commands, the scenarios and the changelog are [31](31-module-commands.md).
  - Milestone 1, line 221: "`modules add` builds in a temporary folder and swaps it in only when compilation succeeds, so a `javac` error no longer destroys the working build; it says when it replaced a module of the same name (decision D23)." In part: the domain function and its unit tests; the command and what it prints are [31](31-module-commands.md).
  - Milestone 1, line 206 (recorded without a solution): "The module build strips `//` comments with a regex that corrupts string literals; `javac` runs with no `-encoding` and no timeout." In part: the class-file reader, the `javac` arguments and the timeout. The `javac` version check is [20](20-java-location.md); the scenarios are [31](31-module-commands.md).
  - [Milestone 5](../roadmap.md#milestone-5-structure), line 495: "Move the module build pipeline out of `cmd/modules/add.py` into a modules domain package that owns the managed-module layout and raises errors instead of printing; the classpath resolver asks it for folders instead of walking the cache." In part (a departure the design README lists: done in milestone 1). The old `cmd/modules/add.py` and the resolver's own walk go in [31](31-module-commands.md).
- Design sections:
  - [13 M1](../design/13-modules-and-java.md#m1-module-names): `validate_module_name`, `Registry.path_of`'s second check, the parametrised unit test. The `modules.feature` scenarios and the changelog are 31's.
  - [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder): `BuiltModule`, `build_module` (steps 1 to 7, with the narrow compile classpath of step 3, decision D61), `module.json`, the modules lock, the one-day cleanup of `.tmp/`, `Registry` (with its name order), the unit tests of `build_module`, and the whole-list unit test of "The classpath of a run" (written here, extended by [33](33-tlc-invocation.md)). What the command prints, the feature scenarios and the changelog are 31's. `BuiltModule.warnings` gets R7's warnings from [34](34-override-check.md); this package fills it with the `javac` lookup's warnings and the "no override class" note. "`ClasspathResolver` asks the registry for the module folders": the parameter is added here, the old walk is removed by 31.
  - [13 M3](../design/13-modules-and-java.md#m3-module-build-details): `ClassInfo`, `read_class`, finding override classes in the compiled output (superclasses followed), the service file rules, the `javac` arguments, the timeout, the output handling, and their unit tests. Not here: the bullet "`javac` has its own version check" (`require_javac` and its pattern), which is [20](20-java-location.md)'s; the feature scenarios, which are 31's.
  - [12 V10](../design/12-tools-and-downloads.md#v10-remove-old-layouts): nothing more; [04](04-delete-dead-code.md) removed the resolver's legacy lines.
  - The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md), rows whose owner this package is: M18 (registered modules in name order), and the first form of S11 (the runtime order, whose owner is 33) with M17 (every registered module takes part in a run). Also M5, a row changed on purpose by D61, whose new behaviour this package tests: the narrow compile classpath, its unit form here and its feature form with the command in [31](31-module-commands.md), as M2's Tests have it.

## Depends on

- [02](02-errors-and-paths.md): `InvalidName` (2), `PathNotFound` and `ModuleNotFound` (4), `ModuleBuildError`, `StoreLocked`, `FileOperationError` and `ToolStartError` (5) from `tlaup/errors.py`; `AppPaths.modules` (`<cache>/module`) for the tests.
- [03](03-test-foundation.md): the isolation fixture; the fake `javac` of `tests/fakes/` and its log; the class files in `tests/fakes/classes/` compiled from `tests/fakes/java-src/` ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)). What this package needs of the fake `javac` beyond T4's words is listed under Context.
- [20](20-java-location.md): the types `JavaRuntime` and `JavaTool` of `tlaup/java/locate.py`, which `get_javac` returns. Not `require_javac` itself: the command binds it ([31](31-module-commands.md)); the tests pass a function that returns a `JavaRuntime` for the fake `javac`.
- [23](23-tool-store.md): the type `Build` of `tlaup/versioning/store.py` ([12 V1](../design/12-tools-and-downloads.md#v1-version-store)), which `get_build` returns: `jar` for the classpath, `name` and `commit` for `built_against`. Nothing else of the store: not `ToolStore`, not its lock, not `TmpFolder`. The modules lock follows the store's pattern with a lock of its own. 23 also adds the `filelock` line to `pyproject.toml`, which the modules lock needs.

Change from the draft (02, 03, 20): 23 is added. V1 is in M2's "Depends on" for the `Build` type only; nothing in M2 uses the store's code or its lock, and the error classes `get_build` raises (`NoPinnedBuild`, `NoToolsInstalled`) are 02's.

## Files

Creates:

- `src/tlaup/modules/__init__.py` (empty, or a docstring), `registry.py`, `build.py`, `classfile.py`.
- `tests/unit/modules/__init__.py` if the test tree uses them, `test_registry.py`, `test_build.py`, `test_classfile.py`.
- `tests/unit/java/test_classpath.py`, new: the whole-list test of the runtime classpath (Tests). The old file of that name went in 03b with the rest of the old suite (decision D62); [33](33-tlc-invocation.md) extends this one.
- In `tests/fakes/java-src/` and `tests/fakes/classes/`: the sources and compiled class files of the shapes listed under Tests that package 03 did not already commit, with the README beside them updated (the compiler's version and the command). See "Class files" under Context.

Changes:

- `src/tlaup/java/classpath.py`: `ClasspathResolver.__init__` gets the keyword-only parameter `module_dirs` (below). With a sequence, the three places that walk `get_modules_dir()` today (`_resolve_paths` for `LIB` and `MODULES`, `resolve` for each module's `classes/`) iterate over it instead. With `None`, the default, they walk `<cache>/modules` exactly as now. Nothing else in the file changes: not the order, not the return types, not `ResolveMode`.

Deletes: nothing. The old `cmd/modules/add.py` with its `find_override_classes` stays until [31](31-module-commands.md).

Must not touch: `src/tlaup/cmd/`, `src/tlaup/tlc/`, `src/tlaup/versioning/paths.py`.

Shared with packages that may run beside this one: `src/tlaup/java/classpath.py` and `tests/unit/java/test_classpath.py` with [33](33-tlc-invocation.md) (which depends on this package, so it comes after) and [31](31-module-commands.md) (also after). `pyproject.toml` and the lock file only if [23](23-tool-store.md)'s `filelock` line is somehow not there; it is one line.

## Interfaces

Provides. Copied from [13 M1, M2, M3](../design/13-modules-and-java.md#m1-module-names) where the design writes them; what stage 4 wrote is marked.

```python
# tlaup/modules/registry.py
def validate_module_name(name: str) -> str        # returns the name or raises InvalidName (code 2)

@dataclass(frozen=True)
class RegisteredModule:                           # written by stage 4: M2 names it and gives module.json's fields
    name: str
    path: Path                                    # <cache>/module/<name>
    built_at: str                                 # UTC, ISO 8601 with Z
    source: str                                   # the resolved source folder, as given to build_module
    javac: str | None                             # "25.0.5"; None with no Java sources or an unread version
    release: int | None                           # None with no Java sources
    built_against: str | None                     # "rolling@bc1b506...", None with no Java sources
    override_classes: tuple[str, ...]

class Registry:                                   # the method names are M2's; the constructor and types are stage 4's
    def __init__(self, root: Path) -> None        # root is AppPaths.modules, <cache>/module
    def list(self) -> list[RegisteredModule]      # sorted by name, in Python's string order (M2; row M18)
    def path_of(self, name: str) -> Path          # validates (M1), then the second, independent check
    def remove(self, name: str) -> None           # raises InvalidName, ModuleNotFound, FileOperationError
    @contextmanager
    def locked(self, timeout: float = 60.0) -> Iterator[None]    # <root>/.lock; raises StoreLocked

# tlaup/modules/build.py
@dataclass(frozen=True)
class BuiltModule:
    name: str
    path: Path
    override_classes: tuple[str, ...]
    replaced: bool                      # a module of this name was registered before
    warnings: tuple[str, ...]           # 11 R7's (package 34), and those of the javac lookup (J2, M3); the command prints them

def build_module(source: Path, *, registry: Registry,
                 get_build: Callable[[], Build],          # the pinned build; raises NoPinnedBuild, NoToolsInstalled
                 get_javac: Callable[[], JavaRuntime],    # require_javac of J2 with its arguments bound; raises
                 release: int, now: Callable[[], datetime], timeout: float = 300.0) -> BuiltModule

# tlaup/modules/classfile.py
@dataclass(frozen=True)
class ClassInfo:
    name: str                        # "tlc2.overrides.QueueOverrides"
    super_name: str | None
    interfaces: tuple[str, ...]
    is_abstract: bool
    is_interface: bool
def read_class(data: bytes) -> ClassInfo        # raises ValueError if not a class file

def find_override_classes(classes_dir: Path) -> list[str]    # written by stage 4: M3's scan as a function
    # every .class file under classes_dir; the names of those that implement tlc2.overrides.ITLCOverrides,
    # directly or through a superclass found among them; abstract classes and interfaces skipped; sorted
```

All class names in `ClassInfo` are written with dots (`tlc2.overrides.ITLCOverrides`), converted from the class file's slashes; [34](34-override-check.md) compares in that form. A nested class keeps its `$` (`a.Outer$Inner`), which is the binary name the service file needs.

**`module.json`** (M2, step 5), written and read by one function each in `registry.py`, written atomically (a file beside it, then `os.replace`):

```json
{"schema": 1, "name": "Queue", "built_at": "2026-11-15T10:00:00Z", "source": "<the resolved source folder>",
 "javac": "25.0.5", "release": 11, "built_against": "rolling@bc1b506bdcad80bb518bf3776a9161c34ff0fc4c",
 "override_classes": ["tlc2.overrides.QueueOverrides"]}
```

`javac`, `release` and `built_against` are `null` for a module with no Java sources; `javac` is also `null` when `require_javac` could not read the version (`JavaRuntime.version` is `None`). `built_against` is `<Build.name>@<Build.commit>` with the commit as the store holds it, and the bare name when the build has no commit ("the build's `name@commit`", read so; a reading of stage 4, confirmed at the stage 4 sign-off, 2026-11-24).

**`ClasspathResolver` after its change** (written by stage 4, from [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder) and [12 V10](../design/12-tools-and-downloads.md#v10-remove-old-layouts); design 03 lists it among the joints with no written signature). The change has three owners, in this order of the code's life:

```python
# tlaup/java/classpath.py, after this package
class ClasspathResolver:
    def __init__(self, config: Settings, project_root: Path | None = None, tool_jar: Path | None = None,
                 extra_libs: list[str] | None = None, extra_modules: list[str] | None = None,
                 *, module_dirs: Sequence[Path] | None = None) -> None
        # module_dirs: the folders of the registered modules, in the order Registry.list() gives them
        #   (by name), for example [m.path for m in Registry(paths.modules).list()].
        #   None: walk <cache>/modules as release 0.8.x does. Only the old callers pass None.
```

- **This package** adds `module_dirs`. For each folder `d` in it, the resolver does what it does today for each subfolder of the old cache: `d/classes`, if it is a folder, on the classpath after the project's classes and the TLA+ module folders and before the tool jar; `d/lib/*.jar`, sorted, after the libraries of the command line, the project and the config; `d/modules`, if it is a folder, in the TLA-Library list and on the runtime classpath after those of the command line, the project and the config. That is the five-step order [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder) now writes out under "The classpath of a run" (roadmap, "Keep"), with an entry that appears twice kept at its first place, and the resolver takes its inputs as arguments, which the same "Keep" line asks for. The old callers (`tlc/runner.py`, `cmd/tlc.py`'s `_show_diagnostic_info` until 04 removes it, `cmd/modules/add.py`, `cmd/modules/path.py`) pass nothing and see no change (finding B2: the call in `cmd/tlc.py` was missing from this list; this package may land before 04).
- **[31](31-module-commands.md)** makes `module_dirs: Sequence[Path]` required (still keyword-only), deletes the walk and the import of `get_modules_dir`, deletes `ResolveMode.COMPILE`, whose last caller is the old `cmd/modules/add.py`, and gives the remaining old caller, `tlc/runner.py`, the registry's folders, so that `main` type-checks. `cmd/tlc.py` is not one by then: its call was in `_show_diagnostic_info`, which [04](04-delete-dead-code.md) deletes, and 31 waits for 04 (findings F3 and G4 of the [second review](review-2026-11-24.md)).
- **[33](33-tlc-invocation.md)** changes what the resolver returns (paths instead of joined strings) and is the new caller: the preflight passes `module_dirs=[m.path for m in Registry(paths.modules).list()]`. Whether 31 or 33 lands first does not matter; their edits are in different lines of the class.

`Registry` does not appear in the resolver's signature on purpose: the resolver stays a function of folders, and milestone 3's "only the modules the project declares" becomes a filter on the `Registry.list()` call ([40](../design/40-later-milestones.md#milestone-3-reproducibility)).

Consumes: the error classes and `AppPaths` (02); `Build` (23); `JavaRuntime`, `JavaTool` (20).

Consumed by: [31](31-module-commands.md) (everything here), [33](33-tlc-invocation.md) (`Registry`, `module_dirs`), [34](34-override-check.md) (`read_class`, `ClassInfo`, `build_module`'s `warnings`, `module.json` as the mark of a registered module's folder), [46](46-doctor.md) and [47](47-completion.md) (`Registry.list()`).

## Tests that must pass

Plain pytest, unit, with real files in `tmp_path` and the fakes; no patching of `tlaup` ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests)). These are T1's "pure functions" (the class-file reader, the name check) and "pieces that sit directly on an edge" (`build_module` with the fake `javac`).

`tests/unit/modules/test_registry.py` (M1, M2):

- `validate_module_name`, parametrised: `../tools`, `../tool`, `..`, `.`, `""`, `/abs`, `a/b`, `a\b`, `.hidden`, `.tmp`, `C:x`, a name with a space, a 65-character name each raise `InvalidName`; valid names (`Queue`, `a`, `x.y_z-1`, a 64-character name) come back unchanged.
- `path_of`: a valid name gives `<root>/<name>`; a valid name whose folder is a symbolic link pointing outside the root raises `InvalidName` (the second check; skipped with the reason where links cannot be made).
- `list()`: returns only folders with a valid name and a readable `module.json` of schema 1; `.tmp/`, `.lock`, a folder without `module.json`, one with a corrupt file and one with `"schema": 99` are not in it.
- `list()`'s order (row M18): modules `Zeta`, `alpha` and `Beta` registered in that order come back as `Beta`, `Zeta`, `alpha` (Python's string order, by code point).
- `remove`: a registered module is gone and nothing of it is left under the root outside `.tmp/`; an unknown name raises `ModuleNotFound`; `../tool` raises `InvalidName` and the folder `<root>/../tool` with a file in it is untouched.
- `locked`: with the lock held by a second process, a short timeout gives `StoreLocked`, whose message names the lock file.

`tests/unit/modules/test_build.py` (M2, M3), with the fake `javac` from the isolation fixture's `PATH` and a `get_javac` that returns a `JavaRuntime` for it:

- A module with only `.tla` files, `get_build` and `get_javac` that fail the test when called: built, `module.json` has `javac`, `release` and `built_against` null, no `classes/`. (M2)
- The narrow compile classpath (decision D61, row M5): a module whose `lib/` holds `b.jar` and `a.jar` (made in that order), with another module registered in the same registry (with its own `classes/` and `lib/` jar): the `-cp` value in the fake's log is exactly the build's jar, then the copy's `lib/a.jar`, then `lib/b.jar`, joined with `os.pathsep`, and nothing of the other module. (M2, step 3)
- A module with Java sources: the fake's log shows one start whose arguments are `-encoding UTF-8 --release 11 -cp <classpath> -d <folder> <sources>`, with `<folder>` under `<root>/.tmp/`; afterwards `classes/` holds the copied class files and `META-INF/services/tlc2.overrides.ITLCOverrides` names the override classes; `module.json` has every field of the shape above; `replaced` is false. (M2, M3)
- The same module added twice: the second has `replaced` true, the folder holds the second build only, and nothing is left under `.tmp/`. (M2)
- The fake `javac` set to fail with a recording: `ModuleBuildError` whose `details` hold the recorded compiler output and the classpath; the module registered before is untouched (its `classes/` and `module.json` are byte for byte the same); nothing of the attempt is left under `.tmp/`. (M2)
- With a timeout of half a second and the fake set to wait: `ModuleBuildError` whose message names the timeout in seconds; the fake's process has exited (its process id from the log's `start` line no longer runs); the registered module, if any, is untouched. (M3)
- The age rule of `.tmp/`, with `now` injected: an entry one day and one minute old is gone after a build (also after a build of a module with no Java), one made a minute ago is still there. (M2)
- `lib/`, `modules/` and `tlc2/` are copied; a `test` and a `tests` folder are not. (M2)
- A source folder with its own `META-INF/services/tlc2.overrides.ITLCOverrides`: the service file in `classes/` is that file, byte for byte, and no class file is read for it. (M3)
- Java sources with no override class among the compiled classes: no service file is written, `override_classes` is empty, and `warnings` holds one note that no override index class was found. (M3)
- A source file holding `String u = "http://x"; // implements ITLCOverrides` in a class that does not implement the interface: the class is not reported. (M3; with class-file reading the source text no longer matters, so this is a regression test of the old regex.)
- The warnings of `get_javac`'s `JavaRuntime` are in `BuiltModule.warnings`. (M2's field comment)
- A source that is not a folder: `PathNotFound`. A source folder whose name fails the rule (for example `my module`): `InvalidName` with a hint to rename the folder, before anything is copied. (M1)
- `get_build` raising `NoPinnedBuild` for a module with Java sources: that error comes out, `get_javac` was not called, nothing is left under `.tmp/`. (M2, step 3)

`tests/unit/modules/test_classfile.py` (M3):

- `read_class` on the real class files of `tests/fakes/classes/`: one implementing `tlc2.overrides.ITLCOverrides`, one implementing nothing, an abstract one implementing it, one implementing it through a superclass, and one whose constant pool has `long` and `double` constants (the two-slot entries); each gives the right name, superclass, interfaces and flags.
- `read_class` on truncated copies of a real class file (cut at every length below the full one) and on random bytes raises `ValueError` and never anything else; a Hypothesis test over `st.binary()` asserts that `read_class` either returns or raises `ValueError`.
- `find_override_classes` on a folder of those files: the direct implementer and the one through a superclass are found; the abstract class, the interface stub and the plain class are not.

`tests/unit/java/test_classpath.py`, new, M2's unit test of "The classpath of a run" (rows S11, M17 and M18 of the inventory), with real folders and jars under `tmp_path`: a project with `classes/`, `modules/` and two jars in `lib/` created in reverse name order; `module_path` and `module_lib_path` set in the settings passed in, `module_lib_path` naming the project's `lib/` so that its jars are reachable twice; two registered modules created in the reverse of their name order, each with `modules/`, `classes/` and a jar, passed as `module_dirs` in `Registry.list()`'s order; a tool jar. The whole runtime classpath (`resolve(ResolveMode.RUNTIME)`) equals one expected list, entry for entry, in the five steps of M2, with each jar once; `get_tla_library_property()` gives the folders of step 2 in the same order; nothing under the isolation fixture's `<cache>/modules` is read. One expected list, written out in the test, not built by the code under test. [33](33-tlc-invocation.md) changes the resolver's return types and extends this file (C6's relative `module_path`, the preflight's caller); 31 changes only what it must for the required `module_dirs`.

Old tests: none left (03b). T11 lists "finding override classes" among behaviour with no test today; these are its first tests. The pull request names the inventory rows it covers: M5 (unit form), M17, M18 and S11's first form. No stateful test applies: design 03 left the modules registry without a spec because it uses the store's pattern.

## Changelog

None. No command reaches this code. [31](31-module-commands.md) writes every entry of M1, M2 and M3.

## Context for the worker

**State of `main` when this starts.** After 01 to 03 and the groundwork and store packages this depends on: `tlaup/errors.py`, `tlaup/paths.py`, `java/locate.py`, `versioning/store.py` exist. The old `tlaup modules add|list|remove|path` (`cmd/modules/`) still copies into `<cache>/modules/<name>/`, writes `metadata.json`, finds the jar through `tlc/compiler.py` and runs a bare `javac`; the old `tlaup tlc` builds its classpath with `ClasspathResolver`, which walks `<cache>/modules` through `versioning/paths.get_modules_dir()`. Both stay exactly as they are. The new code works on `AppPaths.modules`, which is `<cache>/module` (D47); the two folders never meet ([02](02-errors-and-paths.md), "What this package rewires").

**Decisions this rests on.**

- D23: no confirmation when a module of the same name is replaced; the command says what it did. `replaced` is how it knows.
- D14: no migration. Modules in the old `<cache>/modules` are never read by the new code.
- D47: the folder is `module/`.
- D15: `pathlib`, no `:` in names (the name rule already refuses it), `os.replace` for atomic writes. A folder cannot be renamed over a folder that is not empty, which is why step 6 is two moves. On Windows a file held open blocks a rename; the move then fails and the registered module stays (not tried).
- The design agent's decision that the module build becomes domain code in milestone 1 and finds override classes by reading the compiled class files ([README](../design/README.md#decisions-the-design-agent-made)).
- The design agent's decision to compile with `--release 11`: a module built with a newer JDK must load on the oldest supported Java. Research 28, as M3 restates it: classes from `javac` 25 and 21 with `--release 11`, and from `javac` 11, load and are used on Java 11, 21 and 25 with both builds, and `javac` printed no warning for the flag; without it a JDK 25 build is refused on Java 11 and 21.
- The one-day age for a half-built module folder is a guess, named as one in the design README; do not tune it.

**The steps of `build_module`, with what the design leaves to the worker.** M2 lists seven steps; these are the points a worker could miss.

1. *Name and source.* `source.resolve()` first; not a folder is `PathNotFound` (4). The name is the resolved folder's last component, through `validate_module_name`, so `tlaup modules add /` (an empty name today) is refused. `InvalidName`'s hint says to rename the folder.
2. *The age of a `.tmp/` entry.* T12 rule 5 forbids modification times in tests, and `now` is injected. So each entry this package makes under `.tmp/` is named `<UTC time>-<random hex>` (for example `20261115T100000Z-3fa9c1d2`, the form of [33](33-tlc-invocation.md)'s run ids, no `:`), and its age is read from the name against `now()` (a reading of stage 4, confirmed at the stage 4 sign-off, 2026-11-24). An entry whose name holds no time is left alone. The cleanup runs before the new temporary folder is made, without the lock (the age keeps a running add safe), and an entry that cannot be removed is skipped, not an error.
3. *The `javac` command and its classpath.* `[<JavaRuntime.tool.path>, "-encoding", "UTF-8", "--release", str(release), "-cp", <classpath>, "-d", <tmp>/classes, *<sources>]`, from an argument list, never a shell; sources are the `.java` files under `modules/tlc2/overrides/` and `tlc2/overrides/` of the copy in the temporary folder, searched recursively as today, sorted. **The compile classpath is narrow** (decision D61, [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder) step 3; finding B8): `Build.jar`, then the `*.jar` files directly in the copy's own `lib/`, sorted by name, joined with `os.pathsep`, and nothing else: not another registered module, not `module_lib_path` (run time only, [14 F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay)), nothing else on the machine, so that a module compiles the same on every machine. `build_module` takes no settings and no resolver, so nothing wider can reach it. Today's compile classpath (`ResolveMode.COMPILE`) was wider; M2's Breaking entry says so, and [31](31-module-commands.md), where users first see it, writes it.
4. *Running it.* `subprocess.run` with `capture_output=True`, the timeout, and the output decoded with replacement. A non-zero exit is `ModuleBuildError` (5) with the output and the classpath as `details`. `subprocess.TimeoutExpired` (the child is killed and reaped by `run`) is `ModuleBuildError("javac did not finish in <timeout> seconds")`. An `OSError` when starting it is `ToolStartError` with the path and the system's message, as J3 gives for `java`. On success the output is dropped: M3 shows `javac`'s warnings only with `--verbose`, which is milestone 4. `javac` is not started through the launcher of [21](21-java-launcher.md): it is a short, bounded call with a timeout, and the lifeline is for the tools that run as long as the user wants.
5. *Override classes.* With the source's own `<source>/META-INF/services/tlc2.overrides.ITLCOverrides`, that file is copied to `classes/META-INF/services/` as written and its class names (comments and blank lines skipped) are `override_classes`; stage 4 reads "the source folder has its own" as that one place. Otherwise `find_override_classes(classes)`; when it finds none, no service file, and one note in `warnings` (M3: "the command says that no override index class was found"). Today's code writes the configured default class name whether or not it exists; that goes.
6. *The swap* (M2, step 6), under `registry.locked()`: whether `<root>/<name>` exists is read under the lock and is `replaced`; if it exists it is moved to `.tmp/<time>-<random>`; the temporary folder is moved into place; if that move fails, the old one is moved back and the error raised (`FileOperationError`); then the old one is deleted, and a failure to delete it is not an error (the age rule takes it a day later). No reader sees a half-built or half-deleted module: each step is one rename.
7. *Any failure* before the swap removes the temporary folder (a `try`/`finally` around steps 2 to 5) and leaves the registered module untouched.

`build_module` prints nothing and asks nothing; the command prints `BuiltModule.warnings` and the "Added" or "Replaced" line.

**The registry.** `list()` reads every folder under the root whose name passes M1's rule and that holds a `module.json` it can read with schema 1; anything else is skipped (a reading error is caught as `(OSError, ValueError)`, which [30 I8](../design/30-ci-and-release.md#i8-lint-rules)'s blind-except rule expects of the new `module list`). `path_of` checks twice: the name rule, then `(root / name).resolve().parent == root.resolve()`, raising `InvalidName` (not `assert`, which `python -O` removes). `remove(name)` validates, takes the lock, raises `ModuleNotFound` (hint: `tlaup module list`) when the name is not a registered module, moves the folder into `.tmp/` and deletes it there, as the store removes a build ([12 V1](../design/12-tools-and-downloads.md#v1-version-store)); a folder that cannot be moved is `FileOperationError`. The lock is `filelock.FileLock(<root>/.lock)` with a finite timeout, never none: since `filelock` 3.29.6 a second wait with no timeout in the same thread raises `RuntimeError` ([12 V11](../design/12-tools-and-downloads.md#v11-concurrent-installs)); a timeout is `StoreLocked` naming the file (stage 4's choice of class: the design names no "modules locked" error, and `StoreLocked` is the `Failed` subclass for exactly this). Taken and released in one thread. Nothing creates the root until something is added.

**The class-file reader** (M3, about 60 lines, standard library only; the length is an estimate). Magic `0xCAFEBABE`; minor and major version; the constant pool count, then entries 1 to count minus 1, each skipped by its tag's size: 1 Utf8 (a two-byte length and the bytes), 3 Integer and 4 Float (4), 5 Long and 6 Double (8, and they take two slots), 7 Class, 8 String, 16 MethodType, 19 Module, 20 Package (2), 15 MethodHandle (3), 9, 10, 11 the three refs, 12 NameAndType, 17 Dynamic, 18 InvokeDynamic (4). An unknown tag is `ValueError`. Then access flags (`0x0400` abstract, `0x0200` interface), this class, super class (0 means none), the interface count and the interfaces, each a Class entry pointing at a Utf8. Truncation (`struct.error`), an index out of range (`IndexError`, `KeyError`) and a bad name (`UnicodeDecodeError` is already a `ValueError`) all become `ValueError`; nothing else may leave the function. Class files encode names in modified UTF-8, which equals UTF-8 for every name the tests use.

**Class files.** [01 T4](../design/01-testing.md#t4-fakes-at-the-edges) says the fake `javac`'s class files are real, compiled once from `tests/fakes/java-src/` with `javac --release 11` and committed with the compiler's version in a README. M3's reader tests need five shapes (implements the interface; implements nothing; abstract and implements it; implements it through a superclass; has `long` and `double` constants), and the build tests need a source with the `"http://x"` string. Add those [03](03-test-foundation.md) did not commit. Compile them against a small stub `tlc2/overrides/ITLCOverrides.java` in `java-src/`, so no `tla2tools.jar` is needed; the stub's own class file is the "interface" case. This needs a JDK once on the worker's machine; the README records which.

**What this package needs of the fake `javac`** beyond T4's sentence ("copies prepared class files for the sources it is given into the `-d` folder, or prints a recorded compiler error and exits 1"). If package 03 did not build these, add them to `tests/fakes/javac` here, with the same kind of reason a new field of the fake `java` needs:

- *Which class files.* For each source `.../tlc2/overrides/X.java` given, the prepared files `tests/fakes/classes/tlc2/overrides/X.class` and `X$*.class`, copied into `<-d>/tlc2/overrides/`. A source with no prepared class makes the fake exit 1 with a message naming it, so a missing fixture fails loudly.
- *A recorded failure.* A recording under `tests/fakes/` (for example `javac-errors/syntax-error.txt`), printed on stderr as `javac` prints errors, exit 1.
- *A wait.* A field such as `compile_delay_ms`, after the `start` line is logged and before anything is copied, for the timeout test; the fake must end on the signal `subprocess.run` sends at the timeout.
- *`-version`.* `javac <version>` on stdout and exit 0, from a `version` field (default `25.0.5`): [01 T4](../design/01-testing.md#t4-fakes-at-the-edges) now says so and 03 builds it, and 18's step `javac is version "<v>"` sets it. Not used here (the tests pass a `JavaRuntime`), but [31](31-module-commands.md)'s scenarios need it through `require_javac`.

**Traps.**

- `module.json` is the mark of a registered module for [34](34-override-check.md) too (it finds the module's name from the folder holding it), so write it last in the temporary folder, and never into a folder that is not a module.
- The temporary folder is inside `<root>/.tmp/`, on the same file system as `<root>`, so the moves are renames, not copies. Do not use the system's temporary folder.
- `copytree` copies the files a link points to; that is fine and is what today's code does.
- Do not import anything from `cmd/modules/add.py` or `versioning/paths.py`: both go in 31.
- `now` is `Callable[[], datetime]` returning an aware UTC time; `built_at` is written as `YYYY-MM-DDTHH:MM:SSZ`.
- `release` is passed by the command (`java.min_version`); never read a setting here.

**Known gaps the design leaves; do not close them.** A `javac` started by a tlaup that is then killed runs to its end or to nothing (it has no lifeline; the timeout bounds it only while tlaup lives). A class that reaches `ITLCOverrides` through an interface that extends it is not followed; M3 follows superclasses only. A command line too long for Windows with very many sources (an `@argfile` would solve it) is not handled. Per-project modules, community modules: milestone 3.

## Done when

- The five test files pass (the four of `tests/unit/modules/` and the new `tests/unit/java/test_classpath.py`).
- `uv run poe lint` (mypy strict covers `tlaup/modules/`) and `uv run poe test` pass; CI is green.
- No file under `src/tlaup/cmd/` or `src/tlaup/tlc/` changed.
- The pull request names every adjusted signature, what it added to the fake `javac` and the fake class files, the JDK used to compile them, and the inventory rows it covers (M5's unit form, M17, M18 and S11's first form), each with its test.

## Out of scope

- The `module` commands, `modules.feature`, binding `get_build` and `get_javac`, printing "Added" or "Replaced" and the warnings, the changelog, deleting `cmd/modules/`, `get_modules_dir` and the resolver's walk, pointing the old `tlaup tlc` at the registry: [31](31-module-commands.md).
- `require_javac`, its pattern and the remembered `javac` answer (M3's version-check bullet): [20](20-java-location.md).
- R7's warnings in `BuiltModule.warnings`: [34](34-override-check.md).
- `-DTLA-Library` and the classpath of a run in the new preflight, and the resolver's return types: [33](33-tlc-invocation.md).
- Java options (13 J1): [33](33-tlc-invocation.md). Finding `java` and `javac` and remembering their versions (13 J2, J3): [20](20-java-location.md).
- The integration test with `docs/examples/QueueModule`: [52](52-integration-tests.md). Completion of module names: [47](47-completion.md). `doctor`'s view of the modules folder: [46](46-doctor.md).

## Risks

- From M2: a module larger than the free space in the cache folder fails at the copy; the registered one survives. A tlaup killed between the two moves of step 6 leaves the name unregistered with the old build in `.tmp/` for a day; the window is two renames long, and the fix is to add the module again.
- From M3: a source that uses language features or library classes newer than Java 11 no longer compiles; the compiler's error names them, and raising `java.min_version` raises the release. Whether the reader fits in about 60 lines is an estimate.
- From M1: a module registered with a name the rule refuses cannot be removed by name. In the first wave that cannot happen in `<cache>/module`, since only this code writes there.
- From D61: a module that compiled against another registered module or a jar of `module_lib_path` no longer compiles; the compiler's error names the missing class, and the Breaking entry (31) says to put a copy of the jar in the module's own `lib/`. Widening the classpath later is additive.
- From the cut: `ClasspathResolver` has a `None` default that means "the old walk" between this package and 31. It is internal, no user sees it, and 31 removes it; it is not a shim in D14's sense, but a reviewer should check that 31 really does.
- From the cut: the committed class files need a real `javac` once; a worker without a JDK cannot produce them.
