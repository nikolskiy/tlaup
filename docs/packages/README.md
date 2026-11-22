# Work packages (pipeline stage 4, first design wave)

Written 2026-11-21 by the stage 4 agent, from the signed-off first design wave ([design](../design/README.md)), the formal check ([specs](../../specs/README.md)) and the [roadmap](../roadmap.md). Status: **not reviewed**. Next is the stage 4 review gate: a fresh agent reviews these packages against the design, and the maintainer signs off before stage 5 starts ([roadmap, "How the work is done"](../roadmap.md#how-the-work-is-done)).

The packages cover milestones 1, 1b and 2. Milestones 3 to 5 are sketched only and get a second design wave after this one is built ([40](../design/40-later-milestones.md)); nothing here builds them, though a few packages close parts of their items, which the traceability table names. No package has been built, and no product code, test, spec or design document was changed by this stage.

There are 59 packages. Nine of them are delivered as two or three pull requests each, so stage 5 has 69 pull requests in all. Each pull request is listed below under its own number (for example 13a and 13b), with its own size and dependencies, and is reviewed on its own.

## How to read a package

Each file `NN-short-name.md` has the same headings: Goal, Covers, Depends on, Files, Interfaces, Tests that must pass, Changelog, Context for the worker, Done when, Out of scope, Risks, and, where it applies, "Pull requests (decided by stage 4)". The line under the title gives the size (S is hours, M one to three days, L a week or more), the suggested model, and whether part of it waits on a question below.

A worker reads its package file, the design sections it links, `AGENTS.md` and the conventions, and nothing else. It never needs `docs/analysis/` or `docs/research/`: what the design took from them is restated in the design or in the package.

## Packages

"Waits for" lists the packages whose merged work this one uses. A package named there is waited for whole: when it has several pull requests, all of them (a dependency on 35 means 35b). Each file's "Depends on" says what exactly it uses from each.

| # | Package | Size | Model | Waits for | Open |
| --- | --- | --- | --- | --- | --- |
| 01 | [Format the tree and enforce it](01-ruff-format.md) | S | mid-tier | none | Q1 |
| 02 | [Errors, paths and the context skeleton](02-errors-and-paths.md) | S | mid-tier | 01 | |
| 03a | [Test foundation](03-test-foundation.md): the fakes and helpers | M | most capable | 01, 02 | |
| 03b | [Test foundation](03-test-foundation.md): settings, isolation, checks, deletions | M | most capable | 03a | Q2, Q17 |
| 04 | [Delete dead code](04-delete-dead-code.md) | S | mid-tier | 03 | |
| 05 | [GitHub recordings and the `github` fixture](05-github-recordings.md) | M | mid-tier | 03 | |
| 06 | [The lifeline agent](06-lifeline-agent.md) | M | mid-tier | 01 | |
| 07 | [Golden files](07-golden-files.md) | M | most capable | 03 | Q3 |
| 08 | [Golden facts](08-golden-facts.md) | L | most capable | 03, 07 | |
| 09 | [The `tlaup_parse` package and its result model](09-parse-package-and-model.md) | M | most capable | 03 | Q4 |
| 10 | [Framing and the code table](10-framing-and-codes.md) | M | most capable | 03, 07, 09 | |
| 11 | [TLA+ values](11-values.md) | M | most capable | 03, 07, 09 | |
| 12 | [The SANY parser](12-sany-parser.md) | M | mid-tier | 07, 09 | |
| 13a | [The TLC parser](13-tlc-parser.md): messages, status, verdict, version | L | most capable | 07, 08, 09, 10, 12 | |
| 13b | [The TLC parser](13-tlc-parser.md): traces | M | most capable | 13a, 11 | |
| 14 | [The PlusCal parser](14-pcal-parser.md) | S | mid-tier | 07, 09 | |
| 15a | [Golden expected results](15-golden-expected-results.md): synthetic and TLC v1.7.4 | M | most capable | 13 | |
| 15b | [Golden expected results](15-golden-expected-results.md): TLC rolling | M | most capable | 15a | |
| 15c | [Golden expected results](15-golden-expected-results.md): SANY and PlusCal | M | most capable | 15a, 12, 14 | |
| 16 | [The messages helper (`Ui`)](16-ui-messages.md) | S | mid-tier | 02, 03 | |
| 17 | [The error handler, `main()` and `--debug`](17-error-handler.md) | M | most capable | 02, 03, 16 | Q6 |
| 18a | [The feature harness](18-feature-harness.md): in-process runner and steps | M | most capable | 02, 03, 07, 16, 17 | |
| 18b | [The feature harness](18-feature-harness.md): real processes and terminals | M | most capable | 18a | |
| 19 | [Layered settings](19-layered-config.md) | M | mid-tier | 02, 03, 16 | Q16 |
| 20 | [Java location and the remembered version check](20-java-location.md) | M | mid-tier | 02, 03 | |
| 21 | [The Java launcher](21-java-launcher.md) | L | most capable | 02, 03, 06, 17 | Q5 |
| 22 | [Version spec and jar information](22-version-spec-and-jarinfo.md) | M | mid-tier | 02, 03, 05 | |
| 23 | [Tool store](23-tool-store.md) | M | most capable | 02, 03, 22 | |
| 24 | [GitHub client](24-github-client.md) | M | most capable | 02, 03, 05 | Q6 |
| 25 | [Remote listing](25-remote-listing.md) | M | mid-tier | 05, 22, 23, 24 | Q7 |
| 26 | [Download and verify](26-download-and-verify.md) | M | most capable | 05, 22 to 25 | |
| 27 | [Install, upgrade, uninstall and pin as steps](27-install-steps.md) | L | most capable | 05, 16, 22 to 26 | Q8 |
| 28 | [First run: `ensure_tools` and the choice of build](28-first-run.md) | S | mid-tier | 05, 16, 22 to 25, 27 | |
| 29a | [The `tool` commands](29-tool-commands.md): install, upgrade, uninstall, pin, current, dir | L | most capable | 04, 05, 16 to 19, 22 to 28 | Q6, Q8 |
| 29b | [The `tool` commands](29-tool-commands.md): list, path, the last deletions | M | most capable | 29a | |
| 30 | [The module build](30-module-build.md) | M | most capable | 02, 03, 20, 23 | |
| 31 | [The `module` commands](31-module-commands.md) | M | mid-tier | 16 to 20, 28, 29, 30 | |
| 32 | [Spec, cfg and project root resolution](32-spec-resolution.md) | M | mid-tier | 02, 03 | |
| 33 | [The TLC invocation: preflight and command builder](33-tlc-invocation.md) | M | most capable | 19, 20, 21, 23, 30, 32 | Q9 |
| 34 | [Override classes and the check before a run](34-override-check.md) | M | mid-tier | 07, 23, 30, 33 | |
| 35a | [Run folders and their locks](35-run-folders.md): the steps and the stateful test | L | most capable | 02, 03, 21, 23 | Q9 |
| 35b | [Run folders and their locks](35-run-folders.md): `run_folder`, notes, listing, cleaning | M | most capable | 35a, 33 | |
| 36 | [The reporter interface](36-reporter-interface.md) | S | mid-tier | 03, 09, 20, 23 | |
| 37 | [The run functions `run_tlc` and `run_tlc_raw`](37-run-tlc.md) | M | most capable | 07, 09, 13, 21, 33, 35, 36 | Q10, Q12 |
| 38a | [The terminal reporter, plain output](38-terminal-reporter.md): code and v1.7.4 | L | most capable | 07, 09, 11, 13, 15, 16, 20, 23, 34, 36, 37 | Q4, Q11 |
| 38b | [The terminal reporter, plain output](38-terminal-reporter.md): rolling expected files | M | most capable | 38a | |
| 39a | [The `tlc` command](39-tlc-command.md): the switch and the in-process tests | L | most capable | 05, 07, 16 to 19, 28, 29, 31, 33, 34, 35, 37, 38 | |
| 39b | [The `tlc` command](39-tlc-command.md): real processes, pipes, terminals | M | most capable | 39a | Q10 |
| 40a | [The live display](40-live-display.md): layout mode | L | most capable | 07, 16, 18, 19, 36 to 39 | Q12 |
| 40b | [The live display](40-live-display.md): refresh interval and the terminal scenarios | M | most capable | 40a | Q16 |
| 41 | [The `sany` command and the shared shape of the other tools](41-sany-command.md) | M | mid-tier | 07, 12, 18, 20 to 23, 28, 32, 33, 38, 39 | |
| 42 | [The `pcal` command](42-pcal-command.md) | S | mid-tier | 07, 14, 18, 21, 38, 41 | Q13 |
| 43 | [The `repl` command](43-repl-command.md) | S | mid-tier | 18, 21, 22, 23, 41 | |
| 44 | [The `config` commands](44-config-commands.md) | M | mid-tier | 03, 16 to 19 | |
| 45 | [The `cache` commands](45-cache-commands.md) | M | mid-tier | 16, 17, 18, 20, 25, 35, 39 | Q14 |
| 46 | [`tlaup doctor`, replacing `check-java`](46-doctor.md) | M | mid-tier | 16 to 20, 22, 23, 24, 29, 39 | Q15 |
| 47 | [Shell completion](47-completion.md) | M | mid-tier | 05, 17, 18, 19, 22, 23, 25, 29, 30, 31, 39, 41, 42, 44 | |
| 48 | [The command tree, `-V`, and the end of tlaup's own exit 1](48-command-tree.md) | M | mid-tier | 29, 31, 39 to 47 | |
| 49 | [Startup cost](49-startup-cost.md) | S | mid-tier | 48 | |
| 50 | [Help text, wording and error messages](50-help-and-messages.md) | M | mid-tier | 48 | |
| 51 | [The generated CLI reference and its drift test](51-cli-reference.md) | S | mid-tier | 50 | |
| 52 | [Integration tests](52-integration-tests.md) | L | most capable | 08, 18, 23, 31, 39, 41, 42, 43, 45, 47 | |
| 53 | [The test workflow](53-ci-workflows.md) | M | mid-tier | 01, 03, 06, 09 | |
| 54 | [The integration job](54-integration-job.md) | M | mid-tier | 46, 52, 53 | |
| 55 | [Release script, release workflow and version bump](55-release-tooling.md) | M | most capable | 06, 53 | |
| 56 | [Dependabot, build fixes and package metadata](56-build-and-metadata.md) | S | mid-tier | 03, 09, 53 | |
| 57 | [Repository hygiene](57-repo-hygiene.md) | S | mid-tier | 03, 53, 56 | |
| 58 | [Lint rules](58-lint-rules.md) | M | mid-tier | 40, 48, 49, 50 | |
| 59 | [Closing checks](59-closing.md) | S | mid-tier | every other package | |

"Open" names the questions below that part of a package waits on. In every case the rest of the package can be built; the waiting part is not to be improvised (stage 5: a worker who finds the design wrong or silent stops and reports).

**Hardest packages**, for the most capable model and the most careful review: 21 (the launcher's signals, D51, D52, D60, with the signals machine as its test first), 35 (run folders and their locks, with the run-folder machine), 13 (the TLC parser, where the model, the code table and the facts first meet real output), 03 (the test foundation everything rests on), 18 (the step vocabulary and the real-process and terminal runners), 27 and 29 (the store's mutations with the store machine, and the switch of a whole command group), 39 (the switch of `tlaup tlc` with about ninety scenarios), 24 (the token's scope and the address rules, which are security-sensitive) and 15 (the line-by-line review of some three hundred expected files).

## Order and parallel work

The order follows [00, "Order of work"](../design/00-overview.md#order-of-work), item by item, with the changes argued under "Why the cut is this way". The graph by periods; within a period every line can run beside the others once its own "Waits for" is merged:

1. **01** alone: the one mechanical `ruff format` commit, before anything branches off (00 item 1).
2. **02** and **06**. 06 touches no existing module.
3. **03a**, then **03b**: the test foundation (00 item 2).
4. From 03 on, these tracks run side by side:
   - Clean-up: **04** (00 item 3).
   - Parser (00 item 4): **07**, **09**; then **08**, **10**, **11**, **12**, **14**; then **13a**, **13b**; then **15a**, **15b**, **15c**.
   - Groundwork (00 item 5): **16**, then **17** and **19**; **20**; **21** once 06 and 17 are in; **18a**, **18b** once 17 is in.
   - Store (00 item 6): **05**, then **22** and **24**; **23**, **25**, **26**, **27**, **28**; **29a** and **29b** once 04, 17, 18 and 19 are in.
   - Spec resolution: **32**.
   - Config commands: **44**, once 18 and 19 are in.
   - CI and release, which touch no `src/` (the design's claim, checked package by package in 53 to 57): **53** once 09 is in (its wheel check names both import packages), then **55** and **56**, then **57**.
5. Modules and runner (00 item 7): **30** once 20 and 23 are in; **31** after 29; **33**, **34**, **35a**, **35b**, **36**, **37**, **38a**, **38b**; then the switch **39a**, **39b**.
6. After 39, side by side (00 items 8 to 10): **40a** then **40b**; **41**, then **42** and **43**; **45**; **46**; **47** once 41, 42 and 44 are in.
7. **48**, the tree as a whole; then **49** and **50** side by side; then **51**, and **58** once 49 and 50 are in.
8. Integration (00 item 11): **52** once the tools and 45 and 47 are in; **54** once 52, 53 and 46 are in.
9. **59**, last.

The longest chain runs 01, 02, 03, 16, 17, 18, then the store to 29, the runner to 39, then 41, 42, 47, 48, 50, 51 and 59. The parser track and the store track are each about as long as the groundwork before 39, so work on all three at once shortens the release most.

**Files that packages of one period share.** Each package names them under Files. The ones that recur: `pyproject.toml` and `uv.lock` (one dependency or settings line each; the final text of every bound is fixed by D59, so two packages writing the same bound write the same line); `src/tlaup/cli.py` (one registration line or block per command package, rewritten as one block by 48); `CHANGELOG.md`; `tests/steps/*.py` (steps are added, never edited, by the package that owns them; 18 has the ownership table); `tests/features/errors.feature` (one block per package); `src/tlaup_parse/__init__.py` (export lines from 09 to 14); `src/tlaup/context.py` (one field each from 02, 16, 17, 19); `docs/contributing/development.md` (different sections). Where two packages of one period change the same function, the files say so and give the order: `java/classpath.py` (30, 31, 33, 41, 39), `tlc/invocation.py` (33, 34, 35b, 41), `project/core.py` (19 and 32, which write identical constants), `modules/build.py` (30, 34).

## Rules every package follows

- **The design's rules.** [00, "What every package must respect"](../design/00-overview.md#what-every-package-must-respect): the conventions, the exit codes of [02 X1](../design/02-cross-cutting.md#x1-exit-codes) and the stream rule of [02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr), the test rules of [01 T12](../design/01-testing.md#t12-rules-for-writing-tests), and D15's platform rules. The package rules of [00's tree](../design/00-overview.md#packages-after-the-first-wave): `tlaup_parse` imports nothing from `tlaup` and does no I/O; nothing imports `tlaup.cmd`; only `ui`, the reporters and the commands print; subprocesses from argument lists, HTTP with timeouts; domain functions get paths and settings as arguments.
- **The conventions.** [`docs/contributing/conventions.md`](../contributing/conventions.md): Conventional Commits, no AI attribution, a changelog entry in the same commit as each user-visible change, no aliases, shims or migrations (D14), no personal or machine data in anything committed.
- **One pull request each.** A package, or each listed part of one, is one pull request from its own worktree. It is done when its stated tests pass, `uv run poe lint` and `uv run poe test` pass, CI is green, its changelog entry and docs are written, and a separate review agent has reviewed it ([roadmap, review gates](../roadmap.md#how-the-work-is-done)).
- **Build beside, then switch.** The code in `src/` is release 0.8.x, and nearly all of it is replaced. A domain package adds new modules beside the old ones, with their own tests, and no command reaches them yet; the old code and its tests stay green. A switch package (29, 31, 39, 44, and 41 to 46 for their new commands) moves one command group onto the new code, deletes the old modules and the old tests [01 T11](../design/01-testing.md#t11-the-existing-tests) assigns to it, adds the feature files, and writes the changelog entries for what the user now sees. A test file is deleted in the pull request that rewrites what it tests, never earlier. Where an old command must keep working until its own switch, the earlier switch makes the smallest edit that keeps it working and says so (for example 29 points the old `tlc`'s jar lookup at the new store). That is not a shim in D14's sense: no old name, folder or layout stays readable for users. Nothing is released between packages (D6), so an in-between `main` may mix old and new behaviour; it is green, and no command is half-built.
- **Test first.** Where a stateful test of the formal check applies (21, 27, 35a), the package's first commit removes its `pending` markers, and the package deletes the matching `reference_*.py` model and its `*_reference_model` tests (D46, [03](../design/03-run-stages-and-specs.md#specs-and-their-tests)). The golden facts are written before the parser and marked pending by pattern ([08](08-golden-facts.md)); 13a and 13b remove the patterns. A pull request that fixes a defect shows the new test failing first (T12 rule 6).
- **Changelog where the user first sees it.** Domain packages mostly write no entry; the switch package that makes the change visible writes the design's entries word for word, and each file says which entries are its own.
- **Signatures are the intended shape.** A worker may adjust a name or a parameter if the behaviour and the tests stay, and says so in the pull request (design README). A shape marked "written by stage 4" is one the design leaves unwritten (for example the joints [03](../design/03-run-stages-and-specs.md#part-1-the-components-and-one-tlc-run) lists, `resolve_spec` or `make_reporter`); the review of this stage checks them.
- **Code that already passes the last lint rules.** [58](58-lint-rules.md) turns on what [30 I8](../design/30-ci-and-release.md#i8-lint-rules) and [14 F6](../design/14-config-and-cli.md#f6-messages) ask for, after the last command package. New code is written to pass them from the start: no blind `except` (two allowed, each with `noqa: BLE001` and a comment: the last branch of the root group's handler, F10, and the completers' guard, C3); only aware UTC datetimes or the injected `now` (DTZ); no `print` in `src/` (T20); no `typer.echo` and no `Console(` outside `tlaup/ui.py` and `tlaup/reporters/`; every `subprocess.run` states `check=`; every executable as an absolute path, from `locate` or `shutil.which`; no `unittest.mock.patch` in tests (TID251, from 03); mypy strict on `src/`, and on `scripts/` and `tests/fakes/` once 58 is in.
- **Never against the real folders.** A worker who runs `tlaup` by hand points it at temporary folders ([development guide](../contributing/development.md#running-tlaup-without-touching-your-own-folders); from 02 on, `TLAUP_HOME` does it in one variable).
- **Known gaps stay open.** Gaps the design postpones are named in the package they touch and are not closed there: the per-run `java.io.tmpdir` for v1.7.4's shared temporary module copies (question 27, after the first implementation; 33, 41), SIGTSTP forwarding (21), finding K1-8 on Windows (35), a pager that does not read (21, 37), `--verbose`, `--quiet`, `--color` and the JSON reporter (milestone 4; 38, 40).

## Why the cut is this way

The maintainer left the cut to stage 4. These are the choices a reader could ask about.

- **Build beside, then switch** (above), rather than rewriting each module in place. Nearly every old module is replaced and about twenty old test files patch old names by their dotted path; rewriting in place would change old behaviour package by package and break those tests long before the code they test is gone. One departure: [32](32-spec-resolution.md) changes `find_project_root` in place, because [01 T11](../design/01-testing.md#t11-the-existing-tests) rewrites its test at R10 and the old command then shows the new rule at once; 32 therefore writes R10's Breaking entry itself.
- **Errors and paths first** (02, before the test foundation). Every later package raises `TlaupError`, and the isolation fixture needs `TLAUP_HOME` ([01 T2](../design/01-testing.md#t2-isolation) depends on F2). 00 item 2 puts F2 in the test foundation; it is one small package before it instead, so 03 is not larger still.
- **The lifeline jar on its own, early** (06). It touches no existing module, and the launcher (21) and CI (53) need it.
- **Settings before the store and the runner** (19, in the groundwork). 00 item 10 puts F1 and F3 with the commands, but the run folders (`tlc.keep`), the Java options, the reporter (`tlc.plain`) and the commands that pass the repository address all read settings. 19 keeps the old readers working (its file has the table of removed keys and who deletes each last reader); the `config` commands (44) are separate and can land early.
- **The module build before the runner** (30). 00 item 10 puts M1 to M3 with the commands, but the preflight's classpath (33) and the override check (34) need the registry and the class-file reader.
- **The reporter interface and the plain reporter before the switch of `tlaup tlc`** (36, 38). 00 item 8 puts the reporters after the runner. `run_tlc` (37) takes a reporter, and the switch (39) needs something that prints; only the live display (40) waits until after the switch. 38 waits for the golden expected results (15), which keeps the roadmap's rule that the reporter work starts after the golden tests pass.
- **Facts before the parser, as pending patterns** (08). The design asks for the facts first and failing; `main` stays green because the facts carry the existing `pending` marker by pattern (`case:topic:name`), and 13a and 13b remove the patterns as their first commits. The patterns allow 13 to land in two parts. `facts.py` holds TLC facts only; SANY and PlusCal assertions are 12's and 14's (question Q18).
- **The manifests with the recordings** (05). Three tracks need `tests/unit/data/manifests/`; 05 is the first of them and builds a small jar from a recorded manifest, so it moves them.
- **`tlaup/stdio.py` in the error handler** (17). The launcher (21) needs `reader_gone`, which F10 defines beside `main()`, and must not import `tlaup.cli`; 17 puts it in a module that imports neither Typer nor Rich.
- **`doctor` after the `tlc` switch** (46). The old runner is the other caller of `java/inspector.py`, which `doctor` deletes with `check-java`.
- **The test workflow before the integration job** (53, 54). The integration job joins the `Test` job and the schedule that the test workflow writes.
- **Help text before the reference** (50, 51), not after. 50's pull request carries a full help dump at 100 columns, which its review reads; 51's first checked-in reference is then the reviewed text. The reverse order would review the text twice.
- **Splits.** Nine packages are delivered as several pull requests, each split at a seam its file states, so that each review fits one sitting: 03 (helpers, then switching them on), 13 (messages, then traces), 15 (by build and tool: some 323 expected files), 18 (in-process, then real processes and terminals), 29 (by command; reading commands first would leave two stores live or nothing to install with), 35 (the step functions with the stateful test, which needs every step at once, then the rest), 38 (by build, for its expected files), 39 and 40 (along their files' parts A and B). Not split, although proposed: 08 (every fact is pending, so its review is of reading the captures, which does not divide well), 27 (the store machine needs install, upgrade, uninstall and pin together) and 52 (tests only, and each half would need the same harness).

## Questions for the maintainer

The design was signed off as it stands, and stage 4 changed none of it. Where a package needed a choice the design does not make, the package marks the part that waits, gives a recommendation, and the rest can be built. The first list blocks a part of a package; the second asks the maintainer to confirm a reading a package already uses; the third is clerical, for one round of fixes.

### Questions a part of a package waits on

| # | Name used in the files | Sections | What is wrong or missing | Options | Recommendation | Waits |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | `format-markdown` | [30 I5](../design/30-ci-and-release.md#i5-workflow-hygiene) | The locked ruff also formats Python code blocks inside Markdown, so the format commit would rewrite seven signed-off design documents and the package files. | Exclude `*.md` from `ruff format`; or let it rewrite them. | Exclude: `[tool.ruff.format] exclude = ["*.md"]` (tried: it leaves exactly the eight Python files). | 01 (one line) |
| Q2 | `pytest-mock-removal` | [01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 2, [T2](../design/01-testing.md#t2-isolation), [T11](../design/01-testing.md#t11-the-existing-tests) | T12 and T2 remove `pytest-mock` in the first testing package; T11 deletes no test before what replaces it. About twenty old test files that live until their switch use `mocker`, and three fixtures stand for GitHub and TLC output that only 05 and 07 replace. | Keep `pytest-mock` and those three fixtures until their files go, with a hook that forbids new uses; or port everything in 03, which then waits for 05 and 07. | The first: a `no-new-mocker` hook over a legacy list that only shrinks; 59 removes the dependency when the list is empty. | 03b |
| Q3 | research 22 adoption | [01 T3](../design/01-testing.md#t3-golden-files) | T3 adopts research 22's captures "like research 1's" and leaves five placements open: the re-runs that duplicate research 1 and 12 under the same names; non-empty stderr files; two different `Live.tla` specs; stale-PlusCal inputs that differ per build; research 28's two class-version captures, which R7 calls golden and T3's table omits. | 07's file gives the options for each. | Keep research 1 and 12 as the golden files; move v1.7.4's one non-empty TLC `.err` beside its `.out`; do not adopt `tool-live`; put per-build inputs in `golden/specs/<build>/`; move research 28's captures as `override-class-too-new-{index,listed}`. | 07 |
| Q4 | exit status words | [02 X1](../design/02-cross-cutting.md#x1-exit-codes), [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package) | `describe_exit_status` needs a word and a meaning for every TLC code; X1 gives only the five manifest words, and no test is named. These words become milestone 4's JSON. | The maintainer supplies the table; or the worker proposes it in the pull request. | Settle it now: 14 assertion failure, 75 to 77 evaluation failure, 150 parse error, 151 configuration error, 255 error, 1 usage error (`known`, noting that the JVM also returns 1), 152 and 153 known with upstream's names. | 09 (one table); the expected files of 38 that show the meaning |
| Q5 | SIGQUIT in the signals machine | [20 G3](../design/20-groundwork.md#g3-java-launcher) (D60), `tests/stateful/test_signals.py` | D60 forwards SIGQUIT to the JVM of a parsed run; the signals machine, last revised before D60, draws SIGQUIT in any phase and expects no change, and its fake child has no SIGQUIT handler, so a launcher that follows G3 kills it. | Give the fake child a handler that notes SIGQUIT and carries on, and assert the note in streaming runs; keep SIGQUIT away from an attached streaming child; or change the design. | The first. It is an edit to a test of the formal check, so it needs the maintainer's word. | 21 (one test edit) |
| Q6 | debug filter | [12 V7](../design/12-tools-and-downloads.md#v7-github-client), [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks) | The filter that keeps the token and query strings out of `--debug` output has no home or signature; a collecting filter would be process-wide state, which 00 allows only in the context, and the handler must reach it without importing `requests`. | A stateless `redact(text, env)` in a light module; a registry reset by the isolation fixture; state on `Ui` or the context. | The first, owned by 24 and called by 17's handler; it must be in before 29, the first command that reads the token. | 17, 24, 29 (one scenario and one test) |
| Q7 | missing asset in the cached list | [12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache) | "A missing asset or a 404 is never cached": seven of the seventeen real releases have no jar, so read literally nothing is ever cached. | Cache the list as it came and never cache an error answer; or cache nothing that has a release without a jar. | The first; the upload gap then shows in `tool list` for up to an hour. 25 is written so. | 25 (a reading) |
| Q8 | uninstall race | [12 V1](../design/12-tools-and-downloads.md#v1-version-store), [V3](../design/12-tools-and-downloads.md#v3-uninstall) | When one of two named builds is removed by another tlaup before this one takes the lock, V1 (gone meanwhile is code 4) and V3 (one argument that matches nothing removes nothing) give no rule. | Remove the rest and exit 4 naming the gone ones; or remove nothing. | The first, which is what the store machine's step does. | 27, 29 |
| Q9 | recover path that does not exist | [11 R6](../design/11-runner.md#r6-run-folders), `tests/stateful/test_run_folders.py` | 33 reads R6 as "a `-recover` path that does not exist is TLC's to judge" and takes no lock; the run-folder machine passes `runs/<id>/states` with `states/` missing and expects the folder's lock to be taken. | The rule "the path, with links resolved, lies under an existing `runs/<id>/`"; or "the path exists". | The first: taking the lock costs nothing and protects the folder. 35 is written so; one test of 33 changes with it. | 33 (one test), 35b |
| Q10 | checkpoint signal steps | [11 R6](../design/11-runner.md#r6-run-folders), [20 G3](../design/20-groundwork.md#g3-java-launcher), [01 T4](../design/01-testing.md#t4-fakes-at-the-edges), [T5](../design/01-testing.md#t5-feature-files-and-steps) | No step can place a signal between messages 2195 and 2196: `once java is running` signals at the JVM's start, `send twice` waits for a signal the deferral withholds, and plain output prints nothing for either message. Also, the fake commits its checkpoint after replaying line m, while TLC commits before it prints 2196, so a test of the one-signal deferral would race. | A step that waits for a marker the fake logs when it begins a checkpoint (one T4 field and one T5 step); or plain pytest only, as 37 already has. Fake: commit before writing line m. | The step, since the design wants the real process; and the fake's commit before line m. | 39b (two scenarios); 37 notes it |
| Q11 | terminal reporter readings | [22 O3](../design/22-reporters.md#o3-terminal-reporter) | O3 does not place four events (checkpoint started and written, recovered, finished), leaves gaps in the header and the hint line, and has no words for "not checked" after an exception before the initial states. | 38's file states each reading and the alternative. | Confirm 38's readings: the four events print nothing; the header leaves out what is not known; "not checked: TLC failed before computing the initial states (TLC exit code N: ...)". | 38a |
| Q12 | waiting line under the layout | [14 F6](../design/14-config-and-cli.md#f6-messages), [20 G3](../design/20-groundwork.md#g3-java-launcher) | The line printed while a first signal is held during a checkpoint goes through `notice` between the reporter's start and close, which F6 forbids while a reporter is up; under the alternate screen it would be lost. G3 and 03 also disagree on who prints it; 21 gives the runner a hook and 37 the wording. | Through the reporter (the Status panel, copied to stderr on close); or leave it on stderr. | Through the reporter. 40 is written so and adds `Reporter.notice`. | 37, 40a |
| Q13 | pcal added labels | [21 S2](../design/21-other-tools.md#s2-pcal) | Step 3 recognises the labels the translator added; step 4 never says where they are printed, so `-- -label -reportLabels` reports nothing through tlaup. | Not printed; on stdout as `<spec>:<line>:<col>: label <name> added`; on stderr as notes. | On stdout: labels are part of the result (X2), and the position form lets an editor jump to them. | 42 |
| Q14 | cache clean with --all and a kind | [23 C1](../design/23-command-layout.md#c1-command-tree) | C1 does not say what `cache clean --runs --all` or `--remote --all` does. | `--all` widens whichever kind is named, and the Java check goes only when no kind is named; or the combination is a usage error. | The first. 45 builds it and writes no scenario for the combination until answered. | 45 |
| Q15 | doctor levels | [23 C1](../design/23-command-layout.md#c1-command-tree) | C1 names the checks and the words `ok`, `warning`, `error` but not which finding is which. | 46's rule: an error is whatever makes a run stop with 3. | Confirm, in particular `javac` missing as a warning and nothing pinned as an error. | 46 |
| Q16 | refresh interval range | [22 O5](../design/22-reporters.md#o5-refresh-interval), [14 F1](../design/14-config-and-cli.md#f1-layered-configuration) | O5 wants an out-of-range `tlc.refresh_interval` from the file or the environment to exit 2; F1 makes a bad value in the file or the environment `ConfigInvalid`, code 3. | Range in the schema, so the file and the environment give 3 and O5's test changes; or type only in the schema and the range in the command, which gives 2 wherever the value came from. | The first, which keeps F1's rule uniform; 19 and 40 are written for the second, and the change is a line in each. | 19, 40b |
| Q17 | stateful tests under warnings as errors | [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings), `tests/stateful/` | With `filterwarnings = error` (T10), six reference-model tests of the formal check fail on `ResourceWarning` (pipes and processes not closed); they pass without it. | 03 fixes the resource handling in those test files, changing no rule or invariant; or add an `ignore` line. | The fix in 03; it touches tests of the formal check, so it needs the maintainer's word. | 03b |
| Q18 | facts for SANY and PlusCal | [21 S5](../design/21-other-tools.md#s5-golden-files-for-sany-and-pluscal), [01 T3](../design/01-testing.md#t3-golden-files), [T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings) | S5 asks for facts and a full expected result per SANY and PlusCal case, but a fact takes a `RunResult` and is shared with the integration tests, and neither `SanyResult` nor `PcalResult` has a dictionary form. T10 says `pending` marks the stateful tests, not the facts. | 08's reading: `facts.py` holds TLC facts only; SANY and PlusCal assertions are 12's and 14's, written failing first; 12 and 14 add `to_dict()`. | Confirm, and add half a sentence each to S5, T3 and T10. | none (the packages are written so) |

### Readings to confirm

Each is used by the package named and written there as a reading, so nothing waits on it.

- [09](09-parse-package-and-model.md), [13](13-tlc-parser.md): the twenty members of `Event` and their fields; a fresh `RunResult` has the verdict `incomplete`; the `Phase` values; `RunResult.from_dict`; `OverrideLoaded.java_class` kept as printed (it is a `file:` address for module overrides found as class files, 12 of 41 instances); `FinalStats.collision_probability` keeps the optimistic of 2193's two estimates; which messages set `workers`.
- [07](07-golden-files.md), [10](10-framing-and-codes.md), [13](13-tlc-parser.md): three synthetic cases T3's list lacks (a file with `\r\n`, one cut off before 2186, an unknown code with error severity, which P4 rule 4 needs and no capture has) are written by 07.
- [17](17-error-handler.md): `reader_gone`, `is_pipe` and their helpers in a new `tlaup/stdio.py` (F10 names no module); an old command's `typer.Exit(1)` stays 1 until 48; an uncaught exception from an old command now gives 5 with one line.
- [19](19-layered-config.md): `TLAUP_MODULE_PATH` and `TLAUP_MODULE_LIB_PATH` for the two keys with no section; the header line of a written config file names a reference page that does not exist yet (one constant; name the planned page now).
- [21](21-java-launcher.md): `ProcessOutcome.stopped_for_closed_pipe`, `pass_fds` and `stop_when_reader_gone` on `ChildRun`, the `on_held` hook; and several silences listed under its Context (a malformed agent argument, whether the agent's source ships in the sdist, which JDK builds the shipped jar, `-cp` for an empty classpath).
- [24](24-github-client.md), [25](25-remote-listing.md), [26](26-download-and-verify.md), [27](27-install-steps.md): the shapes V7 names without giving (`progress`, `DownloadInfo`, a status code on the error); `fetch_build` cannot hand back the refreshed release after its one retry, which costs one extra download at the next install for a release without a digest; which errors mean "GitHub cannot be asked" (network, rate limit, bad data; not a tag's 404).
- [28](28-first-run.md), [29](29-tool-commands.md): the which-build question has no default; `uninstall --all` asks y or n with n the default; the first-run prompt when no stable release exists is the lookup's own error; `tool list`'s status column and the marking of a stale cached list.
- [30](30-module-build.md), [31](31-module-commands.md): `javac` compiles against the build's jar and the module's own `lib/*.jar` only (today it also sees other modules and `module_lib_path`; a Changed entry says so); the age of a `.tmp/` entry is read from its name against the injected `now`, since T12 rule 5 forbids modification times; one step added to T5's list, `javac is version "<v>"`.
- [33](33-tlc-invocation.md), [35](35-run-folders.md), [37](37-run-tlc.md): `--workers` and `--keep` travel in the request only, not in the settings' flags layer that F1 mentions; `-seed` drawn from 0 to 2^63-1 (not checked against TLC; 52 proves it); the locale test of R3's path warning; `RunOutcome.kept` carries rundirs' whole `Kept`, and `kept_note` makes the two note lines; `run.json` gains a `reason` key for why a folder was kept.
- [38](38-terminal-reporter.md), [40](40-live-display.md): the phase word "Starting" for the two phases O4 leaves out; the layout frames are drawn from v1.7.4; two duration forms stay two (O3's result line and R6's note).
- [39](39-tlc-command.md): R7's changelog entry "the run output lists the operator overrides TLC reports loading" has nothing behind it in the first wave (O3 prints nothing for `OverrideLoaded`, R7 puts the list in a verbose header of milestone 4); 39 should drop or defer it. Recommendation: defer.
- [44](44-config-commands.md): an Added entry for `config path` and `config get`, which C1 gives none.
- [18](18-feature-harness.md), [45](45-cache-commands.md), [46](46-doctor.md): answers on a terminal are typed at once and read one line per read; `the java command matches the expected file` replaces the scenario's folders, the lifeline's process id and the run id first; a placeholder `{kept-id}`; no step scripts a Java whose version answer is not a version, or sets `javac`'s version alone; `rundirs.clean_lock_files` and `ToolStore.leftovers()` added for `cache clean` and `doctor`.
- [52](52-integration-tests.md), [53](53-ci-workflows.md), [54](54-integration-job.md), [58](58-lint-rules.md): `TLAUP_TEST_JARS` may name a store's tool folder as well as T9's `<build>/tla2tools.jar` folder, and a stable jar's tag comes from the folder name or `build.json`; the integration fixture keeps `JAVA_HOME` as well as `PATH` (I1 needs it, T2 says only `PATH`); the lifeline job is a required check (I2 says so, I5's list omits it); `uv sync --upgrade` in the newest-dependencies job is the one exception to `--locked`; `git` and the editor are resolved with `shutil.which` once bandit's B607 skip goes; T20 applies to the whole tree with `scripts/` and `tests/fakes/` exempt; B1 to B3 get no changelog entry; the Python 3.15 classifier is checked once against `trove-classifiers`; the reused-process-id test of the lifeline may need `sudo` for `unshare` on the hosted runner.
- [03](03-test-foundation.md): each declared run of the fake `java` is used once (T4 says "the first entry that matches", T5's two-run scenarios need each used once); no bounds are designed for `hypothesis` and `pytest-randomly` (the locked version as the floor, the next major as the cap).

### Clerical

- [14 F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay)'s YAML block names the section `tools:` and lacks `tlc.keep`; [F7](../design/14-config-and-cli.md#f7-help-text)'s table and changelog text, [12 V1](../design/12-tools-and-downloads.md#v1-version-store) ("under `tools/`", three times), [V7](../design/12-tools-and-downloads.md#v7-github-client) (`tlaup --debug tools install rolling`), V8 and [01 T11](../design/01-testing.md#t11-the-existing-tests) (`tools_*.feature`, `tools_list.feature`) still use the plural names D47 replaced.
- [13 M1](../design/13-modules-and-java.md#m1-module-names) and its Fixed entry say `../tools` (now `<cache>/tool`, so `../tool`), and the entry names `tlaup module remove`, a spelling that never existed before the rename.
- [12 V4](../design/12-tools-and-downloads.md#v4-upgrade-and-pin)'s sketch `upgrade(store, client, name | None)` lacks the remote; 27 writes `upgrade(store, remote, client, spec, ...)`.
- [20 G1](../design/20-groundwork.md#g1-tlc-invocation)'s sketch writes `ui.out(...)` and `notice=ui.notice`; in F6 `out` is a console and the method is `note`.
- [22 O4](../design/22-reporters.md#o4-live-display)'s terminal scenario asserts "`Result: interrupted`"; O3's table writes "Result: incomplete, interrupted after ...".
- [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package)'s changelog entry says `tlaup.tlc.models` is gone; the layout code keeps it until 40.
- Two changes have two changelog entries each: a killed tlaup (R6 Added and G3 Fixed) and a Ctrl-C that waits for a checkpoint (R6 Changed and G3 Changed); 39 writes both until told otherwise. C1's "`config edit EDITOR` no longer takes the editor" duplicates F5's Breaking entry (44 writes it once); V8's Removed entry for `fetch-cache clear` duplicates half of C1's cache row (29 and 45 divide it).
- [10 P4](../design/10-parser.md#p4-framing-and-never-losing-output) rule 2 lists the typed codes without 2271, 2204 and 2195 to 2198, and P5 calls 2204, 2210 and 2271 information, while P3's event table types them (13 follows the table); the upstream name of code 2285 is recorded nowhere; P3 counts 37 instances of 2168 where the captures now have 41; the old 2186 pattern knows only `Finished in <n>ms` while 54 captures print `Finished in 01s`; [P8](../design/10-parser.md#p8-sany-output)'s "Depends on P2, P4" holds only for the window inside TLC, and its "36 on rolling" counts a list file as a capture; P3's verdict test names a case `cfg-error`, which does not exist.
- [01 T3](../design/01-testing.md#t3-golden-files) puts `<case>.json` beside the `.out`, and [T8](../design/01-testing.md#t8-expected-output-files) says expected files live under `expected/` (15 follows T3); T3's list of synthetic cases lacks the three named under "Readings to confirm"; T11 counts "185 test functions in 43 files" (207 items are collected today), calls two `mkdir` lines in `tools/test_path.py` "legacy-folder tests", omits the four `check-java` command tests, and says `test_check_java.py` is kept "until J2" although the old code it tests lives until 46; T4 gives the fake `javac` no `-version` answer, which M3 needs; T5's list of feature files has none for completion or for `-V`.
- [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)'s pytest block has no `lifeline` marker, which [30 I2](../design/30-ci-and-release.md#i2-unit-job) needs; I2's list of lifeline-job tests omits G3's `-Xrs` case and the REPL on a pseudo-terminal; [I5](../design/30-ci-and-release.md#i5-workflow-hygiene)'s required jobs omit the lifeline job; I8 lists one allowed blind `except` and C3 needs a second.
- [21 S1](../design/21-other-tools.md#s1-sany)'s feature list names `-- -bogus`, but the matching capture is `sany-grouped-unknown` (`-xy`); S1's hint names "the generic exec command once milestone 4 adds it", which a 0.9.0 message cannot name.
- [00](../design/00-overview.md#packages-after-the-first-wave)'s tree does not list the modules stage 4 added: `tlaup/stdio.py` (17), `project/spec.py` (32), `java/opts.py` (33), `versioning/first_run.py` (28), `reporters/text.py` (38), `cmd/common.py` (41), `tlaup/doctor.py` (46).
- No `.gitattributes` rule protects the golden files' bytes under `core.autocrlf` on Windows; 07's consistency test catches a rewritten file.

## Not cut

- **Roadmap items that are repository settings or the maintainer's to do**, named in the package they touch: the ruleset on `main` (I7; it waits on 53's check name `Test`), the `pypi` environment's reviewer and bypass (L5), the backfill of old release pages (L3), GitHub topics (B3), the hand check of completion in an interactive zsh and fish before the release (47), and the roadmap's [maintainer actions](../roadmap.md#maintainer-actions-and-sessions), of which two-factor confirmation and capturing CI logs touch 55 and 53.
- **The documentation track** ([roadmap](../roadmap.md#documentation-track-parallel-start-with-milestone-1)) is not designed, except the CLI reference generator and its drift test ([23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference), package 51) and the development guide changes [01 T11](../design/01-testing.md#t11-the-existing-tests) names (03, and each package that changes the code map). Not cut, for want of a design: the README rewrite, the concepts page, the examples and their manifest (so T9's examples row is not built in 52), running the README quick start in CI, the reference pages, the guides, troubleshooting, the welcome page of the contributing guide, the changelog checks in CI and the changelog history.
- **Postponed by the design**, named in the package they touch and not closed: see "Known gaps stay open" above, and running the `specs/` models in the integration job ([03](../design/03-run-stages-and-specs.md#specs-and-their-tests): "a later step and not part of this plan").

## Traceability

### Roadmap items of milestones 1, 1b and 2

Every open item (`- [ ]`) of the three milestones, by its line in the [roadmap](../roadmap.md), maps to one owning package: the one that builds the item, or, for a removal or a switch, that does it. "With" names the packages that hold a part. Ticked items (the new name, trunk plus tags, Dependabot alerts, the Nix flake) need no package. Where a design departs from an item's wording, the [design index's list of departures](../design/README.md#where-the-design-departs-from-the-roadmap) wins.

| Line | Milestone | Item | Design | Owner | With |
| --- | --- | --- | --- | --- | --- |
| 147 | 1 | Capture real `-tool` output from TLC 1.7.4 and the ... | P1, T3 | [07](07-golden-files.md) | [08](08-golden-facts.md), [13](13-tlc-parser.md), [15](15-golden-expected-results.md) |
| 149 | 1 | Move the parser stack (message framing, codes, values, models, ... | P2, P3 | [09](09-parse-package-and-model.md) | [10](10-framing-and-codes.md) to [14](14-pcal-parser.md); [39](39-tlc-command.md) deletes the old stack |
| 152 | 1 | Never lose output (decision D9): anything the parser does ... | P4 | [10](10-framing-and-codes.md) | [13](13-tlc-parser.md), [39](39-tlc-command.md) |
| 153 | 1 | Read the TLC version from the startup message so ... | P9 | [13](13-tlc-parser.md) |  |
| 154 | 1 | Fix error-trace parsing so real counterexamples yield states: location ... | P5 | [13](13-tlc-parser.md) |  |
| 157 | 1 | If TLC can write traces as JSON itself (investigation ... | P6 | [13](13-tlc-parser.md) | nothing is built (P6) |
| 160 | 1 | Fix function-valued variables (`(a :> 1 @@ b :> ... | P7 | [11](11-values.md) |  |
| 161 | 1 | Fix SANY error grouping: errors are flushed after every ... | P8 | [12](12-sany-parser.md) | [13](13-tlc-parser.md) |
| 164 | 1 | Show the violated-invariant text together with the trace. Today ... | P10 | [38](38-terminal-reporter.md) |  |
| 165 | 1 | Print TLC text without Rich markup interpretation; today, on ... | P11 | [38](38-terminal-reporter.md) |  |
| 169 | 1 | Report run errors as what they are. Today every ... | R1 | [37](37-run-tlc.md) | [17](17-error-handler.md), [21](21-java-launcher.md), [39](39-tlc-command.md) |
| 173 | 1 | Forward SIGTERM to the JVM so a CI timeout ... | R2, G3 | [37](37-run-tlc.md) | [21](21-java-launcher.md), [39](39-tlc-command.md) |
| 175 | 1 | Do not crash on non-UTF-8 bytes in TLC output. ... | R3 | [37](37-run-tlc.md) | [16](16-ui-messages.md), [21](21-java-launcher.md), [39](39-tlc-command.md) |
| 176 | 1 | Pass a `--cfg` file outside the project root to ... | R4 | [32](32-spec-resolution.md) | [33](33-tlc-invocation.md), [39](39-tlc-command.md) |
| 180 | 1 | Spec names: a dot in the name is mangled ... | R5 | [32](32-spec-resolution.md) | [39](39-tlc-command.md) |
| 181 | 1 | Stop run-cache cleanup from deleting other specs' directories: it ... | R6 | [35](35-run-folders.md) | [39](39-tlc-command.md), [45](45-cache-commands.md) |
| 190 | 1 | Report clearly when an override module fails to load ... | R7 | [34](34-override-check.md) | [38](38-terminal-reporter.md), [39](39-tlc-command.md) |
| 195 | 1 | The project-root rule counts a parent folder that has ... | R10 | [32](32-spec-resolution.md) |  |
| 196 | 1 | The run-cache fingerprint covers the default `.cfg` only, not ... | R12, R6 | [35](35-run-folders.md) | [39](39-tlc-command.md) deletes the old code |
| 197 | 1 | The module build strips `//` comments with a regex ... | M3 | [30](30-module-build.md) | [31](31-module-commands.md) |
| 198 | 1 | Unknown config keys are silently ignored, so a typo ... | F1 | [19](19-layered-config.md) |  |
| 202 | 1 | Pass everything after `--` to TLC. Add `--workers`, defaulting ... | R8 | [33](33-tlc-invocation.md) | [39](39-tlc-command.md) |
| 205 | 1 | Make `--show-command` print the exact command that would run, ... | R9 | [39](39-tlc-command.md) | [35](35-run-folders.md) |
| 211 | 1 | Reject module names containing path separators or `..`, absolute ... | M1 | [30](30-module-build.md) | [31](31-module-commands.md) |
| 212 | 1 | `modules add` builds in a temporary folder and swaps ... | M2 | [30](30-module-build.md) | [31](31-module-commands.md) |
| 213 | 1 | Fix `tools uninstall --all`, which stops after removing the ... | V3 | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| 214 | 1 | A failed uninstall exits non-zero and does not move ... | V3 | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| 215 | 1 | Concurrent installs: write the pin and metadata atomically and ... | V11, V1 | [27](27-install-steps.md) | [23](23-tool-store.md), [29](29-tool-commands.md) |
| 219 | 1 | Remove installs from a URL (decision D13). Do this ... | V6 | [04](04-delete-dead-code.md) |  |
| 220 | 1 | Download to a temporary file, check it is a ... | V5 | [26](26-download-and-verify.md) | [22](22-version-spec-and-jarinfo.md), [23](23-tool-store.md), [27](27-install-steps.md), [29](29-tool-commands.md) |
| 221 | 1 | Refuse unencrypted addresses and any redirect to one. (S) ... | V7 | [24](24-github-client.md) |  |
| 222 | 1 | After download, compare the commit the jar reports about ... | V5 | [26](26-download-and-verify.md) | [22](22-version-spec-and-jarinfo.md), [27](27-install-steps.md) |
| 226 | 1 | Read all pages of tags and releases; choose "latest ... | V8 | [25](25-remote-listing.md) | [24](24-github-client.md) |
| 230 | 1 | GitHub token support (`GITHUB_TOKEN`, `GH_TOKEN`), `Accept` and `User-Agent` headers, ... | V7 | [24](24-github-client.md) | [29](29-tool-commands.md) |
| 233 | 1 | Do not crash on a non-JSON or non-list API ... | V7, V8, V4 | [24](24-github-client.md) | [25](25-remote-listing.md), [27](27-install-steps.md) |
| 237 | 1 | One preflight used by every `tlaup tlc` path, checking ... | R11 | [33](33-tlc-invocation.md) | [39](39-tlc-command.md) |
| 238 | 1 | No tracebacks for users: missing Java, missing jar with ... | F10 | [17](17-error-handler.md) | [39](39-tlc-command.md) and the other switch packages |
| 243 | 1 | First-run prompt (decision D4): when nothing is pinned, ask ... | V9, X4 | [28](28-first-run.md) | [29](29-tool-commands.md), [39](39-tlc-command.md) |
| 245 | 1 | Remove the legacy fallback jar path, so it is ... | V10 | [04](04-delete-dead-code.md) | [23](23-tool-store.md), [29](29-tool-commands.md), [33](33-tlc-invocation.md) |
| 249 | 1 | Java options: a `TLAUP_`-prefixed variable and a repeatable flag, ... | J1 | [33](33-tlc-invocation.md) | [39](39-tlc-command.md) |
| 250 | 1 | Use `JAVA_HOME` when set, falling back to `PATH`, for ... | J2 | [20](20-java-location.md) | [31](31-module-commands.md), [39](39-tlc-command.md), [46](46-doctor.md) |
| 251 | 1 | One Java start per run: read the TLC version ... | J3 | [20](20-java-location.md) | [13](13-tlc-parser.md), [23](23-tool-store.md), [29](29-tool-commands.md), [39](39-tlc-command.md) |
| 258 | 1 | Layered configuration (decision D10): packaged defaults, user file, environment, ... | F1 | [19](19-layered-config.md) | [44](44-config-commands.md) |
| 259 | 1 | `config` commands work when the file is broken, and ... | F4 | [44](44-config-commands.md) | [19](19-layered-config.md) |
| 260 | 1 | Remove settings nothing reads (`workspace.root`, `workspace.spec_dir`, the unread `tla.community_modules` ... | F3 | [19](19-layered-config.md) |  |
| 261 | 1 | Environment overrides for the tool's folders (decision D25). Lands ... | F2 | [02](02-errors-and-paths.md) |  |
| 262 | 1 | `config edit`: accept `$VISUAL` and `$EDITOR` values with arguments ... | F5 | [44](44-config-commands.md) |  |
| 266 | 1 | Error messages (raised list): list the locations searched when ... | F11 | [50](50-help-and-messages.md) | [24](24-github-client.md), [25](25-remote-listing.md), [27](27-install-steps.md), [28](28-first-run.md), [30](30-module-build.md), [32](32-spec-resolution.md), [33](33-tlc-invocation.md) |
| 267 | 1 | Route every message through the one UI helper; there ... | F6 | [16](16-ui-messages.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md), [44](44-config-commands.md), [50](50-help-and-messages.md), [58](58-lint-rules.md) |
| 268 | 1 | Help text (raised list): what `upgrade` means (newest build ... | F7, C5 | [50](50-help-and-messages.md) | [51](51-cli-reference.md) |
| 269 | 1 | Wording: one word for a stopped run ("canceled" and ... | F8 | [50](50-help-and-messages.md) | [31](31-module-commands.md), [38](38-terminal-reporter.md), [40](40-live-display.md) |
| 273 | 1 | Skip the `git rev-parse` call on normal installs; load ... | F9 | [49](49-startup-cost.md) |  |
| 283 | 1b | A single TLC invocation value (spec, cfg, project root, ... | G1 | [33](33-tlc-invocation.md) | [37](37-run-tlc.md), [39](39-tlc-command.md) |
| 284 | 1b | A small family of domain errors (spec not found, ... | G2, X1 | [02](02-errors-and-paths.md) | [17](17-error-handler.md) |
| 286 | 1b | A generic Java tool invocation (jar, classpath, JVM options, ... | G3 | [21](21-java-launcher.md) |  |
| 292 | 1b | The lifeline agent (decision D51): a small Java agent ... | G3, CI | [06](06-lifeline-agent.md) | [21](21-java-launcher.md), [53](53-ci-workflows.md), [52](52-integration-tests.md) |
| 293 | 1b | `sany` command: parse a spec and report diagnostics with ... | S1 | [41](41-sany-command.md) |  |
| 299 | 1b | `pcal` command: run the PlusCal translator; passthrough for its ... | S2 | [42](42-pcal-command.md) | [14](14-pcal-parser.md) |
| 302 | 1b | `repl` command: interactive, so no output parsing; the terminal ... | S3 | [43](43-repl-command.md) |  |
| 304 | 1b | Keep all three thin (note 15): no logic beyond ... | S4 | [41](41-sany-command.md) | [42](42-pcal-command.md), [43](43-repl-command.md) |
| 306 | 1b | Golden-file tests for SANY and PlusCal output per TLC ... | S5, T3 | [12](12-sany-parser.md) | [07](07-golden-files.md), [14](14-pcal-parser.md), [15](15-golden-expected-results.md), [41](41-sany-command.md), [42](42-pcal-command.md), [43](43-repl-command.md) |
| 313 | 1b | A reporter interface fed by the parsed result and ... | O1 | [36](36-reporter-interface.md) | [37](37-run-tlc.md), [39](39-tlc-command.md) |
| 314 | 1b | Delete display code that nothing in `src/` references (`StatusFooterComponent`, ... | O2 | [04](04-delete-dead-code.md) | [40](40-live-display.md) |
| 315 | 1b | Live terminal reporter: render the layout on a terminal; ... | O3, O4 | [40](40-live-display.md) | [38](38-terminal-reporter.md) |
| 319 | 1b | Make `--refresh-interval` and the matching config key take effect. ... | O5 | [40](40-live-display.md) |  |
| 320 | 1b | Fix the per-line re-rendering cost, which grows with the ... | O7 | [40](40-live-display.md) | [38](38-terminal-reporter.md) |
| 321 | 1b | Snapshot tests through a fixed-width, colourless console with an ... | O6, T8 | [40](40-live-display.md) | [03](03-test-foundation.md), [38](38-terminal-reporter.md) |
| 325 | 1b | Review the layout of every command so it follows ... | C1 | [48](48-command-tree.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md), [44](44-config-commands.md), [45](45-cache-commands.md), [46](46-doctor.md) |
| 326 | 1b | Typing versions (note 45): accept a version without the ... | C2, X3 | [29](29-tool-commands.md) | [22](22-version-spec-and-jarinfo.md), [23](23-tool-store.md) |
| 329 | 1b | Shell completion, with completers for installed versions and module ... | C3 | [47](47-completion.md) | [52](52-integration-tests.md) |
| 332 | 1b | Move the version flag to `-V` so `-v` can ... | C4 | [48](48-command-tree.md) |  |
| 351 | 2 | Design the testing approach from scratch before any other ... | T1, T12 | [03](03-test-foundation.md) | every package (T12) |
| 359 | 2 | Isolation is automatic and total: every test runs with ... | T2 | [03](03-test-foundation.md) | [53](53-ci-workflows.md) |
| 360 | 2 | Unit tests cannot reach the network or start an ... | T4 | [03](03-test-foundation.md) | [05](05-github-recordings.md) |
| 364 | 2 | The `tlaup tlc` command path is tested end to ... | T5 | [39](39-tlc-command.md) | [18](18-feature-harness.md) |
| 367 | 2 | Download and GitHub failure modes are tested: failure mid-stream, ... | T6 | [26](26-download-and-verify.md) | [24](24-github-client.md), [25](25-remote-listing.md), [27](27-install-steps.md) |
| 374 | 2 | Integration tests: registered markers with strict checking; working skip ... | T9 | [52](52-integration-tests.md) |  |
| 375 | 2 | Coverage policy: branch coverage on; a `fail_under` near the ... | T10 | [03](03-test-foundation.md) | [59](59-closing.md) |
| 382 | 2 | Integration job on every push, with a matrix over ... | I1 | [54](54-integration-job.md) |  |
| 386 | 2 | Unit job on Python 3.11 and the newest release, ... | I2 | [53](53-ci-workflows.md) | [03](03-test-foundation.md), [56](56-build-and-metadata.md) |
| 389 | 2 | One job that installs the newest dependency versions the ... | I3 | [53](53-ci-workflows.md) |  |
| 390 | 2 | Build check on every push: build, `twine check`, install ... | I4 | [53](53-ci-workflows.md) |  |
| 391 | 2 | Enforce `ruff format --check`; `uv sync --locked`; an explicit ... | I5 | [53](53-ci-workflows.md) | [01](01-ruff-format.md) |
| 392 | 2 | Run the pre-commit hooks in CI, without the test ... | I6 | [53](53-ci-workflows.md) | [57](57-repo-hygiene.md) |
| 393 | 2 | Ruleset on `main`: changes arrive by pull request with ... | I7 | not cut | maintainer action: the ruleset is a repository setting; it waits on the check name `Test` that [53](53-ci-workflows.md) introduces ([53](53-ci-workflows.md)'s pull request carries the command) |
| 394 | 2 | Lint rules: enable ruff's blind-except, naive-datetime and print rule ... | I8 | [58](58-lint-rules.md) | [03](03-test-foundation.md) (TID251) |
| 398 | 2 | Harden `scripts/release.sh`: on `main`, clean tree, `HEAD` equal to ... | L1 | [55](55-release-tooling.md) |  |
| 399 | 2 | Restructure `release.yml` into three jobs: a read-only build (lint, ... | L2 | [55](55-release-tooling.md) |  |
| 400 | 2 | Release pages: each page gets that version's changelog section ... | L3 | [55](55-release-tooling.md) | the backfill of old pages is a maintainer action after 0.9.0 |
| 401 | 2 | A `poe` task around `uv version --bump`, so `pyproject.toml` ... | L4 | [55](55-release-tooling.md) |  |
| 402 | 2 | `pypi` environment: add the maintainer as required reviewer and ... | L5 | not cut | maintainer action: the `pypi` environment's reviewer and bypass are repository settings ([30 L5](../design/30-ci-and-release.md#l5-pypi-environment)) |
| 403 | 2 | Before each release, refresh the lock file and let ... | L6 | [55](55-release-tooling.md) | a step of `releasing.md`; the maintainer follows it |
| 404 | 2 | Follow the version rule of decision D27 from 0.9.0 ... | L7 | [55](55-release-tooling.md) | a step of `releasing.md`; the maintainer follows it |
| 409 | 2 | `.github/dependabot.yml` for the `uv` and `github-actions` ecosystems: one monthly ... | B1 | [56](56-build-and-metadata.md) |  |
| 410 | 2 | Build fixes (note 33): `setuptools>=77.0.3`, which the SPDX licence ... | B2 | [56](56-build-and-metadata.md) | [16](16-ui-messages.md), [17](17-error-handler.md), [23](23-tool-store.md) |
| 414 | 2 | PyPI and GitHub metadata (note 37): keywords; the missing ... | B3 | [56](56-build-and-metadata.md) | GitHub topics are a maintainer action |
| 418 | 2 | Pre-commit: move the test hook to pre-push; add a ... | H1 | [57](57-repo-hygiene.md) | [01](01-ruff-format.md), [03](03-test-foundation.md) |
| 419 | 2 | `poe clean` also removes `build` and the egg-info folder, ... | H2 | [57](57-repo-hygiene.md) |  |
| 420 | 2 | One story for Python versions: `.python-version`, the CI matrix, ... | H3 | [57](57-repo-hygiene.md) | [53](53-ci-workflows.md), [56](56-build-and-metadata.md) |
| 421 | 2 | A two-line `SECURITY.md` pointing at GitHub private vulnerability reporting, ... | H4 | [57](57-repo-hygiene.md) |  |

Items of later milestones that packages close in part, though those milestones are not designed here: "Version identity as a type and one version store" (line 438, D37) and the remote side of "Adopt upstream's `rolling` release" (line 445) in 23 and 25; `tools meta sync` (line 453; the command is removed) in 29, and `tools upgrade` comparing only the first build (line 454) in 27 and 29; "Non-interactive version selection" (line 470, the syntax only) in 22; "Exit codes" (line 471) in 09, 17 and 48; the module build as domain code (line 485) in 30 and 31; the housekeeping item's explicit command registration (line 490) in 48.

### Design sections

Every section identifier of the first wave maps to one owning package; "With" names the packages that build a part of it, or say where its parts went. Each package file's "Covers" says which part of a shared section it has.

| Section | Owner | With |
| --- | --- | --- |
| [T1](../design/01-testing.md#t1-the-approach) | [03](03-test-foundation.md) | every package follows it |
| [T2](../design/01-testing.md#t2-isolation) | [03](03-test-foundation.md) | [52](52-integration-tests.md) (the integration fixture), [53](53-ci-workflows.md) (the CI check) |
| [T3](../design/01-testing.md#t3-golden-files) | [07](07-golden-files.md) | [08](08-golden-facts.md) (facts), [13](13-tlc-parser.md) and [10](10-framing-and-codes.md) (the three properties), [15](15-golden-expected-results.md) (expected results), [05](05-github-recordings.md) (the manifests and research [29](29-tool-commands.md)'s recordings) |
| [T4](../design/01-testing.md#t4-fakes-at-the-edges) | [03](03-test-foundation.md) | [05](05-github-recordings.md) (the network half) |
| [T5](../design/01-testing.md#t5-feature-files-and-steps) | [18](18-feature-harness.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md), [40](40-live-display.md), [45](45-cache-commands.md) add the steps they own; every feature file is its first user's |
| [T6](../design/01-testing.md#t6-download-and-github-failure-tests) | [26](26-download-and-verify.md) | [24](24-github-client.md), [25](25-remote-listing.md), [27](27-install-steps.md) (rows divided in [24](24-github-client.md)'s to [27](27-install-steps.md)'s files) |
| [T7](../design/01-testing.md#t7-property-tests-for-values) | [11](11-values.md) | [10](10-framing-and-codes.md) (the framing property) |
| [T8](../design/01-testing.md#t8-expected-output-files) | [03](03-test-foundation.md) |  |
| [T9](../design/01-testing.md#t9-integration-tests) | [52](52-integration-tests.md) |  |
| [T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings) | [03](03-test-foundation.md) | [59](59-closing.md) (the final `fail_under`, the end of `pending`) |
| [T11](../design/01-testing.md#t11-the-existing-tests) | [03](03-test-foundation.md) | each switch package deletes the old tests its "Until" names |
| [T12](../design/01-testing.md#t12-rules-for-writing-tests) | [03](03-test-foundation.md) | every package follows it; [58](58-lint-rules.md) adds the last checks |
| [X1](../design/02-cross-cutting.md#x1-exit-codes) | [17](17-error-handler.md) | [09](09-parse-package-and-model.md) (`describe_exit_status`), [18](18-feature-harness.md) and the switch packages (scenarios), [48](48-command-tree.md) (rule 1) |
| [X2](../design/02-cross-cutting.md#x2-stdout-and-stderr) | [38](38-terminal-reporter.md) | [39](39-tlc-command.md) (scenarios and entry), [40](40-live-display.md) (where the layout is drawn), [41](41-sany-command.md) |
| [X3](../design/02-cross-cutting.md#x3-version-syntax) | [22](22-version-spec-and-jarinfo.md) | [23](23-tool-store.md) (`format_build`, the round trip), [29](29-tool-commands.md) (scenarios and entries) |
| [X4](../design/02-cross-cutting.md#x4-rolling) | [23](23-tool-store.md) | [25](25-remote-listing.md) (`stable_of`), [29](29-tool-commands.md) (entries) |
| [P1](../design/10-parser.md#p1-golden-files) | [07](07-golden-files.md) | [08](08-golden-facts.md), [15](15-golden-expected-results.md) |
| [P2](../design/10-parser.md#p2-the-tlaup_parse-package) | [09](09-parse-package-and-model.md) | [10](10-framing-and-codes.md) to [14](14-pcal-parser.md) |
| [P3](../design/10-parser.md#p3-result-model) | [09](09-parse-package-and-model.md) | [13](13-tlc-parser.md) (status, verdict), [37](37-run-tlc.md) (fields the runner sets) |
| [P4](../design/10-parser.md#p4-framing-and-never-losing-output) | [10](10-framing-and-codes.md) | [13](13-tlc-parser.md) (interpretation, event count) |
| [P5](../design/10-parser.md#p5-error-traces) | [13](13-tlc-parser.md) | [10](10-framing-and-codes.md) (the kind column) |
| [P6](../design/10-parser.md#p6-json-traces-from-tlc) | [13](13-tlc-parser.md) | nothing is built |
| [P7](../design/10-parser.md#p7-values) | [11](11-values.md) | [09](09-parse-package-and-model.md) (the `Value` type) |
| [P8](../design/10-parser.md#p8-sany-output) | [12](12-sany-parser.md) | [13](13-tlc-parser.md) (SANY inside TLC) |
| [P9](../design/10-parser.md#p9-tlc-version) | [13](13-tlc-parser.md) |  |
| [P10](../design/10-parser.md#p10-error-text-with-the-trace) | [38](38-terminal-reporter.md) |  |
| [P11](../design/10-parser.md#p11-tlc-text-and-rich-markup) | [38](38-terminal-reporter.md) |  |
| [R1](../design/11-runner.md#r1-run-errors-reported-as-what-they-are) | [37](37-run-tlc.md) | [21](21-java-launcher.md), [17](17-error-handler.md), [39](39-tlc-command.md) |
| [R2](../design/11-runner.md#r2-signals) | [37](37-run-tlc.md) | [21](21-java-launcher.md), [39](39-tlc-command.md) |
| [R3](../design/11-runner.md#r3-non-utf-8-output) | [37](37-run-tlc.md) | [16](16-ui-messages.md), [21](21-java-launcher.md), [33](33-tlc-invocation.md) (the path warning), [39](39-tlc-command.md) |
| [R4](../design/11-runner.md#r4-spec-cfg-and-working-folder) | [32](32-spec-resolution.md) | [33](33-tlc-invocation.md) (steps 1, 2, 6), [39](39-tlc-command.md), [52](52-integration-tests.md) |
| [R5](../design/11-runner.md#r5-spec-names) | [32](32-spec-resolution.md) | [39](39-tlc-command.md) |
| [R6](../design/11-runner.md#r6-run-folders) | [35](35-run-folders.md) | [33](33-tlc-invocation.md) (per-run values), [37](37-run-tlc.md) (the frame), [39](39-tlc-command.md), [45](45-cache-commands.md), [52](52-integration-tests.md) |
| [R7](../design/11-runner.md#r7-override-modules-that-do-not-load) | [34](34-override-check.md) | [30](30-module-build.md), [38](38-terminal-reporter.md), [39](39-tlc-command.md) |
| [R8](../design/11-runner.md#r8-passthrough-and-workers) | [33](33-tlc-invocation.md) | [39](39-tlc-command.md) |
| [R9](../design/11-runner.md#r9-show-command) | [39](39-tlc-command.md) | [35](35-run-folders.md) (its unit test) |
| [R10](../design/11-runner.md#r10-project-root) | [32](32-spec-resolution.md) |  |
| [R11](../design/11-runner.md#r11-preflight) | [33](33-tlc-invocation.md) | [28](28-first-run.md) (step 3), [39](39-tlc-command.md) |
| [R12](../design/11-runner.md#r12-run-cache-fingerprint) | [35](35-run-folders.md) | [39](39-tlc-command.md) deletes the old code |
| [V1](../design/12-tools-and-downloads.md#v1-version-store) | [23](23-tool-store.md) | [27](27-install-steps.md) (step classes), [29](29-tool-commands.md), [46](46-doctor.md) (leftovers) |
| [V2](../design/12-tools-and-downloads.md#v2-version-order-and-lookup) | [23](23-tool-store.md) | [25](25-remote-listing.md) |
| [V3](../design/12-tools-and-downloads.md#v3-uninstall) | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| [V4](../design/12-tools-and-downloads.md#v4-upgrade-and-pin) | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| [V5](../design/12-tools-and-downloads.md#v5-download-and-verify) | [26](26-download-and-verify.md) | [22](22-version-spec-and-jarinfo.md) (`jarinfo`), [27](27-install-steps.md) |
| [V6](../design/12-tools-and-downloads.md#v6-remove-installs-from-a-url) | [04](04-delete-dead-code.md) |  |
| [V7](../design/12-tools-and-downloads.md#v7-github-client) | [24](24-github-client.md) | [29](29-tool-commands.md) |
| [V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache) | [25](25-remote-listing.md) | [29](29-tool-commands.md), [45](45-cache-commands.md), [47](47-completion.md) |
| [V9](../design/12-tools-and-downloads.md#v9-first-run-prompt) | [28](28-first-run.md) | [29](29-tool-commands.md), [39](39-tlc-command.md) |
| [V10](../design/12-tools-and-downloads.md#v10-remove-old-layouts) | [04](04-delete-dead-code.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md) (the jar lookup's last callers) |
| [V11](../design/12-tools-and-downloads.md#v11-concurrent-installs) | [27](27-install-steps.md) | [23](23-tool-store.md) |
| [V12](../design/12-tools-and-downloads.md#v12-install) | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| [M1](../design/13-modules-and-java.md#m1-module-names) | [30](30-module-build.md) | [31](31-module-commands.md) |
| [M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder) | [30](30-module-build.md) | [31](31-module-commands.md), [34](34-override-check.md) |
| [M3](../design/13-modules-and-java.md#m3-module-build-details) | [30](30-module-build.md) | [20](20-java-location.md) (the `javac` version check), [31](31-module-commands.md) |
| [J1](../design/13-modules-and-java.md#j1-java-options) | [33](33-tlc-invocation.md) |  |
| [J2](../design/13-modules-and-java.md#j2-finding-java) | [20](20-java-location.md) | [39](39-tlc-command.md), [46](46-doctor.md) |
| [J3](../design/13-modules-and-java.md#j3-one-java-start) | [20](20-java-location.md) | [13](13-tlc-parser.md), [23](23-tool-store.md), [29](29-tool-commands.md), [39](39-tlc-command.md), [46](46-doctor.md) |
| [F1](../design/14-config-and-cli.md#f1-layered-configuration) | [19](19-layered-config.md) | [44](44-config-commands.md) (`config set`) |
| [F2](../design/14-config-and-cli.md#f2-folder-overrides) | [02](02-errors-and-paths.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [44](44-config-commands.md), [45](45-cache-commands.md), [46](46-doctor.md) (the commands that print folders) |
| [F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay) | [19](19-layered-config.md) | [29](29-tool-commands.md) (`tool.token_hosts`) |
| [F4](../design/14-config-and-cli.md#f4-config-commands-with-a-broken-file) | [44](44-config-commands.md) |  |
| [F5](../design/14-config-and-cli.md#f5-config-edit) | [44](44-config-commands.md) |  |
| [F6](../design/14-config-and-cli.md#f6-messages) | [16](16-ui-messages.md) | the switch packages convert the call sites; [29](29-tool-commands.md) and [50](50-help-and-messages.md) write the entries; [58](58-lint-rules.md) the checks |
| [F7](../design/14-config-and-cli.md#f7-help-text) | [50](50-help-and-messages.md) | [51](51-cli-reference.md) |
| [F8](../design/14-config-and-cli.md#f8-wording) | [50](50-help-and-messages.md) | [31](31-module-commands.md), [38](38-terminal-reporter.md), [40](40-live-display.md) |
| [F9](../design/14-config-and-cli.md#f9-startup-cost) | [49](49-startup-cost.md) | [47](47-completion.md) |
| [F10](../design/14-config-and-cli.md#f10-no-tracebacks) | [17](17-error-handler.md) | [18](18-feature-harness.md), [47](47-completion.md) (completion in `main()`) |
| [F11](../design/14-config-and-cli.md#f11-error-messages) | [50](50-help-and-messages.md) | the packages that raise the errors |
| [G1](../design/20-groundwork.md#g1-tlc-invocation) | [33](33-tlc-invocation.md) | [37](37-run-tlc.md), [39](39-tlc-command.md) |
| [G2](../design/20-groundwork.md#g2-domain-errors) | [02](02-errors-and-paths.md) | [17](17-error-handler.md) (the one handler) |
| [G3](../design/20-groundwork.md#g3-java-launcher) | [21](21-java-launcher.md) | [06](06-lifeline-agent.md) (the lifeline jar), [37](37-run-tlc.md), [39](39-tlc-command.md), [52](52-integration-tests.md), [53](53-ci-workflows.md) |
| [S1](../design/21-other-tools.md#s1-sany) | [41](41-sany-command.md) | [38](38-terminal-reporter.md) (`format_diagnostic`), [52](52-integration-tests.md) |
| [S2](../design/21-other-tools.md#s2-pcal) | [42](42-pcal-command.md) | [14](14-pcal-parser.md) (the parser) |
| [S3](../design/21-other-tools.md#s3-repl) | [43](43-repl-command.md) | [52](52-integration-tests.md) |
| [S4](../design/21-other-tools.md#s4-keeping-them-thin) | [41](41-sany-command.md) | [42](42-pcal-command.md), [43](43-repl-command.md) |
| [S5](../design/21-other-tools.md#s5-golden-files-for-sany-and-pluscal) | [12](12-sany-parser.md) | [07](07-golden-files.md) (the move), [14](14-pcal-parser.md), [15](15-golden-expected-results.md) |
| [O1](../design/22-reporters.md#o1-reporter-interface) | [36](36-reporter-interface.md) | [37](37-run-tlc.md) (its tests), [39](39-tlc-command.md) (`make_reporter`) |
| [O2](../design/22-reporters.md#o2-delete-dead-display-code) | [04](04-delete-dead-code.md) | [38](38-terminal-reporter.md), [39](39-tlc-command.md), [40](40-live-display.md) (the rows O3 and O4 replace) |
| [O3](../design/22-reporters.md#o3-terminal-reporter) | [38](38-terminal-reporter.md) | [39](39-tlc-command.md) |
| [O4](../design/22-reporters.md#o4-live-display) | [40](40-live-display.md) |  |
| [O5](../design/22-reporters.md#o5-refresh-interval) | [40](40-live-display.md) |  |
| [O6](../design/22-reporters.md#o6-snapshot-tests) | [40](40-live-display.md) | [38](38-terminal-reporter.md) (the plain half) |
| [O7](../design/22-reporters.md#o7-rendering-cost-and-memory) | [40](40-live-display.md) | [38](38-terminal-reporter.md) |
| [C1](../design/23-command-layout.md#c1-command-tree) | [48](48-command-tree.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md), [41](41-sany-command.md) to [47](47-completion.md) (one group each) |
| [C2](../design/23-command-layout.md#c2-typing-versions) | [29](29-tool-commands.md) |  |
| [C3](../design/23-command-layout.md#c3-completion) | [47](47-completion.md) | [52](52-integration-tests.md) (the shell checks) |
| [C4](../design/23-command-layout.md#c4-version-flag) | [48](48-command-tree.md) | [50](50-help-and-messages.md) (the summary text) |
| [C5](../design/23-command-layout.md#c5-help-and-the-cli-reference) | [51](51-cli-reference.md) |  |
| [I1](../design/30-ci-and-release.md#i1-integration-job) | [54](54-integration-job.md) |  |
| [I2](../design/30-ci-and-release.md#i2-unit-job) | [53](53-ci-workflows.md) | [03](03-test-foundation.md), [06](06-lifeline-agent.md) |
| [I3](../design/30-ci-and-release.md#i3-newest-dependencies-job) | [53](53-ci-workflows.md) |  |
| [I4](../design/30-ci-and-release.md#i4-build-check) | [53](53-ci-workflows.md) |  |
| [I5](../design/30-ci-and-release.md#i5-workflow-hygiene) | [53](53-ci-workflows.md) | [01](01-ruff-format.md) (the format commit) |
| [I6](../design/30-ci-and-release.md#i6-pre-commit-in-ci) | [53](53-ci-workflows.md) |  |
| [I7](../design/30-ci-and-release.md#i7-ruleset-on-main) | not cut | maintainer action: a repository ruleset; it waits on [53](53-ci-workflows.md)'s check name `Test` |
| [I8](../design/30-ci-and-release.md#i8-lint-rules) | [58](58-lint-rules.md) | [03](03-test-foundation.md) (TID251) |
| [L1](../design/30-ci-and-release.md#l1-release-script) | [55](55-release-tooling.md) |  |
| [L2](../design/30-ci-and-release.md#l2-release-workflow) | [55](55-release-tooling.md) | [53](53-ci-workflows.md) (the action pins of `test.yml`) |
| [L3](../design/30-ci-and-release.md#l3-release-pages) | [55](55-release-tooling.md) | the backfill is a maintainer action |
| [L4](../design/30-ci-and-release.md#l4-version-bump-task) | [55](55-release-tooling.md) |  |
| [L5](../design/30-ci-and-release.md#l5-pypi-environment) | not cut | maintainer action: repository settings of the `pypi` environment |
| [L6](../design/30-ci-and-release.md#l6-lock-refresh-before-a-release) | [55](55-release-tooling.md) | a release step; the maintainer follows it |
| [L7](../design/30-ci-and-release.md#l7-version-rule) | [55](55-release-tooling.md) | a release step; the maintainer follows it |
| [B1](../design/30-ci-and-release.md#b1-dependabot) | [56](56-build-and-metadata.md) |  |
| [B2](../design/30-ci-and-release.md#b2-build-fixes) | [56](56-build-and-metadata.md) | [03](03-test-foundation.md) (development bounds), [16](16-ui-messages.md), [17](17-error-handler.md), [23](23-tool-store.md) (one runtime bound each) |
| [B3](../design/30-ci-and-release.md#b3-package-metadata) | [56](56-build-and-metadata.md) | GitHub topics are a maintainer action |
| [H1](../design/30-ci-and-release.md#h1-pre-commit-hooks) | [57](57-repo-hygiene.md) | [01](01-ruff-format.md) (the format hook), [03](03-test-foundation.md) (the two checks) |
| [H2](../design/30-ci-and-release.md#h2-clean-task-and-gitignore) | [57](57-repo-hygiene.md) |  |
| [H3](../design/30-ci-and-release.md#h3-python-versions) | [57](57-repo-hygiene.md) | [53](53-ci-workflows.md) (the matrix), [56](56-build-and-metadata.md) (the classifiers) |
| [H4](../design/30-ci-and-release.md#h4-security-policy) | [57](57-repo-hygiene.md) |  |
