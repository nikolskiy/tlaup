# TLC output captured with TLC 1.7.4

Captured on 2026-11-14 on Linux (Debian 13, x86_64, 12 cores) with `java` 25.0.5 (OpenJDK, Debian build).
Java 21.0 was also run on a subset for comparison (see docs/research/01-tlc-output.md). Java 11 was not available.

Jar: github.com/tlaplus/tlaplus release v1.7.4 ("The Xenophanes release", Latest, published 2024-08-05), asset tla2tools.jar, 2,274,532 bytes, SHA-256 936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88. Version line: `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`.

Specs and configs are shared by both versions in `../specs/`. They were copied to one working folder and run from there,
so the `Parsing file` lines hold that absolute path; timestamps, pids, seeds and temp folders differ on every run.
Every case ran with a fresh `-metadir`, shown as `<metadir>`. Files in this folder are the combined stdout and stderr, unedited.
`plain/` holds the same runs without `-tool` (bonus).

| File | Spec | What it shows | Command (run in the folder with the specs) | Exit |
|---|---|---|---|---|
| `success.out` | Success | finishes, no error; ends with 2193 and statistics | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> Success` | 0 |
| `violation.out` | Violation | invariant violated; state values wrapped over several lines (records, sequences, long strings) | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> Violation` | 12 |
| `deadlock.out` | Deadlock | deadlock reached (2114) with trace | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> Deadlock` | 11 |
| `liveness-back-to-state.out` | LiveBack | temporal property violated; trace ends with 'Back to state' (2122) | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> LiveBack` | 13 |
| `liveness-stuttering.out` | LiveStutter | temporal property violated; trace ends with 'Stuttering' (2218) | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> LiveStutter` | 13 |
| `sany-semantic-error.out` | SanyError | SANY semantic error (unknown operator); 3002 follows | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> SanyError` | 150 |
| `parse-error.out` | ParseError | SANY parse error (unbalanced parenthesis); 3002 follows | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> ParseError` | 150 |
| `assertion-failure.out` | Assertion | Assert failure, code 2132 | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> Assertion` | 14 |
| `coverage.out` | Success | -coverage 1: coverage statistics (2201, 2221, 2772, 2773, 2779 ...) | `java -cp tla2tools.jar tlc2.TLC -tool -coverage 1 -metadir <metadir> Success` | 0 |
| `workers-4.out` | Success | -workers 4: the 2187 line says '4 workers' | `java -cp tla2tools.jar tlc2.TLC -tool -workers 4 -metadir <metadir> Success` | 0 |
| `simulate.out` | Success | -simulate num=3 -depth 20 -seed 7: simulation mode (2209/2210 instead of 2200/2199) | `java -cp tla2tools.jar tlc2.TLC -tool -simulate num=3 -depth 20 -seed 7 -metadir <metadir> Success` | 0 |
| `multi-error-continue.out` | MultiError | -continue: two invariant violations and a deadlock in one run | `java -cp tla2tools.jar tlc2.TLC -tool -continue -metadir <metadir> MultiError` | 11 |
| `postcondition-false.out` | Post | POSTCONDITION is false; 2404 in 1.8.0. In 1.7.4 the keyword is rejected: config error 5006 nested in 1000 | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> Post` | 255 |
| `stack-overflow.out` | Stack | RECURSIVE operator without end: Java StackOverflowError. 1.7.4 prints a raw Java stack trace (about 1000 lines) inside message 1000; 1.8.0 prints message 1005 instead | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> Stack` | 75 |
| `java-override-exception.out` | Boom + java/tlc2/module/Boom.java | Java override throws IllegalStateException: message 2154 nested inside message 1000, and text ': ' before a STARTMSG marker on the same line | `java -cp tla2tools.jar:classes/v1.7.4 tlc2.TLC -tool  -metadir <metadir> Boom` | 75 |
| `java-override-stack-trace.out` | BoomTrace + java/tlc2/module/BoomTrace.java | Java override throws StackOverflowError: a Java stack trace inside the nested message 2154 | `java -cp tla2tools.jar:classes/v1.7.4 tlc2.TLC -tool  -metadir <metadir> BoomTrace` | 75 |
| `print-output.out` | Print | PrintT/Print output interleaved between messages (user output has no markers); -continue gives 2 errors | `java -cp tla2tools.jar tlc2.TLC -tool -continue -metadir <metadir> Print` | 11 |
| `big-states.out` | Big | 2,248,091 distinct states: Progress lines with thousands separators above 999,999 (2200) | `java -cp tla2tools.jar tlc2.TLC -tool -workers 4 -metadir <metadir> Big` | 0 |
| `version-bad-option.out` | (no spec) | '-version' is not an option: version line (2262) then error 1102; exit code 1 | `java -cp tla2tools.jar tlc2.TLC -tool -version -metadir <metadir>` | 1 |
| `print-marker.out` | PrintMarker | spec prints strings that contain marker text: text before and after a marker on one line; fake STARTMSG 9999 without ENDMSG | `java -cp tla2tools.jar tlc2.TLC -tool  -metadir <metadir> PrintMarker` | 11 |

Exit codes of the plain (non `-tool`) runs in `plain/`: success 0; violation 12; deadlock 11; liveness-back-to-state 13; liveness-stuttering 13; sany-semantic-error 150; parse-error 150; assertion-failure 14; coverage 0; workers-4 0; simulate 0; multi-error-continue 11; postcondition-false 255; stack-overflow 75; java-override-exception 75; java-override-stack-trace 75; print-output 11; big-states 0; version-bad-option 1; print-marker 11.

Java-override cases need a class folder: `javac --release 11 -cp tla2tools.jar -d classes/<label> ../specs/java/tlc2/module/*.java`;
the command above adds `classes/<label>` to the class path (`<label>` was `v1.7.4` or `v1.8.0`).
