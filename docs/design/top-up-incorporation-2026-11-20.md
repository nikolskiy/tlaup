# Working in the top-up answers, 2026-11-20

Written 2026-11-20 by the stage 3 design agent. It records how the answers to investigation questions 19 to 35 ([research](../research/README.md)), the [independent review](top-up-review-2026-11-20.md) and the maintainer's choices ([notes](top-up-notes-2026-11-20.md), "Settled after the review") were worked into the design documents, the specs of the formal check and the roadmap. Later stages read the sections and the roadmap, not this file: everything here is also said, with its reason, where it applies. Each change in a section is marked "top-up". Nothing was committed.

Where the investigating agent and the reviewer agreed, their shared recommendation was taken; where they differed, the maintainer's choice of 2026-11-20 was taken. Three points neither settled were then decided by the maintainer; see "Decisions needed" at the end.

## Per question

**19, `-workers auto`.** [11 R8](11-runner.md#r8-passthrough-and-workers): the "waiting" paragraph is replaced by the answer; tlaup passes `auto` unchanged on both builds, the Python CPU-count fallback goes, and tlaup's own check stays strict (it refuses `+3`). A test with `taskset` is added.

**20, `-metadir` creation.** [11 R9](11-runner.md#r9-show-command): the printed command is pasted as it is, no `mkdir` line, no platform note; what TLC prints when the folder cannot be made is stated. R9 also leaves the lifeline out (from 35).

**21, output encoding.** [20 G3](20-groundwork.md#g3-java-launcher) adds the three UTF-8 options in `argv()`, before the user's Java options and outside `java.opts`, for `tlc`, `sany`, `pcal` and `repl` (D56). [11 R3](11-runner.md#r3-non-utf-8-output) gets the facts, a preflight hint for non-ASCII file names under a non-UTF-8 locale, and the correction of its sentence that TLC's output does not follow the locale. [13 J1](13-modules-and-java.md#j1-java-options) and [21 S2](21-other-tools.md#s2-pcal) say what the options are for.

**22, more captures.** [10 P3](10-parser.md#p3-result-model) gains the verdict, `resumed` and `counts_approximate`, the events for checkpoints and recovery, and the mode `depth-first` (D54). [P5](10-parser.md#p5-error-traces): `-difftrace` states are completed by carrying variables forward (a `printed` flag per variable; the "print as TLC printed" fallback goes), the `-dfid` header and code 2216, the kinds of 2104, 2112, 2147, 2173, 2179, 5001, 5003 and 2229, and the rule that a 1000 holding one nested message with a kind takes that kind. [P8](10-parser.md#p8-sany-output): 4802 and the stuttering lints are errors and the table of warning texts goes (D55); the two warning forms and the stderr line are designed from their own captures. [22 O3](22-reporters.md#o3-terminal-reporter): the result line is built from the verdict with TLC's code beside it, and `show_states_as_printed` goes. [21 S1](21-other-tools.md#s1-sany) and [S5](21-other-tools.md#s5-golden-files-for-sany-and-pluscal): the stream question, 4802 and the `-d` width are settled, and the new captures are golden cases; [01 T3](01-testing.md#t3-golden-files) lists them. [40](40-later-milestones.md#milestone-4-automation-surface) gains open question 6, whether tlaup's own exit code should follow the verdict.

**23, Typer.** [14 F10](14-config-and-cli.md#f10-no-tracebacks): the facts now cover 0.22.0 to 0.29.2, and the bound is `typer>=0.27.2,<1.0.0` (D59, [30 B2](30-ci-and-release.md#b2-build-fixes)). [23 C3](23-command-layout.md#c3-completion): the completion modules are the same on every release. [C5](23-command-layout.md#c5-help-and-the-cli-reference): the script stays, not `typer utils docs`. [01 T5](01-testing.md#t5-feature-files-and-steps): two test rules, the reader closed before tlaup writes (no `| head -1` on short output) and SIGINT reset to the default in real-process test children.

**24, paths and links.** [11 R4](11-runner.md#r4-spec-cfg-and-working-folder): both "waiting" paragraphs are replaced; the changelog and help promise the rule for relative paths after `--` (all against the starting folder except `-config`); on Windows the spec's textual form is passed only when it names the same file, else `SpecNotFound`, and the relative `-config` is computed lexically. [R6](11-runner.md#r6-run-folders): a relative `-recover` path is resolved against the starting folder. [R8](11-runner.md#r8-passthrough-and-workers): the table's rows follow.

**25, default checkpoints.** [11 R6](11-runner.md#r6-run-folders) is rewritten around the facts: TLC checkpoints every 30 minutes by itself, kept folders are gigabytes, so keeping is asked for at the start and kept folders are visible (D53); tlaup passes `-fp` and `-seed` and repeats them on resume (D52). [14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay) gains `tlc.keep`; [20 G1](20-groundwork.md#g1-tlc-invocation) replaces `no_keep` with `keep` and adds `fp` and `seed`; [23 C1](23-command-layout.md#c1-command-tree) replaces `--no-keep` with `--keep` and adds `cache clean RUN_ID`.

**26, old jar commits.** [02 X3](02-cross-cutting.md#x3-version-syntax): every published jar has a commit, so the no-commit forms are for other jars only. [12 V5](12-tools-and-downloads.md#v5-download-and-verify): v1.7.1 confirms reading the commit from the jar, and a note for the future (peel annotated tags; warn, not fail, before v1.7.4).

**27, SANY and the library path.** [21 S1](21-other-tools.md#s1-sany): `sany` passes the same library path and classpath as `tlc`. [13 J1](13-modules-and-java.md#j1-java-options): v1.7.4's shared temporary module copies are named as a known gap, postponed until after the first implementation.

**28, Java 11 and macOS.** [13 J3](13-modules-and-java.md#j3-one-java-start): the minimum stays 11; on macOS every `java` and `javac` under `/usr/bin`, and any file that is `/usr/libexec/java_home`, is never remembered; the stub's "Unable to locate a Java Runtime" is `JavaNotFound`. [M3](13-modules-and-java.md#m3-module-build-details) and [11 R7](11-runner.md#r7-override-modules-that-do-not-load): the hint on 2173 names the class-file versions and the running Java; the check of class-file versions before a run is named as possible later. [30 I1](30-ci-and-release.md#i1-integration-job): the Java 11 cells.

**29, CI facts and recordings.** [30 I1](30-ci-and-release.md#i1-integration-job): Temurin 11 on macOS arm64, `macos-13` gone, the cache's immutability confirmed. [I2](30-ci-and-release.md#i2-unit-job): the newest Python is 3.15. [L2](30-ci-and-release.md#l2-release-workflow): every action pinned by commit, with the commits found (both reports recommend it; the first wording pinned only the actions of the two sensitive jobs). [12 V7](12-tools-and-downloads.md#v7-github-client) and [V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache), [01 T4](01-testing.md#t4-fakes-at-the-edges) and [T6](01-testing.md#t6-download-and-github-failure-tests): the real recordings; the `x-ratelimit-remaining: 0` test is the one that fires.

**30, library behaviours.** [30 B2](30-ci-and-release.md#b2-build-fixes): `filelock>=4.2.1`, `rich>=13.8.0` with the cap removed, the development dependencies' bounds (D59); `pydantic>=2.5.3`. [11 R6](11-runner.md#r6-run-folders): the lock behaviours by version, the `foreign_file` unit test beside the second-look test, the Windows end order, and the two rules (no `Deadlock` mapped to "busy", one thread per lock); [12 V11](12-tools-and-downloads.md#v11-concurrent-installs) the same for the store lock. [14 F10](14-config-and-cli.md#f10-no-tracebacks) and [02 X1](02-cross-cutting.md#x1-exit-codes): Windows' `EINVAL` is a closed pipe and exits 141 (D57); `reader_gone` registers for `POLLOUT` and reads `POLLERR` or `POLLHUP`. [14 F1](14-config-and-cli.md#f1-layered-configuration): the key is named from the field part of `loc`. [22 O4](22-reporters.md#o4-live-display): `pyte` works, so the fallback goes. [01 T4, T5, T10](01-testing.md#t4-fakes-at-the-edges): `responses` with `pytest-socket`, the short body as `ChunkedEncodingError`, pytest-bdd 9.0.1, coverage's subprocess patch. The specs gain the release-time unlink variant and the Windows argument (below).

**31, progress and a closed stdout.** [22 O3](22-reporters.md#o3-terminal-reporter) and [O4](22-reporters.md#o4-live-display): progress comes once a minute, so tlaup adds no spacing; the layout's long silences are said. [11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are): a closed stdout stops TLC in a raw run too, through `reader_gone(1)` in `run_passthrough`'s wait loop, not on Windows, where the help of `--raw` says TLC runs on (D58); [20 G3](20-groundwork.md#g3-java-launcher) gives `run_passthrough` the option.

**32, SANY and PlusCal working folder.** [21 S1](21-other-tools.md#s1-sany) and [S2](21-other-tools.md#s2-pcal): both stay in the spec's folder, with the reasons; SANY cannot follow D34.

**33, 34 and 35, a killed tlaup.** [11 R6](11-runner.md#r6-run-folders): option 4 on every system, the lifeline agent, plus option 3 on Linux and macOS, the inherited lock (D51); option 2 rejected as a liveness test and kept only to date a stopped run; the run's lock is tlaup's own descriptor through `lock_descriptor`, with tlaup's own wait and second look (`RunLock`); the release rule; the remaining window on Windows. The sweep can remove an unsettled folder at once. Checkpoints are trusted only when complete, and a first signal during one waits in a parsed run (D52). [20 G3](20-groundwork.md#g3-java-launcher): the agent, the jar (built in the release workflow or checked in, with a CI test that the shipped jar matches its source), `pass_fds`, no `preexec_fn`, the checkpoint row of the signal table, and the rejected alternatives; one test confirms `ProcessHandle.isAlive` against a reused process id on Java 11. [11 R2](11-runner.md#r2-signals) and [03](03-run-stages-and-specs.md) follow.

## New decisions

D51 to D59, dated 2026-11-20, in the roadmap's log and in the [design index](README.md#decisions-made-in-this-wave):

| # | Decision | Changes |
| --- | --- | --- |
| D51 | A killed tlaup's TLC ends: the lifeline everywhere, the inherited lock on Linux and macOS. | Settles R6's open choice (option 1 was held). |
| D52 | Only a complete checkpoint is trusted; `-fp` and `-seed` passed and repeated; a first signal during a checkpoint waits in a parsed run. | Changes G3's signal table and the Signals spec. |
| D53 | Keeping a run folder is asked for at the start; otherwise nothing is left; kept folders are visible and never removed silently. | Replaces the second half of D36 and D48, narrows D49. |
| D54 | The result is a verdict from TLC's messages, with `resumed`; the exit code stays TLC's, with a warning on disagreement. | Adds a milestone 4 open question. |
| D55 | 4802 is an error in `tlc` and `sany`. | Reverses the walk-through notes' first record. |
| D56 | The launcher always adds the three UTF-8 options. | |
| D57 | A closed pipe on Windows exits 141. | |
| D58 | A closed stdout stops TLC, raw runs included. | |
| D59 | `filelock>=4.2.1`, `rich>=13.8.0` uncapped, `typer>=0.27.2,<1.0.0`, `pydantic>=2.5.3`. | |

Choices 10 to 14 of the maintainer (the spec variant, Windows paths, the macOS Java rules, the walk-through's agreements, the smaller points) change no decision and are design details in their sections. Design-agent choices made on the way are listed in the [design index](README.md#decisions-the-design-agent-made) under "Made while working in the top-up answers"; the reviewer should look at those first.

Two items of the roadmap no longer match the design in wording, and the index lists them as departures: `--show-command` prints the exact command apart from the lifeline (D51), and SIGTERM is forwarded at once except during a checkpoint in a parsed run (D52).

## The specs

**RunFolders** ([`specs/RunFolders.tla`](../../specs/RunFolders.tla)):

- A constant `LockFollowsTLC`. With it, `Kill` hands the run's own lock and the recovered folder's lock to the orphan TLC (two new lock objects per run, `TLCOwn` and `TLCRec`) instead of releasing them, and `OrphanExit` releases them as the operating system does when the JVM ends. `OrphanExit` is fair (the lifeline).
- `keep` per run, chosen at the start and forced when `-recover` names a folder whose run asked; settle keeps only when the run asked, did not finish and has a complete checkpoint; the sweep never removes a kept folder, removes an unsettled one at once unless it is resumable, and keeps the 30-day rule only for folders with no `run.json`; `cache clean` spares a resumable unsettled folder (D49).
- Checkpoints in two steps (`CheckpointBegin` leaves `"tmp"`, `CheckpointEnd` makes it `"ok"`); a TLC that stops in between leaves an incomplete one.
- `NoDeleteUnderTLC` and `OneTLCPerFolder` hold without their exception for a killed tlaup; the weaker forms are `NoDeleteUnderLiveTLC` and `OneTLCPerFolderUnlessKilled`. `KeptSurvives` and `CheckpointSurvives` are restated for D53, `KeptIsComplete` is new, `LiveRunLocked` covers an orphan's lock, and `NothingLeft` excludes the folders that stay on purpose.
- A constant `UnlinkOnRelease` for filelock 3.20.4 to 3.29.4, applied to the visits' `FileLock` releases (the run's own lock is tlaup's and never unlinks).
- Configs: `orphan-delete` and `orphan-recover` became `windows-delete` and `windows-recover` (the window that remains without the inherited lock); `windows` (expect ok: the lock and live-run properties and the weaker forms), `windows-checkpoint` (expect `CheckpointSurvives` violated, finding K1-8 below) and `unlink-on-release` (expect `LockExclusive` violated, three processes) are new; every other config gained the two constants.

**Signals** ([`specs/Signals.tla`](../../specs/Signals.tla)):

- `TlaupDies` at any moment, to a phase `killed` in which no handler runs, and `LifelineEnds`, fair, which ends the child; the liveness property `ChildEndsWithTlaup`.
- A parsed run (`parsed`) and the parser's checkpoint mark (`chkpt`, set and cleared by `CheckpointBegin` and `CheckpointEnd`, the latter fair); with the constant `Defer`, a first signal during the mark is held and `CheckpointEnd` sends it on. `FirstSignalWaitsForCheckpoint` is new and `SignalReachesChild` is reworded.
- Configs: `no-deferral` (expect `FirstSignalWaitsForCheckpoint` violated) and `no-lifeline` (expect `ChildEndsWithTlaup` violated) are new.

**ToolStore** is unchanged and was checked again with the rest.

**Check results.** One run of `specs/check.sh` on 2026-11-20, with TLC 2026.05.26.235334 (rev 4ba7d88, the `v1.8.0` jar), OpenJDK 25.0.5, Linux, 12 cores, `-workers auto`: 30 configs in 1 h 44 min, 29 as their first line expects. The thirtieth, `RunFolders-windows`, expected `KeptSurvives` and `CheckpointSurvives` to hold on Windows, and TLC found that they do not (finding K1-8, below and in [the specs' README](../../specs/README.md#findings)). Those two were moved to a new variant, `RunFolders-windows-checkpoint`, and both configs were checked again with the same setup: `windows` holds (115,266,090 distinct states, 55 min) and `windows-checkpoint` fails as expected. So all 31 configs now come out as expected. The main `RunFolders` model holds with 97,386,562 distinct states in 51 min (16.6 million before the revision); `no-hour-rule` 80.4 million in 41 min; `Signals` 95,838 in 5 s; `ToolStore`, unchanged, 4,575,854 in 43 s. The specs' README has every row.

**Finding K1-8** (new). On Windows and network file systems, a resume started in the seconds after a kill, while the orphan TLC still runs with the lock free, that stops before its own TLC starts, decides to delete the folder; the orphan then commits a checkpoint and ends; and the resume's end deletes that checkpoint. It is the accepted window (D51, D15) with a cost that was not visible when the window was accepted, and the maintainer accepted it (item 3 under "Decisions needed"); [11 R6](11-runner.md#r6-run-folders) names it under Risks.

[Design 03, part 2](03-run-stages-and-specs.md#part-2-tla-specs-of-the-design) is updated to match and lists what the Hypothesis stateful tests in `tests/stateful/` must gain. **The test files were not changed**: they still mirror the specs of 2026-11-18. Bringing them up to the revised specs is work for before the formal check's review, or for the first work package that builds the run folders and the launcher.

Not done, as the brief asks: no upstream report was filed. The investigating agent suggested one, and the reviewer agreed, about TLC's checkpoint commit not being crash-safe (a stop between the queue's commit and the rest gives a `-recover` that exits 0 having missed states) and about `-recover` over-counting distinct states; contacting upstream is the maintainer's call.

## Decisions needed

None left. The maintainer settled the three points this pass raised on 2026-11-20:

1. **The `pydantic` floor: `pydantic>=2.5.3`**, with no lowest-versions CI job ([30 B2](30-ci-and-release.md#b2-build-fixes), D59). Research 30 shows the settings model working from 2.0 on, and 2.5.3 is the floor Typer 0.29 and later declare. The other options were a lowest-versions job with `pydantic>=2.0`, and keeping `pydantic>=2.12.5`.
2. **Which first signal waits for a checkpoint: all three**, SIGINT, SIGTERM and SIGHUP, as written ([20 G3](20-groundwork.md#g3-java-launcher), D52). The maintainer added that the user must be told at once that the signal was received and why tlaup waits; the waiting line now names the signal, with its own wording for SIGTERM.
3. **Finding K1-8: accepted and named**, as part of the window on Windows and network file systems (D51, D15; [11 R6](11-runner.md#r6-run-folders) Risks). The short wait before acting on a folder whose tlaup is gone was not taken.
