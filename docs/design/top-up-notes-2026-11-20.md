# Notes after the top-up investigation, 2026-11-20

The maintainer walked through the seventeen top-up results ([research 19 to 35](../research/README.md)) with the agent that ran them, one question per step, on 2026-11-19 and 2026-11-20. For each question the agent gave the answer, what it means for the design and its own recommendation. This file records what the maintainer said during the walk-through. It changes no decision and no design section yet: the design documents still carry their "waiting on" wording.

Next, by the maintainer's plan: a separate session with a more capable model reads the result files and the design, without the recommendations below, and recommends its own solutions; the two sets are compared, and the outcome is worked into the design.

## To redesign later

### Kept run folders (research 25, with 34 and 35)

Research 25 found that TLC writes a checkpoint every 30 minutes without `-checkpoint`, on both builds. So every run stopped or crashed after about half an hour leaves a run folder under [R6](11-runner.md#r6-run-folders), and a large run's folder can be one to tens of gigabytes. Today R6 keeps such a folder for 30 days.

The maintainer wants this part redesigned at a later stage, not patched now:

- Large kept folders must be visible: where they are, how big, and why they were kept.
- A folder that is kept must really be resumable. Research 35 found that a checkpoint can be broken by a stop at the wrong moment, whatever stops TLC (Ctrl-C included), and that `-recover` can then exit 0 having missed states. Research 25 and 22 found that 1.8.0 warns on `-recover` without the run's `-seed` and `-fp`.
- Large folders left after runs the user will not resume, or is unsure about, need a solution.
- 30 days is too long. Even a day is too long when the user has not explicitly said the files are wanted. Keeping should be something the user asks for, not the default.

### Parser and run result (research 22)

The findings of research 22 go into the redesign for a deeper look, which may come up with an alternative to the agent's recommendation:

- `-difftrace` states can be completed by carrying unchanged variables forward (checked on 10 pairs), so the "print as TLC printed" fallback of [P5](10-parser.md#p5-error-traces) is not needed.
- `-dfid` traces use their own message codes (2216 on v1.7.4, 2217 on 1.8.0) and bare `N:` headers; the parser as designed would not recognise them.
- The error kinds P5 waited for now have codes: false `ASSUME` 2104, evaluation 2179, action property 2112, config 5001, 5003 and 2229.
- With `-continue`, TLC can print errors and still exit 0; a 4802-only spec makes TLC exit 150 while standalone SANY exits 0.

The agent recommended taking the first three into the parser design (with `-dfid` at low priority), building the run's result from TLC's messages with the exit code as a cross-check, and treating 4802 inside a TLC run as TLC does (a failure), while standalone SANY keeps it a warning. The maintainer agreed and asked that the redesign review this decision from the recorded results, without running the tests again.

## Agreed in the walk-through

The maintainer accepted the agent's recommendation for these questions:

- **19, `-workers auto`:** close the "waiting on 19" note in [R8](11-runner.md#r8-passthrough-and-workers); drop the Python CPU-count fallback; tlaup passes `auto` unchanged. tlaup's own check of `--workers` stays strict and refuses `+3`, which TLC accepts.
- **20, metadir creation:** close the "waiting on 20" note in [R9](11-runner.md#r9-show-command); the command `--show-command` prints is pasted as it is, with no platform note.
- **21, output encoding:** the Java launcher ([G3](20-groundwork.md#g3-java-launcher)) adds `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8` by default, for every tool it starts (`tlc`, `sany`, `pcal`). For non-ASCII file names under a non-UTF-8 locale, which no Java option fixes, tlaup gives a hint rather than changing the child's environment. R3's sentence that TLC's output does not follow the locale is corrected.
- **22, parser:** as above, with the review in the redesign.
- **23, Typer:** the lower bound becomes `typer>=0.27.2` (the first with a public `TyperException`); the CLI reference keeps the design's own script ([C5](23-command-layout.md#c5-help-and-the-cli-reference)), not `typer utils docs`.

## Still open

For 24 and 26 to 35, and for 25 beyond the redesign note above, the maintainer heard the agent's recommendation but did not settle it. They go to the independent session. The questions that matter most there are 35, 33 and 34 (which of R6's four options for a killed tlaup; the agent recommended option 4 with a Java agent that watches tlaup's process id), 30 (the `filelock>=4.2.1` and `rich>=13.8.0` bounds, how the RunFolders spec states the library's behaviour on release, and what a closed pipe on Windows exits with), and 25.
