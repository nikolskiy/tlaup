# 34: How often TLC writes under its `-metadir`

## Question

How often does TLC write anything under its `-metadir` folder during a long run, on each supported build (v1.7.4 and
1.8.0 rolling), with and without `-checkpoint`? Which files change (contents, mtime of files and of folders, new
files), and what is the longest time between two writes while TLC is working? Can "nothing under the folder was
written for a day" stand for "no TLC is running here"? This decides whether option 2 of
[11 R6](../design/11-runner.md#r6-run-folders), Risks (count an unsettled folder's age from its last write instead of
from `started`) can be taken.

## Source

- Roadmap, investigation list item 34; [11 R6](../design/11-runner.md#r6-run-folders) Risks, option 2;
  [`specs/README.md`](../../specs/README.md#runfolders) (finding K1-5); [research 17](17-metadir.md) for what the
  folder holds.
- Jars: v1.7.4 (`TLC2 Version 2.19 of 08 August 2024`, rev 5a47802, sha256 `936a2620...`) and 1.8.0 (rolling)
  (`TLC2 Version 2026.11.15.002146`, rev bc1b506, sha256 `7e53aa63...`; the rolling and v1.8.0 assets are the same
  bytes).
- Java: OpenJDK 25.0.5 for every run. Linux x86-64, 12 cores, ext4 on LVM (not tmpfs). Other agents ran TLC on the
  same machine at the same time (load average about 7), so throughput numbers are rough; the gaps below do not
  depend on speed except where said.
- Upstream source at the two pinned commits, read from a sparse clone (links below). `B18` stands for
  `https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src`
  and `B174` for the same path at `5a47802b5c391f59ecdd44117981f4ff8c0656ba`.
- Experiments: `tests/fixtures/research/34-metadir-write-frequency/`. `watch_run.py` starts TLC with
  `-metadir <run>/md`, stats every entry under `md` (the folder, TLC's timestamped folder, every file) once a second,
  logs new and removed entries and size or mtime changes, and records at each poll the age of the newest mtime under
  the folder ("staleness", what a sweep counting from the last write would see). After the chosen time it sends
  SIGTERM to the TLC pid. `batch.sh` holds every run; `summaries.json` the results; `events/` the logs (the two
  large ones trimmed). `inotifywait` is not installed, so polling was used; a poll every second sees the last write
  of each second, which is enough for gaps of seconds and more.

## Short answer

- **Breadth-first model checking that keeps finding states writes all the time.** Both builds, with and without
  `-checkpoint`: something under the folder changed in every one-second poll for 15 minutes; the longest silence was
  0.8 s (v1.7.4) and 0.3 s (1.8.0). What changes: the per-worker trace files `<Spec>-<n>.st` grow (in 8 KB steps),
  queue pool files (`0`, `1`, ... 212,992 bytes each) are created and deleted by the thousand (about 9,400 created and
  8,600 deleted in 15 minutes), so the timestamped folder's own mtime changes every second; `<Spec>_<n>.fp` grow when
  the in-memory fingerprint table fills (64 MB at about 130 s, 128 MB at about 370 s in these runs).
- **TLC can work for a long time and write nothing.** A write happens only when an 8 KB trace buffer fills (about 450
  new states per worker), the state queue holds more than 8,192 states, the fingerprint table fills, a checkpoint is
  taken, or (with a liveness property) the behaviour-graph buffers fill. Measured silences while TLC was busy:

  | Run | v1.7.4 | 1.8.0 |
  |---|---|---|
  | Few expensive states (about 5 a minute), no `-checkpoint`, 36 min | 1,809 s, then the default checkpoint | 1,815 s, then the default checkpoint |
  | Same, `-checkpoint 1` | 76 s | 78 s |
  | One state that takes about 12 minutes, `-checkpoint 1`, 20 min | not run | 710 s: the checkpoint waited for the state |
  | `-simulate -depth 100`, 10 min (and 1.8.0 with `-checkpoint 1`) | 600 s, nothing ever written | 600 s, nothing ever written |
  | `-dfid 60`, 10 min, no `-checkpoint` | 600 s, nothing written | 600 s, nothing written |
  | `-dfid 60 -checkpoint 1`, 3 min | not run | 72 s (only checkpoint files) |
  | Liveness, 16 M states: final temporal check | 102 s | 106 s |

- **Without `-checkpoint`, TLC still checkpoints every 30 minutes** in breadth-first and `-dfid` mode (the default
  interval is `30 * 60 * 1000 + 42` ms), on both builds. That is the only upper bound on a silence, and it does not hold:
  the checkpoint waits until every worker has finished the state it is working on, is not taken during a liveness check,
  and does not exist in `-simulate` (or in 1.8.0's `-generate`, which runs the same simulator). `-checkpoint 0` turns it off ([research 25](25-default-checkpoints.md) observed both).
- So **"nothing written for a day" does not mean "no TLC here"**. It is true in practice for ordinary breadth-first
  runs, whose silences are bounded by about 30 minutes plus the longest single state plus the longest liveness check.
  It is false for a simulation (never writes; a day of simulation leaves a folder last written at its start), for a
  state or a liveness check that takes longer than the threshold, for `-checkpoint 0` runs that find few states, and
  for a machine that was suspended longer than the threshold.
- Which mtime to read: the newest mtime over every entry under the run folder. The timestamped folder's own mtime
  changes only when files are created, renamed or deleted; appends to `.st`, `.fp`, `nodes_*` and `ptrs_*` change only
  the file's mtime. In the slow runs no file was created between checkpoints, so the folder mtime alone and the file
  mtimes agree; in general they do not.

## Confidence

Verified on Linux with Java 25 for the runs in the table, both builds, from the source at the two commits and from
measurements. Partly verified: the bound "30 minutes plus one state" for breadth-first runs without `-checkpoint`
(source, and one 36-minute run per build; not run for hours). The claims about `-generate`, `-checkpoint 0`, a
suspended machine and a liveness check longer than a day come from the source and from scaling the measured times,
not from runs. Not tested: Windows, macOS, Java 11 and 21, `-fpmem`/`-gzip` variants, distributed TLC, a periodic
liveness check during the search longer than a few seconds.

## Evidence

### When TLC writes (source)

| What | Write trigger | Source |
|---|---|---|
| Per-worker trace `<Spec>-<n>.st` | every new distinct state appends a predecessor pointer (about 18 bytes) to a `BufferedRandomAccessFile`, whose buffer is 8 KB (`LogBuffSz = 13`): a write about every 450 new states per worker | `Worker.writeState` [B18 tlc2/tool/Worker.java#L301](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/Worker.java#L301) ([B174 #L214](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/Worker.java#L214)); buffer size [B18 tlc2/util/BufferedRandomAccessFile.java#L34](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/util/BufferedRandomAccessFile.java#L34) ([B174 #L25](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/util/BufferedRandomAccessFile.java#L25)) |
| Queue pool files `0`, `1`, ... | the in-memory enqueue buffer holds 8,192 states (`DiskStateQueue.BufSize`); when it is full it is written to a new pool file. A cleaner thread deletes read pool files in batches of about 100 | `DiskStateQueue.enqueueInner` and `StatePoolCleaner` [B18 tlc2/tool/queue/DiskStateQueue.java#L31](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/queue/DiskStateQueue.java#L31) ([B174 #L28](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/queue/DiskStateQueue.java#L28)) |
| Fingerprint files `<Spec>_<n>.fp` | flushed when the in-memory table is full (`needsDiskFlush`), and at a checkpoint | [B18 tlc2/tool/fp/DiskFPSet.java#L321](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/fp/DiskFPSet.java#L321) ([B174 #L319](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/fp/DiskFPSet.java#L319)) |
| Behaviour graph `nodes_<n>`, `ptrs_<n>` (liveness only) | buffered appends while new states are added; read, not written, by the liveness check | [B18 tlc2/tool/liveness/AbstractDiskGraph.java#L103](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/liveness/AbstractDiskGraph.java#L103) ([B174 #L102](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/liveness/AbstractDiskGraph.java#L102)) |
| Checkpoint `*.chkpt` (written as `.tmp`, then renamed) | `TLCGlobals.doCheckPoint`: when `chkptDuration` has passed since the last one. The default is `30 * 60 * 1000 + 42` ms, so a checkpoint is taken every 30 minutes without `-checkpoint`; `-checkpoint 0` turns it off | [B18 tlc2/TLCGlobals.java#L247](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L247) (default at [#L31](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L31)); [B174 #L145](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L145) (default at #L23) |

When the checkpoint is taken: the main thread wakes every progress interval (60 s) and calls `doPeriodicWork`
([B18 ModelChecker.java#L708](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L708),
[B174 #L660](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L660)).
If a checkpoint or a liveness check is due it calls `theStateQueue.suspendAll()`, which waits until every worker has
finished the state it is expanding. A periodic liveness check runs first, then the checkpoint. So the checkpoint is
late by up to the time of one state, plus the time of the liveness check. The same thread prints the progress lines:
in the 12-minute-state run TLC printed no progress line for 12 minutes either.

Other modes:

- `-simulate` (and `-generate`, 1.8.0 only, same `Simulator`; not run): the metadir and its timestamped folder are created
  (`FileUtil.makeMetaDir` runs before the mode is chosen), but the simulator uses `NoOpLiveCheck` or the in-memory
  `LiveCheck1` and has no checkpoint; nothing is ever written to the folder
  ([B18 tlc2/tool/Simulator.java#L115](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/Simulator.java#L115),
  [B174 #L84](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/Simulator.java#L84)).
  The experimental liveness simulation writes to a temporary folder outside the metadir.
- `-dfid`: the fingerprint set is in memory (`MemFPIntSet`), there is no disk queue or trace file; only the
  checkpoint writes (`Big.fp.chkpt`, `vars.chkpt`)
  ([B18 tlc2/tool/DFIDModelChecker.java#L676](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/DFIDModelChecker.java#L676),
  [B174 #L669](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/DFIDModelChecker.java#L669)).

The write logic is the same in the two commits; only line numbers and the 1.8.0 `settings.chkpt` differ.

### Specs

All in `specs/` of the fixture folder.

- `Big`: four counters, 400^4 states, never finishes in a run; 2 workers. Queue, trace and fingerprints grow all the
  time.
- `Slow`: one counter; each step builds `R` sets of 810,000 numbers (`K = 900`). `Slow.cfg` (`R = 10`) gives about
  5 states a minute; `SlowStep12min.cfg` (`R = 400`) about 12 minutes a state. 1 worker. The worst case for "TLC works
  without writing": few states, each expensive.
- `Live`: two counters mod `N` with `WF` and the property `[]<>(a + b >= 0)` (it holds); `N = 1500` (2.25 M states)
  and `Live4000.tla` with `N = 4000` (16 M states; copy it as `Live.tla` to run it). 2 workers.
- `-simulate -depth 100` and `-dfid 60` runs use `Big`.

### Results

`summaries.json`; "silence" is the largest staleness seen while the TLC process was alive (after the first 5 s);
"writes" is the number of distinct values the newest mtime took.

| Run | Build | Args | Length | Exit | Silence | Writes |
|---|---|---|---|---|---|---|
| big-174-default | v1.7.4 | `-workers 2` | 902 s | 143 (SIGTERM) | 0.8 s | 853 |
| big-180-default | 1.8.0 | `-workers 2` | 901 s | 143 | 0.3 s | 853 |
| big-174-ck1 | v1.7.4 | `-workers 2 -checkpoint 1` | 902 s | 143 | 0.2 s | 858 |
| big-180-ck1 | 1.8.0 | `-workers 2 -checkpoint 1` | 902 s | 143 | 0.2 s | 858 |
| slow-174-default | v1.7.4 | `-workers 1` | 2161 s | 143 | 1809 s | 5 |
| slow-180-default | 1.8.0 | `-workers 1` | 2162 s | 143 | 1815 s | 5 |
| slow-174-ck1 | v1.7.4 | `-workers 1 -checkpoint 1` | 902 s | 143 | 76 s | 14 |
| slow-180-ck1 | 1.8.0 | `-workers 1 -checkpoint 1` | 901 s | 143 | 78 s | 14 |
| veryslow-180-ck1 | 1.8.0 | `-workers 1 -checkpoint 1`, 12-minute states | 1201 s | 143 | 710 s | 4 |
| sim-174 | v1.7.4 | `-workers 1 -simulate -depth 100` | 601 s | 143 | 600 s | 2 |
| sim-180 | 1.8.0 | same | 601 s | 143 | 600 s | 2 |
| sim-180-ck1 | 1.8.0 | same with `-checkpoint 1` | 601 s | 143 | 600 s | 2 |
| dfid-174 | v1.7.4 | `-workers 1 -dfid 60` | 601 s | 143 | 600 s | 2 |
| dfid-180 | 1.8.0 | same | 601 s | 143 | 600 s | 2 |
| dfid-180-ck1 | 1.8.0 | `-workers 1 -dfid 60 -checkpoint 1` | 201 s | 143 | 72 s | 5 |
| live-174 | v1.7.4 | `-workers 2`, 2.25 M states | 36 s | 0 | 18.5 s | 14 |
| live-180 | 1.8.0 | same | 38 s | 0 | 21 s | 15 |
| live4000-174 | v1.7.4 | `-workers 2`, 16 M states, `-Xmx1500m` | 169 s | 0 | 102 s | 59 |
| live4000-180 | 1.8.0 | same | 165 s | 0 | 106 s | 55 |

"Writes = 2" means the metadir and the timestamped folder were created in the first second and nothing changed after.

Details:

- **Big, default and `-checkpoint 1`.** Event counts for big-180-default: 9,434 files created, 8,611 deleted, 1,688
  file changes, 847 changes of a folder's mtime, in 901 s. About 18 pool files are created per second; `.st` files
  grow every second; `Big_0.fp` and `Big_1.fp` went 0 -> 64 MB at about 130 s and `Big_1.fp` 64 -> 128 MB at about
  370 s (same on v1.7.4). With `-checkpoint 1` 14 checkpoints were written per run, and the folder held about 3 GB at
  the end (1.6 GB without). TLC had found about 73 M distinct states at 15 minutes on both builds.
- **Slow, default.** Both builds: the files of research 17 appear in the first 5 s (`Slow.st`, `Slow-0.st`,
  `Slow_0.fp`, `Slow_1.fp`, all empty), then nothing changes until 1,813 s (v1.7.4) and 1,820 s (1.8.0), when the
  default checkpoint writes `Slow-0.chkpt`, `Slow.st.chkpt`, `queue.chkpt`, `vars.chkpt` (and `settings.chkpt` on
  1.8.0) and flushes `Slow-0.st` (0 -> about 1 KB, the first write of the trace file, after about 100 states). The
  next checkpoint would have come at about 3,600 s; the run was stopped at 2,160 s. This is also a direct answer to
  question 25 for these two builds: TLC writes checkpoint files every 30 minutes without `-checkpoint`.
- **Slow, `-checkpoint 1`.** The first checkpoint at 80 s, then one about every 70-78 s: a checkpoint is due after
  60 s but waits for the state in progress (about 12 s per state here).
- **Very slow (12-minute states), `-checkpoint 1`, 1.8.0.** Writes at 1 s and 2 s (folder and empty files), then
  nothing until 711.7 s, when the first checkpoint was written right after the second state was found
  (`Checkpointing completed at 22:53:09`, `Progress(2) at 22:53:09`). `-checkpoint 1` asked for one after 60 s; it
  came after 711 s. With states that take a day, a checkpoint comes once a day.
- **Simulate.** 9 progress lines, 12.6 M traces generated on 1.8.0, and not one write under the folder. With
  `-checkpoint 1` the same.
- **DFID.** 28 M distinct states in 10 minutes, no write under the folder (the default checkpoint was not due yet).
  With `-checkpoint 1`, writes only at the checkpoints: 66 s (`Big.fp.chkpt` 68 MB, `vars.chkpt`), 128-129 s
  (`Big.fp.tmp` then renamed over `Big.fp.chkpt`), and so on.
- **Liveness.** During the search the folder is written as for any breadth-first run, plus `nodes_0` and `ptrs_0`
  (108 MB and 36 MB at 2.25 M states). The periodic check during the search (6 s at about 0.8 M states) and the final
  check write nothing: the final check took 19-20 s for 2.25 M states and 1 min 45 s for 16 M states, and the
  silences measured (18.5 to 106 s) are those final checks. They grow with the number of states (about 6.5 us a state
  here, for a one-branch tableau; a property with more tableau nodes multiplies the graph). By scaling, a run of
  about 10^10 distinct states with a liveness property would be silent for most of a day at its end; with the default
  `-lncheck`, every periodic check during the search is a silence of the same kind, though TLC limits their share of
  the run time (`livenessRatio`).

### What a sweep should look at

- The newest mtime of all entries under the run folder, recursively. Folder mtimes change on create, rename and
  delete (pool files, `.tmp` -> `.chkpt`); file mtimes change on writes into them. Appends to `.st`, `.fp`,
  `nodes_*`, `ptrs_*` touch the file only.
- Reading does not change mtime, so a liveness check that reads its graph files looks the same as no process at all.
- mtimes are wall-clock times. A machine that sleeps for a day leaves a live TLC's folder unwritten for a day
  (not tested, follows from the clock).

## Implications for the roadmap

For [11 R6](../design/11-runner.md#r6-run-folders), Risks, option 2 (count an unsettled folder's age from its last
write):

- **It cannot rely on last-write age as proof that no TLC runs.** A folder whose newest mtime is a day old can belong
  to a live TLC in these cases:
  1. `-simulate` (or `-generate` on 1.8.0): never writes, so the age from the last write equals the age from the start, the very
     thing option 2 was meant to fix. (Deleting such a folder is harmless to the simulation itself, which never opens
     a file there, per research 17's "quiet run continues"; but it is a folder deleted under a running TLC.)
  2. A state whose successors take longer than the threshold to compute: no trace write, no checkpoint, until the
     state is done; then the next checkpoint or pool file write crashes TLC with `FileNotFoundException` if the folder
     was deleted (research 17).
  3. A liveness check (final or periodic) longer than the threshold; a periodic one is followed by more writes, so the
     same crash.
  4. `-checkpoint 0` with few new states: nothing bounds the silence.
  5. A machine suspended (or a TLC stopped with SIGSTOP) longer than the threshold, which then resumes.
- **What threshold would be safe for the common case.** For breadth-first model checking with the default or any
  `-checkpoint N`, the silence is at most about max(N, 30 min) + the longest single state + the longest liveness
  check. One day covers every run measured here by a factor of 48 or more (the longest measured silence was 1,815 s).
  As a heuristic, "newest mtime under the folder older than one day" is right for ordinary runs and wrong only in the
  cases above. Two days or a week would shrink cases 2, 3 and 5 but not case 1 or 4.
- **Option 2 is still better than counting from `started`** for the case it was written for: a breadth-first run
  that began more than a day before its tlaup was killed. Under option 1 the next sweep deletes such a folder at once;
  under option 2 it waits until the run has been silent for a day, which for these runs means TLC has stopped. If it
  is taken, the sweep must read every entry's mtime recursively (the folder's own mtime is not enough), and it stays a
  heuristic: the design should not describe it as "no TLC is running".
- It does nothing for finding K1-3 (`-recover` into a folder whose TLC still runs), as R6 already says. Options 3 and
  4 (questions 33 and 35) close the risk as a whole; nothing here argues against preferring option 4.
- For question 25 ([result](25-default-checkpoints.md)) and the "Kept folders can be large" risk: this agrees with it; both builds take a checkpoint every 30 minutes without
  `-checkpoint` (breadth-first and `-dfid`, not `-simulate`), so any breadth-first run that is interrupted after 30
  minutes leaves a resumable folder. The checkpoint of `Big` after 15 minutes of `-checkpoint 1` was about 3 GB of
  folder.

## Open follow-ups

- Not run for hours: a breadth-first run without `-checkpoint` that finds few states for several checkpoint
  intervals, and a liveness run large enough for a final check of an hour or more.
- `-generate` and a suspended machine were not run; they follow from the source and the clock. `-checkpoint 0` was run by research 25 (no checkpoint in 32 minutes), not watched here.
- Windows and macOS were not tested; mtime behaviour of NTFS and APFS for appends is expected to match but was not
  checked.
- Whether deleting the folder during a final liveness check makes TLC fail (it reads `nodes_*` and `ptrs_*` through
  open handles on Linux; on Windows the deletion fails) was not tested.

## Date checked

2026-11-19 (UTC). Runs between 08:04 and 09:20 UTC.
