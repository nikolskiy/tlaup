# Review of the top-up investigation (questions 19 to 35)

Written 2026-11-20 by a fresh design reviewer (Claude Opus 5.5), for the maintainer, to compare with the recommendations of the agent that ran the investigation. It reviews the results of questions 19 to 35 in [`docs/research/`](../research/README.md) against the design sections they serve, the specs of the formal check ([`specs/README.md`](../../specs/README.md)) and the roadmap's decisions.

How it was written. Parts 1 to 3 were written first, from each result's Question, Short answer, Confidence and Evidence, the design sections and the specs. The reviewer had not read the results' "Implications for the roadmap" sections or the [top-up notes](top-up-notes-2026-11-20.md) at that point. Part 4, the comparison, was written after parts 1 to 3 were saved. Nothing was run for this review; where a claim below rests on the reviewer's own reasoning and not on a result, it says so.

Two terms used throughout:

- **Orphan TLC**: a TLC whose tlaup was killed (SIGKILL, a crash) while TLC went on running.
- **Lifeline agent**: the small `-javaagent` of [research 35](../research/35-jvm-ends-with-tlaup.md). It runs inside the JVM, watches tlaup's process id, and ends the JVM when tlaup is gone.

## Recommendations that change the most

**1. Take option 4 for a killed tlaup, with the lifeline agent in PID mode on every system; on Linux and macOS also let the JVM inherit the run's lock (option 3).** Research 35 shows the agent ends the JVM within about one to two seconds of any kill, on all three systems, for every tool, at a start-up cost of 20 to 40 ms. It does not touch stdin, so `tlaup repl` keeps working. Option 4 alone still leaves a window of about two seconds in which the lock is free and TLC still runs. Research 33 shows that on Linux and macOS a duplicate of the lock's descriptor, passed to the JVM, keeps the lock held until the JVM has gone. Together the two make "the lock is free" mean "no TLC runs here" exactly, on Linux and macOS. On Windows, and on network file systems, only the short window remains; D15 accepts that. Option 2 (ages from the last write) is rejected as a test of liveness: [research 34](../research/34-metadir-write-frequency.md) shows a simulation never writes. In the specs, `Kill` hands the run's locks to the orphan TLC instead of releasing them, the orphan's exit becomes fair, and the two properties that today carry an exception for a killed tlaup hold without it. In [20 G3](20-groundwork.md#g3-java-launcher) the launcher adds the agent to every Java start and `--show-command` leaves it out.

**2. A kept checkpoint is trusted only when it is complete, and the resume command repeats the run's fingerprint and seed.** Research 35 found that a stop in the middle of a checkpoint can leave a checkpoint that `-recover` accepts and then finishes with "no error" while it misses up to 69 % of the states. That is a wrong verdict, the worst thing tlaup can print. It also happens through tlaup's own Ctrl-C, since tlaup forwards SIGTERM. Every broken case in the research left `.tmp` files behind, and no finished checkpoint did. So R6's test "something is named `*.chkpt`" becomes: `queue.chkpt` and `vars.chkpt` are present and no file ending in `.tmp` (or rolling's `settings.tmp.chkpt`) is. A folder that fails the test is treated as one with no checkpoint. Separately, every recovered run in research 35 over-counted its states, while the one recovery in [research 25](../research/25-default-checkpoints.md) that repeated `-seed` and `-fp` gave the exact count. The reviewer's reading, not yet checked: the over-count comes from a different fingerprint polynomial on recovery. So tlaup should pass `-fp` and `-seed` itself when the user did not, record them in `run.json`, and repeat them in the resume command. In a parsed run, a first Ctrl-C that arrives while TLC is writing a checkpoint should wait for that checkpoint to finish.

**3. The run's result is decided from what TLC printed, not from its exit code.** [Research 22](../research/22-more-tool-captures.md) found TLC exiting 0 after two invariant violations (`-deadlock -continue`), exiting 0 after a depth-first search too shallow to find an existing violation, and never stopping under `-generate`. Today the reporter's result line is built from the exit code ([22 O3](22-reporters.md#o3-terminal-reporter)), so it would print a success for a run that found errors. The parser's result should carry a verdict: errors found, no error in a complete search, no error in a bounded search (simulation, `-dfid`, `-depth`), or incomplete (stopped, crashed, not started). It should also say when the run resumed from a checkpoint. The result line and the JSON are built from that verdict. The exit code stays TLC's (D29), and tlaup warns on stderr when the code and the verdict disagree. Changing the exit code instead is a real alternative and the maintainer's call.

**4. Every diagnostic SANY prints under "Semantic errors:" is an error, including 4802.** TLC refuses such a spec with 150 (research 22), so the design's table of "warnings" (P8) would make `tlaup sany` exit 0 for a spec `tlaup tlc` refuses. That breaks D29's promise that the two commands give the same number for the same spec. Only the PlusCal "changed since last translation" messages are true warnings.

**5. The Java launcher always adds `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8`.** [Research 21](../research/21-output-encoding.md) shows that without them TLC writes `?` for every non-ASCII character in a C locale and cp1252 on Windows. Worse, on v1.7.4 with Java 11 in a C locale, the PlusCal translator destroys non-ASCII text in the user's own `.tla` file. The three options fix every case tried. They belong to the launcher, before the user's options, not to the default of the setting `java.opts`, which a user can replace.

**6. Lower bounds: `filelock>=4.2.1`, `rich>=13.8.0` with the upper cap removed, `typer>=0.27.2,<1.0.0`.** Each is the earliest version for which everything the design relies on was shown to hold ([research 30](../research/30-library-behaviours.md), [research 23](../research/23-typer-versions.md)). On Windows a closed pipe raises `OSError` with `EINVAL`, not `BrokenPipeError`; tlaup should treat that as a closed pipe and exit 141 too.

## Question by question

Each section gives the answer and how far to trust it, what it changes in the design, the recommendation with its reason and any real alternative, and what the result leaves open.

### 19. `-workers auto`

**Answer.** Both builds accept `auto`, on Java 11 and 25, case-insensitively. It means `availableProcessors()`, which follows `taskset` and cgroup CPU quotas. Trusted: run on both builds and both Javas, and the option-parsing code is identical in the two commits. A real container runtime was not run; a systemd cgroup quota stood in for it, which reads the same kernel files.

**What it changes.** [11 R8](11-runner.md#r8-passthrough-and-workers), the paragraph "Waiting on question 19": the fallback that replaces `auto` with a number computed in Python is not needed.

**Recommendation.** Delete the fallback and pass `-workers auto` on both builds. TLC's own answer already honours CPU limits, which was the reason the design preferred it. tlaup's own check of `--workers` stays as designed (`auto` or a positive integer). It is stricter than TLC (TLC takes `+3` and ` auto `), which is fine for a tlaup option.

**Left open.** The startup line (2187) gives the worker count but not whether it came from `auto`. That matters only for the resume command (see 25): a resume on another machine gets another count, and rolling then warns that the settings differ.

### 20. Does TLC create a missing `-metadir`?

**Answer.** Yes, with all missing parents, on both builds, three Javas, Linux, macOS and Windows. Trusted.

**What it changes.** [11 R9](11-runner.md#r9-show-command), "Waiting on question 20": the pasted command works as printed.

**Recommendation.** Remove the waiting paragraph and the `mkdir -p` alternative. Keep the help line that advises replacing `-metadir` for a long run pasted by hand. With the lifeline agent (question 35) one more rule is needed here: the printed command must not contain the agent, because a pasted command would carry the process id of a tlaup that has already exited, and the JVM would stop at once. The help of `--show-command` can say that the printed command has no lifeline.

**Left open.** Nothing for the design. When a user's own `-metadir` cannot be created, TLC dies with a Java stack trace before its banner and exit 1; that text reaches the user as printed (D9), which is enough.

### 21. Output encoding

**Answer.** TLC, SANY and the translator write exactly what the JVM's stream encodings produce. UTF-8 locales give UTF-8; a C or POSIX locale gives US-ASCII with `?`; Windows gives cp1252; macOS is UTF-8 everywhere. The smallest set of options that fixed every case is `-Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8`. Trusted for Linux and for pipes on macOS and Windows. A real Latin-1 locale was not available; the stand-in is reasonable.

**What it changes.** [20 G3](20-groundwork.md#g3-java-launcher), "Encoding" ("Waiting on question 21"); [11 R3](11-runner.md#r3-non-utf-8-output), Rejected and Risks.

**Recommendation.** The launcher puts the three options first among the JVM options of every Java start (TLC, SANY, PlusCal, REPL), before the setting `java.opts` and the user's options, so that a user can still override one; the JVM takes the last value. Reasons: it removes the replacement characters in traces on Linux CI (often a C locale) and on Windows; on v1.7.4 with Java 11 it also makes TLC read a UTF-8 spec correctly; and it stops the PlusCal translator from writing `?` into the user's file, which is data loss, not cosmetics. Not putting them in the default of `java.opts`: a user who sets that setting would lose them without noticing. The cost: a spec saved in Latin-1 is now read as UTF-8 on Java 11. Java 18 and later already read files as UTF-8, so this aligns the old Java with the new.

**Alternative.** Only `-Dsun.stdout.encoding` and `-Dsun.stderr.encoding`: they work on every Java tried but are undocumented, and they do not fix reading the spec or the translator's file. Not recommended.

**Left open.** A non-ASCII spec or cfg path in a C locale cannot be fixed by a JVM option (1.8.0 dies with `InvalidPathException`). Two ways: a preflight warning when such a path meets a non-UTF-8 locale (cheap, recommended), or setting `LC_ALL=C.UTF-8` in the child's environment when the locale is C or POSIX (fixes it, but changes the child's environment behind the user's back; `C.UTF-8` is missing on some systems).

### 22. More TLC and SANY captures

**Answer.** All asked cases were captured on both builds with the two streams apart. The facts that matter for the design: TLC writes nothing to stderr in `-tool` mode except v1.7.4's `File does not exist` line for a missing module; `-difftrace` prints the first and (in model checking) the last state in full and only the changed variables between, and carrying variables forward rebuilds the full trace exactly (10 of 10 pairs); rolling prints action arguments in the header (`Step(1)`); `-dfid` uses message 2216 on v1.7.4 and a bare `1:` header; `ALIAS` and `-generate` do not exist on v1.7.4; the five error kinds without a capture now have one; 4802 alone makes TLC exit 150; SANY refuses grouped flags itself. Trusted: every row is a captured file on both builds; Java 25 and Linux only, which is enough for output shapes.

**What it changes.** [10 P5](10-parser.md#p5-error-traces) (`-difftrace`, headers, kinds), [P3](10-parser.md#p3-result-model) (mode, status), [P8](10-parser.md#p8-sany-output) (the severity table, the stderr line), [21 S1](21-other-tools.md#s1-sany) (the `-d` refusal), [22 O3](22-reporters.md#o3-terminal-reporter) (the result line), [01 T3](01-testing.md#t3-golden-files) (which captures become golden files).

**Recommendations.**

- **`-difftrace`.** Replace the interim rule ("print states as printed when `-difftrace` is given") with the verified rule: a state's missing variables are carried from the previous state, and each variable records whether TLC printed it in this state. The changed-variable display then works with and without the option. In `-simulate` and `-generate` the last state is partial too; the same rule covers it.
- **Headers.** Keep the action text as printed (`Step(1)` on rolling). Add the `-dfid` shape: a state message whose header is `^\d+: ?$` is a state with no action, and on v1.7.4 the code 2216 is a state message in a `-dfid` run. Without this every `-dfid` trace would become an unknown message.
- **Mode.** 2271 gives the mode "depth-first" (it is not in the Examples manifest's vocabulary, so the word is tlaup's); 2188 covers `-generate`.
- **Kinds.** 2104 is `assumption`; 2179 at the top level is `evaluation`; 2112 is `property` (an action property has no loop line, which the trace already shows); 5001, 5003 and 2229 are `config`; 2147 is `exception`. One rule more, so that the JSON is the same on both builds: when a top-level 1000 holds exactly one nested message whose code has a kind of its own (v1.7.4 nests 5001, 5003 and 2179 this way), the error takes that kind. The reporter still prints the whole message.
- **The result.** See the next heading.
- **SANY severity (P8).** Remove 4802 from the table of known warnings, and the table with it: TLC exits 150 for 4802 and for the two stuttering lints, so they are errors for every purpose a user has. `tlaup sany` then returns 150 for them, as D29 promises ("the number `tlaup tlc` returns for the same spec"). The PlusCal staleness messages stay warnings: TLC exits 0 and checks the model.
- **The stderr line (P8).** The v1.7.4 stderr line is `File does not exist`, not the diagnostic, so the design holds as written: in a TLC run it reaches the user on stderr, and the diagnostic comes from stdout. Remove the "Waiting on question 22" paragraph.
- **`-d` (S1).** SANY itself refuses `-dl` and the other grouped forms with exit 255 without starting the explorer, so tlaup's refusal of exactly `-d` is the right width. No change.
- **Golden files.** Adopt the new captures as golden files for both builds, including the two warning forms as files of their own and the v1.7.4 level errors.

**How a run's result is decided.** The exit code can mislead in three captured ways: `-deadlock -continue` with two violations exits 0; `-dfid` with a depth too small exits 0 while a violation exists; `-generate` on a correct spec never ends. A recovered run's state counts can be wrong (question 35). Recommendation: P3 gains a `verdict` that the parser and runner set from the messages, the mode and the way the run ended:

| Verdict | When |
| --- | --- |
| `errors` | At least one error opened (any severity 1 or 2 message, or a SANY error). |
| `no-error` | Finished (2186), no error, and an exhaustive search: breadth-first with no depth bound. |
| `no-error-bounded` | Finished, no error, and a bounded search: `-simulate`, `-generate`, `-dfid`, or `-depth`. |
| `incomplete` | Stopped by a signal, crashed, or ended without 2186. |
| `not-checked` | Stopped before model checking: a parse, config or usage error. |

A second field, `resumed`, is set when 2197 and 2198 arrive. The result line and the JSON are built from `verdict` and `resumed`, with TLC's exit code shown beside them, not in their place. When the exit code says success and the verdict says `errors`, tlaup prints one `warning:` line on stderr naming both. The exit code itself stays TLC's, as D29 and the roadmap's "Keep" list say.

The alternative is to make tlaup's exit code follow the verdict when the two disagree (for example 12 when TLC says 0 and errors were parsed). It protects a CI script that checks only the exit code. It costs the rule that tlaup's code is TLC's, and raw runs (which parse nothing) would then answer differently from parsed runs for the same spec. That is the maintainer's choice; the warning line is the smaller step and can come first.

**Left open.** Whether 2193 ("No error has been found") appears for every exhaustive success on both builds was not checked as a rule; the verdict above does not depend on it. A string argument that contains ` line 3, col 4 to ...` would break the header pattern; not produced, and the fallback (an unknown message shown as printed) is safe.

### 23. Typer across versions

**Answer.** Every Typer from 0.22.0 to 0.29.2 gave the same exit codes, completion behaviour and closed-pipe results as 0.29.1, with two exceptions: `typer.TyperException` is public only from 0.27.2, and before 0.26.0 Typer depends on a separate Click (with Click older than 8.2.1 a bare group exits 0). Trusted for the 13 versions run on Python 3.13; partly for the versions only scanned. `typer utils docs` works but its notation changes between releases.

**What it changes.** [30 B2](30-ci-and-release.md#b2-build-fixes) (the bound), [14 F10](14-config-and-cli.md#f10-no-tracebacks) (the sentence "Typer carries its own copy of Click"), [23 C3](23-command-layout.md#c3-completion), [23 C5](23-command-layout.md#c5-help-and-the-cli-reference).

**Recommendation.** `typer>=0.27.2,<1.0.0`. It is the earliest version where F10 and C3 can be written as designed without a fallback import. A lower floor buys nothing for a command-line tool that users install into its own environment, and it doubles what has to be tested. Keep tlaup's own reference generator in C5 rather than `typer utils docs`: the checked-in reference should change when help text changes, not when Typer changes its notation. F10's sentence about Click becomes true for every allowed version.

**Left open.** Python 3.11, 3.12 and 3.14 were not run; the newest-dependencies CI job covers the drift.

### 24. Path-taking flags and links

**Answer.** Every relative path given to a TLC flag is read against TLC's working folder, which is tlaup's starting folder (D34). The one exception is `-config`, read against the spec's folder. A cfg outside the spec's folder reached with `..` works on v1.7.4. TLC never resolves links: on Linux and macOS a `..` after a link is walked from the link's target, and R4's `relpath(realpath(...))` names the validated file in all ten layouts. Windows collapses `..` as text, so that computation is wrong there when a link is involved. Trusted: Linux in full, macOS and Windows in CI.

**What it changes.** [11 R4](11-runner.md#r4-spec-cfg-and-working-folder), steps 3 and 4 and "What changes for users"; [11 R8](11-runner.md#r8-passthrough-and-workers), the `-config` row; [11 R6](11-runner.md#r6-run-folders), `-recover`.

**Recommendations.**

- Remove both "Waiting on question 24" paragraphs of R4. The changelog and the help can now promise the rule: relative paths after `--` are read from the folder tlaup was started in, except `-config`, which is read from the spec's folder; `-dump` and `-userFile` need their folder to exist.
- On Windows, compute the relative `-config` from the absolute paths as text (`os.path.abspath` of both), not from `realpath`. That is what the Windows file API does, and it is one line. D15 means it is not tested in CI; a unit test of the function with the platform injected is enough.
- R6's `-recover PATH` rules: a relative `PATH` is resolved against the starting folder before "with links resolved, is inside `<cache>/runs/<id>/`" is decided. That is what TLC does (it reads `-recover` against its working folder), so tlaup and TLC agree on which folder is meant.

**Left open.** `-dumpTrace tlc` wrote no file in the research run; the design does not depend on it.

### 25. Checkpoints without `-checkpoint`

**Answer.** Both builds write a checkpoint every 30 minutes (30 min 42 ms) by default, in breadth-first and `-dfid` mode, counted from the JVM's start; `-simulate` never checkpoints; `-checkpoint 0` turns it off. Recovering on rolling without the original `-seed` and `-fp` prints warning 2285; with them it gave the exact state count. Trusted for the facts run (two builds, Linux, Java 25, one run each); `-dfid` and liveness from the source only.

**What it changes.** [11 R6](11-runner.md#r6-run-folders): "Why keep checkpoints" ("Waiting on question 25"), "Settle", "The resume command", Risks (size of kept folders), the sweep's rules.

**How often kept folders appear.** Every breadth-first run that is interrupted, or whose tlaup fails, more than about 31 minutes after it started, unless `--no-keep` is given. For anyone running long models this is common: a closed laptop lid, a CI timeout, a Ctrl-C to change a constant.

**Their size.** Not the checkpoint files alone: the whole timestamped folder is needed to resume (queue pool files, trace files, fingerprint files). Research 34 measured 1.6 GB after 15 minutes of a fast run without `-checkpoint`, and 3 GB with `-checkpoint 1`. Gigabytes per kept folder is the normal case for a run that lasted long enough to be kept.

**Recommendations.**

1. **Trust only a complete checkpoint** (from research 35; see question 35 for the evidence). Settle's condition 2 becomes: TLC's timestamped folder holds `queue.chkpt` and `vars.chkpt`, and no file whose name ends in `.tmp` or is `settings.tmp.chkpt`. The sweep and `cache clean` use the same test for unsettled folders (D49). A folder that fails it is settled as a folder with no checkpoint: deleted at the end, with no note. Reason: a resume from it either fails or, in one case, reports "no error" without exploring the whole state space. Keeping it would offer the user a command that can lie. The loss is small: some interrupted checkpoints that would still have recovered are deleted, because tlaup cannot tell them from the broken ones.
2. **Make the resume repeat the fingerprint and the seed.** tlaup passes `-fp <n>` and `-seed <n>` on every run where the user gave neither, chosen at random the way TLC would, records them in `run.json`, and the resume command repeats them. Reading them from message 2187 would work for parsed runs only; choosing them works for raw runs too. Reason: rolling warns on every plain resume, and the over-count after recovery (question 35) is most likely the fingerprint changing. The resume command should also carry the worker count the run used, where it is known (from 2187 in a parsed run), because rolling's settings check compares it too.
3. **Print the size in the note** ("Checkpoint kept (2.1 GB): ..."), and show sizes in `tlaup cache list`, so that a user sees the cost the moment it is incurred.
4. **Shorten the expiry of kept folders from 30 to 7 days.** A resume usually follows the interruption within hours or days; a kept folder of gigabytes for a month, on a laptop, is a cost the user did not choose. `tlaup cache clean --all` stays for removing one sooner. The alternative is to keep 30 days and rely on the printed size; that keeps more data for longer, which is the safer side for the rare late resume. Either is defensible; the reviewer prefers 7.
5. **The checkpoint after 30 minutes is not on by tlaup's choice.** tlaup should not change TLC's default (no `-checkpoint 0` by default): a long run that is interrupted is exactly the case R6 exists for. `--no-keep` (D48) covers the trial runs.

**Left open.** Whether matching `-fp` and `-seed` removes the over-count on v1.7.4 too, and on `-workers 2`; a run is needed (see 35). Whether `-fp` and `-seed` exist with the same meaning on v1.7.4 (the reviewer believes so; a capture is needed before the design relies on it).

### 26. Commits in older jars

**Answer.** Every published `tla2tools.jar`, back to v1.5.6, carries `X-Git-Revision`; older releases have no jar. Only v1.8.0 and rolling carry a build time. The v1.7.1 jar was built from a commit other than its tag's. Trusted: all nine manifests read.

**What it changes.** [12 V1](12-tools-and-downloads.md#v1-version-store), [V5](12-tools-and-downloads.md#v5-download-and-verify), [02 X3](02-cross-cutting.md#x3-version-syntax).

**Recommendation.** Keep the printed form for a build with no commit, with one unit test, but remove the "waiting" wording: it is never seen for a published jar and remains only for a jar that tlaup builds or that a future upstream publishes without the entry. v1.7.1 confirms the design's choice to take a build's commit from the jar, not from the tag; say so in V5. A build with a commit and no build time is the normal case for every stable release, so the shortest printed form for those is `name@commit`, which is already the rule.

**Left open.** Nothing.

### 27. Standalone SANY and the library path

**Answer.** Standalone SANY honours `-DTLA-Library` and the classpath exactly as TLC does, on both builds. It does not search the spec's folder when started elsewhere. v1.7.4 copies every module it reads from a jar into `<java.io.tmpdir>/<Module>.tla`, a shared fixed name. TLC v1.7.4 cannot load the CommunityModules jars at all. Trusted on Linux; macOS and Windows not run.

**What it changes.** [21 S1](21-other-tools.md#s1-sany).

**Recommendation.** `tlaup sany` passes the same library path and classpath as `tlaup tlc` builds (modules, override jars), and keeps running in the spec's folder (see 32). Then SANY and TLC find the same modules, because TLC also uses the spec's folder as its working folder for module lookup.

**Left open.** Two things outside S1, worth a line each in the design. First, v1.7.4's shared temporary copies: two v1.7.4 runs at once write the same `/tmp/<Module>.tla` files (read from the source, not tried). Passing `-Djava.io.tmpdir=<run folder>/tmp` for TLC runs would remove the collision and also the files a killed JVM leaves behind (research 35: `deleteOnExit` does not run after SIGKILL); it needs one run on both builds before the design relies on it. Second, CommunityModules do not load on v1.7.4: that belongs to the design note of milestone 3 (D11).

### 28. Java 11 and the macOS `java`

**Answer.** Both builds run on Java 11; the minimum stays 11. An override class too new for the running Java gives message 2173 (the index class) or 1000 with `UnsupportedClassVersionError` (a class it lists), exit 255. `--release 11` classes load on 11, 21 and 25. The macOS `/usr/bin/java` is a stub that picks a JDK each time, honours `JAVA_HOME`, and `exec`s the JDK, so the process id stays the JVM's. With no JDK it exits 1 with "Unable to locate a Java Runtime". Trusted: Linux, Ubuntu and macOS runners.

**What it changes.** [13 J3](13-modules-and-java.md#j3-one-java-start), [M3](13-modules-and-java.md#m3-module-build-details), [11 R7](11-runner.md#r7-override-modules-that-do-not-load) part 4, [30 I1](30-ci-and-release.md#i1-integration-job).

**Recommendations.**

- R7's hint for a class that cannot be read must fire on 2173 as well as on 1000. As written it keys on 1000 only and would stay silent for the more common case (the index class itself compiled too new). The text of 2173 names the class and both class-file versions, so the hint can say "rebuild with `tlaup module add` (which compiles with `--release 11`)".
- J3's rule "never remember `/usr/bin/java` on macOS" is now a fact, not a precaution; keep it.
- The version check should recognise the stub's "Unable to locate a Java Runtime" (exit 1, nothing on stdout) and report `JavaNotFound`, code 3, with the hint to install a JDK, instead of a failed version parse.
- The process id staying the JVM's means signals and the lifeline reach the JVM directly on macOS; nothing in G3 changes.

**Left open.** Java 17 and 8 were not run; neither is a supported minimum, so nothing waits.

### 29. CI facts and recordings

**Answer.** Temurin 11 exists for macOS arm64; `macos-13` is gone; the newest CPython is 3.15.2; every action is several major versions ahead of the workflows; `setup-uv` has no major-version tag; recordings of paging and of a rate-limit 403 were made. Trusted, as of 2026-11-19; these facts age fast.

**What it changes.** [30 I1](30-ci-and-release.md#i1-integration-job), [I2](30-ci-and-release.md#i2-unit-job), [L2](30-ci-and-release.md#l2-release-workflow), [12 V7](12-tools-and-downloads.md#v7-github-client), [V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache), [01 T4](01-testing.md#t4-fakes-at-the-edges), [T6](01-testing.md#t6-download-and-github-failure-tests).

**Recommendation.** Use the recordings as the T4 and T6 fixtures. Pin each action by the commit SHA found, with the release named in a comment, and let Dependabot (D44) move them; `setup-uv` is pinned by its full tag. Keep `macos-latest` as the only macOS cell; an Intel cell (`macos-15-intel`) is not needed for anything the design checks. The newest-Python job uses 3.15. The work package that writes the workflows should look the SHAs up again on the day, since a week-old pin is already behind.

**Left open.** A 429 response was not seen; the design treats it like a 403 with `Retry-After`, which stays a synthetic case.

### 30. Library behaviours

**Answer.** The second look of `filelock` arrived in 3.20.4, but 3.20.4 to 3.29.4 also delete the lock file by name on release, which breaks mutual exclusion in a new way; 3.29.5 to 4.2.0 change the lock file's modification time when locking, which the one-hour rule reads. 4.2.1 is the first version where everything R6 relies on holds, on Linux, macOS and Windows. Rich's `on_broken_pipe` exists from 13.8.0 and behaves the same up to 15.0.0, as does its live display on the alternate screen. On Windows a write to a pipe whose reader has gone raises `OSError` with `EINVAL`. `pyte`, coverage's subprocess patch, pytest-bdd 9.0.1, `responses` and Pydantic 2.0 and later work as the test design assumes, with the details below. Trusted: filelock on every release on Linux and eight on macOS and Windows; Rich on six versions; the rest on Linux.

**What it changes.** [30 B2](30-ci-and-release.md#b2-build-fixes) (bounds), [11 R6](11-runner.md#r6-run-folders) Risks, [14 F10](14-config-and-cli.md#f10-no-tracebacks) and [02 X1](02-cross-cutting.md#x1-exit-codes) (Windows), [22 O4](22-reporters.md#o4-live-display), [01 T4, T5, T10](01-testing.md#t4-fakes-at-the-edges).

**Recommendations.**

- **`filelock>=4.2.1`.** The unit test R6 already names (the waiter ends up on the file at the path) stays, and gains the two checks that tell the bad version ranges apart: after a release the lock file still exists, and taking or releasing the lock leaves its modification time alone. Then a later filelock that changes either is caught on the newest-dependencies job.
- **A lock library that deletes the lock file by name on release, in the RunFolders spec.** On Linux and macOS no allowed version does this, so the main spec should not model it. Add one variant that does, expected to break `LockExclusive`, so that the reason for the lower bound is checked and not only stated; it is a small change to `Release`. On Windows every version deletes on release, but Windows refuses to delete a file that any process has open, so the release-time delete removes the file only when nobody holds or waits on it, and the probe found exclusion intact. Record that argument in the spec's README beside "Windows" under "Leaves out", rather than modelling Windows; D15 does not ask for more. R6 should also say that on Windows lock files do not outlive their release, so the one-hour rule for folderless lock files does nothing there, harmlessly.
- **`rich>=13.8.0`, and remove the cap `<14`.** Every version from 13.8.0 to 15.0.0 behaved the same for the closed pipe and the live display. The newest-dependencies job and the real-process scenarios are the guard against a future change.
- **A closed pipe on Windows exits 141.** F10's handler treats an `OSError` with `errno == EINVAL` raised by a write to stdout or stderr as a closed pipe when that stream is a pipe (on Windows, `os.fstat(fd)` reports a FIFO for a pipe; to be confirmed by the worker) and then takes the same path as `BrokenPipeError`: no message, 141. Reasons: F10 promises no traceback, and today's result on Windows is a traceback and exit 1; and one code for one situation on every system keeps scripts portable. The alternative, code 5 with "cannot write output", is what F10's general rule would give, but `tlaup tool list | more` closed early is not a failure. A test can only be a unit test with an injected error (no Windows CI, D15).
- **`select.poll` on macOS.** Register the descriptor for `POLLOUT` and read `POLLERR` or `POLLHUP` as "reader gone"; an empty mask reports nothing on macOS. Treat `POLLNVAL` as "not a pipe". F10's `reader_gone` should say both in so many words.
- **Pydantic.** Set the floor where CI can test it. If the lowest-dependencies run uses Python 3.11, `pydantic>=2.0` is proven; otherwise use the lowest version that has wheels for the lowest Python CI runs. F1's message builder must name the key from the field part of `loc`, not the whole tuple (a union field puts its member's tag in `loc`).
- **Test tools.** `pytest-bdd>=9.0.1` (the only version that works with the locked pytest); doc strings arrive as the `docstring` argument. `coverage>=7.10.6` with `patch = ["subprocess"]`; a child killed by an unhandled signal loses its coverage, which is expected and needs no workaround. For `responses`, a body shorter than its `Content-Length` makes `requests` raise `ChunkedEncodingError`; T6's truncated-download case asserts that tlaup catches it and reports the download as failed. Under `pytest-socket` 0.8 with `-W error`, a blocked socket surfaces as `UserWarning`; T4 should not assert on `SocketBlockedError` by type. `pyte` reports bold green as `brightgreen`; O4's screen checks compare colours with that in mind.
- **filelock and one thread.** Since 3.29.6 a second lock object waiting with no timeout in the same thread raises `RuntimeError("Deadlock ...")`. Every wait in R6 and V11 has a finite timeout, so the design is not affected; V11 should say that the store lock is never waited for without a timeout, so it stays that way.

**Left open.** Resizing the terminal under the live layout was not tried (pyte). Windows Rich behaviour was tried for pipes only, not for a console.

### 31. Progress interval and a closed stdout

**Answer.** TLC prints progress every 60 seconds (the first about 3 seconds after the initial states); simulation every 60 seconds from the start. Rolling takes `-Dtlc2.TLC.progressInterval`; v1.7.4 has no way to change it. A checkpoint or a slow state delays the next line (research 34 saw 12 minutes without one). The JVM does not stop when its stdout's reader goes: TLC runs to the end unseen, with its real exit code. Trusted on Linux; the closed-pipe case also on macOS and Windows.

**What it changes.** [22 O3](22-reporters.md#o3-terminal-reporter) (plain progress), [11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are) ("Waiting on question 31"), [22 O4](22-reporters.md#o4-live-display).

**Recommendations.**

- Plain mode prints progress lines as TLC sends them; TLC already spaces them at 60 seconds, so no spacing of tlaup's own is needed. The live display must not treat a long silence as a hang: its elapsed time comes from the refresh thread, which O4 already has.
- **`tlaup tlc --raw Spec | head` should stop TLC.** The design accepted documenting that TLC runs on. A cheaper fix exists in the design already: `run_passthrough` waits in steps of a fifth of a second, and F10 has `reader_gone(1)`. In each step, if tlaup's stdout is a pipe whose reader has gone, the launcher terminates the child as for a first signal and the run ends with 141, as a parsed run does. That makes raw and parsed runs behave alike, and it stops a run nobody can see from holding CPUs for hours. On Windows, where `poll` is missing, the help text says TLC runs on.
- Do not set `tlc2.TLC.progressInterval` by default. Users who want faster progress on rolling can pass it with `--java-opt`.

**Left open.** The extra progress line before the liveness check, and the last line of a clean finish in `-tool` mode, were read from the source only; the parser takes progress messages wherever they come, so nothing waits.

### 32. SANY and PlusCal in the starting folder

**Answer.** SANY does not behave the same: started elsewhere with an absolute spec, it does not find the modules beside the spec, and a module in the starting folder would shadow them. The translator behaves the same apart from `-writeAST`, which writes into the working folder, and the file names in its messages, which follow the argument as given. Trusted on Linux for both builds.

**What it changes.** [21 S1](21-other-tools.md#s1-sany), [S2](21-other-tools.md#s2-pcal).

**Recommendation.** Keep the design as it stands: `sany` and `pcal` run in the spec's folder with the bare file name. For SANY there is no other correct choice: putting the spec's folder on `-DTLA-Library` still lets a file in the starting folder win. It is also what TLC does internally (it searches the spec's folder first), so `tlaup sany` and `tlaup tlc` see the same modules. For `pcal` the starting folder would work, but one rule for the two tools that read a spec file on their own is easier to explain, and the translator's messages then name the file briefly. The difference from `tlc` (D34) is explained in the help of `sany` and `pcal` in one line: they read the spec from its own folder.

**Left open.** Symbolic links to the spec's folder were not tried for SANY. Running in "the spec's folder" should mean the folder as the user named it (not resolved), as R4 does for TLC.

### 33. Letting the JVM inherit the run's lock

**Answer.** On Linux and macOS, yes: a `flock` belongs to the open file description, so a JVM started with a copy of the descriptor keeps the lock after tlaup is killed, until the JVM ends. The JVM and TLC leave the descriptor alone, on both builds and three Javas. `filelock` gives the descriptor through its public `on_acquired` hook, but calls it borrowed. A normal `release()` in tlaup ends the JVM's hold too. `preexec_fn` makes `Popen` fail with a filelock descriptor (an `os.dup` survives). A POSIX record lock (`lockf`) is not kept. On Windows the `filelock` lock does not follow the child; a share-mode handle would. Trusted: Linux in full, macOS and Windows on one CI run each; NFS not tried.

**What it changes.** [11 R6](11-runner.md#r6-run-folders), Risks, option 3; [20 G3](20-groundwork.md#g3-java-launcher), `run_streaming` and `run_passthrough` (a `pass_fds` argument); [`specs/RunFolders.tla`](../../specs/RunFolders.tla), the `Kill` action.

**Recommendation.** Take option 3 on Linux and macOS as a complement to option 4, not instead of it (see 35 for the whole argument). The mechanics:

- In the `on_acquired` hook, tlaup duplicates the descriptor (`os.dup`) and keeps the duplicate; it never closes, unlocks or keeps the borrowed one, which is what the hook's contract asks. The duplicate of the run's own lock, and of the recovered run's lock after `-recover`, go to the JVM in `pass_fds`. tlaup closes its duplicates after `Popen`.
- No `preexec_fn` anywhere in the launcher (option 4 does not need one).
- The release order stays as R6 has it: the lock is released only after the child is gone. That is already guaranteed by the launcher's `finally` and the frame; R6 should name it as a rule, because a release while the JVM lives would now free the JVM's hold too.
- A unit test pins the property: a child holding the duplicate keeps the lock after its parent is killed with SIGKILL, and loses it when the child ends. A `filelock` that switched to per-process locks fails it.

On Windows and on network file systems the lock is not inherited; the window of option 4 alone remains there (about two seconds), which D15 accepts.

**Alternative.** Option 3 without option 4: it closes the lock question, but an orphan TLC then holds its folder for as long as it runs, possibly days, invisible and using every core. The maintainer's reason for option 4 (an orphan TLC serves no purpose) stands; option 3 alone is not enough.

**Left open.** NFS (Linux emulates `flock` with POSIX locks there, which are per process); a share-mode lock for Windows, if Windows ever matters more than D15 says.

### 34. How often TLC writes under its `-metadir`

**Answer.** A breadth-first run that keeps finding states writes every second. But TLC can work for a long time without writing: 30 minutes for few expensive states (until the default checkpoint), 12 minutes for one slow state, the whole final liveness check, and for ever in `-simulate`, `-generate` or `-dfid` without a checkpoint. So "nothing written for a day" does not mean "no TLC here". Trusted: measured on both builds on Linux; the longest silences beyond the runs come from the source and from scaling.

**What it changes.** [11 R6](11-runner.md#r6-run-folders), Risks, option 2, and the sweep's ages for unsettled folders (finding K1-5).

**Recommendation.** Reject option 2 as a way to tell whether TLC is running. A simulation of a day leaves a folder whose last write is its first second, and the sweep would delete it under the live TLC. Once options 4 and 3 hold (35), the question it was meant to answer no longer exists: a free lock means no TLC. The measurement is then still useful for a different purpose: the 30-day (or 7-day, see 25) age of a folder that was never settled and holds a complete checkpoint should count from the newest modification time of anything under it, which is when the run stopped, not from `started`. That gives a run killed after 29 days its full time to be resumed, and K1-5's surprise goes away. Research 34 says how to read it: the newest mtime over every entry, files and folders, recursively.

**Left open.** A machine suspended for longer than the age: under options 4 and 3 that no longer matters for safety, only for how long a folder is kept.

### 35. Making the JVM end with tlaup

**Answer.** Yes, on Linux, macOS and Windows, by several means. The lifeline agent in PID mode works the same on all three, for every tool, with `-Xrs`, and under `tlaup repl`; it ends the JVM 0.1 to 1.6 seconds after tlaup dies and costs 19 to 43 ms at start-up. The parent-death signal works on Linux only and is tied to the thread that started the child. The pipe and stdin variants delay every JVM exit by up to 1.7 seconds, and the stdin variant breaks the REPL. A watcher process and a Windows job object work too. Separately and more importantly: neither build registers a shutdown hook, and a checkpoint is not atomic. A stop in the middle of one, by any means including tlaup's own SIGTERM, can break it, and one case recovers with exit 0 and misses states. Every recovery over-counted by 0.1 to 1.7 %. Trusted for the mechanisms (three systems, two jars, three Javas). The checkpoint cases are single runs at chosen breakpoints on Linux, but they exercise TLC's own code, which does not depend on the system.

**What it changes.** [11 R6](11-runner.md#r6-run-folders), Risks (the choice of option), Settle (what counts as a checkpoint), the resume command; [20 G3](20-groundwork.md#g3-java-launcher) (the launcher adds the agent; the signal table); [11 R9](11-runner.md#r9-show-command); [`specs/RunFolders.tla`](../../specs/RunFolders.tla) and [`specs/Signals.tla`](../../specs/Signals.tla); the stateful tests.

**Recommendation: option 4 by the lifeline agent in PID mode, plus option 3 on Linux and macOS.**

Why the agent and not the others: it is one mechanism on all three systems; it lives inside the JVM, so it cannot be killed apart from it, unlike a watcher process; it needs no `preexec_fn`, so it does not clash with the inherited lock (33) or with Python's threads; it leaves stdin alone. Its cost is a small jar shipped with tlaup and about 30 ms per Java start.

Why option 3 as well: with the agent alone, after a kill the lock is free for one to two seconds while TLC still runs. A `cache clean`, a sweep of an old folder, or a `-recover` in that window would act on a live run. The window is small, but the inherited lock closes it exactly on the two systems the design supports, for the price of a `pass_fds`.

What the design gains: a free lock means no TLC runs in the folder. The sweep, `cache clean` and `-recover` rule 2 are then right without an exception, the accepted risk in R6 goes, and the K1-3 finding (a second TLC on one checkpoint) cannot happen.

**Details for the launcher (G3).**

- The agent jar is package data in the wheel. Its Java source is in the repository, compiled with `--release 11`, and a test checks that the shipped jar was built from that source, so a binary nobody can read is never shipped. How the jar is built for a release (a build step, or a checked-in jar with that test) is a decision for the work package.
- The launcher puts `-javaagent:<jar>=pid=<tlaup pid>` first among the JVM options, for every tool. A `lifeline: bool = True` field on `JavaInvocation` lets `--show-command` leave it out (20).
- The agent should check the process's start time as well as its id (`ProcessHandle.info().startInstant()`, read once when the agent starts), so that a process id reused within the poll interval is not taken for tlaup. The research's agent did not; it is a small addition and needs one test.
- The agent's poll interval of 500 ms gave about one second. That is fine; a shorter interval buys little.
- The signal table of G3 does not change for signals tlaup receives. The agent matters only when tlaup cannot act. Its exit code (143) is never seen by anyone.

**Details for checkpoints (R6 and G3).**

- The completeness test of 25 applies to every kept or unsettled folder.
- In a parsed run, the parser sees 2195 ("Checkpointing of run") and 2196 ("Checkpointing completed"). A first signal that arrives between the two is recorded but not forwarded until 2196 arrives; tlaup says on stderr that it is waiting for TLC to finish its checkpoint and that a second Ctrl-C stops at once. A second signal acts at once, as now. The grace period (10 seconds, then `kill()`) does not start until the signal has been forwarded, so tlaup never kills TLC itself in the middle of a checkpoint. This changes G3's table (one row, "while a checkpoint is being written") and Signals.tla (below). In a raw run tlaup sees no messages, and the completeness test is the only protection.
- A resumed run is marked `resumed` in the result (22), and its state counts are shown as approximate until the `-fp` question is settled.

**What changes in the specs.**

- `RunFolders.tla`. `Kill(p)` no longer releases the locks of `p`'s run when its TLC is live: the lock objects pass to the orphan TLC (a constant `LockFollowsTLC`, TRUE for Linux and macOS). `OrphanExit(r)` releases them. `OrphanExit` gets weak fairness in `Fairness` (option 4: the orphan always ends). `Checkpoint(r)` gains a "broken" outcome when the TLC is stopped during it, and `Settle` and the sweep keep only a complete one; a new property `KeptIsComplete` says no folder is kept or spared because of a broken checkpoint. With these, `NoDeleteUnderOrphanTLC` and `OneTLCPerFolderAfterKill` should hold, and become the main properties in place of `NoDeleteUnderTLC` and `OneTLCPerFolder` with their exceptions. A variant with `LockFollowsTLC = FALSE` (Windows, NFS) is expected to fail them, and documents the window that remains there. The orphan-recover and orphan-delete variants change their expectation accordingly.
- `Signals.tla`. Today it leaves out a SIGKILL of tlaup. Add an action `TlaupDies` (SIGKILL or a crash, at any moment), after which the handlers are gone and the child must end: a liveness property `ChildEndsWithTlaup` under fairness of the child's end, standing for the agent. Add the checkpoint rule if it is taken: the child has a "checkpointing" phase, a first signal in it is held until the phase ends, and `SignalReachesChild` is reworded to "reaches the child once its checkpoint is written, or at the second signal".
- The stateful tests follow the specs: the run-folder machine's kill rule keeps the child's descriptor open in a child process until the model's orphan exits; the signals machine gains the kill of the tlaup stand-in, which needs a child process for tlaup itself.

**Left open.**

- Whether matching `-fp` (and `-seed`) removes the over-count, on both builds and with several workers. This decides whether resumed counts can be called exact. One run per build with the research's `Wide` spec answers it.
- The cause of the late JVM exit with a thread blocked on a pipe; irrelevant once the PID mode is chosen.
- A console-script launcher on Windows (`tlaup.exe`) that may itself use a job object; the agent covers both cases anyway.
- Whether a checkpoint message (2195, 2196) is always printed in `-tool` mode around the commit, on both builds, at the moments the deferral needs. Research 22 captured both messages; their exact place relative to the commit should be read from the source before the deferral is designed in detail.

## Comparison

Written after parts 2 and 3 were saved, from the [top-up notes](top-up-notes-2026-11-20.md) and the "Implications for the roadmap" section of each result file. "The agent" is the agent that ran the investigation and walked the maintainer through it. Parts 2 and 3 are left as they were written; where this comparison changes the reviewer's mind, it says so here.

### Question by question

**19, `-workers auto`.** Agree. The maintainer accepted the same thing: pass `auto` unchanged, drop the fallback, keep tlaup's check strict.

**20, `-metadir` creation.** Agree. The agent and the reviewer both found one consequence of question 35 here: `--show-command` must leave the lifeline agent out of the printed command.

**21, encoding.** Agree on the three options and on giving a hint rather than changing the child's locale for non-ASCII file names; the maintainer accepted both. Two small differences. The notes name `tlc`, `sany` and `pcal`; the reviewer would add `repl`, which evaluates `Print` and shows values, for the same reason. And the reviewer places the options in the launcher before `java.opts`, not in the setting's default, so that a user who sets `java.opts` does not lose them; the agent's text does not say where they go.

**22, parser.** Agree with all three parser changes (`-difftrace` carried forward, the `-dfid` shape, the new kinds) and with building the result from TLC's messages with the exit code as a cross-check. The reviewer adds the rule that a 1000 holding one nested message with a kind of its own takes that kind; the agent states the same for 5001 and 5003 ("the nested codes decide the kind, as the design already does for 5006"), so this is agreement in substance. One real difference, on 4802: see "Parser and run result" below.

**23, Typer.** Agree: `typer>=0.27.2,<1.0.0`, and keep the design's own reference script. The maintainer accepted both. The agent adds two test details worth taking: reset SIGINT to the default in real-process test children, and do not use `| head -1` on short output (the closed-before-start form is not racy).

**24, paths and links.** Agree, and the agent found something the reviewer missed. On Windows, a `..` after a link in the spec path itself makes the spec not found, so R4 step 3 ("otherwise the path is passed with its `..` in place") also fails there, not only step 4. The agent's fix, to pass the textual form on Windows only when it names the same file, is the right one. Both recommend the lexical `relpath` for the cfg on Windows.

**25, default checkpoints.** The facts and the measures agree: the stricter checkpoint test, `-fp` and `-seed` in the resume command, sizes in the note and in `tlaup cache`. The agent leaves open whether tlaup reads `-fp` and `-seed` from the banner or always passes them; the reviewer recommends always passing them, because that works for raw runs too. The reviewer's recommendation of a 7-day expiry for kept folders does not meet the maintainer's requirement that keeping should be something the user asks for. It is withdrawn in favour of the direction under "Kept run folders" below.

**26, old jar commits.** Agree. The agent adds that any future check against a tag's commit must peel annotated tags and must be a warning for releases older than v1.7.4 (v1.7.1); the design reads no tag commits, so this is a note for the future, not a change.

**27, SANY and the library path.** Agree that `tlaup sany` passes the same library path and classpath as `tlaup tlc`. The reviewer adds a per-run `java.io.tmpdir` for v1.7.4's shared temporary module copies, which needs one run before it is designed; the agent lists the same collision as an open follow-up.

**28, Java 11 and macOS.** Agree on all points. The agent goes a little further in two places, both worth taking: exclude from remembering every `java` and `javac` directly under `/usr/bin` on macOS (or any file that is the same file as `/usr/libexec/java_home`), and a cheap check before the run that compares the highest class-file version under `classes/` with the running Java. The second is optional; the hint on 2173 is the necessary part.

**29, CI facts.** Agree. The agent adds that the real 403 has no `Retry-After`, so V7's `x-ratelimit-remaining: 0` test is the one that fires; and that `release/v1` of the PyPI action is a branch, so pinning it by commit is a real gain.

**30, library behaviours.** Agree on `filelock>=4.2.1` and `rich>=13.8.0` with the cap removed. Differences:

- *Closed pipe on Windows.* The agent sets out the choice (code 5 as F10's general rule gives, or 141, or 1) and leaves it to the maintainer. The reviewer recommends 141, with the narrow test the agent describes (`OSError`, `errno == EINVAL`, the stream is a pipe). Reason: a reader that closes early is not a failure, and one code for one situation keeps scripts portable.
- *The release-time unlink in the spec.* The agent offers a variant or a sentence in the specs' README; the reviewer recommends the variant, so the reason for the bound is checked, plus the README argument for Windows. Both recommend the `foreign_file` case as a unit test beside the second-look test; the reviewer's part 3 named the "file kept after release" and "mtime unchanged" checks but not that one, and should have.
- *Pydantic.* The agent proposes `>=2.5.3`, Typer 0.29's own floor. With the Typer floor at 0.27.2 that reason weakens. Both agree the floor must be one the lowest-versions CI run can install on its Python.
- The agent adds two rules the reviewer did not state and that should be written into R6: `take_lock` must not map filelock's `RuntimeError("Deadlock ...")` to "busy", and lock objects are thread-local, so a step function takes and releases a lock in one thread.

**31, progress and a closed stdout.** Agree that plain mode needs no spacing. Difference on `--raw | head`: the agent recommends that a closed pipe stops the child in a parsed run (the design already does this through the launcher's `finally`) and that the help of `--raw` says TLC runs on. The reviewer recommends stopping TLC in a raw run as well, by polling `reader_gone(1)` in `run_passthrough`'s wait loop, which costs a few lines and uses code F10 already has. Trade-off: it makes a raw run depend on `select.poll` (Linux and macOS; Windows keeps the documented behaviour), and it is tlaup reacting to a stream it otherwise does not touch in raw mode.

**32, SANY and PlusCal working folder.** Agree: both stay in the spec's folder, one rule for the two standalone tools.

**33, inherited lock.** The main difference. The agent calls option 3 a fall-back, not needed once option 4 is taken. The reviewer recommends it as a complement on Linux and macOS, because option 4 alone leaves a window of about two seconds after a kill. In that window `cache clean`, a sweep of an old folder or `-recover` can act on a live TLC. The agent sees the same window and offers two ways out for option 4 alone: accept it and name it, or make `-recover` and `cache clean` wait when the `pid` in `run.json` is gone. The reviewer's view: with option 3 the window disappears exactly on the supported systems, the specs' properties hold without exception, and the cost is a `pass_fds`. The agent's points 3 and 5 are real costs of option 3 and are already met by the design: the release comes after the child is gone, and nothing uses `preexec_fn`. One open point remains on how to hand over the descriptor. The reviewer proposed an `os.dup` taken in `filelock`'s `on_acquired` hook, which keeps filelock's re-check. The agent prefers tlaup's own `os.open` with `lock_descriptor`, which follows the documented API but means tlaup writes the re-check and the timeout itself. The reviewer's route depends on how the hook's word "borrowed" is read; the agent's on tlaup's own code. If the maintainer wants no dependence on an undocumented use, the agent's route is the safer one. If the window is accepted instead, the agent's pid-wait is a reasonable middle way, but it brings back a pid check, which R6 rejected as a lock.

**34, metadir writes.** Agree that "nothing written" cannot stand for "no TLC". The agent keeps option 2 as a heuristic that is better than counting from `started`; the reviewer uses the same measurement only for a different purpose (when did a stopped run stop), once option 4 has made liveness a non-question. Under the maintainer's new requirement for kept folders (below) the expiry rule matters less, and this difference matters less with it.

**35, the JVM ends with tlaup.** Agree on the mechanism: the lifeline agent in PID mode, one jar for every tool and every system, built in the release workflow or checked in, never compiled on the user's machine; no `preexec_fn`, no pipe variant, no watcher. The agent also states that `ProcessHandle.isAlive` compares start times, which makes the reviewer's proposed start-time check unnecessary. The reviewer withdraws it, but would keep one test with a reused-pid stand-in to confirm it on Java 11. Differences:

- The window: see 33.
- *Checkpoints.* The agent proposes the same stricter test (`queue.chkpt` and `vars.chkpt`, no `.tmp`), and leaves to the maintainer whether a suspect checkpoint is kept with a warning or not offered. The reviewer recommends not keeping it, and adds two measures the agent does not have: hold a first Ctrl-C in a parsed run while TLC is between 2195 and 2196, and always pass `-fp` and `-seed`.
- *Signals.tla.* The agent says nothing in it needs to change except perhaps `ChildNeverOrphaned` for SIGKILL. The reviewer proposes a `TlaupDies` action with a liveness property, which is the same idea stated as a model step. The checkpoint deferral, if taken, is a real change to the signal table and to the spec.
- *RunFolders.tla.* With option 4 alone the agent models the kill as ending TLC in the same step or a later step that must come. The reviewer models the locks passing to the orphan (option 3) and the orphan's exit as fair (option 4). The agent's own Implications for 33 describe the same change to `Kill` and `OrphanExit` as the reviewer's. So the spec change is agreed if option 3 is taken.
- The agent suggests an upstream report about the checkpoint commit not being crash-safe and the over-count. The reviewer agrees it is worth reporting; contacting upstream is the maintainer's call.

### To redesign later: kept run folders

The maintainer's requirements (from the notes): a kept folder is visible (where, how big, why); a kept folder is really resumable; folders the user will not resume, or is unsure about, need a solution; keeping is something the user asks for, and even a day is too long otherwise. A direction that meets them:

1. **Keeping is asked for at the start.** `tlaup tlc --keep`, or the setting `tlc.keep: true` (and `TLAUP_TLC_KEEP`), marks a run as one whose checkpoint should survive an interruption. Without it, every run deletes its folder at the end however it ended. This is the inverse of D48: `--no-keep` becomes the default and its flag goes. It changes D36 and D48, and D49 then applies only to runs that asked. Asking at the start, rather than asking at the moment of the Ctrl-C, keeps D23 (no new prompts) and works the same in CI, in raw runs and after a kill, where nobody can be asked.
2. **Without `--keep`, nothing waits a day.** A run that did not ask deletes its folder at its own end. A folder left by a killed tlaup is removed by the next sweep at once, whatever it holds; with the lifeline (option 4, with option 3 on Linux and macOS) a free lock means no TLC runs there. `run.json` records `"keep": false` so the sweep knows. When the run had a checkpoint that was thrown away, the "interrupted" line says so in a few words ("a checkpoint was not kept; use --keep to keep one"), so a user who wanted it learns how for next time.
3. **With `--keep`, a folder is kept only if it is resumable.** That means a complete checkpoint (`queue.chkpt` and `vars.chkpt`, no `.tmp` files), written by a run that was given an explicit `-fp` and `-seed` by tlaup, so the resume command can repeat them. In a parsed run a first Ctrl-C during a checkpoint waits for it to finish (part 3, question 35). If no complete checkpoint exists, the run says so and the folder is deleted: there is nothing to resume, and a half-written checkpoint can lie.
4. **Visible.** The note gives the path, the size and the reason: "Checkpoint kept (2.1 GB, interrupted after 2 h 13 min, checkpoint of 14:02): <path>", then the resume command. `tlaup cache list` shows each kept folder with spec, cfg, build, size, age, why it was kept and whether its lock is held. Every `tlaup tlc` start prints one line on stderr when kept folders exist: "3 kept run folders hold 7.4 GB (tlaup cache list)". That line is the answer for folders the user has forgotten or is unsure about: they are reminded at every run until they decide.
5. **How long.** A folder the user asked to keep is not removed silently. It goes when a resume from it finishes (as now), when the user runs `tlaup cache clean --all` or a new `tlaup cache clean <run-id>`, or when a resume from it is interrupted again and kept anew. If an upper bound is still wanted, it should be long (30 days from the last write, per research 34) and announced in the reminder line before it acts ("removed in 2 days"), never a surprise.
6. **The specs.** RunFolders gains `keep` per run: the sweep's rule "unsettled with a checkpoint is spared" applies only when `keep` is true, and `KeptSurvives` and `CheckpointSurvives` are stated for runs that asked. With option 4 the property "no folder of a run that did not ask outlives the next sweep" becomes checkable.

What this costs: a user who forgot `--keep` and interrupts a ten-hour run loses its checkpoint. The reminder in point 2 makes that a one-time lesson, and the alternative (keeping by default) is exactly what the maintainer ruled out. A softer variant keeps a run that did not ask until the end of the same tlaup's next run, but it brings back the "unsure" folders the requirements want gone, so the reviewer does not recommend it.

### To redesign later: the parser's result

The maintainer agreed with the agent: take the three parser changes, build the run's result from TLC's messages with the exit code as a cross-check, and treat 4802 inside a TLC run as a failure while standalone SANY keeps it a warning. The maintainer asked the redesign to review that from the recorded results. A direction that keeps what was agreed and settles the rest:

1. **One verdict, decided from messages.** The parser and runner set `verdict` (`errors`, `no-error`, `no-error-bounded`, `incomplete`, `not-checked`) and `resumed`, as part 3 of this review describes under question 22. The verdict is built from what the recorded captures show: an error is any severity 1 or 2 message, or a SANY error; a search is complete only for breadth-first without a depth bound that reached 2186; `-simulate`, `-generate`, `-dfid` and `-depth` are bounded; a run stopped by a signal, a crash or a missing 2186 is incomplete. Nothing in it needs the exit code.
2. **The exit code is the cross-check, shown and compared.** The result line reads from the verdict and names TLC's exit code beside it. When the two disagree (the `-deadlock -continue` capture: two violations, exit 0), tlaup prints one warning naming both. Whether tlaup's own exit code should then follow the verdict is the one decision left; part 3 sets out its trade-off. The reviewer's suggestion: keep D29's pass-through and the warning now, and settle the exit code together with the JSON result in milestone 4, where scripts will read the verdict directly.
3. **4802.** The reviewer differs from what was agreed, and asks the maintainer to look at it again on these grounds, all from the captures. SANY alone prints 4802 under `Semantic errors:` with `*** Errors: 1`, the same frame as a real error, and exits 0, as it does for real semantic errors too, so its exit code says nothing either way. TLC refuses the spec with 3002 and exit 150. The two stuttering lints behave the same. Only research 12's reading of SANY's message table calls 4802 a warning; nothing the user sees does. Treating it as a warning in `tlaup sany` gives exit 0 for a spec that `tlaup tlc` refuses with 150, which is what D29 says should not happen ("`tlaup sany` returns 150 for a spec with errors, the number `tlaup tlc` returns for the same spec"). A user who runs `tlaup sany` as a quick check in CI would see it pass and the model check fail. The recommendation stands: an error in both commands. If the maintainer prefers to show SANY's own classification, a middle way is to print it as `warning:` but still exit 150 from `tlaup sany`, with the reason "TLC refuses specs with this message"; that keeps the label and the promise, at the cost of a warning that fails a build.
4. **What a resumed run says.** A run that recovered from a checkpoint (2197, 2198) is marked `resumed`. Its state counts are shown as approximate unless it was resumed with the original `-fp` and `-seed`, which tlaup's own resume command will always pass once point 3 of the previous section is done. The one open fact is whether matching `-fp` removes the over-count on v1.7.4 and with several workers; one run per build answers it.
5. **Rejected for now.** A separate parser for `-dfid` beyond the header and code rule: the agent rated `-dfid` low priority and the reviewer agrees; the two rules are enough to keep its traces from becoming unknown messages.
