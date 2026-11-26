# 35. Run folders and their locks

Size: L. Suggested model: most capable. Status: 35a built, 35b ready.

## Goal

`src/tlaup/tlc/rundirs.py` holds everything [11 R6](../design/11-runner.md#r6-run-folders) gives the run folders: one locked folder per run, `run.json`, settle and the completeness test, the sweep, `list_runs` and the clean functions `tlaup cache clean` will call, the resume command and the note's text. The stateful test of the RunFolders spec passes against it. No command uses it yet: `tlaup tlc` still runs through the old runner and `tlc/run_cache.py`.

## Covers

- Roadmap items ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)):
  - "Stop run-cache cleanup from deleting other specs' directories: it matches by name prefix across all projects, can delete the directory of a run in progress, and `modules add` and `modules remove` wipe every run directory ..." (roadmap line 190). In part: the run folders, their locks, the sweep and the clean functions. The switch of `tlaup tlc` onto them, `--keep`, removing `--cleanup` and the old run cache are [39](39-tlc-command.md); `cache list` and `cache clean` are [45](45-cache-commands.md); `module add` and `remove` stop touching run data in [31](31-module-commands.md) and 39.
  - "The run-cache fingerprint covers the default `.cfg` only, not a `--cfg` file or extended modules." (line 205). In part: R12 is settled by having no fingerprint here; the deletion of `compute_spec_hash`, `_cleanup_stale_spec_dirs` and `get_spec_run_dir` is 39's (their three tests went with the old suite in [03](03-test-foundation.md), decision D62).
- Design sections:
  - [11 R6](../design/11-runner.md#r6-run-folders): everything that creates, locks, settles, sweeps, lists and cleans run folders, the resume command and the note's two lines; the unit tests of R6's "Tests" marked "Unit (`rundirs`)", "Unit, the resume command" and the stateful test. Not here: the per-run values the preflight decides (`run_id`, `metadir`, `keep`, `fp`, `seed`, `suppress_te_spec`: [33](33-tlc-invocation.md)); the frame that calls `settle` and adds the note to an exception, and R6's "Unit, the frame" test ([37](37-run-tlc.md)); the checkpoint deferral ([21](21-java-launcher.md), 37); the feature scenarios ([39](39-tlc-command.md), [45](45-cache-commands.md)); the integration tests ([52](52-integration-tests.md)).
  - [11 R12](../design/11-runner.md#r12-run-cache-fingerprint): nothing to build; the deletion is 39's.
  - [22 O2](../design/22-reporters.md#o2-delete-dead-display-code): the one `format_elapsed`, which the note and [38](38-terminal-reporter.md)'s result line share.
  - [11 R9](../design/11-runner.md#r9-show-command): its one `rundirs` unit test (a folder under `runs/` with no `run.json` survives a sweep and a plain `cache clean`).
  - [23 C1](../design/23-command-layout.md#c1-command-tree), the `cache clean` and `cache list` rows: their rules for run folders, as `clean_runs` and `list_runs`. The commands are [45](45-cache-commands.md).
  - [03 K1](../design/03-run-stages-and-specs.md#k1-run-folders) and ["Specs and their tests"](../design/03-run-stages-and-specs.md#specs-and-their-tests): this package builds the code of `tests/stateful/test_run_folders.py`.
- Rows of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) this package owns: R7 (TLC gets a `-metadir` under tlaup's cache, so its state never lands in the project): `run_folder`'s unit test below shows the folder under `paths.runs` and none beside the spec; [39](39-tlc-command.md) writes the scenario through `tlaup tlc` (finding G1).

## Depends on

- [02](02-errors-and-paths.md): `FileOperationError`, `InternalError` (code 5), the `NotFound` family (code 4; `PathNotFound` if it fits a run id that names no folder); `AppPaths.runs`.
- [03](03-test-foundation.md): the isolation fixture, `hypothesis`, the `pending` marker and the CI profile.
- [21](21-java-launcher.md): `ProcessOutcome` with `stopped_for_closed_pipe: bool = False` (`settle` reads it; the stateful test builds one with four fields). Nothing is started through the launcher here.
- [23](23-tool-store.md): `format_build`, for `run.json`'s `"build"` (`"rolling@bc1b506"`); `filelock>=4.2.1` in the runtime dependencies (whichever of 23, 30 and 35 merges first adds the line; check it is there).
- [33](33-tlc-invocation.md): `TlcInvocation` and `TlcRequest`, and `RecoveredRun` with `find_recovered_run`, which this package moves into `rundirs.py` (see Interfaces). 33 lands first and stubs nothing.

Change from the draft (33, 21): 02, 03 and 23 are named. Only `run_folder` and the resume command read the invocation; the step functions, and so the stateful test, need none of 33. 33 is still a real dependency, not a type only: this package moves its function, and the resume command reads the fields 33 fills.

## Files

Creates:

- `src/tlaup/tlc/rundirs.py`.
- `src/tlaup/durations.py` with `format_elapsed` ([22 O2](../design/22-reporters.md#o2-delete-dead-display-code)): the one way tlaup writes a duration, which the note uses here and [38](38-terminal-reporter.md)'s result line imports. `tests/unit/test_durations.py`: 0.7, 4.2, 45, 60, 133, 3720 and 7980 seconds give `0.7 s`, `4.2 s`, `45 s`, `1 min 00 s`, `2 min 13 s`, `1 h 02 min` and `2 h 13 min`; 9.96 and 59.6 seconds round up into the next form (`10 s`, `1 min 00 s`), never `10.0 s` or `60 s`.
- `tests/unit/tlc/test_rundirs.py` (settle, the sweep, `clean_runs`, `list_runs`, `run_folder`, the kept summary, R9's test); `tests/unit/tlc/test_rundirs_locks.py` (`RunLock`, the visit's `FileLock`, the inherited lock); `tests/unit/tlc/test_resume_command.py` (the resume command, the note, the reminder). One file or three is the worker's choice.

Changes:

- `tests/stateful/test_run_folders.py`: first commit, remove the four `pending` markers; then delete what belonged to the throwaway model (below) and bring the docstring up to date ("runs against `tlaup.tlc.rundirs`").
- `src/tlaup/tlc/invocation.py`: `RecoveredRun` and `find_recovered_run` move out; it imports them from `tlaup.tlc.rundirs`. `tests/unit/tlc/test_invocation.py` keeps its tests of them, with the import changed if it names the module.
- `specs/README.md`, "The stateful tests": one sentence that the run-folder machine now runs against `tlaup.tlc.rundirs` and that `reference_rundirs.py` and its tests are gone.
- `pyproject.toml` and `uv.lock`: only if `filelock>=4.2.1` is not yet a runtime dependency (one line; shared with 23 and 30).

Deletes:

- `tests/stateful/reference_rundirs.py`.
- In `tests/stateful/test_run_folders.py`: `reference_impl` and the four tests `test_run_folders_machine_against_the_reference_model`, `test_a_lock_object_stands_for_a_process_reference_model`, `test_a_jvm_keeps_the_run_lock_reference_model`, `test_kept_folder_survives_a_second_resume_reference_model`.

Not touched: `src/tlaup/tlc/run_cache.py`, which the old runner still calls; [39](39-tlc-command.md) deletes it with the old runner (its test went with the old suite in [03](03-test-foundation.md), D62). `get_tlc_run_dir` in `versioning/paths.py` stays for the old code; 39 removes it.

Shared files: `src/tlaup/tlc/invocation.py` with 33 (finished before) and [34](34-override-check.md) (a different place in the file); the `filelock` line.

## Interfaces

Provides, from [11 R6](../design/11-runner.md#r6-run-folders). What stage 4 wrote from the design's words, or changed, is marked; a worker may adjust a name or a parameter if the behaviour and the tests stay, and says so in the pull request. The names the stateful test calls are fixed by it (`tests/stateful/test_run_folders.py`): `RunStart`, `RunFolder`, `RunLock`, `EntryVisit`, `list_entries`, `abandon`, `lock_fds`, `entered`, the end steps.

```python
# tlaup/tlc/rundirs.py
def list_entries(runs: Path, *, folders_only: bool = False) -> list[str]   # the run ids that have a folder or a lock file

class RunLock:                                              # tlaup's own lock on one <id>.lock (D51)
    def __init__(self, path: Path, *, wait: float): ...
    def acquire(self) -> None                               # FileOperationError after `wait`
    def duplicate(self) -> int                              # os.dup of the locked descriptor, for pass_fds
    def release(self) -> None                               # unlock, then close
    def abandon(self) -> None                               # close without unlocking

class RunStart:                                             # "Start"
    def __init__(self, runs: Path, now: Callable[[], datetime], *, run_id: str | None = None,
                 recover: Path | None = None, info: Mapping[str, object] | None = None,
                 wait: float = 5.0,
                 tlc_args: Sequence[str] = (),                      # 35a; written by stage 4, see below
                 invocation: TlcInvocation | None = None): ...   # 35b; written by stage 4, see below
    run_id: str
    path: Path
    def create_lock_file(self) -> None
    def take_lock(self) -> None                             # RunLock.acquire; FileOperationError after `wait`
    def take_recover_lock(self) -> None                     # nothing to do unless `recover` lies under an existing runs/<id>/
    def make_folder(self) -> None
    def write_run_json(self) -> None
    def sweep(self) -> KeptSummary
    def entered(self) -> RunFolder                          # hands the locks to the folder; also after a failed step
    def abandon(self) -> None                               # every lock descriptor closed, nothing unlocked: a kill

class RunFolder:
    path: Path | None                                       # None when the user passed their own -metadir
    kept_summary: KeptSummary                               # what the sweep left kept: count and bytes
    lock_fds: tuple[int, ...]                               # duplicates for the JVM (D51); empty on Windows
    resumes_exactly: bool                                   # written by stage 4, see below
    def settle(self, process: ProcessOutcome | None, *,
               workers_reported: int | None = None) -> Settled   # decides once; deletes nothing yet
    def end_own(self) -> None                               # delete the folder and remove its lock file, unless it is kept
    def release_own(self) -> None
    def end_recovered(self) -> None                         # the same for the folder -recover named
    def release_recovered(self) -> None
    def abandon(self) -> None                               # RunLock.abandon for both locks

class EntryVisit:                                           # one entry of runs/ under its lock
    def __init__(self, runs: Path, run_id: str, now: Callable[[], datetime]): ...
    def take_lock(self) -> bool                             # one attempt, no waiting; False: the entry is in use
    def sweep(self) -> None                                 # the sweep's rule for this entry
    def clean(self, *, include_kept: bool) -> bool          # `cache clean`'s rule; True if the folder went
    def release(self) -> None

@dataclass(frozen=True)
class Kept:
    path: Path                     # the run folder; after -recover, the recovered run's folder
    checkpoint_dir: Path           # TLC's timestamped folder in it, where the *.chkpt files are
    size: int                      # bytes, the whole run folder
    stopped_after: timedelta       # from this run's `started` to the end of the run
    checkpoint_at: datetime        # when the complete checkpoint was written
    reason: str                    # written by stage 4: "interrupted", "tlaup failed" or "TLC crashed (exit N)"
    resume_command: str | None     # stage 4 made it optional: None for a RunFolder built without an invocation (always in 35a)

@dataclass(frozen=True)
class Settled:
    kept: Kept | None
    dropped: Literal["not-asked", "incomplete", "depth-first"] | None

@dataclass(frozen=True)
class KeptSummary:
    count: int
    size: int

@contextmanager
def run_folder(inv: TlcInvocation, paths: AppPaths, now: Callable[[], datetime], *,
               wait: float = 5.0) -> Iterator[RunFolder]          # `wait`: written by stage 4, for the test R6 names
def sweep(paths: AppPaths, now: Callable[[], datetime]) -> KeptSummary
def list_runs(paths: AppPaths) -> list[RunRecord]                 # for `tlaup cache list`
def clean_runs(paths: AppPaths, *, include_kept: bool, run_id: str | None = None) -> CleanReport
def complete_checkpoint(folder: Path) -> Path | None              # the timestamped folder that holds one, or None (D52)
```

Written by stage 4 from what R6 and C1 say in words:

```python
def kept_note(kept: Kept) -> tuple[str, str]          # the two lines of "The note"; the frame (37) and print_run_notes (39) use it
def reminder(summary: KeptSummary) -> str             # "3 kept run folders hold 7.4 GB (tlaup cache list)"
def format_size(n: int) -> str                        # "2.1 GB"; also for `cache clean`'s "space freed" (45)

# tlaup/durations.py
def format_elapsed(seconds: float) -> str             # "0.7 s", "45 s", "2 min 13 s", "2 h 13 min"; O2's one function, which 38 imports
def resume_command(inv: TlcInvocation, checkpoint_dir: Path, *, fp: int | None, seed: int | None,
                   workers_reported: int | None, windows: bool = os.name == "nt") -> str

@dataclass(frozen=True)
class RunRecord:                   # one folder, as `tlaup cache list` shows it (23 C1); not the reporter's RunInfo
    run_id: str
    path: Path
    has_run_json: bool
    spec: str | None
    cfg: str | None
    build: str | None              # the build the checkpoint was written by
    started: datetime | None
    ended: datetime | None
    last_change: datetime          # the newest modification time of anything under the folder
    size: int                      # the recorded size of a kept folder, else measured
    in_use: bool                   # its lock is held
    kept: bool
    keep: bool
    reason: str | None             # why kept; "unsettled after a kill" for an unsettled resumable folder
    checkpoint_complete: bool

@dataclass(frozen=True)
class CleanReport:
    removed: tuple[str, ...]       # run ids
    freed: int                     # bytes
    in_use: tuple[str, ...]        # folders left because their lock was held

# moved here from tlaup/tlc/invocation.py (33), unchanged in behaviour (33 builds R6's rule as settled, Q9)
@dataclass(frozen=True)
class RecoveredRun: ...            # run_id, folder, keep, fp, seed, as 33 wrote it
def find_recovered_run(extra_args: Sequence[str], cwd: Path, runs: Path) -> RecoveredRun | None
def recovered_run_id(path: Path, runs: Path) -> str | None     # the path-level rule both use
```

Notes on the stage 4 shapes:

- **Why `find_recovered_run` moves here.** `rundirs.py` is the one module that knows the layout of `runs/` and the keys of `run.json`, which it writes; 33 reads four of them. `RunStart` is handed the `-recover` path itself (the stateful test passes `runs/<id>/states`), so the rule "is this path inside a run folder, and which" is the path-level `recovered_run_id`, which `find_recovered_run` calls after it has found the word after `-recover` and made it absolute against `cwd`. `invocation.py` imports from here; `rundirs.py` imports `TlcInvocation` only under `TYPE_CHECKING`, so there is no import cycle. 33's tests of the function stay where they are.
- **`RunStart(tlc_args=..., invocation=...)`.** The step objects take the runs folder and the fields of `run.json` so that the stateful test needs no invocation (R6, "The steps"). Two things need more than that: the `"depth-first"` reason, read from TLC's arguments, and the resume command, built from the whole request. They come in separately, so that 35a does not wait for [33](33-tlc-invocation.md) (finding C5 of the stage 4 review): `tlc_args`, TLC's own arguments as plain strings, is 35a's and is all settle needs for `-dfid`; `invocation` is added in 35b, where `run_folder` passes both (`tlc_args=inv.extra_args`), and with it settle fills `Kept.resume_command`. The stateful test passes neither, and then `Kept.resume_command` is `None` and no run counts as `-dfid`.
- **`settle(..., workers_reported=)`.** The resume command's `--workers` is "the number TLC reported in its start line (2187) when the run was parsed and TLC's arguments held no `-workers`". Only the runner has the parsed result; [37](37-run-tlc.md) passes `result.workers`. The stateful test calls `settle(outcome)` and `settle(None)`, which this keeps.
- **`resumes_exactly`.** [10 P3](../design/10-parser.md#p3-result-model) and D54: a resumed run's counts are approximate "unless it was resumed with the original `-fp` and `-seed`: tlaup knows that when `-recover` names a folder under `runs/` whose `run.json` has the values this run passed". True when this run holds the recovered folder's lock and that folder's `run.json` (read under the lock) records an `fp` and a `seed` equal to the values this run passes. 37 sets `counts_approximate = result.resumed and not folder.resumes_exactly`.
- **`Kept.reason`** and **`run.json`'s `"reason"`.** The note's first line names the reason, and `cache list` shows "why it was kept (interrupted, tlaup failed, TLC crashed, or unsettled after a kill)". R6's `run.json` has no field for it, so settle writes `"reason"` with `ended`, `kept`, `keep` and `size` when it keeps. A gap stage 4 closed. Settled with the maintainer at the stage 4 sign-off, 2026-11-24 (index, "Settled since"): the key is internal to tlaup's own folders and `cache list` shows the words, but `cache list` reads it, so a later change touches 45 too.
- **`lock_fds` gives fresh duplicates at each read**, owned by the caller, who passes them to `pass_fds` once; the launcher closes them after `Popen` ([21](21-java-launcher.md)). The stateful test reads it once and closes what it got. Read it once per run.
- **A gap between packages, settled here and in 37 by stage 4:** the outcome carries the whole `Kept` (`RunOutcome.kept`, [37](37-run-tlc.md)), and the two lines are always made by `kept_note`, so the frame's `add_note` and [39](39-tlc-command.md)'s `print_run_notes` print the same text.

**What `run_folder` reads from the invocation**, and nothing else: `run_id`; `metadir` (`None`: no folder and no lock of its own); `keep`; `fp` and `seed`; `extra_args` (the word after `-recover`, the user's own `-fp` and `-seed` when `fp` or `seed` is `None`, `-dfid`, `-workers`); `cwd` (a relative `-recover` path); `spec`, `cfg` and `build` (for `run.json`); `request` (the resume command: whether `--cfg`, `--workers`, `--coverage`, `--raw` and `--java-opt` were given). It does not read `java`, `classpath`, `config_arg`, `project_root`, `tla_library`, `override_classes`, `warnings`, `jvm_options`, `workers`, `coverage`, `tool_mode` or `suppress_te_spec`.

**Who owns each per-run value** (for reconciling with 33):

| Value | Decided by | Used here as |
| --- | --- | --- |
| `run_id`, `metadir` | 33 (`new_run_id`; `paths.runs / run_id`, or `None` with the user's `-metadir`) | the folder and lock-file names; nothing made when `metadir` is `None` |
| `keep` | 33 (request, setting, a recovered run that asked or was kept) | `run.json`'s `"keep"`; `take_recover_lock` also forces it true from the recovered `run.json` read under the lock, as the stateful test checks |
| `fp`, `seed` | 33 (random, or the recovered run's, or `None` when the user gave one) | `run.json` records the value the run uses: `inv.fp`, else the integer after the user's `-fp` (null if it does not parse); the same for `seed`. The resume command repeats `run.json`'s |
| `suppress_te_spec` | 33 | not read |
| The `-recover` path and its folder | 33 reads `run.json` before the lock (for `keep`, `fp`, `seed`); 35 takes the lock and reads it again under it | `RunStart(recover=)`, the second lock, settle in that folder |

Consumes: `ProcessOutcome` (21); `TlcInvocation`, `TlcRequest` (33); `format_build` (23); `AppPaths` and the errors (02); `filelock.lock_descriptor`, `filelock.unlock_descriptor`, `filelock.FileLock`.

Consumed by: [37](37-run-tlc.md) (`run_folder`, `RunFolder`, `Settled`, `Kept`, `kept_note`, `reminder`); [39](39-tlc-command.md) (`kept_note` in `print_run_notes`); [45](45-cache-commands.md) (`list_runs`, `clean_runs`, `RunRecord`, `CleanReport`, `format_size`); 33 (`find_recovered_run`, after the move).

## Tests that must pass

**Stateful, test first.** `tests/stateful/test_run_folders.py`. The package's first commit removes the `pending` marker from `test_run_folders_machine`, `test_a_lock_object_stands_for_a_process`, `test_a_jvm_keeps_the_run_lock` and `test_kept_folder_survives_a_second_resume`; the pull request shows that run red ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 6). All four pass at the end under `CI=1` (200 examples). The package deletes `reference_rundirs.py` and the four `*_reference_model` tests. The machine is a signed-off artefact of the formal check: a failure is a finding against the code or, if the code follows R6, a finding to report, never a test to bend.

**Unit, plain pytest** (`tests/unit/tlc/test_rundirs.py`, real files under `tmp_path`, an injected clock, ages set with `os.utime`). From R6's Tests:

- `settle` for each exit code class (0 and 10 to 14 finished; 255 and 1 not; a signal; a closed-pipe stop; `None` for tlaup failing), with and without `keep`, with a complete checkpoint, with none, and with each incomplete form (`.tmp` beside the two files; `settings.tmp.chkpt` alone; `vars.chkpt` missing), with its `dropped` reason; a `-dfid` run under `keep` with only the fingerprint files gives `"depth-first"` (TU7); a kept folder's `run.json` holds both `"kept": true` and `"keep": true` (FC1), with `ended`, `size` and `reason`; a second call returns the first answer, also when the second is `settle(None)` after a run that had finished.
- `sweep` with an injected clock, for kept, unsettled and `run.json`-less folders, with and without a held lock: a kept folder survives a sweep at 400 days; an unsettled folder that asked and has a complete checkpoint survives; an unsettled one that did not ask is removed at once; a `run.json`-less folder survives at 29 days counted from its newest file and is removed at 31; a lock file with no folder survives at 59 minutes and is removed at 61; a `run.json` that cannot be read counts as none (the 30-day rule), so a damaged kept folder is not removed.
- `clean_runs` without `include_kept` leaves the resumable unsettled folder, the kept one and the `run.json`-less one, and removes them with `include_kept` or with their id; an unknown id raises the `NotFound` family (4); an id whose lock is held raises `FileOperationError` (5) saying it is in use; `CleanReport` lists what went and the bytes freed.
- `sweep` and `clean_runs` leave a folder whose lock is held, once by a lock object of the test itself and once by a second Python process started by the test.
- R7 (inventory row): `run_folder` for an invocation whose spec is in a project folder under `tmp_path` makes its folder under `paths.runs`, and nothing is created in the project folder or beside the spec.
- `run_folder` with `-recover` into a folder whose lock the test holds raises `FileOperationError` after the wait (`wait` set short) and leaves its own folder and lock file removed; the same with `-recover <that folder>/states` where `states/` does not exist (Q9); `-recover <runs>/<an id with no folder>/states` takes no second lock; with `-metadir` among TLC's arguments it makes no folder and no lock file under `runs/`, and with `-recover` into a managed folder as well it still takes and holds that folder's lock.
- The kept summary counts the recorded `size` of two kept folders, and measures one that has none.
- `list_runs`: one record per folder, with `in_use` true for a held lock, `reason` "unsettled after a kill" for an unsettled resumable folder, and a `run.json`-less folder listed with its id, size and last change.
- R9: a folder under `runs/` with no `run.json` survives a sweep and a plain `clean_runs`.

**Unit, the lock rules** (`tests/unit/tlc/test_rundirs_locks.py`; formal check and D51):

- A `RunLock` waits for a lock whose holder then removes the lock file and releases; the waiter ends up holding a lock on the file that exists at the path, and a third attempt is refused (the second look, finding K1-2). This is the one test of the second look: the stateful machine takes a lock in one call and cannot reach it (03).
- After a release the lock file still exists; taking or releasing a lock leaves its modification time alone.
- The `foreign_file` case: a holder removes its lock file, a second object takes the lock of a new file under the name, the first releases; the file at the name still exists and the second still holds it (a helper that unlinks the name on release fails this).
- The same three for the `FileLock` of a visit, so that a `filelock` outside the bound fails on the newest-dependencies job.
- On Windows the second look's test asserts that the removal under the lock fails and the property still holds, or is skipped with that reason.
- The inherited lock, Linux and macOS: a child process started with `RunLock.duplicate()` in `pass_fds` keeps the lock after its parent is killed with SIGKILL (the parent is a Python process the test starts, which takes the lock and starts the child), so a third attempt is refused, and loses it when the child ends; a `RunLock.release` in the parent while the child lives frees it. A `RunLock` or `filelock` that switched to per-process locks fails it.
- `take_lock` does not turn `filelock`'s `RuntimeError("Deadlock ...")` into "busy"; nothing here waits without a timeout, so it is reported as an internal error. (Stage 4 adds no test for an error nothing can produce; the rule is checked in review.)

**Unit, the resume command and the note** (`tests/unit/tlc/test_resume_command.py`, hand-built `TlcInvocation` and `Kept` values): a relative spec and `--cfg` come out absolute; `--keep` is there; `--raw`, `--coverage`, `--workers 4` and two `--java-opt` are carried, and a `workers` from the settings is not, unless the start line reported a count; an existing `-recover X`, `-fp` or `-seed` among TLC's arguments is replaced, not doubled; the result parses back with `shlex.split` to the expected list; with `windows=True` the join is `subprocess.list2cmdline`'s. Added by stage 4: `kept_note` gives the two lines of "The note" for each of the three reasons, `reminder` gives the singular and the plural form, `format_size` the units.

Old tests: none; the old suite went in [03](03-test-foundation.md) (D62), `tests/unit/tlc/test_run_cache.py` with it.

## Changelog

None in this package: no command reaches the code. [39](39-tlc-command.md) writes R6's entries (Fixed, the two Changed, the two Added, Removed) word for word when `tlaup tlc` moves onto it; [45](45-cache-commands.md) writes the `cache` entries.

## Context for the worker

Read [11 R6](../design/11-runner.md#r6-run-folders) whole, Facts to Risks, then [the RunFolders part of the specs' README](../../specs/README.md#runfolders) with its findings, then `tests/stateful/test_run_folders.py` and `reference_rundirs.py` before you delete it. The throwaway model is about 370 lines and is the smallest working form of the step functions; it is not the design: it has no `run_folder`, no resume command, no sizes or times, no Windows order of removal and a 10 ms poll where R6 says 50.

### The decisions, with the reason for each

- **D36.** `-noGenerateSpecTE` on builds that have it (33 decides it); its second half, keeping every unfinished run with a checkpoint, is replaced by D53.
- **D46.** The protocol is split into one call per step of the spec, so the stateful test can interleave several "tlaups" in one process.
- **D48 (replaced by D53).** A trial run stopped and tried again leaves nothing; now the default, with no flag.
- **D49 (narrowed by D53).** `cache clean` without `--all` uses the sweep's rule: nothing resumable is removed without `--all` or its id. Finding K1-4: otherwise the sweep and `cache clean` disagreed about a killed run's checkpoint.
- **D51.** The run's own lock and the recovered folder's are tlaup's own descriptor (`os.open` plus `filelock.lock_descriptor`), duplicated into the JVM on Linux and macOS: only a descriptor tlaup owns can be handed to a child and later closed without unlocking, so "the lock is free" means "no TLC runs here". The visits keep `FileLock`, since they never hand a lock to a child.
- **D52.** A checkpoint is kept only when complete (`queue.chkpt` and `vars.chkpt`, no `.tmp`, no `settings.tmp.chkpt`): a checkpoint stopped half way can recover with exit 0 and miss states. `-fp` and `-seed` are recorded and repeated, so a resume is exact and rolling does not warn (2285).
- **D53.** Keeping is asked for at the start; otherwise a run deletes its folder however it ended, and a killed run's folder goes at the next sweep. Kept folders are shown and never removed silently. TLC checkpoints every 30 minutes by itself; keeping by default would have kept gigabytes after every long run.
- **D54.** A resumed run's counts are approximate unless resumed with the original `-fp` and `-seed`; `resumes_exactly` is how 37 knows.
- **D58.** A run stopped because its reader went away is settled as an interrupted run (R1).
- **D59.** `filelock>=4.2.1`: 3.20.4 to 3.29.4 unlink the lock file by name on release (breaks exclusion, spec variant `unlink-on-release`), 3.29.5 to 4.2.0 change its modification time on locking (breaks the one-hour rule).
- **D14.** Nothing reads the old `run/tlc/<stem>_<hash>` folders; they are not migrated.
- **D15.** Below.

### Rules a worker could miss

- **Lock order at the start**: create the lock file, take its lock (wait up to five seconds), take the recovered folder's lock the same way, make the folder, write `run.json`, sweep. The lock file sits beside the folder, so there is no moment when an unlocked new folder exists. `create_lock_file` makes `runs/` if it is missing.
- **`RunLock`**: `os.open` read and write, create, never truncate (so the file's time is set only when it is created); one non-blocking attempt every 50 ms until `wait` is over, then `FileOperationError`; `wait=0` makes one attempt. After locking, the second look: compare `os.fstat` of the descriptor with `os.stat` of the path (device and inode); if the path is missing or names another file, unlock, close, start over.
- **A visit** uses `filelock.FileLock(..., timeout=0)` and holds it only while it looks. Taking an entry's lock creates its lock file when there is none (K1-7); the one-hour rule removes such a file later. A lock is taken and released in one thread (`FileLock` objects are thread-local).
- **The end**: a kept folder is left and its lock released; any other folder is deleted, the lock file removed while the lock is still held, then the lock released. Removing the lock file is the last thing done under the lock (finding K1-1). If deleting the folder fails, the lock file is removed all the same; a later sweep finds the folder with a free lock. Own folder first, then the recovered one: the order of the stateful test's end rules.
- **Release only after the child is gone.** A release in tlaup unlocks the JVM's copy too (one open file description). The launcher's `finally` guarantees the child is gone on every way out, so the end steps release; `abandon` (close without unlocking, leave the lock file, let the system release when the JVM ends) is for the stateful test and for a way out that cannot confirm the child is gone. 37 does not call it.
- **Settle decides once.** "Finished" means a `ProcessOutcome` with `stopped_by` `None`, no closed-pipe stop and a tool exit code of 0 or 10 to 14 (research 15). Kept when not finished, the run is a kept run (asked, or resumes a folder that says keep or kept, FC1) and the folder holds a complete checkpoint. When a checkpoint was there and was not kept: `"not-asked"` when the run did not ask (the stateful test expects this for any `*.chkpt` or `*.tmp`, complete or not; R6's gloss says "complete"), `"depth-first"` when it asked and TLC's arguments hold `-dfid`, `"incomplete"` otherwise. After `-recover` into a managed folder the checkpoint is looked for there; the new run's own folder holds none and is deleted.
- **Keeping writes** `ended`, `"kept": true`, `"keep": true`, `size` and `reason` into the kept folder's `run.json` (a resumed folder gets a fresh `ended` and `size`).
- **The sweep's rules** (D53): a kept folder is never removed; an unsettled folder with a `run.json` is removed at once unless it says `keep` and holds a complete checkpoint (D49); a folder with no `run.json`, or one that cannot be read, is removed 30 days after its newest change (the newest modification time of anything under it, not the timestamped folder's own time, research 34); a lock file whose folder is gone is removed only when it is more than an hour old, and only while the sweep holds its lock. An entry whose lock is held is never touched, the process's own locks included (a second lock object on the same file in one process is refused). Errors while deleting are ignored; the next sweep tries again.
- **`clean_runs`** visits folders only (`list_entries(..., folders_only=True)`, as the stateful test does) and removes a lock file with its folder; lock files without a folder are the sweep's. Default: what the sweep would remove and is not resumable; never a kept folder, an unsettled resumable one, or one without `run.json`. `include_kept`: those too. A run id: that one folder whatever it is, when its lock is free.
- **`-recover PATH`** (question Q9, settled with the maintainer as R6 now says): relative to `cwd`, links resolved as far as the path exists, then under an existing `runs/<id>/` or not, whether or not `PATH` itself exists. The stateful test asks for exactly this: it passes `runs/<id>/states` for any existing folder, often one with no `states/`, and expects the lock taken whenever `runs/<id>/` exists (`take_recover_lock`). Taking the lock for a missing checkpoint folder costs nothing and protects the folder while TLC reports the error. Under one: that folder's lock is taken after the run's own and before the sweep, held to the end, and a lock that is not free after the wait is `FileOperationError`, "the run folder <path> is in use by another tlaup run" (rule 2: two TLCs writing one checkpoint would destroy it). Outside `runs/`, or under a `runs/<id>/` that has no folder: TLC's to judge; no second lock, no note.
- **The user's `-metadir`**: no folder and no lock of its own, nothing cleaned in the user's folder, `RunFolder.path` is `None`; the `-recover` rules still apply when `PATH` lies under an existing `runs/<id>/`. The sweep of `<cache>/runs/` still runs (stage 4's choice, low impact, which follows R6's words): it touches nothing of the user's, and the reminder line comes from it.
- **A failed start step.** `run_folder` hands what it holds to `entered()` and runs the end steps, so a lock that was taken is released and a folder that was made is deleted, then lets the error go on. When the run's own lock could not be taken, its new lock file is left: removing it without the lock is unsafe, and the one-hour rule removes it. A folder that cannot be created and a `run.json` that cannot be written are `FileOperationError` (5) with the path (R1's table).
- **`run.json`**: `{"schema": 1, "spec", "cfg", "build", "pid", "started", "tlaup", "keep", "fp", "seed", "ended": null, "kept": false, "size": null}`; `started` in UTC, `2026-11-15T10:00:00Z`; `tlaup` the version string `tlaup --version` prints. `run_folder` passes these through `info`; `RunStart` writes them with `schema`, `started`, `ended`, `kept` and `size`. The stateful test passes only `{"keep": ...}`.
- **The run id** has no `:`, so it is a valid folder name on Windows.
- **The resume command**: `tlaup tlc <absolute spec>`, `--cfg <absolute cfg>` only when `--cfg` was given, `--keep`, then in this order `--workers` (TLC's reported count when the run was parsed and TLC's arguments held no `-workers`; else as given on the command line; never when it came from the settings), `--coverage`, `--raw`, each `--java-opt=VALUE`; then `--`, TLC's arguments with every `-recover`, `-fp` and `-seed` and the word after each removed, then `-fp` and `-seed` from `run.json`, then `-recover` and `Kept.checkpoint_dir`. `--auto-install` is left out. Joined with `shlex.join`, `subprocess.list2cmdline` on Windows. It does not carry the environment or the starting folder; the build is whatever is pinned when it is run.
- **The note**, from `kept_note`: `Checkpoint kept (2.1 GB, interrupted after 2 h 13 min, checkpoint of 14:02): <the run folder>` and `Resume with: <command>`. What R6 shows only by example is built so (stage 4's choices): sizes in decimal units with one decimal (`kB`, `MB`, `GB`); durations by `format_elapsed`, the result line's form (settled with the maintainer at the stage 4 sign-off, 2026-11-24): below ten seconds with one decimal (`0.7 s`, `4.2 s`), below a minute in whole seconds (`45 s`), below an hour as minutes and two-digit seconds (`1 min 00 s`, `2 min 13 s`), and from an hour on as hours and two-digit minutes (`1 h 02 min`, `2 h 13 min`); the reason as `interrupted`, `tlaup failed` or `TLC crashed (exit 255)`, each followed by `after <duration>`; the checkpoint's time as `HH:MM` in the local zone, with the date before it when it is not the day the run ended. `checkpoint_at` is the newer modification time of `queue.chkpt` and `vars.chkpt`. `stopped_after` runs from this run's own start to settle. A unit test must not depend on the machine's zone: pass a zone in, or set `TZ` with `monkeypatch` and call `time.tzset`.
- **The reminder**: `1 kept run folder holds 2.1 GB (tlaup cache list)`, `3 kept run folders hold 7.4 GB (tlaup cache list)`. The summary counts the kept folders the sweep visited (a kept folder whose lock is held at that moment, because it is being resumed, is not counted), with `run.json`'s `size`, measuring one that has none.

### Guessed waits and ages, as the design names them

- **Five seconds** for a run's lock: R6 calls it "a guess at longer than any sweep holds one, and than a killed tlaup's JVM takes to end" (the lifeline ends a JVM within about two seconds; 0.1 to 1.6 s measured).
- **50 ms** between attempts: R6's figure, not measured.
- **One hour** for a lock file with no folder: it protects the instant between a start's creating its lock file and locking it. With the second look the formal check found the gap closed without the rule (`no-hour-rule` holds); the rule keeps lock files from being removed under a starting run and cleans K1-7's leftovers.
- **30 days** for a folder with no `run.json` (a command pasted from `--show-command`): its age is its only guard; a pasted simulation silent for 30 days is not protected, and R9's help says to give a long pasted run a `-metadir` of the user's own.

### What the formal check changed in R6

K1-1: removing the lock file is the last step under the lock. K1-2: the second look is part of the protocol (and `filelock>=4.2.1`). K1-3: a `-recover` into a killed tlaup's folder could start a second TLC; closed on Linux and macOS by the inherited lock (D51). K1-4: `cache clean` spares a resumable checkpoint (D49). K1-5: the sweep's age rule for unsettled folders; gone with D51 and D53 (a free lock means no TLC). K1-6 and K1-9 (review FC1): a kept folder survives a second resume, because settle writes `"keep": true` with `"kept": true`. K1-7: a visit leaves an empty lock file behind. K1-8: the Windows window below. Also: "two sweeps never in one folder at once" holds because each holds the entry's lock, not for the reason first given.

### Windows (D15) and what is not tested there

Nothing here runs on Windows in CI. Write it so it should work: no `pass_fds` there, so `lock_fds` is empty and the lock does not follow the JVM; an open file cannot be deleted, so the removal of a lock file under its lock fails and is ignored, and `RunLock.release` removes the lock file after it has unlocked and closed it (the order `filelock` uses there; another holder keeps its own handle open without delete sharing, so no other holder's file is removed, research 30); deletion errors are ignored and the next sweep retries; paths with `pathlib`, the resume command with `list2cmdline`. Whether `filelock.lock_descriptor` behaves on Windows as on Linux was not tried. Not tested on Windows: everything; the stateful test is skipped there (`LockFollowsTLC = TRUE` is Linux and macOS), and the Windows forms of the spec, the window of about two seconds after a kill and finding K1-8, have no test.

### Known gaps the design accepts; do not close them

- **K1-8, a SIGKILL on Windows** (and on network file systems where `flock` is per process): for about two seconds after tlaup is killed its TLC runs with the lock free, so a sweep, a `cache clean` or a `-recover` can act on a live run; a resume started in that window that stops before its own TLC starts can delete a checkpoint the orphan commits afterwards. Accepted (D51, D15).
- On Linux and macOS a lock stays held for up to two seconds after its tlaup is killed; the five-second wait covers it.
- The completeness test rests on research 35's breakpoints (every broken case left a `.tmp`); liveness checking adds a file to the commit and was not run. Whether TLC writes its checkpoint files directly in the timestamped folder was read from two builds' listings only.
- That the original `-fp` and `-seed` make a resumed run's counts exact rests on one run (rolling, one worker); [52](52-integration-tests.md) checks both builds and two workers.
- The per-run `java.io.tmpdir` for v1.7.4 is postponed ([13 J1](../design/13-modules-and-java.md#j1-java-options)).

### State of `main` when this starts

`tlaup tlc` runs through `tlc/runner.py`, which calls `tlc/run_cache.py` (one folder per spec under `<cache>/run/tlc/`); `module add` and `remove` (or their replacements from 31) may still call `clear_tlc_run_cache`. None of that is touched. Beside it exist `tlaup/errors.py`, `tlaup/paths.py` (`AppPaths.runs` names the new `<cache>/runs/`, read by nobody yet), `java/launcher.py`, `versioning/store.py` with `format_build`, `tlc/invocation.py` and `tlc/command.py`. Nothing imports `rundirs.py` when this package merges, except `invocation.py` for the moved function.

## Done when

- The four stateful tests pass without `pending` under `CI=1`; the pull request shows them red after the first commit; `reference_rundirs.py` and the four reference tests are gone and the docstring says what the machine runs against.
- The unit tests above pass on Linux and on the macOS job; `uv run poe lint` (mypy strict on `rundirs.py`) and `uv run poe test` pass; CI is green.
- No test waits for an amount of time ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 5): ages come from the injected clock and `os.utime`, waits are for a condition with a timeout, and `wait` is a parameter.
- `specs/README.md` has its sentence; 33's tests of `find_recovered_run` pass from the new place.
- The pull request lists every signature that differs from this file and each choice under Context it did not follow, says what was run on which system, and names the inventory row it owns (R7).
- No changelog entry (none is due).

## Out of scope

- `run_id`, `metadir`, `keep`, `fp`, `seed`, `suppress_te_spec` and reading a recovered `run.json` before the lock: [33](33-tlc-invocation.md).
- The frame (`signals_held` round `run_folder`, settle on every way out, the note on an exception, the reminder printed before `reporter.start`), `RunOutcome`, `counts_approximate` and R6's "Unit, the frame" test: [37](37-run-tlc.md).
- The checkpoint deferral and its waiting line: [21](21-java-launcher.md) (`on_held`), 37 (the line, handed to `Reporter.notice`), the reporters ([36](36-reporter-interface.md), [38](38-terminal-reporter.md), [40](40-live-display.md)).
- `print_run_notes`, `--keep`, the R6 scenarios of `tlc_run.feature` and `tlc_signals.feature`, removing `--cleanup`, `run_cache.py` and its test: [39](39-tlc-command.md).
- `tlaup cache dir`, `list`, `clean` and `cache.feature`: [45](45-cache-commands.md).
- The integration tests: a real violation leaves nothing in `<cache>/runs` and no `_TTrace_` file; a real interrupted `-checkpoint 1` run under `--keep` resumed to the same distinct-state count on both builds with `-workers 2`; tlaup killed with SIGKILL leaves no `java` after five seconds and, on Linux and macOS, a second tlaup's `cache clean <run-id>` is refused until the JVM has gone: [52](52-integration-tests.md).

## Risks

From R6:

- On Windows and network file systems the two seconds after a kill (above, K1-8).
- The completeness test rests on research 35's breakpoints; the deferral of 21 and 37 makes a stop in the middle rarer only in parsed runs.
- A user who forgot `--keep` loses the checkpoint of a long run; the result line says so.
- Kept folders can be gigabytes and stay until the user removes them; the note, `cache list` and the reminder make them visible.
- `RunLock` is tlaup's own code: its wait and second look are tested only by this package's unit tests. The visits rest on `filelock>=4.2.1`.
- The five-second wait is a guess. The resume command does not carry the environment or the starting folder.

From the cut:

- The package is large for one review: the whole protocol, three unit test files and the stateful test. It is not split here; the report to the index proposes a split (the step functions and their lock tests with the stateful test first; `run_folder`, the resume command, the note, `list_runs` and `clean_runs` second).
- Five shapes are stage 4's (`invocation`, `workers_reported`, `resumes_exactly`, `Kept.reason` and its `run.json` key, `Kept.resume_command` optional), and `RunRecord`, `CleanReport`, `kept_note`, `reminder`, `format_size` have no written signature in the design. 37, 39 and 45 are cut against them; a change here must reach those packages.
- The stateful test fixes the step functions' names and arguments; if one needs another argument the test changes with it, which the specs' README allows a worker to find.

## Pull requests (decided by stage 4)

This package is delivered as two pull requests; the index lists them as 35a and 35b. The stateful machine needs every step at once, so its markers come off in 35a and nowhere else.

- **35a**: every step function the stateful test calls (`RunLock`, `RunStart` with `tlc_args`, `RunFolder` with `settle`, the visits with sweep and clean, `list_entries`, the completeness test, the module-level `sweep`), `Kept` with every field but `resume_command` (always `None` here: path, checkpoint folder, size, both times and reason, which settle writes into `run.json`), `Settled`, `KeptSummary`, the lock, settle and sweep unit tests (the `-dfid` case through `tlc_args`), and the stateful test with all four markers removed and the throwaway model deleted. Nothing in 35a names `TlcInvocation`, so mypy needs nothing of 33. Depends on 02, 03, 21, 23.
- **35b**: `RunStart(invocation=...)` and with it `Kept.resume_command`, `run_folder(inv, ...)`, the full `run.json`, `resume_command`, `kept_note`, `reminder`, `format_size`, `durations.py` with `format_elapsed` and its test, `list_runs` and `RunRecord`, `clean_runs` and `CleanReport`, the `-recover` tests of `run_folder`, and the move of `find_recovered_run` from 33. Depends on 35a and 33.

A package that names 35 as a dependency waits for 35b.
