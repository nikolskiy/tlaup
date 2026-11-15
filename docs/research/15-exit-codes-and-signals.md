# 15. TLC exit codes and signals

## Question

What exit codes does TLC return in each supported version (v1.7.4 and the current rolling build)? What does the JVM
return after SIGINT and SIGTERM? Does the JVM keep running after tlaup receives SIGTERM? Which codes are free for
tlaup's own setup error? Do the two analysis reports (06 section 3.4, 03 item M3), which stated this from reading,
agree with runs?

## Source

- Upstream table, `tlc2.output.EC.ExitStatus`, path `tlatools/org.lamport.tlatools/src/tlc2/output/EC.java`:
  - v1.7.4, commit `5a47802b5c391f59ecdd44117981f4ff8c0656ba` (release published 2024-08-05):
    <https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/output/EC.java>
  - rolling, commit `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c` (release published 2026-10-23, TLC "Version
    2026.11.15.002146"):
    <https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/output/EC.java>
- Jars tested: `gh release download` of `tla2tools.jar` from each tag. v1.7.4: 2,274,532 bytes, sha256
  `936a2620…0e050e88`, banner `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`. rolling: 4,510,884 bytes, sha256
  `7e53aa63…fb84f`, banner `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`. Java: OpenJDK 25.0.5 (`/usr/bin/java`),
  Linux 6.12, Python 3.13, typer 0.29.1.
- Local: `src/tlaup/tlc/runner.py`, `src/tlaup/cmd/tlc.py`, `.venv/lib/python3.13/site-packages/typer/core.py`.
- Everything captured is under `tests/fixtures/research/15-exit-codes/` (specs, scripts, outputs, matrices).

## Short answer

1. TLC's exit codes (same table in both versions): 0 success; 10 assumption false (also postcondition in rolling);
   11 deadlock; 12 safety (invariant) violation; 13 liveness or action-property violation; 14 `Assert` failure;
   75 evaluation failure (spec; also out of memory in practice); 76 invariant evaluation failure; 77 liveness
   formula evaluation failure; 150 SANY parse or semantic error; 151 config (`.cfg`) error; 152 and 153 are declared
   (`ERROR_STATESPACE_TOO_LARGE`, `ERROR_SYSTEM`) but nothing maps to them; 255 anything unclassified. TLC's launcher
   itself returns 1 for bad command-line usage (unknown flag, missing argument, bad number, `-help`, `-version`).
2. The two versions differ in one observed way: a missing `.cfg` file gives 255 in v1.7.4 and 151 in rolling. The
   rolling table also maps more config-parse codes and the postcondition codes to existing numbers.
3. Direct signals to the JVM (both versions, Java 25): SIGINT gives exit 130, SIGTERM gives 143, SIGHUP gives 129
   (rolling only, tried). TLC prints nothing at all on these signals (no summary, no "Finished").
4. tlaup does not forward SIGTERM: after SIGTERM to the tlaup process only, tlaup dies with the signal (`$?` 143) and
   the java child survives, reparented to PID 1, still burning CPU. Reproduced twice (normal and `--raw` mode).
   Confirms report 03 M3. SIGTERM to the whole process group works only because the group signal reaches java too.
5. Report 06 section 3.4 is wrong on Ctrl-C: tlaup exits 143 (not 241, not 130) after a single SIGINT to the tlaup
   process, because the JVM exits 143 after `process.terminate()` and tlaup passes it through.
6. Free for tlaup's own codes: 3 to 9, 15 to 63, 79 to 125 (see section (d) for what to avoid). Recommended: 2
   usage, 3 for "not set up / environment" (jar missing, no Java), clear of every code TLC returned.

## Confidence

Verified, with limits: all exit codes below come from runs on one machine (Linux, Java 25). Not run: Windows,
macOS, TTY (Rich Live) mode, a state-space-too-large case (152), a system error (153), SIGINT with a real
terminal. "Free" is verified only against what the two jars returned and the `ExitStatus` constants.

## Evidence

### (a) Upstream table

`EC.ExitStatus` (identical constants in both commits; v1.7.4 lines 302-323):

```
ERROR = 255, SUCCESS = 0
VIOLATION_ASSUMPTION = 10, VIOLATION_DEADLOCK = 11, VIOLATION_SAFETY = 12, VIOLATION_LIVENESS = 13, VIOLATION_ASSERT = 14
FAILURE_SPEC_EVAL = 75, FAILURE_SAFETY_EVAL = 76, FAILURE_LIVENESS_EVAL = 77
ERROR_SPEC_PARSE = 150, ERROR_CONFIG_PARSE = 151, ERROR_STATESPACE_TOO_LARGE = 152, ERROR_SYSTEM = 153
default (unmapped EC code) -> 255
```

`errorConstantToExitStatus` has no case for 152 or 153, so they are never returned by this function. Rolling adds
`TLC_POSTCONDITION_FALSE`, `TLC_POSTCONDITION_EVALUATION_ERROR`, `TLC_POSSIBLE_UNWITNESSED` (all to 10), the
`TLC_CONFIG_PROPERTY_ACTION_LEVEL*` codes and `CFG_*` parser codes (all to 151). That is why "no cfg file" is 151 in
rolling (`CFG_ERROR_READING_FILE`) and 255 in v1.7.4. The source TODO notes that classes of errors are not yet
allocated.

### (a) Runs

Command: `java -cp tla2tools.jar tlc2.TLC -metadir <tmp> <Spec>.tla`, `$?` recorded (`timeout` wrapper). Script
`tests/fixtures/research/15-exit-codes/run_matrix.sh`; results `matrix-v1.7.4.txt`, `matrix-rolling.txt`; first 3 kB
of each output in `outputs/`.

| Case (spec) | v1.7.4 | rolling | Notes |
|---|---|---|---|
| success (Ok) | 0 | 0 | |
| invariant violated (Inv) | 12 | 12 | |
| temporal property violated (Live) | 13 | 13 | |
| action property violated (Act) | 13 | 13 | |
| deadlock (Dead) | 11 | 11 | |
| `Assert` failure (Asrt) | 14 | 14 | |
| `ASSUME` false (Assum) | 10 | 10 | |
| SANY syntax error (Parse) | 150 | 150 | |
| SANY semantic error, unknown operator (Sem) | 150 | 150 | "Parsing or semantic analysis failed." |
| no `.cfg` for the spec (NoCfg) | 255 | 151 | "File not found." as ConfigFileException |
| `.cfg` names undefined SPECIFICATION (BadCfg) | 151 | 151 | |
| `.cfg` syntax error (CfgSyn) | 255 | 151 | |
| `-config nope.cfg` | 255 | 151 | |
| spec file does not exist | 255 | 151 | TLC looks for the cfg first |
| invariant evaluation error, `x \div 0` (Eval) | 75 | 75 | not 76: raised while computing initial states |
| error inside `Next` (NextEval, `1 \div x`) | 255 | 255 | unclassified EC, falls to default |
| unknown flag `-bogus` | 1 | 1 | prints usage |
| no arguments | 1 | 1 | "Missing input TLA+ module." |
| `-workers abc` | 1 | 1 | |
| `-help` | 1 | 1 | prints help |
| `-version` | 1 | 1 | not an option; "unrecognized option". See follow-ups |
| out of memory, `-Xmx64m`, 10^8-entry function in `Init` (Oom) | 75 | 75 | OOM is caught by TLC and reported as "Java heap space" |
| `-tool` mode (Ok, Inv, Parse) | 0, 12, 150 | same | tool mode does not change codes |

An earlier OOM attempt (`-Xmx24m` on the 10^8-state counter) did not fail within 120 s (TLC spills states to disk), so
it was replaced by the large-`Init` case above.

Side effects observed: the rolling build writes `<Spec>_TTrace_<n>.tla` and `.bin` files next to the spec after
an error trace (not in v1.7.4); TLC also extracts standard modules to `/tmp` (`Parsing file /tmp/Naturals.tla`).
The matrix script deletes the trace files.

### (b) Signals sent straight to the JVM

`signal_jvm.py` starts `java -cp tla2tools.jar tlc2.TLC ... Long.tla` (counter to 10^8, runs ~minutes), waits 8 s,
sends the signal to the java PID, reads the exit status from `Popen` (positive = the JVM called exit; negative = killed
by the signal).

| Version | SIGINT | SIGTERM | SIGHUP | SIGKILL |
|---|---|---|---|---|
| v1.7.4 | 130 | 143 | not run | not run |
| rolling | 130 | 143 | 129 | killed (-9) |

All exits took under one second. The last line of each output is the last `Progress(...)` line; TLC prints no
interruption message and no final statistics. Outputs: `outputs/sig_*.out.txt`. So the JVM does exit with 128+n, as
expected, via its own shutdown path, not a kernel kill.

### (c) Signals sent to tlaup

`signal_tlaup.py` starts `.venv/bin/tlaup tlc Long --cfg Long [--raw]` in its own session (so its process group is
private), with `XDG_CONFIG_HOME`/`XDG_CACHE_HOME` pointing at a scratch folder holding `tools install v1.7.4`. After
10 s it sends the signal and reports tlaup's `Popen` return code (negative = killed by that signal; the shell would
show 128+n), then whether the java child is still alive. stdout is a file, so this is the non-TTY path. Results:
`signal_tlaup_results.txt`.

| Signal sent to | tlaup exit | java child afterwards |
|---|---|---|
| SIGTERM, tlaup only | killed by SIGTERM (`$?` 143) | ALIVE, parent PID 1, CPU time 21 s then 26 s five seconds later; killed by hand |
| SIGTERM, tlaup only, `--raw` | killed by SIGTERM (143) | ALIVE, parent PID 1, CPU 17 s then 22 s; killed by hand |
| SIGINT, tlaup only | 143 | gone |
| SIGINT, tlaup only, `--raw` | 143 | gone |
| SIGINT twice, 0.3 s apart, tlaup only | 130 (silent, no traceback) | gone |
| SIGINT to the whole group (Ctrl-C-like) | 143, 130, 130 in three runs; `--raw` 143 | gone |
| SIGTERM to the whole group | killed by SIGTERM (143) | gone (java got SIGTERM too, exits 143) |

Reading the results against `runner.py`:

- No signal handler exists in `src/`, so SIGTERM uses Python's default action: immediate death with no cleanup, and
  `Popen`'s context manager does not run. The java child is not signalled. Its stdout pipe is now closed, but it
  keeps checking states (CPU time grew). This is the first run, not just a reading of the code.
- First SIGINT: `KeyboardInterrupt` is caught (`runner.py:209`/`:248`), `process.terminate()` sends SIGTERM, the JVM
  exits 143, and `process.returncode` (143) is returned and passed to `typer.Exit`. So a Ctrl-C ends with 143, which
  reads as "terminated", and the table in report 06 (-15 / 241) is wrong: Python sees 143, not -15, because the JVM
  handled the signal and exited itself.
- A second SIGINT during the drain loop is not handled in `runner.py`; it escapes to Typer, which converts
  `KeyboardInterrupt` into `Exit(130)` (`typer/core.py:346-347`, typer 0.29.1) with no message. Report 03 M3 expected
  an unhandled traceback; with this typer version it is a silent 130 instead. Python's default (re-raise SIGINT, `-2`)
  does not apply.
- With a real Ctrl-C the group gets SIGINT, so java exits 130 on its own and also gets SIGTERM from `terminate()`;
  which exit status wins is a race (143 once, 130 twice in non-raw runs, 143 in the raw run). Anything that relies on
  the code after Ctrl-C must set it itself.
- Left over: none. Java processes I started were PIDs 992870 and 1003163 (killed by hand) and the rest exited by
  themselves; `ps` confirmed none remained.

Not tested: a TTY (the Rich `Live` path), a signal while TLC is still in SANY parsing, SIGHUP to tlaup.

### (d) Free codes and conventions

Used by TLC: 0, 1 (launcher usage errors, `-help`, `-version`), 10-14, 75-77, 150, 151, 255 (observed); 152, 153
declared. Conventions to avoid:

- 1: used by TLC for usage errors, and by Python/Typer for generic failure.
- 2: shell and Click/Typer convention for usage errors (tlaup already gets 2 from Click).
- 126, 127: shell "cannot execute" and "command not found".
- 128+n (129 to 160): a shell reports a signal death this way (130 SIGINT, 137 SIGKILL, 143 SIGTERM), and the JVM
  uses it for its own signal exits. TLC's 150 and 151 sit inside this range (signals 22 and 23), so do not use
  anything from 129 up for tool codes.
- 64-78 (BSD sysexits): TLC uses 75-77, so avoid the whole block.
- 255: TLC's catch-all.

Free and safe: 3 to 9, 15 to 63, 79 to 125 (nothing in 126+ is safe). Suggested: 2 usage (from Click), 3 setup/environment error (no jar, no
Java, bad config), 4 and up for other tool-side domain errors (spec file not found, cfg not found by tlaup before
TLC runs). 130 for Ctrl-C and 143 for SIGTERM stay as signal codes.

## Implications for the roadmap

- Milestone 1, signal forwarding: the claim that the JVM survives SIGTERM to tlaup is now verified by run (twice).
  Fix needed: a SIGTERM handler in `run_tlc` that terminates the child, waits, and exits 143.
- "Exit 130 on Ctrl-C" is not what happens today: it is 143 (single Ctrl-C, parent only), a race between 130 and 143
  (group), and 130 for a second Ctrl-C via Typer. tlaup must choose and set 130 itself after an interrupt; do not pass
  the JVM's code through for that case.
- "Survive a second Ctrl-C while draining": currently a second Ctrl-C ends the process with 130 and no output;
  java is already told to stop by then, so nothing is orphaned in the runs here. Whether the loss of the final summary
  is acceptable is a design point.
- Milestone 1b/4: TLC's code space is 0, 10-14, 75-77, 150-151, 255 (plus 1 for TLC usage errors). Setup error: 3 is
  free. Passing TLC's code through unchanged is feasible. The tool should also map code to a name (the table above)
  and print/emit it, since 150 vs 151 vs 255 distinguish parse, config and "unclassified".
- tlaup should not rely on TLC codes for "no cfg": it is 255 on v1.7.4 and 151 on rolling, so a cfg check in tlaup
  before launching (already in `cmd/tlc.py`) gives a stable behaviour.
- Version portability: the code table is the same in both versions for the common cases; only the config-error
  classification widened in rolling.

## Open follow-ups

- Decide how `-version` should be run: `tlc -version` is not an option in either jar (exit 1, prints the banner on
  the first line), which `get_tlc_version` happens to rely on. Out of scope here, noted only.
- Run the same signal tests under a TTY (Rich Live) and on macOS/Windows, where SIGTERM and process groups differ.
- Find the upstream commit that changed the missing-cfg code from 255 to 151, if the maintainers want to say "since
  version X"; not searched.
- Cases not provoked: 152, 153, 77 (liveness formula evaluation failure), 76 via a level-too-high invariant.

## Date checked

2026-11-14.
