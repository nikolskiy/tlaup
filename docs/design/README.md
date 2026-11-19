# Design documents (pipeline stage 3, first wave)

Written 2026-11-15 by the stage 3 design agent, from the [roadmap](../roadmap.md) and the [investigation results](../research/README.md). Status: **reviewed three times by fresh agents, on 2026-11-15 and 2026-11-16, and revised after each; signed off by the maintainer on 2026-11-18**. The first review found it not ready; the second check, of the revision, found it ready after small fixes with one blocker, and those fixes are in. A third check on 2026-11-16, of the second round's fixes only, again found it ready after small fixes, with sixteen findings; those are worked in too, and that third revision has not been read by a fresh agent. The findings and what became of each are in [review-2026-11-15.md](review-2026-11-15.md). Nothing here has been built or tested; every design is a plan. No product code was changed by this stage. On 2026-11-16 [03](03-run-stages-and-specs.md) was added after the third check: a walk-through of one TLC run, and the plan for a formal check of the design before stage 4 (decision D46). No fresh agent has read it.

**Sign-off, 2026-11-18.** The maintainer walked through the three tables below with the design agent, on 2026-11-17 and 2026-11-18, with no further review agent, and accepted every decision the design agent made, every departure from the roadmap, and the open questions as they stand. Settled on the way: decision D47 (singular `tool` and `module`). Changed at the sign-off: question 32 on the folder SANY and PlusCal run in ([21 S1](21-other-tools.md#s1-sany)); a milestone 3 roadmap item on removing builds nobody needs ([40](40-later-milestones.md#open-questions-for-the-design-note)); contract tests of the Typer names tlaup relies on ([14 F10](14-config-and-cli.md#f10-no-tracebacks)); `tlc --plain` and the setting `tlc.plain` ([22 O4](22-reporters.md#o4-live-display)); rule 10 of [01 T12](01-testing.md#t12-rules-for-writing-tests), which makes the choice between an in-process and a real-process scenario a rule instead of a judgement. Questions 19 to 32 go to the top-up round of stage 2. Part 2 of 03, the formal check, has its own review when its specs are written (roadmap, "Formal check of the design"); stage 4 starts after it.

The first wave designs milestones 1, 1b and 2 in full and sketches milestones 3 to 5. Where a design and the roadmap differ, the difference is listed under "Where the design departs from the roadmap" below, so the review can check each one.

## Documents

| File | Covers |
| --- | --- |
| [00-overview.md](00-overview.md) | The shared pieces every item builds on, in one picture: packages, the run pipeline, the order of work. |
| [01-testing.md](01-testing.md) | The testing approach (decision D16) and the testing items of milestone 2. Designed first. |
| [02-cross-cutting.md](02-cross-cutting.md) | Exit codes, stdout and stderr, the version syntax, what "rolling" means and how it sorts. |
| [03-run-stages-and-specs.md](03-run-stages-and-specs.md) | Added 2026-11-16, not reviewed yet: the components and one TLC run through them, stage by stage; the TLA+ specs and stateful property tests that check the design before stage 4 (decision D46). |
| [10-parser.md](10-parser.md) | Milestone 1, parser: the `tlaup_parse` package, traces, values, SANY, never losing output. |
| [11-runner.md](11-runner.md) | Milestone 1, runner: signals, the cfg path, run folders, overrides, passthrough, preflight, project root. |
| [12-tools-and-downloads.md](12-tools-and-downloads.md) | Milestone 1: the version store, install, uninstall, pin, GitHub, the first-run prompt, removing old layouts. |
| [13-modules-and-java.md](13-modules-and-java.md) | Milestone 1: `module add` and `remove`, the module build, Java options, `JAVA_HOME`, one Java start. |
| [14-config-and-cli.md](14-config-and-cli.md) | Milestone 1: layered configuration, folder overrides, messages, help, tracebacks, startup cost. |
| [20-groundwork.md](20-groundwork.md) | Milestone 1b: the TLC invocation value, domain errors, the generic Java launcher. |
| [21-other-tools.md](21-other-tools.md) | Milestone 1b: the `sany`, `pcal` and `repl` commands. |
| [22-reporters.md](22-reporters.md) | Milestone 1b: the reporter interface, the terminal reporter, the live display. |
| [23-command-layout.md](23-command-layout.md) | Milestone 1b: the command tree for sign-off, typing versions, completion, `-V`. |
| [30-ci-and-release.md](30-ci-and-release.md) | Milestone 2: CI, release, dependencies and build, repository hygiene. |
| [review-2026-11-15.md](review-2026-11-15.md) | The stage 3 review: the findings of three fresh agents and what became of each. |
| [40-later-milestones.md](40-later-milestones.md) | Milestones 3 to 5: direction, open questions, what the first wave leaves room for. Sketch only. |

Reading order for a reviewer: 00, 01, 02, 03, then any area. A work-package agent (stage 4) reads 00, 01, 02, 03 and the area it is cutting.

## How an item is written

Each roadmap item has a section with a short identifier (for example P5 or R3) that the roadmap links to. A section gives:

- **Problem**: what is wrong today, with the source location where it matters.
- **Design**: the chosen approach.
- **Rejected**: the alternatives and why they lost.
- **Interfaces**: function signatures and data shapes, where the item has any.
- **Tests**: what proves it, in the forms defined in [01-testing.md](01-testing.md).
- **Changelog**: the entry it needs, and whether it is a breaking change.
- **Depends on** and **Risks**.
- The decision (D number) or research file it relies on. Where research contradicts an earlier assumption, the research wins and the section says so.

Small items share a section when they change the same few lines. Source locations were checked against the code on 2026-11-15 (commit `ad9ce57`).

Signatures are written in Python and are the intended shape, not final code: a worker may adjust a name or a parameter if the behaviour and the tests stay as designed, and says so in the pull request.

## Decisions made in this wave

Settled with the maintainer on 2026-11-15 and written into the roadmap's decision table.

| # | Decision | Where |
| --- | --- | --- |
| D29 | Exit codes: 2 usage, 3 not set up, 4 not found, 5 failed; tlaup never returns 1; the wrapped tool's code passes through; `sany` returns 150 for a spec with errors. | [02](02-cross-cutting.md#x1-exit-codes) |
| D30 | stdout carries the result, including SANY diagnostics and TLC warnings; stderr carries progress, the live status and tlaup's own messages; `--raw` passes both streams through. | [02](02-cross-cutting.md#x2-stdout-and-stderr) |
| D31 | Version syntax: tag with or without `v`, `stable`, `rolling`, `tag@commit`, `tag@CalVer`. `latest` is not offered. | [02](02-cross-cutting.md#x3-version-syntax) |
| D32 | "rolling" is the upstream release tagged `rolling`; it sorts above every numbered version; builds of one name sort by build time. | [02](02-cross-cutting.md#x4-rolling) |
| D33 | Command-line behaviour is tested with pytest-bdd feature files; the parser and the download code are tested in plain pytest. | [01](01-testing.md#t1-the-approach) |
| D34 | TLC runs in the folder tlaup was started from, with the spec as an absolute path. | [11](11-runner.md#r4-spec-cfg-and-working-folder) |
| D35 | When the pinned TLC build cannot load a registered override class, tlaup warns and runs. | [11](11-runner.md#r7-override-modules-that-do-not-load) |
| D36 | tlaup passes `-noGenerateSpecTE` by default on builds that have it. | [11](11-runner.md#r6-run-folders) |
| D37 | The version store is built in milestone 1, not milestone 3. | [12](12-tools-and-downloads.md#v1-version-store) |
| D38 | No short command forms (`ls`, `rm`); the pinned build is shown by `tlaup tool current`. | [23](23-command-layout.md#c1-command-tree) |
| D39 | The parser's import package is `tlaup_parse`. | [10](10-parser.md#p2-the-tlaup_parse-package) |
| D40 | The live display is the full-screen layout, finished (D3), not a one-line footer. It is drawn on stderr when both streams are terminals; the result is printed on stdout when it closes. | [22 O4](22-reporters.md#o4-live-display), [02 X2](02-cross-cutting.md#x2-stdout-and-stderr) |
| D41 | The GitHub token goes to `api.github.com` and to hosts in the user-level setting `tool.token_hosts`, and nowhere else. | [12 V7](12-tools-and-downloads.md#v7-github-client), [14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay) |
| D42 | With a config file that does not parse, `config path` and `config edit` work; `show`, `get` and `set` stop with exit 3. | [14 F4](14-config-and-cli.md#f4-config-commands-with-a-broken-file) |
| D43 | `tool uninstall NAME` with several builds asks which on a terminal; with `--yes` or no terminal it removes all. | [12 V3](12-tools-and-downloads.md#v3-uninstall) |
| D44 | Dependabot opens one grouped pull request per ecosystem. | [30 B1](30-ci-and-release.md#b1-dependabot) |
| D45 | The preflight checks spec, cfg, tool build, Java, in that order; `--show-command` never prompts or installs. | [11 R11](11-runner.md#r11-preflight) |
| D46 | Before stage 4, TLA+ specs of the run folders, the tools store and the launcher's signals are checked with TLC, and each is mirrored by a Hypothesis stateful test that the work packages use as their test first. Settled 2026-11-16. | [03](03-run-stages-and-specs.md#part-2-tla-specs-of-the-design) |
| D47 | The command groups `tools` and `modules` become `tool` and `module`; so do the config section (`tool.repository`, `tool.token_hosts`, `TLAUP_TOOL_...`) and the cache folders (`tool/`, `module/`). Settled 2026-11-17, during the sign-off. | [23 C1](23-command-layout.md#c1-command-tree) |

## Decisions the design agent made

Not put to the maintainer one by one; each is argued in its section. The review should look at these first.

| Decision | Why | Where |
| --- | --- | --- |
| Research fixtures move from `tests/fixtures/research/` to `tests/parse/golden/` and `tests/recordings/`. | Decision D7 wants golden files with the parser's tests; one copy, not two. | [01 T3](01-testing.md#t3-golden-files) |
| Each run gets its own run folder with a lock file; there is no per-spec folder and no fingerprint. | Removes the prefix-match deletion, the v1.7.4 same-second collision and the incomplete fingerprint in one step (research 17). | [11 R6](11-runner.md#r6-run-folders) |
| A run folder that holds a TLC checkpoint is kept, and its path printed, only when the run did not finish (a signal, a crash). A finished run deletes its folder. | Deleting it would destroy the only way to resume. Whether TLC checkpoints without `-checkpoint` was not checked (question 25); the rule keys on the files being there. | [11 R6](11-runner.md#r6-run-folders) |
| The project root is the spec's folder, or its parent only when the spec's folder is named `spec`, `specs`, `test` or `tests`; never the home folder. | The roadmap leaves the fix to design; this closes the `~/lib` case without waiting for the project file. | [11 R10](11-runner.md#r10-project-root) |
| A build's commit comes only from the jar's manifest; the tag's commit is not fetched. | Research 7 and 14: the tag and the jar move at different moments, and the jar is the stronger identity. The download is checked against the asset's size and digest instead. | [12 V5](12-tools-and-downloads.md#v5-download-and-verify) |
| Uninstalling the pinned build clears the pin; it no longer falls back to another build. | A silent switch to another TLC changes results. | [12 V3](12-tools-and-downloads.md#v3-uninstall) |
| The first-run answer is `--auto-install` and `TLAUP_AUTO_INSTALL`. | Decision D4 asks for a flag and a variable and names neither. | [12 V9](12-tools-and-downloads.md#v9-first-run-prompt) |
| The module build becomes domain code in milestone 1 and finds override classes by reading the compiled class files. | The temp-folder build rewrites the function anyway; reading class files removes the comment-stripping regex. | [13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder) |
| Override classes are compiled with `--release 11`; `javac` gets its own version check. Listed as Breaking, with the module name rule. | A module built with a newer JDK should load on the oldest supported Java. What TLC prints when it does not was not checked (question 28). | [13 M3](13-modules-and-java.md#m3-module-build-details) |
| Settings removed: `workspace.*`, `tlc.java_class`, `tlc.overrides_class`, `tla.*`; `tool.repository` replaces the two URL keys. | The roadmap asks to read each setting or remove it; none has a use case, and pagination needs one base address. | [14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay) |
| Unknown config keys give a warning, not an error. | An old file must still load (roadmap, layered configuration). | [14 F1](14-config-and-cli.md#f1-layered-configuration) |
| Messages use plain prefixes (`error:`, `warning:`, `hint:`) with no symbols. | Removes the glyph-encoding crash the roadmap lists under milestone 4. | [14 F6](14-config-and-cli.md#f6-messages) |
| A stopped run is called "interrupted" everywhere. | One word, and the usual one for exit 130. | [14 F8](14-config-and-cli.md#f8-wording) |
| New runtime dependency `filelock`; new test dependencies `pytest-bdd`, `hypothesis`, `responses`, `pytest-socket`, `pytest-randomly`; `pytest-mock` is removed. | Locks that work on every platform; the test design. | [01](01-testing.md), [12 V1](12-tools-and-downloads.md#v1-version-store) |
| `sany` and `pcal` run in the spec's folder with the bare file name; `tlc` and `repl` do not change folder. | Each is the arrangement the research actually ran (16 for TLC, 12 for the others). | [21](21-other-tools.md) |
| `tools meta sync`, `modules path`, `tlc --version`, `tlc --cleanup`, `fetch-cache`, `check-java` and `config list` go; `doctor`, `cache`, `completion`, `tool current`, `module dir` and `config path/show/get/set` arrive. | The command tree, for sign-off as a whole. | [23 C1](23-command-layout.md#c1-command-tree) |
| The integration job also runs weekly. | A rolling build can change TLC's output between pushes. | [30 I1](30-ci-and-release.md#i1-integration-job) |
| Made during the revision after the review: | | |
| Symbolic links in a spec path are not resolved; `--cfg` accepts only names ending in `.cfg`. | TLC then looks beside the path the user gave, and reads the file that was validated (research 16). Linked folders wait on question 24. | [11 R4](11-runner.md#r4-spec-cfg-and-working-folder), [R5](11-runner.md#r5-spec-names) |
| `sany` and `pcal` read the tool's two streams through one pipe; `tlaup sany -- -d` is refused. | v1.7.4 writes one diagnostic line to stderr and the captures do not say which (question 22); `-d` loops for ever with no input. | [21 S1](21-other-tools.md#s1-sany) |
| `tlaup sany` returns 150 for an error, not for a warning alone. | A warning should not fail a build script. What TLC returns for such a spec is part of question 22. | [21 S1](21-other-tools.md#s1-sany), [10 P8](10-parser.md#p8-sany-output) |
| A build's folder name is its name plus 12 digits of its SHA-256; a build with no commit has a defined printed form. | The first id collided for two jars of one name and commit. Older jars wait on question 26. | [12 V1](12-tools-and-downloads.md#v1-version-store), [02 X3](02-cross-cutting.md#x3-version-syntax) |
| `tool install` of a build already installed exits 0, with a warning when GitHub cannot be asked; a moved tag keeps the older build and the pin; `TLAUP_AUTO_INSTALL` also answers `tool install` with no version. | The first design had no section for `install` itself. | [12 V12](12-tools-and-downloads.md#v12-install) |
| `config set` takes one YAML value and rewrites the file; comments are lost. Removed settings give one combined warning. | PyYAML cannot keep comments, and no new dependency is worth it for this. | [14 F1](14-config-and-cli.md#f1-layered-configuration), [F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay) |
| The short options `-f` and `-y` go. | One spelling per option, as D38 does for commands. | [23 C1](23-command-layout.md#c1-command-tree) |
| Errors are mapped to exit codes inside the root command group; completion uses two private Typer modules. | The locked Typer has no separate Click; probed on 0.29.1 only (question 23). | [14 F10](14-config-and-cli.md#f10-no-tracebacks), [23 C3](23-command-layout.md#c3-completion) |
| While the layout is up, result text is spooled and copied to stdout when it closes; the layout needs 60 columns by 15 rows, else output is plain; `tlc --plain`, or the setting `tlc.plain`, gives plain output on a terminal. | Nothing is lost (D9) and the scrollback holds the same text a redirected run gives. The flag was added at the sign-off, 2026-11-18. | [22 O4](22-reporters.md#o4-live-display) |
| Golden folders are matched to a live build by release line, not by exact build. | The integration job's rolling jar is always newer than any recorded folder. | [01 T3](01-testing.md#t3-golden-files), [T9](01-testing.md#t9-integration-tests) |
| Scenarios that pass output through, or need a pipe, a signal or a terminal, run tlaup as a real process; the rest run in-process. | An in-process runner cannot see a child's inherited streams. | [01 T5](01-testing.md#t5-feature-files-and-steps) |
| The Java version check is remembered only for a plain binary named `java`. | With a version manager's shim the answer depends on the folder. | [13 J3](13-modules-and-java.md#j3-one-java-start) |
| `.python-version` moves to 3.11 and the classifiers between the lowest and newest supported go. | Development then happens on the lowest supported version. | [30 H3](30-ci-and-release.md#h3-python-versions) |
| Made during the second revision, after the second check: | | |
| A closed output pipe exits 141, for help and Typer's own messages too; a hang-up is 129; a child killed by a signal tlaup did not send is 128 plus the signal's number. A wrapped tool's own 1 is never changed. | The shell's conventions; D29 names none of the three. The 141 needs three measures because Rich handles a closed pipe itself (tried on the locked versions, Linux only; questions 23 and 30). | [02 X1](02-cross-cutting.md#x1-exit-codes), [14 F10](14-config-and-cli.md#f10-no-tracebacks) |
| `tlaup`, or a group, with no command prints help on stdout and exits 2. | Typer's behaviour, kept: an incomplete command line is a usage error. | [02 X1](02-cross-cutting.md#x1-exit-codes) |
| Environment variables are `TLAUP_<SECTION>_<KEY>`, lists comma-separated; `TLAUP_JAVA_OPTS` adds to the setting; `TLAUP_HOME`, `TLAUP_CONFIG_DIR`, `TLAUP_CACHE_DIR` and `TLAUP_DATA_DIR` move folders; `TLAUP_DEBUG` and `TLAUP_AUTO_INSTALL` are switches. | The roadmap asks for an environment layer and names no scheme. | [14 F1](14-config-and-cli.md#f1-layered-configuration), [F2](14-config-and-cli.md#f2-folder-overrides) |
| `tool install` with no version asks "stable or rolling", or takes `TLAUP_AUTO_INSTALL`, and otherwise exits 2; it no longer installs the newest stable. | A silent choice of build is what D4 removes from the first run. | [12 V12](12-tools-and-downloads.md#v12-install) |
| Two version forms beyond D31: a bare CalVer, and `name@sha256:...` for an installed build. A bare CalVer is always a build time, never a tag. Builds print in the shortest of four forms that names one build, and every printed form can be typed back. | Two builds of one name and commit with no build time had no printed form. | [02 X3](02-cross-cutting.md#x3-version-syntax) |
| The store decides "already installed" by name and full SHA-256; a folder already sitting at a build's id gets a `-2`, `-3` suffix beside it and is never replaced. | A folder tlaup cannot read may belong to a newer tlaup. | [12 V1](12-tools-and-downloads.md#v1-version-store) |
| `.netrc` credentials are never used; a jar is downloaded from its public address and carries no token by default; addresses are compared after parsing, and query strings are cut from messages. | With a netrc entry `requests` replaced the token and sent the netrc credentials to the asset host (tried). | [12 V7](12-tools-and-downloads.md#v7-github-client) |
| `uninstall --all` with no terminal and no `--yes` is a usage error; `upgrade` with several builds of a name replaces only the newest. A value that does not fit, given to `config set`, is a usage error. | One rule per case; the second check found cases with none or two. | [12 V3](12-tools-and-downloads.md#v3-uninstall), [V4](12-tools-and-downloads.md#v4-upgrade-and-pin), [14 F1](14-config-and-cli.md#f1-layered-configuration) |
| `tlaup cache list` is a new command. Bash completes a build up to its name only; the part after `@` is typed. | The "Checkpoint kept" note names a folder there was no command to look at. Bash splits words at `@` (tried). | [23 C1](23-command-layout.md#c1-command-tree), [C3](23-command-layout.md#c3-completion) |
| Required CI checks are lint, unit, integration and build, through one job; the newest-dependencies job is not required. | A job that fails because a dependency released must not block a merge. | [30 I5](30-ci-and-release.md#i5-workflow-hygiene) |
| `filelock>=4.2.10` and `rich>=13.8.0`; the cap on Rich stays until question 30 is answered. | The only versions checked, and what Typer 0.29.1 itself requires. | [30 B2](30-ci-and-release.md#b2-build-fixes) |
| Checks that need only the command line (options that conflict, the `--workers` value, Java option quoting, `sany -- -d`) run before the spec check. | A usage error should not wait behind a prompt. D45's order holds for the rest. | [11 R11](11-runner.md#r11-preflight) |
| The command prints "Checkpoint kept" and the resume command, after the reporter has closed; on an error the note travels with the exception. The resume command uses absolute spec and cfg paths and does not carry the environment or the starting folder. `-recover` into a run folder that is in use is refused (code 5). | One rule for raw and parsed runs; the first design had two. | [11 R6](11-runner.md#r6-run-folders), [22 O1](22-reporters.md#o1-reporter-interface) |
| A signal that was ignored when tlaup started stays ignored (`nohup`); SIGQUIT is survived and not forwarded, so the JVM prints its thread dump; a Ctrl-C left to the REPL is not recorded. | Each was broken by the first revision or had no rule (tried, Linux, Java 25). | [20 G3](20-groundwork.md#g3-java-launcher) |
| Waits and ages chosen without measurement: 5 seconds for a run's lock, one hour before a lock file with no folder is removed, 2 seconds to empty the output queue, one day for a half-built module folder. | Guesses, named so a worker does not take them for findings. | [11 R6](11-runner.md#r6-run-folders), [20 G3](20-groundwork.md#g3-java-launcher), [13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder) |
| `tlaup sany` refuses exactly `-d`; the macOS system `java` is never remembered. | Until questions 22 and 28 say more. | [21 S1](21-other-tools.md#s1-sany), [13 J3](13-modules-and-java.md#j3-one-java-start) |
| A parsed message has one ordered body of lines and nested messages; nested messages raise no event of their own. New error kind `usage`, new event `ModeSeen`; the SANY parser gives every line a class. | The input can then be rebuilt exactly (checked by script over the captures). | [10 P3](10-parser.md#p3-result-model), [P8](10-parser.md#p8-sany-output) |
| A reporter has `close()`, which never raises; a failed write is kept and raised after the run. After a layout run TLC's stderr lines stand together above the result text in the scrollback. | An error must not be drawn into a screen that is about to vanish, and must not be replaced by a second one. | [22 O1](22-reporters.md#o1-reporter-interface), [O4](22-reporters.md#o4-live-display) |
| One test depends on the real clock for about two seconds; synthetic cases carry a `.why` file. | Only a paced run on a real terminal shows that the live display redraws. | [22 O4](22-reporters.md#o4-live-display), [01 T3](01-testing.md#t3-golden-files) |
| Made during the third revision, after the third check: | | |
| Output that cannot be written for a reason other than a closed pipe (a full disk under a redirect) is code 5 with `error: cannot write output: ...`; at the last flush it never replaces a non-zero code. A usage error whose message cannot be written exits 5, not 2. | The third check got 120 and a traceback there (tried with `/dev/full`). | [14 F10](14-config-and-cli.md#f10-no-tracebacks), [02 X1](02-cross-cutting.md#x1-exit-codes) |
| After a signal tlaup drops what is left in stdout's buffer instead of waiting for a reader. A tlaup blocked in a write to a pager that is not reading still waits for the pager; accepted. | The last flush could block behind `less` (tried); the write itself is not covered (not tried). | [14 F10](14-config-and-cli.md#f10-no-tracebacks), [20 G3](20-groundwork.md#g3-java-launcher) |
| `upgrade stable` installs a newer stable tag beside the old one and removes nothing; `upgrade` refuses every other build spec. `uninstall A B` removes nothing when one argument matches no build. | One rule per case. | [12 V4](12-tools-and-downloads.md#v4-upgrade-and-pin), [V3](12-tools-and-downloads.md#v3-uninstall) |
| An address with a backslash, a user part or white space is refused, and every host decision is made on the address `requests` prepared. | `urlsplit` and `requests` disagree on a crafted address (tried without sending). | [12 V7](12-tools-and-downloads.md#v7-github-client) |
| The capability check for `sany`, `pcal` and `repl` comes before the Java check; `signals_held` is told at entry whether a Ctrl-C is left to the child. `Ui` has `terminal` and `size` arguments for tests. The Status panel has the phase "Interrupted". An open SANY diagnostic with no message is dropped. | Each closes a gap the third check found between two sections. | [21](21-other-tools.md), [20 G3](20-groundwork.md#g3-java-launcher), [14 F6](14-config-and-cli.md#f6-messages), [22 O4](22-reporters.md#o4-live-display), [10 P8](10-parser.md#p8-sany-output) |

## Where the design departs from the roadmap

| Roadmap says | Design says | Reason |
| --- | --- | --- |
| Skip value parsing for traces if TLC can write JSON traces. | Not used; the text parser stays the only source. | Research 2: v1.7.4 has no such flag and the JSON loses types. [10 P6](10-parser.md#p6-json-traces-from-tlc) |
| Compare the commit the jar reports with the expected commit from the tag. | Identity is read from the jar; the download is verified by size and digest; the commit is compared only when the user typed one (`tag@commit`). | Research 7 and 14. [12 V5](12-tools-and-downloads.md#v5-download-and-verify) |
| Shortcuts `latest`, `stable` and `rolling`. | `stable` and `rolling` only. | Decision D31. |
| Accept `tag@sha` and the folder name wherever a version is accepted (milestone 4). | `tag@commit`, and for a build that form cannot name, a build time or `name@sha256:...`; folder names stop being shown or accepted. | The store makes folder names an internal detail. [02 X3](02-cross-cutting.md#x3-version-syntax) |
| Version identity as a type and one version store, in milestone 3. | Built in milestone 1. | Decision D37. |
| Module build moved to a domain package in milestone 3 or 5. | Done with the milestone 1 safety item. | See the table above. |
| Editor-style diagnostics in plain output, in milestone 4. | Done in milestone 1b with the `sany` command and the terminal reporter. | The reporter is written once. [22 O3](22-reporters.md#o3-terminal-reporter) |
| Exit 130 on Ctrl-C by passing the code through. | tlaup sets 130 itself. | Research 15: the JVM's code after Ctrl-C is a race between 130 and 143. |
| `tools upgrade` checks the remote again (milestone 1) and compares only the first of several builds (milestone 3). | Both fixed in milestone 1, since the store answers "newest installed build of this tag". | [12 V4](12-tools-and-downloads.md#v4-upgrade-and-pin) |
| The preflight checks jar, Java, spec and cfg in that order. | Spec, cfg, tool build, Java. | Decision D45. |
| One Dependabot pull request. | One per ecosystem. | Decision D44. |
| Read all pages of tags and releases; test "a tag without a commit". | Releases only; no such test. | Research 8, and the commit comes from the jar. [12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache), [01 T6](01-testing.md#t6-download-and-github-failure-tests) |
| Decide whether `module_path` and `module_lib_path` are documented or folded into the project file. | Left as they are, undocumented; the decision moves to milestone 3 with the project file. | [14 F3](14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay) |
| `fail_under` near the current 83. | 80, raised at the end of milestone 2. | The suite is rewritten; the old number measures the old tests. [01 T10](01-testing.md#t10-coverage-policy-and-pytest-settings) |
| The token is sent only to the GitHub API host. | Also to hosts the user lists. | Decision D41. |

## Waiting on a top-up investigation

The first wave added questions 19 to 22 to the roadmap's investigation list; the review added 23 to 29 and widened 19 and 22; the second check added 30 and 31 and widened 22, 23, 24 and 28; the sign-off added 32. No item is blocked as a whole; each names the part that waits.

| Question | Items that wait | What waits |
| --- | --- | --- |
| 19: does TLC accept `-workers auto`, on each supported build? | [11 R8](11-runner.md#r8-passthrough-and-workers) | What tlaup passes for `auto` on a build that does not accept it. |
| 20: does TLC create a missing `-metadir` folder? | [11 R9](11-runner.md#r9-show-command) | Whether the printed command can be pasted as it is. |
| 21: which character encoding does TLC write, per Java version and locale? | [20 G3](20-groundwork.md#g3-java-launcher) | Whether the launcher adds an encoding option by default. |
| 22: more `-tool` captures (`-difftrace`, checkpoints, simulation, `ALIAS`, a false `ASSUME`, an evaluation error, a cfg error and others), separate stderr for TLC, SANY and PlusCal, the exit code for a warning-only spec, SANY's warning forms and level errors on v1.7.4 as captures of their own, and whether SANY reads `-dl` as `-d`. | [10 P5](10-parser.md#p5-error-traces), [P3](10-parser.md#p3-result-model), [P8](10-parser.md#p8-sany-output), [01 T3](01-testing.md#t3-golden-files), [21 S1](21-other-tools.md#s1-sany), [S5](21-other-tools.md#s5-golden-files-for-sany-and-pluscal) | The error kinds with no capture, `-difftrace` states, which SANY line goes to stderr, the SANY warning rules, and how wide the `-d` refusal is. |
| 23: Typer across the allowed version range. | [14 F10](14-config-and-cli.md#f10-no-tracebacks), [23 C3](23-command-layout.md#c3-completion), [C5](23-command-layout.md#c5-help-and-the-cli-reference), [30 B2](30-ci-and-release.md#b2-build-fixes) | The lower bound for `typer`; until then it is the locked 0.29. |
| 24: path-taking TLC flags with an absolute spec; a cfg reached with `..` on v1.7.4; a spec behind a symbolic link; the last two together. | [11 R4](11-runner.md#r4-spec-cfg-and-working-folder), [R8](11-runner.md#r8-passthrough-and-workers) | What the help and changelog say about relative paths after `--`. |
| 25: does TLC checkpoint without `-checkpoint`? | [11 R6](11-runner.md#r6-run-folders) | How often an interrupted run leaves a folder to resume from. |
| 26: do jars older than v1.7.4 carry a commit? | [12 V5](12-tools-and-downloads.md#v5-download-and-verify), [V1](12-tools-and-downloads.md#v1-version-store), [02 X3](02-cross-cutting.md#x3-version-syntax) | Whether the no-commit form is ever seen. |
| 27: standalone SANY with `-DTLA-Library`. | [21 S1](21-other-tools.md#s1-sany) | Whether `sany` finds modules the way `tlc` does. |
| 28: Java 11 with both builds; a newer JDK's class on an older Java; what the `java` on a macOS path is. | [13 J3](13-modules-and-java.md#j3-one-java-start), [M3](13-modules-and-java.md#m3-module-build-details), [30 I1](30-ci-and-release.md#i1-integration-job) | The minimum Java, the message the override check names, and whether the macOS system `java` may be remembered. |
| 29: CI facts and real GitHub recordings. | [30 I1](30-ci-and-release.md#i1-integration-job), [I2](30-ci-and-release.md#i2-unit-job), [L2](30-ci-and-release.md#l2-release-workflow), [12 V7](12-tools-and-downloads.md#v7-github-client), [V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache), [01 T4](01-testing.md#t4-fakes-at-the-edges), [T6](01-testing.md#t6-download-and-github-failure-tests) | The newest Python, matrix cells, action SHAs, and the paging and rate-limit recordings. |
| 30: library behaviours nobody has tried across the allowed versions: Rich's live display and its closed-pipe handling, `select.poll` on macOS, `pyte`, coverage's subprocess patch, pytest-bdd, `responses`, and the lowest Pydantic and `filelock`. | [14 F10](14-config-and-cli.md#f10-no-tracebacks), [02 X1](02-cross-cutting.md#x1-exit-codes), [22 O4](22-reporters.md#o4-live-display), [01 T4](01-testing.md#t4-fakes-at-the-edges), [T5](01-testing.md#t5-feature-files-and-steps), [T10](01-testing.md#t10-coverage-policy-and-pytest-settings), [11 R6](11-runner.md#r6-run-folders), [30 B2](30-ci-and-release.md#b2-build-fixes) | The 141 outside the locked versions and Linux, the dependency bounds, and whether the test tools work as described; none of the test libraries was installed for the design. |
| 31: how often TLC prints progress; whether the JVM runs on when its stdout is closed. | [22 O3](22-reporters.md#o3-terminal-reporter), [11 R1](11-runner.md#r1-run-errors-reported-as-what-they-are) | Whether plain mode spaces progress lines itself, and what `tlaup tlc --raw Spec \| head` does. |
| 32: SANY and PlusCal started in the starting folder with an absolute spec path. | [21 S1](21-other-tools.md#s1-sany), [S2](21-other-tools.md#s2-pcal) | Whether `sany` and `pcal` follow D34 as `tlc` does, or keep running in the spec's folder. |

## Roadmap item to design

The roadmap carries a "Design:" link on every item of milestones 1, 1b and 2. The identifiers are grouped like this:

| Prefix | Document | Roadmap section |
| --- | --- | --- |
| T | 01-testing | Milestone 2, testing approach |
| X | 02-cross-cutting | The four first-wave decisions |
| P | 10-parser | Milestone 1, parser |
| R | 11-runner | Milestone 1, runner; reaching TLC; preflight; recorded problems |
| V | 12-tools-and-downloads | Milestone 1, safety (tools), downloads and GitHub, first run. V2 (order and lookup) and V12 (install itself) have no roadmap item of their own; the items that link to V1, V4, V5 and V9 build on them. |
| M, J | 13-modules-and-java | Milestone 1, safety (modules), Java |
| F | 14-config-and-cli | Milestone 1, configuration, messages and help, startup cost |
| G | 20-groundwork | Milestone 1b, shared groundwork |
| S | 21-other-tools | Milestone 1b, other tools |
| O | 22-reporters | Milestone 1b, reporters |
| C | 23-command-layout | Milestone 1b, command layout |
| I, L, B, H | 30-ci-and-release | Milestone 2: CI, release, build, hygiene |
