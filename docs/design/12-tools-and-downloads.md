# 12. Milestone 1: tools and downloads

Covers milestone 1's "Safety" items for tools, "Downloads and GitHub", and from "First run and failures" the first-run prompt and the removal of old layouts. Relies on decisions D4, D13, D14, D19, D23, D31, D32, D37, D41, D43, D45 and research [7](../research/07-rolling-race.md), [8](../research/08-github-api-ordering.md), [14](../research/14-jar-manifest.md), [18](../research/18-digest-field.md).

All of it is in `tlaup/versioning/`. Commands under `cmd/tools/` become argument parsing plus printing; the logic is in functions that take the store and the client as arguments.

## V1 Version store

Decision D37 pulls forward the milestone 3 item "Version identity as a type, not a parsed folder name. Typed metadata is the source of truth, with one writer, one reader and a schema version. One version store ... is the only code that composes or parses folder names."

**Problem.** Folder names are composed or parsed in eight places with two rules that disagree: `list_local_versions` splits on the first hyphen, `upgrade` on the last. A tag with a hyphen breaks both. The metadata file is written without a schema, read as a bare `dict`, and holds a version string obtained by starting Java, or an empty string if that failed. A folder with a half-written jar counts as installed. The pin is written in place.

**Design.**

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
    url: str                      # the asset's download address as the release gave it (V8); never a redirect's signed address
    asset_id: int | None
    asset_updated_at: str | None
    digest_checked: bool          # the download was compared with GitHub's digest

class ToolStore:
    def __init__(self, paths: AppPaths, *, now: Callable[[], datetime]): ...
    def builds(self) -> list[Build]                       # sorted by 02 X4
    def find(self, spec: VersionSpec) -> list[Build]      # V2
    def pinned(self) -> Build | None                      # raises PinnedBuildMissing
    def add(self, jar: Path, info: JarInfo, *, name: str, prerelease: bool,
            source: Source, repair: bool = False) -> Build    # below: what "already there" means
    def update(self, build: Build, *, prerelease: bool, source: Source) -> Build    # rewrites build.json only
    def remove(self, build: Build) -> None
    def pin(self, build: Build) -> None
    def unpin(self) -> None
    @contextmanager
    def locked(self, timeout: float = 60.0) -> Iterator[None]    # raises StoreLocked
```

On disk, in the first wave under the cache folder (milestone 3 moves it):

```
<cache>/tool/
    .lock
    pin                         one line: a build id
    <build-id>/
        tla2tools.jar
        build.json              {"schema": 1, ...the fields of Build except id and path}
    .tmp/                       downloads in progress (V5) and folders on their way out
        <random>/               one download, or one removed build
        <random>.lock           held by the tlaup that owns the folder (V11)
```

**Formal check, 2026-11-18.** V1, V3, V4, V11 and V12 were written as `specs/ToolStore.tla` and checked with TLC; [the specs' README](../../specs/README.md#toolstore) says what was modelled, with which bounds, and what was found. What the check changed in these sections is marked "formal check". The one point it left to the maintainer, the order of the two steps of uninstall, was settled on 2026-11-18: the order stays, and the state a kill between them leaves is accepted (decision D50, V3).

*The steps, one call each* (decision D46; fixed by the checked spec). `install`, `upgrade`, `uninstall` and `pin` are these steps in order, and `ToolStore.remove` is `move_out` and `delete_out`. The steps are the spec's actions, and the stateful test calls them one at a time from several objects in one process, each with its own store object and so its own locks ([03](03-run-stages-and-specs.md#specs-and-their-tests)). The download steps take two functions instead of the client, so the test needs no network: what upstream publishes under a name now, and `fetch_build` with the client bound.

```python
# tlaup/versioning/store.py
class TmpFolder:                                           # a folder under .tmp/ and the lock file beside it (V11)
    path: Path
    def lock(self) -> None                                 # create the lock file and take its lock
    def make(self) -> None
    def discard(self) -> None                              # delete the folder
    def release(self) -> None                              # remove the lock file, then release the lock

class ToolStore:                                           # beside the interface above
    def acquire(self, timeout: float = 60.0) -> None       # locked() is acquire and release; raises StoreLocked
    def release(self) -> None
    def new_tmp(self) -> TmpFolder
    def clean_tmp(self) -> None                            # V11
    def move_out(self, build: Build) -> TmpFolder | None   # remove(), first half: one rename; None if the build has gone
    def delete_out(self, out: TmpFolder) -> None           # remove(), second half

# tlaup/versioning/install.py
Lookup = Callable[[str], Release]                          # what upstream publishes under a name now (V8)
Fetch = Callable[[Release, Path], tuple[Path, JarInfo]]    # fetch_build with the client bound (V5)

class Install:                                             # install() calls these in order
    def __init__(self, store: ToolStore, name: str, lookup: Lookup, fetch: Fetch, *, force: bool = False): ...
    tmp: TmpFolder | None
    build: Build | None                                    # set by look() or add()
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
    def __init__(self, store: ToolStore, builds: Sequence[Build]): ...
    removed: list[Build]
    def move_out(self) -> None
    def delete_out(self) -> None
    def clear_pin(self) -> None

class Pin:                                                 # take_store_lock and release_store_lock as above
    def __init__(self, store: ToolStore, build: Build): ...
    def write_pin(self) -> bool                            # False: the build is no longer installed
```

- **The build id** is made by the store and read by nobody else: the name with every character outside `[A-Za-z0-9._]` replaced by `_`, then `-`, then the first 12 hexadecimal digits of the jar's SHA-256: `rolling-7e53aa636dac`. No character is invalid on Windows. Nothing splits the id again, and nothing finds a build by working out its id: the name, the commit, the CalVer and the full SHA-256 are in `build.json`. (The first version of this design built the id from the commit and the CalVer, which collided for two different jars of one name and commit with no build time, and gave `v1.6.0-` for a jar with no commit.)
- **An id only has to be free.** The text above is not unique. Different names give the same text (`a-b`, `a_b`, `a/b` and `a+b` all become `a_b`), so one jar under two such names would ask for one id; two jars of one name can agree in 12 digits; and a folder the store cannot read as a build can already sit there: a leftover, a damaged `build.json`, or one written by a newer tlaup with a schema this one does not know. So when the first candidate exists, whatever it is, the store tries the same text followed by `-2`, then `-3`, and takes the first that does not exist. It never replaces, repairs or deletes a folder it did not read as the very build being added; `tlaup doctor` reports such folders as leftovers. (The second check found that the earlier rule, "an existing id can only be the same name and bytes", was false in each of these cases and could drop a second name silently.)
- **"Already there" is decided by content.** `add` looks through `builds()` for a build with the same `name` and the same full `sha256`, and never infers it from an id. If there is one, the temporary copy is discarded and that build is returned; with `repair=True` its jar is first replaced by the verified one with `os.replace` and its `build.json` rewritten the same way ([V12](#v12-install), `--force`). If there is none, the folder is moved to the first free id. So the store never holds two builds with the same name and SHA-256, which the printed forms rely on ([02 X3](02-cross-cutting.md#x3-version-syntax)), and one jar installed under two names is two builds.
- **`build.json` is the truth.** One function writes it (`_write_build`), one reads it (`_read_build`); both check `schema`. A folder is a build only if it holds a jar *and* a readable `build.json` with a known schema. Anything else under `tools/` is ignored by `builds()` and reported by `tlaup doctor` as a leftover.
- **Writes are atomic.** `build.json` and `pin` are written to a temporary file in the same folder and moved into place with `os.replace`. A build folder is assembled under `.tmp/` and renamed into place (V5).
- **Mutations take the lock.** `add`, `update`, `remove`, `pin`, `unpin` each require the caller to hold `locked()`; they assert it. Reads do not lock. What a reader can see while another tlaup writes:
  - `add`: the folder is complete under `.tmp/` before one rename puts it in place, so a reader sees the build or does not.
  - `update`, `pin`, `unpin`: one file replaced with `os.replace`; old or new.
  - `remove`: the folder is first renamed into `.tmp/` (one rename), then deleted there, so a reader never sees a half-deleted build.
  - A reader that listed a build just before it was removed finds its jar gone when it opens it. `pinned()` and the preflight report that as `PinnedBuildMissing`; a JVM that already has the jar open keeps running on Linux and macOS. Between the preflight's look and Java opening the jar there is still a moment in which the build can be removed. Java then reports that it cannot load its main class and exits 1, and tlaup passes the 1 on as the tool's own code ([02 X1](02-cross-cutting.md#x1-exit-codes)); that case is not reported as `PinnedBuildMissing`. Found by the formal check (2026-11-18, [finding K2-3](../../specs/README.md#findings)) and left as it is. Closing it would need readers to take the lock, which this design does not want, or the run to look at the store again when Java fails at once; the second is cheap, and the maintainer's to ask for.
- **What a mutation decides on is read under the lock** (formal check, 2026-11-18, [finding K2-1](../../specs/README.md#findings)). A command looks at the store before it takes the lock: to decide whether to download, to ask the user which build, to say "already installed". None of that may decide what is written. Once the lock is held the command reads again: `install` whether anything is pinned, and, when it found the build installed and downloaded nothing, whether that build is still there; `upgrade` whether the pin names the build it compared and whether that build is still installed; `uninstall` whether each build is still there and whether the pin names one it removed; `pin` whether the build is still installed. The outcome is the one the command would have had if it had started at the moment it got the lock: a build that has gone meanwhile is `VersionNotFound` (code 4) for `pin` and for `uninstall`, and for `upgrade` there is then nothing to remove and no pin to move. `upgrade` never removes the build it has just added. An `install` whose build has gone lets the lock go and starts again from the lookup, this time downloading ([finding K2-5](../../specs/README.md#findings); `Install.add` returns false). The first wording did not say where these were read. Read before the lock, TLC found the pin replaced by a second install, the pin left on a build an uninstall removed, and `pin` writing a build that had been removed, each with no tlaup killed. The stateful test found the fifth case, an install pinning a build that was removed after it found it, which the first version of the spec had modelled too kindly to show.
- **The pin** names a build id. `pinned()` returns `None` when there is no pin file, and raises `PinnedBuildMissing` when the file names a build that is not in `builds()`; it never falls back to another build or to an old jar path (V10).

What changes compared with the roadmap's milestone 3 item: nothing in substance. The item is done here; milestone 3 keeps `ToolStore`'s interface and changes the layout beneath it (a level for other distributions, the data folder, a layout marker), which is why the id is opaque and the paths come from `AppPaths`.

**Rejected.** *Patching the existing functions* and building the store later: the seven milestone 1 fixes would be written twice. *A database file* (SQLite or one JSON index): a second source of truth beside the folders; a crash between the two would need repair logic. *Symlinks for the pin*: the roadmap's "Keep" list keeps the plain file.

**Tests.** Unit, on a store in a temporary folder with small real jars: add then list; a folder without `build.json` is not a build; a `build.json` with `"schema": 99` is not a build; a jar without metadata is not a build; pin, unpin; `pinned()` raises when the build's folder is removed; ids for a tag with a hyphen and a slash; two builds of one commit with different CalVers coexist; two different jars with the same name, the same commit and no build time coexist; a jar with no commit is stored with `commit` null and an id like any other; the same jar under two names gives two builds; the same jar under `a-b` and then `a_b` gives two builds with two ids; `add` when a folder with no `build.json`, with an unparsable one, and with `"schema": 99` already sits at the first id: each time the folder is untouched and the build lands at the next id; two jars made to agree in 12 digits (the id function is given a shorter prefix length in the test) coexist; adding the same name and bytes twice returns the first build and leaves one folder; with `repair=True` the jar on disk is replaced; `add` without the lock held fails; after `remove`, nothing of the build is left under `tools/` outside `.tmp/` even when the delete step is made to fail. The `tools_*.feature` files state their starting point through the store (`Given the build ... is installed`), so every feature exercises reading. Stateful (`tests/stateful/test_tool_store.py`): the Hypothesis state machine that mirrors [the spec](../../specs/README.md#toolstore) on the step functions above, with one plain test that a store object in the test process is refused, and refuses, like a second Python process. Written before the code and marked `pending` ([03](03-run-stages-and-specs.md#specs-and-their-tests)).

**Changelog.** Breaking: "Installed tools are stored in a new layout with a `build.json` beside each jar. They live in the cache's `tool` folder (was `tools`). Builds installed by earlier versions are not recognised: run `tlaup tool install` again. The old `tools` folder can be deleted." (D14: no migration.)

**Depends on.** F2, G2, `jarinfo` (V5). **Risks.** A layout break now and another in milestone 3. Both land in 0.9.0, so users reinstall once (D6, D14). On Windows a folder holding a jar that a running JVM has open cannot be renamed or deleted; `remove` then fails with `FileOperationError` (code 5) and the build stays. That is the wanted outcome, but it was not tried: no research ran on Windows and there is no Windows CI (D15).

## V2 Version order and lookup

Implements [02 X3](02-cross-cutting.md#x3-version-syntax) and [X4](02-cross-cutting.md#x4-rolling).

```python
# tlaup/versioning/order.py
def version_key(tag: str) -> tuple | None          # (1, 7, 4, suffix_rank, suffix) or None if not a number
def sort_key(build: Build) -> tuple                # rolling first, then version_key descending, then build time
def stable_of(releases: Sequence[Release]) -> Release | None

# ToolStore.find(spec) -> list[Build]
```

`find`: `stable` gives the builds of the highest-numbered name whose builds are not prereleases; `rolling` the builds named `rolling`; a tag the builds with that name, tried as typed and then with `v`; a commit prefix, a CalVer or a `sha256:` prefix after `@` narrows the list; a bare CalVer matches on `calver` alone, across names. A build with no commit matches its bare name and never a `@commit`. The result is sorted newest first. Zero results is the caller's `VersionNotFound`; more than one is the caller's decision (ask, or `AmbiguousVersion`).

`resolve_latest_version` and its sort key (version, `published_at`, folder modification time, name) are deleted; nothing chooses "the latest installed build" any more (V3).

**Tests.** [02 X3 and X4](02-cross-cutting.md#x3-version-syntax) list them.

No roadmap item links to this section; it is the shared lookup that X3 and X4 specify and that V3, V4, V9 and V12 call.

## V3 Uninstall

Roadmap: "Fix `tools uninstall --all`, which stops after removing the pinned version; the same happens with several named versions when the pinned one is not last." "A failed uninstall exits non-zero and does not move the pin; the build-selection prompt rejects negative indexes."

**Problem.** `any(_remove_path(p, pinned_dir) for p in targets)` stops at the first `True`, so removal ends at the pinned build (`cmd/tools/uninstall.py:95`). `_remove_path` decides whether the pinned build "was removed" before it tries to remove it, so when removing the pinned build fails, the pin is still cleared and moved to another build (`cmd/tools/uninstall.py`); the command exits 0 either way. The prompt accepts `-1`, which Python reads as "the last one".

**Design.** `uninstall(store, builds) -> UninstallReport` in `versioning/install.py`:

1. Under the lock, remove every build in turn; collect `(build, error)` for those that fail. No short circuit.
2. If the pinned build was among those removed successfully, clear the pin. **The pin does not move to another build.** The command says `rolling@bc1b506 was pinned; nothing is pinned now` and gives the hint `tlaup tool pin <name>` listing what is left.
3. If the pinned build failed to be removed, the pin is untouched.
4. If any removal failed, the command prints each failure and exits 5; the builds that could be removed are removed.

The pin of step 2 is read under the lock, after the removals, not when the command started (V1, "What a mutation decides on is read under the lock").

**After a killed uninstall the pin can name a removed build** (decision D50, settled 2026-11-18, [finding K2-2](../../specs/README.md#findings)). Steps 1 and 2 remove the pinned build and then clear the pin, in that order. A tlaup killed between the two leaves a pin that names a removed build while nobody holds the lock. That state is accepted. The next command that reads the pin reports `PinnedBuildMissing` with its hint, which is the designed answer to that state (V1), so nothing is lost, and `tlaup tool pin` or `tlaup tool install` puts it right: for its first-install rule, an install counts a pin that names a missing build as nothing pinned (V12; review finding FC5). So "the pin is absent or names an installed build" holds whenever the lock is free, except after a tlaup was killed while it held the lock. The other order, clearing the pin first, was not taken: it is less simple, since a removal that fails must then write the pin back to keep step 3, and a kill between the two steps still leaves a state to report (the build installed with nothing pinned, `NoPinnedBuild`). In the spec this is `UnpinFirst = FALSE`; `ToolStore-unpin-first` checks the other order and shows that it holds too.

**Selection** (decisions D23 and D43). Each argument is a version spec. When it matches one build, that build is removed with no question: naming a version is the confirmation (D23). When it matches several builds of one name:

| Situation | What happens |
| --- | --- |
| On a terminal (`ui.is_interactive()`), no `--yes` | The builds are listed, numbered, in their printed form ([02 X3](02-cross-cutting.md#x3-version-syntax)), and the user is asked which one, or `all`. The answer is validated as a whole number in range or the word `all`; anything else, including `-1` and `7` for a list of two, asks again. |
| `--yes` | All of them are removed: `--yes` answers "which" with "all" (the roadmap's milestone 4 asks that `--yes` cover every prompt). |
| Not on a terminal | All of them are removed: naming the name is the confirmation for every build of that name. A script that wants one build names it as `name@commit`. |

`--all` keeps its confirmation, and each case has one rule:

| `uninstall --all` | What happens |
| --- | --- |
| `--yes` | Every build is removed, with no question. |
| On a terminal, answered yes | Every build is removed. |
| On a terminal, answered no | Nothing is removed; the note is `nothing removed`; exit 0. |
| Not on a terminal, no `--yes` | `UsageError` (code 2): "`--all` asks for confirmation and there is no terminal; add `--yes`". Nothing is removed. This is not `CannotAsk` (3): what is missing is an option on the command line, not something about the installation. |

The rows are read after one check that comes first: **when nothing is installed**, the note is `no builds are installed` and the exit is 0, with or without `--yes`, with or without a terminal, and with no question. There is nothing to confirm, so the fourth row does not apply.

**Several arguments, one of which matches nothing** (`uninstall v1.8.0 nosuch`): every argument is resolved before anything is removed. If any matches no installed build, nothing is removed and the command is `VersionNotFound` (code 4), naming each argument that matched nothing. A question about "which build" for another argument is not asked first.

`uninstall` with neither a version nor `--all`, or with both, is a usage error raised by the command ([23 C1](23-command-layout.md#c1-command-tree)). The `default` argument (the pre-store jar) is gone with V10.

**Why no fallback.** Today removing the pinned build silently pins "the latest" other build, chosen by a sort that puts rolling last. A run after that uses a different TLC without the user having asked for it. After this change the next run stops at the preflight with the command to run.

**Rejected.** Keeping the fallback and announcing it: still changes which TLC runs as a side effect of a removal.

**Tests.** `tool_uninstall.feature`, in-process except where a scenario says "on a terminal": those are real processes on a pty with the answers typed ([01 T5](01-testing.md#t5-feature-files-and-steps); the store is prepared on disk, and no network is needed). Three builds with the middle one pinned, `--all --yes` leaves none and no pin; two named builds with the pinned one first; two builds named, the pinned one made impossible to remove (its own folder is made read-only, so it cannot be moved out; the tools folder stays writable), gives exit 5, the other build is gone, the stuck one is intact and the pin still names it; two builds of `rolling`, on a terminal, answers `-1`, then `7`, then `2`: `stderr contains "<question>" 3 times`, the second build removed, the first left; the same with the answer `all`; the same store with `--yes` removes both without asking; the same store with no terminal and no `--yes` removes both; `rolling@<commit>` removes one in every mode; removing the pinned build leaves `no build is pinned` and the next `tlaup tlc` exits 3; `--all` on a terminal answered `n` removes nothing and exits 0; `--all` with no terminal and no `--yes` exits 2 and removes nothing; `--all` with nothing installed and no terminal exits 0 with the note, with and without `--yes`; `v1.8.0 nosuch` with `v1.8.0` installed exits 4, names `nosuch`, and `v1.8.0` is still installed; two builds of `rolling` on a pty with stderr redirected to a file removes both without asking, since the question could not be seen. The unit test of `uninstall()` covers the failure order: first build fails, second succeeds, both reported.

**Changelog.** Fixed: "`tlaup tool uninstall --all` stopped after removing the pinned version." "A failed uninstall now exits 5 and leaves the pin alone." Breaking: "Uninstalling the pinned build clears the pin; it no longer switches to another installed build. Pin one with `tlaup tool pin`." "With several installed builds of one name, `tlaup tool uninstall NAME` without a terminal, or with `--yes`, removes all of them; name one build as `NAME@COMMIT`."

**Depends on.** V1, V2, F6. **Risks.** A script that ran `tool uninstall rolling` expecting one build to go now removes every rolling build; the changelog entry says so, and the builds can be installed again only while upstream still publishes them (an older rolling build cannot be downloaded again, research 5).

## V4 Upgrade and pin

Roadmap (milestone 1): "`tools upgrade`, and an install of a moving tag, check the remote again instead of trusting the one-hour cache." Milestone 3 items done here because the store makes them free: "`tools upgrade` by name compares only the first of several installed builds of that tag."

**Design.** `upgrade(store, client, name | None)`:

1. The name is the argument, or the pinned build's name. A build spec is a usage error (code 2), because upgrade moves a name forward and a build does not move: that covers `NAME@COMMIT`, `NAME@CalVer`, `NAME@sha256:...` and a bare CalVer ([02 X3](02-cross-cutting.md#x3-version-syntax)); the message names the name to use instead when the spec matches an installed build. `stable` and `rolling` are names and are accepted. `stable` is resolved fresh to the newest stable tag, as in V12, and then compared like any name: when that tag is newer than every installed stable build, it is installed beside them and nothing is removed, since "the old build" in step 4 is a build of the same name; the pin moves to it only if the pinned build was the newest installed stable one, and the note says which builds remain. With no argument and nothing pinned, it is `NoPinnedBuild` (code 3) when builds are installed, with the hint to name one (`tlaup tool upgrade rolling`), and `NoToolsInstalled` (code 3) when none are. If no build of the name is installed, upgrade is `install` of that name (V12).
2. Fetch the release for that name fresh, never from the lookup cache (V8).
3. Compare with the **newest installed build of that name** (V2), using `same_as_published(build, release)`, which V12 uses too: equal if the release's digest (the hexadecimal part after `sha256:`, V5) equals the build's `sha256`, or, for a release without a digest, if `asset_updated_at` and `size` are equal. Equal means "up to date": nothing is downloaded, and the build's `prerelease` flag is refreshed if upstream changed it (`store.update`).
4. Otherwise install the published build (V5). If the old build was pinned, the pin moves to the new one and the command says so. The old build is then removed, as today. **With several installed builds of the name, "the old build" is only the newest one**, the one that was compared. Older builds of that name are left alone, and the note says how many remain and names `tlaup tool uninstall`. The pin moves only if it named the replaced build; a pin on an older build of the name stays where it is, and the note says that too. Both are read under the lock (V1): if another tlaup has upgraded the name in the meantime, the build that was compared is gone and the pin no longer names it, so this upgrade finds the new build already there, moves nothing and removes nothing. Whether upgrade should keep it is a question of the milestone 3 design note, since a rolling build cannot be downloaded again ([40](40-later-milestones.md#milestone-3-reproducibility)); the function has a `keep_old` parameter, false for now.

`pin(store, spec, ui)`: finds the build (V2); when several match, asks which if `ui.is_interactive()`, which needs stdin and stderr both to be terminals ([14 F6](14-config-and-cli.md#f6-messages)), and otherwise fails with code 2 and the candidates; writes the pin. Decision D26 (installing a newer build of a pinned tag moves the pin) stays a milestone 3 item; `install` here pins only when nothing is pinned.

**Tests.** `tool_upgrade.feature`: installed build equals the published digest, nothing is downloaded and one request was sent to GitHub even though a one-minute-old lookup cache exists; a different digest installs the new build, moves the pin, removes the old; two installed builds of `rolling`, the comparison is with the newer, and after the upgrade the older one is still installed; the same with the older one pinned leaves the pin on it; upgrading a name that is not installed installs it; no argument with nothing pinned exits 3, with and without builds installed; a bare CalVer and `rolling@<commit>` exit 2 with no request sent; `stable` with `v1.7.4` installed and pinned and `v1.8.0` published installs `v1.8.0`, moves the pin, and leaves `v1.7.4` installed. `tool_pin.feature`: by tag without `v`; `tag@commit`; ambiguous without a terminal exits 2; ambiguous on a pty asks, and the typed answer is pinned (a real process, [01 T5](01-testing.md#t5-feature-files-and-steps)); ambiguous on a pty with stderr redirected exits 2.

**Changelog.** Fixed: "`tlaup tool upgrade` could report 'already up to date' for up to an hour after upstream published a new build." Changed: "`upgrade` compares the installed jar with the published one by SHA-256 where GitHub provides it."

## V5 Download and verify

Roadmap: "Download to a temporary file, check it is a valid jar, then rename. A folder without a jar and its metadata does not count as installed. `--force` keeps the old build until the new one is verified. Never report a truncated jar or a proxy's HTML page as installed." And: "After download, compare the commit the jar reports about itself with the expected commit, since the tag and the jar are fetched separately and upstream moves both."

**Problem.** `_download_jar` streams straight into the final folder with no length, zip or digest check; a body cut short without an exception is installed. `--force` deletes the old build before downloading. The commit recorded is the tag's at lookup time, which can be up to an hour stale (tlaup's own cache) or 4.5 minutes off upstream (research 7).

**Facts.** The jar's manifest holds its full commit in `X-Git-Revision` and, on rolling builds, its build time, readable with `zipfile` and no JVM (research 14). The release object holds the asset's `size`, and for uploads since mid-2025 a SHA-256 `digest`; v1.7.4 and older have none (research 18). Upstream replaces an asset by delete-then-upload, so the download address can answer 404 for one to three seconds (research 7).

**Design: the jar says what it is; the release says what the bytes should be.**

```python
# tlaup/versioning/jarinfo.py        no network, no JVM
@dataclass(frozen=True)
class JarInfo:
    sha256: str; size: int
    commit: str | None           # X-Git-Revision, None if absent
    built_at: str | None         # Build-TimeStamp
    calver: str | None           # built_at as %Y.%m.%d.%H%M%S in UTC
    capabilities: frozenset[str]
def read_jar(path: Path) -> JarInfo        # raises DownloadVerificationError if not a TLA+ tools jar

# tlaup/versioning/download.py
def fetch_build(client: GitHubClient, release: Release, dest_dir: Path, progress) -> tuple[Path, JarInfo]
```

`read_jar` requires: a valid zip (`ZipFile.testzip()` returns nothing); an entry `tlc2/TLC.class`; a readable `META-INF/MANIFEST.MF`. The manifest reader handles CRLF and continuation lines (a line starting with a space continues the previous one; research 14 notes none of the three jars needed it, so a hand-wrapped manifest is a test case). `Build-Tag`, `Build-Rev`, `X-Git-Tag` and `Implementation-Version` are not read (research 14: placeholders or not unique).

`fetch_build`:

1. Stream the asset from its `download_url` (V8) to `<cache>/tool/.tmp/<random>/tla2tools.jar`, hashing as it goes. Reading stops one byte past the release's `size`: a body longer than the asset is a mismatch, and a server cannot fill the disk.
2. Check the number of bytes against `Content-Length` and against the release's `size`.
3. If the release has a `digest`, compare. GitHub writes it as `sha256:<64 hexadecimal digits>` (research 18); the part after the prefix is compared with the hash, ignoring case. A digest with another prefix is not compared, and `digest_checked` is false, as for a release with none.
4. On a mismatch of size or digest, or a 404, wait 2 seconds (through the client's injected `sleep`), fetch the release object again and retry **once**: the likely cause is that upstream replaced the asset in between, a gap of one to three seconds (research 7, implication 6). A second mismatch is `DownloadVerificationError`.
5. `read_jar`. A proxy's HTML page fails here as "not a zip".
6. Return the path and the info. The caller, holding the store lock, hands them to the store; what the store does when a build with the same name and bytes is already there, and what `--force` does, is [V12](#v12-install). Nothing here touches an installed build, so an installed build is intact until its replacement has been verified.

**The commit comparison, and where this departs from the roadmap.** The roadmap item compares the jar's commit with the commit the tag points at. The research changes the picture: the tag and the asset move at different moments by design, so a mismatch is normal for minutes after every upstream build, and the jar's own commit is the stronger identity because it is read from the installed bytes (research 7, implication 2). So:

- The build's commit is **always** the jar's. The tags API is no longer called; tlaup never states a commit it did not read from a jar.
- What protects against a wrong or damaged download is the size and digest check against the release object fetched immediately before.
- The commit **is** compared when the user stated one: `tool install rolling@bc1b506` fails with `VersionNotFound` if the downloaded jar's commit does not start with `bc1b506`, saying which commit upstream publishes now.

For a release without a digest (v1.7.4 and older), the checks are size, zip validity and `tlc2/TLC.class`, and `digest_checked` is false. Trusting such a jar on first download and pinning its SHA-256 afterwards is milestone 3's subject.

**Rejected.** *Comparing with the tag and failing on a mismatch*: would fail every install made within minutes of an upstream build. *Comparing and renaming the folder to the jar's commit*: that is what "identity from the jar" already does, without the extra requests. *Starting Java to ask the jar its version*: needs Java at install time and is what wrote empty strings into the metadata.

**Tests.** The table in [01 T6](01-testing.md#t6-download-and-github-failure-tests), plus these rows that table needs: a body longer than the asset's size (reading stops, verification fails); a digest written `SHA256:` in upper case (compared); a digest with an unknown prefix (installed, `digest_checked` false); a 404 on the asset, then success (one 2-second wait through the injected `sleep`, installed). Unit, `read_jar` on the three recorded manifests packed into small jars: v1.7.4 gives commit `5a47802b...`, no CalVer, no `repl`; rolling gives `2026.11.15.002146`; a manifest with a wrapped `X-Git-Revision` line; a manifest without `X-Git-Revision` gives `commit` null; a zip without a manifest; a text file. `tool_install.feature` (in-process): after a failed download `the installed builds are:` unchanged.

**Changelog.** Fixed: "A download that was cut short, or a proxy's error page, could be recorded as an installed build. Downloads are now checked for length, for being a TLA+ tools jar, and against GitHub's SHA-256 where it provides one, before anything is installed." "`tool install --force` deleted the installed build before the new download had succeeded." Changed: "The commit shown for a build is read from the jar itself."

**Depends on.** V1, V7, V8. **Risks.** `testzip` reads every entry of the jar. Timed once while fixing this design: 0.09 seconds for a 4.4 MB tools jar with 2,162 entries, on one Linux machine with Python 3.13; hashing the same file took under 0.01 seconds. GitHub's digest comes from the same account as the file, so it detects corruption and a replaced asset, not a compromised release; the documentation says so (research 18). A jar with no `X-Git-Revision` is installed with no commit and can be named only by its tag ([02 X3](02-cross-cutting.md#x3-version-syntax)); no published release has such a jar (top-up, [research 26](../research/26-old-jar-commits.md): every jar back to v1.5.6 carries one), so this is the path for a jar tlaup builds or a future upstream publishes without it. Research 26 also confirms taking the commit from the jar and not from the tag: the v1.7.1 tag points at `be99a7d`, and its jar was built from `cdddf55`, the release branch. Should a check against a tag's commit ever be added, it must peel annotated tags (v1.5.6, v1.5.7, v1.6.0 and v1.7.2 are annotated) and be a warning, not a failure, for releases older than v1.7.4; none is designed.

## V6 Remove installs from a URL

Roadmap: "Remove installs from a URL (decision D13). Do this first; it removes cases the items below would otherwise handle."

**Design.** Delete `is_url`, `extract_version_from_url`, `download_version_from_url`, `write_version_metadata_from_url`, the URL branch of `install`, and their tests (`test_version_manager_url.py`, `test_urls.py`, the URL tests in `test_install.py` and `test_metadata.py`). `tool install https://...` is then refused by the version grammar, which has no colon in a name: a usage error (code 2) with the hint that installing from an address is not supported ([02 X3](02-cross-cutting.md#x3-version-syntax)). It is never looked up, so it is not "not found" (4).

**Changelog.** Removed: "`tlaup tool install <URL>`. Install by version name; installing from an address may return later."

**Depends on.** Nothing; third in the order of work.

## V7 GitHub client

Roadmap: "GitHub token support (`GITHUB_TOKEN`, `GH_TOKEN`), `Accept` and `User-Agent` headers, retry with backoff, and a clear message when rate-limited. The token is never printed ... and is sent only to the GitHub API host." "Refuse unencrypted addresses and any redirect to one." "Do not crash on a non-JSON or non-list API response."

**Design.**

```python
# tlaup/versioning/github.py
class GitHubClient:
    def __init__(self, base_url: str, *, token: str | None, token_hosts: Collection[str], user_agent: str,
                 sleep: Callable[[float], None] = time.sleep, attempts: int = 3): ...
    def get_json(self, path_or_url: str) -> tuple[Any, Mapping[str, str]]
    def get_paged(self, path: str) -> list[Any]                  # follows Link: rel="next"
    def download(self, url: str, dest: BinaryIO, progress) -> DownloadInfo
```

- **Base address**: the setting `tool.repository`, default `https://api.github.com/repos/tlaplus/tlaplus` ([14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay)). It must be `https`, with no user name or password, no query string and no fragment; anything else is `ConfigInvalid`.
- **How an address is read.** Every decision about an address (is it `https`, is it this host, may it carry the token) is made on **the address `requests` will connect to**, not on the string as it arrived: the client prepares the request first and reads `PreparedRequest.url` with `urllib.parse.urlsplit`. The two can differ. For `https://evil.example\@api.github.com/x`, `urlsplit` on the raw string gives the host `api.github.com`, while `requests` 2.34.2 prepares a request to `evil.example` (found by the third check; tried again by preparing requests without sending them). The auth object that adds the token is handed the prepared request, so it reads the right address by construction; the same-host checks for a redirect and for a "next" address prepare the request before they compare. An address is refused outright, before anything is sent, when it holds a backslash, a user part (`user@` or `user:password@`), white space or a control character, or when `requests` cannot prepare it: `ConfigInvalid` for `tool.repository`, `RemoteDataError` for an address a server sent. In the prepared address the scheme must be `https`; the host is `hostname`, which is lower-cased and has no port or user part; the port must be absent or 443. An address with any other port, or one that does not parse, is treated as another host: it gets no token and fails the same-host checks below. Host names are compared whole, never by suffix. Tried with the locked `requests` 2.34.2: `https://API.GitHub.com/x` gets the header, `https://api.github.com:8443/x` does not.
- **Headers**: `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, `User-Agent: tlaup/<version>`. No contact details in the user agent.
- **Token**: `GH_TOKEN`, else `GITHUB_TOKEN` (the order the `gh` tool uses). **Where it may go** (decision D41): to `api.github.com`, and to the hosts listed in the user-level setting `tool.token_hosts` ([14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay)); nowhere else. `token_hosts` passed to the constructor is that set. The header `Authorization: Bearer` is added **per request**, by an auth object set on the session, and only when the request's address, read as above, is `https` on a host in the set. So:
  - the default setup sends the token to the API and not to the host that serves assets;
  - `tool.repository` pointing at another host does **not** send the token there, unless the user also listed that host in `tool.token_hosts`. A repository address can come from the environment and, in milestone 3, could have come from a project file; the token must not follow it. Neither setting can be set by a project file ([14 F1](14-config-and-cli.md#f1-layered-configuration));
  - a redirect, or the "next" address of a paged list, is a new request and is checked the same way.

  The token is held in one private attribute; the client's `repr` and every error message omit it; `--debug` output passes through a filter that replaces the token's value with `***` wherever it appears.
- **`.netrc` is never used.** `requests` reads `~/.netrc` (or `$NETRC`) and adds its credentials to a request when the session and the request have no auth object; it then replaces an `Authorization` header set by hand. Read in the locked 2.34.2 (`Session.prepare_request`) and tried: with a netrc entry for the host, a session with a hand-set bearer header sent `Basic` credentials instead, to the API host and to the asset host alike. The client therefore always sets its own auth object on the session, also when there is no token; with one present `requests` does not read netrc (tried: the API request carried `Bearer`, the request to the asset host carried no `Authorization`, and with no token neither did). The object must be **truthy**: `requests` tests it with `not self.auth`, so an auth object that defines `__bool__` or `__len__` and comes out false lets netrc back in (found by the third check against a local server). The client's auth class defines neither, and a unit test asserts `bool(session.auth)` with and without a token. `trust_env` stays on, so the proxy variables and the certificate variables of the environment still apply (tried for `HTTPS_PROXY`). The other place `requests` reads netrc is when it follows a redirect itself, which the client never lets it do (below). The changelog says that credentials in `.netrc` are not used.
- **Which address a jar is downloaded from.** The asset's `browser_download_url` from the release object, which is the address today's code uses and the one research 7 describes: it names the asset by tag and file name, on `github.com`, and redirects to a storage host with a signed query string. `github.com` is not `api.github.com`, so with the default settings **the download carries no token**, on the first request and on the redirect. The asset's API address (`.../releases/assets/<id>`) is not used: it would put the download on the token's host for no gain with a public repository. With `tool.repository` on a host listed in `tool.token_hosts`, the download address is whatever that server's release object gives, and it carries the token only if its host is in the list. Downloading from a private repository or a GitHub Enterprise host was not tried by anyone.
- **Query strings never leave the client.** A redirect target and a "next" address can carry a signed or otherwise meaningful query string. Every address the client puts into an error message, a note, `build.json` (`Source.url` is the `browser_download_url`, never a redirect's target) or a debug line is cut at the `?`. The exceptions of `requests` quote the full address in their text, so the client does not let that text through as it is: it hands each query string it meets to the same filter that hides the token, and the filter removes it from everything printed under `--debug`, the traceback included.
- **Redirects** are followed by hand (`allow_redirects=False`, at most five): each `Location` must be `https`, otherwise `NetworkError("refused a redirect to an unencrypted address")` before any request is sent there.
- **Retry**: on a connection error, a timeout, or a 5xx answer: up to `attempts` tries in all (three by default), with waits of 1 and then 2 seconds between them, doubling for a larger `attempts`, through the injected `sleep`.
- **Rate limit**: a 403 or 429 with `x-ratelimit-remaining: 0` or a `Retry-After` is `RateLimited(reset_at)`, raised at once with no retry. The message: "GitHub's rate limit is used up (resets at HH:MM). Set GITHUB_TOKEN to raise it from 60 to 5,000 requests an hour." When a token was sent, the second sentence is left out.
- **Bad answers**: a body that is not JSON, or a list where an object is expected or the reverse, is `RemoteDataError` naming the address.
- **Pagination**: `get_paged` asks for `per_page=100` and follows the `rel="next"` address from the `Link` header (research 8: the addresses are on another path than the request's, so they are used as given, not rebuilt). Before it is used, the address must be `https` and on the same host as the request that returned it, both read as above; otherwise `RemoteDataError`. At most 50 pages are followed.
- **Addresses built from names**: a tag put into a path is percent-encoded ([02 X3](02-cross-cutting.md#x3-version-syntax) allows `/` in a tag).
- **TLS** uses the operating system's trust store; `truststore` is set up in the client's constructor, not when the package is imported ([14 F9](14-config-and-cli.md#f9-startup-cost)).
- Every request has a timeout (10 seconds to connect, 30 between bytes).

**Rejected.** `requests`' own redirect following with a check afterwards: by then the request to the unencrypted address has been made. `urllib3.Retry` on the adapter: sleeps on its own clock, which tests cannot replace. Reading the token through the `gh` tool: starts a process and couples tlaup to it.

**Tests.** The client rows of [01 T6](01-testing.md#t6-download-and-github-failure-tests), each through `responses`. Token scope, unit: with `GH_TOKEN` set, a recorded install makes requests to two hosts, and the API requests carry the header while the download does not; with `tool.repository` on another host and `tool.token_hosts` empty, no request carries it; with that host listed, requests to it do; a redirect from the API host to an unlisted host is followed without it; a `Link` "next" address on another host, on the same host with port 8443, or with `http`, is `RemoteDataError`; the API host written in upper case gets the header and the API host with port 8443 does not; a `Link` "next" address and a redirect `Location` of the form `https://other.example\@api.github.com/x` are refused with `RemoteDataError` and no request is sent; `tool.repository` set to that form, or to one with a tab in the host, is `ConfigInvalid`; `tool.repository` with a user name in it is `ConfigInvalid`; three failing answers give exactly two sleeps, of 1 and 2 seconds. Netrc, unit: with `NETRC` pointing at a file that has entries for the API host and the asset host, and `GH_TOKEN` set, the API request carries the bearer header and the download carries no `Authorization`; with no token, neither request carries one. Token secrecy: a feature (in-process) runs `tlaup --debug tools install rolling` against a failing GitHub and asserts the token's value appears in neither stream. Query strings, plain pytest (the feature steps have none for a redirect with a `Location`, nor for the contents of `build.json`): `responses` serves a download that redirects to an address with `?sig=secret-value`; once the body then fails, and the test asserts `secret-value` is in neither captured stream under `--debug`; once it succeeds, and the test asserts no `build.json` under the store contains it.

**Changelog.** Added: "`GITHUB_TOKEN` or `GH_TOKEN` is used for GitHub API requests, which raises the rate limit. The token is sent only to `api.github.com`, and to hosts you list in `tool.token_hosts`; it is never printed. Credentials in `.netrc` are not used." Fixed: "A GitHub rate limit was reported as a generic failure." "A non-JSON answer from GitHub (for example from a proxy) caused a traceback." Changed: "Unencrypted addresses, and redirects to them, are refused."

**Depends on.** G2, F3. **Risks.** GitHub answers some rate limits with 403 and no headers (secondary limits); these are reported as a plain 403 with GitHub's own message text. A user who points `tool.repository` at a GitHub Enterprise host and forgets `tool.token_hosts` gets unauthenticated requests and, on a private host, a 401 or 404; the error then carries the hint that the token is not sent to that host and names the setting. A real rate-limit answer was recorded by research 29 (top-up): a 403 with `x-ratelimit-remaining: 0` and `x-ratelimit-reset` (seconds since the epoch) and no `Retry-After`, so of the two tests above `remaining == 0` is the one that fires, and the reset time comes from `x-ratelimit-reset`. A real 429 was not obtained; it stays handled as documented. The netrc rule rests on how one `requests` version decides to read the file; the netrc unit test is what fails if a later version reads it in another place. A user who relied on `.netrc` to authenticate to GitHub through tlaup has to set `GH_TOKEN` instead; 0.8.2 had no token support, so netrc was the only way, and the changelog line says so.

## V8 Remote listing and its cache

Roadmap: "Read all pages of tags and releases; choose 'latest stable' by version, not by API order; never install a prerelease while saying 'stable'." "Key the remote-version cache on the request, not only the asset name, and write it atomically."

**Facts (research 8).** Releases are the list of what can be downloaded; 17 today, one page. Tags (114, two pages) are needed only for commits, which V5 no longer takes from them. Today's code reads one page of 30 tags and loses `rolling` at the next `v1.x` tag.

**Design.**

```python
# tlaup/versioning/remote.py
@dataclass(frozen=True)
class Release:
    tag: str; prerelease: bool; draft: bool
    created_at: str; published_at: str | None
    asset: Asset | None                 # the tla2tools.jar asset, None if the release has none

@dataclass(frozen=True)
class Asset:
    id: int; size: int; digest: str | None; updated_at: str
    download_url: str                   # the release object's browser_download_url (V7)

class Remote:
    def __init__(self, client: GitHubClient, cache_dir: Path, *, now): ...
    def releases(self, *, max_age: float = 3600) -> tuple[list[Release], Freshness]
    def release(self, tag: str) -> Release          # GET /releases/tags/<tag>; never cached
    def resolve(self, spec: VersionSpec) -> Release # "stable" -> stable_of(releases(max_age=0)); else release(tag)
```

- **Only releases are read.** `releases()` is `get_paged("/releases")`: one request today. The tags endpoints are not used. This departs from the roadmap item's "read all pages of tags and releases", for the reason in the facts above, and the README lists it. One consequence for the tests: the roadmap's milestone 2 case "a tag without a commit" has nothing left to test, because no commit is taken from a tag; [01 T6](01-testing.md#t6-download-and-github-failure-tests) has no row for it.
- **`stable`** is `stable_of` (V2): the highest version number among releases that are not prereleases, not drafts, and have the jar. If there is none, `VersionNotFound("no stable release is available")`; it never falls back to the first entry.
- **Install and upgrade ask fresh.** `release(tag)` is never cached, and `resolve("stable")` refreshes the list. Only `tool list` uses the cached list.
- **The cache** is one file per request: `<cache>/remote/<first 16 hex digits of SHA-256 of the address>.json`, holding `{"schema": 1, "url": ..., "fetched_at": <UTC>, "data": ...}`, written to a temporary file and moved into place. Age is computed from `fetched_at` with the injected clock, not from the file's modification time. A cache file that cannot be read is treated as absent.
- **`Freshness`** keeps today's four states (roadmap, "Keep"): online, cached, stale (network failed, old data shown), unavailable. A missing asset or a 404 is never cached (research 7: it can be a one-second gap).
- `tlaup cache clean` removes `<cache>/remote/` ([23 C1](23-command-layout.md#c1-command-tree)); `fetch-cache clear` goes.

**`tool list` in the first wave** (the milestone 4 item improves it further): one table on stdout; rows are the releases in the order of X4, each followed directly by the installed builds of that name; installed builds whose name is no longer upstream come last. Columns: Version, Build (`commit7`, and the CalVer where known), Published (the asset's update date), Status (`available`, `installed`, `installed, update available` when the newest installed build of that name differs from the published one by digest), Pinned. The header "Tag/SHA" becomes "Build". When the network is unavailable, the installed builds are listed and one `warning:` line goes to stderr through the UI helper.

**Rejected.** Reading tags to show the remote commit in `tool list`: two more requests and the race of research 7, to show a number that may not match the jar. `GET /releases/latest` for stable: one release only, depends on the maintainers' flag, and research 8 calls it a cross-check, not a source. Conditional requests with ETags: a real saving on the rate limit, not needed at one request per listing.

**Tests.** The listing rows of [01 T6](01-testing.md#t6-download-and-github-failure-tests). The two-page case uses a recording made for the test: the real list is one page today, so the recorded 17 releases are served as two pages with a `Link` header in the form research 8 recorded for tags. A real two-page recording with its headers now exists (research 29, `releases-paged`, asked for ten at a time; top-up) and replaces the made one: the second page has no `rel="next"`, and the next addresses have the form `https://api.github.com/repositories/<id>/releases?...&page=N`. Unit: the cache with an injected clock at 59 and 61 minutes; a corrupt cache file; two different base addresses do not share a cache file. `tools_list.feature`: online, cached, stale and unavailable, each against an expected file; an older installed rolling build shows `update available` on its own row, directly under the `rolling` row.

**Changelog.** Fixed: "Only the first 30 tags were read from GitHub, so `rolling` would have disappeared at the next upstream release." "The 'Tag/SHA' column of `tool list` is now 'Build'." Changed: "`tool list` keeps installed builds next to their upstream release and marks one that has a newer build available." Removed: "`tlaup fetch-cache clear`; use `tlaup cache clean`."

**Depends on.** V7, V2.

## V9 First-run prompt

Roadmap: "First-run prompt (decision D4): when nothing is pinned, ask once between stable and rolling, then install the choice. A flag and an environment variable answer it; error with a hint when there is no terminal." Relies on D4, D32.

**Design.** Two functions. The question itself is one of them, so the preflight and `tool install` ask it the same way:

```python
def choose_first_build(remote, ui, *, auto_install: str | None) -> VersionSpec      # "stable" or "rolling"
def ensure_tools(store, remote, client, ui, *, auto_install: str | None, may_install: bool = True) -> Build
```

`ensure_tools` is called by the preflight of `tlc`, `sany`, `pcal` and `repl` ([11 R11](11-runner.md#r11-preflight)), **after the spec and a named cfg have been checked** (decision D45). A mistyped spec name is therefore reported, with code 4, before any question is asked and before anything is downloaded.

| State | What happens |
| --- | --- |
| A build is pinned | It is returned. |
| Builds are installed, none pinned | `NoPinnedBuild` (code 3) with the names to pin. No prompt: the choice between stable and rolling is not the question here. |
| Nothing installed, `may_install` is false | `NoToolsInstalled` (code 3) with the hint to run `tlaup tool install stable` or `rolling`. This is `--show-command`, which never asks and never installs ([11 R9](11-runner.md#r9-show-command)). |
| Nothing installed, `auto_install` is `stable` or `rolling` | That is installed and pinned (V12), with one notice on stderr. |
| Nothing installed, `ui.is_interactive()` | The prompt below; the choice is installed and pinned, and the command carries on. |
| Nothing installed, not interactive, no answer | `CannotAsk` (code 3): "no TLA+ tools installed" / "run `tlaup tool install stable` or `tlaup tool install rolling`, or set TLAUP_AUTO_INSTALL". |

The prompt, on stderr:

```
No TLA+ tools are installed. Which build should tlaup install?
  1) stable   v1.7.4, released 2024-08-05
  2) rolling  the newest development build, updated 2026-11-15
Choice [1]:
```

- The question is written to stderr and the answer read from stdin, so it is asked only when **both** are terminals (`ui.is_interactive()`, [14 F6](14-config-and-cli.md#f6-messages)). With stderr redirected the user would be asked a question they cannot see.
- The dates come from the release list (one request). If the network is unavailable the prompt is not shown and the error is the network error.
- `auto_install` comes from the option `--auto-install stable|rolling` on the four run commands, else from `TLAUP_AUTO_INSTALL`; any other value is a usage error.

`tlaup tool install` with no version asks the same question through `choose_first_build`; what it does with the answer, and what it does when builds are already installed, is [V12](#v12-install).

**Rejected.** A general `--yes`: it does not say *which* build. A setting `tool.default`: decision D4 is about the first run only; once something is pinned the pin is the default. Asking again when builds are installed but none is pinned: the user has builds and needs to pick one, which `tool pin` does. Asking before the spec is checked (the roadmap's order, and the first version of this design): a typo in the spec name led to a question and a download before the typo was reported (D45).

**Tests.** The prompt needs the release list and its answer leads to a download, and a real process cannot be served recordings, so every case in which the question is asked is plain pytest through the one seam of [14 F6](14-config-and-cli.md#f6-messages): `ensure_tools` (or `choose_first_build`) called with a `Ui` built on in-memory streams, the answers in its stdin and `interactive=True`, and `responses` serving GitHub. Those cases: the prompt answered `2` installs and pins rolling and returns the build; an empty line takes the default, stable; `9` and then `1` asks twice; an empty read (end of input) raises `CannotAsk`; the network failing before the prompt raises the network error and writes no question; `may_install=False` raises `NoToolsInstalled` and asks nothing, whatever `interactive` and `auto_install` are. `first_run.feature` (in-process, where the streams are not terminals, so nothing is ever asked): the rows of the table that ask no question; `TLAUP_AUTO_INSTALL=rolling tlaup tlc Spec` installs and runs, the fake `java` being started for the original command; `--auto-install nightly` exits 2; nothing installed and a spec that does not exist exits 4 with no request to GitHub and nothing installed, also with `TLAUP_AUTO_INSTALL` set; `tlc Spec --show-command` with nothing installed exits 3 with no request, also with `TLAUP_AUTO_INSTALL` set; nothing installed and no variable exits 3 (`CannotAsk`). One real-process scenario on a pty covers the order of D45 where a prompt could otherwise appear: nothing installed and a spec that does not exist exits 4 and the screen shows no question. "stdin a terminal and stderr not" is covered where it needs no network, by the uninstall scenario of V3.

**Changelog.** Added: "With no tools installed, `tlaup tlc` (and `sany`, `pcal`, `repl`) asks whether to install the stable release or the rolling build, installs it and carries on. `--auto-install stable|rolling` or `TLAUP_AUTO_INSTALL` answers the question for scripts. The spec is checked first, and `--show-command` never asks or installs."

**Depends on.** V1, V5, V8, V12, R11, F6. **Risks.** A first run downloads 4.5 MB in the middle of a command the user expected to be quick; the notice on stderr names what is being installed and from where.

## V10 Remove old layouts

Roadmap: "Remove the legacy fallback jar path, so it is never shown as the expected location, and all other legacy-layout code (pin migration, flat module form) ... A pin that points at a missing build is a clear error with a hint, not a silent fallback."

**Design.** Delete: `get_tlc_jar_path` and `tlc/compiler.py` (callers use `store.pinned().jar`); `_migrate_legacy_pin` and its call; the `default` target of `uninstall`; in `ClasspathResolver`, the two "Legacy fallback" lines that add a module's top folder and the `modules_dir/lib` lookup (the flat module form); `get_github_cache_file` and the cache-file name nothing writes; `test_migration.py` and the legacy tests in `test_path.py` and `test_uninstall.py`. The `tlaup` folders have never held these layouts (D14).

The error for a pin that names a missing build is `PinnedBuildMissing` (V1, R11).

**Changelog.** Removed: "Support for old storage layouts (a jar directly in the cache folder, the symlink pin, the `tlc` folder, modules without a `modules/` subfolder). The `tlaup` folders never contained them."

## V11 Concurrent installs

Roadmap: "Concurrent installs: write the pin and metadata atomically and take a lock, so two installs of one version do not collide."

**Design.** Covered by V1, V5 and V12 together: every write is a rename; mutations hold `<cache>/tool/.lock`; downloads happen outside the lock into separate temporary folders, and the lock is taken only to move a verified build into place and to write the pin. Two installs of one build both download; the second finds a build with the same name and bytes present under the lock and discards its copy (V12). A lock that cannot be taken in 60 seconds is `StoreLocked` (code 5) naming the lock file. The store lock is never waited for without a timeout (top-up, [research 30](../research/30-library-behaviours.md)): since `filelock` 3.29.6 a second lock object waiting with no timeout in the same thread raises `RuntimeError("Deadlock ...")`, and with a finite timeout the same case gives `Timeout`, which is `StoreLocked`. A lock is taken and released in one thread, since `FileLock` objects are thread-local. The lower bound is `filelock>=4.2.1` ([30 B2](30-ci-and-release.md#b2-build-fixes)), for the reasons R6 gives: the `.tmp/` lock files below are removed under their lock as run-folder lock files are.

**Leftover temporary folders** (a tlaup killed mid-download or mid-removal). Each folder under `.tmp/` has a lock file beside it, `.tmp/<random>.lock`, created and taken before the folder is made and held by the owning process until the folder has been moved into place or deleted. The next mutation that holds the store lock goes through `.tmp/`: for each folder it tries to take that folder's lock without waiting; if it gets it, the owner is gone and the folder and its lock file are removed; if not, the folder is in use and is left alone. No age is involved, so a download that takes two hours on a slow line is never removed under its owner. (The first version of this design removed folders "older than one hour", which could.) The lock is beside the folder, not inside it, so there is no moment at which the folder exists and is not yet locked. This is the same rule the run folders use ([11 R6](11-runner.md#r6-run-folders)).

**The lock file of a temporary folder** is removed by its owner, while it still holds the lock and as the last thing before the release, once the folder has been moved into place or deleted. A lock file with no folder, whose owner was killed after making the file and before making the folder, is removed by the cleanup under the run folders' rule: only when it is more than one hour old, and while the cleanup holds its lock ([11 R6](11-runner.md#r6-run-folders)). The first wording did not say who removes these files, and the cleanup looked at folders only, so they would have stayed for ever. Found while writing the spec (2026-11-18, [finding K2-4](../../specs/README.md#findings)), not by TLC: the spec does not model the lock files under `.tmp/`, whose questions are the run folders' and are checked there.

**Tests.** The last row of [01 T6](01-testing.md#t6-download-and-github-failure-tests) (two threads, a barrier, one store). A unit test holds the store lock in a second process and asserts `StoreLocked` with a short timeout. Unit: a temporary folder whose lock is held by a second process survives a mutation, whatever its age; one whose lock is free is removed, whatever its age. Unit (formal check, 2026-11-18): after an install and after a failed download nothing of the command is left under `.tmp/`, neither folder nor lock file; a lock file with no folder survives a cleanup at 59 minutes and is removed at 61.

**Depends on.** V1, V5, V12. **Risks.** A lock held on a network file system may not behave as on a local disk; `filelock` falls back to a weaker lock where the system has none, and the cache folder is expected to be local. Not tried.

**Changelog.** Fixed: "Two `tlaup tool install` commands running at once could leave a damaged install."

## V12 Install

Added after the stage 3 review, which found that no section designed `install` itself: [00](00-overview.md#packages-after-the-first-wave) pointed `versioning/install.py` at V3 and V4, which are uninstall and upgrade. Roadmap items served: "Download to a temporary file, check it is a valid jar, then rename ... `--force` keeps the old build until the new one is verified" (the part V5 leaves to the caller), the help-text point "`install` with no version; first install is pinned" ([14 F7](14-config-and-cli.md#f7-help-text)), and the error-message point "drop 'Successfully installed' after 'already installed' and mention `--force`" ([14 F11](14-config-and-cli.md#f11-error-messages)). Relies on D4, D26, D31, D32 and research 7 and 18.

**Problem.** Today `install` decides "already installed" from a folder name that carries the tag's commit as it was up to an hour ago; with `--force` it deletes first; with no version it installs "latest stable", which could be a prerelease; and it prints "Successfully installed" after "already installed". The first version of this design left the new behaviour to be inferred from V5 and V9, and V5 said a download is discarded when "a build with the same `sha256`" exists, which would have made `tools install v1.8.0` a silent no-op whenever `rolling` holds the same jar, and `tools pin v1.8.0` then fail.

**Design.**

```python
# tlaup/versioning/install.py
@dataclass(frozen=True)
class InstallReport:
    build: Build
    downloaded: bool            # a download was made
    already_installed: bool     # the store already held this name and these bytes
    pinned: bool                # this call pinned it
    could_not_check: str | None # the reason, when the build was installed and GitHub could not be asked

def install(store, remote, client, spec: VersionSpec, *, force: bool = False, progress) -> InstallReport
def same_as_published(build: Build, release: Release) -> bool      # shared with upgrade (V4)
```

**One rule for "already there": the same name and the same bytes.** The store identifies a build by its name and its SHA-256 (V1). `rolling` and `v1.8.0` holding one jar are two builds, each stored once; installing one never satisfies a request for the other ([02 X4](02-cross-cutting.md#x4-rolling)).

What `tool install VERSION` does, by case. In every case the release is looked up fresh, never from the lookup cache (V8): one request.

| Case | What happens | Download |
| --- | --- | --- |
| No build of that name is installed | Fetch and verify (V5), add to the store. | Yes |
| A build of that name is installed and is what upstream publishes now (`same_as_published`) | Nothing is downloaded. The line is `v1.7.4@5a47802 is already installed (use --force to download it again)`, with no "Successfully installed" after it. The build's `prerelease` flag and source record are refreshed if upstream changed them. If another tlaup has removed the build by the time this one holds the lock, the command starts again and is the first row (V1, "What a mutation decides on is read under the lock"; formal check, 2026-11-18). | No |
| A build of that name is installed and upstream now publishes other bytes (a moving tag) | Fetch and verify, add as a second build of that name. The older build stays; `install` never removes a build. The note names both and says which is pinned. | Yes |
| A build of that name is installed, the release has no digest, and upstream uploaded the same file again (same bytes, a new upload time) | `same_as_published` is false, so the jar is downloaded and verified. The store finds the name and bytes already there, discards the copy, and the build's source record is updated with the new upload time (`store.update`), so the next install makes no download. The line is the "already installed" one. | Yes, discarded |
| `--force` | Always fetch and verify. If the result has the same name and bytes as an installed build, the installed build is kept and repaired in place: the verified jar replaces the installed one with `os.replace`, then `build.json` is rewritten the same way. If the bytes differ it is the moving-tag row. An installed build is never deleted first. | Yes |
| `NAME@COMMIT`, `NAME@CALVER` or `NAME@sha256:...`, and that build is installed | Already installed; no request is needed to know it, and none is made. | No |
| `NAME@COMMIT` or `NAME@CALVER` matching **several** installed builds (a short commit prefix shared by two, or one commit built twice) | Already installed, as the row above: no request, exit 0, and the line names each matching build in its printed form. With `--force` it is a usage error (code 2) listing the candidates, since one build must be named to be repaired. | No |
| The same with `--force` | `--force` wins over "no request": what upstream publishes under `NAME` is fetched and verified. If it is the build that was named, that build is repaired in place. If upstream publishes another build now, nothing is installed or changed and the error is `VersionNotFound` (code 4), saying that the named build is installed, cannot be downloaded again, and was left as it is. | Yes, discarded on mismatch |
| `NAME@COMMIT` or `NAME@CALVER`, not installed | Fetch what upstream publishes under that name; if the jar's commit or build time is not the one asked for, nothing is installed and the error is `VersionNotFound` (code 4), naming the build upstream publishes now and saying that an older build of a moving tag cannot be downloaded (research 5). | Yes, discarded on mismatch |
| `NAME@sha256:...`, not installed | `VersionNotFound` (code 4): the form names installed builds only ([02 X3](02-cross-cutting.md#x3-version-syntax)). | No |
| A bare CalVer | Installed, under one name or under several (`rolling` and `v1.8.0` hold the same jar today): already installed, and the line names each. Not installed: `VersionNotFound`; the first wave cannot fetch a build by CalVer ([02 X3](02-cross-cutting.md#x3-version-syntax)). `--force` with a bare CalVer is a usage error: there is no name to fetch. | No |
| `stable` | Resolved against a fresh release list (V8), then one of the rows above for the tag it names. | |
| `latest`, a URL | Usage errors, both (code 2; [02 X3](02-cross-cutting.md#x3-version-syntax), V6). | No |

`same_as_published(build, release)`: true when the release has a `sha256:` digest and it equals the build's `sha256`; for a release without a usable digest (v1.7.4 and older, research 18), true when the asset's `size` and `updated_at` equal the build's recorded `size` and `source.asset_updated_at`. So `tool install v1.7.4` with v1.7.4 installed costs one API request and no download, which is what the integration job's cache step relies on ([30 I1](30-ci-and-release.md#i1-integration-job)).

**When GitHub cannot be asked and a build of that name is installed.** `install` returns that build with `could_not_check` set; the command prints `warning: could not check GitHub for a newer build of v1.7.4: <reason>` and exits 0. The user asked for the version to be available, and it is. With no build of that name installed, the network error is the result (code 5). `--force` with no network is the network error. This is a choice made in this design; it is listed in the README.

**The pin.** `install` pins the build it returns only when nothing is pinned ("the first build installed is pinned"). "Nothing is pinned" means no pin, or a pin that names a build that is not installed, the state a killed uninstall can leave (D50); so an install puts that state right, as V3 says (review finding FC5; the spec's `PinStep` reads it the same way). "Nothing is pinned" is read under the lock (V1): of two installs that both started with nothing pinned, the first pins its build and the second leaves the pin alone. It never moves an existing pin: decision D26, the pin following a newer build of its tag, stays a milestone 3 item ([40](40-later-milestones.md#milestone-3-reproducibility)). When a second build of the pinned name is installed, the note says the pin did not move and gives the command: `rolling@1a2b3c4 installed; rolling@bc1b506 is still pinned (tlaup tool pin rolling@1a2b3c4)`. `tool upgrade` is the command that moves the pin and removes the old build (V4).

**`tool install` with no version.** It asks which build, through `choose_first_build` (V9): the stable-or-rolling question on a terminal; the value of `TLAUP_AUTO_INSTALL` when set, the same variable that answers the question for the run commands; otherwise `UsageError` (code 2) asking for `stable` or `rolling`. It asks whether or not builds are already installed, because the user ran `install`; it then follows the table above for the answer. It no longer picks "latest stable" silently. In milestone 3 "no version" will mean "what the project file asks for".

**How the store is used.** Under the store lock: `store.find` for the name; then `store.add(jar, info, name=..., prerelease=..., source=...)`. `add` decides "already there" by comparing the name and the full SHA-256 with the installed builds, never by the id (V1): if such a build exists it discards the temporary copy and returns that build, and with `repair=True` (the `--force` rows) it first replaces the installed jar and `build.json` with the verified ones; otherwise it moves the folder to the first free id. Two tlaups installing one build at once both end with the one build (V11).

**Rejected.** *Discarding a download whenever any build has the same SHA-256* (the first version of V5): makes a name un-installable while another name holds the same jar. *One stored jar with two names*: the right end state, and milestone 3's, because it changes `Build.name` into a list and with it the pin and every printed form. *Skipping the request when the name is installed*: correct for a tag that never moves, wrong for `rolling` and for `v1.8.0` today, and tlaup has no table of which tags move (X4). *Failing when GitHub cannot be asked and the build is installed*: makes an offline machine, or one over the rate limit, fail a command whose purpose is already met. *Moving the pin to the newer build of its name*: D26, milestone 3. *Removing the older build of a moving tag on install*: that is `upgrade`; an older rolling build cannot be downloaded again.

**Tests.** `tool_install.feature` (in-process, GitHub served from recordings): each row of the table, asserting `the installed builds are:`, the pin, the note or error, and the number of requests and downloads; `rolling` installed, then `tool install v1.8.0` with the same recorded jar gives two builds and `tool pin v1.8.0` succeeds; `tool install v1.7.4` run twice: after the second `I run`, `0 jar download(s) were made` and `1 request(s) were sent to GitHub` (the counts cover the last run only, [01 T5](01-testing.md#t5-feature-files-and-steps)); the same with GitHub failing the second time exits 0 with one `warning:`; `--force` whose download fails leaves the installed build intact and pinned (the row of [01 T6](01-testing.md#t6-download-and-github-failure-tests)); `--force` on a build whose jar on disk was truncated by the test repairs it; first install pins, second does not; no version with `TLAUP_AUTO_INSTALL=stable` installs stable without asking; no version, no terminal, no variable exits 2; `--force v1.7.4@<commit>` with that build installed and published repairs it, and with another build published exits 4 and changes nothing; a release with no digest whose asset has a new upload time and the same bytes makes one download, leaves one build, and a second install makes none; a bare CalVer installed under two names exits 0 and names both; `rolling@<prefix>` matching two installed builds exits 0, names both and sends no request, and with `--force` exits 2; an address exits 2 with no request. The question for "no version" needs the release list, so it is plain pytest, not a feature: the command's function is called with a `Ui` built on in-memory streams, the answer in its stdin and `interactive=True` ([14 F6](14-config-and-cli.md#f6-messages)), with one build installed and `responses` serving GitHub, and the chosen build is installed. Unit: `same_as_published` for a digest match, a digest mismatch, no digest with equal and with different size or date, and a digest in upper case.

**Changelog.** Fixed: "`tlaup tool install` printed 'Successfully installed' after 'already installed'." "`tlaup tool install` could treat a moving tag such as `rolling` as up to date for an hour after upstream published a new build; it now asks GitHub every time and compares the installed jar with the published one." Changed: "Installing a newer build of a name that is already installed keeps the older build and leaves the pin where it is; `tlaup tool upgrade` replaces the older build and moves the pin." Breaking: "`tlaup tool install` with no version asks which build to install (stable or rolling), or takes the answer from `TLAUP_AUTO_INSTALL`, and fails without either; it used to install the latest stable release."

**Depends on.** V1, V2, V5, V8, V9. **Risks.** For a release without a digest, "already installed" rests on the asset's size and upload time, which shows that upstream did not replace the file, not that the file on disk is undamaged; `tlaup doctor` checks the installed jar against its recorded SHA-256 ([23 C1](23-command-layout.md#c1-command-tree)), and `--force` repairs it. Keeping the older build of a moving tag lets rolling builds pile up at 4.5 MB each; `tool list --installed` shows them and `tool upgrade` or `tool uninstall` removes them.
