# 31. How often TLC prints progress, and what a closed stdout does to the JVM

## Question

Roadmap question 31. Two facts the design states from memory: (1) how often TLC prints a progress line (message 2200
and its relatives, with and without `-tool`, in model checking and in simulation), whether the interval is fixed, and
whether a flag sets it; (2) whether the JVM ignores a closed stdout, so that `java -jar tla2tools.jar Spec | head -1`
leaves TLC running unseen, whether output errors are swallowed, and what a closed stderr does. Asked for v1.7.4 and
1.8.0 (rolling), Java 25.

## Source

- Upstream, read at the two pinned commits (paths under `tlatools/org.lamport.tlatools/src/`):
  - v1.7.4, `5a47802b5c391f59ecdd44117981f4ff8c0656ba`: [`tlc2/tool/TLCGlobals.java` line 120](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/TLCGlobals.java#L120),
    [`tlc2/tool/AbstractChecker.java`](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/AbstractChecker.java),
    [`tlc2/tool/ModelChecker.java`](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java),
    [`tlc2/tool/Simulator.java`](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/Simulator.java).
  - rolling, `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c` (TLC 2026.11.15.002146): the same four files,
    [`TLCGlobals.java` lines 219-222](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/TLCGlobals.java#L219-L222),
    [`AbstractChecker.java`](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/AbstractChecker.java),
    [`ModelChecker.java`](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java),
    [`Simulator.java`](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/Simulator.java).
  - Output goes through `tlc2/output/MP.java`, which calls `ToolIO.out.println(...)` (`util/ToolIO.java`: `public static PrintStream out = System.out`).
- Jars: v1.7.4 (sha256 `936a2620…0e050e88`, `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`) and rolling = v1.8.0
  (sha256 `7e53aa63…fb84f`, `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`). Java: OpenJDK 25.0.5 for every run. Linux
  x86-64, 12 cores. Python 3.13 for the timing script.
- Earlier results: [01](01-tlc-output.md) (message numbers, the progress capture), [15](15-exit-codes-and-signals.md)
  (exit 12 for an invariant violation, SIGTERM gives 143).
- Design asking: [22 O3, O4](../design/22-reporters.md), [11 R1, R2](../design/11-runner.md).
- Captures, scripts and specs: `tests/fixtures/research/31-progress-and-closed-stdout/` (`<repo>` below is the repository).

## Short answer

1. **Progress interval in model checking: fixed at 60 seconds, with one early report.** The first progress message
   comes about 3 seconds after the initial states (the checker waits 3000 ms before its periodic loop), then one every
   60.0 seconds (measured: 60.00 to 60.05 s apart in four runs of 4 minutes, plain and `-tool`, both versions). In v1.7.4
   the interval is a `final` constant (`1 * 60 * 1000`) with no flag. In rolling it is the system property
   `tlc2.TLC.progressInterval` (whole seconds, at least 1, default 60), set with `java -Dtlc2.TLC.progressInterval=5 -jar …`;
   it worked in rolling (reports 5.0 s apart) and was ignored by v1.7.4. There is no TLC command-line flag for it in
   either build. The interval does not change over time. Time spent in periodic work (checkpoint, liveness) delays the
   next message slightly; it is never shorter than the interval, except that the first report is early.
   Other progress-shaped output: the source prints one extra 2200 just before the liveness check starts when liveness is
   on (not run here), and with `-tool` a last progress-format line at the end of a run that finishes without error (not
   seen: every long run here ended on a violation or was killed).
2. **Progress in simulation: one message every 60 seconds, the first at 60 seconds, no early one** (a separate
   `ProgressReport` thread that waits the interval before its first message). Measured 60.0 s apart in both versions.
   Rolling honours `-Dtlc2.TLC.progressInterval` here too (5.0 s apart); v1.7.4 does not. Plain text is
   `Progress: N states checked.` in v1.7.4 and `Progress: N states checked, M traces generated (trace length: mean=…)` in
   rolling; with `-tool` both use message 2209, whose v1.7.4 form is `Progress(-1) … N states generated, -1 distinct states
   found, -1 states left on queue.` and whose rolling form is `Progress(<traces>) …` with the same tail.
3. **The JVM does not stop when its stdout reader goes.** `java … Spec | head -1` and a Python reader that exits after one
   line both left the java process running to the end of the model check (133 s, with the load of other agents), and it
   exited with 12 (invariant violation), the same code as an unpiped run. Same in v1.7.4 and rolling. Nobody sees the
   result: the output after the first line is lost, the exit code is real, and no message about the pipe is printed
   anywhere. The reason is as the brief guessed: the JVM ignores SIGPIPE; the write fails with an `IOException`; the
   `PrintStream` that `System.out` is catches it, sets its error flag and goes on. Confirmed by running TLC in-process
   from a small class that calls `tlc2.TLC` and then asks `System.out.checkError()`: `true` after the reader had gone,
   and `System.err.checkError()` `false`. TLC never calls `checkError`, so nothing reacts to the flag.
4. **A closed stdout or stderr changes nothing visible either.** `>&-` (stdout closed) and `2>&-` (stderr closed): the JVM
   starts, takes the lowest free descriptors for its own files (in these runs descriptor 1, or 2, became the JDK's
   `lib/modules` file, opened read-only), so TLC's writes go to a descriptor that rejects them; the run still ended with
   exit 12 in both versions. `2>/dev/full` (stderr writes fail with ENOSPC): the run ended with exit 12 and a complete
   stdout. TLC prints almost nothing on stderr in a normal run, so stderr problems would show only with unusual errors.
5. **macOS and Windows behave the same** (CI run, section (e)): the JVM stayed alive 2 s after the reader closed the pipe and TLC ran to the end with exit 12, on both versions, both OSes.
6. **Stopping needs the pid.** TLC prints `[pid: N]` in its start line (message 2187, both versions, with and without
   `-tool`), so a reader that leaves early can still learn the pid, but only if it reads that line first.

## Confidence

Verified for: the intervals (source at both commits and timed runs of four minutes, plain and `-tool`, both versions,
and 40 to 150 s runs for the simulator and for the flag); the survival of the JVM under `head -1` and under a reader
that exits, in both versions; the error flag (in-process probe, rolling only); closed stdout, closed stderr and a full
stderr (both versions for the first two, rolling for the full stderr). macOS and Windows verified for the closed-stdout case only (section (e); the interval is the same Java code, not re-timed there). Not verified: a JVM other than OpenJDK 25.0.5 (the `lib/modules`
descriptor reuse depends on how the JDK opens files, so it may differ on Java 11); liveness runs (the extra progress
line before liveness is from the source only); more than one worker; a run so long that the interval might drift; the
exact end-of-run progress behaviour (no extra 2200 appeared on a violation exit; a clean finish with `-tool` was not
timed). Timings were taken while other agents were running TLC on the same 12 cores; the progress interval is a wait of
exactly 60 s, so the load moved no line by more than 0.05 s, but the amount of work between lines (states per interval)
reflects a busy machine.

## Evidence

### (a) Source

v1.7.4 `TLCGlobals.java:120`: `public static final int progressInterval = 1 * 60 * 1000;`. Rolling `TLCGlobals.java:221-222`:

```java
public static final int progressInterval = Math
    .max(Math.abs(Integer.getInteger(TLC.class.getName() + ".progressInterval", 60)), 1) * 1000;
```

(`TLC.class.getName()` is `tlc2.TLC`; the value is seconds; 0 becomes 1; negative becomes positive.) Neither
`TLC.java` has a command-line option that sets `progressInterval`: the only interval option it parses is `-coverage`
(minutes, `coverageInterval`), which counts progress rounds and does not change the progress interval.

Model checking, `AbstractChecker.runTLC` (both commits): `this.wait(3000)` once (skipped if the run is already done),
then `while (true) { doPeriodicWork(); synchronized(this) { if (!done) runTLCContinueDoing(count, depth); … } }`. In
`ModelChecker.runTLCContinueDoing`: `printProgresStats(-1, false)` first, then `this.wait(TLCGlobals.progressInterval)`.
So the first message is at about 3 s, and the following ones at one interval each, since `wait(60000)` returns after
60 s unless something calls `notify` (the checker does so when the run is done). Simulation, `Simulator.ProgressReport.run`
(both commits): `this.wait(TLCGlobals.progressInterval)` first, then print `TLC_PROGRESS_SIMU` (2209), in a loop: the first
message is one interval after the thread starts; rolling also prints a last report when the simulation ends ("Waking the
progress thread serves double duty … one final progress report", `Simulator.java` around line 356).
Output: `MP.printMessage` → `ToolIO.out.println`; `ToolIO.out` is `System.out`; neither `MP` nor `ToolIO` calls
`checkError` (grep of both commits: no hits).

### (b) Timing runs

Spec `spec/Big.tla` (four counters 0..120, 214 million states, no end inside the window), `-workers 2 -deadlock -Xmx700m`,
killed by pid with SIGTERM after 285 s (exit 143). Script `stamp.py` timestamps each stdout line against a monotonic clock
from process start. Four runs started together on 2026-11-18. Seconds since process start of each progress message
(`captures/progress-*.txt`):

| Run | Initial states done | Progress messages at (s) |
| --- | --- | --- |
| v1.7.4 plain | 1.8 | 4.82, 64.85, 124.86, 184.86, 244.88 |
| v1.7.4 `-tool` | 1.8 | 4.86, 64.88, 124.88, 184.88, 244.89 |
| rolling plain | 1.9 | 4.89, 64.90, 124.91, 184.91, 244.96 |
| rolling `-tool` | 1.3 | 4.33, 64.36, 124.36, 184.38, 244.38 |

So: first message 3.0 s after the initial states, then 60.0 s apart; the same in both versions and both output modes.
`-tool` message 2200 and plain `Progress(n) at …` are the same event.

Simulation (`-simulate -workers 1 -deadlock`, `captures/sim-*.txt`, killed at 150 s): v1.7.4 plain at 62.08 and 122.08 s;
v1.7.4 `-tool` (2209) at 62.56 and 122.59; rolling plain at 62.31 and 122.31; rolling `-tool` at 62.55 and 122.56. Each is
the first message one interval (60 s) after the simulator started (about 2 s after process start), then 60 s later.

Flag: `-Dtlc2.TLC.progressInterval=5` (`captures/flag5-*.txt`): rolling model checking at 7.18, 12.19, 17.19, … 37.22 s
(5.0 s apart after the early first); rolling simulation at 8.07, 13.08, … 38.10 s; v1.7.4 model checking printed one line
(6.61 s) and nothing more up to 40 s (property ignored).

A short real run (`captures/closed-rolling-closederr-out.txt` and the v1.7.4 equivalent, the full stdout of a 134 s and a
148 s run) shows the same pattern: first `Progress` at 4 s, the next at 64 s and 124 s, and nothing at the end of the
run apart from the summary and `Finished in …`.

The size of a message over a long run: about one message per minute per run, so 60 an hour; `RunResult.progress` growth
is negligible in every length the roadmap cares about. With the property set to 1 second it would be 3,600 an hour.

### (c) A closed stdout

`closed.sh` starts TLC (spec `spec/Mid.tla`, a 24-million-state check that ends with an invariant violation after
2 to 2.5 minutes under the load of other agents, `-workers 1 -Xmx250m`) as `{ java …; echo exit=$? > rc; } | head -1`,
records the java pid (the shell `exec`s java, so the pid is the shell's), and every 10 s prints whether the pid is alive
and its CPU ticks (`captures/closed-log-*.txt`). Result, same for all four variants (v1.7.4 and rolling, `head -1` and a
Python reader that prints one line and exits): the first line was seen by the reader, the java process stayed in state S
with the CPU ticks rising (about 400 ticks per 10 s, one core), until it exited by itself at 133 s with `exit=12`.
`/proc/<pid>/fd/1` was a pipe whose reader had gone (`pipe:[…]`) for the whole time. `head` itself had exited at once;
`SIGPIPE` never stopped java.

In-process probe `Probe.java` (calls `new tlc2.TLC()`, `handleParameters`, `process`, then prints the flags to a file):
`System.out.checkError() = true`, `System.err.checkError() = false`; `process()` returned normally with the number 2110 (a TLC
message code, not an exit status; the probe did not map it). The flag is the stream's own (`PrintStream` swallows the `IOException` of a broken pipe), which the JVM sets and nothing reads.

Closed descriptors (`captures/closed-log-*closedout.txt`, `*closederr.txt`, `*fullerr.txt`): with `>&-`, `/proc/<pid>/fd`
showed `1 -> <jdk>/lib/modules` (the JVM, finding fd 1 free, opened the JDK's module image on it), TLC's output went to a
read-only descriptor and failed silently, and the run ended with exit 12. With `2>&-` the same on fd 2 (stdout was a
file and had all 3,038 lines). With `2>/dev/full` stdout had all lines and exit was 12. In all, no message about the
failed write appeared anywhere. (Danger worth knowing, not tested: if the JVM had reused fd 1 for a file opened for
writing, TLC's output would go into that file; the JDK opens `lib/modules` and the jar read-only, so here it did not.)

### (e) macOS and Windows (CI)

Run <https://github.com/nikolskiy/tlaup/actions/runs/44489200898> (2026-11-19, success). Images: ubuntu26 20261111.82.6
x86_64, macos26 20261112.0504.1 arm64, win25-vs2026 20261103.298.1 x86_64. Java: Temurin 21 (21.0.13) on PATH. Script
`ci_closed_stdout.py` (reader takes one line and closes the pipe; java checked 2 s later; waits for exit). Logs in `ci/`:

| OS | v1.7.4 | rolling |
| --- | --- | --- |
| Linux | alive after 2 s, exit 12 | alive after 2 s, exit 12 |
| macOS | alive after 2 s, exit 12 | alive after 2 s, exit 12 |
| Windows | alive after 2 s, exit 12 | alive after 2 s, exit 12 |

So the closed pipe is ignored on all three. Not shown: Windows error flag (assumed the same), and Java 11.

### (d) Commands

```
python3 stamp.py OUT 285 java -Xmx700m -jar tla2tools.jar [-tool] -workers 2 -deadlock -metadir ./states Big
python3 stamp.py OUT 150 java … [-tool] -simulate -workers 1 -deadlock -metadir ./s Big
python3 stamp.py OUT 40  java … -Dtlc2.TLC.progressInterval=5 -jar … -workers 1 -deadlock -metadir ./s Big
./closed.sh NAME JAR head|reader|closed-out|closed-err|full-err
java -cp tla2tools.jar:probe Probe -workers 1 -metadir ./states -nowarning Mid | head -1
```

Every process was stopped by its pid (SIGTERM from the script's own timer) or ended by itself; none was left running.

## Implications for the roadmap

- **Plain mode needs no spacing of its own.** TLC's progress lines are 60 s apart after an early first one, in both
  versions, plain and `-tool`, so the design's wording "one line per TLC progress message" holds and
  [22 O3](../design/22-reporters.md#o3-terminal-reporter) can say "about once a minute, measured (research 31)" in place
  of "from memory". The condition O3 named for adding a minimum distance (a much shorter interval on some build) is met
  only if a user passes `-Dtlc2.TLC.progressInterval=N` through `--java-opt` on rolling; then lines come as fast as the
  user asked, which is their choice, and the reporter prints them as it does now. The design's remark that the one capture with two
  lines (in [01](01-tlc-output.md)) has them 3 seconds apart is explained by the early first report followed by a
  report before the end; a regular gap is 60 s.
- **Tests that count progress** (22 O4, the `progress` list of 11) can assume one entry per minute; the "newest 50" and the
  `max_output_lines` cap are not at risk. `--refresh-interval` is independent.
- **The O4 live view** is idle for up to 60 s after the first progress row (about 3 s in); a layout that shows "no
  progress yet" must expect a gap that long between rows. In simulation the first row comes only at about 60 s, with the
  `Progress(-1)` v1.7.4 form carrying no distinct-state count (`-1`), as 01 already found.
- **`tlaup tlc --raw Spec | head`**: tlaup writes nothing to stdout itself in raw mode, so `head` closing the pipe reaches
  TLC, and the JVM ignores it; TLC runs to its end, unseen, with its exit code lost. What tlaup does about its own side
  is [11 R1/R2](../design/11-runner.md): it reads the child's pipe, so it gets the closed pipe when it writes to its own
  stdout (`BrokenPipeError`), ends with 141, and if it also ends the JVM at that point (terminate it, as for SIGTERM)
  the run stops instead of burning CPU for the rest of the model check. Today's R2 says nothing about a broken pipe
  reaching the JVM. The answer to R2's open sentence is therefore: the run **does** go on unless tlaup stops it, and the
  `--raw` help should say so; a design choice for the maintainer is whether a closed pipe in the runner should also stop
  the child (recommended: yes, same path as the first signal, because nobody can read the result). With `exec`-style
  replacement (tlaup replaced by java) there would be nothing to stop it; tlaup is not that, so it can. Stating this does
  not change a decision; it fills the "waiting on question 31" in 11 R1.
- A reader that wants to stop a run it started and then lost must have the pid: TLC's start line gives `[pid: N]`;
  `tlaup` knows it from `Popen` in any case.
- Setting TLC's interval: tlaup could pass `-Dtlc2.TLC.progressInterval=N` itself on rolling only (v1.7.4 ignores it),
  for example a shorter interval for the live view. Nothing in the design asks for it; it would be a new option and needs
  a check of the build before it is passed.

## Open follow-ups

- Windows: that the error flag is set there (the run behaved as on Linux; the flag itself was not probed). Java 11 on all OSes.
- Java 11 and 21: whether the descriptor reuse on a closed stdout/stderr differs; and a test where the JVM would open a file
  for writing on the freed descriptor.
- Whether a 2200-format message is printed at the end of a clean run with `-tool` (source says `printProgresStats(startTime,
  true)` at the end of `ModelChecker` when `TLCGlobals.tool` is set; the runs here all ended with a violation, which
  returns earlier). The golden files in 01 settle it for the parser.
- A liveness run, to see the extra progress message before the liveness check and how long a silent gap can be after it
  (liveness can take a long time with no progress).
- Many workers and a heavy `-checkpoint` run: whether checkpoint time delays the progress by more than the 0.05 s seen.

## Date checked

2026-11-18.
