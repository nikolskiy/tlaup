# 35. Making the JVM end when tlaup ends

## Question

Can the JVM that tlaup starts be made to end when tlaup ends, however tlaup ends, SIGKILL included, on Linux, macOS and Windows; and how? For each way that works: does it still work with the user's own Java options, a `-metadir` of their own and `tlaup repl` (stdin is the terminal); does the signal or exit it gives TLC leave the last checkpoint usable for `-recover`, also when the JVM is stopped in the middle of writing one; what does it cost at start-up; does it fit the launcher's signal handling ([20 G3](../design/20-groundwork.md#g3-java-launcher)) and its rule that the child stays in tlaup's process group? Decides which of the four options [R6, Risks](../design/11-runner.md#r6-run-folders) lists for a killed tlaup is taken (the maintainer prefers option 4).

## Source

- Experiments on Linux x86-64, 12 cores, kernel 6.12, on 2026-11-18. Python 3.14.3 (uv's python-build-standalone build) for the harness and the stand-in parent; Java OpenJDK 25.0.5, OpenJDK 21.0.13 (agent warnings only) and Temurin 11.0.33+10; util-linux 2.41.5 (`setpriv`). Jars: v1.7.4 (`5a47802`, sha256 `936a2620...0e050e88`) and 1.8.0 (rolling) (`bc1b506`, sha256 `7e53aa63...fb84f`, CalVer 2026.11.15.002146).
- The machine was shared with other agents (load average 20 to 23 on 12 cores during the runs), so the local timings are rough; the CI timings below are from quiet runners.
- CI run: <https://github.com/nikolskiy/tlaup/actions/runs/44489200898> (branch `research/top-up-experiments`, commit `0d43a75`, 2026-11-19 08:37 to 08:48 UTC, conclusion success). Runner images: ubuntu-latest = ubuntu26 20261111.82.6 x86_64; macos-latest = macos26 20261112.0504.1 arm64; windows-latest = win25-vs2026 20261103.298.1 x86_64. Java on PATH: Temurin 21 (21.0.13+9 on ubuntu and macOS, 21.0.13.1+2 on Windows; the scripts print `21.0.13` and `21.0.13.1`); Python 3.13.17 and 3.13.18. The jars were the two of the brief, sha256 checked on the runner. Logs: `outputs/ci-{ubuntu,macos,windows}/q35-{kill,kill-xrs,repl,startup}.txt`.
- Upstream source read at the two commits: `tlc2/tool/ModelChecker.java` (`checkpoint()`), `tlc2/tool/queue/DiskStateQueue.java`, `tlc2/tool/TLCTrace.java`, `tlc2/tool/fp/DiskFPSet.java`, `tlc2/tool/fp/MultiFPSet.java`, `util/InternTable.java`, `tlc2/tool/CheckpointSettings.java` (rolling only), `tlc2/TLCGlobals.java`, for example <https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L759-L786> and <https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/tool/ModelChecker.java#L706-L727>.
- Everything that produced the results, and the captured results, is under `tests/fixtures/research/35-jvm-ends-with-tlaup/`:
  - `ci/` holds the scripts that also run on macOS and Windows: `parent.py` (stands in for tlaup's launcher and applies one mechanism), `watcher.py`, `common.py`, `check_kill.py`, `check_repl.py`, `check_startup.py`, and `java/Lifeline.java` (the experiment agent) and `java/Sleeper.java` (a JVM that sleeps and logs whether its shutdown hook ran).
  - `ckpt_kill.py`: the checkpoint experiment (Linux, jdb breakpoints).
  - `outputs/`: the captured results (paths replaced by `<tmp>`).

## Short answer

1. **Yes, on Linux, macOS and Windows, verified.** In the control case (nothing done) the JVM outlived a parent killed hard on all three systems, every time: on POSIX it was reparented to PID 1, on Windows it just ran on. With any of the ways below that applies to the system, it ended 0.0 to 1.6 s after its parent was killed. "Killed" means SIGKILL, SIGSEGV (a crash) or SIGTERM with no handler on Linux and macOS, and `TerminateProcess` on Windows. This held:
   - on both jars;
   - locally with Java 25 and Java 11, on the runners with Java 21;
   - with `-Xrs` among the user's options;
   - under `tlaup repl` on a terminal (Linux and macOS; the Windows ways do not touch stdin).

   The ways:
   - **Parent-death signal** (Linux only): `prctl(PR_SET_PDEATHSIG, SIGTERM)` in the child before `exec`, either from a `preexec_fn` (ctypes) or by starting `setpriv --pdeathsig TERM -- java ...`.
   - **A lifeline agent in the JVM**: a 70-line `-javaagent` whose daemon thread waits for tlaup to go and then calls `System.exit(143)`. It can wait for end of file on a pipe that only tlaup holds the write end of (POSIX), or on stdin; or it can poll `ProcessHandle.of(<tlaup pid>).isAlive()` (all three systems), or wait on `ProcessHandle.onExit()` (all three).
   - **A watcher process** (all three): a small second Python process that waits for tlaup's exit and then stops the JVM. It uses a pidfd on Linux, kqueue `NOTE_EXIT` on macOS and `WaitForMultipleObjects` on Windows.
   - **A Windows job object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`**: the JVM was gone in under 50 ms, a hard kill.

   **Recommended: the agent in PID mode.** It is the one way that works the same on all three systems and for every tool. On the quiet runners it adds 19 to 43 ms to a bare JVM's start and up to 33 ms to TLC's, and it ends the JVM within about a second of tlaup's death (0.1 to 1.4 s with TLC). The pipe variant reacts faster but costs about 0.35 s (Linux) to 1.7 s (macOS) at *every* JVM exit, so it is rejected.
2. **The candidates' caveats, as found.** The parent-death signal is tied to the *thread* that started the child: started from a thread that then ends, the JVM got SIGTERM at once while tlaup lived on, both through `preexec_fn` and through `setpriv` (with `setpriv` it is even a race, because `prctl` runs after `Popen` has returned). The stdin variant of the agent collides with `tlaup repl` (stdin is the terminal there); the pipe variant does not. uv's Python build has no `os.pidfd_open` or `signal.pidfd_send_signal`, so a Linux watcher needs the raw system calls through ctypes.
3. **What TLC gets makes no difference to its files.** Neither jar registers a shutdown hook (no `addShutdownHook` anywhere in either jar), so `System.exit` from the agent, a SIGTERM from the parent-death signal or the watcher, and a SIGKILL all stop TLC's threads wherever they are. The only difference seen is that an orderly exit runs `deleteOnExit` (TLC's copies of the standard modules in `java.io.tmpdir`) and a SIGKILL does not.
4. **A checkpoint is not safe against a stop at the wrong moment, whatever stops TLC.** This holds for every mechanism and equally for Ctrl-C and the SIGTERM tlaup already forwards. `checkpoint()` writes `.tmp` files, then commits them one by one, deleting old queue pool files and renaming. The JVM was stopped at chosen points with jdb breakpoints, and `-recover` was then run to the end on a spec whose state count is known (1,771,561 states for rolling, 16,777,216 for v1.7.4):
   - Stopped before anything was committed, or between checkpoints: the run recovers and finishes without missing states.
   - Stopped in the first checkpoint: there is nothing to recover.
   - Stopped after the queue's old pools were deleted, or between deleting `queue.chkpt` and renaming `queue.tmp`: `-recover` fails (exit 1 or 255).
   - Stopped after the queue was committed and before the rest was: `-recover` *succeeds with exit 0 and silently misses states*. Rolling found 1,534,282 of 1,771,561 states; v1.7.4 found 5,134,656 of 16,777,216.
   - A SIGTERM during a checkpoint was no safer than a SIGKILL: one such case lost its pool files.
   - Separately, every recovered run, even from a clean checkpoint, reports 0.1 to 1.7 % *more* distinct states than exist.
5. **Start-up cost is small, except for the pipe reader.** Medians on the quiet CI runners:
   - The agent in PID mode adds 19 ms (Linux), 25 ms (macOS) or 43 ms (Windows) to a bare JVM.
   - On TLC on a two-state spec it adds 22 ms (Linux), 33 ms (Windows) or nothing measurable (macOS, where the run with the agent was faster).
   - A thread blocked reading a pipe makes every JVM exit later: 375 ms against 39 ms on Linux, and 1,770 ms against 67 ms on macOS. That rules out the pipe and stdin variants.
   - `preexec_fn` makes `Popen` take 1.3 ms instead of 0.2 ms (fork instead of vfork), and `setpriv` adds 0.5 ms.
   - A watcher costs one more Python start: 13 ms on Linux, 30 ms on macOS, 49 ms on Windows, off the critical path.
   - A job object costs nothing measurable.

## Confidence

Verified for the main question: whether the JVM can be made to end and how, on all three systems. Linux was run locally (both jars, Java 25 and 11, a loaded machine) and on CI; macOS arm64 and Windows x86-64 ran on GitHub-hosted runners with Java 21 (all checks) and Java 11 (the kill check, second run). The checkpoint results are verified for the breakpoints chosen, on Linux with Java 25, with one spec and one run per scenario; they are TLC's own code and do not depend on the mechanism or the OS. Not settled: whether the over-count after `-recover` means states are explored twice or a wrong counter, and why a JVM with a thread blocked on a pipe exits late.

## Evidence

### How the experiments are built

`ci/parent.py` stands in for the launcher. It starts one `java` child with `Popen` from its main thread: stdin from the null device, stdout and stderr piped and drained by daemon threads, the same process group (G3). It applies one mechanism, prints `CHILD <pid>` and `READY`, and waits; after `--lifetime` seconds it stops the child itself. `check_kill.py` starts it in a session of its own, so that a kill reaches the parent alone, the way `kill -9 <tlaup pid>` would. Once the child has run for 1.5 s (3 s for TLC), it kills the parent and watches the child's PID for 8 s; on Linux a zombie counts as gone. The child is either `Sleeper` (its shutdown hook appends `hook` to a log, so an orderly exit is told apart from a hard kill) or TLC on a spec that runs for hours, with `-workers 1 -metadir <own folder>`. The agent writes `lifeline eof` or `lifeline parent-gone` to the same log before it calls `System.exit(143)`. Every child and watcher is killed by PID at the end.

Mechanisms as `parent.py` applies them:

| Name | What the parent does |
| --- | --- |
| `none` | nothing (the control) |
| `pdeathsig-preexec` | `preexec_fn` that calls `prctl(PR_SET_PDEATHSIG, SIGTERM)` through ctypes and exits 122 if `getppid()` is no longer the parent (the parent died before the call) |
| `pdeathsig-setpriv` | argv prefixed with `setpriv --pdeathsig TERM --` |
| `*-thread` | the same, but `Popen` runs on a thread that lingers 0.5 s and ends while the parent lives on |
| `agent-pipe` | `os.pipe()`; the read end goes to the child with `pass_fds`, the parent keeps the write end; `-javaagent:lifeline.jar=pipe=/dev/fd/<n>` |
| `agent-stdin` | `stdin=PIPE`, the parent keeps it open; `-javaagent:lifeline.jar=stdin` |
| `agent-pid` | `-javaagent:lifeline.jar=pid=<parent pid>,interval=500` (polls `ProcessHandle.of(pid).isAlive()`) |
| `agent-onexit` | `-javaagent:lifeline.jar=onexit=<parent pid>` (`ProcessHandle.onExit().join()`) |
| `watcher` | after `Popen`, starts `python -I watcher.py <parent pid> <child pid>`, which ignores SIGINT and SIGHUP, waits for either process to end, and if the parent went first sends SIGTERM to the child (SIGKILL after 10 s) |
| `job` (Windows) | `CreateJobObjectW`, `SetInformationJobObject` with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, `AssignProcessToJobObject` after `Popen`; the handle is not inheritable |

The agent is placed right after `java`, before the options that stand for the user's own. It is compiled with `javac --release 11` and printed no warning on Java 11, 21 or 25.

### Linux: the parent killed hard

Command: `python q35/check_kill.py --child sleeper` (all kills), `--child sleeper --kills KILL --xrs`, `--child tlc174,tlcrolling --kills KILL`, and the same three children under Java 11 (`Q35_JAVA=<tmp>/jdk11/...`). Full output: `outputs/kill-sleeper-j25.txt`, `outputs/kill-tlc.txt`. Seconds from the kill until the child was gone; "survived" means still running 8 s later, its parent now PID 1:

| Mechanism | Sleeper, Java 25: KILL / SEGV / TERM | Sleeper `-Xrs`, KILL | TLC v1.7.4, Java 25 / 11 | TLC rolling, Java 25 / 11 | Sleeper, Java 11 |
| --- | --- | --- | --- | --- | --- |
| none (control) | survived / survived / survived | survived | survived / survived | survived / survived | survived |
| pdeathsig-preexec | 0.10 / 0.10 / 0.10, hook ran | 0.00, no hook | 0.31 / 0.10 | 0.05 / 0.40 | 0.05 |
| pdeathsig-setpriv | 0.05 / 0.10 / 0.10, hook ran | 0.00, no hook | 0.36 / 0.41 | 0.05 / 0.15 | 0.05 |
| either, `-thread` | **ended before the kill**, exit 143 (-15 with `-Xrs`) | same | same | same | same |
| agent-pipe | 0.10 / 0.15 / 0.15 | 0.11, hook ran | 0.36 / 0.35 | 0.36 / 0.05 | 0.05 |
| agent-stdin | 0.05 / 0.10 / 0.10 | 0.15 | 0.37 / 0.36 | 0.35 / 0.25 | 0.05 |
| agent-pid (500 ms) | 0.34 / 0.46 / 0.37 | 0.21 | 0.84 / 0.87 | 0.51 / 0.35 | 0.46 |
| agent-onexit | 0.33 / 0.21 / 0.41 | 0.41 | 0.61 / 0.87 | 0.31 / 0.30 | 0.16 |
| watcher (pidfd) | 0.20 / 0.15 / 0.10 | 0.05, no hook | 0.36 / 0.41 | 0.05 / 0.41 | 0.05 |

- KILL is `kill -9` of tlaup. SEGV is a crashed Python. TERM is a SIGTERM that meets Python's default action, standing for a Python with no handler yet (the design installs handlers in `signals_held`, and then SIGTERM is forwarded as G3 says).
- With `-Xrs` (a user option that stops the JVM handling SIGTERM itself) the parent-death signal and the watcher's SIGTERM kill the JVM by the default action, with no shutdown hooks; it still ends. The agent is not affected, since it calls `System.exit`.
- The `-thread` rows show the thread caveat. The kernel sends the parent-death signal when the thread that forked the child ends, even when another thread of the same process takes it over. Through `setpriv`, `prctl` runs only after `setpriv` has been exec'd, which is after `Popen` has returned. A thread that ends within those few milliseconds leaves the JVM with no signal at all (the first, unlingering run of the experiment: the child survived the thread and died only with the process).
- `ProcessHandle.onExit()` on a process that is not a child polls with a growing interval (300 ms, then 30 ms more each time, capped at 5 s, in `ProcessHandleImpl`), so after a long run it can take up to 5 s. The fixed 500 ms poll of `agent-pid` does not grow.
- uv's Python 3.14.3 has neither `os.pidfd_open` nor `signal.pidfd_send_signal` (`hasattr` is false for both), so `watcher.py` falls back to `syscall(434)` and `syscall(424)` through ctypes; every watcher line above says "pidfd via ctypes syscall".

### Linux: `tlaup repl`

`python q35/check_repl.py`: the script holds a pseudo-terminal (standing for the user's terminal, which outlives tlaup). `parent.py --passthrough` starts `java tlc2.REPL` (rolling) on it. The script types `1+1`, expects `2`, then kills the parent with SIGKILL (`outputs/repl.txt`):

| Mechanism | REPL answered | After the parent was killed |
| --- | --- | --- |
| none | yes | still running after 8 s |
| pdeathsig-preexec | yes | ended 0.10 s |
| pdeathsig-setpriv | yes | ended 0.05 s |
| agent-pipe | yes | ended 0.15 s |
| agent-pid | yes | ended 0.58 s |
| agent-stdin | **no** | ended 0.05 s |
| watcher | yes | ended 0.10 s |

`agent-stdin` cannot be used when stdin is the terminal: the child's stdin must then be the pipe, so the REPL never sees what is typed. The pipe on a separate descriptor and the PID poll leave stdin alone.

### What a stopped TLC leaves: checkpoints

Source. `ModelChecker.checkpoint()` calls `beginChkpt` on the queue, the trace, the fingerprint set, the intern table, the liveness checker and (rolling only) the settings. Each writes a `.tmp` file: `queue.tmp`, `<Spec>-<w>.tmp`, `vars.tmp`, `settings.tmp.chkpt`. Then the workers resume and `commitChkpt` runs in the same order:

- `DiskStateQueue.commitChkpt` first deletes the pool files the old checkpoint still refers to, then deletes `queue.chkpt`, then renames `queue.tmp` to it.
- The others delete their old `.chkpt` and rename.
- The fingerprint set has no checkpoint file of its own: `DiskFPSet` notes that it is rebuilt from the trace on recovery.

Nothing makes the set of renames atomic, and no shutdown hook exists in either jar (`grep -rl addShutdownHook` over the unpacked jars: no hits).

The checkpoint interval was set with `-Dtlc2.TLCGlobals.chkpt=1000` (milliseconds; both jars read it, and a value other than the default also counts as "explicitly enabled"). Checkpoints are taken at the periodic-work interval, which rolling lets be set with `-Dtlc2.TLC.progressInterval=2` (seconds) and which v1.7.4 runs whenever its `doPeriodicWork` comes round. In passing: the default interval is `30 * 60 * 1000 + 42` ms, so both jars write a checkpoint every 30 minutes without `-checkpoint` (question 25).

`ckpt_kill.py` starts TLC with a JDWP agent on 127.0.0.1. It waits for the needed number of `Checkpointing completed` lines and attaches `jdb`. It sets a line breakpoint in `ModelChecker.checkpoint()` or `DiskStateQueue.commitChkpt()` (line numbers read from each jar's `LineNumberTable`), waits for `Breakpoint hit` (all threads suspended) and lists the folder. Then it kills the JVM: SIGKILL, or SIGTERM followed by `resume`. Last it runs `java -Dtlc2.TLCGlobals.chkpt=0 -cp <jar> tlc2.TLC -deadlock -workers 2 -recover <folder> Wide.tla` to the end.

The spec is `Wide`: `f \in [1..6 -> 0..B]`, each step increments one entry, `-deadlock`. It has `(B+1)^6` states, so a run that finishes with that count explored everything. Without a kill, rolling with B = 10 gave `1771561 distinct states found` three times, with and without checkpoints. v1.7.4 used B = 15: one run without a kill gave `16777216 distinct states found`. Java 25, `-workers 2`. Outputs: `outputs/checkpoint-*.jsonl`.

| Stopped at | rolling: -recover gives | v1.7.4: -recover gives |
| --- | --- | --- |
| first checkpoint, all `.tmp` written (`first-begun`) | exit 255, `vars.chkpt (No such file or directory)` | same |
| first checkpoint, queue committed (`first-queue-committed`) | exit 255, no `vars.chkpt`; the folder has a `queue.chkpt` | same |
| a later checkpoint, `queue.tmp` written, the rest not begun (`later-begin-mid`) | exit 0, 1,773,203 | not run |
| a later checkpoint, all `.tmp` written, nothing committed (`later-begun`) | exit 0, 1,773,969 | exit 0, 16,783,091 |
| the old pools deleted, `queue.chkpt` still old (`later-pools-deleted`) | exit 1, `when reading pool file 12 ... No such file or directory` | exit 1, the same for pool 13 |
| `queue.chkpt` deleted, `queue.tmp` not yet renamed (`later-chkpt-deleted`) | exit 255, `queue.chkpt (No such file or directory)` | same |
| queue committed, trace, intern table and settings not (`later-queue-committed`) | **exit 0, 1,534,282: states missed** | **exit 0, 5,134,656: states missed** |
| all but the intern table committed (`later-fp-committed`) | exit 0, 1,814,374 | exit 0, 16,853,320 |
| 0.3 s after a checkpoint completed (`between`) | exit 0, 1,789,607 | exit 0, 16,801,911 |
| the same with SIGTERM (`between-TERM`) | exit 0, 1,777,107 | not run |
| all `.tmp` written, then SIGTERM and resume (`later-begun-TERM`) | exit 1, pool file 20 missing | exit 1, pool file 17 missing |
| queue committed, then SIGTERM and resume (`later-queue-committed-TERM`) | exit 0, 1,775,702 | not run |

With `-workers 1` (rolling) the `between` and `later-begun` cases also over-counted (1,773,118 and 1,778,012; `outputs/checkpoint-rolling-w1.txt`). Reading the table:

- Every recovery that did not fail over-counts, even from a checkpoint whose write had completed. An over-count leaves the verdict sound if it comes from states explored twice; an under-count does not. That is the `later-queue-committed` row: TLC said "no error" with 13 % (rolling) and 69 % (v1.7.4) of the states unexplored.
- SIGTERM is not safer than SIGKILL. The JVM's shutdown sequence lets the checkpointing thread run on until the halt, so with SIGTERM the moment the files stop changing is a race (`later-begun-TERM` lost its pools; with SIGKILL the same point recovered).
- The windows that break a checkpoint are the commit's deletions and renames. Each rename is short, but deleting the old pools is one file per pool (up to hundreds on a large run).
- Whether a folder "holds a checkpoint" cannot be told from the names R6 uses ("something under the folder is named `*.chkpt`"). After a stop in the first checkpoint, rolling leaves `settings.tmp.chkpt`, which matches `*.chkpt`, and the `first-queue-committed` state has a real `queue.chkpt`. Neither can be recovered. A finished checkpoint leaves no `.tmp` files (listings during and between checkpoints); a stopped one leaves `queue.tmp`, `vars.tmp`, `<Spec>-<w>.tmp`, `settings.tmp.chkpt` or a mix.

None of this depends on the mechanism: the agent's `System.exit` and the parent-death SIGTERM stop TLC exactly as the SIGTERM tlaup forwards on Ctrl-C does, and the job object or a watcher's SIGKILL as a SIGKILL does.

### macOS and Windows (CI run)

The same scripts ran on the three runners (run and images under Source). The commands:
- `python q35/check_kill.py`
- `python q35/check_kill.py --child sleeper --xrs`
- `python q35/check_repl.py`
- `python q35/check_startup.py`

Logs are in `outputs/ci-*/`. The ubuntu runner repeated the local Linux results with Java 21: every mechanism ended the child, the controls survived and the `-thread` cases ended before the kill. There, unlike in uv's build, the watcher found `os.pidfd_open` in the runner's Python. The ubuntu REPL rows match the local table.

Seconds from the kill until the child was gone; "survived" means still running 8 s later. On macOS the kill is SIGKILL, SIGSEGV or SIGTERM; on Windows it is `TerminateProcess` (`Popen.kill()`), after which the parent's exit code is 1.

| Mechanism | macOS Sleeper KILL / SEGV / TERM | macOS `-Xrs` | macOS TLC v1.7.4 / rolling | Windows Sleeper | Windows `-Xrs` | Windows TLC v1.7.4 / rolling |
| --- | --- | --- | --- | --- | --- | --- |
| none (control) | survived ×3, parent now PID 1 | survived | survived / survived | survived | survived | survived / survived |
| agent-pipe | 0.13 / 0.03 / 0.10, hook ran | 0.06 | 1.18 / 0.01 | n/a | n/a | n/a |
| agent-stdin | 0.09 / 0.06 / 0.11 | 0.20 | 1.16 / 0.20 | 0.05, hook ran | 0.05 | 0.35 / 0.05 |
| agent-pid | 0.22 / 0.23 / 0.28 | 0.30 | 1.36 / 0.61 | 0.15, hook ran | 0.15 | 0.45 / 0.20 |
| agent-onexit | 0.18 / 0.17 / 0.14 | 0.19 | 1.45 / 0.26 | 0.05 | 0.05 | 0.35 / 0.05 |
| watcher | 0.06 / 0.09 / 0.09 (kqueue, SIGTERM, hook ran) | 0.01, no hook | 0.80 / 0.06 | 0.05 (`TerminateProcess`, no hook) | 0.00 | 0.05 / 0.05 |
| job, kill on close | n/a | n/a | n/a | 0.00, no hook | 0.00 | 0.00 / 0.00 |

**Java 11, second CI run.** The run: <https://github.com/nikolskiy/tlaup/actions/runs/44491714376> (commit `8647da2`, 2026-11-19 UTC). Images: macos26 20261102.0473.1 arm64 and win25-vs2026 20261103.298.1. Java: Temurin 11.0.33+10 through `Q35_JAVA`. Command: `check_kill.py --child sleeper,tlcrolling --kills KILL` (`TERMINATE` on Windows). Logs: `outputs/ci2-{macos,windows}/q35-kill-java11.txt`.

The same picture as with Java 21: the control survived on both systems, and every mechanism ended the child.

| Mechanism | macOS: Sleeper / TLC rolling | Windows: Sleeper / TLC rolling |
| --- | --- | --- |
| agent-pipe | 0.00 / 0.08 | n/a |
| agent-stdin | 0.00 / 0.14 | 0.05 / 0.05 |
| agent-pid | 0.61 / 0.38 | 0.20 / 0.25 |
| agent-onexit | 0.10 / 0.24 | 0.05 / 0.05 |
| watcher | 0.01 / 0.07 | 0.05 / 0.00 |
| job | n/a | 0.00 / 0.00 |

**The `/usr/bin/java` stub on macOS keeps the process id** (question 28, its second run): the PID `Popen` returns is the PID of the JVM. A watcher, or the launcher's own signals, therefore reach the JVM, and not a stub that would have been left behind. The agent in PID mode watches tlaup's PID, not the JVM's, so it is not affected either way.

- On macOS the agent's `/dev/fd/<n>` opening of an inherited pipe works.
- On Windows, `ProcessHandle.of(pid)` from the agent sees a process that is not its parent's child go away. The job object kills at once and with no shutdown hooks, as `TerminateProcess` does.
- The slower v1.7.4 times on macOS are the time TLC v1.7.4 takes to exit there; the agent had noticed sooner. Every mechanism shows them, the watcher too.

`tlaup repl` on macOS, through a pseudo-terminal, `1+1` typed, then SIGKILL of the parent:

| Mechanism | REPL answered | After the kill |
| --- | --- | --- |
| none | yes | still running after 8 s |
| agent-pipe | yes | ended 1.55 s |
| agent-pid | yes | ended 1.62 s |
| agent-stdin | **no** | ended 0.00 s |
| watcher | yes | ended 1.55 s |

The REPL takes about 1.5 s to exit on macOS whatever stops it; the watcher's SIGTERM takes as long as the agent's `System.exit`. Windows prints "skipped": its mechanisms do not touch stdin, and a console REPL was not driven there.

### Start-up cost

Local, `python q35/check_startup.py --runs 15` (`outputs/startup.txt`), medians, load average about 22:

| Measured | ms |
| --- | --- |
| JVM that starts and exits (Sleeper 0 s), plain | 228 (another run 183, a third 283) |
| the same with the agent, PID mode | 399 (367, 329) |
| the same with the agent, pipe mode | 653 (609, 506) |
| TLC on a two-state spec, plain | 2287 (another run 1975, 1418) |
| the same with the agent, PID mode | 2223 (1493, 1722) |
| `Popen` of `true`, plain | 0.7 |
| `Popen` with the pdeathsig `preexec_fn` | 7.1 |
| `true` run to the end, plain / through `setpriv --pdeathsig TERM --` | 4.7 / 6.9 |
| a watcher process's own start (Python `-I`) | 68 |

CI runners, `python q35/check_startup.py` (9 runs, TLC 4), medians in ms, Java 21:

| Measured | ubuntu | macOS | Windows |
| --- | --- | --- | --- |
| JVM that starts and exits, plain | 38.6 | 67.3 | 97.5 |
| the same with the agent, PID mode | 57.2 | 92.8 | 140.1 |
| the same with the agent, pipe mode | 375.5 | 1769.6 | n/a |
| TLC on a two-state spec, plain | 427.5 | 587.9 | 1236.0 |
| the same with the agent, PID mode | 449.9 | 537.1 | 1269.2 |
| `Popen` plain / with the pdeathsig `preexec_fn` | 0.2 / 1.3 | 3.2 / n/a | 1.6 / n/a |
| `true` plain / through `setpriv` | 0.4 / 0.9 | n/a | n/a |
| a watcher process's own start | 13.2 | 30.0 | 48.6 |
| `Popen` and wait, plain / plus creating and assigning a job | n/a | n/a | 26.6 / 27.0 |

- The PID mode costs 19 to 43 ms on a bare JVM and at most 33 ms on TLC; on macOS TLC was faster with it, which is noise.
- A pipe reader makes every JVM exit later: by 0.34 s on Linux and 1.7 s on macOS. The JVM evidently waits at exit while a thread is blocked in a native read of a pipe. The cause was not looked into; the cost alone rules the pipe and stdin variants out.

### What each kind of end looks like

- SIGKILL of tlaup, a crash (SIGSEGV, `os.abort`), and SIGTERM or SIGHUP before `signals_held` is entered: tlaup runs no code, and the mechanisms above are the only thing that reaches the JVM. Verified for KILL, SEGV and TERM on Linux and macOS, and for `TerminateProcess` on Windows (Task Manager's "End task" on the Python process is the same call).
- SIGTERM, SIGINT and SIGHUP while `signals_held` is held: G3 forwards them; the mechanism does nothing extra. When tlaup exits normally after the JVM, the pipe closes, the PID goes and the watcher sees the child gone first; the JVM has already ended.
- Closing the terminal sends SIGHUP to the foreground process group, which reaches the JVM itself (research 15: it exits 129), so it needs no mechanism. `kill -9 -<pgid>` kills the JVM directly. Both follow from the process-group rule and need nothing new.
- `nohup tlaup ...` then SIGKILL: SIGHUP is ignored, and the mechanisms still end the JVM when tlaup dies.
- Not tried on Windows: a console-script launcher (`tlaup.exe` from pip or uv) may itself start `python.exe` in a kill-on-close job. The JVM would then inherit the job and die with the launcher. That would not cover a kill of `python.exe` itself, which is what the CI did, and the agent covers both.

## Implications for the roadmap

**R6 option 4 is supported on all three systems.** It needs one change to its wording: "as soon as" becomes "within about two seconds" (the JVM's own exit time included: up to 1.6 s was seen on macOS).

- **Recommended mechanism: the lifeline agent in PID mode, the same on Linux, macOS and Windows.**
  - tlaup ships a small prebuilt `lifeline.jar` (compiled with `--release 11`, a few kilobytes) as package data. The launcher adds `-javaagent:<that jar>=pid=<tlaup's pid>` to every JVM it starts.
  - One mechanism for every OS and every tool (TLC, SANY, pcal, the REPL).
  - It does not touch stdin, file descriptors or the process group.
  - It survived `-Xrs` on all three systems, and a `-javaagent` or `-metadir` of the user's does not touch it.
  - It gives TLC the same orderly exit as the SIGTERM tlaup already forwards.
  - It closes the start-up race itself: if tlaup is already gone when the agent starts, `ProcessHandle.of` finds nothing and the JVM exits at once. `ProcessHandle.isAlive` compares start times, so a reused PID is not mistaken for tlaup.
  - Cost: 19 to 43 ms at start on the runners, plus a poll every 500 ms. The poll interval is the delay; it can be made shorter.
  - The jar has to be built in the release workflow (a JDK is already there for the integration tests) or committed as a binary; it cannot be compiled on the user's machine, which may have only a JRE.
- **Possible additions, not needed by the results:**
  - the kill-on-close job on Windows, which ends the JVM at once even if the agent were somehow disabled;
  - `setpriv --pdeathsig` on Linux where present (util-linux 2.33 or later, not BusyBox).

  Each adds a second code path per OS for what the agent already does. I would not add them.
- **Rejected for the launcher:**
  - the pipe and stdin variants: they slow every JVM exit (0.34 s on Linux, 1.7 s on macOS), and stdin collides with `tlaup repl`;
  - `preexec_fn`: it runs Python code between `fork` and `exec` in a process that may already have threads, gives up `vfork`, and exists on Linux only;
  - `onExit()`: up to 5 s of delay after a long run;
  - a watcher process: a second process to start and keep alive, and on Linux its pidfd calls are missing from uv's Python build.
- **What changes in R6.**
  - The first Risks bullet changes from "leaves its JVM running and its lock free" to "the JVM ends within about two seconds, and the lock is free".
  - That closes K1-3 and K1-5, except for those seconds. Either a `-recover` or `cache clean` that finds a free lock on an unsettled folder whose `run.json` `pid` is gone waits that long, or the window is accepted and named.
  - Options 2 and 3 (questions 33 and 34) are no longer needed for this risk.
  - D49's resumable unsettled folder holds. But "holds a checkpoint" must not be "something is named `*.chkpt`": rolling's `settings.tmp.chkpt` matches it with nothing to recover. A tighter test is "`queue.chkpt` and `vars.chkpt` exist". A `*.tmp` file (or `settings.tmp.chkpt`) beside them means TLC was stopped during a checkpoint; such a checkpoint may fail to recover, or recover and miss states.
  - The resume note could then say so ("TLC was stopped while writing a checkpoint; resuming may not explore every state") or not offer resuming at all. That choice is the maintainer's. It applies to every stop, Ctrl-C included, not only to a kill.
- **What changes in G3.**
  - `JavaInvocation` (or the launcher's `spawn`) gains the lifeline option, placed before the user's JVM options.
  - `--show-command` must leave it out. A pasted command would carry the PID of a tlaup that has gone, and its JVM would exit at once.
  - The process-group rule and the signal table are unchanged. The "Rejected" entry "Putting the child in its own process group" gains a sentence: the lifeline does not make a separate group safe, because the terminal's SIGINT, SIGHUP and SIGQUIT must still reach the JVM.
  - The Windows risk sentence ("there is no SIGTERM or SIGHUP to receive") is unchanged; the agent covers the hard kill there as well.
  - Exit code 143 from the agent is never seen by anyone.
- **What changes in the specs.**
  - `RunFolders`: its `Kill` action can end the process's TLC too, in the same step or in a following step that is bound to come, to model the window. `NoDeleteUnderOrphanTLC` and `OneTLCPerFolderAfterKill` should then hold without their exceptions (the `orphan-delete` and `orphan-recover` configs flip from "fails" to "holds"), or hold up to that step.
  - `Signals`: it leaves SIGKILL out. Nothing in it changes, but `ChildNeverOrphaned` could be stated for SIGKILL as well, since the lifeline now covers it. Its "Leaves out" list should name the lifeline.
- **The tests** (R6 and G3): an integration scenario on each CI OS, tlaup killed hard during a run and "no `java` process is left" within a few seconds. `check_kill.py` is the shape of that test.
- **Outside question 35, worth an upstream report (read only, nothing filed):**
  - TLC's checkpoint commit is not crash-safe. A stop between `DiskStateQueue.commitChkpt` and the trace commit gives a `-recover` that exits 0 having missed states.
  - `-recover` over-counts distinct states even from a clean checkpoint.
  - Both jars, Linux, Java 25.

## Open follow-ups

Nothing here needs a second CI run for the decision.

- Whether the over-count after `-recover` is double exploration or a wrong counter. Compare generated-state counts against a run that never stopped, or check the fingerprint set after recovery.
- The under-count was seen once per jar at one breakpoint. How often a real stop lands in that window on a large run (many pools to delete) was not measured.
- Why a JVM with a thread blocked reading a pipe exits late (0.34 s Linux, 1.7 s macOS). It does not matter once the pipe is rejected.
- Java 11 on macOS and Windows: done in the second CI run (above), kill check only. Start-up cost and the REPL with Java 11 on those systems were not run; nothing points to a difference.
- The Windows console-script launcher's own job object (above).
- Liveness checking (`liveCheck.beginChkpt` and `commitChkpt`) adds one more file to the commit; no spec with liveness was run.

## Date checked

2026-11-18 (local); CI run 2026-11-19 UTC.
