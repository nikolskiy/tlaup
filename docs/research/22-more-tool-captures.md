# 22: More real tool captures (TLC `-tool` shapes that passthrough reaches, and stdout apart from stderr)

## Question

Roadmap, investigation list, question 22: real `-tool` output, for each supported version, for the cases question 1 lists as not run and that passthrough after `--` now makes reachable: `-difftrace` on a violation and on a liveness counterexample; a checkpoint written with a short `-checkpoint` interval, and `-recover` from it; a violation found in `-simulate` and in `-generate` mode; a trace under an `ALIAS`; a trace whose action has parameters or is a sub-action of `Next`; a deadlock with `-deadlock` given. Also stdout and stderr captured separately for the 20 cases of question 1 and for the SANY and PlusCal cases of question 12 (to see what is written to stderr, in particular the one stderr line v1.7.4 writes for a missing module). Also: `-tool` output for a false `ASSUME`, an evaluation error, an action-property violation and a cfg error; a `-dfid` run and a `-generate` run; the PlusCal "changed since last translation" case on its own, and SANY `-help`, each as a single-command capture; TLC's exit code for a spec whose only SANY message is a warning (4802); whether SANY accepts grouped single-letter flags such as `-dl`; SANY level errors on v1.7.4; the SANY warning block and the `!! WARNING` line each as a capture of its own. Where a flag does not exist on v1.7.4, record that. It feeds [10 P5](../design/10-parser.md#p5-error-traces), [10 P8](../design/10-parser.md#p8-sany-output), [01 T3](../design/01-testing.md#t3-golden-files) and [21 S1, S5](../design/21-other-tools.md#s1-sany).

## Source

- Jars (already downloaded, not downloaded again): v1.7.4, sha256 `936a262061c9...` (`TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`), and `rolling`/v1.8.0, byte-identical, sha256 `7e53aa636dac...` (`TLC2 Version 2026.11.15.002146 (rev: bc1b506)`; "1.8.0" below). Commits 5a47802b5c391f59ecdd44117981f4ff8c0656ba and bc1b506bdcad80bb518bf3776a9161c34ff0fc4c.
- Java: OpenJDK 25.0.5 (Linux x86-64, 12 cores) for every run. Not run on Java 21 or 11 (none of the findings looks Java-dependent; the question did not ask).
- Everything below is read from captured files. Fixtures: `tests/fixtures/research/22-more-tool-captures/` with `v1.7.4/` and `v1.8.0/` (named like research 12; research 1 used `1.7.4/`), `specs/` (new specs), `run.py` (the driver that produced every file), `verify_difftrace.py` and `verify-difftrace.txt`. Per version: 164 cases, each `<case>.out` (stdout) and `<case>.err` (stderr, an empty file when nothing was written), `commands.txt` (case, command, exit code), `README.md` (the same as a table with the bytes of each stream and the files a run left next to the spec), `inputs/` (generated stale PlusCal modules). Paths are `<tmp>` and `<repo>`; `/tmp/Naturals.tla` and `/tmp/tlc-<n>/` are TLC's own extraction folder.
- Each case ran in its own fresh copy of the spec folder; `-metadir` was under the scratch folder. The 20 cases of question 1 and 60 of question 12 reuse those specs and commands (`q01-*`, `q12-*`); `tool-*` reuse the specs of research 15.
- Dates: run on 2026-11-18 (local time, Hawaii; the last cases finished after midnight UTC). Other agents were running on the machine at the same time; no timing is claimed.

## Short answer

All asked cases were captured on both builds, with the two streams apart, except where a flag does not exist (listed). Main findings, each a fact in the files:

1. **TLC writes nothing to stderr in `-tool` mode.** All 40 runs of the 20 question 1 cases and every new TLC case have an empty stderr file, with one exception: v1.7.4 with a missing module (`tool-missing-module`) writes one line, `File does not exist: <path>/NoSuchModule.tla while looking in these directories: jar:file:...!/tla2sany/StandardModules/`. That is the `File does not exist` line, not the diagnostic: the abort block with `Cannot find source file for module NoSuchModule imported in module MissMod.` is on stdout, inside the 2220/2219 window, on both builds. Exit codes of the 20 cases are the same as in research 1.
2. **SANY alone** writes everything to stdout except the same `File does not exist` line on stderr (v1.7.4: for a missing module and for a missing file; 1.8.0: for a missing file only, not for a missing module). `XMLExporter` writes its parse errors and stack traces to stderr, and `tlc2.REPL` on 1.8.0 writes the jline warning to stderr. `pcal.trans` never writes to stderr.
3. **`-difftrace`**: the first state is complete, later states list only the variables that changed (a one-variable spec prints the variable every time, so there the option is invisible). Rebuilding each state by carrying every missing variable forward from the previous state gives exactly the trace of the same run without `-difftrace` (10 of 10 pairs, both builds, `verify-difftrace.txt`). In a model-checking run the last state of a trace is printed in full anyway; in `-simulate` and `-generate` it is not. Headers, `Back to state`, `Stuttering` and the codes are unchanged.
4. **Action headers.** Both builds print the name of the operator that holds the action (a sub-action of `Next` such as `Pick`, `Step`, `Viaz`, not `Next`); an action reached through `INSTANCE` is named by the outer operator and module. **1.8.0 adds the arguments to the name** (`<Step(1) line 6, col 12 to line 6, col 52 of module Params>`, `Step(2)`); 1.7.4 prints `Step`. In `-simulate` and `-generate` on 1.8.0 the first state header carries a location (`<Init line 4, col 9 to line 6, col 16 of module Violation>`); in 1.7.4 it is `<Initial predicate>` in all modes.
5. **`-dfid` traces are a different shape**: the state messages are code **2216** on 1.7.4 (2217 on 1.8.0) and the header has no angle brackets and no action: `1:` (1.7.4) or `1: ` with a trailing space (1.8.0). The other `-dfid` messages differ too (2271 start, 2205 level, 2206 `Progress(-1)`, 2204 end instead of 2199, 2208). With `-dfid` 2 (the start depth) or 5, TLC stopped without finding a violation that exists (exit 0); with 10 or 20 it found it or finished.
6. **`ALIAS` does not exist on v1.7.4** (`ALIAS` in the cfg is read as an invariant name; message 2229, exit 151). On 1.8.0 the trace shows the alias record's fields as the variables (`x`, `sum`, `label`); `-difftrace` works on those fields.
7. **`-generate` does not exist on v1.7.4** (`Error: unrecognized option: -generate`, 1102, exit 1). On 1.8.0 it is a hidden option (absent from `-help`): `Running Random Simulation ...` (2188), then violation (exit 12), deadlock (11); `-generate` on a spec with no error never stops (killed at 120 s by the driver); `-generate num=3` finished with exit 0. `-simulate` violations and deadlocks give the usual 2110/2114 and trace, exit 12/11/13. `-generateSpecTE` exists on both builds and is accepted by 1.8.0 (prints a new message 2501 with the path of `<Spec>_TTrace_<n>.tla`); `-noGenerateSpecTE` exists only on 1.8.0.
8. **Checkpoint and recover** work in `-tool` mode with new messages 2195 (`Checkpointing of run <folder>`), 2196 (`Checkpointing completed at (...)`), 2197 (`Starting recovery from checkpoint <folder>/`), 2198 (`Recovery completed. N states examined. M states on queue.`); the shortest interval is 1 minute (`-checkpoint 0` did not checkpoint in 40 s). **1.8.0 prints a severity-3 message 2285** when `-recover` is run with a different seed or fingerprint, and it names the flags to pass: `Changed: seed, fingerprint.` / `To match the checkpoint, rerun with -seed -9042213659811338606 -fp 4 -workers 1.` Since `-seed` and `-fp` are random by default, a plain resume always gets this warning on 1.8.0. v1.7.4 has no such message. `-recover <missing folder>`: 1000:1 `java.io.FileNotFoundException ... vars.chkpt`, exit 255, stdout only, both builds. A run stopped by SIGTERM prints nothing at the end (driver exit 143).
9. **The five "kinds" without a `-tool` capture now have one** (table in Evidence): false `ASSUME` is 2104:1 (exit 10, no trace); an evaluation error is 2179 nested at severity 0 inside 1000:1 when it happens in an invariant (exit 75, then 2103) and a top-level 2179:1 with a trace when it happens in `Next` (exit 255); an action-property violation is 2112:1 with 2121 and states, no loop (exit 13); config errors are 5001/5003/2229 with exit 255 (1.7.4: the 5001 and 5003 are nested in 1000:1, with 5001 and 5003 at severity 0) or 151 (1.8.0: top-level, severity 1; 1.7.4 also uses 151 for 2229).
9b. **`-deadlock` given**: on `Deadlock` TLC finishes with no error, exit 0 (`deadlock-flag`). With `-deadlock -continue` on `MultiError` TLC prints two invariant violations with traces (`InvA`, `InvB`) and still exits **0** on both builds (`deadlock-flag-multierror`), whereas the same spec with `-continue` and deadlock checking on exits 11 (`q01-multi-error-continue`). So the exit code of a `-continue` run does not say that errors were found.
10. **A spec whose only SANY message is 4802 makes TLC exit 150 on both builds**, with 3002 and no model checking: SANY prints it under `Semantic errors:` as `*** Errors: 1`, and TLC does not tell it from an error. The same holds for the two stuttering-lint messages (`[] followed by action not of form [A]_v`). The PlusCal "changed since last translation" warnings are true warnings: TLC exits 0 and checks the model; the warning text sits inside the 2220/2219 window.
11. **SANY does not accept grouped flags** on either build: `-ls`, `-dl`, `-xy` give `Illegal switch: -dl` (1.7.4) or `Invalid option: -dl` + `Try 'SANY -help' for more information.` (1.8.0) on stdout, exit 255, without starting the explorer, although the 1.8.0 synopsis is written `[-dls]`. Separate `-d -l` and `-l -s` work.
12. **SANY `-help`**: 1.8.0 prints a 45-line man-style page on stdout with ANSI bold escape codes, exit 0; 1.7.4 prints `Illegal switch: -help`, exit 255; `-h` is illegal on both (255).
13. **SANY level errors on v1.7.4** have the same text and order as on 1.8.0 (`Level error in applying operator ':` ... and `Level error: assumptions must be level 0 (Constant), but this one has level 1.`), under `Semantic errors:`, exit 0; `-error-codes` does not exist there (`Illegal switch`, 255).
14. **Warning forms as captures of their own** (`sany-stale-alg`, `sany-stale-tla`, `sany-stale-both`, `sany-stale-two-files`, and inside TLC `stale-*-tool`): 1.7.4 one line `!! WARNING: <text>` directly under `Parsing file`; 1.8.0 a block `Warnings (1) during syntax parsing of <F>:` with `In module M` and the text, each separated by blank lines, ended by the next `Semantic processing` line. In SANY alone `<F>` is `PcalStaleAlg.tla`; inside TLC it is `PcalStaleAlg` (no extension). Three texts: the algorithm changed, the translation changed, both changed. The 1.7.4 text for "both" is misspelt (`... translation in module X filename since the last translation.`); 1.8.0 reads `Both the PlusCal algorithm and its TLA+ translation in module X have changed since the last translation.`

## Confidence

Verified for every case in the table below on Java 25 and Linux x86-64, on both builds. Partly verified: the "last state is printed in full" rule of `-difftrace` (seen in 4 model-checking specs and in simulation on 1.7.4 and 1.8.0, not read from source); the meaning of `-generate` (observed behaviour only; the option is undocumented); `-dfid` stopping early (observed, not explained). Not answered: macOS and Windows (not asked); a liveness trace under `-difftrace` where a state keeps a variable that the previous state had (the one capture changes both variables in the last state, so it shows partial printing only in states 2 and 3); Java 11 and 21; several workers together with `-difftrace` on a liveness spec (workers-4 with a safety violation was run).

## Evidence

### Cases

Exit codes and bytes of stderr are from `commands.txt` and the `.err` files. "n/a" means the build rejects the flag (the capture shows how). Case names are file names without extension in each version folder.

| Group | Case(s) | Spec | 1.7.4 exit | 1.8.0 exit | stderr |
|---|---|---|---|---|---|
| -difftrace | `difftrace-violation` (+ `-nodiff` for the same run), `difftrace-q1-violation`, `difftrace-workers-4` | Diff (3 variables), Violation | 12 | 12 | empty |
| -difftrace | `difftrace-liveness` (+ `-nodiff`), `difftrace-liveness-q1-back-to-state`, `-q1-stuttering` | DiffLive, LiveBack, LiveStutter | 13 | 13 | empty |
| -difftrace | `difftrace-deadlock` | Deadlock | 11 | 11 | empty |
| simulate | `simulate-violation`, `simulate-violation-diff` | Violation, Diff | 12 | 12 | empty |
| simulate | `simulate-deadlock`, `simulate-liveness` | Deadlock, LiveBack | 11, 13 | 11, 13 | empty |
| generate | `generate-violation`, `generate-violation-num` (`num=3`), `generate-deadlock` | Violation, Deadlock | 1 (n/a) | 12, 12, 11 | empty |
| generate | `generate-success` (never stops), `generate-success-num` | Success | 1 (n/a) | 137 (driver killed it at 120 s), 0 | empty |
| TE spec | `generateSpecTE-violation`, `noGenerateSpecTE-violation`, `plain-violation-files` | Violation | 12, 1 (n/a), 12 | 12, 12, 12 | empty |
| dfid | `dfid-success` (5), `dfid-violation` (2), `dfid-deadlock` (2) | Success, Violation, Deadlock | 0 | 0 | empty |
| dfid | `dfid-violation-deep` (10), `dfid-success-deep` (20) | Violation, Success | 12, 0 | 12, 0 | empty |
| ALIAS | `alias-violation`, `alias-violation-difftrace` | Alias | 151 (n/a) | 12 | empty |
| action shapes | `params-violation`, `params-step-violation` (`Step(i)`), `params-instance-exists-violation` (`I!Bump(i)`), each also with `-difftrace` | Params | 12 | 12 | empty |
| -deadlock | `deadlock-flag`, `deadlock-flag-multierror` (`-continue`) | Deadlock, MultiError | 0, 0 | 0, 0 | empty |
| error kinds | `tool-assum`, `tool-eval`, `tool-nexteval`, `tool-act`, `tool-asrt`, `tool-live` | research 15 specs | 10, 75, 255, 13, 14, 13 | same | empty |
| config | `tool-badcfg`, `tool-cfgsyn`, `tool-nocfg`, `tool-nospecfile`, `tool-cfg-missing` | research 15 specs | 151, 255, 255, 255, 255 | 151, 151, 151, 151, 151 | empty |
| usage | `tool-workers-bad`, `tool-noargs`, `tool-help` | none | 1 | 1 | empty |
| resources | `tool-oom` (`-Xmx64m`) | Oom | 75 | 75 | empty |
| SANY in TLC | `tool-missing-module`, `tool-name-mismatch` | MissMod, Mismatch | 150, 150 | 150, 150 | 1.7.4 missing module: 184 bytes; else empty |
| warnings | `warn4802-tool`, `warn4802-plain`, `warnstutter-tool` | Warn4802, WarnStutter | 150 | 150 | empty |
| warnings | `stale-alg-tool`, `stale-tla-tool`, `stale-both-tool`, `stale-alg-plain` | PcalStale* | 0 | 0 | empty |
| checkpoint | `checkpoint-run` (`-checkpoint 1`, SIGTERM at 80 s), `checkpoint-recover`, `checkpoint-recover-missing` | Slow | 143, 0, 255 | 143, 0, 255 | empty |
| SANY alone | `sany-help`, `sany-h` | none | 255, 255 | 0, 255 | empty |
| SANY alone | `sany-stale-alg`, `-tla`, `-both`, `sany-stale-two-files`, `sany-warn4802` | PcalStale*, Warn4802 | 0 | 0 | empty |
| SANY alone | `sany-grouped-ls`, `sany-grouped-ls-semerr`, `sany-grouped-dl` (stdin `quit`), `sany-grouped-unknown` | Good, SemErr | 255 | 255 | empty |
| SANY alone | `sany-separate-l-s`, `sany-s-semerr`, `sany-separate-d-l` (stdin `quit`) | Good, SemErr | 0 | 0 | empty |
| SANY alone | `sany-levelerr-174`, `sany-level-174` (both builds ran them; the name is the question's) | LevelErr, Level | 0, 255 | 0, 255 | empty |
| SANY alone | `sany-levelerr-errorcodes-174` (`-error-codes`) | LevelErr | 255 (illegal switch) | 4 | empty |
| SANY alone | `sany-grouped-lerror-codes` (it is `-l -error-codes`, two separate flags; the name is misleading) | LevelErr | 255 (illegal switch) | 0 | empty |
| SANY alone | `sany-missing-module-ext`, `sany-name-mismatch-ext`, `sany-nofile-no-sep` | MissMod, Mismatch, none | 255 | 255 | 1.7.4: 188 bytes for the first, 175 for the third; 1.8.0: 202 for the third; else empty |
| question 1 | `q01-*`, 20 cases | research 1 specs | as research 1 (0, 12, 11, 13, 13, 150, 150, 14, 0, 0, 0, 11, 255 or 10, 75 or 255, 75, 75, 11, 0, 1, 11) | | empty in all 40 runs |
| question 12 | `q12-*`, 60 cases (all of research 12's single commands; the composite retranslate file, the pty REPL session, the history file and the message-code list were not repeated) | research 12 inputs | as research 12 | | see below |

Stderr in the 60 question 12 cases: v1.7.4 non-empty for `q12-sany-missingmod` and `q12-sany-nofile` (the `File does not exist` line, 184 and 172 bytes), `q12-repl-stdin-eof` (class not found), `q12-xml-good`, `-help`, `-parseerr`, `-semerr` (Java exceptions). 1.8.0 non-empty for `q12-sany-nofile` (the same line, with `./Nope.tla` and a list of directories), `q12-repl-stdin-eof` (the jline `WARNING: Unable to create a system terminal` line), `q12-xml-help`, `-parseerr`, `-semerr`. Every PlusCal case and every `tla2sany.SANY` case other than the missing-file and missing-module ones has an empty stderr. On `XMLExporter` the parse error text and the semantic error text are on stderr on 1.8.0.

All 60 exit codes are the same as research 12 recorded (checked by script). The two differences between builds in question 1 are the ones research 1 gave: `postcondition-false` (255 and 10) and `stack-overflow` (75 and 255).

### `-difftrace` (P5)

`difftrace-violation` on `Diff` (variables `a`, `b`, `c`; `a` changes in steps 2 to 5). Both builds print the same states:

```
1: <Initial predicate>        /\ a = 0  /\ b = 0  /\ c = <<0, 0, 0>>
2: <Next line 5, col 12 ...>  /\ a = 1
3: <Next line 5, col 12 ...>  /\ a = 2
4: <Next line 5, col 12 ...>  /\ a = 3
5: <Next line 5, col 12 ...>  /\ a = 4  /\ b = 0  /\ c = <<0, 0, 0>>      last state: full
```

The same pattern is in `params-violation-difftrace` (states 1 and 3 full, 2 shows `z`), `alias-violation-difftrace` (1.8.0), `difftrace-q1-violation` (the wrapped `log` value is a normal variable; state 3 omits `store`) and `difftrace-workers-4`. In `simulate-violation-diff` the last state is partial (`b`, `c` only) on both builds. In the liveness case `difftrace-liveness` states 2 and 3 show only `p`, state 4 both variables (both changed), then `2: Back to state: <Next ...>` as without the option; on 1.7.4 the 2116 text is `Temporal properties were violated.` (no name), on 1.8.0 `Temporal property Reach was violated.` (research 1's table row for 1.7.4 says the named form; the 1.7.4 files in research 1 have the unnamed form too).

`verify-difftrace.txt` (the script `verify_difftrace.py` parses the 2217 states of a `-difftrace` run, carries forward the missing variables and compares with the run without the option):

```
v1.7.4 difftrace-violation states 5 vs 5 partial states: 3 carry-forward equals full trace: True
v1.7.4 difftrace-liveness states 4 vs 4 partial states: 2 carry-forward equals full trace: True
v1.7.4 params-violation-difftrace states 3 vs 3 partial states: 1 carry-forward equals full trace: True
v1.7.4 difftrace-q1-violation states 4 vs 4 partial states: 1 carry-forward equals full trace: True
(1.8.0: the same four, plus alias-violation-difftrace states 4 vs 4 partial states: 2 ... True)
```

Limits of this check: variable values are compared as text; `-difftrace` was not run on a spec where a variable changes to a value that prints the same.

### Headers, simulation and `-generate` (P5)

- BFS: `1: <Initial predicate>` on both builds. Simulation on 1.7.4: `<Initial predicate>`. Simulation and `-generate` on 1.8.0: `1: <Init line 4, col 9 to line 6, col 16 of module Violation>` (and `Init line 4, col 9 to line 4, col 13 of module Deadlock`).
- Actions: `params-step-violation` 1.7.4 `<Step line 6, col 12 to line 6, col 52 of module Params>` twice; 1.8.0 `<Step(1) line 6, ...>` then `<Step(2) line 6, ...>`. `Pick == \E i \in 1..2 : Step(i)` is the sub-action in `Next`; TLC names `Step`, the operator the action is defined in, not `Pick` or `Next`. `params-violation` and `params-instance-exists-violation`: `<Viaz line 8, col 9 to line 8, col 39 of module Params>` and `<Viaq line 14, col 9 to line 14, col 57 of module Params>`, both builds, no `I!Bump` and no arguments (the action is the outer operator body; `Bump(2)` and `Bump(i)` are inside it). So a header action text can contain `(`, `)`, digits and commas on 1.8.0, which the P5 pattern `^(?P<action>.+?) line (\d+), col ...` accepts. An argument that is a string containing ` line 3, col 4 to line 5, col 6 of module X` would be read wrongly by that pattern; not produced and not tried.
- `-generate` on 1.8.0: `generate-violation` (exit 12) and `generate-deadlock` (11) print the usual 2110/2114, 2121, 2217 states; the process was not stopped by the run. `generate-success`: no end; the driver killed it after 120 s with 1,435 bytes of stdout. On 1.7.4 the five `generate-*` cases print `@!@!@STARTMSG 1102:1 @!@!@ Error: unrecognized option: -generate Usage: java tlc2.TLC [-option] inputfile` after 2262, exit 1.

### `-dfid` (P5)

`dfid-violation-deep` (`Violation`, `-dfid 10`), 1.7.4 and 1.8.0:

```
@!@!@STARTMSG 2216:4 @!@!@        1.7.4: code 2216, header "1:"
1:
/\ store = [alpha |-> {}, beta |-> {}, gamma |-> {}]
...
@!@!@STARTMSG 2217:4 @!@!@        1.8.0: code 2217, header "1: " (a trailing space)
```

Other `-dfid` messages: 2271 `Running depth-first search Model-Checking with fp ...` (both builds, instead of 2187), 2208 `Finished computing initial states: 1 states generated, with 1 of them distinct.`, 2205 `Starting level 2: 1 states generated, 1 distinct states found.`, 2206 `Progress(-1) at ...: 39 states generated, 13 distinct states found, -1 states left on queue.`, 2204 `39 states generated, 13 distinct states found.` (no 2199, no 2193, no 2194, no 2268). `dfid-success` (`-dfid 5`) printed levels 2 to 5 and ended after 13 distinct states of the 16 reachable; `dfid-success-deep` (`-dfid 20`) went to level 8 with 16. `dfid-violation` (`-dfid 2`) ended after 7 states with exit 0 though the invariant is violated at depth 4.

### ALIAS (P5)

`alias-violation`, 1.8.0: `x = 0, sum = 0, label = "step"`, then `x = 1, sum = 3, ...`: the names are the fields of the alias record, `y` is not shown. 1.7.4: `@!@!@STARTMSG 2229:1 @!@!@ The invariant ALIAS specified in the configuration file / is not defined in the specification.` exit 151, no model checking. `ModelConfig` of v1.7.4 contains no `ALIAS` string and that of 1.8.0 does (`getAlias`).

### Error kinds in `-tool` mode (P5 "waiting on question 22")

| Case | Messages (top level unless "nested") | Exit, both builds unless said |
|---|---|---|
| `tool-assum` | `2104:1` `Assumption line 4, col 8 to line 4, col 12 of module Assum is false.`; no trace | 10 |
| `tool-eval` (invariant `x \div 0`) | `1000:1` (`The exception was ...`) containing `2179:0` `The second argument of \div is 0.`; then `2103:1` (nested expressions); no trace | 75 |
| `tool-nexteval` (`\div 0` in `Next`) | `2179:1` `The second argument of \div is 0.`, `2121:1`, one `2217` state, `2103:1` | 255 |
| `tool-act` (action property `Dec`) | `2112:1` `Action property Dec is violated.`, `2121:1`, states 1 and 2 (no loop line, no stuttering line) | 13 |
| `tool-asrt` | `2132:1`, `2121:1`, states, `2103:1` (as research 1) | 14 |
| `tool-badcfg` (`SPECIFICATION Nope`) | `2229:1` `The name Nope specified in the configuration file / is not defined in the specification.` | 151 (1.7.4: 151 as well) |
| `tool-cfgsyn` (`SPECIFICATION` with no name) | 1.8.0: `5003:1` `TLC found an error in the configuration file at line 1 / The keyword SPECIFICATION was not followed by an identifier.` 1.7.4: `1000:1` (`The exception was a tlc2.tool.ConfigFileException` then `: `) with `5003:0` nested | 1.8.0: 151; 1.7.4: 255 |
| `tool-nocfg`, `tool-nospecfile`, `tool-cfg-missing` | 1.8.0: `5001:1` `TLC encountered the following error when trying to read the configuration file X.cfg: / File not found.` 1.7.4: the same text as `5001:0` nested in `1000:1` | 1.8.0: 151; 1.7.4: 255 |
| `tool-workers-bad`, `tool-noargs` | `1102:1` `Error: worker number or 'auto' required. But encountered abc` / `Error: Missing input TLA+ module.`, then `Usage: ...` (1.8.0: `[-help] [-option]`) | 1 |
| `tool-oom` (`-Xmx64m`) | `1000:1` `Java heap space`, `2147:1` `TLC was unable to fingerprint.` and a fingerprint stack trace | 75 |
| `tool-missing-module` | inside 2220/2219 (see below), then `3002:1` | 150 |
| `tool-name-mismatch` | the same, `File name 'Mismatch' does not match the name 'Other' of the top level module it contains.` | 150 |

Notes. 1.7.4 and 1.8.0 differ for the config errors in two ways: severity and nesting of 5001 and 5003, and the exit code (255 against 151). The 2229 message is the same on both and is the only config message with top-level severity 1 on 1.7.4. In `tool-eval` the inner 2179 has severity 0.

### Warnings, SANY inside TLC and the stderr line

`tool-missing-module` on 1.7.4, stdout between 2220 and 2219:

```
Parsing file <tmp>/q22/work/v1.7.4/tool-missing-module/MissMod.tla
Parsing file /tmp/Naturals.tla
Fatal errors while parsing TLA+ spec in file MissMod
tla2sany.semantic.AbortException
*** Abort messages: 1
Unknown location
Cannot find source file for module NoSuchModule imported in module MissMod.
```

and stderr: the `File does not exist: ...` line. 1.8.0: stdout has `In module MissMod`, the message, `*** Errors: 1`, `In module MissMod`, the message again; stderr empty. So the v1.7.4 abort block always has its message on stdout; the "position line without message" case that P8's rules would drop does not occur.

`warn4802-tool`, both builds: between 2220 and 2219 `Semantic errors:`, `*** Errors: 1`, `line 4, col 16 to line 4, col 16 of module Warn4802`, `Non-unique fields in constructor.`; after 2219 and 2185, `3002:1 Parsing or semantic analysis failed.`; exit 150. `warn4802-plain` (no `-tool`): exit 150. `warnstutter-tool`: two semantic messages (`[] followed by action not of form [A]_v.`, `<> followed by action not of form <<A>>_v.`), exit 150. `sany-warn4802` (SANY alone): exit 0 on both.

`stale-alg-tool`, 1.8.0 (inside TLC; blank lines left out):

```
Parsing file <tmp>/q22/work/v1.8.0/stale-alg-tool/PcalStaleAlg.tla
Parsing file /tmp/tlc-<n>/Naturals.tla (jar:file:...)
Warnings (1) during syntax parsing of PcalStaleAlg:
In module PcalStaleAlg
The PlusCal algorithm in module PcalStaleAlg has changed since its last translation.
Semantic processing of module Naturals
```

`sany-stale-alg`, 1.8.0 (SANY alone): the same but the header reads `Warnings (1) during syntax parsing of PcalStaleAlg.tla:`. 1.7.4, SANY alone or inside TLC: `Parsing file <path>/PcalStaleAlg.tla` then `!! WARNING: The PlusCal algorithm in module PcalStaleAlg has changed since its last translation.` then `Parsing file /tmp/Naturals.tla`. In `sany-stale-two-files` each file has its own block. Exit codes are 0 everywhere (SANY alone and TLC). The stale inputs were made by running each build's `pcal.trans` on a module with the algorithm of `Pcal.tla` under a new name, then editing the algorithm (`x + 1` to `x + 2`), or the translation (`A == /\ pc = "A" /\ TRUE`), or both (`inputs/`).

### Checkpoint and recover

`checkpoint-run` (`Slow`, `-checkpoint 1`, SIGTERM sent by the driver at 80 s): after the first interval, 2195 and 2196 about 60 s after the start (`Checkpointing of run <tmp>/.../26-11-18-22-07-18` on 1.7.4; the 1.8.0 folder has milliseconds), then a 2200 progress line; the run was stopped there. Left in the metadir folder: `Slow-0.chkpt`, `Slow-0.st`, `Slow.st`, `Slow.st.chkpt`, `Slow_0.fp`, `Slow_1.fp`, `queue.chkpt`, `vars.chkpt` and, on 1.8.0, `settings.chkpt` (as research 17). `checkpoint-recover` (`-recover <that folder>`): after 2185, `2197:0 Starting recovery from checkpoint <folder>/`, `2198:0 Recovery completed. 535 states examined. 1 states on queue.` (1.7.4; 592 on 1.8.0), then normal progress to the end of the run, exit 0. On 1.8.0 a `2285:3` message precedes 2198:

```
Recovering this checkpoint with different settings can produce inconsistent state counts and counterexamples with missing or incorrect states. Results may be unreliable.
The checkpoint was created with -seed -9042213659811338606 -fp 4 -workers 1 (fingerprint -4107963342645125260).
This run is using -seed 8955305772308153403 -fp 7 -workers 1 (fingerprint -5630083135614502665).
Changed: seed, fingerprint.
To match the checkpoint, rerun with -seed -9042213659811338606 -fp 4 -workers 1.
Recovery will continue with the current settings at your own risk.
```

The run's own 2187 line (`Running breadth-first search Model-Checking with fp 5 and seed ...`) is where `-fp` and `-seed` can be read.

### New message codes, by file

Codes that appear in these captures and not in research 1's 40 files: 2104, 2112, 2147, 2179, 2195, 2196, 2197, 2198, 2204, 2205, 2206, 2208, 2229, 2271, 5001, 5003 on both builds; 1000 at severity 0, 1000 at severity 0 (the `-generateSpecTE` chatter) and 2216 on 1.7.4 only; 2285 and 2501 on 1.8.0 only (`-recover` with other settings; `-generateSpecTE`). `generateSpecTE-violation` on 1.7.4 also writes `SpecTE.tla` and `SpecTE.cfg` into the working folder and prints four `1000:0` messages (`Will generate a SpecTE file pair if error states are encountered.`, `The model check run produced error-states - we will generate the SpecTE files now.`, `The file <path>/SpecTE.tla has been created.`, ...). On 1.8.0 `-generateSpecTE` writes `Violation_TTrace_<n>.tla` and `.bin` and prints `2501:0 Trace exploration spec path: ./Violation_TTrace_<n>.tla`. Without the option, 1.8.0 in `-tool` mode wrote no extra file (`q01-violation`), and in plain mode it wrote the `_TTrace_` pair (`plain-violation-files`); 1.7.4 wrote none in either mode.

### SANY alone

- `sany-help` 1.8.0: exit 0, 45 lines on stdout, 12 lines contain ESC `[1m` or `[3m` sequences, `SYNOPSIS` reads `SANY [-dls] [-error-codes] [-messagesAsErrors codes] [-suppressMessages codes] FILE...`. `sany-h` on 1.8.0: `Invalid option: -h` and `Try 'SANY -help' for more information.`, exit 255. 1.7.4: `Illegal switch: -help` and `Illegal switch: -h`, one line each on stdout, exit 255.
- Grouped flags: `-ls`, `-dl`, `-xy` all give the invalid-option line and exit 255 on both builds; `-dl Good.tla` with stdin `quit` did not start the explorer. `-d -l Good.tla` with stdin `quit` started it (banner, `*** TLA+ semantic graph exploration tool v 1.0 (DRJ)`, prompt `>>`) on both.
- Level errors on 1.7.4 (`sany-levelerr-174`): `line 6, col 8 to line 6, col 10 of module LevelErr` then `Level error in applying operator ':` / `The level of argument 1 exceeds the maximum level allowed by the operator.`, and `line 4, col 1 to line 4, col 12 of module LevelErr` then `Level error: assumptions must be level 0 (Constant), ` (a trailing space) / `but this one has level 1.`; identical on 1.8.0 apart from banner, `Parsing file` format and the `Linting` line. `sany-level-174` (the precedence conflict): `Fatal errors while parsing TLA+ spec in file Level.tla`, abort block, exit 255 on 1.7.4.

### Reproduction

`TLAUP_TMP=<scratch folder> python3 tests/fixtures/research/22-more-tool-captures/run.py v1.7.4` (and `v1.8.0`); about 12 minutes per version, most of it `checkpoint-run` and `checkpoint-recover`. `javac --release 11` is used for the Boom classes of the question 1 cases. `python3 verify_difftrace.py` in the fixture folder re-checks the carry-forward claim.

## Implications for the roadmap

These change nothing by themselves; they are what the design owners should look at.

- **P5, `-difftrace`.** The fallback "print states as TLC printed them when `-difftrace` is among the arguments" is not needed for correctness: carrying each missing variable forward from the previous state gives the complete state (verified on 10 pairs), so the parser can fill the variables and the reporter's changed-variable display keeps working. The state's `lines` stay as printed. A parser that does not carry forward would show variables as vanished, which is the risk P5 named. The first state is always complete; a state may have one variable or all.
- **P5, headers.** The header pattern holds for `Step(1)` and for `Init line ...` (simulation, 1.8.0). `-dfid` traces do not fit: code 2216 on 1.7.4, header `N:` or `N: ` with no brackets; as written they would be `UnknownMessage` (the 2216 one would not even be recognised as a state). A rule for 2216 and for the header `^\d+:\s*$` is needed if `-dfid` is to be parsed. The 1.7.4 liveness message has no property name (`Temporal properties were violated.`), so the name is `None` there; P5 already allows that.
- **P5, kinds.** The kinds the design waited for now have codes: `assumption` 2104; `evaluation` 2179 (top level with a trace, or nested at severity 0 in a 1000 with the 2103 after it, so the top-level error is the 1000, not the 2179); action property 2112 (a property kind, with trace and no loop line); config 5001, 5003 and 2229 (top-level on 1.8.0, with 5001 and 5003 nested at severity 0 in a 1000 on 1.7.4, where the 1000 is the error and the nested codes decide the kind, as the design already does for 5006); 2147 (fingerprint failure after an OOM, with 1000 `Java heap space`).
- **P5, new informational and warning messages.** 2195 to 2198 (checkpoint, recover), 2204 to 2208 and 2271 (`-dfid`), 2210, 2501 are severity 0; 2285 is a severity-3 warning (1.8.0) and should show as a warning, not as unknown. A `-generateSpecTE` run on 1.7.4 prints four `1000:0` messages (severity 0, code 1000 usually an error code), so the severity-first rule matters there.
- **Resume command ([11 R6](../design/11-runner.md#r6-run-folders)).** On 1.8.0 `-recover` without the original `-seed`, `-fp` and `-workers` always warns (2285). The first run's 2187 message holds `fp N` and `seed S`; TLC's own warning gives the flags to repeat. The resume command could carry them. 1.7.4 does not warn and nothing in its output records a difference.
- **Exit codes with `-continue`.** `-deadlock -continue` with two invariant violations exits 0 on both builds; a result built only from the exit code would call it a success. The message stream has the two 2110 errors.
- **P8, the open stderr question.** Inside a TLC run SANY's diagnostics are all on stdout; the only stderr text is the `File does not exist` line of a missing module on v1.7.4. That is the first of the two cases P8 distinguished: nothing in the parser changes; the line reaches the user through stderr. The v1.7.4 abort block has its message on stdout, so the dropped-diagnostic case cannot arise from a missing module. For `tlaup sany` (merged streams) the captured files remain valid inputs.
- **P8, warning forms.** Both forms now exist as captures. Differences the parser must cover: the 1.7.4 one-line `!! WARNING: ...` (with a misspelt "both" text) and the 1.8.0 block; the block header ends in `.tla:` in SANY alone but has no extension inside TLC (the parser must not take the file from it, or must accept both); the three texts. A warning block on 1.8.0 inside TLC is ended by the next `Semantic processing` line, as the design says.
- **TLC's exit code for a 4802-only spec is 150.** TLC fails the run with 3002 for the warning-level message 4802 and for the stutter-lint messages, because SANY puts them under `Semantic errors:` with `*** Errors: N`. So the parser's rule "4802 is a warning by its text" disagrees with what TLC does with it; for `tlaup sany` the decision (return 150 for an error, not for a warning alone) was made on SANY's own exit code, 0. PlusCal's stale-translation warnings are real warnings (TLC exit 0).
- **S1, grouped flags.** SANY rejects `-dl`, `-ls` on both builds with exit 255 and without starting the explorer, so refusing exactly `-d` is enough to avoid the endless prompt loop; no grouped form needs a rule. The 1.8.0 synopsis `[-dls]` is misleading and should not be copied into tlaup's help.
- **S5, golden cases.** Cases now capturable as single commands: `sany-help` (1.8.0 only; 1.7.4's single illegal-switch line), `sany-stale-alg/-tla/-both` for the warning block (one file each), level errors on 1.7.4, 4802. The help text carries ANSI escape codes (ESC `[1m`): they sit in lines of class `OTHER` and a plain-text parser sees them as part of the line.
- **Passthrough set (R8).** `-generate` is rejected by 1.7.4 (exit 1, 1102) and accepted by 1.8.0 and the flag is hidden from `-help`; `-noGenerateSpecTE` is rejected by 1.7.4; `ALIAS` in a cfg fails on 1.7.4 with 151. If tlaup ever reports "this flag needs 1.8.0", these are three examples.
- **Testing ([01 T3](../design/01-testing.md#t3-golden-files)).** The golden set can take the new cases as real files. Time-dependent values (the 2185 time, 2200 progress, the 2285 seeds, the checkpoint folder name) need the same normalisation as research 1.

## Open follow-ups

- `-dfid` ending early (`dfid-violation`, `dfid-success`) was observed and not explained; if tlaup ever offers `-dfid`, check against TLC's source whether the search is meant to stop at the start depth.
- `-difftrace` with a spec where a variable changes to a value that prints the same, and a liveness trace whose loop state keeps a variable unchanged, were not run.
- `-generate` has no documentation; its exact semantics (when it stops, whether it checks properties) were not read from source.
- Java 21 and 11, macOS and Windows: not run (no such part in this question).
- The 2285 warning on `-recover` was seen with default seeds only; a recover with the printed flags (to see whether the warning disappears) was not run.

## Date checked

2026-11-18 (local time, Hawaii), jars as given above (v1.8.0 and `rolling` byte-identical on that date).
