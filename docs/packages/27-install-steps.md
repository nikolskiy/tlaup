# 27. Install, upgrade, uninstall and pin as steps

Size: L as a whole, delivered as two pull requests of size M each (27a and 27b, see the end of this file). Suggested model: most capable. Status: ready. The uninstall race (question Q8) is answered by the design: re-check under the lock and remove nothing ([12 V3](../design/12-tools-and-downloads.md#v3-uninstall), finding B7).

## Goal

`tlaup.versioning.install` holds install, upgrade, uninstall and pin, each as a class of step functions that the checked spec fixed and as one function that calls those steps in order and returns a report. The stateful test of the ToolStore spec passes against this code with its `pending` markers removed, and the throwaway model it was tried on is gone. No command uses any of it yet.

## Covers

- Roadmap items:
  - "Fix `tools uninstall --all`, which stops after removing the pinned version ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: `uninstall()` removes every build with no short circuit. The command and its feature file are package 29.
  - "A failed uninstall exits non-zero and does not move the pin; the build-selection prompt rejects negative indexes." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the pin rules of `uninstall()` and the which-build question used by `pin()`. The exit code 5 and the uninstall prompt are package 29.
  - "Concurrent installs: write the pin and metadata atomically and take a lock, so two installs of one version do not collide." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: two installs at once, as a whole. The lock, the atomic writes and the `.tmp/` cleanup were package [23](23-tool-store.md).
  - "Download to a temporary file, check it is a valid jar, then rename. ... `--force` keeps the old build until the new one is verified. ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: `--force` and repair in place. The download was [26](26-download-and-verify.md); the user sees it in 29.
  - "After download, compare the commit the jar reports about itself with the expected commit ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part, as the design departs from it: the comparison with a commit the user typed (`install rolling@bc1b506`).
  - "Do not crash on a non-JSON or non-list API response. ... `tools upgrade`, and an install of a moving tag, check the remote again instead of trusting the one-hour cache ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: `install` and `upgrade` look the release up fresh and compare with `same_as_published`.
  - "Download and GitHub failure modes are tested: ... and a forced reinstall that fails." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)), in part: the two T6 rows below. The other rows are packages 24 to 26.
  - "`tools upgrade` by name compares only the first of several installed builds of that tag." ([milestone 3](../roadmap.md#milestone-3-reproducibility), done in milestone 1 by V4), in part: the comparison with the newest build of the name. The command is 29.
- Design sections:
  - [12 V12](../design/12-tools-and-downloads.md#v12-install): `install()`, `InstallReport`, `same_as_published`, every row of the table as domain behaviour, "When GitHub cannot be asked", "The pin", "How the store is used". Not here: `tool install` with no version (the question is package 28's `choose_first_build`, the command is 29), `tool_install.feature`, the notes the command prints, the changelog.
  - [12 V3](../design/12-tools-and-downloads.md#v3-uninstall): `uninstall()` and its four steps, the pin rules, D50's order, and the unit test of the failure order. Not here: the selection table (asking which build, `--yes`, no terminal), the `--all` confirmation, "several arguments, one of which matches nothing", the notes and exit codes, `tool_uninstall.feature`: package 29.
  - [12 V4](../design/12-tools-and-downloads.md#v4-upgrade-and-pin): `upgrade()` with steps 1 to 4, `stable`, `keep_old`, and `pin()` with its question. Not here: `tool_upgrade.feature`, `tool_pin.feature`.
  - [12 V11](../design/12-tools-and-downloads.md#v11-concurrent-installs): what is left after package 23: two installs of one build at once, and nothing of a command left under `.tmp/` after an install and after a failed download.
  - [12 V1](../design/12-tools-and-downloads.md#v1-version-store): the step classes `Install`, `Upgrade`, `Uninstall`, `Pin` and the types `Lookup` and `Fetch`; "What a mutation decides on is read under the lock" as far as these steps read; the stateful test.
  - [01 T6](../design/01-testing.md#t6-download-and-github-failure-tests): the rows "`--force` reinstall fails" and "Two installs of one build at once".
  - [03 K2](../design/03-run-stages-and-specs.md#k2-tools-store), [03, "Specs and their tests"](../design/03-run-stages-and-specs.md#specs-and-their-tests) and [the specs' README](../../specs/README.md#toolstore): the ToolStore machine as this package's test first (with [23](23-tool-store.md) for the store's own steps).

## Depends on

- [23](23-tool-store.md): `ToolStore` with every step function (`acquire`, `release`, `new_tmp`, `clean_tmp`, `move_out`, `delete_out`, `add` with `repair`, `update`, `pin`, `unpin`, `find`, `builds`, `pinned`), `Build`, `Source`, `TmpFolder`, `sort_key`.
- [25](25-remote-listing.md): `Release`, `Asset`, `Remote.release` and `Remote.resolve`.
- [26](26-download-and-verify.md): `fetch_build`, which `Fetch` binds, and `usable_digest`.
- [24](24-github-client.md): `GitHubClient` (bound into `Fetch`), the `NetworkError` that carries a status, `RateLimited`, `RemoteDataError`, and the `Progress` type.
- [22](22-version-spec-and-jarinfo.md): `VersionSpec`, `JarInfo`, `read_jar`, and the small-jar helper in `tests/unit/versioning/conftest.py`.
- [16](16-ui-messages.md): `Ui` with `ask` and `is_interactive`, for `pin()` and for `choose_build`, and its constructor on in-memory streams for the tests.
- [05](05-github-recordings.md): the `github` fixture, for the tests of the four functions.
- [02](02-errors-and-paths.md) and [03](03-test-foundation.md): the error classes, `AppPaths`, the isolation fixture, `hypothesis`, the `pending` marker.

Changes from the draft (23, 25, 26): 16 is added, because V4 writes `pin(store, spec, ui)` and the which-build question is asked through `Ui.ask`; 24, 22, 05, 02 and 03 are added because they are used directly. 16 is in the groundwork track, which runs beside this one; it is the one dependency that crosses tracks, and package 28 needs it anyway.

## Files

Creates:

- `src/tlaup/versioning/install.py`
- `tests/unit/versioning/test_install.py` (the four functions and `same_as_published`)
- `tests/unit/versioning/test_install_concurrent.py` (the two T6 rows and the `.tmp/` tests of V11)

Changes:

- `tests/stateful/test_tool_store.py`: the first commit removes the three `pending` markers (`test_tool_store_machine`, `test_counterexample`, `test_a_store_object_stands_for_a_process`). A later commit deletes `reference_impl`, `test_tool_store_machine_against_the_reference_model`, `test_counterexample_against_the_reference_model` and `test_a_store_object_stands_for_a_process_reference_model`, and brings the module docstring up to date (it says the machine runs against the throwaway model too). Nothing else in the file changes: it is a reviewed artefact of the formal check. If the code cannot meet the test as written, that is a finding for the pull request, not an edit of the test.
- `specs/README.md`, "The stateful tests": one sentence that the store machine now runs against `tlaup.versioning` and that `reference_store.py` and its tests are gone. The README names the file as present.
- `tests/unit/versioning/conftest.py`: helpers the tests share (a store with given builds, a `Lookup` from a table), if they are not there.

Deletes: `tests/stateful/reference_store.py`.

Must not touch: the old modules under `src/tlaup/versioning/` (`api.py`, `downloader.py`, `metadata.py`, `paths.py`, `resolver.py`, `schema.py`, `__init__.py`) and `cmd/tools/`. Package 29 deletes them; their old tests went in 03b (decision D62). The new module name `install.py` collides with no old module; the old command module `cmd/tools/install.py` is in another package.

Shared with other packages: `tests/unit/versioning/conftest.py` with 22, 23 and 26, which are finished before this starts. `specs/README.md` with packages 21 and 35, which each add one sentence to the same part for their own machine; three separate sentences, so a conflict is a rebase of one line.

## Interfaces

Provides, from [12 V1](../design/12-tools-and-downloads.md#v1-version-store) (copy; the section has the full text), with what this package adds marked "written by stage 4":

```python
# tlaup/versioning/install.py
Lookup = Callable[[str], Release]                          # what upstream publishes under a name now (V8)
Fetch = Callable[[Release, Path], tuple[Path, JarInfo]]    # fetch_build with the client bound (V5)

class Install:                                             # install() calls these in order
    def __init__(self, store: ToolStore, name: str, lookup: Lookup, fetch: Fetch, *, force: bool = False): ...
    tmp: TmpFolder | None
    build: Build | None                                    # set by look() or add()
    release: Release | None                                # written by stage 4: what look() looked up
    info: JarInfo | None                                   # written by stage 4: what download() verified
    def look(self) -> bool                                 # True: there is something to download
    def lock_tmp(self) -> None
    def make_tmp(self) -> None
    def download(self) -> None
    def give_up(self) -> None                              # a failed download, or StoreLocked: discard, release
    def take_store_lock(self, timeout: float = 60.0) -> None
    def clean_tmp(self) -> None
    def add(self) -> bool                                  # False: nothing was downloaded and the build has gone; start again
    def pin_if_none(self) -> None
    def release_store_lock(self) -> None
    def release_tmp(self) -> None

class Upgrade:                                             # as Install, with these three in place of pin_if_none
    old: Build | None                                      # the build that was compared (V4, step 3)
    def move_pin(self) -> None
    def move_old_out(self) -> None
    def delete_old(self) -> None

class Uninstall:                                           # take_store_lock, clean_tmp and release_store_lock as above
    def __init__(self, store: ToolStore, builds: Sequence[Build], *,
                 groups: Sequence[Sequence[Build]] | None = None): ...   # groups: written by stage 4, see below
    removed: list[Build]
    failed: list[tuple[Build, TlaupError]]                 # written by stage 4: could not be moved out (V3, step 1)
    missing: list[Build]                                   # written by stage 4: a group with none left under the lock
    def move_out(self) -> None
    def delete_out(self) -> None
    def clear_pin(self) -> None

class Pin:                                                 # take_store_lock and release_store_lock as above
    def __init__(self, store: ToolStore, build: Build): ...
    def write_pin(self) -> bool                            # False: the build is no longer installed
```

`Upgrade`'s constructor, written by stage 4: `Upgrade(store, name, lookup, fetch, *, keep_old: bool = False, old: Build | None = None)`. With `old` not given, `look()` sets `old` to the newest installed build of `name` and returns whether it differs from what upstream publishes. With `old` given (the `stable` case of V4, below), `look()` returns true, `move_pin` moves the pin only if it names that build, and the removal steps do nothing. With `keep_old`, `move_old_out` and `delete_old` do nothing. The stateful test constructs `Upgrade(store, name, lookup, fetch)` only, so these keywords must default as written.

From [12 V12](../design/12-tools-and-downloads.md#v12-install):

```python
@dataclass(frozen=True)
class InstallReport:
    build: Build
    downloaded: bool            # a download was made
    already_installed: bool     # the store already held this name and these bytes
    pinned: bool                # this call pinned it
    could_not_check: str | None # the reason, when the build was installed and GitHub could not be asked
    matches: tuple[Build, ...] = ()   # written by stage 4: every installed build a build spec or a bare CalVer
                                      # matched, when it matched more than one (V12, rows 6 and 11); `build` is the first

def install(store, remote, client, spec: VersionSpec, *, force: bool = False, progress) -> InstallReport
def same_as_published(build: Build, release: Release) -> bool      # shared with upgrade (V4)
```

Three functions 03 lists as having no written signature yet, and one helper. Written by stage 4, from V3 and V4 in words and from what the stateful test calls:

```python
@dataclass(frozen=True)
class UpgradeReport:
    name: str                       # the name that was upgraded (for `stable`, the tag it resolved to)
    build: Build                    # the newest build of the name after the call
    old: Build | None               # the build that was compared; None when the name was not installed
    up_to_date: bool                # nothing was downloaded: `old` is what upstream publishes
    installed: InstallReport | None # set when no build of the name was installed and upgrade was install (V4, step 1)
    pin_moved: bool                 # the pin named `old` under the lock and now names `build`
    removed: Build | None           # `old`, when this call removed it
    remaining: tuple[Build, ...]    # the other builds of the name still installed, for the note (V4, step 4)

def upgrade(store, remote, client, spec: VersionSpec | None, *, keep_old: bool = False,
            progress=None) -> UpgradeReport

@dataclass(frozen=True)
class UninstallReport:
    removed: tuple[Build, ...]
    failed: tuple[tuple[Build, TlaupError], ...]   # each failure, in the order of the builds given
    missing: tuple[Build, ...]                     # non-empty: nothing was removed (V3, under the lock)
    unpinned: Build | None                         # the pinned build, when it was removed and the pin cleared

def uninstall(store, builds: Sequence[Build], *, groups: Sequence[Sequence[Build]] | None = None) -> UninstallReport

def pin(store, spec: VersionSpec, ui: Ui) -> Build    # V4 names it so; returns the build now pinned

def choose_build(ui: Ui, question: str, builds: Sequence[Build], *, allow_all: bool) -> list[Build]
    # lists the builds, numbered from 1, in their printed form (format_build with every installed build),
    # on stderr through ui, and asks; the answer is a whole number in range, or "all" when allow_all.
    # Used by pin() here and by the uninstall command (29), so the rule of V3's table exists once.
```

`upgrade` takes the parsed spec, not a bare name, because rejecting a build spec with code 2, and naming the name to use instead when it matches an installed build, is V4's rule (step 1) and belongs with the function. V4's sketch `upgrade(store, client, name | None)` has no `remote`; it needs one to look the release up, so the signature follows `install`'s.

What each function does, in the order the steps run. The sections have the full text; these are the points a worker could get wrong.

**`install`.**

1. Parse nothing (the spec arrives parsed). `latest` and addresses never get here: `parse_version_spec` refuses them (package 22).
2. A spec with `@commit`, `@calver` or `@sha256:`, or a bare CalVer, is looked up in the store first: if it matches installed builds and `force` is false, no request is made; the report has `already_installed` and, for several matches, `matches`. With `force`, a bare CalVer and a build spec matching several builds are `UsageError` (2) listing the candidates; a build spec matching one build fetches what upstream publishes under its name and repairs that build only if the verified jar has its SHA-256, else `VersionNotFound` (4) saying the named build is installed, cannot be downloaded again and was left as it is. `NAME@sha256:` not installed and a bare CalVer not installed are `VersionNotFound` with no request.
3. The release is looked up fresh, once. `stable` through `Remote.resolve` (a fresh list); a tag through `Remote.release`, tried as typed and, when that is `VersionNotFound` and the name does not start with `v`, again with `v` in front ([02 X3](../design/02-cross-cutting.md#x3-version-syntax); package 25's `resolve` does not do the second try). The build's name is the release's tag as upstream spells it, never the text the user typed. `install` hands `Install` a `Lookup` that answers this first call with the release it already has and asks `Remote.release` again only when the steps start over (finding K2-5), so `tool install v1.7.4` twice costs one request the second time, as V12's test counts.
4. A release without the jar: `VersionNotFound` with the reason (package 25's rule).
5. The steps: `look`; if there is something to download, `lock_tmp`, `make_tmp`, `download`. Then, for `NAME@COMMIT` or `NAME@CALVER` not installed, the verified jar's commit must start with the prefix, or its CalVer equal the one asked for; if not, `give_up` and `VersionNotFound` naming the build upstream publishes now and saying that an older build of a moving tag cannot be downloaded (research 5). Then `take_store_lock` (60 seconds), `clean_tmp`, `add`; if `add` is false, `release_store_lock` and start again at `look`. Then `pin_if_none`, `release_store_lock`, `release_tmp`. On any error after `lock_tmp`, `give_up` before the error leaves, and the store lock is released if it was taken.
6. `look()` with `force` false: the newest installed build of the name that is `same_as_published` is "already there"; `build` is set and nothing is downloaded. With `force`, always download.
7. `add()` with a download: `store.add(jar, info, name=..., prerelease=release.prerelease, source=..., repair=force)`. Without one: under the lock, read again whether `build` is still installed; if not, return false (K2-5); if it is and upstream's `prerelease` flag or source record differ from the build's, `store.update` (V12, row 2). The row "no digest, same bytes, a new upload time" falls out of this: `same_as_published` is false, the jar is downloaded, `store.add` finds the same name and bytes and returns that build, and `add()` then updates its source so that the next install makes no download.
8. `pin_if_none()`: under the lock, nothing is pinned when there is no pin file or the pin names a build that is not installed (the state D50 accepts; review finding FC5). Read it there, not before (finding K2-1).
9. GitHub cannot be asked: when step 3 raises `NetworkError`, `RateLimited` or `RemoteDataError`, `force` is false and a build of that name is installed, the report returns the newest such build with `could_not_check` holding the error's message, after the same `take_store_lock`, `pin_if_none`, `release_store_lock` as any other path that returns a build. With no build of the name, or with `force`, the error is the result. Which errors count as "GitHub cannot be asked" is read so from V12's words (settled with the index's readings, 2026-11-24); `VersionNotFound` (a 404 on the tag) is not one of them.
10. The pin rule applies to every path that returns one build: it is pinned when nothing is pinned. When a build spec matched several builds, nothing is pinned, since no one build was asked for ("the build it returns", read so and settled with the index's readings).

`Source`, written by `install` for a download: `kind="github-release"`, `url=release.asset.download_url` (never a redirect's address, package 24), `asset_id`, `asset_updated_at`, and `digest_checked` true exactly when `usable_digest(release.asset)` is not `None` (package 26). Known and accepted: `fetch_build` cannot hand back the release it fetched again after its one retry (the stateful test fixes the `Fetch` type), so after an upstream replacement during the download `asset_id` and `asset_updated_at` are one upload old. The jar and its SHA-256 are right. For a release with a digest nothing follows from it; for one without, the next install sees a different upload time, downloads once more and discards the copy (row 4 of V12's table), after which the record is current. Do not change `Fetch` to return the release.

**`same_as_published(build, release)`.** True when `usable_digest(release.asset)` is not `None` and equals `build.sha256`; otherwise true when `release.asset.size == build.size` and `release.asset.updated_at == build.source.asset_updated_at`. A digest with another prefix counts as no digest. A release with no asset is never the same.

**`upgrade`.**

1. Spec: `None` means the pinned build's name. With nothing pinned: `NoPinnedBuild` (3) when builds are installed, with the hint to name one (`tlaup tool upgrade rolling`), `NoToolsInstalled` (3) when none are. A pin that names a missing build: `PinnedBuildMissing` from `store.pinned()`. A spec with `@...` or a bare CalVer: `UsageError` (2) before any request, naming the name to use when it matches an installed build. `stable` and `rolling` are names.
2. `stable` is resolved fresh to the newest stable tag. If builds of that tag are installed, it is upgraded like any name. If none is, it is installed beside the installed stable builds with `Upgrade(..., old=<newest installed stable build>, keep_old=True)`: nothing is removed, and the pin moves to it only when, under the lock, it names that build. With no stable build installed at all, it is `install`.
3. A name with no installed build: `install` of that name (`installed` in the report).
4. Otherwise the `Upgrade` steps: `look` (fresh release, never the lookup cache; compare with the newest installed build of the name through `same_as_published`); up to date: no download, and the `prerelease` flag is refreshed with `store.update` under the lock if upstream changed it. Else `lock_tmp`, `make_tmp`, `download`, `take_store_lock`, `clean_tmp`, `add`, `move_pin`, `move_old_out`, `delete_old`, `release_store_lock`, `release_tmp`.
5. Read under the lock (V1): `move_pin` moves the pin only if it names `old`; `move_old_out` removes `old` only if it is still installed and is not the build just added. So when another tlaup upgraded the name meanwhile, this call moves nothing and removes nothing. Older builds of the name are never touched; `remaining` lists them for the note.

**`uninstall`.** Under the lock, in D50's order: `take_store_lock`, `clean_tmp`, `move_out` (first the check below; then every build in turn, no short circuit; a build whose rename fails goes into `failed` with its `FileOperationError` and the loop goes on), `delete_out` (a deletion that fails leaves the moved-out folder under `.tmp/` with its lock file released, for the next `clean_tmp`; the build counts as removed, since nothing of it is left in the store), `clear_pin` (the pin is read now, after the removals, and cleared only if it names a build in `removed`; it never moves to another build), `release_store_lock`. A build that failed keeps the pin if it was pinned.

**The check under the lock** (question Q8, settled by the design, finding B7; [12 V3](../design/12-tools-and-downloads.md#v3-uninstall), "Several arguments, one of which matches nothing"). Once the lock is held, `Uninstall.move_out` first reads `store.builds()` and checks that what it is to remove is still installed, before it moves any build out. The outcome is the one the command would have had if it had started at that moment: an argument that matches nothing removes nothing. So the builds come in **groups**, one per argument the user gave, each holding the builds that argument matched (`groups`, written by stage 4; V3 says it in words and gives no shape). With `groups=None`, the form the stateful machine uses, each build is a group of its own. A group none of whose builds is still installed puts its builds into `missing`; then nothing at all is moved out, and `removed` stays empty. Otherwise the builds of a group that have gone meanwhile are dropped and the rest are moved out: an argument that is a name matching several builds, of which one has gone, still matches the others. The command ([29](29-tool-commands.md)) turns a non-empty `missing` into `VersionNotFound` (code 4) naming those arguments; for `--all` it passes one group of every build, and an empty one means nothing is installed any more (V3's note `no builds are installed`, exit 0). The machine names one build per uninstall, so it passes with this rule as it did before: a build gone meanwhile removes nothing.

**`pin`.** `store.find(spec)`; none: `VersionNotFound` (4). Several: on `ui.is_interactive()`, `choose_build(..., allow_all=False)`; otherwise `AmbiguousVersion` (2) with the candidates in their printed form. Then `Pin` under the lock; `write_pin` false is `VersionNotFound` (the build was removed meanwhile; finding K2-1).

**`choose_build`.** The answer is validated through `Ui.ask`'s `choices` (the numbers `1` to `n` as text, and `all` when allowed), so `-1`, `0` and `7` for a list of two are asked again (V3's table). V3 names no default for this question. Pass none if package 16's `ask` accepts that (an empty line then asks again); if it does not, say so in the pull request and use no default by the nearest means, since "the newest" as a default would remove or pin a build the user did not name.

Consumes: `ToolStore`, `Build`, `Source`, `TmpFolder`, `sort_key` (23); `format_build`, `VersionSpec`, `JarInfo` (22, 23); `Release`, `Remote` (25); `fetch_build`, `usable_digest` (26); `GitHubClient` (24); `Ui` (16); the errors (02).

Used later by: `ensure_tools` (28) through `install`; the `tool` commands (29) through all four functions and `choose_build`; package 52 copies a jar into the store through `ToolStore.add`, not through `install`.

## Tests that must pass

**Stateful, test first.** `tests/stateful/test_tool_store.py`. The package's first commit removes its three `pending` markers, and the pull request shows that run red ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 6): the machine, the five counterexample replays and the second-process test then fail at the import of `tlaup.versioning.install`. At the end they pass with the CI profile (`CI=1`, 200 examples). The package deletes `tests/stateful/reference_store.py` and the three `*_reference_model` tests with `reference_impl`. The invariants are `PinConsistent`, `PinNeverMovesSilently`, `PinWritesInstalled`, `InstallPinsInstalled`, `NoPartialBuild`, `NoDuplicate`, `TmpOwnerSafe` and `ReaderOutcome` ([the specs' README](../../specs/README.md#the-stateful-tests)); the replays cover K2-1 (three traces), K2-5 and FC5.

**The two rows of [01 T6](../design/01-testing.md#t6-download-and-github-failure-tests)**, plain pytest in `tests/unit/versioning/test_install_concurrent.py`, against `install()` with the real client and `fetch_build` and `responses` serving GitHub through the `github` fixture:

| Row | Expectation |
| --- | --- |
| `--force` reinstall fails | With `v1.7.4` installed and pinned, `install(..., force=True)` whose download fails (a body cut short, so `DownloadVerificationError` after one retry) raises; afterwards `store.builds()` is what it was, the build's jar has its recorded SHA-256, the pin still names it, and nothing of the command is left under `.tmp/`. |
| Two installs of one build at once | Two threads, a barrier before `take_store_lock`, each with its own `ToolStore` object on the same folder (a `FileLock` is thread-local, so one object cannot stand for two tlaups): both download, both return the same build; one build folder with a valid `build.json`; the pin names it; no error; nothing left under `.tmp/`. |

The same file has V11's unit tests that package 23 left: after a successful `install()` and after one whose download fails, nothing of the command is left under `.tmp/`, neither folder nor lock file. This completes the "no temporary file left" clause of T6's download rows, which package 26 could only assert inside the folder it was given.

**Plain pytest of the four functions**, `tests/unit/versioning/test_install.py`, on a real store in `tmp_path` with small real jars, the `github` fixture and `responses`. They test the functions where the feature files of 29 cannot (the race replays, the question on in-memory streams) and give every branch a run before any command exists; 29's feature files then state the same rules through the command line. Each asserts state (the builds, the pin, the report's fields, the number of requests and downloads), never wording.

- `same_as_published` (V12): a digest that matches, one that does not, no digest with equal size and date and with a different size and a different date, a digest written in upper case, a digest with another prefix (treated as none).
- `install`, one test per row of V12's table: not installed (a download, added, pinned when nothing is pinned); installed and published (no download, one request, `already_installed`; a changed `prerelease` flag is written by `update`); a moving tag (a second build of the name, the first kept, the pin left where it was); no digest, same bytes, a new upload time (one download, one build, the source updated, and a second `install` makes no download); `force` with the same bytes repairs a truncated jar in place and keeps the id, and with other bytes adds a second build; `NAME@COMMIT` installed (no request); `NAME@COMMIT` matching two builds (no request, `matches` holds both, nothing pinned) and with `force` (`UsageError`); `force` with `NAME@COMMIT` installed and published (repaired) and with another build published (`VersionNotFound`, nothing changed); `NAME@COMMIT` not installed and the jar's commit another (`VersionNotFound`, nothing installed, `.tmp/` empty); `NAME@sha256:` not installed (`VersionNotFound`, no request); a bare CalVer installed under two names (`matches` holds both), not installed (`VersionNotFound`), and with `force` (`UsageError`); `stable` (resolved through a fresh list); `1.7.4` installs `v1.7.4` and records the name `v1.7.4`. GitHub failing with a build installed: `could_not_check` set, exit path with no error; with none installed and with `force`: the network error.
- `install` and the pin: the first install pins, the second does not; a pin that names a missing build counts as nothing pinned; an empty `pin` file, and one holding only a newline, count as nothing pinned and `install` pins its build over it (inventory row T4, its `install` half; the store half is [23](23-tool-store.md)'s; [12 V1](../design/12-tools-and-downloads.md#v1-version-store)).
- `upgrade`, V4's cases: up to date (no download, one request, although a one-minute-old lookup cache file exists); another digest (new build installed, pin moved, old removed); two installed builds of `rolling` (compared with the newer; the older still installed, in `remaining`); the same with the older one pinned (pin unchanged); a name not installed (installed); no spec with nothing pinned (`NoPinnedBuild` with builds installed, `NoToolsInstalled` without); a bare CalVer and `rolling@<commit>` (`UsageError`, no request); `stable` with `v1.7.4` installed and pinned and `v1.8.0` published as stable (installed beside it, pin moved, `v1.7.4` kept); `keep_old=True` keeps the old build.
- `uninstall`, V3's unit test of the failure order: of two builds the first cannot be moved out (its own folder made read-only; skipped with the reason when the suite runs as root), the second can; both are reported, the second is gone, the first is intact, and the pin, which names the first, is unchanged. Also: removing the pinned build clears the pin and does not move it; three builds with the middle one pinned all go and no pin is left (the short circuit of today).
- The race, V3's plain pytest on the `Uninstall` steps (V1) with two store objects: two builds named (two groups), the second removed through the other store object before `take_store_lock`: nothing is removed, the first build is still installed, `missing` names the second, and `removed` is empty; two builds of `rolling` in one group (named by `rolling`), one removed meanwhile: the other is removed and `missing` is empty; one group of every build (`--all`) with every build removed meanwhile: nothing is moved and `missing` holds them.
- `pin`: by spec; several matches with `interactive=True` and the answer `2` in stdin pins the second; `-1`, then `7`, then `2` asks three times; several matches with `interactive=False` is `AmbiguousVersion` and nothing is written; a build removed between `find` and the lock is `VersionNotFound` and the pin is unchanged. The `Ui` is built on `io.StringIO` streams ([01 T5](../design/01-testing.md#t5-feature-files-and-steps), "Prompts have one mechanism").

Old tests: none is left (03b, decision D62). The pull request names the inventory row it covers: T4, the `install` half.

## Changelog

None in this package. What a user sees of V3, V4, V11 and V12 arrives with the commands, and package 29 writes every entry of those sections.

## Context for the worker

Decisions:

- D46: the steps are the actions of `specs/ToolStore.tla`, checked with TLC; their boundaries are fixed. The stateful test calls them one at a time from several objects in one process, each with its own store object and so its own locks.
- D50: uninstall removes the pinned build, then clears the pin. A tlaup killed between the two leaves a pin naming a removed build; the next reader reports `PinnedBuildMissing`, and an install puts it right (its "nothing pinned" counts that state).
- D26 stays a milestone 3 item: `install` never moves an existing pin. Only `upgrade` moves it, and only off the build it compared.
- D23 and D43: naming a version is the confirmation; the which-build question is asked only on a terminal (`ui.is_interactive()`: stdin and stderr both terminals, [14 F6](../design/14-config-and-cli.md#f6-messages)).
- D29: the codes in the text above; nothing returns 1.
- D15: no Windows CI. On Windows a folder whose jar a running JVM holds open cannot be renamed; `move_out` then fails and that build is in `failed`. Not tried.

The rule a worker is most likely to break: **what a mutation decides on is read under the lock** (V1; findings K2-1 and K2-5). Looking at the store before the lock is allowed for deciding whether to download, for asking the user and for saying "already installed". What is written is decided only from what is read after `take_store_lock`: whether anything is pinned (`pin_if_none`), whether the found build is still there (`Install.add`), whether the pin names `old` and `old` is still installed (`move_pin`, `move_old_out`), whether each build is still there and whether the pin names a removed one (`Uninstall`), whether the build is still installed (`write_pin`). The five replay tests fail on each mistake of this kind every time; the machine finds them only by chance.

How the steps are called by the test, and must therefore behave (read `tests/stateful/test_tool_store.py` before writing anything):

- `Install(store, name, lookup, fetch)` with positional arguments; `look()` calls `lookup(name)` itself and may be called again after `add()` returned false. `download()` fetches the release `look()` found. The throwaway model looks up again in `download()`; either passes the machine, and the request counts of V12 decide for the first.
- `take_store_lock(timeout=0)` is one attempt that raises `StoreLocked` at once; the machine relies on it never waiting.
- `give_up()` may be called at `dl` (after `make_tmp`) or while waiting for the store lock, and must leave nothing under `.tmp/` for its own folder.
- A killed process is a step object that is dropped and garbage-collected: its locks are released by `filelock` when the lock objects go, its `.tmp/` folder stays for the next `clean_tmp`. Nothing in the step classes may keep a lock alive past the object (no module-level registry).
- `Upgrade.look()` false ends the command in the machine; the `prerelease` refresh of V4 step 3 is done by `upgrade()` outside the machine's path (the machine's releases are never prereleases).
- `Uninstall.removed` and `Upgrade.old` are read by the machine; keep those names.

`tests/stateful/reference_store.py` shows one way to arrange the steps in about 350 lines, before you delete it. It is not the design: it has no `build.json` schema, no ids, no `find`, no `repair`, no `failed` or `gone`. Where it and V1 differ, V1 is right.

Upstream facts the code relies on, from research the design restates: upstream moves `rolling` and `v1.8.0` on every build of its main branch, and both hold the same jar today, which the store keeps as two builds (X4); an older rolling build cannot be downloaded again (research 5), which is why `install` never removes a build and `keep_old` exists; releases before mid-2025 (v1.7.4 and older) have no digest (research 18).

Known gaps the design postpones, not to be closed here: one stored jar with two names (milestone 3); D26; pruning old builds (a milestone 3 item added at the sign-off).

State of `main` when this starts: the 0.8.x commands on the old `versioning/` modules, with packages 22 to 26 beside them and package 16's `Ui`. `tests/stateful/test_tool_store.py` has run its reference-model tests since package 03 (with 03b's `ResourceWarning` fixes, question Q17); its `pending` tests have never run.

## Done when

- The stateful test passes without its `pending` markers under `CI=1`; the pull request shows it red after the first commit.
- `reference_store.py` and the three `*_reference_model` tests are gone; the module imports nothing that is gone and its docstring says what it runs against; `specs/README.md` has its sentence.
- The tests above pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- No file listed under "Must not touch" is in the diff.
- The pull request (27b) says what it found about `Ui.ask` and a question with no default, and how the groups reach `Uninstall`.

## Out of scope

- `ensure_tools`, `choose_first_build`, `--auto-install`, `TLAUP_AUTO_INSTALL`: package [28](28-first-run.md).
- The `tool` commands, the uninstall selection table and its prompt, the `--all` confirmation, the notes, exit codes as a user sees them, the five `tool_*` feature files, the progress bar, the changelog entries and the deletion of the old modules: package [29](29-tool-commands.md).
- The download itself and its T6 rows: package [26](26-download-and-verify.md). The store, its lock, `clean_tmp` and their tests: package [23](23-tool-store.md).
- "Did you mean" for a version that matches nothing ([14 F11](../design/14-config-and-cli.md#f11-error-messages)): package 50.
- Completion of installed versions: package 47.

## Risks

- From V12: for a release without a digest, "already installed" rests on the asset's size and upload time, which shows that upstream did not replace the file, not that the file on disk is undamaged; `tlaup doctor` (46) checks the jar against its SHA-256 and `--force` repairs it. Older builds of a moving tag pile up at 4.5 MB each.
- From V3: a script that ran `tool uninstall rolling` expecting one build to go now removes every rolling build (the command's rule, 29).
- From 03: the stateful test interleaves at step boundaries only; a race inside one step is outside the spec and the test. A race that needs one command to wait while another takes four steps is found by chance; the replay tests are the guard for the five known ones.
- From the cut: the package is large as a whole (four functions, four step classes, one stateful machine, about fifty unit tests), so it is delivered as 27a and 27b below. The machine needs all four step classes at once, not the four functions, so the seam falls between them.
- From the cut: the user-visible behaviour of these functions is first checked through the command line two packages later, in 29.

## Pull requests (decided in the review of the packages, finding B18)

This package is delivered as two pull requests; the index lists them as 27a and 27b. The index's earlier reason for not splitting ("the store machine needs install, upgrade, uninstall and pin together") holds for the four step classes, not for the four functions, so the seam keeps every step class in the first part.

- **27a**: `install.py` with `Lookup`, `Fetch`, the four step classes (`Install`, `Upgrade`, `Uninstall` with its groups and its check under the lock, `Pin`), `install()`, `InstallReport` and `same_as_published`; the stateful test with its markers removed, `reference_store.py` and the `*_reference_model` tests deleted, the `specs/README.md` sentence; the two T6 rows and V11's `.tmp/` tests (`test_install_concurrent.py`); the unit tests of `same_as_published`, `install` and the pin, and V3's race tests on the `Uninstall` steps. Depends on 02, 03, 05, 16, 22 to 26.
- **27b**: `upgrade()` and `UpgradeReport`, `uninstall()` and `UninstallReport`, `pin()` and `choose_build`, with their unit tests. Depends on 27a.

A package that names 27 as a dependency waits for 27b.
