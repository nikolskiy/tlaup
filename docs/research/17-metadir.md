# 17: What TLC writes under `-metadir`

## Question

What does TLC write under `-metadir` on each run, can two runs share one folder, and what is safe to delete while a
run is in progress? Also: where does TLC write without `-metadir`, what do `-recover`, `-cleanup` and `-dumpTrace` do,
how is the timestamped folder name built, and what does `src/tlaup/tlc/run_cache.py` assume?

## Source

- Jars downloaded with `gh release download` on 2026-11-14 from github.com/tlaplus/tlaplus:
  - v1.7.4 (published 2024-08-05): `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`, sha256 `936a2620...`.
  - `rolling` (published 2026-10-23) and `v1.8.0` (pre-release, 2026-11-15 00:29 UTC) are byte-identical, sha256
    `7e53aa63...`: `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`. Below "1.8.0" means this jar.
- Java: OpenJDK 25.0.5, Linux x86-64, tmpfs scratch folder.
- Upstream source, pinned (full SHAs: 5a47802b5c391f59ecdd44117981f4ff8c0656ba and bc1b506bdcad80bb518bf3776a9161c34ff0fc4c):
  - `FileUtil.makeMetaDir`: [v1.7.4](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/util/FileUtil.java#L229),
    [1.8.0](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/util/FileUtil.java#L268)
    (`createExclusiveDirectoryWithApproximateName` just below it).
  - `TLCGlobals.metaRoot = "states"`: [1.8.0 line 269](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L269)
    ([v1.7.4 line 167](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L167)).
  - `TLC.java` option parsing and `-cleanup`/`makeMetaDir` call: [1.8.0 lines 1256-1283](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1256-L1283)
    ([v1.7.4 lines 949-958](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L949-L958)).
  - `ModelChecker.cleanup(boolean)`: [1.8.0 line 867](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L867)
    ([v1.7.4 line 804](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L804)).
- Experiments: scripts and trees in `tests/fixtures/research/17-metadir/` (`trees.txt` has every tree quoted below;
  `specs/` the specs; `pair.py`, `sigrun.py`, `run_bg.sh` the drivers).
- tlaup code: `src/tlaup/tlc/run_cache.py`, `src/tlaup/tlc/runner.py` lines 144-156, `src/tlaup/cmd/tlc.py` line 100,
  `src/tlaup/cmd/modules/add.py` line 139, `src/tlaup/cmd/modules/remove.py` line 18.

## Short answer

- With `-metadir X`, every TLC run creates one new subfolder `X/<yy-MM-dd-HH-mm-ss[.SSS]>` and puts all its files in
  it. The folder name is the TLC start time in the JVM's local time zone. Millisecond digits are default in 1.8.0
  and absent by default in 1.7.4 (`-Dutil.FileUtil.milliseconds=true` turns them on in 1.7.4).
- Inside the folder: fingerprint files `<Spec>_<n>.fp`, per-worker trace files `<Spec>-<n>.st`, `<Spec>.st`, and
  numbered queue spill files (plain integers, about 200 KB each). With `-checkpoint` also `queue.chkpt`,
  `vars.chkpt`, `<Spec>-<n>.chkpt`, `<Spec>.st.chkpt`, and in 1.8.0 `settings.chkpt`. No `MC*.out`, no `nodes_*`.
- After a normal finish TLC deletes its timestamped folder (both versions, with and without `-checkpoint`);
  `X` stays and is empty.
- After an invariant violation: 1.7.4 also deletes the folder (all 4 test cases, no `-checkpoint`); 1.8.0 leaves it,
  with `.st`/`.fp` files and queue pool files (seen: 5 files for a 6-state spec, 67 files and about 29 MB for a
  2.8M-state spec). With `-checkpoint` and a non-empty queue at the violation both versions keep the folder on purpose
  (checkpoint then veto cleanup).
- After SIGTERM (exit 143) or SIGINT (exit 130), or a crash: the folder stays, nothing is cleaned up, both versions.
  The same holds for a disk-full crash.
- Two concurrent runs with the same `-metadir`: 1.7.4 fails the later one (exit 1, a Java exception with the text
  "that directory already exists"), 15 of 15 pairs started together. 1.8.0 survives: if the millisecond name is taken
  it creates `<name><random digits>` instead (0 failures in 20 pairs; the fallback path was shown with
  `-Dutil.FileUtil.milliseconds=false`).
- Deleting while running is not uniformly safe. If TLC is quiet (no queue spill files being created, no checkpoint
  due) it continues and finishes with exit 0 and does not recreate the folder. If it is busy it crashes with
  `FileNotFoundException` (exit 1). A checkpoint always crashes it after the folder is gone. See Evidence.
- Without `-metadir`: `<spec dir>/states/<timestamp>` if the spec path is absolute, `<cwd>/states/<timestamp>` if
  it is relative. TLC's own `-cleanup` deletes only `./states` in the cwd, never the `-metadir`, never the spec
  folder's `states`.
- `-recover <path of the timestamped folder>` works in both versions; it reuses that same folder and deletes it on
  success. `-dumpTrace` exists in 1.8.0 only; it writes where its argument says (relative to the cwd), not in the
  metadir.
- tlaup's cache folder `~/.cache/tlaup/run/tlc/<stem>_<hash>` is the `-metadir`. Its cleanup matches the prefix
  `<stem>_`, so running `Foo` deletes the run folder of `Foo_bar` (reproduced, below). The hash covers the spec
  path, the spec file and the default `<stem>.cfg` only.

## Confidence

Verified for everything measured on the two jars named above, on Linux with Java 25. Partly verified:
the 1.7.4 versus 1.8.0 difference after a violation (observed, but the source of `cleanup` is identical in both, so
I could not explain it from the source). Not tested: Windows and macOS, `-fpmem`/`-gzip` variants, `-simulate`, `-dfid`,
liveness (`.fp` graph files), distributed TLC, `-coverage`, a custom Java override module run.

## Evidence

### Folder name (source)

`FileUtil.makeMetaDir(Date, specDir, fromChkpt)`, 1.8.0:

- `fromChkpt != null` (that is `-recover`): returns that path unchanged, creates nothing.
- Otherwise the parent is `TLCGlobals.metaDir` if `-metadir` was given, else `Paths.get(specDir).resolve("states")`.
  `-metadir` text is parsed as `args[i] + File.separator`.
- Name: `new SimpleDateFormat("yy-MM-dd-HH-mm-ss.SSS").format(date)`, where `date = new Date(startTime)`. The
  property `util.FileUtil.milliseconds` defaults to `"true"` in 1.8.0 (comment: MAK 07/2021, because scripts that run
  TLC in a loop collided) and to false in 1.7.4 (`Boolean.getBoolean`, so `...HH-mm-ss` unless set).
- Creation is atomic (`Files.createDirectory`). On `FileAlreadyExistsException` 1.8.0 calls
  `Files.createTempDirectory(parent, name)`, which appends a random decimal number to the name. 1.7.4 does
  `Assert.check(!filedir.exists(), EC.SYSTEM_METADIR_EXISTS)` then `mkdirs`: a check-then-create, so it fails
  rather than recovers (and a true same-instant race could even pass the check twice; not observed).
- The time zone is the JVM default. In these runs it printed local time (HST); the same spec run in two zones would
  name its folders differently. tlaup should not parse the names.

Observed names: `26-11-14-22-24-19.862` (1.8.0), `26-11-14-22-27-11` (1.7.4). Fallback in 1.8.0 (two runs,
milliseconds off, same second): `26-11-14-22-39-37` and `26-11-14-22-39-3716107081365761733521`.

### What is in the folder

Commands: `java -cp <jar> tlc2.TLC -workers N -metadir X [-checkpoint 1] Spec.tla` from a private cwd.
Full lists are in `tests/fixtures/research/17-metadir/trees.txt`. During a run (`Slow`, 1 worker, running):

| File | Meaning | Seen when |
|---|---|---|
| `<Spec>_0.fp`, `<Spec>_1.fp` | fingerprint set files (0 bytes in all small runs and at checkpoint time) | always |
| `<Spec>-<w>.st` | per-worker trace file, grows with states (130 MB for 2M states in the first test) | always |
| `<Spec>.st` | trace file (0 bytes) | always |
| plain integers (`6400`, `200`) | disk-queue pool files, 212,992 bytes each; 59 to 183 of them on a multi-million-state spec | busy runs |
| `queue.chkpt`, `vars.chkpt`, `<Spec>-<w>.chkpt`, `<Spec>.st.chkpt` | checkpoint | `-checkpoint N` after the first interval |
| `settings.chkpt` (88 bytes) | checkpoint settings, new in 1.8.0 | `-checkpoint`, 1.8.0 only |
| `queue.tmp`, `<Spec>-4223.st` | transient, seen while checkpointing | v1.7.4 mid-checkpoint |

Not seen: `MC*.out`, `nodes_*`, `*.dump`. Those belong to the Toolbox or to `-dump`.

Side files outside the metadir:

- On an error trace 1.8.0 writes `<Spec>_TTrace_<epoch>.tla` and `.bin` next to the spec (default
  `-teSpecOutDir`: the spec folder) unless `-noGenerateSpecTE`. 1.7.4 does not, unless `-generateSpecTE` is given
  (and has no `-noGenerateSpecTE` option: it exits with "unrecognized option"). These are never cleaned up by TLC.
  tlaup does not pass `-noGenerateSpecTE` (grep of `src/` for `TTrace|generateSpecTE`: no hits).
- TLC copies standard modules to `java.io.tmpdir/tlc-<digits>/` (`deleteOnExit`); `/tmp` held 523 such
  folders when I looked, which suggests runs that were killed or crashed leave them (mine and other agents'; not attributed or tested).

### After the run ends

| Case | v1.7.4 | 1.8.0 |
|---|---|---|
| Normal finish (Small, Mid, Slow; with and without `-checkpoint`) | folder deleted, `X` empty | folder deleted, `X` empty |
| Invariant violation, tiny spec (Viol), exit 12 | folder deleted | folder kept: 5 files, 0 bytes |
| Invariant violation, 2.8M states (MidViol), exit 12 | folder deleted | folder kept: 67 files, `.st` 14 MB each + 62 pool files |
| Violation with `-checkpoint 1`, queue not empty | folder kept, 13 files incl. `queue.chkpt` 260,670 bytes | kept, 14 files |
| SIGTERM at 20 s, exit 143 | folder kept (4 empty files) | folder kept |
| SIGINT at 20 s, exit 130 | folder kept | folder kept |
| SIGTERM at 70 s with `-checkpoint 1` | folder kept with `.chkpt` files | same + `settings.chkpt` |
| Disk full (`No space left on device`) | `TLC threw an unexpected exception`, folder kept | `Error: when writing the disk`, folder kept |

Source for the rule: `ModelChecker.cleanup(success)` ends with `FileUtil.deleteDir(metadir, success)`. `deleteDir(f, true)` removes
recursively; `deleteDir(f, false)` is a plain `File.delete()` on the directory, which fails if it is not empty. A
violation passes `success=false`, so the folder survives unless it is empty. `ModelChecker.VETO_CLEANUP`
(`-Dtlc2.tool.ModelChecker.vetoCleanup=true`) skips deletion; with it 1.7.4 also keeps the folder after a
violation (5 files), which confirms the deleting call is the `cleanup` one. Why 1.7.4 leaves nothing after a
violation although the code is the same: not found. (Both `ModelChecker.cleanup` and `doDeleteDir` are identical in
the two commits; a guess is that 1.7.4 reports the violation with `success == true` or removes the files first.)

A caveat on SIGINT: a bash background job starts with SIGINT ignored, and the JVM then never installs its handler;
my first SIGINT test did nothing for that reason. The valid result above used `sigrun.py` (Python restores the
default handler first). tlaup runs TLC with `subprocess.Popen` from Python in the foreground, so Ctrl-C reaches it.

### Two runs in one `-metadir`

`pair.py` starts two TLC processes back to back, same spec, same `-metadir`, 15 (1.7.4) or 20 (1.8.0) times:

- 1.7.4: `{(0, 1): 8, (1, 0): 7}`: in every pair exactly one run failed with exit 1:
  `Exception in thread "main" util.Assert$TLCRuntimeException: TLC writes its files to a directory whose name is generated from the current time. This directory should be .../26-11-14-22-39-40, but that directory already exists. Trying to run TLC again will probably fix this problem.`
  The second-resolution name makes this nearly certain for any two starts within one second (`tlaup tlc` run twice in a script, or a watch loop).
- 1.8.0: `{(0, 0): 20}`: no failures. Whether any pair actually hit the same millisecond is unknown; the
  fallback was triggered on purpose with milliseconds off (two timestamped folders, the second with random digits
  appended). The two runs then have separate folders and do not touch each other's files.
- Different specs with one `-metadir` also get separate folders; nothing else is shared at the top of `X`.

### Deleting while a run is in progress

`Slow` is 1 worker, 4001 states, one expensive step each, about 2 minutes. `rm -rf X/<timestamp>` (and, separately,
`rm -rf X`) 20 s after start:

| Case | Result |
|---|---|
| No `-checkpoint`, folder deleted, v1.7.4 and 1.8.0 | TLC finished, exit 0, 4001 states, no error, folder not recreated (`X` empty) |
| No `-checkpoint`, whole `X` deleted, both versions | same, `X` is not recreated |
| `-checkpoint 1`, folder or `X` deleted, both versions | at the first checkpoint (about 60 s): `Error: TLC threw an unexpected exception ... FileNotFoundException: .../queue.tmp (No such file or directory)`, run aborted |
| `MidViol` (2 workers, queue spilling), `rm -rf X/*` 3 s in, both versions | exit 1, `.../166 (No such file or directory)` (a queue pool file); `rm` itself raced with TLC creating files ("Directory not empty") |

So "continues" holds only when TLC does not need a new file in that folder; the open `.st` and `.fp` handles keep
working. I did not test a violation after deleting the folder of a quiet run. Nothing in TLC notices the missing folder. Safe to delete while a run might be active: nothing in
the folder, or the folder itself. Safe only after the process has exited: everything.

### `-recover`, `-cleanup`, `-dumpTrace`

- `-recover <id>`: the "id" is the path of the checkpoint's timestamped folder. Source:
  `fromChkpt = args[i] + File.separator`, and `makeMetaDir` returns it. Test: SIGTERM at 70 s of a `-checkpoint 1` run,
  then `-recover <folder>` on both versions: `Recovery completed. 2268 states examined. 1 states on queue.` (1.7.4),
  `2220` (1.8.0), finished, exit 0, 4001 states, no new timestamp folder was created, and the old folder was deleted at the end.
  `-metadir` is not needed. A cache that deletes the metadir takes the only recovery point with it.
- `-cleanup`: help text "clean up the states directory". Source: `FileUtil.deleteDir("states", true)`, a path relative to the
  JVM cwd (`TLCGlobals.metaRoot`), skipped when recovering. Test (both versions): stale `cwd/states/stale`,
  `specdir/states/stale` and `md/keep`; ran `-cleanup -metadir md` with an absolute spec path: only `cwd/states` was removed;
  `specdir/states` and `md` untouched. It is not a way to clean `-metadir`.
- `-dumpTrace <format> <file>`: 1.8.0 only (1.7.4: `Error: unrecognized option: -dumpTrace`). With `json rel.json` the file
  appeared in the cwd. `${metadir}` substitution applies to the older `-dump` option; with `-dumpTrace json
  '${metadir}/t.json'` TLC created a literal folder named `${metadir}` in the cwd. Format `tla` needs CommunityModules
  and failed without them. Nothing is written for traces inside the metadir (the `*.st` files are internal and binary).

### Without `-metadir`

(`nm/` test, both versions, Viol spec) A relative spec path run from its own folder wrote `./states/<timestamp>`.
An absolute path run with cwd `/` wrote `<spec dir>/states/<timestamp>` and nothing under `/`. In 1.7.4 both
`states` folders were empty after the violation (cleanup), in 1.8.0 each held the 5 files. So `states/` lands in
the cwd for relative spec paths. tlaup passes `cwd = project_root or spec dir` and `-metadir <cache>`, so this path
is not used by tlaup.

### What `run_cache.py` assumes

Code facts (`src/tlaup/tlc/run_cache.py`, `runner.py` line 144):

1. One folder per spec: `~/.cache/tlaup/run/tlc/<stem>_<hash8>`, passed as `-metadir`. TLC then makes a
   timestamped subfolder in it on every run.
2. `compute_spec_hash` hashes the absolute spec path, the spec bytes and `<stem>.cfg` bytes (the default name only).
   Not hashed: the `--cfg` file that is actually passed (`-config`), extended or instanced modules, custom Java
   modules, the jar version, TLC options. Checked with a script (private `XDG_CACHE_HOME`): hash without cfg
   `0b3494d7`; with an unrelated `Other.cfg` `0b3494d7`; with `Foo.cfg` `306c7db8`.
3. Before every run `_cleanup_stale_spec_dirs` deletes every directory in `run/tlc` whose name starts with `<stem>_`
   and is not the current one. Reproduced: with run folders for `Foo` (spec in `a/`) and `Foo_bar` (in `b/`, with a
   TLC folder inside), calling `get_spec_run_dir(Foo)` deleted `Foo_bar_8286705a` and left only `Foo_0b3494d7`.
   It also deletes: the folder of another project's spec with the same stem and a different path (path is in the hash,
   so each path gets its own folder and the next run of either deletes the other's); and the folder of a run in
   progress after the user edits the spec and starts a second run (what happens to that run is the "Deleting while
   running" table: it may crash at the next checkpoint or queue spill, and the checkpoint is lost).
4. `clear_tlc_run_cache` (`tlaup tlc --cleanup`, `modules add`, `modules remove`) deletes all of `run/tlc`
   with `shutil.rmtree`, including folders of runs in progress, and `suppress(OSError)` hides a failed deletion.
5. Nothing deletes the timestamped folders TLC leaves behind (1.8.0 after any violation; both versions after
   SIGTERM, SIGINT, crash or disk-full). The only thing that ever removes them is the stem-prefix cleanup after the
   spec or its default cfg changes, or the whole-cache wipe. Folders of a spec that never changes grow without limit
   (one MidViol-size violation left 29 MB).
6. Not assumed, but implied: it never uses `-recover`, so the checkpoint files are never used.
   The design does not guard against two tlaup runs of one spec at once (1.7.4 fails one of them; 1.8.0 does not).

## Implications for the roadmap

- Milestone 1 cleanup: the safe unit is the TLC timestamped folder, not the per-spec folder. Matching must be exact
  (`<stem>_<hash>` split on the last underscore, or better a marker file / index with the spec path), never
  `startswith("<stem>_")`. Names with underscores are common in TLA+ (`Foo_bar`).
- To define "run in progress" tlaup needs its own lock or pid file per run folder; TLC offers none and does not mind
  the folder disappearing until a checkpoint or queue spill happens (then it crashes with exit 1 and a Java stack).
  Never delete a folder that a live tlaup/TLC process uses.
- Define when timestamped folders are removed: after a violation or interrupt in 1.8.0 they hold gigabytes in the
  worst case and no use unless `-checkpoint`/`-recover` is wanted (without `-checkpoint` there is no `.chkpt`, so
  the leftovers cannot be recovered). A reasonable rule: tlaup deletes the folder itself after the TLC process exits
  (success, violation, signal) unless the user used `-checkpoint`; and removes folders older than N days on startup.
  This is a design choice; the evidence only shows TLC will not do it.
- Do not rely on `-cleanup`; it targets `./states` only.
- If tlaup wants a fresh folder per run it can pass `-metadir <cache>/<spec>/<run id>` itself and drop the dependence on TLC's
  timestamp. That also removes the 1.7.4 same-second collision. The collision matters only if 1.7.4 stays supported.
- "The run-cache fingerprint covers the default .cfg only": confirmed (hash of `0b3494d7` unchanged when another cfg exists);
  also not covered: modules the spec EXTENDS, and the jar. If the hash only exists to reset checkpoints, note that
  TLC does not check a checkpoint against the spec at `-recover`; it needs the same spec and cfg.
- `<Spec>_TTrace_*.tla/.bin` files are written next to the user's spec by 1.8.0 and never removed; a separate
  decision (pass `-noGenerateSpecTE` or `-teSpecOutDir` into the cache, or leave).

## Open follow-ups

- Why 1.7.4 deletes the folder after a violation (same `cleanup` code). Answering needs a debugger or a trace of
  `deleteDir` calls on 1.7.4.
- Whether a violation trace can still be printed after the folder was deleted in a quiet run (not tested).
- Whether the same-millisecond fallback in 1.8.0 was ever hit in the 20 pairs (not logged).
- Behaviour on Windows (open files cannot be deleted there; the Linux "continues running" result will not transfer)
  and macOS.
- Whether `-recover` accepts a spec with an edited cfg (TLC does not appear to check).
- The `/tmp/tlc-*` module copies left by killed runs, and whether tlaup should care.
- Liveness (`-liveness` disk graphs), `-fpmem` and `-dfid` leave other files; not run here.

## Date checked

2026-11-14.
