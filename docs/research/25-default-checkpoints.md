# 25: Does TLC checkpoint without `-checkpoint`?

## Question

Does TLC write checkpoints when `-checkpoint` is not given, after how long, on each supported build (v1.7.4 and
1.8.0 rolling)? Question 17 ran only with a short interval (`-checkpoint 1`). The answer says how often a run folder
is kept after an interrupt ([design 11 R6](../design/11-runner.md#r6-run-folders)), and how much disk kept folders
can take.

## Source

- Jars (the two the brief names, not downloaded again):
  - v1.7.4: `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`, sha256 `936a2620...`, commit
    5a47802b5c391f59ecdd44117981f4ff8c0656ba.
  - 1.8.0 (rolling): `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`, sha256 `7e53aa63...`, commit
    bc1b506bdcad80bb518bf3776a9161c34ff0fc4c.
- Java: OpenJDK 25.0.5 (Debian), Linux x86-64, 12 cores, real disk. Other research agents ran TLC and javac on the
  same machine at the same time (load average up to 45), so the state rates below are not meaningful; the
  checkpoint times are wall-clock timer driven and were not affected.
- Upstream source read at the two pinned commits (links in Evidence).
- Experiments, in
  [`tests/fixtures/research/25-default-checkpoints/`](../../tests/fixtures/research/25-default-checkpoints/):
  `specs/Long.tla` and `.cfg`; `run_bg.sh` (the first four runs), `run_dfl.py` (the runs that were sent SIGINT, and
  the recoveries), `watch.sh` (folder listings every 20 s), `condense.py` (keeps only listings in which something
  other than the growing trace file changed); `trees/<run>.txt` the condensed listings; `out/<run>.txt` TLC's output
  of every run, with the parsing lines and machine details removed. `trees/roll-default.txt` after 22:27:40 and
  `out/roll-recover.txt` are the discarded double run described at the end of Evidence.

## Short answer

- **Yes, on both builds, every 30 minutes, by default.** The default interval is `30 * 60 * 1000 + 42` ms
  (30 minutes and 42 ms), identical in v1.7.4 and 1.8.0. With no `-checkpoint` the first checkpoint was written
  30 min 4 s after the JVM started on both builds, and again 30 minutes after that (observed on v1.7.4, and on
  1.8.0 in a recovered run, whose timer starts with its own JVM).
- **The clock starts when the JVM loads `TLCGlobals`**, at the very start of `tlc2.TLC`, so parsing and the initial
  states count. TLC only looks at the clock in its periodic loop, which runs once per progress report (60 s), so a
  checkpoint lands at the first progress tick at or after 30 minutes: between 30 and about 31 minutes after start,
  then every 30 to 31 minutes. The checkpoint is printed just before that tick's `Progress(...)` line:
  ```
  Checkpointing of run <tmp>/q25/meta/v174-default/26-11-18-21-56-44
  Checkpointing completed at (2026-11-18 22:26:48)
  ```
- **The files are the same as with `-checkpoint N`** (research 17's list): `queue.chkpt`, `vars.chkpt`,
  `<Spec>-<n>.chkpt`, `<Spec>.st.chkpt`, and on 1.8.0 `settings.chkpt`. So a run interrupted more than about 30
  minutes after it started has a checkpoint, and R6 keeps its folder.
- **`-checkpoint 0` disables it** (source: `doCheckPoint` returns false when the interval is 0; observed: no
  `*.chkpt` file and no "Checkpointing" line after 32 minutes on either build). `-checkpoint N` is in minutes,
  an integer; negative is refused.
- **The unit and the mechanism are the same on both builds and in every BFS mode.** `-dfid` (depth-first) also
  checkpoints on the same timer, but only the fingerprint set (no queue). `-simulate` never checkpoints (the
  simulator has no checkpoint code). With liveness checking the liveness graph is checkpointed too.
- **Differences between default and an explicit `-checkpoint`:** the default value is recognised by its odd 42 ms
  (`chkptExplicitlyEnabled()`). Only an explicit interval makes TLC write a last checkpoint when a run ends with a
  violation or a time bound while the queue is not empty (research 17's "violation with `-checkpoint 1`" case);
  with the default it does not. The periodic checkpoints are the same.
- **A recovered run warns on 1.8.0 unless `-seed` and `-fp` are repeated.** Recovering the default checkpoint
  printed a "Recovering this checkpoint with different settings ..." warning naming the `-seed` and `-fp` of the
  checkpoint, because both are random by default; see Implications (it touches R6's resume command).
- **Interrupt and recover work from a default checkpoint on both builds.** 1.8.0: SIGINT ten seconds after the
  first default checkpoint (exit 130), then `-recover` with the run's `-seed` and `-fp`: no warning, finished with
  the exact state count (103,041), folder deleted. v1.7.4: SIGTERM after the second default checkpoint (exit 143;
  SIGINT could not be used, see Evidence), then `-recover` with new random `-seed`/`-fp`: no warning (v1.7.4 has no
  settings check), finished, folder deleted, but counted 103,042 distinct states, one too many.

## Confidence

Verified on Linux with Java 25 for both builds: the default interval and its unit from the source, the first
default checkpoint on both builds by running, the second on v1.7.4 and in a recovered 1.8.0 run by running,
interrupt and `-recover` on both, `-checkpoint 0` by running for 32 minutes on both. `-dfid`, `-simulate` and liveness were read from the source only, not run. macOS and Windows
were not run; nothing in the code path is platform dependent (a timer and ordinary file writes).

## Evidence

### Source, pinned

- Default interval and the system property that overrides it (`-Dtlc2.TLCGlobals.chkpt=<ms>`):
  `DEFAULT_CHECKPOINT_DURATION = (30 * 60 * 1000) + 42` and
  `chkptDuration = Integer.getInteger(TLCGlobals.class.getName() + ".chkpt", DEFAULT_CHECKPOINT_DURATION)`;
  `lastChkpt = System.currentTimeMillis()` as a static initialiser.
  [v1.7.4 TLCGlobals lines 23, 123, 132](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L23),
  [1.8.0 lines 31, 225, 234](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L31).
- `doCheckPoint()`: forced (JMX) first, then `chkptDuration == 0` means never, else "now - lastChkpt >= interval".
  `chkptExplicitlyEnabled()` is `chkptDuration > 0 && chkptDuration != DEFAULT_CHECKPOINT_DURATION`.
  [v1.7.4 lines 134-164](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L134-L164),
  [1.8.0 lines 236-266](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L236-L266).
- `-checkpoint` parsing: `Integer.parseInt(arg) * 1000 * 60` (minutes, int arithmetic, negative refused); usage text
  "interval between check point; defaults to 30".
  [v1.7.4 TLC lines 590-613](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L590-L613),
  [1.8.0 lines 853-876](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L853-L876).
  The only place TLC itself sets the interval to 0 is a model packed inside the jar (distributed TLC):
  [1.8.0 line 1204](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1204).
- The periodic loop: `AbstractChecker.runTLC` calls `doPeriodicWork()` then `runTLCContinueDoing`, which waits
  `progressInterval` (60 s; on 1.8.0 settable with `-Dtlc2.TLC.progressInterval=<s>`, fixed in v1.7.4).
  [1.8.0 AbstractChecker lines 451-490](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/AbstractChecker.java#L451-L490),
  [1.8.0 ModelChecker line 1035](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L1035),
  [1.8.0 TLCGlobals line 221](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java#L221).
- BFS: `ModelChecker.doPeriodicWork` asks `doCheckPoint()` once, suspends the workers, and calls `checkpoint()`
  (queue, trace, fingerprint set, intern table, liveness graph, and on 1.8.0 the settings file); the files are
  written as `.tmp` and renamed over the old `.chkpt` on commit.
  [v1.7.4 lines 660-727](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L660-L727),
  [1.8.0 lines 708-781](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L708-L781).
  The two builds differ only in 1.8.0's `PERIODIC` hook and `settings.chkpt`.
- End-of-run checkpoint only when explicitly enabled: `cleanup` checks `chkptExplicitlyEnabled()`.
  [v1.7.4 line 811](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L811),
  [1.8.0 line 874](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L874).
- `-dfid`: `DFIDModelChecker.doPeriodicWork` uses the same `doCheckPoint()` and checkpoints the fingerprint set,
  the intern table and the liveness graph.
  [v1.7.4 line 683](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/DFIDModelChecker.java#L683),
  [1.8.0 line 690](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/DFIDModelChecker.java#L690).
- `-simulate`: `Simulator.java` and `SimulationWorker.java` contain no checkpoint code at either commit
  (`grep -ci chkpt` gives 0).
- Messages: "Checkpointing of run %1%", "Checkpointing completed at (...)", "Starting recovery from checkpoint %1%",
  "Recovery completed. %1% states examined. %2% states on queue." (`MP.java`, EC `TLC_CHECKPOINT_*`).

### Runs

Spec `Long` (fixture `specs/Long.tla`): two counters up to 320 with a deliberately slow guard, 103,041 distinct
states, about an hour or more with one worker on a loaded machine. Every run with `-workers 1` and its own
`-metadir <tmp>/q25/meta/<name>`, started 2026-11-18 21:56:44 (local time of the machine, which TLC also uses):

| Run | Build | Flags | First "Checkpointing completed" | `*.chkpt` files |
| --- | --- | --- | --- | --- |
| v174-default | v1.7.4 | none | 22:26:48 (30 min 4 s after start) | yes |
| roll-default | 1.8.0 | none | 22:26:48 (30 min 4 s) | yes |
| v174-cp0 | v1.7.4 | `-checkpoint 0` | none by 22:28:48, then stopped | none |
| roll-cp0 | 1.8.0 | `-checkpoint 0` | none by 22:28:48, then stopped | none |

The default runs printed the two checkpoint lines directly before the `Progress(...)` line of the same second, the
31st progress tick:

```
Progress(206) at 2026-11-18 22:25:48: 42,027 states generated (2,443 s/min), 21,219 distinct states found (1,228 ds/min), 205 states left on queue.
Checkpointing of run <tmp>/q25/meta/v174-default/26-11-18-21-56-44
Checkpointing completed at (2026-11-18 22:26:48)
Progress(211) at 2026-11-18 22:26:48: 44,165 states generated (2,138 s/min), 22,293 distinct states found (1,074 ds/min), 210 states left on queue.
```

Folder listing six seconds after the checkpoint (name, bytes, modification time; `watch.sh` took one every 20 s,
the full listings are in the fixture's `trees/`):

```
v1.7.4                                       1.8.0
Long-0.chkpt     16      22:26:48            Long-0.chkpt     16      22:26:48
Long_0.fp        0       21:56:45            Long_0.fp        0       21:56:45
Long-0.st        289809  22:26:48            Long-0.st        233779  22:26:48
Long_1.fp        0       21:56:45            Long_1.fp        0       21:56:45
Long.st          0       21:56:44            Long.st          0       21:56:44
Long.st.chkpt    0       22:26:48            Long.st.chkpt    0       22:26:48
queue.chkpt      3607    22:26:48            queue.chkpt      3250    22:26:48
vars.chkpt       7770    22:26:48            settings.chkpt   88      22:26:48
                                             vars.chkpt       12429   22:26:48
```

Before 22:26:48 the folders held only `Long_0.fp`, `Long_1.fp`, `Long.st` and `Long-0.st`, the files research 17
lists for a run without a checkpoint. The `-checkpoint 0` folders never held anything else.

The v1.7.4 default run went on and checkpointed again exactly 30 minutes later, at the 61st tick:

```
Checkpointing of run <tmp>/q25/meta/v174-default/26-11-18-21-56-44
Checkpointing completed at (2026-11-18 22:56:48)
Progress(374) at 2026-11-18 22:56:48: 133,368 states generated (2,997 s/min), 67,005 distinct states found (1,499 ds/min), 268 states left on queue.
```

`queue.chkpt` (4593 bytes), `vars.chkpt`, `Long-0.chkpt` and the trace `Long-0.st` (871,065 bytes) got new times;
the folder held the same names as after the first checkpoint, so each checkpoint replaces the previous one. A
second rolling run (`roll2`, started 22:28:48 with `run_dfl.py`) checkpointed at 22:58:52, 30 min 4 s after its
start, with the same files as `roll-default`. The rolling default run itself had to be discarded before its second
checkpoint (see the last part of this section).

### Interrupt and recover

- **1.8.0, SIGINT.** `roll2` was sent SIGINT (to the `java` pid) at 22:59:02, ten seconds after its first default
  checkpoint. Exit 130, nothing printed, the folder left with the checkpoint files above (`Long-0.st` 469,690
  bytes, `queue.chkpt` 4593, `settings.chkpt` 87, `vars.chkpt` 12,428; 486,814 bytes in all). Before the recovery a
  copy of the folder was made, so it could be recovered twice.
  - `-recover <folder>` with no other flags: recovered, with the settings warning (both values random by default):
    ```
    Starting recovery from checkpoint <tmp>/q25/meta/roll2/26-11-18-22-28-48.671/
    Warning: Recovering this checkpoint with different settings can produce inconsistent state counts and counterexamples with missing or incorrect states. Results may be unreliable.
    The checkpoint was created with -seed 3820130351746780114 -fp 69 -workers 1 (fingerprint -1665820305993667152).
    This run is using -seed -1572532724220346458 -fp 56 -workers 1 (fingerprint -6569412558207616258).
    Changed: seed, fingerprint.
    To match the checkpoint, rerun with -seed 3820130351746780114 -fp 69 -workers 1.
    Recovery will continue with the current settings at your own risk.
    Recovery completed. 36130 states examined. 269 states on queue.
    ```
    The values it names are the ones the interrupted run printed in its banner ("with fp 69 and seed
    3820130351746780114").
  - `-seed 3820130351746780114 -fp 69 -recover <copy>`: recovered with no warning, "Recovery completed. 36130 states
    examined. 269 states on queue.", and went on exploring. Thirty minutes after its own start it checkpointed
    again, into the folder it recovered from (23:30:02; the timer starts with each JVM, a recovered run is no
    different). It finished at 23:40:15, exit 0, with "169848 states generated, 103041 distinct states found, 0
    states left on queue.", the exact count, and TLC deleted the folder.
  - A first try with the wrong values (taken from another run's banner by mistake, `out/roll2-rec-wrongseed.txt`)
    printed the same warning: the check compares the values, it does not only look for the flags.
- **v1.7.4, SIGTERM.** The v1.7.4 default run had SIGINT ignored (next part), so it was stopped with SIGTERM at
  22:57:00, after its second checkpoint: exit 143, folder 888,923 bytes. `-recover` on it with no other flags:
  "Starting recovery from checkpoint ...", "Recovery completed. 67005 states examined. 269 states on queue.", no
  settings warning (v1.7.4 writes no `settings.chkpt`). It finished at 23:16:49, exit 0, and TLC deleted the
  timestamped folder. Its total was "139080 states generated, 103042 distinct states found, 0 states left on
  queue." The spec has 321 × 321 = 103,041 states, so the recovered run counted one state too many. The cause
  was not looked into, and no uninterrupted run of the spec was completed to compare with on the same build.
- Neither recovered run made a new timestamped folder; both went on writing in the folder they recovered from
  (research 17 saw the same).

### A trap met on the way: SIGINT ignored by a background JVM

The first SIGINT, sent to the `java` of `roll-default`, did nothing: that JVM was started as a background job (`&`)
of a non-interactive shell, which starts its children with SIGINT ignored (`/proc/<pid>/status` showed
`SigIgn: 0000000000000003`, SIGHUP and SIGINT), and the JVM then does not install its own handler. The run went on,
and a `-recover` started on its folder ran for a few seconds next to it (both writing one folder) before both were
stopped with SIGTERM (exit 143). That folder was thrown away. The interrupt test was repeated with `run_dfl.py`,
which resets SIGINT and SIGHUP to their defaults in the child. Design 20 G3 already keeps an ignored signal
ignored on purpose (`nohup`); this is the same mechanism seen from the other side: a tlaup started in the
background of a script cannot be stopped with SIGINT, and neither can its TLC.

## Implications for the roadmap

- **R6 fires for any run interrupted after about 30 minutes.** A run stopped earlier, without `-checkpoint`, has no
  `*.chkpt` file and leaves nothing; a run stopped later is kept. So kept folders are not rare: every long run that
  a user stops with Ctrl-C, that a CI job times out, or that crashes (out of memory, which is the usual end of a
  long run) after half an hour leaves one. The rule as written ("keyed on the files being there") holds unchanged;
  the "Waiting on question 25" notes in R6 (Why keep checkpoints, Risks) can be replaced by this answer.
- **Size.** A kept folder is not just the checkpoint files: it is the whole timestamped folder. In these runs the
  checkpoint files proper were small (queue 3 KB, vars 8 to 12 KB), and the bulk was the trace file `<Spec>-<n>.st`,
  which TLC writes for every run whether it checkpoints or not, at roughly 10 to 16 bytes per distinct state
  (13 here; research 17's 2.8 M-state run had 29 MB). On top of that come the queue (`queue.chkpt` is a full copy of
  the unexplored states, plus spill files of about 200 KB each while running) and, once the fingerprint set no
  longer fits in memory, its disk files. No `.fp.chkpt` file appeared: with the default in-memory fingerprint set
  TLC rebuilds it from the trace on recovery. So a run of 10^8 to 10^9 distinct states, the kind that runs for
  hours, leaves a folder of one to tens of gigabytes, and stays 30 days under R6. The design's "up to gigabytes"
  (D48) is right. `tlaup cache` showing sizes, `--no-keep` and `cache clean --all` are the controls; a total-size
  line in `tlaup cache` and in the "Checkpoint kept" note would make the cost visible when it happens.
- **The resume command should carry `-seed` and `-fp` on rolling builds.** TLC 1.8.0 records the seed and the
  fingerprint index of a run in `settings.chkpt`, and recovering with different ones prints a multi-line warning
  ("Results may be unreliable") that names the values to pass. Both are random unless given. R6's resume command
  is "TLC's arguments as given, plus `-recover`", so as designed every resumed run that did not pin them gets this
  warning. Options for the designer: tlaup reads `seed` and `fp` from TLC's banner line ("with fp 58 and seed
  ...", printed by both builds) and adds them to the resume command; or tlaup always passes `-fp`/`-seed`; or the
  warning is accepted. v1.7.4 has no settings file and no warning, but its recovery with new random values counted
  one state too many (103,042 of 103,041) while the 1.8.0 recovery with matching values was exact, which fits the
  warning's own claim ("inconsistent state counts"). One run each, so this is a hint, not a measurement. The same
  applies to v1.7.4: carrying the values costs nothing there either. Not changed here.
- **`-checkpoint 0` is the way to make a run that never leaves a checkpoint**, if a mode wants that (it is cheaper
  than `--no-keep` only in that TLC skips the suspend-and-write every 30 minutes; with `--no-keep` the folder is
  deleted anyway). The design needs no change.
- **For tests:** R6's integration test with `-checkpoint 1` stays the practical one; a default checkpoint takes 30
  minutes. A test that needs one sooner without changing TLC's arguments can set
  `-Dtlc2.TLCGlobals.chkpt=<ms>` through the Java options (both builds read it); not run here.
- **For question 34 (not answered here), what was seen about how often files change:** in a run without a
  checkpoint the only file that changed was the trace `<Spec>-<n>.st`, growing in 8 KB steps (one step every
  30 to 60 s at this spec's slow rate, far more often in a fast spec); `<Spec>_<n>.fp` and `<Spec>.st` kept their
  creation time and size 0 for the whole run; no queue spill files appeared because the queue stayed small (about
  200 states). The `*.chkpt` files changed only at each checkpoint, all within the same second, written as `.tmp`
  and renamed. The folder's own modification time therefore changes only when a file is created or renamed (at the
  start and at each checkpoint, and when a queue spill file is created or removed), not while the trace grows.

## Open follow-ups

- `-dfid`, `-simulate` and a spec with liveness were not run; their behaviour is from the source.
- macOS and Windows not run (no platform-specific code in this path; not proposed for the CI run).
- A spec whose initial states take longer than 30 minutes, or a checkpoint that itself takes minutes (a large
  queue): the timer is not reset by the time the checkpoint takes, only set when the check passes, so long
  checkpoints do not push the next one back much. Not measured.
- The size of `queue.chkpt` for a wide state space was not measured; it is the size of the queue at that moment.

## Date checked

2026-11-18 (all runs between 21:56 and 23:41 on the machine's clock; source read the same day at the two
pinned commits).
