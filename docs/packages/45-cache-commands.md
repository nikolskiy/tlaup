# 45. The `cache` commands: `dir`, `list`, `clean`

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup cache dir` prints the cache folder; `tlaup cache list` shows every run folder with what [11 R6](../design/11-runner.md#r6-run-folders) records about it and the total size of the kept ones; `tlaup cache clean` removes what [23 C1](../design/23-command-layout.md#c1-command-tree) says, by the rules of R6, and prints what it removed and the space freed. No network, no Java, and installed tools and modules are never touched.

## Covers

- Roadmap items:
  - "Review the layout of every command so it follows the most common CLI patterns ..." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 334), in part: "one `cache` command replacing `fetch-cache clear` and the `tlc --cleanup` flag". The tree as a whole is [48](48-command-tree.md).
  - "Stop run-cache cleanup from deleting other specs' directories ... TLC also adds a timestamped folder per run that is never removed; define when those are cleaned up." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust), line 190), in part: the user's command for it. The rules and functions are [35](35-run-folders.md); `--keep`, the sweep at every run and removing `--cleanup` are [39](39-tlc-command.md).
- Design sections:
  - [23 C1](../design/23-command-layout.md#c1-command-tree): the rows "`fetch-cache clear` and `tlc --cleanup` become `cache clean`; `cache dir` and `cache list` are new" and "`cache list` is new", with `--all` and a kind (question Q14) and nothing to clean (preserved-behaviour row O7) as C1 now states them; the `cache` lines of the tree, `cache.feature` of the Tests, and the changelog line of the first row (see Changelog).
  - [11 R6](../design/11-runner.md#r6-run-folders), in part: "Kept folders are visible" (the command `cache list`), the `cache clean` bullet list, and the feature tests "`cache clean` removes an unsettled folder that is not resumable and leaves a kept one; `cache clean <run-id>` removes the kept one; `cache clean` with an unknown id exits 4" and "`tlaup cache list` does not" print the reminder. The functions are 35's.
  - [12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache), the bullet "`tlaup cache clean` removes `<cache>/remote/`".
  - [13 J3](../design/13-modules-and-java.md#j3-one-java-start): the remembered Java check, which `cache clean --all` removes (C1).
  - [14 F2](../design/14-config-and-cli.md#f2-folder-overrides): "`tlaup cache dir` ... print the folders in effect".
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes) and [20 G2](../design/20-groundwork.md#g2-domain-errors), in part: the `errors.feature` scenarios for what `cache clean` reaches.
  - The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md), row O7 (owner 45): clearing when there is nothing to clear succeeds.

## Depends on

- [35](35-run-folders.md): `list_runs`, `RunRecord`, `clean_runs`, `CleanReport`, `format_size`, `list_entries`, `EntryVisit` (for the lock files, below), the `NotFound` family and `FileOperationError` that `clean_runs` raises for a run id.
- [39](39-tlc-command.md): `tlaup tlc --keep`, which makes the kept folder `cache.feature` works on (C1: "a kept folder made by the checkpoint-writing fake `java` under `--keep`"), and the scenario steps 39 uses with it.
- [25](25-remote-listing.md): the layout of `<cache>/remote/` (one `<key>.json` per request, written through a temporary file and a rename) and the rule that a cache file that cannot be read is treated as absent, which is what makes removing the folder safe at any moment.
- [20](20-java-location.md): `<cache>/java.json`, and its rule that a missing or unreadable file is ignored and rewritten by the next check.
- [18](18-feature-harness.md): `tests/test_features.py`, the steps (`the cache holds <n> run folder(s)`, `the cache holds no lock files`, `{kept}`, `{runs}`, `a file "<path>" containing:`, `the file ... exists` / `does not exist`, the result steps), `errors.feature`. 18's table gives `{kept-id}` to this package (see Context).
- [17](17-error-handler.md) and [16](16-ui-messages.md): the root group that maps errors; `Ui.result`, `Ui.note`.
- [02](02-errors-and-paths.md): `AppPaths.cache`, `runs`, `remote`, `java_cache`.

Change from the draft (35, 25, 20, 39): 18, 17, 16 and 02 are named because the commands and the scenarios use them directly; none changes the order.

## Files

Creates:

- `src/tlaup/cmd/cache.py`: the `cache` group (`no_args_is_help=True`) and its three commands, thin: each parses its arguments, calls the functions below, prints through `ctx.obj.ui`.
- `tests/features/cache.feature` and its expected files under `tests/features/expected/cache/`.
- `tests/unit/cmd/test_cache.py`: the plain pytest tests under Tests.

Changes:

- `src/tlaup/tlc/rundirs.py`: one function, `clean_lock_files` (Interfaces). 35 built `clean_runs` to visit folders only ("lock files without a folder are the sweep's"); C1 also makes `cache clean` remove a lock file whose folder is gone once it is more than one hour old.
- `src/tlaup/cli.py`: register the group with `app.add_typer(cache_app, name="cache")` and its commands with explicit `command(...)` calls in one block ([23 C1](../design/23-command-layout.md#c1-command-tree), last row). [48](48-command-tree.md) later rewrites the registration block as a whole.
- `tests/features/errors.feature`: the scenarios under Tests.
- `CHANGELOG.md`: see Changelog.

Deletes: nothing. [29](29-tool-commands.md), which comes before 39 and so before this package, deleted `src/tlaup/cmd/fetch_cache/` with the old lookup cache; its old tests went in 03b (decision D62).

Shared with packages that may run beside it (40 to 47 after 39): `src/tlaup/cli.py` (one registration block each), `tests/features/errors.feature` (one block of scenarios each), `CHANGELOG.md`. `src/tlaup/tlc/rundirs.py` is 35's; no other package of the period touches it.

## Interfaces

The commands, from [23 C1](../design/23-command-layout.md#c1-command-tree):

```
tlaup cache dir
tlaup cache list
tlaup cache clean [RUN_ID] [--runs] [--remote] [--all]
```

No option has a one-letter form ([48](48-command-tree.md)'s test checks it).

| Command | stdout | stderr | Exit |
| --- | --- | --- | --- |
| `cache dir` | One line: `AppPaths.cache`. It prints the folder whether or not it exists, and creates nothing. | nothing | 0 |
| `cache list` | One line per run folder, then one total line (below). Nothing at all when there are no run folders. | nothing; no reminder line (R6: "`--show-command` and the `cache` commands do not print it") | 0 |
| `cache clean` | nothing | One `note` per removed run folder, one for the remembered lookups, one for the Java check (with `--all`), then one line with the space freed (below). | 0; 2, 4, 5 (below) |

**`cache list`** prints, for each `RunRecord` from `list_runs(paths)`, in the order of its `started` time (oldest first; folders without `run.json` by `last_change`), one line holding: the run id; the spec's file name and the cfg's (`Spec.tla`, `Spec.cfg`); the build recorded in `run.json`; when it started and when it last changed, as `YYYY-MM-DD HH:MM UTC` ([14 F8](../design/14-config-and-cli.md#f8-wording)'s form for times); its size, through `format_size`; `in use` when its lock is held; whether it is kept and why (`reason`: "interrupted", "tlaup failed", "TLC crashed (exit N)", or "unsettled after a kill" for an unsettled resumable folder); and whether its checkpoint is complete. A folder without `run.json` gets what is known: its id, size and last change. The last line gives the total size of the kept folders and how many there are. The exact column layout is written by stage 4 into an expected file (`cache/list.txt`) and is the worker's to choose; the review reads that file. No network, no Java, no settings: the command needs `AppPaths` only.

**`cache clean`**, the rules of C1 and R6, in its words:

| Given | Removes | Exit |
| --- | --- | --- |
| nothing | Every run folder whose lock is free and that the sweep would remove: an unsettled folder that is not resumable (`clean_runs(paths, include_kept=False)`). Never a kept folder, an unsettled one that asked to be kept and holds a complete checkpoint, or one without `run.json` (D49, D53). Lock files whose folder is gone and that are more than one hour old (`clean_lock_files`). Everything under `<cache>/remote/` (V8). | 0 |
| `--runs` | The run-folder part of the row above, and the lock files; not `remote/`. | 0 |
| `--remote` | Only `<cache>/remote/`. | 0 |
| `--all` | Every run folder whose lock is free, kept, resumable and `run.json`-less ones too (`include_kept=True`); the lock files as above; `remote/`; and `<cache>/java.json` (C1: "Only `--all` with no kind named also removes the remembered Java check"). | 0 |
| `--runs --all` | Every run folder whose lock is free, kept ones included (`include_kept=True`), and the lock files; not `remote/`, not `java.json` (C1: `--all` widens the kind that is cleaned). | 0 |
| `--remote --all` | The same as `--remote`: every remembered lookup goes anyway; not `java.json`. | 0 |
| `RUN_ID` | That one run folder, whatever it is, when its lock is free, and its lock file; nothing else (`clean_runs(paths, include_kept=True, run_id=RUN_ID)`). | 0; 4 when the id names no folder (the `NotFound` family `clean_runs` raises); 5 when its lock is held (`FileOperationError`, "in use") |
| `RUN_ID` with `--runs`, `--remote` or `--all` | Nothing. A usage error, `ConflictingOptions` (review finding TU6), raised before anything is looked at. | 2, one `error:` line |
| `--runs` and `--remote` together | The same as nothing given: both kinds. With `--all` too, the same as `--all` alone except `java.json`, which goes only when no kind is named. | 0 |
| nothing to remove (a fresh home, or a second run) | Nothing. Not an error (C1; inventory row O7). | 0 |

A run folder whose lock is held is never removed and never makes the command fail, except when it is the one `RUN_ID` names: `CleanReport.in_use` lists such folders, and the command prints one `note` per folder left in use. Nothing under `<cache>/tool/` or `<cache>/module/` is touched; the help says so (C1: "It never touches installed tools or modules, which live under the cache folder until milestone 3; the help says so").

**What it prints.** One `note` per removed run folder (its run id), `removed the remembered GitHub lookups` when `remote/` held anything, `removed the remembered Java check` when `java.json` was there, and a last `note` with the total freed, `format_size(...)` of the run folders' `CleanReport.freed` plus the bytes of what was removed under `remote/` and `java.json`. When nothing was removed, one note saying so, and exit 0 (C1: "says that nothing was removed and exits 0"). The wording is the worker's, in [14 F6](../design/14-config-and-cli.md#f6-messages)'s form (no prefix for a note, no "Success:"); the review reads it from the scenarios' stderr.

**Written by stage 4, in `tlaup/tlc/rundirs.py`:**

```python
def clean_lock_files(paths: AppPaths, now: Callable[[], datetime]) -> int
    # visits each entry of list_entries(paths.runs) that has a lock file and no folder, through EntryVisit:
    # takes its lock with one attempt (a held lock is left alone), removes the lock file when it is more than
    # one hour old by its modification time, then releases (R6: the removal is the last thing under the lock).
    # Returns the number removed. The same rule EntryVisit.sweep applies to such an entry.
```

It reuses `EntryVisit.sweep` for these entries if that is exactly the one-hour rule there; the worker checks against 35's code and says which in the pull request. It is not called for a `RUN_ID`, which touches nothing else.

**Removing `remote/` and `java.json`.** `remote/` is emptied file by file (every entry under it, temporary files included) rather than removed as a folder, so a tlaup that writes a lookup at the same moment either sees its rename succeed into an existing folder or fails its own write, which [25](25-remote-listing.md) treats as no cache. `java.json` is removed with `Path.unlink(missing_ok=True)`. A file that cannot be removed is `FileOperationError` (5) naming it.

Consumes: `list_runs`, `RunRecord`, `clean_runs`, `CleanReport`, `format_size`, `list_entries`, `EntryVisit` (35); `AppPaths` (02); `ConflictingOptions`, `FileOperationError` (02); `Ui` (16).

## Tests that must pass

**`tests/features/cache.feature`**, in-process (none of T5's five situations applies: no passthrough, no pipe, no signal, no terminal), per [01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 10. The kept folder is made as C1 says: a `tlaup tlc --keep` run whose fake `java` writes a complete checkpoint and exits with 255, the arrangement of [39](39-tlc-command.md)'s keeping scenarios (`the build ... is installed and pinned`, `a spec ... from the golden specs`, `java replays ... with exit code 255`, `java writes "queue.chkpt, vars.chkpt" into its metadir`, `I run "tlaup tlc Spec --keep"`).

- `cache list` with no run folders: exit 0, `stdout is empty`.
- With the kept folder: `cache list` prints one line holding the run id, the spec's name, the build, its size and why it was kept, and a total line (C1). Asserted fact by fact, since the run id and the times vary (see Context, "The expected file"): `stdout contains "{kept-id}"`, `stdout contains` the spec's file name, `stdout contains "v1.7.4"` (the build), one fact of the size (the unit `format_size` gives for a folder of a few bytes, which is what the fake's checkpoint files make; the exact figure is the unit test of the rendering below), `stdout contains "TLC crashed"` (the reason for exit 255; see Context, "The kept folder's reason"), and the total line's fact. `stderr is empty` (no reminder line).
- `cache clean` leaves that folder: `the cache holds 1 run folder`.
- `cache clean {kept-id}` removes it and its lock file and nothing else: `the cache holds no run folders`, `the cache holds no lock files`, and a file put under `{runs}/../remote/` before is still there. See Context, "Naming the kept folder".
- `cache clean --all` removes every one: with the kept folder and a second, unsettled resumable folder (a second `--keep` run whose fake writes the checkpoint and is then killed is not reachable in-process; use a hand-made folder with a `run.json` holding `"keep": true`, `"ended": null` and a complete checkpoint, written with `a file ... containing:`), `cache clean` leaves both, `cache clean --all` removes both.
- `cache clean nosuch` exits 4 (`stdout is empty`, `stderr contains "error:" 1 times`).
- `cache clean <its id> --all` exits 2 with one `error:` line, and the folder is still there.
- `cache clean --remote` with a file under `<cache>/remote/` and the kept folder: the file is gone, `the cache holds 1 run folder`. `cache clean --runs` with an unsettled folder that is not resumable (hand-made: `run.json` with `"keep": false`, `"ended": null`) and a remote file: the folder is gone and the file stays. `cache clean` with no option removes both.
- `cache clean --all` with `{runs}/../java.json` present (T5 has no `{cache}` placeholder; the cache folder is the parent of `{runs}`) removes it; `cache clean` without `--all` leaves it. The file is made with `a file ... containing:` (the fake `java` is a script and is never remembered, J3).
- `cache clean --runs --all` with the kept folder, a file under `{runs}/../remote/` and `{runs}/../java.json`: the kept folder is gone, the remote file and `java.json` are still there (C1, question Q14). `cache clean --remote --all` with the same three: the remote file is gone, the kept folder and `java.json` stay.
- Nothing to clean (inventory row O7, C1): on a fresh home, `cache clean` exits 0, `stdout is empty`, `stderr does not contain "error:"`; run a second time after a `cache clean --all`, the same.
- A lock file with no folder: hand-made with an old modification time is not possible through the steps (no step sets a time, and rule 5 forbids the clock), so the one-hour rule is plain pytest (below); the scenario asserts only that `cache clean` leaves a fresh lock file with no folder (`the file "{runs}/x.lock" exists` afterwards).
- Nothing under `{tools}` or `{modules}` is touched by `cache clean --all`: with a build installed (29's step) and a file under `{modules}`, both are still there.
- `cache dir` prints one line, the cache folder, and creates nothing on a fresh home.
- `tlaup cache` alone exits 2 with the help on stdout and nothing on stderr (X1 rule 7).

`tests/features/errors.feature` (in-process), each asserting the code, `stdout is empty` and `stderr contains "error:" 1 times`: row 2, `cache clean <id> --all`; row 4, `cache clean nosuch`.

**`tests/unit/cmd/test_cache.py`**, plain pytest, with real folders in a temporary `AppPaths`:

- `clean_lock_files` with an injected clock: a lock file with no folder whose modification time is 59 minutes old survives, one 61 minutes old is removed; one whose lock the test holds (a lock object of the test itself, and a second Python process started by the test) survives at any age; a lock file whose folder exists is not visited.
- `cache clean RUN_ID` on a folder whose lock the test holds exits 5 and the folder stays (a scenario cannot hold a lock while tlaup runs, [01 T5](../design/01-testing.md#t5-feature-files-and-steps)): an in-process `CliRunner` call in the test.
- `cache clean` with a folder in use and another removable: exit 0, the second is gone, the first is named as in use on stderr.
- The freed total equals the sum of the removed folders' sizes and of the files removed under `remote/` and `java.json`.

- The rendering of `cache list` (if the worker splits it into a function that takes records, as Context recommends): records with fixed times and sizes against `tests/unit/cmd/expected/cache-list.txt`, which is where the size figure is checked.

No stateful test applies: `clean_runs` and the visits are already in [35](35-run-folders.md)'s state machine, and `clean_lock_files` is a loop over the same visit. The pull request names inventory row O7 as covered.

## Changelog

Under `## [Unreleased]`.

From [23 C1](../design/23-command-layout.md#c1-command-tree), word for word, under Breaking: "`tlaup fetch-cache clear` and `tlaup tlc --cleanup` are now `tlaup cache clean`; `tlaup cache list` shows the run folders, and `tlaup cache clean RUN_ID` removes one." The design gives this change one entry: V8 and R6 no longer carry Removed entries of their own for `fetch-cache clear` and `tlc --cleanup` (they point to C1). It is written here, where `cache clean` exists, although the two old names went earlier (29, 39): nothing is released in between (D6).

Added, written by stage 4 from C1's rows (they give no text for it): "`tlaup cache dir` prints the cache folder; `tlaup cache clean` removes the remembered GitHub lookups and the run folders nothing will resume, and with `--all` also kept run folders and the remembered Java check. It never removes installed tools or modules."

R6's Changed entry, which names `cache clean <run-id>` and `--all`, is 39's.

## Context for the worker

**From 35b** (noted at its merge, 2026-11-25). `CleanReport.cannot_lock` lists the folders whose lock file could not be opened in a full clean (report them; they are not "in use"), and one id that cannot be locked is a `FileOperationError` (5); `RunRecord.cannot_lock` marks such a folder in `list_runs`, whose `in_use` is then false.

**Decisions this rests on.** D49 and D53: nothing that can be resumed is removed without `--all` or its id, and a kept folder is never removed silently; `cache clean` uses the sweep's rule. D51: a held lock means a live run, or the TLC of a killed tlaup on Linux and macOS; it is never removed. D14: no `fetch-cache` alias. D29: 2 for a run id with an option, 4 for an id that names nothing, 5 for one in use. D30: the listing on stdout, notes on stderr. Review finding TU6: a run id excludes the other options.

**What the functions already do** ([35](35-run-folders.md)): `clean_runs` takes each lock with one attempt before it looks, removes a lock file with its folder (the removal is the last thing under the lock, finding K1-1), visits folders only, and raises for a run id that names nothing or is in use. `list_runs` reads each lock with one attempt to set `in_use`, takes the newest modification time of anything under a folder as its last change (research 34: the timestamped folder's own time does not move while files grow), and uses the size `run.json` recorded at the keep. Do not reimplement any of it in the command.

**Taking a lock creates its lock file** when there is none (R6, finding K1-7): a `cache list` or `cache clean` that meets a folder with no lock file leaves a new, empty one; the one-hour rule removes it later. A scenario that asserts `the cache holds no lock files` after `cache list` on a folder without one would fail for this reason; the scenarios above do not.

**Naming the kept folder.** `{kept}` expands to the kept folder's path ([18](18-feature-harness.md)); `cache clean` takes a run id, which is the folder's name, not a path (C1: `RUN_ID`). Run ids are random, and no step can read an id back from `cache list`'s output. [01 T5](../design/01-testing.md#t5-feature-files-and-steps) has the placeholder for it, `{kept-id}`, the last path part of `{kept}`, with the same failure when there is no kept folder or more than one; 18's ownership table gives it to this package, the first that needs it, so add it to 18's expansion in `tests/steps/_scenario.py`. Making `cache clean` accept a path as well was not chosen: it widens the command for the sake of a test.

**The expected file.** A `cache list` line holds the run id (random) and times (the real clock at the run). An expected file cannot hold them (T8: nothing is normalised in the helper). So `cache.feature` asserts the facts with `contains` steps, and the column layout is shown in the pull request by pasting one real `cache list` output; the plain pytest test may render a list built by hand from `RunRecord` values with fixed times against `tests/unit/cmd/expected/cache-list.txt`, if the worker splits the rendering into a function that takes records. Recommended: do that; it is what puts the layout in front of a reviewer.

**The kept folder's reason.** A run whose fake exits with 255 is kept as "TLC crashed (exit 255)" (R6: "TLC crashed (exit N)"); "interrupted" needs a signal, which is a real process, and `cache.feature` is in-process. That is why the scenario above asserts `TLC crashed`.

**State of `main` when this starts.** `tlaup tlc` is on the new runner with `--keep` and the sweep (39); `tlc --cleanup` is gone (39); `fetch-cache` is gone (29). `tlaup cache` does not exist yet, so the sweep at every run has done all the cleaning since 39. The other packages of 40 to 47 may be in flight beside this one.

## Done when

- The scenarios and unit tests above pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- `tlaup cache dir`, `cache list` and `cache clean` exist with the options of the tree and no one-letter form; `cmd/fetch_cache/` does not exist.
- The changelog entries are written, and C1's line is under `## [Unreleased]` once (no separate Removed entry for `fetch-cache clear` or `tlc --cleanup` beside it).
- The pull request pastes one real `cache list` output and one `cache clean` stderr, says how `{kept-id}` was added, and names the inventory row it owns (O7).

## Out of scope

- The run-folder protocol, `list_runs`, `clean_runs`, the sweep, the note and the reminder: [35](35-run-folders.md). `--keep`, the reminder at every run, removing `--cleanup`: [39](39-tlc-command.md).
- The lookup cache's format and `write_cache`: [25](25-remote-listing.md). The Java check and `java.json`'s format: [20](20-java-location.md).
- Deleting `cmd/fetch_cache/`, `src/tlaup/cache/` and the old lookup cache: [29](29-tool-commands.md).
- The tree test and the scenario that `fetch-cache` exits 2: [48](48-command-tree.md).
- Removing builds nobody needs, and moving tools and modules out of the cache folder: milestone 3 ([40](../design/40-later-milestones.md)).

## Risks

- From C1 and R6: kept folders can be gigabytes and stay until the user removes them; `cache list` is where they are seen, and `cache clean --all` removes every one at once. The help says what `--all` removes.
- From R6: on Windows and on network file systems a tlaup killed with SIGKILL leaves its TLC running for about two seconds with its lock free; a `cache clean` in that window acts on a live run (D51, D15).
- From the cut: `clean_lock_files` is a small addition to 35's module, which the stateful test does not exercise; its unit tests above are the guard.
- From the cut: `--runs --all` removes kept folders, which a user who reads `--runs` as "only the safe ones" may not expect; the help says what `--all` adds to each kind.
