# 32. Spec, cfg and project root resolution

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

Four functions turn what the user typed into the paths a run uses: `resolve_spec`, `resolve_cfg`, `config_arg` and `find_project_root`, each with unit tests on real files. The new project-root rule (R10) is in effect at once, because today's `tlaup tlc` already calls `find_project_root`; the other three are called by nothing until the preflight of [33](33-tlc-invocation.md).

## Covers

- Roadmap items ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)):
  - "Pass a `--cfg` file outside the project root to TLC so that TLC reads the file that was validated; today only its name is passed." In part: the functions that find the cfg and compute the `-config` value. The preflight that calls them is [33](33-tlc-invocation.md); the command, the feature scenario and the changelog entries are [39](39-tlc-command.md); the integration test is [52](52-integration-tests.md).
  - "Spec names: a dot in the name is mangled by `with_suffix` (`Foo.v2` becomes `Foo.tla`), `.` raises an error, and any existing file such as a `.cfg` is accepted as the spec." In part: the function and its unit test. The command and the changelog entry are [39](39-tlc-command.md).
  - "The project-root rule counts a parent folder that has `lib/`, `modules/` or `classes/`, so a spec under `~/work` with `~/lib` present runs with `~` as its root ..." In full, apart from the line of the verbose run header that names the root, which is the terminal reporter's ([38](38-terminal-reporter.md)).
- Design sections:
  - [11 R5](../design/11-runner.md#r5-spec-names): all of the design and its unit test.
  - [11 R4](../design/11-runner.md#r4-spec-cfg-and-working-folder): steps 3 (the spec path, links and `..`), 4 (the `-config` value) and 5 (how `--cfg` is found), with the unit tests. Steps 1, 2 and 6 and "What changes for users" are properties of the command line that [33](33-tlc-invocation.md) builds and [39](39-tlc-command.md) switches on.
  - [11 R10](../design/11-runner.md#r10-project-root): all of it.
  - [14 F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay): only the row that says the names `spec`, `modules`, `classes` and `lib` are constants in `tlaup/project/core.py`. The settings themselves are [19](19-layered-config.md).

## Depends on

- [02](02-errors-and-paths.md): `UsageError`, `SpecNotFound`, `CfgNotFound` from `tlaup/errors.py` ([20 G2](../design/20-groundwork.md#g2-domain-errors)), with their `details` argument for the list of paths tried.
- [03](03-test-foundation.md): the isolation fixture (the tests run in a temporary working folder with `HOME` moved), the pytest settings, and the rules of [01 T12](../design/01-testing.md#t12-rules-for-writing-tests).

No change from the draft.

## Files

Creates:

- `src/tlaup/project/spec.py`: `resolve_spec`, `resolve_cfg`, `config_arg`. A file that 00's tree does not list; see "Where the functions live" under Context.
- `tests/unit/spec/test_resolve_spec.py`, `tests/unit/spec/test_resolve_cfg.py`.

Changes:

- `src/tlaup/project/core.py`: `find_project_root` gets R10's rule and the signature below; the folder names become the constants `SPEC_DIR = "spec"`, `MODULES_DIR = "modules"`, `CLASSES_DIR = "classes"`, `LIB_DIR = "lib"` and the tuple of folder names that allow the parent rule (`spec`, `specs`, `test`, `tests`). `_is_project_root` loses its three name parameters.
- `src/tlaup/project/__init__.py`: exports unchanged (`find_project_root`).
- The old callers of `find_project_root`, one line each, so that the old command keeps working with the new signature: `src/tlaup/cmd/tlc.py` (one call, in `tlc`; the second, in `_show_diagnostic_info`, was removed by [04](04-delete-dead-code.md)) and `src/tlaup/tlc/runner.py` (two calls, in `build_tlc_command` and `run_tlc`). Each becomes `find_project_root(spec_file, Path.home())`. Nothing else in those files changes; they are deleted or rewritten by [39](39-tlc-command.md).
- `tests/unit/spec/test_project.py`: rewritten for R10 (see Tests).
- `CHANGELOG.md`: R10's entry.

Deletes: nothing. `resolve_spec_file` and `resolve_cfg_file` in `src/tlaup/tlc/runner.py`, and the old tests that reach them (`tests/unit/spec/test_resolution_scenarios.py`, three tests of `tests/unit/tlc/test_runner.py`), stay until [39](39-tlc-command.md).

Files another package of the same parallel group also touches:

- `src/tlaup/project/core.py`, `src/tlaup/cmd/tlc.py` and `src/tlaup/tlc/runner.py` with [19](19-layered-config.md), if 19 removes the `workspace.*` settings while the old callers still read `config.workspace.modules_dir` and `classes_dir`. The overlap is the same three call lines and the constants; whichever package lands second keeps the form above. With this package merged, the old callers no longer read `workspace.*` for the project root at all.
- `CHANGELOG.md`: one block of lines.

## Interfaces

Provides. R5 and R10 give two of the signatures in their text; the other two, and every keyword argument, are written by stage 4 from what the sections say in words. A worker may adjust a name or a parameter if the behaviour and the tests stay, and says so in the pull request.

```python
# tlaup/project/spec.py
def resolve_spec(text: str, cwd: Path, *, platform: str = sys.platform) -> Path
    # 11 R5; signature from R5, `platform` written by stage 4 (R4 step 3, the Windows rule).
    # Returns an absolute path that ends in .tla and is a file. Links are not resolved.
    # Raises UsageError (empty, ".", "..", or a folder with no candidate) or SpecNotFound (details: the paths tried).

def resolve_cfg(text: str, spec: Path, cwd: Path, project_root: Path | None) -> Path
    # written by stage 4 from 11 R4 step 5. `spec` is resolve_spec's result.
    # Returns the absolute path of the first candidate that is a file. Raises CfgNotFound (details: the paths tried).

def config_arg(cfg: Path, spec: Path, *, platform: str = sys.platform) -> str
    # written by stage 4 from 11 R4 step 4: the text given to TLC as -config, relative to the spec's folder.
    # Reads the disk on Linux and macOS (it resolves links); pure text on Windows.

# tlaup/project/core.py
SPEC_DIR = "spec"; MODULES_DIR = "modules"; CLASSES_DIR = "classes"; LIB_DIR = "lib"

def find_project_root(spec: Path, home: Path) -> Path | None      # 11 R10; signature from R10
```

Behaviour, each point from the linked section:

- **`resolve_spec`** ([R5](../design/11-runner.md#r5-spec-names)). Relative text is read against `cwd`.
  1. Empty, `.` or `..`: `UsageError`, "SPEC must be a TLA+ file or its name".
  2. Text ending in `.tla`: that path must be a file.
  3. Otherwise try, in order, `text + ".tla"` (appended, never `with_suffix`, so `Foo.v2` looks for `Foo.v2.tla`) and `<parent>/spec/<name>.tla`, where `spec` is `SPEC_DIR`.
  4. A path that exists and does not end in `.tla` is never accepted. `Spec.cfg` is `SpecNotFound`, with the hint "did you mean Spec.tla?" when that file exists. A folder is refused only when no candidate of step 3 exists: with a folder `Foo/` and a file `Foo.tla`, the result is `Foo.tla`; with only the folder it is a `UsageError` saying SPEC is a folder.
  5. `SpecNotFound` carries the paths tried as `details`.
  6. The form of the result ([R4](../design/11-runner.md#r4-spec-cfg-and-working-folder), step 3). The path is made absolute as the user gave it; links are never resolved. `..` is removed as text (`os.path.abspath`) when the textual form is the same file as the path with its `..` in place (`os.path.samefile`); otherwise, on Linux and macOS, the path is returned with its `..` in place. With `platform` a Windows value, the textual form is returned only when it names the same file, and anything else is `SpecNotFound`.
- **`resolve_cfg`** (R4, step 5). The name tried is `text` when it ends in `.cfg`, else `text + ".cfg"`; a file named exactly `text` without the suffix is never accepted. If the text is absolute, that one path; otherwise the name is tried beside the spec (`spec.parent`), then in `cwd`, then in `project_root` when there is one. The first that is a file wins. A folder met twice (the spec's folder is also the working folder) is tried once.
- **`config_arg`** (R4, step 4). On Linux and macOS: `os.path.relpath(os.path.realpath(cfg), os.path.realpath(spec.parent))`. With `platform` a Windows value: `os.path.relpath(os.path.abspath(cfg), os.path.abspath(spec.parent))`, no `realpath`; when `relpath` raises because the two are on different drives, the absolute path of the cfg.
- **`find_project_root`** ([R10](../design/11-runner.md#r10-project-root)).
  1. The spec's own folder is the root if it holds `modules/`, `classes/` or `lib/`.
  2. Otherwise the spec's parent folder is the root if it holds one of the three and the spec's folder is named `spec`, `specs`, `test` or `tests`.
  3. A folder is never the root if it is `home` or a filesystem root.
  4. Otherwise `None`.

Consumes: the three error classes of [02](02-errors-and-paths.md). Nothing else from `tlaup`.

Consumers, for orientation: `resolve_tlc_invocation` ([33](33-tlc-invocation.md)) calls all four; `resolve_tool_invocation` ([41](41-sany-command.md)) calls `resolve_spec`.

## Tests that must pass

All plain pytest, real files in `tmp_path`, no mocks ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 1: pure functions given real files). Links are made with `os.symlink`; a test that needs one is skipped with the reason where links cannot be made.

`tests/unit/spec/test_resolve_spec.py`:

- R5's parametrised cases: `Foo`; `Foo.tla`; `Foo.v2` (finds `Foo.v2.tla`, and does not find `Foo.tla`); `dir/Foo`; `Foo` found under `spec/`; `.`; `""`; `..`; `Foo.cfg` (with and without a `Foo.tla` beside it: the hint is there only with it); a folder name alone (`UsageError`); a folder name with a `.tla` file of the same name beside it (the file).
- The seven cases of today's `tests/unit/spec/test_resolution_scenarios.py`, as inputs of the same test (R5: "move here"): `my_model.tla`; `my_model` in the working folder; `my_model` under `spec/`; a missing name; `subdir/my_model`; `subdir/my_model` under `subdir/spec/`; a missing name under an existing `subdir/`. The old file drives the old command through mocks and stays until [39](39-tlc-command.md).
- `SpecNotFound.details` lists every path tried, in order.
- The result is absolute, and a spec reached through a link (a linked folder, and a link to the file) is returned by the path the user named, not by the target's.
- R4 step 3: `../rootproj/spec/Spec` from another folder comes back without the `..` (research 16's row F10, below); a spec path with a `..` after a link (`L/lnk/../proj/Spec.tla` in the link tree below, which the operating system reads as `real/proj/Spec.tla` while the textual form `L/proj/Spec.tla` does not exist) comes back with its `..` in place; the same input with `platform="win32"` is `SpecNotFound`.

`tests/unit/spec/test_resolve_cfg.py`:

- For each of research 16's rows F1 to F14 (the tree and the rows are under Context): the file `resolve_cfg` returns is the row's validated file, and `config_arg`, joined to the spec's folder, is the same file (`os.path.samefile`).
- For each of research 24's rows R1 to R10 (the link tree under Context): the same assertion with the spec's folder reached through a symbolic link, including a cfg outside it reached with `..`.
- With `platform="win32"`: `config_arg` gives the lexical value for each row, compared with values written out by hand in the test (the table under Context has them, with how they were worked out).
- `--cfg foo` with a file `foo` and no `foo.cfg` is `CfgNotFound`; `--cfg foo` with `foo.cfg` finds it; an absolute path without `.cfg` gets the suffix.
- The order: a file of the same name beside the spec, in the working folder and in the project root, removed one at a time, is found in that order.
- `CfgNotFound.details` lists the paths tried.

`tests/unit/spec/test_project.py`, rewritten ([01 T11](../design/01-testing.md#t11-the-existing-tests): "kept until R10"). The call becomes `find_project_root(spec_file, home)` with a `home` under `tmp_path`.

- Kept as they are, apart from the call: `spec_dir_has_classes` (the spec's own folder holds the marker) and `none`.
- Rewritten with the spec's folder named `spec` instead of `subdir`: `parent_has_classes`, `detected_by_lib`, `detected_by_modules`.
- New: the spec in `work/` with `lib/` in the parent (no root); the spec in `tests/` with `modules/` in the parent (root); the parent is the home folder (no root); the spec's folder is the home folder and has `lib/` (no root).

Old tests: `tests/unit/spec/test_project.py` is rewritten in place. The other old tests must stay green with the changed call lines: `tests/unit/spec/test_classpath.py` and `tests/unit/test_tlc_modules_path.py` put their markers in the spec's own folder or use a folder named `spec`, and `tests/unit/tlc/test_raw.py` and `test_runner.py` replace `find_project_root` by name; run them. No stateful test applies.

T12 rule 6: the pull request shows the three rewritten cases of `test_project.py` and the four new ones failing against the old rule before the function is changed.

## Changelog

Written here, because the old `tlaup tlc` calls `find_project_root` and so shows the new rule from this package on:

- Breaking (R10): "A folder is treated as the project root of a spec only if it is the spec's own folder, or its parent when the spec is in a folder named `spec`, `specs`, `test` or `tests`. The home folder is never a project root. A project that keeps specs in a differently named subfolder must move `modules/`, `classes/` or `lib/` beside the specs or rename the subfolder."

Not written here; they describe `tlaup tlc` once it calls the new functions, and [39](39-tlc-command.md) writes them:

- R4: the Fixed entry about `--cfg` outside the project, and the Breaking entry about the folder TLC runs in.
- R5: the Fixed entry about spec names.

## Context for the worker

**State of `main` when this starts.** After 01 to 03 (and perhaps 04, 19 and others of the parallel groups): release 0.8.x code. `tlaup tlc` runs through `src/tlaup/tlc/runner.py`, which has its own `resolve_spec_file` and `resolve_cfg_file` and calls `tlaup.project.find_project_root(spec_file, modules_dir=..., classes_dir=...)`. Read the three call sites as they are on the day; [04](04-delete-dead-code.md) and [19](19-layered-config.md) may have edited them.

**Where the functions live** (decided by stage 4). 00's tree names `tlc/invocation.py` for the preflight and no home for these functions; [14 F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay) puts the folder-name constants in `tlaup/project/core.py`, and [40](../design/40-later-milestones.md#milestone-3-reproducibility) says `find_project_root` keeps its signature when milestone 3 changes its body. So the project package stays: `core.py` keeps `find_project_root` and the constants, and `spec.py` is new beside it. Not under `tlc/`, because `sany` and `pcal` call `resolve_spec` too ([21](../design/21-other-tools.md)) and should not import the TLC runner's package.

**Why this package edits old code, when a domain package normally does not.** The cut's rule is "build beside, then switch". For `resolve_spec`, `resolve_cfg` and `config_arg` that holds: they are new names and nothing calls them. `find_project_root` is different: R10 changes the rule of a function that exists, T11 says its test file is kept and rewritten at R10, and a second function of the same name beside the old one would have to be moved again at the switch. So the function is changed in place and its three old callers get the new call. The consequence is wanted and is in the changelog: the old command follows the new rule from here on. The old runner uses the root for three things (the working folder of TLC, the spec argument relative to it, the classpath), and with fewer folders counting as a root it falls back to the spec's folder, as it does today for a spec with no root.

**Decisions this rests on.**

- D34: TLC runs where tlaup was started, with the spec as an absolute path and the cfg relative to the spec's folder. TLC takes the folder of an absolute spec as its base folder, which is why the form of the path matters.
- D14: no alias or shim. The old keyword arguments of `find_project_root` go; nothing keeps them readable.
- D15: no Windows CI. The two Windows rules are reachable on Linux through the `platform` argument, and that is the only reason the argument exists.
- The design agent's decisions listed in the design README: links in a spec path are not resolved; `--cfg` accepts only names ending in `.cfg`; the project root is the spec's folder or its parent under the four names, never the home folder.

**Why links are not resolved.** TLC never resolves links: it builds paths from the spec path it is given and hands them to the operating system. So modules and the default cfg are found beside the path the user named, also when the spec is itself a link to a file. Resolving the spec's path would make TLC search beside the link's target, and a spec linked into a project would lose the project's modules.

**Why the `-config` value is computed from resolved paths on Linux and macOS, and from the typed paths on Windows.** The operating system follows links when it walks `..`. A relative path from the resolved form of the spec's folder to the resolved form of the cfg therefore names the validated file with or without links. Windows collapses `..` as text before it follows a link, so there the lexical form is the one that names the file Windows itself opens. An absolute `-config` is not used: on v1.7.4 it fails when the spec is absolute too and the cfg is outside the spec's folder.

**Why only `.cfg` names.** TLC strips a trailing `.cfg` from `-config` and adds it again, so a file without the suffix could be validated by tlaup and then not be the file TLC opens.

**Research 16's tree and rows** (restated; a worker does not read the research). Under one temporary folder `<T>`:

```
proj/Spec.tla  proj/Spec.cfg  proj/a.cfg  proj/sub/a.cfg  proj/cfgs/b.cfg  proj/my cfgs/with space.cfg
outside/out.cfg
work/Spec.cfg  work/a.cfg  work/sub/a.cfg
rootproj/lib/  rootproj/modules/            (so rootproj is the project root of a spec in rootproj/spec/)
rootproj/spec/Spec.tla  rootproj/spec/Spec.cfg  rootproj/spec/sib.cfg
rootproj/cfgs/x.cfg  rootproj/root.cfg  rootproj/out.cfg  rootproj/my cfgs/sp.cfg
```

`rootproj/out.cfg` is a decoy with the name of the outside file. Give each cfg different content so a test can also tell files apart by reading them. The rows are the commands the research ran against release 0.8.x, where rows F5, F7, F8 and F12 read another file of the same name and F11, F13 and F14 found none. The last two columns are what the new rules give; stage 4 worked them out by hand from R4's steps, and the test's assertion is the design's (`samefile`), not these strings.

| Row | Working folder | Spec typed | `--cfg` typed | Validated file | `-config` value |
| --- | --- | --- | --- | --- | --- |
| F1 | `rootproj` | `spec/Spec` | `sib` | `rootproj/spec/sib.cfg` | `sib.cfg` |
| F2 | `rootproj` | `spec/Spec` | `cfgs/x.cfg` | `rootproj/cfgs/x.cfg` | `../cfgs/x.cfg` |
| F3 | `rootproj` | `spec/Spec` | `my cfgs/sp.cfg` | `rootproj/my cfgs/sp.cfg` | `../my cfgs/sp.cfg` |
| F4 | `rootproj` | `spec/Spec` | `../outside/out.cfg` | `outside/out.cfg` | `../../outside/out.cfg` |
| F5 | `rootproj` | `spec/Spec` | `<T>/outside/out.cfg`, and the same without `.cfg` | `outside/out.cfg` | `../../outside/out.cfg` |
| F6 | `rootproj` | `spec/Spec` | `out` | `rootproj/out.cfg` | `../out.cfg` |
| F7 | `work` | `<T>/rootproj/spec/Spec` | `<T>/outside/out.cfg` | `outside/out.cfg` | `../../outside/out.cfg` |
| F8 | `work` | `<T>/rootproj/spec/Spec` | `../outside/out.cfg` | `outside/out.cfg` | `../../outside/out.cfg` |
| F9 | `work` | `<T>/rootproj/spec/Spec` | `<T>/rootproj/cfgs/x.cfg` | `rootproj/cfgs/x.cfg` | `../cfgs/x.cfg` |
| F10 | `work` | `../rootproj/spec/Spec` | none | none; the spec is `<T>/rootproj/spec/Spec.tla` | none |
| F11 | `proj` | `Spec` | `../outside/out.cfg` | `outside/out.cfg` | `../outside/out.cfg` |
| F12 | `work` | `<T>/proj/Spec` | `sub/a.cfg` | `proj/sub/a.cfg`, not `work/sub/a.cfg` | `sub/a.cfg` |
| F13 | `proj` | `Spec` | `my cfgs/with space.cfg` | `proj/my cfgs/with space.cfg` | `my cfgs/with space.cfg` |
| F14 | `proj` | `Spec` | `cfgs/b` | `proj/cfgs/b.cfg` | `cfgs/b.cfg` |

**Research 24's link tree and rows** (restated). Under `<T>`:

```
real/proj/Spec.tla  real/proj/Spec.cfg  real/proj/sub/a.cfg  real/out.cfg  real/other/o.cfg
outside/o.cfg
L/lnk -> ../real/proj        L/out.cfg            (a decoy: the lexical reading of L/lnk/../out.cfg)
deep/a/b/Spec.tla  deep/a/b/Spec.cfg  deep/a/out.cfg  deep/out.cfg
L2/lnk -> ../deep/a/b        L2/out.cfg           (a decoy)
Lf/Spec.tla -> ../real/proj/Spec.tla   Lf/Spec.cfg
work/out.cfg
```

The spec is typed through the link. The third column is what R4's expression gave on Linux and macOS in the research, and TLC read the validated file in all twenty runs (ten rows, two builds). The fourth is the lexical value for `platform="win32"`, worked out by hand by stage 4 from the rule (`relpath` of the two paths as typed, `..` collapsed as text); the research ran that form on Windows and found it right in every row where the file exists, but did not record the strings.

| Row | Spec typed | Cfg validated, as typed | `-config` on Linux and macOS | Lexical value (Windows rule) |
| --- | --- | --- | --- | --- |
| R1 | `L/lnk/Spec.tla` | `L/lnk/../out.cfg` (the file `real/out.cfg`) | `../out.cfg` | `../out.cfg` (by Windows' reading the file `L/out.cfg`) |
| R2 | `L/lnk/Spec.tla` | `L/out.cfg` | `../../L/out.cfg` | `../out.cfg` |
| R3 | `L2/lnk/Spec.tla` | `L2/lnk/../out.cfg` (the file `deep/a/out.cfg`) | `../out.cfg` | `../out.cfg` (by Windows' reading `L2/out.cfg`) |
| R4 | `L2/lnk/Spec.tla` | `L2/lnk/../../out.cfg` (the file `deep/out.cfg`) | `../../out.cfg` | `../../out.cfg`; on a real Windows the typed path collapses to `<T>/out.cfg`, which does not exist, so `resolve_cfg` has already said `CfgNotFound` |
| R5 | `L2/lnk/Spec.tla` | `L2/out.cfg` | `../../../L2/out.cfg` | `../out.cfg` |
| R6 | `L2/lnk/Spec.tla` | `work/out.cfg` | `../../../work/out.cfg` | `../../work/out.cfg` |
| R7 | `L2/lnk/Spec.tla` | `outside/o.cfg` | `../../../outside/o.cfg` | `../../outside/o.cfg` |
| R8 | `L/lnk/Spec.tla` | `real/proj/sub/a.cfg` | `sub/a.cfg` | `../../real/proj/sub/a.cfg` |
| R9 | `Lf/Spec.tla` (a link to the file) | `real/out.cfg` | `../real/out.cfg` | `../real/out.cfg` |
| R10 | `real/proj/Spec.tla` (no link) | `outside/o.cfg` | `../../outside/o.cfg` | `../../outside/o.cfg` |

In R9 the spec's folder is `Lf/`, the folder of the link itself, and TLC joins the value to that same folder. On Linux the Windows column can only be compared as text: the files it names by Windows' reading are not the files Linux reaches.

**Points the design leaves to the worker.** None of them is needed by a listed test; say in the pull request what was chosen.

- Whether `find_project_root` compares a folder with `home` and with the filesystem root by text or by file identity. Stage 4's reading: by identity (`samefile` or resolved paths), so that a home folder reached through a link is still refused; the root that is returned is built from the spec path as given, with no link resolved, to match R4 step 3.
- Whether the four folder names of rule 2 are compared case-sensitively. Stage 4's reading: exactly as written, lower case.
- An empty `--cfg` value. The design names no rule; it must not be a traceback.

**Traps.**

- `Path.with_suffix` is the defect R5 removes; build candidates with string concatenation on the name.
- `os.path.abspath` collapses `..` as text and does not touch the disk; `Path.resolve` and `os.path.realpath` follow links. Step 6 of `resolve_spec` needs the first, `config_arg` on Linux and macOS needs the second, and mixing them up passes every test that has no link in it.
- `os.path.samefile` raises when a path does not exist; the textual form of a spec path with `..` after a link may not exist.
- The cross-drive case of `config_arg` cannot be reached on Linux (`os.path.relpath` never raises there). It is inferred, not run, and not unit-tested; the design says so.
- The functions print nothing and read no environment: `cwd` and `home` are arguments ([00](../design/00-overview.md#packages-after-the-first-wave)).

## Done when

- The three test files pass, with the F and R rows as parametrised cases; the old unit tests still pass.
- `uv run poe lint` and `uv run poe test` pass; CI is green.
- R10's changelog entry is under `## [Unreleased]`, Breaking.
- The pull request shows the red run of the rewritten and new `test_project.py` cases (T12 rule 6), and names any signature it adjusted.

## Out of scope

- The preflight that calls these functions, `TlcInvocation.config_arg`, the warning for a non-ASCII path under a locale that is not UTF-8: [33](33-tlc-invocation.md).
- Deleting `resolve_spec_file`, `resolve_cfg_file` and their old tests; the feature scenario with a decoy `out.cfg`; the changelog entries of R4 and R5: [39](39-tlc-command.md).
- The integration test of R4 with real TLC on both builds, including the link rows: [52](52-integration-tests.md).
- `ClasspathResolver` and what it does with the root: [30](30-module-build.md) and [33](33-tlc-invocation.md).
- The project file as the root marker: milestone 3.

## Risks

- From R10: layouts such as `project/models/Spec.tla` with `project/lib/` stop finding the root; the changelog says what to do. Because of the cut this reaches the old command at once, before the rest of the runner changes.
- From R4: the Windows cross-drive case is inferred, not run; the Windows rules of steps 3 and 4 were checked on a hosted runner by the research, not by tlaup's own CI (D15).
- From R5: a user who passed a spec file with another suffix can no longer do so; TLC itself requires `.tla`.
- From the cut: the hand-written Windows values in the second table are stage 4's arithmetic, not a recording. A worker who finds one wrong against the rule corrects the table's value in the test and says so.
- From the cut: `src/tlaup/project/core.py` and the three call lines may be edited by [19](19-layered-config.md) at the same time.
