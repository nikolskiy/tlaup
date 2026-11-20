# 19: Does TLC accept `-workers auto`?

## Question

Does TLC accept `-workers auto` on each supported build (v1.7.4 and 1.8.0 rolling), what does its startup line
(message 2187, with and without `-tool`) say then, how many workers does `auto` give compared with the core count
(also under a `taskset` or cgroup CPU limit), and what happens with `-workers 0`, a negative value, a non-number and a
missing value? Asked by the roadmap's investigation list (question 19), for
[design 11 R8](../design/11-runner.md#r8-passthrough-and-workers) and decision D24 (`--workers` defaults to `auto`).

## Source

- Jars: v1.7.4, `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`, sha256 `936a2620...`; "1.8.0 (rolling)",
  `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`, sha256 `7e53aa63...` (the rolling and v1.8.0 assets are
  byte-identical).
- Java: OpenJDK 25.0.5 and Temurin 11.0.33+10, both with every case; Linux x86-64, 12 cores. Other agents were running
  on the same machine; nothing here depends on timing.
- Upstream source, pinned: `TLC.java` option parsing,
  [v1.7.4 lines 741-770](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L741-L770),
  [1.8.0 lines 1004-1033](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1004-L1033).
  The startup line is built from the same `workers`, `plural` and `cores` values in both
  ([v1.7.4 lines 1151-1187](https://github.com/tlaplus/tlaplus/blob/5a47802b5c391f59ecdd44117981f4ff8c0656ba/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1151-L1187),
  [1.8.0 line 1546](https://github.com/tlaplus/tlaplus/blob/bc1b506bdcad80bb518bf3776a9161c34ff0fc4c/tlatools/org.lamport.tlatools/src/tlc2/TLC.java#L1546)).
- Experiments: `tests/fixtures/research/19-workers-auto/` (`run.sh` the matrix, `cpu.sh` the `taskset` runs, outputs
  `matrix-java25.txt`, `matrix-java11.txt`, `taskset.txt`, `cgroup-quota.txt`, spec in `specs/`; the spec is a six-state
  counter that ends in a deadlock, so every successful start exits 11).

## Short answer

- Both builds accept `-workers auto`, on Java 25 and Java 11. Verified by running, and by reading the source: the
  option-parsing block is the same code in both commits, apart from a space in one error message.
- `auto` is `Runtime.getRuntime().availableProcessors()` and nothing else. It was 12 on the 12-core machine
  (`with 12 workers on 12 cores`). The match is case-insensitive and ignores surrounding spaces (`AUTO` and ` auto `
  work).
- Under `taskset -c 0-2` it gave 3 workers, under `taskset -c 5` 1 worker, under a cgroup quota (`systemd-run --user
  --scope -p CPUQuota=...`) 200% gave 2, 250% gave 3, 50% gave 1. The same on both builds and both Javas. The "cores"
  number in the startup line is the same value (`availableProcessors()`), so it shows the limit too.
- The startup line (message 2187, one line) reads the same on both builds, apart from the tail inside the parentheses
  (the JVM's name): `Running breadth-first search Model-Checking with fp <n> and seed <n> with 12 workers on 12 cores
  with 3415MB heap and 64MB offheap memory [pid: <n>] (Linux ..., <JVM vendor> <version> ..., MSBDiskFPSet,
  DiskStateQueue).` It says `1 worker` (singular) for one. With `-tool` the line is wrapped in
  `@!@!@STARTMSG 2187:0 @!@!@` ... `@!@!@ENDMSG 2187 @!@!@`, with the same text. The number is the plain worker count:
  nothing in the line says whether it came from `auto`.
- Bad values, identical on both builds and both Javas, exit code 1 each time, and no model checking starts:
  - `-workers 0` and `-workers -1`: `Error: at least one worker required.`
  - `-workers x`, `2.5`, and an empty string: `Error: worker number or 'auto' required. But encountered <value>`
  - `-workers` as the last argument: `Error: expect an integer or 'auto' for -workers option.`
  - `+3` is accepted (3 workers; Java's `Integer.parseInt`).
  Without `-tool` the text is printed as `Error: Error: ...` (the prefix twice) followed by `Usage: java tlc2.TLC
  [-option] inputfile` (v1.7.4) or `[-help] [-option]` (1.8.0). With `-tool` it is message 1102:1 (`@!@!@STARTMSG
  1102:1 @!@!@` ... `Error: at least one worker required.` and the usage line ... `@!@!@ENDMSG 1102 @!@!@`), after the
  version message 2262.

## Confidence

Verified (run on both jars and both Java versions; the source matches). Not run: Windows, macOS, a container runtime
with a real Docker or Kubernetes CPU limit (a systemd cgroup quota stands in for it; the JVM reads the same cgroup
files), Java 21 (not asked; the Java 25 and 11 results agree).

## Evidence

Source, the same in both commits (the 1.8.0 version differs only in the error text of `-dfid`, not of `-workers`):

```java
} else if (args[index].equals("-workers")) {
    index++;
    if (index < args.length) {
        try {
            int num = args[index].trim().toLowerCase().equals("auto")
                    ? Runtime.getRuntime().availableProcessors()
                    : Integer.parseInt(args[index]);
            if (num < 1) { printErrorMsg("Error: at least one worker required."); return false; }
            TLCGlobals.setNumWorkers(num);
            index++;
        } catch (Exception e) {
            printErrorMsg("Error: worker number or 'auto' required. But encountered " + args[index]);
            return false;
        }
    } else { printErrorMsg("Error: expect an integer or 'auto' for -workers option."); return false; }
```

The `-help` text of both builds says "defaults to 1. Use 'auto' to automatically select the number of threads based on
the number of available cores." (v1.7.4 `TLC.java` line 1434, 1.8.0 line 1878.)

Matrix command (`run.sh`, ran `tlc2.TLC [-tool] -workers <value> -metadir <tmp>/q19/meta -nowarning W`):

| value | v1.7.4 and 1.8.0, Java 25 and 11 |
| --- | --- |
| `auto`, `AUTO`, ` auto ` | `with 12 workers on 12 cores`, exit 11 (deadlock in the test spec) |
| `1`, `4`, `+3` | `with 1 worker`, `4 workers`, `3 workers`, exit 11 |
| `0`, `-1` | exit 1, `Error: at least one worker required.` |
| `x`, `2.5`, empty | exit 1, `Error: worker number or 'auto' required. But encountered ...` |
| missing value | exit 1, `Error: expect an integer or 'auto' for -workers option.` |

Counts over the two matrix files: 12 `12 workers` lines, 4 each for `1 worker`, `3 workers`, `4 workers`, in each file.
The Java 11 run of v1.7.4 and 1.8.0 gave the same lines; its startup line ends `(... Eclipse Adoptium 11.0.33 x86_64,
MSBDiskFPSet, DiskStateQueue)`.

Startup line with `-tool` (v1.7.4, `-workers auto`):

```
@!@!@STARTMSG 2187:0 @!@!@
Running breadth-first search Model-Checking with fp 113 and seed 5152671765734002002 with 12 workers on 12 cores with 3415MB heap and 64MB offheap memory [pid: N] (Linux x86-64, Debian 25.0.5 x86_64, MSBDiskFPSet, DiskStateQueue).
@!@!@ENDMSG 2187 @!@!@
```

Limits (`taskset.txt`, `cgroup-quota.txt`):

| limit | `availableProcessors()` and startup line, both builds, Java 25 and 11 |
| --- | --- |
| none | 12 workers on 12 cores |
| `taskset -c 0-2` (`nproc` 3) | 3 workers on 3 cores |
| `taskset -c 5` (`nproc` 1) | 1 worker on 1 cores (sic: "1 cores") |
| cgroup `CPUQuota=200%` | 2 workers on 2 cores |
| `CPUQuota=250%` | 3 workers on 3 cores (rounded up) |
| `CPUQuota=50%` | 1 worker on 1 cores |

## Implications for the roadmap

- R8's "Waiting on question 19" is resolved in favour of the primary design: both builds take `-workers auto`, so tlaup
  passes `-workers auto` unchanged on both and the Python fallback (`os.process_cpu_count()` and the others) is not
  needed. Nothing needs a per-build branch.
- TLC's `auto` respects `taskset` and cgroup quotas on Java 11 and 25, so the container case R8 worried about is covered
  by TLC itself.
- tlaup's own check of the `--workers` value can mirror TLC's: `auto` (TLC also accepts any case and surrounding spaces;
  tlaup may be stricter) or an integer of at least 1. TLC rejects 0, negative values and non-numbers itself with exit 1
  and `Error: ...`, so even without tlaup's check a bad value does not start a run; tlaup's check only makes the error
  earlier and clearer (exit 2). `+3` is accepted by TLC; whether tlaup accepts it is a design choice.
- The startup line does not tell whether `auto` was used; the tlaup output that wants to show "auto" must remember what
  it passed. A parser for message 2187 can read the plain count (`with N worker[s] on M core[s]`; note the singular
  `worker`, but `1 cores` stays plural).
- Test idea for R8: `--workers auto` on a one-core `taskset` yields `1 worker on 1 cores`.

## Open follow-ups

- Windows and macOS: `availableProcessors()` is a JVM property, no TLC code differs; unlikely to need a CI run. Not run.
- A real container limit (Docker `--cpus`) was not tried; a systemd CPU quota went through the same JVM code path.
- Whether a repeated `-workers` flag takes the last value (R8's rejected "last one wins"): from the source each
  occurrence calls `setNumWorkers` again, so the last one wins on both builds; not run.

## Date checked

2026-11-18 (jar identity per the brief; rolling asset checked 2026-11-19 UTC by the coordinator).
