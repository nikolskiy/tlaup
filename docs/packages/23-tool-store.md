# 23. Tool store

Size: M. Suggested model: most capable. Status: built.

The size is at the upper end of M: one class with its lock and temporary folders, the order and lookup rules, the printed form, and about forty unit tests and one property test.

## Goal

`tlaup.versioning.store` holds the one class that reads and writes installed builds, the pin and the store lock, with the step-level functions the formal check fixed; `tlaup.versioning.order` sorts builds; `format_build` prints a build in a form that can be typed back. All of it is tested on real files and real locks in a temporary folder. No command uses it yet, and the old code is untouched.

## Covers

- Roadmap items:
  - "Version identity as a type, not a parsed folder name. Typed metadata is the source of truth, with one writer, one reader and a schema version. One version store ..." ([milestone 3](../roadmap.md#milestone-3-reproducibility); pulled forward by D37), in part: the store itself. Package 27 builds install, upgrade, uninstall and pin on it and package 29 puts the commands on it.
  - "Concurrent installs: write the pin and metadata atomically and take a lock ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: atomic writes, the store lock, `StoreLocked`, the temporary folders and their cleanup. Two installs racing as a whole is package 27.
  - "Download to a temporary file, check it is a valid jar, then rename. A folder without a jar and its metadata does not count as installed ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the second sentence, and the rename into place. The download is package [26](26-download-and-verify.md).
  - "Remove the legacy fallback jar path ... A pin that points at a missing build is a clear error with a hint, not a silent fallback." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: `pinned()` raises `PinnedBuildMissing`. Package [04](04-delete-dead-code.md) removed the fallback; packages 29 and 33 show the error.
  - "Typing versions ..." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)), in part: lookup of a spec among installed builds and the printed form. Parsing is package [22](22-version-spec-and-jarinfo.md); the commands are package 29.
  - "Adopt upstream's `rolling` release ... `rolling` must sort correctly although it has no version number." ([milestone 3](../roadmap.md#milestone-3-reproducibility)), in part: the order of builds. `stable_of` over releases is package [25](25-remote-listing.md); one build with two names stays a milestone 3 item.
- Design sections:
  - [12 V1](../design/12-tools-and-downloads.md#v1-version-store): everything that is in `store.py` (`Build`, `Source`, `ToolStore`, `TmpFolder`, the layout on disk, the id rule, "already there", `build.json`, atomic writes, the lock, the pin, and the step-level functions `acquire`, `release`, `new_tmp`, `clean_tmp`, `move_out`, `delete_out`), with V1's unit tests. The step classes of `install.py` (`Install`, `Upgrade`, `Uninstall`, `Pin`), the rule "what a mutation decides on is read under the lock" as far as the commands follow it, and the stateful test are package 27.
  - [12 V2](../design/12-tools-and-downloads.md#v2-version-order-and-lookup): `version_key`, `sort_key`, `ToolStore.find`. `stable_of` is package 25. The deletion of `resolve_latest_version` is package 29.
  - [02 X3](../design/02-cross-cutting.md#x3-version-syntax): `format_build`, the printing table, its unit tests and the Hypothesis round trip. Parsing was package 22.
  - [02 X4](../design/02-cross-cutting.md#x4-rolling): "How it sorts", for installed builds, and `stable` among installed builds.
  - [12 V11](../design/12-tools-and-downloads.md#v11-concurrent-installs): the parts that are the store's own: the store lock and its timeout, the lock file beside each temporary folder, the cleanup of leftovers, and their unit tests. The rest of V11 is package 27.
- The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md): rows T4 (an empty pin file is no pin; the store half, [27](27-install-steps.md) the `install` half), T14 (two builds of one tag side by side) and T30 (a pinned folder with no jar is `PinnedBuildMissing`), whose owner this package is.

## Depends on

- [22](22-version-spec-and-jarinfo.md): `VersionSpec` (the argument of `find`), `parse_version_spec` (the round-trip test), `JarInfo` and `read_jar` (the argument of `add`, and the test jars), and the small-jar helper in `tests/unit/versioning/conftest.py`.
- [02](02-errors-and-paths.md): `AppPaths` with its derived paths `tools` and `pin` ([14 F2](../design/14-config-and-cli.md#f2-folder-overrides)); `StoreLocked`, `PinnedBuildMissing`, `FileOperationError` from `tlaup.errors`.
- [03](03-test-foundation.md): the isolation fixture; `hypothesis` as a development dependency and its CI profile; the pytest settings.

The draft named only 22. 02 and 03 are added because this package uses them directly.

## Files

Creates:

- `src/tlaup/versioning/store.py`
- `src/tlaup/versioning/order.py` (`version_key`, `sort_key`; package 25 adds `stable_of`)
- `tests/unit/versioning/test_store.py`, `test_order.py`, `test_format_build.py`, `test_format_build_props.py`

Changes:

- `src/tlaup/versioning/spec.py`: adds `format_build`. It needs `Build` for its annotations only; import it under `TYPE_CHECKING`, since `store.py` imports `VersionSpec` from this module.
- `pyproject.toml`: `filelock>=4.2.1` among the runtime dependencies, with no upper cap (D59, [30 B2](../design/30-ci-and-release.md#b2-build-fixes)). `uv.lock` follows; `filelock` 4.2.10 is already in the lock file as a dependency of a development tool, so the lock changes little.
- `tests/unit/versioning/conftest.py`: what the store tests add to the jar helper, if anything.

Shared with other packages: the `filelock` line in `pyproject.toml` and the lock file. Packages 30 (the module folder's lock) and 35 (run folders) need the same line; whichever merges first adds it and the others find it there. It is one line. `spec.py` is also 22's, but 22 is finished before this starts.

Must not touch: the old modules `versioning/api.py`, `downloader.py`, `metadata.py`, `paths.py`, `resolver.py`, `schema.py`, `versioning/__init__.py`, `cmd/tools/`, and everything under `tests/stateful/`. Their old tests went in 03b (decision D62); the ordering cases of the old `test_resolution.py`, rewritten for D32, are this package's `test_order.py`. No new module name collides with an old one: `store.py` and `order.py` are new; the old `versioning/paths.py` is not `tlaup/paths.py`.

Deletes: nothing.

## Interfaces

Provides, from [12 V1](../design/12-tools-and-downloads.md#v1-version-store) (copy; the section has the full text):

```python
# tlaup/versioning/store.py
@dataclass(frozen=True)
class Build:
    id: str                       # the folder name; opaque outside the store
    name: str                     # "v1.7.4", "rolling"
    commit: str | None            # 40 hex digits, from the jar's manifest; None if the jar has none
    calver: str | None            # "2026.11.15.002146", None when the jar has no Build-TimeStamp
    built_at: str | None          # the manifest's Build-TimeStamp
    sha256: str
    size: int
    prerelease: bool
    source: Source                # where it came from
    installed_at: str             # UTC, ISO 8601 with Z
    capabilities: frozenset[str]  # 00, "What a build can do"
    path: Path                    # the build's folder
    @property
    def jar(self) -> Path

@dataclass(frozen=True)
class Source:
    kind: str                     # "github-release" in the first wave
    url: str                      # the asset's download address as the release gave it; never a redirect's signed address
    asset_id: int | None
    asset_updated_at: str | None
    digest_checked: bool          # the download was compared with GitHub's digest

class TmpFolder:                                           # a folder under .tmp/ and the lock file beside it (V11)
    path: Path
    def lock(self) -> None                                 # create the lock file and take its lock
    def make(self) -> None
    def discard(self) -> None                              # delete the folder
    def release(self) -> None                              # remove the lock file, then release the lock

class ToolStore:
    def __init__(self, paths: AppPaths, *, now: Callable[[], datetime]): ...
    def builds(self) -> list[Build]                       # sorted by 02 X4
    def find(self, spec: VersionSpec) -> list[Build]      # V2
    def pinned(self) -> Build | None                      # raises PinnedBuildMissing
    def add(self, jar: Path, info: JarInfo, *, name: str, prerelease: bool,
            source: Source, repair: bool = False) -> Build
    def update(self, build: Build, *, prerelease: bool, source: Source) -> Build    # rewrites build.json only
    def remove(self, build: Build) -> None                # move_out, then delete_out
    def pin(self, build: Build) -> None
    def unpin(self) -> None
    @contextmanager
    def locked(self, timeout: float = 60.0) -> Iterator[None]    # acquire and release; raises StoreLocked
    def acquire(self, timeout: float = 60.0) -> None       # raises StoreLocked
    def release(self) -> None
    def new_tmp(self) -> TmpFolder
    def clean_tmp(self) -> None                            # V11
    def move_out(self, build: Build) -> TmpFolder | None   # one rename; None if the build has gone
    def delete_out(self, out: TmpFolder) -> None
```

On disk, under `AppPaths.tools`, which is `<cache>/tool/` (D47):

```
<cache>/tool/
    .lock
    pin                         one line: a build id
    <build-id>/
        tla2tools.jar
        build.json              {"schema": 1, ...the fields of Build except id and path}
    .tmp/
        <random>/               one download, or one removed build
        <random>.lock           held by the tlaup that owns the folder
```

From [12 V2](../design/12-tools-and-downloads.md#v2-version-order-and-lookup) and [02 X3](../design/02-cross-cutting.md#x3-version-syntax):

```python
# tlaup/versioning/order.py
def version_key(tag: str) -> tuple | None          # (1, 7, 4, suffix_rank, suffix) or None if not a number
def sort_key(build: Build) -> tuple                # rolling first, then version_key descending, then build time

# tlaup/versioning/spec.py
def format_build(build: Build, others: Sequence[Build] = ()) -> str
    # the printing table; `others` is every installed build, and only those with the build's name are looked at
```

Package 25 sorts releases by the same rule for names (`rolling`, then numbers highest first, then other names). Write the part of `sort_key` that orders names as a function of the tag alone, so that 25 can use it for releases without a second copy of the rule.

Consumes: `VersionSpec`, `parse_version_spec`, `JarInfo`, `read_jar` (22); `AppPaths`, the three error classes (02).

Used later by: packages 25 (`order.py`), 26 (a `TmpFolder` as the download's folder), 27 (everything), 28, 29, 33 (`store.pinned()` in the preflight), 46 (`doctor`), 52 (copying a jar into the store, [01 T9](../design/01-testing.md#t9-integration-tests)).

## Tests that must pass

Plain pytest and one property test, all on a store in `tmp_path` with small real jars and real `filelock` locks. No mocks ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests)).

`tests/unit/versioning/test_store.py`, V1's list:

- add, then list; a folder without `build.json` is not a build; a `build.json` with `"schema": 99` is not a build; a jar without metadata is not a build.
- pin, unpin; `pinned()` is `None` with no pin file and raises `PinnedBuildMissing` when the build's folder is removed, and when the pinned build's folder holds no jar (inventory row T30).
- An empty `pin` file, and one holding only a newline, give `pinned()` `None`; `pin(build)` on that store writes the build's id over it (inventory row T4, owner this package; [12 V1](../design/12-tools-and-downloads.md#v1-version-store)). That `Install` pins its build over an empty pin file, the other half of T4's test, needs `install.py` and is [27](27-install-steps.md)'s.
- ids for a tag with a hyphen and a slash (no character outside `[A-Za-z0-9._-]` in the folder name).
- two builds of one commit with different CalVers coexist; two different jars with the same name, the same commit and no build time coexist (these two cases are the test of inventory row T14, owner this package); a jar with no commit is stored with `commit` null and an id like any other.
- the same jar under two names gives two builds; the same jar under `a-b` and then `a_b` gives two builds with two ids.
- `add` when a folder with no `build.json`, with an unparsable one, and with `"schema": 99` already sits at the first id: each time that folder is untouched and the build lands at the next id (`-2`).
- two jars made to agree in 12 digits coexist (the id function takes the prefix length as a parameter, and the test gives it a shorter one).
- adding the same name and bytes twice returns the first build and leaves one folder; with `repair=True` the jar on disk is replaced.
- `add` without the lock held fails; so do `update`, `remove`, `pin` and `unpin`.
- after `remove`, nothing of the build is left under the tool folder outside `.tmp/`, also when the delete step is made to fail (for example by making the moved-out folder's content read-only; skipped with the reason when the suite runs as root).
- `update` rewrites `build.json` only: the jar's bytes and the id are unchanged.
- `build.json` and `pin` are complete after every write: a reader that lists while a second store object adds never sees a folder without both files (a plain test that interleaves the calls, not a race).
- an unreadable pin file (for example a folder named `pin`) is `FileOperationError` (code 5) naming the file ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks), last bullet of its notes); [29](29-tool-commands.md)a has its scenario.

The store's part of V11, in the same file:

- A second Python process holds the store lock; `acquire` with a short timeout raises `StoreLocked`, and the message names the lock file. The same with a second `ToolStore` object in the test process: it is refused, and refuses, like the other process. (The stateful test has this check too, but it cannot run before package 27.)
- A temporary folder whose lock is held by a second process survives `clean_tmp`, whatever its age; one whose lock is free is removed with its lock file, whatever its age.
- A lock file with no folder survives `clean_tmp` at 59 minutes and is removed at 61. The age is the difference between the injected `now` and the file's time; the test moves `now`, not the file's time.

`tests/unit/versioning/test_order.py`, V2 and X4 (this replaces the ordering cases of the old `test_resolution.py`, without modification times):

- `rolling` sorts above every numbered name; numbered names by number, highest first; `v1.5.0rc1` below `v1.5.0`; a name that is neither sorts last, by name.
- builds of one name by build time, newest first; a build with no build time after those that have one, then by install time.
- `find`: a tag as typed and with `v` added; `stable` is the highest-numbered name whose builds are not prereleases, and is empty when every build is one; `rolling`; a commit prefix, a CalVer and a `sha256:` prefix after `@` narrow the list; a bare CalVer matches across names; a build with no commit matches its bare name and never a `@commit`; the result is newest first; nothing matching gives an empty list.

`tests/unit/versioning/test_format_build.py`, X3: one test per row of the printing table, including two commits that share seven digits (the prefix grows), a build with no commit beside one with a commit, and two builds of one name and commit with no build time (`name@sha256:` with 12 digits, more when two share them).

`tests/unit/versioning/test_format_build_props.py`, X3's round trip, with Hypothesis: for every build `b` of a generated store, `store.find(parse_version_spec(format_build(b, store.builds())))` is exactly `[b]`, with no exception. The generator makes what a store can hold: names that fit the `tag` grammar and are not `stable`, `latest` or of CalVer shape; no two builds with the same name and SHA-256; commits, build times and SHA-256 values drawn from small pools, so that shared commits, shared seven-digit prefixes, shared build times and shared twelve-digit SHA-256 prefixes all occur; builds with no commit, with no build time, and with neither. The first run's Hypothesis statistics are quoted in the pull request ([01 T7](../design/01-testing.md#t7-property-tests-for-values), Risks, applies here too).

The stateful test. `tests/stateful/test_tool_store.py` mirrors the checked spec on the step functions, and its `tlaup_impl` imports `tlaup.versioning.install`, `remote` and `jarinfo` beside the store. Until package 27 has written `install.py` (and 25 `remote.py`) it cannot be imported, so **this package removes no `pending` marker and does not delete `tests/stateful/reference_store.py`**; package 27 does both as the first commit of 27a. Meanwhile the store is tested by the unit tests above, which cover each step function alone, and by the second-process lock test. Read the stateful test before writing the store all the same: it shows exactly how the steps are called (`acquire(timeout=0)`, `new_tmp()`, `tmp.path`, `builds()`, `pinned()`, `build.id`, `build.jar`, `build.sha256`), and the store must fit it unchanged.

About `filelock` and the reference-model tests. `tests/stateful/test_tool_store.py` and `test_run_folders.py` skip themselves when `filelock` cannot be imported. In the development environment it already can: `filelock` 4.2.10 is in `uv.lock` today as a dependency of a development tool. So their `..._reference_model` tests have been running since package 03 added `hypothesis`, not since this package. What changes here is that they no longer rest on another tool's dependency. If they do not run on `main` when this package starts (check the test run's skip reasons), they start with this package's first commit, and a failure then is a finding to report in the pull request, not a test to edit: the machines are reviewed artefacts of the formal check (03b fixed the `ResourceWarning`s that `filterwarnings = error` gave them, question Q17, without changing what they check).

Old tests: none is left (03b). The pull request names the inventory rows it owns, each with its test: T4 (its store half), T14 and T30 (findings F1 and G1 of the [second review](review-2026-11-24.md)).

## Changelog

None. V1's entry (Breaking: "Installed tools are stored in a new layout with a `build.json` beside each jar. They live in the cache's `tool` folder (was `tools`) ...") describes what a user sees once the commands use the store; package 29 writes it, with X4's "`rolling` is listed first in `tlaup tool list`, then versions by number."

## Context for the worker

Decisions:

- D37: the store is built in milestone 1; milestone 3 keeps `ToolStore`'s interface and changes the layout beneath it. That is why the id is opaque and every path comes from `AppPaths`.
- D46: the design was checked as `specs/ToolStore.tla` before any code. The step functions are the spec's actions, so their boundaries are fixed: `move_out` is exactly one rename, `delete_out` the deletion, `acquire` and `release` are apart. [The specs' README](../../specs/README.md#toolstore) says what was modelled and what was not (the `-2` suffix rule, `--force`, the lock files under `.tmp/` as files).
- D47: the folder is `<cache>/tool/`.
- D59: `filelock>=4.2.1`, uncapped. Earlier versions unlink the lock file on release (3.20.4 to 3.29.4) or change its modification time when locking (3.29.5 to 4.2.0), and the one-hour rule for lock files reads that time.
- D50: an uninstall killed between its two steps can leave a pin that names a removed build. The store's part is only that `pinned()` then raises `PinnedBuildMissing` and never falls back.
- The empty pin file (inventory row T4, [12 V1](../design/12-tools-and-downloads.md#v1-version-store)): an empty `pin`, or one holding only white space, is "nothing pinned" for every reader, as 0.8.x has it; strip the text before reading the id.
- D14: no migration. The old layout lived in `<cache>/tools/`; the new store never reads it.
- D15: no Windows CI. The id has no character that is invalid on Windows; writes use `os.replace`; on Windows a folder holding a jar that a running JVM has open cannot be renamed, and `remove` then fails with `FileOperationError` and the build stays. Not tried on Windows.

The rules a worker could miss (all in V1; stated here because each was once wrong in the design):

- **The id is made by the store and read by nobody else.** The name with every character outside `[A-Za-z0-9._]` replaced by `_`, then `-`, then the first 12 hexadecimal digits of the jar's SHA-256. Nothing splits an id again and nothing finds a build by working out its id.
- **An id only has to be free.** When the first candidate exists, whatever it is, try the same text with `-2`, `-3`, and take the first that does not exist. Never replace, repair or delete a folder that was not read as the very build being added.
- **"Already there" is decided by content**: the same `name` and the same full `sha256` among `builds()`, never by the id. Then the temporary copy is discarded and that build returned; with `repair=True` its jar is first replaced with `os.replace` and its `build.json` rewritten the same way. The store never holds two builds with the same name and SHA-256, which `format_build`'s last row relies on. One jar under two names is two builds.
- **`build.json` is the truth.** One function writes it and one reads it; both check `schema`. A folder is a build only if it holds a jar and a readable `build.json` with a known schema; everything else is ignored by `builds()`.
- **Writes are atomic**: a temporary file in the same folder, then `os.replace`. A build folder is complete under `.tmp/` before one rename puts it in place. `remove` renames the folder into `.tmp/` first and deletes it there.
- **Mutations require the lock and assert it; reads never lock.** A reader can list a build and find its jar gone a moment later; that is known and stays ([finding K2-3](../../specs/README.md#findings)).
- **`add` takes the jar's path inside a temporary folder** and moves that folder, with the `build.json` it writes into it. The `TmpFolder` object and its lock stay with the caller, who releases it afterwards.
- **The lock.** `<cache>/tool/.lock`, a `filelock.FileLock`. Never waited for without a timeout: with no timeout a second lock object in the same thread raises `RuntimeError("Deadlock ...")` since `filelock` 3.29.6; with a finite timeout the same case gives `Timeout`, which is `StoreLocked`. A lock is taken and released in one thread, since `FileLock` objects are thread-local. Each `ToolStore` object has its own lock object; a second object in one process is refused like another process, which is what lets the stateful test stand for several tlaups.
- **Temporary folders.** The lock file `.tmp/<random>.lock` is created and locked before the folder is made, so there is no moment at which the folder exists unlocked. `clean_tmp` tries each folder's lock without waiting: got it, the owner is gone and folder and lock file are removed; not got, it is left alone. No age is involved for folders. A lock file with no folder is removed only when it is more than one hour old and while the cleanup holds its lock. `TmpFolder.release` removes the lock file as the last thing before releasing.
- **`now` is injected.** `installed_at` and the age of a lock file come from it; nothing reads the clock ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges), Time).
- **No printing.** The store returns values or raises `TlaupError` subclasses ([00](../design/00-overview.md#packages-after-the-first-wave), the rules under the tree).

`tests/stateful/reference_store.py` is a throwaway model of the same step functions, written to try the test. It shows one way to arrange the locks and renames in about 350 lines. It is not the design: it has no `build.json` schema, no id rule, no `find`, no `repair`. Where it and V1 differ, V1 is right.

`find`, from V2 and X4: `stable` gives the builds of the highest-numbered name whose builds are not prereleases; a build's `prerelease` flag is the one recorded at install and is not looked up again, so `stable` among installed builds can lag behind upstream (X4 says so and accepts it). Zero results and several results are the caller's to judge (`VersionNotFound`, asking, or `AmbiguousVersion`); `find` raises neither.

`format_build`: the four rows are tried in order, and "another build" always means another installed build of the same name. The form depends on what else is installed, so a printed form can match two builds after another install; that is by design.

Not in V1's interface, and not to be added on a guess: a listing of leftover folders for `tlaup doctor` (V1 says doctor reports them). Package 46 adds what it needs.

State of `main` when this starts: the 0.8.x code with packages 01 to 03 and 22 on top. `tlaup/paths.py` (package 02) has `AppPaths`; the old `versioning/paths.py` and the old layout functions still exist and still serve the old commands. The new store and the old code share no folder and no file.

## Done when

- The tests above pass, the property test with the CI profile; `uv run poe lint` and `uv run poe test` pass; CI is green.
- `filelock>=4.2.1` is a runtime dependency and `uv.lock` is updated with `uv lock`.
- `tests/stateful/` is unchanged and its reference-model tests pass.
- No file listed under "Must not touch" is in the diff.
- The pull request quotes the Hypothesis statistics of the round-trip test and says how the delete step is made to fail in the `remove` test.
- The pull request names inventory rows T4 (the store half), T14 and T30, each with its test.

## Out of scope

- `install.py`: `Install`, `Upgrade`, `Uninstall`, `Pin`, `install()`, `same_as_published`, `upgrade()`, `uninstall()`, `pin()` (V12, V3, V4), the rest of V11 (two installs at once, nothing left under `.tmp/` after a command), the stateful test and the deletion of the reference model: package 27.
- The first-run prompt (V9): package 28. The `tool` commands, their feature files, the deletion of the old modules and the changelog entries: package 29.
- `stable_of` and the order of releases: package [25](25-remote-listing.md).
- `tool list`, `tool current`, `tool path`, `doctor`: packages 29 and 46.
- Moving tools to the data folder, one build with two names, a level for other distributions: milestone 3.

## Risks

- From V1: a layout break now and another in milestone 3; both land in 0.9.0, so users reinstall once. On Windows, renaming a folder whose jar is open fails; the wanted outcome (`FileOperationError`, the build stays) was not tried.
- From V11: a lock on a network file system may not behave as on a local disk; the cache folder is expected to be local. Not tried.
- From 03: the tests interleave at step boundaries only. A race inside one step (the two system calls of a rename) is outside the spec and the tests.
- From the cut: the stateful test, which is this code's "test first", cannot run until package 27. A mistake in a step function that only an interleaving shows is found one or two packages later. The unit tests of each step and reading the stateful test before coding are the guard.
- From the cut: the package is large for one review. If it has to be split, `order.py` with `format_build` and their tests can go first on their own only with a stand-in `Build`; the better split is the store's `.tmp/` and lock part (V11) as a second pull request.
