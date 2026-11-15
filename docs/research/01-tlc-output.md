# 01: Real TLC `-tool` output for each supported version

## Question

What does TLC really print with `-tool` for success, invariant violation, deadlock, liveness (back-to-state and stuttering), SANY semantic and parse errors, assertion failure and coverage, on the latest stable release (v1.7.4) and the current rolling build (1.8.0)? Also: several workers, simulation mode, the version line, a runtime error with a Java stack trace, several errors in one run, a false postcondition (2404), progress lines above 999,999 states, a message nested in another, text before or after a marker on the same line, and a warning forced by its severity. Captured as golden files for Milestone 1 (Parser, first item).

## Source

- Jars downloaded with `gh release download <tag> -R tlaplus/tlaplus -p tla2tools.jar` (repository `tlaplus/tlaplus`), tags `v1.7.4`, `v1.8.0`, `rolling`. Release list: https://github.com/tlaplus/tlaplus/releases
- Real runs of `java -cp tla2tools.jar tlc2.TLC -tool ...` on this machine. Nothing was taken from documentation or memory; every claim below is read from a captured file.
- Fixtures: `tests/fixtures/research/01-tlc-output/` (`1.7.4/`, `1.8.0/`, `specs/`). Each version folder has a `README.md` with a table: file, spec, what it shows, exact command, exit code. `commands.txt` repeats the commands.

## Short answer

All requested cases were captured for both versions, 20 cases each, plus the same 20 without `-tool` (in `plain/`). The captured jars:

| | v1.7.4 | v1.8.0 and `rolling` |
|---|---|---|
| Release | "The Xenophanes release", Latest, 2024-08-05 | pre-release v1.8.0, published 2026-11-15T00:29:14Z; `rolling` pre-release, asset updated 2026-11-15T00:32:15Z |
| `tla2tools.jar` size | 2,274,532 bytes | 4,510,884 bytes |
| SHA-256 | `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88` | `7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f` |
| Version line (message 2262) | `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)` | `TLC2 Version 2026.11.15.002146 (rev: bc1b506)` |

The v1.8.0 jar and the rolling jar are byte-identical (`cmp` says so), so there is one 1.8.0 capture, not two. Findings the parser must handle (all in the files):

1. Format: a message is `@!@!@STARTMSG <code>:<severity> @!@!@`, body lines, `@!@!@ENDMSG <code> @!@!@`. Output that is not inside a message also appears: SANY's `Parsing file ...`, `Semantic processing of module ...`, `Linting of module ...` (1.8.0 only), SANY's semantic and parse error text, spec output from `Print`/`PrintT`, Java stack traces.
2. Messages can nest: `1000` (unexpected exception) contains `2154` (Java override failed) or `5006` (config error), and the inner marker sits on the same line after `: `. See `1.8.0/java-override-exception.out` line 38 and `1.7.4/postcondition-false.out` line 15.
3. Severities seen: 0 (info), 1 (error), 3 (warning: only `2401`, in every run), 4 (state or trace item). Severity 2 and 5 were not seen.
4. Exit codes seen: 0 success, 1 bad option, 10 postcondition false (1.8.0), 11 deadlock, 12 invariant violated, 13 temporal property violated, 14 assertion failure, 75 unexpected exception, 150 SANY parse or semantic error, 255 (1.7.4: config error, and 1.8.0 StackOverflowError).
5. 1.7.4 and 1.8.0 differ in small ways that matter for a golden-file parser (details in Evidence).

## Confidence

Verified for the cases that were captured. Partly verified for: text after a marker on the same line (only provoked artificially by a spec that prints marker text), a severity-2 message (not provoked), several workers with liveness checking (not run). Not run: Java 11 (see Evidence).

## Evidence

### Environment

- Linux 6.12 (Debian 13), x86_64, 12 cores. `java -version`: OpenJDK 25.0.5+8 (Debian), at `/usr/bin/java`. All captures used this Java 25.
- JDKs present: `/usr/lib/jvm/` has Java 21 and 25; no Java 11. Java 11 was not tested. The v1.7.4 jar manifest says `Created-By: 11.0.3+7-LTS`, so it targets Java 11.
- Java 21 was run on all 20 cases for 1.8.0 (`java-21-openjdk-amd64/bin/java`). I diffed 5 cases (success, violation, liveness-back-to-state, assertion-failure, coverage) after removing times, pids, seeds, temp folders and rates: no difference. The other cases were not diffed. The Java 21 outputs are not kept in the fixtures. The 2187 line includes the OS and Java vendor/version string (`Debian 25.0.5 x86_64` on 1.7.4, `Debian 25.0.5 64bit` on 1.8.0), so it differs by Java and by version.
- Each run used a fresh `-metadir`. The specs were run from one working folder; the `Parsing file` lines contain that absolute path, and on 1.7.4 standard modules are extracted to `/tmp/Naturals.tla`, on 1.8.0 to `/tmp/tlc-<random>/Naturals.tla (jar:file:...)`. Timestamps, `pid`, `seed`, `fp` and rates change from run to run, so a test should not compare whole files byte for byte without normalizing them.
- Dates: downloaded and run 2026-11-14 (local time HST; it was already 2026-11-15 in UTC, which is why the v1.8.0 release looks "published tomorrow").

### What each case contains

Cases (spec in `specs/`, file in each version folder as `<case>.out`):

| Case | Spec | Key messages seen |
|---|---|---|
| success | Success | 2185, 2189, 2190, 2200, 2193 (no error, with fingerprint probabilities), 2199, 2194, 2268, 2186 |
| violation | Violation | 2110 invariant violated, 2121, 2217 states. State values wrap: a record in a sequence continues on following lines (`/\ log = << [ op |-> "add",` then `     key |-> ...` and a long string moved to its own line) |
| deadlock | Deadlock | 2114, then 2121 and 2217 trace |
| liveness-back-to-state | LiveBack | 2192, 2116 `Temporal property Reach was violated.`, 2264, 2217 states, 2122 `1: Back to state: <Next line ...>`, 2267 |
| liveness-stuttering | LiveStutter | same, ending with 2218 `3: Stuttering` |
| sany-semantic-error | SanyError | Between 2220 and 2219: plain text `Semantic errors:`, `*** Errors: 1`, `line 5, col 18 to line 5, col 31 of module SanyError`, ``Unknown operator: `undefinedThing'.``; then 3002 `Parsing or semantic analysis failed.`, 2186. Exit 150 |
| parse-error | ParseError | Plain text `***Parse Error***`, `Encountered "Beginning of definition" at line 6, column 1 and token "1"`, `Residual stack trace follows:`, `Fatal errors while parsing TLA+ spec in file ParseError`, `Could not parse module ParseError from file ParseError.tla`; then 3002. Exit 150 |
| assertion-failure | Assertion | 2132 `The first argument of Assert evaluated to FALSE; the second argument was:` then the message string, then 2121 and 2217, then 2103 (nested expressions). Exit 14 |
| coverage | Success, `-coverage 1` | 2201 header, 2779 (variable), 2773 (Init), 2772 (Next action), 2774, 2221 (sub-expression lines, some start with `|`), 2202. 1.7.4 has no 2779 |
| workers-4 | Success, `-workers 4` | 2187 says `with 4 workers on 12 cores` |
| simulate | Success, `-simulate num=3 -depth 20 -seed 7` | 2188 (not 2187), 2269, 2209 `Progress(3) ... 61 states generated, -1 distinct states found, -1 states left on queue.` (the `-1` values are real), and in 1.8.0 also 2190 and 2210 `Simulation using seed 7 and aril 0` |
| multi-error-continue | MultiError, `-continue` | 2110 `InvA`, 2110 `InvB`, 2114 deadlock, each followed by its own 2121 and trace. Exit 11 |
| postcondition-false | Post | 1.8.0: 2404 `Postcondition Post at line 8, col 9 to line 8, col 31 of module Post is false.` Exit 10. 1.7.4: no support; see below |
| stack-overflow | Stack | see below |
| java-override-exception | Boom | see below |
| java-override-stack-trace | BoomTrace | see below |
| print-output | Print, `-continue` | `"init-print"`, `<<"step", 0>>`, `"inv-print"  TRUE` lines between and inside traces (the same lines are repeated after each error); two errors in one run |
| big-states | Big, `-workers 4` | see below |
| version-bad-option | none, `-version` | 2262, then 1102 `Error: unrecognized option: -version`. Exit 1 |
| print-marker | PrintMarker | see below |

### The version line

`-version` is not a TLC option on either build. Message 2262 is the first message of every run, `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)` and `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`. A run with an unknown option prints it before the 1102 error (`1.7.4/version-bad-option.out`). The 1.7.4 jar manifest says `Implementation-Version: 2.0 2024-08-08`, which differs from the TLC line; the `-help` text says `Version 2.19 of 08 August 2024`.

### Warning by severity

Message `2401:3` (the `-XX:+UseParallelGC` advice) is in 38 of the 40 `-tool` captures (all except `version-bad-option`, which stops at option parsing) and is the only severity-3 message seen. Its wording differs: 1.7.4 `Please run the Java VM which executes TLC with a throughput optimized garbage collector by passing ...`; 1.8.0 `Please run the Java VM, which executes TLC with a throughput optimized garbage collector, by passing ...`. It is printed because the runs did not pass the flag: a check run with `java -XX:+UseParallelGC` (1.8.0, Success, scratch only) printed no 2401. A parser test for "warning by severity" can use this message.

### Nested messages and text on the same line as a marker

- `1.8.0/java-override-exception.out` lines 33 to 44:

```
@!@!@STARTMSG 1000:1 @!@!@
TLC threw an unexpected exception.
...
The exception was a java.lang.RuntimeException
: @!@!@STARTMSG 2154:0 @!@!@
Attempted to apply the operator overridden by the Java method
...
boom from Java override
@!@!@ENDMSG 2154 @!@!@
@!@!@ENDMSG 1000 @!@!@
```

  The inner STARTMSG follows `: ` on the same line, the severity of the inner message is 0 while the outer is 1. Same shape in 1.7.4, and in both versions in `postcondition-false` for 1.7.4 with code 5006 (`1.7.4/postcondition-false.out` line 15).
- Text before and after a marker on one line only occurs here when the spec prints it: `print-marker.out` has `"before @!@!@STARTMSG 2185:0 @!@!@ after"` and a lone `"@!@!@STARTMSG 9999:1 @!@!@"` with no ENDMSG. These are Print output (inside quotes, the strings are what TLC prints). Text before a marker (`: `) is real TLC behaviour; text after a marker on the same line was not produced by TLC itself. I tried 6 runs with 12 workers and PrintT in `Next` (40,000 lines each, scratch only) and found no interleaving of a marker with other text.

### Runtime error with a Java stack trace

- 1.7.4 `stack-overflow.out` (RECURSIVE operator that never ends): message `1000:1` says `The exception was a java.lang.StackOverflowError`, followed by `java.lang.StackOverflowError` and about 1,000 lines of `\tat tlc2.tool.impl...` inside the message, then 2103 `The error call stack is empty`. Exit 75. The stack trace lines are inside the message body, not outside.
- 1.8.0 `stack-overflow.out`: message `1005:1` (`This was a Java StackOverflowError. It was probably the result of an incorrect recursive function definition ...`), 2121 and a 2217 trace, no stack trace. Exit 255.
- `java-override-stack-trace.out` (both versions): a Java override (`specs/java/tlc2/module/BoomTrace.java`, built with `javac --release 11`) that throws `StackOverflowError`. Message 2154 nested in 1000 contains `java.lang.StackOverflowError` and `\tat tlc2.module.BoomTrace...` lines, ending with a blank line before ENDMSG. Exit 75. Throwing `IllegalStateException`, `AssertionError` or `Error` from the override gives no stack trace, only the message text (`java-override-exception.out`, and a scratch run of the other two).

### False postcondition (2404)

1.8.0 prints message 2404 (see table). 1.7.4 does not know the `POSTCONDITION` keyword: `1.7.4/postcondition-false.out` has 1000 containing 5006 `TLC found an error in the configuration file at line 2. It was expecting a keyword, but did not find it.`, exit 255. So 2404 cannot be captured on 1.7.4; that is a fact about the build, not a capture failure.

### Progress lines above 999,999 states

`big-states.out` (`Big`, 2,248,091 distinct states, 6,692,791 generated), the numbers carry thousands separators and the unit text stays:

```
Progress(148) at 2026-11-14 22:27:29: 1,581,826 states generated (1,581,826 s/min), 537,890 distinct states found (537,890 ds/min), 10,473 states left on queue.
Progress(391) at ...: 6,692,791 states generated (43,132,917 s/min), 2,248,091 distinct states found (14,488,234 ds/min), 0 states left on queue.
```

This is the 1.7.4 capture. In the 1.8.0 capture the first progress line is `Progress(188) ...: 3,010,185 states generated (3,010,185 s/min), 1,017,832 distinct states found (1,017,832 ds/min), 12,837 states left on queue.`, so both generated and distinct counts exceed 999,999 there. Small runs print `Progress(3) at ...: 4 states generated, 3 distinct states found, 0 states left on queue.` with no rates (liveness case), or with rates (`26 states generated (2,540 s/min)`). The final summary 2199 (`6692791 states generated, 2248091 distinct states found, 0 states left on queue.`) has no separators.

### Differences between 1.7.4 and 1.8.0

Found by comparing the sequence of message codes per case:

- 1.8.0 prints `Linting of module <M>` (plain text) after semantic processing.
- 2194 (`The depth of the complete state graph search is N.`): 1.8.0 also prints it after a liveness violation, an assertion failure and a stack overflow, where 1.7.4 does not. 2268 (outdegree): 1.7.4 prints it after invariant violation and deadlock too; 1.8.0 only after completed runs.
- Coverage: 1.8.0 adds 2779 for variables.
- Simulation: 1.8.0 adds 2190 and 2210.
- Stack overflow: 1000 with raw trace (1.7.4) vs 1005 (1.8.0).
- POSTCONDITION unsupported on 1.7.4.
- 2401 wording and the `Parsing file` format differ.
- Where both print the same codes (success, SANY semantic error), the lines are identical apart from the version, 2401 text, `Linting`, paths and times.

### Not captured or limits

- Java 11: not installed. Java 21 vs 25: only 5 cases compared, identical after normalizing.
- Severity 2 (TLC bug) and 5 messages: not provoked.
- One spec per case; no spec was run with `-deadlock`, `-checkpoint`, `-recover`, `-dump`, `-gzip` or with `-difftrace`.
- Values with very large wrapping (lines over 80 columns of nested sets) were captured only in the one `violation` spec.
- No Windows or macOS captures.
- The `rolling` tag will move; the capture is of the build with SHA-256 above (the same as v1.8.0 on 2026-11-14).

## Implications for the roadmap

- Golden files for the first Milestone 1 item exist now under `tests/fixtures/research/01-tlc-output/{1.7.4,1.8.0}/`. The parser's expected results can be written against them. A test should normalize time, pid, seed, fp, rates and the run path (or the parser should not use them).
- The parser cannot assume that every line is inside a message, that markers are alone on a line, or that messages do not nest. Cases with these properties are in the fixtures (`java-override-*`, `postcondition-false` on 1.7.4, `print-*`, `sany-*`, `parse-error`).
- SANY errors and parse errors arrive as plain text between 2220 and 2219 and are then followed by 3002 with severity 1; the text has line and column in the form `line L, col C to line L, col C of module M`.
- Do not rely on one message code across versions: 2404, 2779, 2210, 1005, `Linting` exist only in 1.8.0; 1.7.4 prints a raw Java stack trace inside message 1000.
- Plain (non `-tool`) output was captured as a bonus in `plain/`.
- `rolling` equals v1.8.0 right now; the "current rolling build" fixture is therefore filed under `1.8.0`. When rolling moves, the fixture folder needs a new name (for example the version line's `2026.11.15.002146`) or a re-capture.

## Open follow-ups

- Decide how to name fixtures for a rolling build once it moves past 2026.11.15.002146.
- Re-capture on Java 11 if it is a supported runtime (not available here).
- Capture a run with `-XX:+UseParallelGC` to confirm 2401 disappears (inferred, not run).
- Try to provoke a severity-2 message and text after a marker from TLC itself (for example output from several workers writing at the same time).
- The 20 `plain/` outputs were not examined beyond exit codes.

## Date checked

2026-11-14 (local HST; 2026-11-15 UTC).
