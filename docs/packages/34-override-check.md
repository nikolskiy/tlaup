# 34. Override classes: which are passed, and the check before a run

Size: M. Suggested model: mid-tier. Status: built.

## Goal

`tlaup/tlc/overrides.py` decides which Java override classes are passed to TLC and says, before the run, which of them the pinned build will not load. The preflight of [33](33-tlc-invocation.md) calls it, so a `TlcInvocation` carries the class names and the warnings; `build_module` returns the same warnings for a module that is being added. The two hint texts for a load that fails inside TLC are here as pure functions.

## Covers

- Roadmap items ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)):
  - "Report clearly when an override module fails to load (raised list)." In part: the collection, the check before a run and the texts of the two hints. Parsing message 2168 and the warnings 2400, 2402, 2403 is [13](13-tlc-parser.md); placing the hint is [38](38-terminal-reporter.md); listing the loaded overrides belongs to the verbose header of milestone 4 (R7 part 3, `--verbose`), which nothing in the first wave prints; the scenarios through `tlaup tlc` and the changelog entries are [39](39-tlc-command.md); the integration test on `docs/examples/QueueModule` is [52](52-integration-tests.md).
- Design sections:
  - [11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load), part 1 (`OverrideClass`, `collect_override_classes`) and part 2 (`check_overrides`), with their unit tests; and from part 4 the wording of the two hints, as functions of text, with the test on research 28's two captures. Part 3 is the parser's and the reporter's. The condition under which a hint is shown is the reporter's ([22 O3](../design/22-reporters.md#o3-terminal-reporter), "Override hint").
  - [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder), one field: `BuiltModule.warnings` gets R7's warnings. The rest of M2 is [30](30-module-build.md).
  - [20 G1](../design/20-groundwork.md#g1-tlc-invocation): the field `TlcInvocation.override_classes` gets its value, and R7's warnings join `TlcInvocation.warnings`.
- Rows of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) this package owns: M7 and R24, both held by `test_overrides.py` below (R24's property itself is placed by [33](33-tlc-invocation.md)'s builder, whose expected file shows it). It also writes M20's property half for [39](39-tlc-command.md): the classes of several modules, first wins, no duplicates (finding G1).

## Depends on

- [02](02-errors-and-paths.md): nothing is raised here; the package only needs `tlaup` importable with its errors for the modules it edits.
- [03](03-test-foundation.md): the isolation fixture and the fake class files (`tests/fakes/classes/`, compiled once from `tests/fakes/java-src/`, [01 T4](../design/01-testing.md#t4-fakes-at-the-edges)).
- [07](07-golden-files.md): research 28's two captures, moved into the golden folder as `override-class-too-new-index` and `override-class-too-new-listed` ([01 T3](../design/01-testing.md#t3-golden-files), question Q3 as settled).
- [23](23-tool-store.md): `Build.capabilities`, for `overrides_property` ([00](../design/00-overview.md#what-a-build-can-do)).
- [30](30-module-build.md): `read_class` and `ClassInfo` from `tlaup/modules/classfile.py` ([13 M3](../design/13-modules-and-java.md#m3-module-build-details)); `build_module` and `BuiltModule`, which this package edits; the `module.json` that marks a registered module's folder.
- [33](33-tlc-invocation.md): `resolve_tlc_invocation`, which this package edits at one place.

Change from the draft (33, 30): 23 is named, for the capability; 07 is added, for the two captures; 02 and 03 are the foundation.

## Files

Creates:

- `src/tlaup/tlc/overrides.py`.
- `tests/unit/tlc/test_overrides.py`.

Changes:

- `src/tlaup/tlc/invocation.py` ([33](33-tlc-invocation.md)), at the place 33 marked, after the classpath is known and the build and Java are found: `classes = collect_override_classes(classpath)`; `override_classes` becomes the tuple of their names; the result of `check_overrides(classes, classpath, build)` is added to `warnings`. Nothing else in the preflight changes, and no step moves.
- `tests/unit/tlc/test_invocation.py`: two cases, below.
- `src/tlaup/modules/build.py` ([30](30-module-build.md)): `build_module` puts R7's warnings for the module it has just built into `BuiltModule.warnings`, checked against the build `get_build()` returned. A module with no Java sources never calls `get_build` and gets no check, as M2 says ("skipped without one").
- The unit test file of `build_module` that 30 wrote: one case.
- `tests/features/modules.feature`, only if [31](31-module-commands.md) is merged when this package starts: 31's R7 scenario (below), which 31 leaves to this package when 34 comes second.
- `CHANGELOG.md`, only in the case named under Changelog.

Deletes: nothing. Today's `get_override_classes` in `src/tlaup/tlc/runner.py` stays until [39](39-tlc-command.md) deletes the old runner.

Files another package also touches: `src/tlaup/tlc/invocation.py` with [35](35-run-folders.md), which reads it and may move `find_recovered_run`; the overlap with this package is none, the edits are in different functions. `src/tlaup/modules/build.py` with [31](31-module-commands.md) only if 31 has to adjust it for the command; a few lines.

## Interfaces

Provides. The first three are copied from [R7](../design/11-runner.md#r7-override-modules-that-do-not-load); the two hint functions are written by stage 4 from part 4's words.

```python
# tlaup/tlc/overrides.py
@dataclass(frozen=True)
class OverrideClass:
    name: str                    # "tlc2.overrides.QueueOverrides"
    declared_in: Path            # the classpath entry
    module: str | None           # the registered module's name, if the entry is one

def collect_override_classes(classpath: Sequence[Path]) -> list[OverrideClass]
def check_overrides(classes: Sequence[OverrideClass], classpath: Sequence[Path], build: Build) -> list[str]

def class_version_hint(text: str) -> str | None        # written by stage 4
    # the specific hint, when `text` holds the JVM's class-file-version sentence; else None
def load_failure_hint(classes: Sequence[str]) -> str   # written by stage 4
    # the general hint, naming the classes that were passed
```

**`collect_override_classes`.** For each classpath entry in order, a folder or a jar: the lines of its `META-INF/services/tlc2.overrides.ITLCOverrides` file, if it has one, with comments and blank lines skipped. Then, for every entry that holds `tlc2/overrides/TLCOverrides.class` and whose service file did not already name it, the default name `tlc2.overrides.TLCOverrides`. Duplicates are dropped, the first wins. The property is passed only when the list is not empty, which is the builder's rule in 33.

**`check_overrides`.** One warning text per finding, in this wording:

- No classpath entry holds the class's `.class` file: "override class X (module M) is not on the classpath and will not load".
- The build lacks the capability `overrides_property` and the name is not `tlc2.overrides.TLCOverrides`: "TLC <build> loads Java overrides only from a class named tlc2.overrides.TLCOverrides; X (module M) will not load, and the TLA+ definitions of its operators will be used".
- Two classpath entries hold a class named `tlc2.overrides.TLCOverrides`: a warning that only the first is used.
- The `.class` file is found and does not implement `tlc2.overrides.ITLCOverrides`: "X (module M) is not an override class (it does not implement tlc2.overrides.ITLCOverrides) and TLC will ignore it". The file is read with `read_class`. A class that reaches the interface through a superclass is followed as far as the superclass can be found on the classpath outside the tools jar; when the chain leaves what can be read, or the file is not a readable class file (`read_class` raises `ValueError`), nothing is said.

"(module M)" is left out when `module` is `None`. `<build>` is the build as tlaup prints it (`format_build` of [23](23-tool-store.md)).

**The two hints** (R7, part 4).

- `load_failure_hint`: "TLC failed while loading the spec. If the error comes from a Java override, one of these classes failed to load: ..." followed by the class names.
- `class_version_hint`: when the text holds the sentence "... has been compiled by a more recent version of the Java Runtime (class file version 69.0), this version of the Java Runtime only recognizes class file versions up to 55.0", the hint "the override class tlc2.overrides.TLCOverrides was compiled for Java 25 (class file 69) and TLC runs on Java 11 (up to 55); rebuild the module with `tlaup module add`, which compiles with `--release 11`, or run TLC on a newer Java". The Java versions are the class-file versions minus 44. The class name stands before "has been compiled" and is written with slashes in the JVM's sentence (`tlc2/overrides/TLCOverrides`); the hint writes it with dots.

Who calls them: the terminal reporter ([38](38-terminal-reporter.md)), under O3's condition. An error with code 2173 always gets a hint: the specific one when its text has the sentence, else the general one. An error of kind `exception` (message 1000) before the initial states, with override classes passed and no nested message of kind `config`, gets the general one, or the specific one when its text holds `java.lang.UnsupportedClassVersionError` and the sentence.

Consumes: `read_class`, `ClassInfo`, `build_module`, `BuiltModule` (30); `Build` (23); `resolve_tlc_invocation`, `TlcInvocation` (33).

## Tests that must pass

Plain pytest, real folders and real class files; jars are made in the test with `zipfile` from the fake class files. No mocks.

`tests/unit/tlc/test_overrides.py`:

- `collect_override_classes` (R7): a folder with a service file; a bare `TLCOverrides.class` in a folder, and in a jar; both a service file and a bare `TLCOverrides.class` in one entry (the default name is added once, after the service file's names, unless the service file names it); a registered module's service file together with a project's own `TLCOverrides.class`, where the list holds both names; a service file with a comment and a blank line; two entries naming one class (the first wins); `module` is set for an entry that belongs to a registered module and `None` for a project's own folder.
- `check_overrides` (R7): each of the four warnings and the clean case. For the second, a `Build` without `overrides_property` and a class named otherwise warns, the same build with a class named `tlc2.overrides.TLCOverrides` does not, and a build with the capability does not. For the fourth: a class that implements the interface only through a superclass in the same folder is not warned about, and neither is one whose superclass cannot be found; a file of random bytes named `X.class` gives no warning and no exception.
- The hints: `class_version_hint` on the text of research 28's two captures gives the specific hint with the right two Java versions (25 and 11 for class files 69 and 55); on a text without the sentence it gives `None`. The message text is read from the capture files, never typed into the test ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 3). The two captures are the `-tool` output of a too-new index class (message 2173) and of a too-new listed class (message 1000 with `UnsupportedClassVersionError`), on each build: `tests/parse/golden/tlc/<build>/override-class-too-new-index.out` and `override-class-too-new-listed.out`, where [07](07-golden-files.md) put them ([01 T3](../design/01-testing.md#t3-golden-files)).

`tests/unit/tlc/test_invocation.py`, two added cases: with a registered module whose class is `QueueOverrides` and a project folder that holds `tlc2/overrides/TLCOverrides.class`, a build with the capability gives `override_classes` holding both names and no override warning; a build without it gives the second warning in `TlcInvocation.warnings`, and the preflight still returns.

The unit tests of `build_module` (30's file), one added case: with the fake `javac`, a module whose class is `QueueOverrides` and a `get_build` returning a build without `overrides_property`, `BuiltModule.warnings` holds the same warning text as the preflight's.

`tests/features/modules.feature`, only if 31 is merged when this starts (finding C3 of the stage 4 review): with `v1.7.4` pinned, `module add Queue` (class `QueueOverrides`) exits 0 and stderr has one `warning:` line naming `QueueOverrides`. When 31 comes after this package, 31 writes the scenario itself.

T12 rule 6: R7's Fixed entry is a defect of today's code (a `TLCOverrides.class` inside a jar is not found once any service file exists). The pull request shows the jar case of `collect_override_classes` failing first, for example by running it against the old rule before the function is complete.

Old tests: none; the old suite went in [03](03-test-foundation.md) (decision D62). "Finding override classes" had no test in 0.8.x; these are its first (inventory row M7, kept, whose unit tests R7 names). No stateful test applies.

## Changelog

The two entries of R7 (a third, about listing the loaded overrides, was dropped from the design on 2026-11-22, since nothing in the first wave prints that list):

- Added: "tlaup warns before a run when a registered Java override class will not be loaded by the pinned TLC build. On v1.7.4 only a class named `tlc2.overrides.TLCOverrides` is loaded."
- Fixed: "On rolling builds an override class named `tlc2.overrides.TLCOverrides` inside a jar on the classpath stopped loading when another override module was registered."

Which package writes them: the Fixed entry describes a run and is written by [39](39-tlc-command.md). The Added entry is written here if `tlaup module add` of [31](31-module-commands.md) is already on `main`, because from this package on it prints the warning when a module is added; otherwise this package writes none and 39 writes both. 39 writes the Added entry only when it is not already there.

## Context for the worker

**State of `main` when this starts.** `tlc/invocation.py` and `tlc/command.py` exist and nothing calls them; `override_classes` is always empty. The old runner still collects classes with `get_override_classes`, for folders only. `modules/build.py` builds modules; whether `tlaup module add` already runs through it depends on whether [31](31-module-commands.md) is merged.

**What the research found, and why the check exists** (research 13, 35 cases per build, Java 25 only; restated from R7).

- Most failures are silent. A class that is missing, not on the classpath, or not an `ITLCOverrides` gives no output and exit 0, and the plain TLA+ definition runs. So TLC's output can report only part of the failures; the rest has to be checked before the run.
- v1.7.4 ignores the `tlc2.overrides.TLCOverrides` property and loads only a class with exactly that name. A module whose class is named otherwise never loads there.
- On rolling builds the property, when set, replaces the default: a real `tlc2.overrides.TLCOverrides` on the classpath is not loaded unless the property names it. That is why the default name is added for every entry that holds the class file, in jars too: without it, a project's own `classes/tlc2/overrides/TLCOverrides.class`, or one inside a jar in `lib/`, would stop loading the moment a registered module made tlaup set the property.
- A class that breaks while loading gives message 1000, exit 255, before any state is computed, without naming the class. A class compiled for a newer Java than the one running is refused with message 2173 for an index class and with a 1000 holding `UnsupportedClassVersionError` for a listed class (research 28, Java 11, 21 and 25, both builds, Linux and macOS).

**Decisions this rests on.**

- D35: warn and run. Nothing here raises; a spec whose TLA+ definitions are correct fallbacks must still run.
- The capability `overrides_property` is decided from the jar at install (the manifest has `Build-TimeStamp`) and stored with the build. No version string is compared. The rule is exact only for the two builds decision D19 supports; for builds between them it is a guess, and a user who hits a wrong guess sees TLC's own behaviour.
- The check is domain code: it returns texts and prints nothing. The command prints the preflight's warnings before TLC starts ([39](39-tlc-command.md)); `module add` prints `BuiltModule.warnings` ([31](31-module-commands.md)).

**Points the design leaves open, and what is built** (stage 4's choices; all internal, so none is a user-visible decision).

- *How an entry is known to be a registered module's.* `collect_override_classes` takes only the classpath, and `OverrideClass.module` wants the module's name. Built so: an entry is a registered module's when it lies in a folder that holds a `module.json` ([13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder): `<cache>/module/<name>/classes`, or a jar under its `lib/`), and the name is that folder's name. One more parameter handed in by the preflight (the registry, or a mapping from entry to name) was the other way; it is not taken, because the classpath already says it.
- *What `build_module` checks.* The design says `module add` "runs the same check against the pinned build". The classes are the module's own override classes, declared in its new `classes/` folder, and the classpath is that folder with the module's `lib/` jars and the build's jar. The check runs on the temporary folder before the swap or on the final folder after it, whichever keeps `declared_in` true; the warning text does not show the path.
- *Importing `tlaup.tlc.overrides` from `tlaup.modules.build`.* It is a sideways import between two domain packages; nothing in [00](../design/00-overview.md#packages-after-the-first-wave) forbids it, and the function imported is pure apart from reading class files.

**Traps.**

- A jar is read with `zipfile`; list its names once per jar and do not extract. R7's risk note: one zip directory read per jar on the classpath, once per run.
- The tools jar itself holds `tlc2/overrides/ITLCOverrides.class` and may hold classes under `tlc2/overrides/`; the superclass chain is followed "outside the tools jar". Do not report the tools jar's own classes as a second `TLCOverrides`, unless it really holds a class of that name; check what the fake jar of the tests holds.
- A service file is text written by people: tolerate a trailing comment after a class name only if the tests need it; the design says comments and blank lines are skipped and nothing more.
- `read_class` raises `ValueError` and nothing else for a bad file (M3). Catch exactly that.
- The hint functions take text and return text. They import nothing from `tlaup_parse` and nothing from the reporters, so the reporter can call them without a cycle.
- The class-file version in the JVM's sentence is written `69.0`; the hint shows `69`.

**Known gaps the design postpones.** Making overrides load on v1.7.4 by generating a collecting `TLCOverrides` class: rejected for the first wave. A check before the run that compares the newest class-file version under the project's `classes/` with the running Java: possible later, not taken now, because the hint on 2173 already says what to do. Do not build either.

## Done when

- `tests/unit/tlc/test_overrides.py` and the added cases pass.
- `uv run poe lint` and `uv run poe test` pass; CI is green.
- The changelog is as the Changelog section says for the state of `main` on the day.
- The pull request shows the red run named under Tests, names any choice under Context that it did not follow, and names the inventory rows it owns (M7, R24).

## Out of scope

- Message 2168 into `RunResult.overrides_loaded`, and the warnings 2400, 2402, 2403: [13](13-tlc-parser.md). The golden cases `override-*`: [07](07-golden-files.md), [15](15-golden-expected-results.md).
- When a hint is shown: [38](38-terminal-reporter.md). The verbose header that lists the loaded overrides: milestone 4.
- The feature scenarios (a registered module on v1.7.4 warns on stderr and Java still starts; on rolling the logged property names both classes), printing the warnings, the changelog: [39](39-tlc-command.md).
- `tlaup module add` printing `BuiltModule.warnings`: [31](31-module-commands.md).
- `docs/examples/QueueModule` on both builds: [52](52-integration-tests.md).

## Risks

- From R7: the capability rule is exact only for the two supported builds. The general hint is shown for any early message 1000 when override classes were passed, so it can stand beside an exception with another cause; its wording is conditional for that reason. Research 13 ran Java 25 only.
- From the cut: the two hint functions are here and their caller is in [38](38-terminal-reporter.md); the index makes 38a wait for this package, so the functions exist when 38 calls them.
- From the cut: this package edits a file of package 30 and a file of package 33. Both edits are a few lines at one place.
