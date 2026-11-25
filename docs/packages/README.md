# Work packages (pipeline stage 4, first design wave)

Written 2026-11-21 by the stage 4 agent, from the signed-off first design wave ([design](../design/README.md)), the formal check ([specs](../../specs/README.md)) and the [roadmap](../roadmap.md). Status: **reviewed 2026-11-21 by four fresh agents** ([review](review-2026-11-21.md)). The review's findings and the maintainer's decisions on them (D61 to D67) were worked into the design and into these packages on 2026-11-24 ([summary](../design/stage-4-review-incorporation-2026-11-24.md)); four more fresh agents reviewed that working-in on 2026-11-24 ([review](review-2026-11-24.md)): ready after small fixes, with one blocker. Its findings were fixed on 2026-11-24, as each finding recommends unless a file says why not ([review](review-2026-11-24.md)); the fixes have not been reviewed again. The maintainer signs off before stage 5 starts ([roadmap, "How the work is done"](../roadmap.md#how-the-work-is-done)).

The packages cover milestones 1, 1b and 2. Milestones 3 to 5 are sketched only and get a second design wave after this one is built ([40](../design/40-later-milestones.md)); nothing here builds them, though a few packages close parts of their items, which the traceability table names. No package has been built. Stage 4 changed no product code, test or spec; the working-in of the review changed the design documents, each change marked there.

There are 59 packages. Thirteen of them are delivered as two to six pull requests each, so stage 5 has 79 pull requests in all. Each pull request is listed below under its own number (for example 13a and 13b), with its own size and dependencies, and is reviewed on its own.

## How to read a package

Each file `NN-short-name.md` has the same headings: Goal, Covers, Depends on, Files, Interfaces, Tests that must pass, Changelog, Context for the worker, Done when, Out of scope, Risks, and, where it applies, "Pull requests". The line under the title gives the size (S is hours, M one to three days, L a week or more), the suggested model and the status. No package waits on a question; where one builds on a reading nobody has confirmed, it is listed under "Readings the packages build on" below.

A worker reads its package file, the design sections it links, `AGENTS.md` and the conventions, and nothing else. It never needs `docs/analysis/` or `docs/research/`: what the design took from them is restated in the design or in the package.

## Packages

"Waits for" lists the packages whose merged work this one uses, as each file's "Depends on" names them. A package named there is waited for whole: when it has several pull requests, all of them (a dependency on 35 means 35b; on 15, all five parts). Each file's "Depends on" says what exactly it uses from each.

| # | Package | Size | Model | Waits for |
| --- | --- | --- | --- | --- |
| 01 | [Format the tree and enforce it](01-ruff-format.md) | S | mid-tier | none |
| 02 | [Errors, paths and the context skeleton](02-errors-and-paths.md) | S | mid-tier | 01 |
| 03a | [Test foundation](03-test-foundation.md): the fakes and helpers | M | most capable | 01, 02 |
| 03b | [Test foundation](03-test-foundation.md): settings, isolation, checks, the old suite deleted | M | most capable | 03a |
| 04 | [Delete dead code](04-delete-dead-code.md) | S | mid-tier | 03 |
| 05 | [GitHub recordings and the `github` fixture](05-github-recordings.md) | M | mid-tier | 03 |
| 06 | [The lifeline agent](06-lifeline-agent.md) | M | mid-tier | 01 |
| 07 | [Golden files](07-golden-files.md) | M | most capable | 03 |
| 08a | [Golden facts](08-golden-facts.md): the driver, the self-checks, research 1, 2, 13 and 28 | M | most capable | 03, 07 |
| 08b | [Golden facts](08-golden-facts.md): research 22's cases | M | most capable | 08a |
| 09 | [The `tlaup_parse` package and its result model](09-parse-package-and-model.md) | M | most capable | 03 |
| 10 | [Framing and the code table](10-framing-and-codes.md) | M | most capable | 03, 07, 09 |
| 11 | [TLA+ values](11-values.md) | M | most capable | 03, 07, 09 |
| 12 | [The SANY parser](12-sany-parser.md) | M | mid-tier | 07, 09 |
| 13a | [The TLC parser](13-tlc-parser.md): messages, status, verdict, version | L | most capable | 07 to 10, 12 |
| 13b | [The TLC parser](13-tlc-parser.md): traces | M | most capable | 11, 13a |
| 14 | [The PlusCal parser](14-pcal-parser.md) | S | mid-tier | 07, 09 |
| 15a | [Golden expected results](15-golden-expected-results.md): synthetic, and TLC v1.7.4 for research 1, 2, 13 and 28 | M | most capable | 03, 07, 08, 13 |
| 15b | [Golden expected results](15-golden-expected-results.md): TLC v1.7.4 for research 22 | M | most capable | 15a |
| 15c | [Golden expected results](15-golden-expected-results.md): TLC rolling for research 1, 2, 13 and 28 | M | most capable | 15a |
| 15d | [Golden expected results](15-golden-expected-results.md): TLC rolling for research 22 | M | most capable | 15b, 15c |
| 15e | [Golden expected results](15-golden-expected-results.md): SANY and PlusCal | M | most capable | 12, 14, 15a |
| 16 | [The messages helper (`Ui`)](16-ui-messages.md) | S | mid-tier | 02, 03 |
| 17 | [The error handler, `main()` and `--debug`](17-error-handler.md) | M | most capable | 02, 03, 16 |
| 18a | [The feature harness](18-feature-harness.md): in-process runner and steps | M | most capable | 02, 03, 07, 16, 17 |
| 18b | [The feature harness](18-feature-harness.md): real processes and terminals | M | most capable | 18a |
| 19 | [Layered settings](19-layered-config.md) | M | mid-tier | 02, 03, 16 |
| 20 | [Java location and the remembered version check](20-java-location.md) | M | mid-tier | 02, 03 |
| 21 | [The Java launcher](21-java-launcher.md) | L | most capable | 02, 03, 06, 17 |
| 22 | [Version spec and jar information](22-version-spec-and-jarinfo.md) | M | mid-tier | 02, 03, 05 |
| 23 | [Tool store](23-tool-store.md) | M | most capable | 02, 03, 22 |
| 24 | [GitHub client](24-github-client.md) | M | most capable | 02, 03, 05, 17 |
| 25 | [Remote listing](25-remote-listing.md) | M | mid-tier | 02, 03, 05, 22 to 24 |
| 26 | [Download and verify](26-download-and-verify.md) | M | most capable | 02, 03, 05, 22 to 25 |
| 27a | [Install, upgrade, uninstall and pin as steps](27-install-steps.md): the step classes, `install()` and the stateful test | M | most capable | 02, 03, 05, 16, 22 to 26 |
| 27b | [Install, upgrade, uninstall and pin as steps](27-install-steps.md): `upgrade()`, `uninstall()`, `pin()` | M | most capable | 27a |
| 28 | [First run: `ensure_tools` and the choice of build](28-first-run.md) | S | mid-tier | 02, 03, 05, 16, 22 to 25, 27 |
| 29a | [The `tool` commands](29-tool-commands.md): install, upgrade, uninstall, pin, current, dir | L | most capable | 02 to 05, 16 to 19, 22 to 28 |
| 29b | [The `tool` commands](29-tool-commands.md): list, path, the last deletions | M | most capable | 29a |
| 30 | [The module build](30-module-build.md) | M | most capable | 02, 03, 20, 23 |
| 31 | [The `module` commands](31-module-commands.md) | M | mid-tier | 02, 03, 16 to 20, 28 to 30 |
| 32 | [Spec, cfg and project root resolution](32-spec-resolution.md) | M | mid-tier | 02, 03 |
| 33 | [The TLC invocation: preflight and command builder](33-tlc-invocation.md) | M | most capable | 02, 03, 19 to 21, 23, 30, 32 |
| 34 | [Override classes and the check before a run](34-override-check.md) | M | mid-tier | 02, 03, 07, 23, 30, 33 |
| 35a | [Run folders and their locks](35-run-folders.md): the steps and the stateful test | L | most capable | 02, 03, 21, 23 |
| 35b | [Run folders and their locks](35-run-folders.md): `run_folder`, notes, listing, cleaning | M | most capable | 33, 35a |
| 36 | [The reporter interface](36-reporter-interface.md) | S | mid-tier | 03, 09, 20, 23 |
| 37 | [The run functions `run_tlc` and `run_tlc_raw`](37-run-tlc.md) | M | most capable | 02, 03, 07, 09, 13, 21, 33, 35, 36 |
| 38a | [The terminal reporter, plain output](38-terminal-reporter.md): code and v1.7.4 | L | most capable | 03, 07, 09, 11, 13, 15, 16, 20, 23, 34, 36, 37 |
| 38b | [The terminal reporter, plain output](38-terminal-reporter.md): rolling expected files | M | most capable | 38a |
| 39a | [The `tlc` command](39-tlc-command.md): the switch and the in-process tests | L | most capable | 02, 05, 07, 16 to 19, 28, 29, 31, 33 to 35, 37, 38 |
| 39b | [The `tlc` command](39-tlc-command.md): real processes, pipes, terminals | M | most capable | 39a |
| 40a | [The live display](40-live-display.md): layout mode | L | most capable | 07, 16, 18, 19, 36 to 39 |
| 40b | [The live display](40-live-display.md): refresh interval and the terminal scenarios | M | most capable | 40a |
| 41 | [The `sany` command and the shared shape of the other tools](41-sany-command.md) | M | mid-tier | 07, 12, 18, 20 to 23, 28, 32, 33, 38, 39 |
| 42 | [The `pcal` command](42-pcal-command.md) | S | mid-tier | 07, 14, 18, 21, 38, 41 |
| 43 | [The `repl` command](43-repl-command.md) | S | mid-tier | 18, 21 to 23, 41 |
| 44 | [The `config` commands](44-config-commands.md) | M | mid-tier | 03, 16 to 19 |
| 45 | [The `cache` commands](45-cache-commands.md) | M | mid-tier | 02, 16 to 18, 20, 25, 35, 39 |
| 46 | [`tlaup doctor`, replacing `check-java`](46-doctor.md) | M | mid-tier | 16 to 20, 22 to 24, 29, 30, 39 |
| 47 | [Shell completion](47-completion.md) | M | mid-tier | 03, 05, 17 to 19, 22, 23, 25, 29 to 31, 39, 41, 42, 44 |
| 48 | [The command tree, `-V`, and the end of tlaup's own exit 1](48-command-tree.md) | M | mid-tier | 16 to 18, 29, 31, 39 to 47 |
| 49 | [Startup cost](49-startup-cost.md) | S | mid-tier | 48 |
| 50 | [Help text, wording and error messages](50-help-and-messages.md) | M | mid-tier | 48 |
| 51 | [The generated CLI reference and its drift test](51-cli-reference.md) | S | mid-tier | 03, 17, 50 |
| 52a | [Integration tests](52-integration-tests.md): the harness, live golden runs, tools, modules, the REPL lifeline test | M | most capable | 03, 06, 08, 18, 23, 31, 39, 41 to 43 |
| 52b | [Integration tests](52-integration-tests.md): runner, signals, completion | M | most capable | 45, 47, 52a |
| 53 | [The test workflow](53-ci-workflows.md) | M | mid-tier | 01, 03, 06, 09 |
| 54 | [The integration job](54-integration-job.md) | M | mid-tier | 46, 52, 53 |
| 55 | [Release script, release workflow and version bump](55-release-tooling.md) | M | most capable | 53 |
| 56 | [Dependabot, build fixes and package metadata](56-build-and-metadata.md) | S | mid-tier | 03, 09, 53 |
| 57 | [Repository hygiene](57-repo-hygiene.md) | S | mid-tier | 03, 53, 56 |
| 58a | [Lint rules](58-lint-rules.md): `BLE` | S | mid-tier | 40, 48 to 50 |
| 58b | [Lint rules](58-lint-rules.md): `DTZ` | S | mid-tier | 40, 48 to 50 |
| 58c | [Lint rules](58-lint-rules.md): `T20` and F6's output check | S | mid-tier | 40, 48 to 50 |
| 58d | [Lint rules](58-lint-rules.md): `PLW1510` | S | mid-tier | 40, 48 to 50 |
| 58e | [Lint rules](58-lint-rules.md): bandit `B607` | S | mid-tier | 40, 48 to 50 |
| 58f | [Lint rules](58-lint-rules.md): mypy on `tests/fakes/`, the last checks | S | mid-tier | 40, 48 to 50 |
| 59 | [Closing the first wave](59-closing.md) | M | mid-tier | every other package |

The table's sizes and models are each file's own header line; where a file gives one size for a package of several pull requests (35, 38, 39 and 40 say L), the parts' sizes are the ones the stage 4 cut gave them. The rows list every package a file's "Depends on" names, the foundation (02, 03) included, so some rows are longer than in the first version of this index; none of the additions changes the order.

**Hardest packages**, for the most capable model and the most careful review: 21 (the launcher's signals, D51, D52, D60, with the signals machine as its test first), 35 (run folders and their locks, with the run-folder machine), 13 (the TLC parser, where the model, the code table and the facts first meet real output), 03 (the test foundation everything rests on, and the deletion of the old suite), 18 (the step vocabulary and the real-process and terminal runners), 27 and 29 (the store's mutations with the store machine, and the switch of a whole command group), 39 (the switch of `tlaup tlc` with about ninety scenarios), 24 (the token's scope and the address rules, which are security-sensitive) and 15 (the line-by-line review of some three hundred expected files, in five parts).

## Order and parallel work

The order follows [00, "Order of work"](../design/00-overview.md#order-of-work), item by item, with the changes argued under "Why the cut is this way". The graph by periods; within a period every line can run beside the others once its own "Waits for" is merged:

1. **01** alone: the one mechanical `ruff format` commit, before anything branches off (00 item 1).
2. **02** and **06**. 06 touches no existing module.
3. **03a**, then **03b**: the test foundation, and the old suite deleted (00 item 2, D62).
4. From 03 on, these tracks run side by side:
   - Clean-up: **04** (00 item 3).
   - Parser (00 item 4): **07**, **09**; then **08a**, **08b**, **10**, **11**, **12**, **14**; then **13a** (once 08b, 10 and 12 are in) and **13b** (once 11 is in); then **15a**; then **15b**, **15c** and **15e** (15e once 12 and 14 are in); **15d** after 15b and 15c.
   - Groundwork (00 item 5): **16**, then **17** and **19**; **20**; **21** once 06 and 17 are in; **18a**, **18b** once 17 is in.
   - Store (00 item 6): **05**, then **22**, and **24** once 17 is in; **23**, **25**, **26**, **27a**, **27b**, **28**; **29a** and **29b** once 04, 17, 18 and 19 are in.
   - Spec resolution: **32**.
   - Config commands: **44**, once 18 and 19 are in.
   - CI and release, which touch no `src/` (the design's claim, checked package by package in 53 to 57): **53** once 06 and 09 are in (its wheel check names both import packages and the checked-in lifeline jar), then **55** and **56**, then **57**.
5. Modules and runner (00 item 7): **30** once 20 and 23 are in; **31** after 29; **35a** once 21 and 23 are in; **33**, **34**, **35b**, **36**, **37** (once 13 is in), **38a** (once 15 is in), **38b**; then the switch **39a**, **39b**.
6. After 39, side by side (00 items 8 to 10): **40a** then **40b**; **41**, then **42** and **43**; **45**; **46**; **47** once 41, 42 and 44 are in.
7. **48**, the tree as a whole; then **49** and **50** side by side; then **51**, and beside it **58a** to **58f** once 49 and 50 are in. The six lint parts edit the same lines of `pyproject.toml`, so they land one at a time, in any order.
8. Integration (00 item 11): **52a** (it can start as soon as 41 to 43 are in), **52b** once 45 and 47 are in, then **54** once 52b, 53 and 46 are in.
9. **59**, last.

The longest chain runs 01, 02, 03a, 03b, then the store track from 05 through 22, 23, 25, 26, 27a, 27b and 28 to 29a and 29b, then 31, 39a, 39b, 41, 42, 47, 48, 50, 51 and 59: 24 pull requests one after another. The parser track reaches 38b two steps before 39a needs it, and the groundwork well before, so work on all three tracks at once shortens the release most. Checked by script on 2026-11-24 from every file's "Depends on" section (and, for split packages, its "Pull requests" section): no package waits for a later-numbered one. Several sections mention a later package without waiting for it ("not a dependency", "runs beside"); only what a package waits for counts.

**Files that packages of one period share.** Each package names them under Files. The ones that recur: `pyproject.toml` and `uv.lock` (one dependency or settings line each; the final text of every bound is fixed by D59, so two packages writing the same bound write the same line); `src/tlaup/cli.py` (one registration line or block per command package, rewritten as one block by 48); `CHANGELOG.md`; `README.md` (29, 31 and 39 rename the commands they switch; 56 makes its links absolute); `tests/steps/*.py` (steps are added, never edited, by the package that owns them; 18 has the ownership table); `tests/features/errors.feature` (one block per package); `src/tlaup_parse/__init__.py` (export lines from 09 to 14); `src/tlaup/context.py` (one field each from 02, 16, 17, 19); `docs/contributing/development.md` (different sections); `tests/lifeline/` (06 writes it, 52a adds the REPL case); `.github/workflows/test.yml` (53 writes it, 54 adds the integration job and the steps that give the lifeline job a rolling jar, 57 removes the lint job's `SKIP`); `.github/workflows/release.yml` (55 alone, including its `tools install` step, which stays broken for tag pushes between 29a and 55; nothing is released in between); `scripts/check_wheel.py` (53 writes it; 29a renames its `tools dir` call if 53 is in first); `tests/stateful/test_signals.py` (03b's resource fixes, 21's SIGQUIT edit); the command modules (49 and 50 edit different lines). Where two packages change the same function or file, the files say so and give the order: `java/classpath.py` (30, 31, 33, 41, 39), `tests/unit/java/test_classpath.py` (30 writes it, 33 extends it), `tlc/invocation.py` (33, 34, 35b, 41), `cmd/tlc.py` (39 writes it, 40 adds two options, 47 the completer; D9), `project/core.py` (19 and 32, which write identical constants), `modules/build.py` (30, 34).

## Rules every package follows

- **The design's rules.** [00, "What every package must respect"](../design/00-overview.md#what-every-package-must-respect): the conventions, the exit codes of [02 X1](../design/02-cross-cutting.md#x1-exit-codes) and the stream rule of [02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr), the test rules of [01 T12](../design/01-testing.md#t12-rules-for-writing-tests), and D15's platform rules. The package rules of [00's tree](../design/00-overview.md#packages-after-the-first-wave): `tlaup_parse` imports nothing from `tlaup` and does no I/O; nothing imports `tlaup.cmd`; only `ui`, the reporters and the commands print; subprocesses from argument lists, HTTP with timeouts; domain functions get paths and settings as arguments.
- **The conventions.** [`docs/contributing/conventions.md`](../contributing/conventions.md): Conventional Commits, no AI attribution, a changelog entry in the same commit as each user-visible change, no aliases, shims or migrations (D14), no personal or machine data in anything committed.
- **One pull request each.** A package, or each listed part of one, is one pull request from its own worktree. It is done when its stated tests pass, `uv run poe lint` and `uv run poe test` pass, CI is green, its changelog entry and docs are written, and a separate review agent has reviewed it ([roadmap, review gates](../roadmap.md#how-the-work-is-done)).
- **Build beside, then switch (D62).** The code in `src/` is release 0.8.x, and nearly all of it is replaced. The old tests go first: 03b deletes `tests/unit/` and `tests/integration/` (apart from the tests 03a added), their fixtures and conftests and `pytest-mock`, in one commit ([01 T11](../design/01-testing.md#t11-the-existing-tests)). What protects the behaviour of 0.8.x from then on is the [inventory](../design/preserved-behaviour-2026-11-22.md): each kept row has an owner package, which writes the row's test in 01's forms, lists it under "Tests that must pass" and names the row in its pull request; 59 checks that every kept row has a test that passes. A domain package adds new modules beside the old ones, with their own tests, and no command reaches them yet. A switch package (29, 31, 39, 44, and 41 to 46 for their new commands) moves one command group onto the new code, deletes the old modules it replaces (no old test is left to delete), adds the feature files, and writes the changelog entries for what the user now sees. Between packages `main` need only be green: it builds, and lint, type checks and the remaining tests pass. An old command may stop working before its switch; no package keeps one working, and no scenario tests an old command's behaviour. Two packages use old names only as a way in: 17's handler test and 18's `errors.feature` call `tools dir` and `tools pin` only to reach the root group (a relative `TLAUP_HOME`, a missing argument), and 29a renames those calls when it deletes the group (findings F6, G10). D62's exception, a CI job that runs real TLC through an old command, arises once: today's `tools install` step, which goes in 03b ([30 I2](../design/30-ci-and-release.md#i2-unit-job)). After it, 53's wheel check may run `tlaup tools dir` until 29a renames it, which starts no Java, and the integration job (54) runs only new commands. Where old code must still type-check until its switch deletes it, an earlier package makes the edit that keeps it compiling and says so (for example 29b's new body of `get_tlc_jar_path`, 32's in-place `find_project_root`). That is not a shim in D14's sense: no old name, folder or layout stays readable for users. Nothing is released between packages (D6).
- **Test first.** Where a stateful test of the formal check applies (21, 27a, 35a), the package's first commit removes its `pending` markers, and the package deletes the matching `reference_*.py` model and its `*_reference_model` tests (D46, [03](../design/03-run-stages-and-specs.md#specs-and-their-tests)). The golden facts are written before the parser and marked pending by pattern ([08](08-golden-facts.md)); 13a and 13b remove the patterns. A pull request that fixes a defect shows the new test failing first (T12 rule 6).
- **Changelog where the user first sees it.** Domain packages mostly write no entry; the switch package that makes the change visible writes the design's entries word for word, and each file says which entries are its own. No entry is written twice.
- **Signatures are the intended shape.** A worker may adjust a name or a parameter if the behaviour and the tests stay, and says so in the pull request (design README). A shape marked "written by stage 4" is one the design leaves unwritten (for example the joints [03](../design/03-run-stages-and-specs.md#part-1-the-components-and-one-tlc-run) lists, `resolve_spec` or `make_reporter`).
- **Code that already passes the last lint rules.** [58](58-lint-rules.md) turns on what [30 I8](../design/30-ci-and-release.md#i8-lint-rules) and [14 F6](../design/14-config-and-cli.md#f6-messages) ask for, one rule group per pull request, after the last command package. New code is written to pass them from the start: no blind `except` (two allowed, each with `noqa: BLE001` and a comment: the last branch of the root group's handler, F10, and the completers' guard, C3); only aware UTC datetimes or the injected `now` (DTZ); no `print` in `src/` (T20); no `typer.echo` and no `Console(` outside `tlaup/ui.py` and `tlaup/reporters/`; every `subprocess.run` states `check=`; every executable as an absolute path, from `locate` or `shutil.which` (`git` in 49, the editor in 44); heavy imports inside the command functions, with the `PLC0415` per-file ignores for `src/tlaup/cmd/**` and `cli.py` that 17 adds ([14 F9](../design/14-config-and-cli.md#f9-startup-cost); `tlaup.cmd.completion` at the top is F9's one exception, 47); no `unittest.mock.patch` in tests (TID251, from 03); mypy strict on `src/`, and on `scripts/` and `tests/fakes/` once 58f is in.
- **Never against the real folders.** A worker who runs `tlaup` by hand points it at temporary folders ([development guide](../contributing/development.md#running-tlaup-without-touching-your-own-folders); from 02 on, `TLAUP_HOME` does it in one variable).
- **Known gaps stay open.** Gaps the design postpones are named in the package they touch and are not closed there: the per-run `java.io.tmpdir` for v1.7.4's shared temporary module copies (question 27, after the first implementation; 33, 41), SIGTSTP forwarding (21), finding K1-8 on Windows (35), a pager that does not read (21, 37), `--verbose`, `--quiet`, `--color` and the JSON reporter (milestone 4; 38, 40).

## Why the cut is this way

The maintainer left the cut to stage 4. These are the choices a reader could ask about.

- **Build beside, then switch** (above), rather than rewriting each module in place. The new code is tested as it is written, the old code keeps building until its switch deletes it, and since the old tests are gone from 03b on (D62), no test of old names holds a rewrite back. One departure: [32](32-spec-resolution.md) changes `find_project_root` in place, because R10 changes the rule of a function that exists and a second function of that name would have to move again at the switch; the old command then shows the new rule at once, so 32 writes R10's Breaking entry itself.
- **Errors and paths first** (02, before the test foundation). Every later package raises `TlaupError`, and the isolation fixture needs `TLAUP_HOME` ([01 T2](../design/01-testing.md#t2-isolation) depends on F2). 00 item 2 puts F2 in the test foundation; it is one small package before it instead, so 03 is not larger still.
- **The lifeline jar on its own, early** (06). It touches no existing module, and the launcher (21) and CI (53) need it. The jar is checked in, with the lifeline job's test that compiles the source and compares the class files.
- **Settings before the store and the runner** (19, in the groundwork). 00 item 10 puts F1 and F3 with the commands, but the run folders (`tlc.keep`), the Java options, the reporter (`tlc.plain`) and the commands that pass the repository address all read settings. 19 gives the old readers of removed keys the one-line edits that keep them type-checking (its file lists them); the `config` commands (44) are separate and can land early.
- **The module build before the runner** (30). 00 item 10 puts M1 to M3 with the commands, but the preflight's classpath (33) and the override check (34) need the registry and the class-file reader.
- **The reporter interface and the plain reporter before the switch of `tlaup tlc`** (36, 38). 00 item 8 puts the reporters after the runner. `run_tlc` (37) takes a reporter, and the switch (39) needs something that prints; only the live display (40) waits until after the switch. 38 waits for the golden expected results (15), which keeps the roadmap's rule that the reporter work starts after the golden tests pass.
- **Facts before the parser, as pending patterns** (08). The design asks for the facts first and failing; `main` stays green because the facts carry the existing `pending` marker by pattern (`case:topic:name`), and 13a and 13b remove the patterns as their first commits. The patterns allow 13 to land in two parts. `facts.py` holds TLC facts only; SANY and PlusCal assertions are 12's and 14's ([01 T3](../design/01-testing.md#t3-golden-files)).
- **The manifests with the recordings** (05). Three tracks need `tests/unit/data/manifests/`; 05 is the first of them and builds a small jar from a recorded manifest, so it moves them.
- **`tlaup/stdio.py` in the error handler** (17). The launcher (21) needs `reader_gone`, which F10 defines beside `main()`, and must not import `tlaup.cli`; 17 puts it in a module that imports neither Typer nor Rich (00's tree now lists it).
- **The debug filter in the GitHub client** (24, after 17). `redact` is a stand-alone function in its own module, and 24 points 17's one debug-printing function at it, so 17 does not wait for 24 and the filter is in before 29, the first command that reads the token.
- **`doctor` after the `tlc` switch** (46). The old runner is the other caller of `java/inspector.py`, which `doctor` deletes with `check-java`.
- **The test workflow before the integration job** (53, 54). The integration job joins the `Test` job and the schedule that the test workflow writes, and gives the lifeline job its rolling jar.
- **Help text before the reference** (50, 51), not after. 50's pull request carries a full help dump at 100 columns, which its review reads; 51's first checked-in reference is then the reviewed text. The reverse order would review the text twice.
- **Splits.** Thirteen packages are delivered as several pull requests, each split at a seam its file states, so that each review fits one sitting: 03 (helpers, then switching them on and deleting the old suite), 08 (by origin: the cases of research 1, 2, 13 and 28, then research 22's; review finding A1), 13 (messages, then traces), 15 (five parts by build and origin, for some three hundred expected files; finding A2), 18 (in-process, then real processes and terminals), 27 (the four step classes with the stateful test, which needs them together, then the other three functions; finding B18), 29 (by command; reading commands first would leave two stores live or nothing to install with), 35 (the step functions with the stateful test, which needs every step at once, then the rest), 38 (by build, for its expected files), 39 and 40 (along their files' parts A and B), 52 (the harness with the live golden runs, tools and modules, then the runner, signals and completion; finding D17), and 58 (one pull request per rule group, as I8 asks; finding D15).

## Settled questions

The first version of this index asked the maintainer eighteen questions. All are settled (walk-through of 2026-11-22 to 2026-11-24); each answer is now in the design, and the packages are written to it.

| # | Question | Answer | Where it lives |
| --- | --- | --- | --- |
| Q1 | Does the format commit touch Markdown? | Yes: ruff may reformat the Python code blocks in Markdown, and the pre-commit hook covers Markdown too. | [30 I5](../design/30-ci-and-release.md#i5-workflow-hygiene), [H1](../design/30-ci-and-release.md#h1-pre-commit-hooks); 01 |
| Q2 | When does `pytest-mock` go? | With the old suite, in 03b; no legacy list and no `no-new-mocker` hook. | D62, [01 T11](../design/01-testing.md#t11-the-existing-tests) |
| Q3 | How are research 22's captures adopted? | The older captures stay golden; a non-empty `.err` beside its `.out`; `tool-live` not adopted; per-build inputs under `golden/specs/<build>/`; research 28's two `override-class-too-new-*` captures added. | [01 T3](../design/01-testing.md#t3-golden-files) |
| Q4 | Which word and meaning for each TLC exit code? | The table of D63; a code TLC does not document is `error`. | D63, [02 X1](../design/02-cross-cutting.md#x1-exit-codes), [10 P2](../design/10-parser.md#p2-the-tlaup_parse-package) |
| Q5 | SIGQUIT in the signals machine | The fake child notes SIGQUIT and carries on; 21 makes the edit. | [03, "Specs and their tests"](../design/03-run-stages-and-specs.md#specs-and-their-tests), [20 G3](../design/20-groundwork.md#g3-java-launcher) |
| Q6 | Where is the debug filter? | A stand-alone `redact(text, env)` in its own module, owned by 24, called by 17's handler, in before 29. | [12 V7](../design/12-tools-and-downloads.md#v7-github-client), [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks) |
| Q7 | What is cached of the release list? | The list as it came back; an error answer never. | [12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache) |
| Q8 | The uninstall race | As the design says: re-checked under the lock; a named build gone meanwhile removes nothing and exits 4. | [12 V3](../design/12-tools-and-downloads.md#v3-uninstall) |
| Q9 | A `-recover` path that does not exist | The folder's lock is taken whenever the path lies under an existing `runs/<id>/`. | [11 R6](../design/11-runner.md#r6-run-folders) |
| Q10 | Steps for a signal during a checkpoint | A checkpoint marker the fake `java` logs and the step `once java has begun its checkpoint`; the fake commits before line m. | [01 T4](../design/01-testing.md#t4-fakes-at-the-edges), [T5](../design/01-testing.md#t5-feature-files-and-steps), [11 R6](../design/11-runner.md#r6-run-folders) |
| Q11 | Gaps in the terminal reporter | The four checkpoint, recovery and finish events print nothing; the header leaves out what is not known; "not checked: TLC failed before computing the initial states (TLC exit code N: ...)"; the hint on a `hint:` line. | [22 O3](../design/22-reporters.md#o3-terminal-reporter) |
| Q12 | The waiting line while a reporter is up | Through `Reporter.notice`: plain output prints it on stderr at once, the live display in its Status panel, copied to stderr on close. | [11 R2](../design/11-runner.md#r2-signals), [22 O1](../design/22-reporters.md#o1-reporter-interface), [O4](../design/22-reporters.md#o4-live-display) |
| Q13 | Where `pcal`'s added labels go | On stdout, `<spec>:<line>:<col>: label <name> added`. | D67, [21 S2](../design/21-other-tools.md#s2-pcal) |
| Q14 | `cache clean --all` with a kind | `--all` widens the kind named; the Java check's file goes only when no kind is named. | [23 C1](../design/23-command-layout.md#c1-command-tree) |
| Q15 | `doctor`'s levels | As 46 builds them: an error is what makes a run stop with 3 (nothing pinned); a missing `javac` is a warning. | [23 C1](../design/23-command-layout.md#c1-command-tree) |
| Q16 | The range of `tlc.refresh_interval` | Kept as built: the schema checks the type, the command the range, which gives 2 wherever the value came from. | [14 F1](../design/14-config-and-cli.md#f1-layered-configuration), [22 O5](../design/22-reporters.md#o5-refresh-interval) |
| Q17 | Stateful tests under warnings as errors | 03b fixes the resource handling in those tests; no rule changes. | [03, "Specs and their tests"](../design/03-run-stages-and-specs.md#specs-and-their-tests), [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings) |
| Q18 | Facts for SANY and PlusCal | `facts.py` holds TLC facts only; the SANY and PlusCal parsers' own tests check their cases first, and both results get a dictionary form. | [01 T3](../design/01-testing.md#t3-golden-files), [T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings), [21 S5](../design/21-other-tools.md#s5-golden-files-for-sany-and-pluscal), [10 P1](../design/10-parser.md#p1-golden-files) |

## Readings the packages build on

Each is a reading of the design that the maintainer has not confirmed. The package named writes it as its plan, so nothing waits on it; **the next review is to confirm each**, or say what the package should do instead. They are in the order of the roadmap's ["How a decision is weighed"](../roadmap.md#how-the-work-is-done): what a user or a script could come to rely on first, internal choices last. Readings that were settled are listed after them, each with who settled it and where it is written (findings E4 and H8 of the [second review](review-2026-11-24.md)).

- [09](09-parse-package-and-model.md), [13](13-tlc-parser.md), [14](14-pcal-parser.md) ([10 P3](../design/10-parser.md#p3-result-model)): the names of the parser's events and results, which milestone 4's JSON exposes (the `Event` members and their fields, the `Phase` values, `RunResult` and the keys of its `to_dict()` and `from_dict()`, the fields of `FinalStats`), and what the first wave puts in them (a fresh `RunResult` has the verdict `incomplete`; `OverrideLoaded.java_class` as TLC printed it; `collision_probability` the optimistic of 2193's two estimates; the messages that set `workers`; a PlusCal diagnostic's `Location.module` is `""`). Internal until milestone 4 publishes its schema, and reviewed then (settled with the maintainer on 2026-11-24; [40, milestone 4](../design/40-later-milestones.md#milestone-4-automation-surface)).
- [27](27-install-steps.md), [28](28-first-run.md) ([12 V4](../design/12-tools-and-downloads.md#v4-upgrade-and-pin), [V9](../design/12-tools-and-downloads.md#v9-first-run-prompt)): the which-build question has no default.
- [35](35-run-folders.md), [45](45-cache-commands.md) ([11 R6](../design/11-runner.md#r6-run-folders)): `run.json` gains a `"reason"` key, which `settle` writes when it keeps a folder and `cache list` reads to show why it was kept; R6's `run.json` has no field for it.
- [29](29-tool-commands.md) ([12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache)): the Status column of `tool list` (`available`, `installed`, `installed, update available`, `installed, not upstream`, by the rule 29 writes); and what a release row shows under Build, and how a cached or stale list is marked, which the expected files decide, the pull request saying what it chose.
- [28](28-first-run.md) ([12 V9](../design/12-tools-and-downloads.md#v9-first-run-prompt)): after an install the pin wins, so when another tlaup pinned a build first, that build is what runs; when no stable release exists, the lookup's own error (`VersionNotFound`, "no stable release is available") comes out before the question is asked.
- [27](27-install-steps.md) ([12 V12](../design/12-tools-and-downloads.md#v12-install)): which errors mean "GitHub cannot be asked" (`NetworkError`, `RateLimited`, `RemoteDataError`; not a tag's 404), on which a build of that name already installed is returned with a warning; and nothing is pinned when a build spec matched several builds.
- [22](22-version-spec-and-jarinfo.md), [29](29-tool-commands.md) ([02 X3](../design/02-cross-cutting.md#x3-version-syntax)): the `latest` refusal's tag from the cached release list needs the repository address from the settings, even on commands that read no other setting; a broken config file falls back to the installed builds.
- [38](38-terminal-reporter.md), [35](35-run-folders.md) ([22 O3](../design/22-reporters.md#o3-terminal-reporter), [11 R6](../design/11-runner.md#r6-run-folders)): two duration forms stay two, O3's result line (`2 min 13 s`, `1 h 02 min`) and R6's "Checkpoint kept" note (`2 h 13 min`), each from its section's example.
- [19](19-layered-config.md) ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration)): `CONFIG_HEADER`, the header line of a written config file, names a reference page that does not exist yet (one constant, naming the planned page). Reviewer F confirmed 19's line (finding F4); the line is text in the user's file, so it stays here for the maintainer.
- [30](30-module-build.md) ([13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder)): `module.json`'s `built_against` is `<name>@<commit>`, or the bare name when the build has no commit.
- [33](33-tlc-invocation.md), [39](39-tlc-command.md), [40](40-live-display.md) (finding C8, a low-impact choice): `--workers`, `--keep`, `--plain` and `--refresh-interval` travel in the request or in `ReporterOptions`, not in the settings' flags layer that [14 F1](../design/14-config-and-cli.md#f1-layered-configuration) lists; `make_reporter` checks `options.plain or settings.tlc.plain`.
- [24](24-github-client.md), [25](25-remote-listing.md), [26](26-download-and-verify.md) ([12 V7](../design/12-tools-and-downloads.md#v7-github-client)): the shapes V7 names without giving them: `progress`, `DownloadInfo`, the status code on the error.
- [26](26-download-and-verify.md) ([12 V5](../design/12-tools-and-downloads.md#v5-download-and-verify)): `fetch_build` hands back the jar and its info, not the release, so after its one retry the caller holds the release it looked up first; the cost, one extra download at the next install of a release without a digest, is accepted.
- [21](21-java-launcher.md) ([20 G3](../design/20-groundwork.md#g3-java-launcher)): the three joints stage 4 wrote (`ProcessOutcome.stopped_for_closed_pipe`, the arguments of `ChildRun`, `reader_gone` as a parameter); 35 and 37 are cut against them.
- [23](23-tool-store.md), [30](30-module-build.md) ([12 V1](../design/12-tools-and-downloads.md#v1-version-store), [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder)): the age of a `.tmp/` entry is read from its name against the injected `now`, since T12 rule 5 forbids modification times.

**Settled since, and where.** Readings of the first version of this index, or of the list above, that are no longer open:

- By the maintainer on 2026-11-24: what `config show` and `config get KEY` print, a section name for `config get` being `ConfigKeyNotFound`, and the environment variables `TLAUP_MODULE_PATH` and `TLAUP_MODULE_LIB_PATH` ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration)); `tool uninstall --all` asking with `y` and `n`, `n` the default ([12 V3](../design/12-tools-and-downloads.md#v3-uninstall)); the phase word `Starting` ([22 O4](../design/22-reporters.md#o4-live-display)); the compile classpath of `module add` (D61, [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder)).
- Confirmed by the second review as low impact ([review](review-2026-11-24.md)): by reviewer F (finding F4), 13's verdict phase as the phase when the error opened, and 13a's state messages kept out of `unknown_messages` (findings A6, A7); 14's continuation lines of a ` -- ` message printed as written (A3; the empty `Location.module` is in the first line above); 04, 29 and 39 dividing [12 V10](../design/12-tools-and-downloads.md#v10-remove-old-layouts)'s deletions by the order of work (A8: 04 removes the legacy fallback of `get_tlc_jar_path`, 29 points it at the new store, 39 deletes it and `tlc/compiler.py`). By reviewer H, 42's banner, `Parsing completed.` and `Translation completed.` printing nothing (C16), and `ToolStore.leftovers()`, added for `doctor` (23, 46).
- Written into the design: the fake `java`'s declared runs each answer one start ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)); the steps' answers typed at once, the replacements of `the java command matches the expected file`, `{kept-id}` and `javac is version` ([01 T5](../design/01-testing.md#t5-feature-files-and-steps)); the three synthetic cases ([01 T3](../design/01-testing.md#t3-golden-files)); the rule for lock files whose folder is gone, which 45's `rundirs.clean_lock_files` builds ([11 R6](../design/11-runner.md#r6-run-folders)); `tlaup/stdio.py` ([00's tree](../design/00-overview.md#packages-after-the-first-wave)); R7's changelog entry on listing loaded overrides, gone from [11 R7](../design/11-runner.md#r7-override-modules-that-do-not-load); and the five readings of 52 to 58 (T9's store folder and build name, T2's `JAVA_HOME`, I5's required lifeline job, I3's `uv sync --upgrade`, I8's `shutil.which` and T20), as reviewer H found.
- Stage 4's low-impact choices, each written with its reason in the package under the roadmap's rule: 33's range of `-seed` (0 to 2^63 - 1, which 52 proves on both builds) and the locale test of R3's path warning; 37's `RunOutcome.kept` carrying the whole `Kept`, and 35's `kept_note`; 40's layout frames drawn from the v1.7.4 captures (O6 names no build); 17's old commands keeping `typer.Exit(1)` until their switch and an uncaught exception from one giving 5 (nothing is released in between, D6); 44's Added entry for `config path` and `config get` (finding H5); 03's bounds for `hypothesis` and `pytest-randomly`; and 06's answers to the lifeline agent's silences (a malformed argument, whether the source ships, the JDK that builds the checked-in jar), which its pull request names.

## Clerical

The clerical list of the first version (plural names left from before D47, counts and codes in 10, the sketches of V4 and G1, the duplicate changelog entries, the synthetic cases, the lifeline marker and job, the tree of 00, `.gitattributes` and the rest) is done in the design; each fix is marked there "(Stage 4 review, 2026-11-24: ...)". Nothing is left on it.

## Not cut

- **Roadmap items that are repository settings or the maintainer's to do**, named in the package they touch: the ruleset on `main` (I7; it waits on 53's check name `Test`), the `pypi` environment's reviewer and bypass (L5), the backfill of old release pages (L3), GitHub topics (B3), the hand check of completion in an interactive zsh and fish before the release (47), and the roadmap's [maintainer actions](../roadmap.md#maintainer-actions-and-sessions), of which two-factor confirmation and capturing CI logs touch 55 and 53.
- **The documentation track** ([roadmap](../roadmap.md#documentation-track-parallel-start-with-milestone-1)) is not designed, except the CLI reference generator and its drift test ([23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference), package 51) and the development guide changes [01 T11](../design/01-testing.md#t11-the-existing-tests) names (03, and each package that changes the code map). Not cut, for want of a design: the README rewrite, the concepts page (which D65 now gives a paragraph), the examples and their manifest (so T9's examples row is not built in 52), running the README quick start in CI, the reference pages, the guides, troubleshooting, the welcome page of the contributing guide, the changelog checks in CI and the changelog history.
- **Postponed by the design**, named in the package they touch and not closed: see "Known gaps stay open" above, and running the `specs/` models in the integration job ([03](../design/03-run-stages-and-specs.md#specs-and-their-tests): "a later step and not part of this plan").

## Traceability

### Roadmap items of milestones 1, 1b and 2

Every open item (`- [ ]`) of the three milestones, by its line in the [roadmap](../roadmap.md) as of 2026-11-24, maps to one owning package: the one that builds the item, or, for a removal or a switch, that does it. "With" names the packages that hold a part. Ticked items (the new name, trunk plus tags, Dependabot alerts, the Nix flake) need no package. Where a design departs from an item's wording, the [design index's list of departures](../design/README.md#where-the-design-departs-from-the-roadmap) wins.

| Line | Milestone | Item | Design | Owner | With |
| --- | --- | --- | --- | --- | --- |
| 156 | 1 | Capture real `-tool` output from TLC 1.7.4 and the ... | P1, T3 | [07](07-golden-files.md) | [08](08-golden-facts.md), [13](13-tlc-parser.md), [15](15-golden-expected-results.md) |
| 158 | 1 | Move the parser stack (message framing, codes, values, models, ... | P2, P3 | [09](09-parse-package-and-model.md) | [10](10-framing-and-codes.md) to [14](14-pcal-parser.md); [39](39-tlc-command.md) deletes the old stack |
| 161 | 1 | Never lose output (decision D9): anything the parser does ... | P4 | [10](10-framing-and-codes.md) | [13](13-tlc-parser.md), [39](39-tlc-command.md) |
| 162 | 1 | Read the TLC version from the startup message so ... | P9 | [13](13-tlc-parser.md) |  |
| 163 | 1 | Fix error-trace parsing so real counterexamples yield states: location ... | P5 | [13](13-tlc-parser.md) |  |
| 166 | 1 | If TLC can write traces as JSON itself (investigation ... | P6 | [13](13-tlc-parser.md) | nothing is built (P6) |
| 169 | 1 | Fix function-valued variables (`(a :> 1 @@ b :> ... | P7 | [11](11-values.md) |  |
| 170 | 1 | Fix SANY error grouping: errors are flushed after every ... | P8 | [12](12-sany-parser.md) | [13](13-tlc-parser.md) |
| 173 | 1 | Show the violated-invariant text together with the trace. Today ... | P10 | [38](38-terminal-reporter.md) |  |
| 174 | 1 | Print TLC text without Rich markup interpretation; today, on ... | P11 | [38](38-terminal-reporter.md) |  |
| 178 | 1 | Report run errors as what they are. Today every ... | R1 | [37](37-run-tlc.md) | [17](17-error-handler.md), [21](21-java-launcher.md), [39](39-tlc-command.md) |
| 182 | 1 | Forward SIGTERM to the JVM so a CI timeout ... | R2, G3 | [37](37-run-tlc.md) | [21](21-java-launcher.md), [36](36-reporter-interface.md) and [40](40-live-display.md) (the waiting line), [39](39-tlc-command.md) |
| 184 | 1 | Do not crash on non-UTF-8 bytes in TLC output. ... | R3 | [37](37-run-tlc.md) | [16](16-ui-messages.md), [21](21-java-launcher.md), [39](39-tlc-command.md) |
| 185 | 1 | Pass a `--cfg` file outside the project root to ... | R4 | [32](32-spec-resolution.md) | [33](33-tlc-invocation.md), [39](39-tlc-command.md) |
| 189 | 1 | Spec names: a dot in the name is mangled ... | R5 | [32](32-spec-resolution.md) | [39](39-tlc-command.md) |
| 190 | 1 | Stop run-cache cleanup from deleting other specs' directories: it ... | R6 | [35](35-run-folders.md) | [39](39-tlc-command.md), [45](45-cache-commands.md) |
| 199 | 1 | Report clearly when an override module fails to load ... | R7 | [34](34-override-check.md) | [38](38-terminal-reporter.md), [39](39-tlc-command.md) |
| 204 | 1 | The project-root rule counts a parent folder that has ... | R10 | [32](32-spec-resolution.md) |  |
| 205 | 1 | The run-cache fingerprint covers the default `.cfg` only, not ... | R12, R6 | [35](35-run-folders.md) | [39](39-tlc-command.md) deletes the old code |
| 206 | 1 | The module build strips `//` comments with a regex ... | M3 | [30](30-module-build.md) | [31](31-module-commands.md) |
| 207 | 1 | Unknown config keys are silently ignored, so a typo ... | F1 | [19](19-layered-config.md) |  |
| 211 | 1 | Pass everything after `--` to TLC. Add `--workers`, defaulting ... | R8 | [33](33-tlc-invocation.md) | [39](39-tlc-command.md) |
| 214 | 1 | Make `--show-command` print the exact command that would run, ... | R9 | [39](39-tlc-command.md) | [35](35-run-folders.md) |
| 220 | 1 | Reject module names containing path separators or `..`, absolute ... | M1 | [30](30-module-build.md) | [31](31-module-commands.md) |
| 221 | 1 | `modules add` builds in a temporary folder and swaps ... | M2 | [30](30-module-build.md) | [31](31-module-commands.md) |
| 222 | 1 | Fix `tools uninstall --all`, which stops after removing the ... | V3 | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| 223 | 1 | A failed uninstall exits non-zero and does not move ... | V3 | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| 224 | 1 | Concurrent installs: write the pin and metadata atomically and ... | V11, V1 | [27](27-install-steps.md) | [23](23-tool-store.md), [29](29-tool-commands.md) |
| 228 | 1 | Remove installs from a URL (decision D13). Do this ... | V6 | [04](04-delete-dead-code.md) |  |
| 229 | 1 | Download to a temporary file, check it is a ... | V5 | [26](26-download-and-verify.md) | [22](22-version-spec-and-jarinfo.md), [23](23-tool-store.md), [27](27-install-steps.md), [29](29-tool-commands.md) |
| 230 | 1 | Refuse unencrypted addresses and any redirect to one. (S) ... | V7 | [24](24-github-client.md) |  |
| 231 | 1 | After download, compare the commit the jar reports about ... | V5 | [26](26-download-and-verify.md) | [22](22-version-spec-and-jarinfo.md), [27](27-install-steps.md) |
| 235 | 1 | Read all pages of tags and releases; choose "latest ... | V8 | [25](25-remote-listing.md) | [24](24-github-client.md) |
| 239 | 1 | GitHub token support (`GITHUB_TOKEN`, `GH_TOKEN`), `Accept` and `User-Agent` headers, ... | V7 | [24](24-github-client.md) | [17](17-error-handler.md) (the debug-printing function that 24 points at `redact`), [29](29-tool-commands.md) |
| 242 | 1 | Do not crash on a non-JSON or non-list API ... | V7, V8, V4 | [24](24-github-client.md) | [25](25-remote-listing.md), [27](27-install-steps.md) |
| 246 | 1 | One preflight used by every `tlaup tlc` path, checking ... | R11 | [33](33-tlc-invocation.md) | [39](39-tlc-command.md) |
| 247 | 1 | No tracebacks for users: missing Java, missing jar with ... | F10 | [17](17-error-handler.md) | [39](39-tlc-command.md) and the other switch packages |
| 252 | 1 | First-run prompt (decision D4): when nothing is pinned, ask ... | V9, X4 | [28](28-first-run.md) | [29](29-tool-commands.md), [39](39-tlc-command.md) |
| 254 | 1 | Remove the legacy fallback jar path, so it is ... | V10 | [04](04-delete-dead-code.md) | [23](23-tool-store.md), [29](29-tool-commands.md), [33](33-tlc-invocation.md), [39](39-tlc-command.md) (V10's deletions divided by the order of work; see the readings) |
| 258 | 1 | Java options: a `TLAUP_`-prefixed variable and a repeatable flag, ... | J1 | [33](33-tlc-invocation.md) | [39](39-tlc-command.md) |
| 259 | 1 | Use `JAVA_HOME` when set, falling back to `PATH`, for ... | J2 | [20](20-java-location.md) | [31](31-module-commands.md), [39](39-tlc-command.md), [46](46-doctor.md) |
| 260 | 1 | One Java start per run: read the TLC version ... | J3 | [20](20-java-location.md) | [13](13-tlc-parser.md), [23](23-tool-store.md), [29](29-tool-commands.md), [39](39-tlc-command.md) |
| 267 | 1 | Layered configuration (decision D10): packaged defaults, user file, environment, ... | F1 | [19](19-layered-config.md) | [44](44-config-commands.md), [29](29-tool-commands.md) (the `tool path` scenario with no config file) |
| 268 | 1 | `config` commands work when the file is broken, and ... | F4 | [44](44-config-commands.md) | [19](19-layered-config.md), [39](39-tlc-command.md) (the scenario with `tlaup tlc Spec`) |
| 269 | 1 | Remove settings nothing reads (`workspace.root`, `workspace.spec_dir`, the unread `tla.community_modules` ... | F3 | [19](19-layered-config.md) |  |
| 270 | 1 | Environment overrides for the tool's folders (decision D25). Lands ... | F2 | [02](02-errors-and-paths.md) |  |
| 271 | 1 | `config edit`: accept `$VISUAL` and `$EDITOR` values with arguments ... | F5 | [44](44-config-commands.md) |  |
| 275 | 1 | Error messages (raised list): list the locations searched when ... | F11 | [50](50-help-and-messages.md) | [24](24-github-client.md), [25](25-remote-listing.md), [27](27-install-steps.md), [28](28-first-run.md), [30](30-module-build.md), [32](32-spec-resolution.md), [33](33-tlc-invocation.md) |
| 276 | 1 | Route every message through the one UI helper; there ... | F6 | [16](16-ui-messages.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md), [44](44-config-commands.md), [50](50-help-and-messages.md), [58](58-lint-rules.md) |
| 277 | 1 | Help text (raised list): what `upgrade` means (newest build ... | F7, C5 | [50](50-help-and-messages.md) | [51](51-cli-reference.md) |
| 278 | 1 | Wording: one word for a stopped run ("canceled" and ... | F8 | [50](50-help-and-messages.md) | [31](31-module-commands.md), [38](38-terminal-reporter.md), [40](40-live-display.md) |
| 282 | 1 | Skip the `git rev-parse` call on normal installs; load ... | F9 | [49](49-startup-cost.md) | [17](17-error-handler.md) (the `PLC0415` ignores), [47](47-completion.md) (the one exception) |
| 292 | 1b | A single TLC invocation value (spec, cfg, project root, ... | G1 | [33](33-tlc-invocation.md) | [37](37-run-tlc.md), [39](39-tlc-command.md) |
| 293 | 1b | A small family of domain errors (spec not found, ... | G2, X1 | [02](02-errors-and-paths.md) | [17](17-error-handler.md) |
| 295 | 1b | A generic Java tool invocation (jar, classpath, JVM options, ... | G3 | [21](21-java-launcher.md) |  |
| 301 | 1b | The lifeline agent (decision D51): a small Java agent ... | G3, I2 | [06](06-lifeline-agent.md) | [21](21-java-launcher.md), [52](52-integration-tests.md) (the REPL case in `tests/lifeline/`), [53](53-ci-workflows.md) (the lifeline job), [54](54-integration-job.md) (its rolling jar) |
| 302 | 1b | `sany` command: parse a spec and report diagnostics with ... | S1 | [41](41-sany-command.md) |  |
| 308 | 1b | `pcal` command: run the PlusCal translator; passthrough for its ... | S2 | [42](42-pcal-command.md) | [14](14-pcal-parser.md), [52](52-integration-tests.md) (the integration tests) |
| 311 | 1b | `repl` command: interactive, so no output parsing; the terminal ... | S3 | [43](43-repl-command.md) |  |
| 313 | 1b | Keep all three thin (note 15): no logic beyond ... | S4 | [41](41-sany-command.md) | [42](42-pcal-command.md), [43](43-repl-command.md) |
| 315 | 1b | Golden-file tests for SANY and PlusCal output per TLC ... | S5, T3 | [12](12-sany-parser.md) | [07](07-golden-files.md), [14](14-pcal-parser.md), [15](15-golden-expected-results.md), [41](41-sany-command.md), [42](42-pcal-command.md), [43](43-repl-command.md) |
| 322 | 1b | A reporter interface fed by the parsed result and ... | O1 | [36](36-reporter-interface.md) | [37](37-run-tlc.md), [39](39-tlc-command.md) |
| 323 | 1b | Delete display code that nothing in `src/` references (`StatusFooterComponent`, ... | O2 | [04](04-delete-dead-code.md) | [40](40-live-display.md) |
| 324 | 1b | Live terminal reporter: render the layout on a terminal; ... | O3, O4 | [40](40-live-display.md) | [38](38-terminal-reporter.md) |
| 328 | 1b | Make `--refresh-interval` and the matching config key take effect. ... | O5 | [40](40-live-display.md) |  |
| 329 | 1b | Fix the per-line re-rendering cost, which grows with the ... | O7 | [40](40-live-display.md) | [38](38-terminal-reporter.md) |
| 330 | 1b | Snapshot tests through a fixed-width, colourless console with an ... | O6, T8 | [40](40-live-display.md) | [03](03-test-foundation.md), [38](38-terminal-reporter.md) |
| 334 | 1b | Review the layout of every command so it follows ... | C1 | [48](48-command-tree.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md), [41](41-sany-command.md) to [47](47-completion.md) (one group or command each) |
| 335 | 1b | Typing versions (note 45): accept a version without the ... | C2, X3 | [29](29-tool-commands.md) | [22](22-version-spec-and-jarinfo.md), [23](23-tool-store.md) |
| 338 | 1b | Shell completion, with completers for installed versions and module ... | C3 | [47](47-completion.md) | [49](49-startup-cost.md) (F9's exception for it), [52](52-integration-tests.md) |
| 341 | 1b | Move the version flag to `-V` so `-v` can ... | C4 | [48](48-command-tree.md) |  |
| 360 | 2 | Design the testing approach from scratch before any other ... | T1, T12 | [03](03-test-foundation.md) | every package (T12) |
| 368 | 2 | Isolation is automatic and total: every test runs with ... | T2 | [03](03-test-foundation.md) | [53](53-ci-workflows.md) |
| 369 | 2 | Unit tests cannot reach the network or start an ... | T4 | [03](03-test-foundation.md) | [05](05-github-recordings.md) |
| 373 | 2 | The `tlaup tlc` command path is tested end to ... | T5 | [39](39-tlc-command.md) | [18](18-feature-harness.md) |
| 376 | 2 | Download and GitHub failure modes are tested: failure mid-stream, ... | T6 | [26](26-download-and-verify.md) | [24](24-github-client.md), [25](25-remote-listing.md), [27](27-install-steps.md) |
| 383 | 2 | Integration tests: registered markers with strict checking; working skip ... | T9 | [52](52-integration-tests.md) |  |
| 384 | 2 | Coverage policy: branch coverage on; a `fail_under` near the ... | T10 | [03](03-test-foundation.md) | [59](59-closing.md) (the `fail_under` from the measured figure) |
| 391 | 2 | Integration job on every push, with a matrix over ... | I1 | [54](54-integration-job.md) |  |
| 395 | 2 | Unit job on Python 3.11 and the newest release, ... | I2 | [53](53-ci-workflows.md) | [03](03-test-foundation.md) (the old `tools install` step goes), [06](06-lifeline-agent.md), [52](52-integration-tests.md), [54](54-integration-job.md), [55](55-release-tooling.md) (`release.yml`'s `tools install` step), [56](56-build-and-metadata.md) |
| 398 | 2 | One job that installs the newest dependency versions the ... | I3 | [53](53-ci-workflows.md) |  |
| 399 | 2 | Build check on every push: build, `twine check`, install ... | I4 | [53](53-ci-workflows.md) |  |
| 400 | 2 | Enforce `ruff format --check`; `uv sync --locked`; an explicit ... | I5 | [53](53-ci-workflows.md) | [01](01-ruff-format.md), [54](54-integration-job.md), [55](55-release-tooling.md) (the same rules for their jobs) |
| 401 | 2 | Run the pre-commit hooks in CI, without the test ... | I6 | [53](53-ci-workflows.md) | [57](57-repo-hygiene.md) |
| 402 | 2 | Ruleset on `main`: changes arrive by pull request with ... | I7 | not cut | maintainer action: the ruleset is a repository setting; it waits on the check name `Test` that [53](53-ci-workflows.md) introduces ([53](53-ci-workflows.md)'s pull request carries the command) |
| 403 | 2 | Lint rules: enable ruff's blind-except, naive-datetime and print rule ... | I8 | [58](58-lint-rules.md) | [03](03-test-foundation.md) (TID251), [17](17-error-handler.md) (`PLC0415`), [49](49-startup-cost.md) and [44](44-config-commands.md) (`shutil.which`) |
| 407 | 2 | Harden `scripts/release.sh`: on `main`, clean tree, `HEAD` equal to ... | L1 | [55](55-release-tooling.md) |  |
| 408 | 2 | Restructure `release.yml` into three jobs: a read-only build (lint, ... | L2 | [55](55-release-tooling.md) |  |
| 409 | 2 | Release pages: each page gets that version's changelog section ... | L3 | [55](55-release-tooling.md) | the backfill of old pages is a maintainer action after 0.9.0 |
| 410 | 2 | A `poe` task around `uv version --bump`, so `pyproject.toml` ... | L4 | [55](55-release-tooling.md) |  |
| 411 | 2 | `pypi` environment: add the maintainer as required reviewer and ... | L5 | not cut | maintainer action: the `pypi` environment's reviewer and bypass are repository settings ([30 L5](../design/30-ci-and-release.md#l5-pypi-environment)) |
| 412 | 2 | Before each release, refresh the lock file and let ... | L6 | [55](55-release-tooling.md) | a step of `releasing.md`; the maintainer follows it |
| 413 | 2 | Follow the version rule of decision D27 from 0.9.0 ... | L7 | [55](55-release-tooling.md) | a step of `releasing.md`; the maintainer follows it |
| 418 | 2 | `.github/dependabot.yml` for the `uv` and `github-actions` ecosystems: one monthly ... | B1 | [56](56-build-and-metadata.md) |  |
| 419 | 2 | Build fixes (note 33): `setuptools>=77.0.3`, which the SPDX licence ... | B2 | [56](56-build-and-metadata.md) | [16](16-ui-messages.md), [17](17-error-handler.md), [23](23-tool-store.md) |
| 423 | 2 | PyPI and GitHub metadata (note 37): keywords; the missing ... | B3 | [56](56-build-and-metadata.md) | GitHub topics are a maintainer action |
| 427 | 2 | Pre-commit: move the test hook to pre-push; add a ... | H1 | [57](57-repo-hygiene.md) | [01](01-ruff-format.md), [03](03-test-foundation.md) |
| 428 | 2 | `poe clean` also removes `build` and the egg-info folder, ... | H2 | [57](57-repo-hygiene.md) |  |
| 429 | 2 | One story for Python versions: `.python-version`, the CI matrix, ... | H3 | [57](57-repo-hygiene.md) | [53](53-ci-workflows.md), [56](56-build-and-metadata.md) |
| 430 | 2 | A two-line `SECURITY.md` pointing at GitHub private vulnerability reporting, ... | H4 | [57](57-repo-hygiene.md) |  |

Items of later milestones that packages close in part, though those milestones are not designed here: "Version identity as a type and one version store" (line 448, D37) and the remote side of "Adopt upstream's `rolling` release" (line 455) in 23 and 25; `tools meta sync` (line 463; the command is removed) in 29, and `tools upgrade` comparing only the first build (line 464) in 27 and 29; "Non-interactive version selection" (line 480, the syntax only) in 22; "Exit codes" (line 481) in 09, 17 and 48; the module build as domain code (line 495) in 30 and 31; the housekeeping item's explicit command registration (line 500) in 48.

### Design sections

Every section identifier of the first wave maps to one owning package; "With" names the packages that build a part of it, or say where its parts went. Each package file's "Covers" says which part of a shared section it has. Checked by script on 2026-11-24: every section heading of `docs/design/*.md` (`## R6 ...`, `### K1 ...`) has its row.

| Section | Owner | With |
| --- | --- | --- |
| [T1](../design/01-testing.md#t1-the-approach) | [03](03-test-foundation.md) | every package follows it |
| [T2](../design/01-testing.md#t2-isolation) | [03](03-test-foundation.md) | [52](52-integration-tests.md) (the integration fixture), [53](53-ci-workflows.md) (the CI check) |
| [T3](../design/01-testing.md#t3-golden-files) | [07](07-golden-files.md) | [08](08-golden-facts.md) (facts), [13](13-tlc-parser.md) and [10](10-framing-and-codes.md) (the three properties), [15](15-golden-expected-results.md) (expected results), [05](05-github-recordings.md) (the manifests and research 29's recordings), [52](52-integration-tests.md) (the facts against live runs) |
| [T4](../design/01-testing.md#t4-fakes-at-the-edges) | [03](03-test-foundation.md) | [05](05-github-recordings.md) (the network half) |
| [T5](../design/01-testing.md#t5-feature-files-and-steps) | [18](18-feature-harness.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md), [40](40-live-display.md), [45](45-cache-commands.md) (`{kept-id}`) add the steps they own; every feature file is its first user's |
| [T6](../design/01-testing.md#t6-download-and-github-failure-tests) | [26](26-download-and-verify.md) | [24](24-github-client.md), [25](25-remote-listing.md), [27](27-install-steps.md) (rows divided in [24](24-github-client.md)'s to [27](27-install-steps.md)'s files) |
| [T7](../design/01-testing.md#t7-property-tests-for-values) | [11](11-values.md) | [10](10-framing-and-codes.md) (the framing property) |
| [T8](../design/01-testing.md#t8-expected-output-files) | [03](03-test-foundation.md) |  |
| [T9](../design/01-testing.md#t9-integration-tests) | [52](52-integration-tests.md) | [06](06-lifeline-agent.md) (the `tests/lifeline/` folder the REPL case joins) |
| [T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings) | [03](03-test-foundation.md) | [59](59-closing.md) (the `fail_under` from the measured figure, at least 80; the end of `pending`) |
| [T11](../design/01-testing.md#t11-the-existing-tests) | [03](03-test-foundation.md) | [59](59-closing.md) (the closing check of the inventory, D62); no switch package deletes an old test |
| [T12](../design/01-testing.md#t12-rules-for-writing-tests) | [03](03-test-foundation.md) | every package follows it; [58](58-lint-rules.md) adds the last checks |
| [X1](../design/02-cross-cutting.md#x1-exit-codes) | [17](17-error-handler.md) | [09](09-parse-package-and-model.md) (`describe_exit_status`, the test over every code), [18](18-feature-harness.md) and the switch packages (scenarios), [48](48-command-tree.md) (rule 1 and the Breaking entry for the exit codes) |
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
| [R2](../design/11-runner.md#r2-signals) | [37](37-run-tlc.md) | [21](21-java-launcher.md) (`on_held`), [36](36-reporter-interface.md) (`Reporter.notice`), [38](38-terminal-reporter.md) and [40](40-live-display.md) (where the waiting line shows), [39](39-tlc-command.md) |
| [R3](../design/11-runner.md#r3-non-utf-8-output) | [37](37-run-tlc.md) | [16](16-ui-messages.md), [21](21-java-launcher.md), [33](33-tlc-invocation.md) (the path warning), [39](39-tlc-command.md) |
| [R4](../design/11-runner.md#r4-spec-cfg-and-working-folder) | [32](32-spec-resolution.md) | [33](33-tlc-invocation.md) (steps 1, 2, 6), [39](39-tlc-command.md), [52](52-integration-tests.md) |
| [R5](../design/11-runner.md#r5-spec-names) | [32](32-spec-resolution.md) | [39](39-tlc-command.md) |
| [R6](../design/11-runner.md#r6-run-folders) | [35](35-run-folders.md) | [33](33-tlc-invocation.md) (per-run values, `find_recovered_run`), [37](37-run-tlc.md) (the frame), [39](39-tlc-command.md), [45](45-cache-commands.md), [52](52-integration-tests.md) |
| [R7](../design/11-runner.md#r7-override-modules-that-do-not-load) | [34](34-override-check.md) | [30](30-module-build.md), [38](38-terminal-reporter.md), [39](39-tlc-command.md) |
| [R8](../design/11-runner.md#r8-passthrough-and-workers) | [33](33-tlc-invocation.md) | [39](39-tlc-command.md) |
| [R9](../design/11-runner.md#r9-show-command) | [39](39-tlc-command.md) | [35](35-run-folders.md) (its unit test) |
| [R10](../design/11-runner.md#r10-project-root) | [32](32-spec-resolution.md) |  |
| [R11](../design/11-runner.md#r11-preflight) | [33](33-tlc-invocation.md) | [20](20-java-location.md) (the timeout's unit test, which stands in for its scenario), [28](28-first-run.md) (step 3), [39](39-tlc-command.md) |
| [R12](../design/11-runner.md#r12-run-cache-fingerprint) | [35](35-run-folders.md) | [39](39-tlc-command.md) deletes the old code |
| [V1](../design/12-tools-and-downloads.md#v1-version-store) | [23](23-tool-store.md) | [27](27-install-steps.md) (step classes), [29](29-tool-commands.md), [46](46-doctor.md) (leftovers) |
| [V2](../design/12-tools-and-downloads.md#v2-version-order-and-lookup) | [23](23-tool-store.md) | [25](25-remote-listing.md) |
| [V3](../design/12-tools-and-downloads.md#v3-uninstall) | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| [V4](../design/12-tools-and-downloads.md#v4-upgrade-and-pin) | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| [V5](../design/12-tools-and-downloads.md#v5-download-and-verify) | [26](26-download-and-verify.md) | [22](22-version-spec-and-jarinfo.md) (`jarinfo`), [27](27-install-steps.md) |
| [V6](../design/12-tools-and-downloads.md#v6-remove-installs-from-a-url) | [04](04-delete-dead-code.md) |  |
| [V7](../design/12-tools-and-downloads.md#v7-github-client) | [24](24-github-client.md) | [17](17-error-handler.md) (the debug-printing function that 24 points at `redact`), [29](29-tool-commands.md) |
| [V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache) | [25](25-remote-listing.md) | [29](29-tool-commands.md) (`tool list`, D64's entries), [45](45-cache-commands.md), [47](47-completion.md) |
| [V9](../design/12-tools-and-downloads.md#v9-first-run-prompt) | [28](28-first-run.md) | [29](29-tool-commands.md), [39](39-tlc-command.md) |
| [V10](../design/12-tools-and-downloads.md#v10-remove-old-layouts) | [04](04-delete-dead-code.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md) (the jar lookup's last callers; see the readings) |
| [V11](../design/12-tools-and-downloads.md#v11-concurrent-installs) | [27](27-install-steps.md) | [23](23-tool-store.md) |
| [V12](../design/12-tools-and-downloads.md#v12-install) | [27](27-install-steps.md) | [29](29-tool-commands.md) |
| [M1](../design/13-modules-and-java.md#m1-module-names) | [30](30-module-build.md) | [31](31-module-commands.md) |
| [M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder) | [30](30-module-build.md) | [31](31-module-commands.md), [34](34-override-check.md) |
| [M2, "The classpath of a run"](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder) | [33](33-tlc-invocation.md) | [30](30-module-build.md) (the whole-list test, written first), [52](52-integration-tests.md) (a project's `classes/` live) |
| [M3](../design/13-modules-and-java.md#m3-module-build-details) | [30](30-module-build.md) | [20](20-java-location.md) (the `javac` version check), [31](31-module-commands.md) |
| [J1](../design/13-modules-and-java.md#j1-java-options) | [33](33-tlc-invocation.md) |  |
| [J2](../design/13-modules-and-java.md#j2-finding-java) | [20](20-java-location.md) | [39](39-tlc-command.md), [46](46-doctor.md) |
| [J3](../design/13-modules-and-java.md#j3-one-java-start) | [20](20-java-location.md) | [13](13-tlc-parser.md), [23](23-tool-store.md), [29](29-tool-commands.md), [39](39-tlc-command.md), [45](45-cache-commands.md) (`cache clean` removes the remembered check), [46](46-doctor.md) |
| [F1](../design/14-config-and-cli.md#f1-layered-configuration) | [19](19-layered-config.md) | [44](44-config-commands.md) (`config set`), [29](29-tool-commands.md) (the `tool path` scenario with no config file) |
| [F2](../design/14-config-and-cli.md#f2-folder-overrides) | [02](02-errors-and-paths.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [45](45-cache-commands.md), [46](46-doctor.md) (the commands that print folders) |
| [F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay) | [19](19-layered-config.md) | [29](29-tool-commands.md) (`tool.token_hosts`) |
| [F4](../design/14-config-and-cli.md#f4-config-commands-with-a-broken-file) | [44](44-config-commands.md) | [39](39-tlc-command.md) (the scenario with `tlaup tlc Spec`) |
| [F5](../design/14-config-and-cli.md#f5-config-edit) | [44](44-config-commands.md) |  |
| [F6](../design/14-config-and-cli.md#f6-messages) | [16](16-ui-messages.md) | the switch packages convert the call sites; [29](29-tool-commands.md) and [50](50-help-and-messages.md) write the entries; [58](58-lint-rules.md) the checks |
| [F7](../design/14-config-and-cli.md#f7-help-text) | [50](50-help-and-messages.md) | [51](51-cli-reference.md) |
| [F8](../design/14-config-and-cli.md#f8-wording) | [50](50-help-and-messages.md) | [31](31-module-commands.md), [38](38-terminal-reporter.md), [40](40-live-display.md) |
| [F9](../design/14-config-and-cli.md#f9-startup-cost) | [49](49-startup-cost.md) | [17](17-error-handler.md) (the `PLC0415` ignores), [47](47-completion.md) (the one exception, `tlaup.cmd.completion`) |
| [F10](../design/14-config-and-cli.md#f10-no-tracebacks) | [17](17-error-handler.md) | [18](18-feature-harness.md), [24](24-github-client.md) (`redact`), [47](47-completion.md) (completion in `main()`) |
| [F11](../design/14-config-and-cli.md#f11-error-messages) | [50](50-help-and-messages.md) | the packages that raise the errors |
| [G1](../design/20-groundwork.md#g1-tlc-invocation) | [33](33-tlc-invocation.md) | [37](37-run-tlc.md), [39](39-tlc-command.md) |
| [G2](../design/20-groundwork.md#g2-domain-errors) | [02](02-errors-and-paths.md) | [17](17-error-handler.md) (the one handler) |
| [G3](../design/20-groundwork.md#g3-java-launcher) | [21](21-java-launcher.md) | [06](06-lifeline-agent.md) (the lifeline jar), [37](37-run-tlc.md), [39](39-tlc-command.md), [52](52-integration-tests.md), [53](53-ci-workflows.md) |
| [K1](../design/03-run-stages-and-specs.md#k1-run-folders) | [35](35-run-folders.md) | the run-folder machine, test first in 35a |
| [K2](../design/03-run-stages-and-specs.md#k2-tools-store) | [27](27-install-steps.md) | [23](23-tool-store.md) (the store's steps); the store machine, test first in 27a |
| [K3](../design/03-run-stages-and-specs.md#k3-signals) | [21](21-java-launcher.md) | the signals machine, test first, with Q5's edit |
| [S1](../design/21-other-tools.md#s1-sany) | [41](41-sany-command.md) | [38](38-terminal-reporter.md) (`format_diagnostic` and `source_excerpt` in `reporters/text.py`, D66), [52](52-integration-tests.md) |
| [S2](../design/21-other-tools.md#s2-pcal) | [42](42-pcal-command.md) | [14](14-pcal-parser.md) (the parser), [52](52-integration-tests.md) (the integration tests on a copy of a PlusCal spec) |
| [S3](../design/21-other-tools.md#s3-repl) | [43](43-repl-command.md) | [52](52-integration-tests.md) |
| [S4](../design/21-other-tools.md#s4-keeping-them-thin) | [41](41-sany-command.md) | [42](42-pcal-command.md), [43](43-repl-command.md) |
| [S5](../design/21-other-tools.md#s5-golden-files-for-sany-and-pluscal) | [12](12-sany-parser.md) | [07](07-golden-files.md) (the move), [14](14-pcal-parser.md), [15](15-golden-expected-results.md) |
| [O1](../design/22-reporters.md#o1-reporter-interface) | [36](36-reporter-interface.md) | [37](37-run-tlc.md) (its tests), [38](38-terminal-reporter.md) and [40](40-live-display.md) (`notice`), [39](39-tlc-command.md) (`make_reporter`) |
| [O2](../design/22-reporters.md#o2-delete-dead-display-code) | [04](04-delete-dead-code.md) | [38](38-terminal-reporter.md), [39](39-tlc-command.md), [40](40-live-display.md) (the rows O3 and O4 replace) |
| [O3](../design/22-reporters.md#o3-terminal-reporter) | [38](38-terminal-reporter.md) | [39](39-tlc-command.md), [41](41-sany-command.md) (the shared excerpt) |
| [O4](../design/22-reporters.md#o4-live-display) | [40](40-live-display.md) | [37](37-run-tlc.md) (the waiting line it shows) |
| [O5](../design/22-reporters.md#o5-refresh-interval) | [40](40-live-display.md) |  |
| [O6](../design/22-reporters.md#o6-snapshot-tests) | [40](40-live-display.md) | [38](38-terminal-reporter.md) (the plain half) |
| [O7](../design/22-reporters.md#o7-rendering-cost-and-memory) | [40](40-live-display.md) | [38](38-terminal-reporter.md) |
| [C1](../design/23-command-layout.md#c1-command-tree) | [48](48-command-tree.md) | [29](29-tool-commands.md), [31](31-module-commands.md), [39](39-tlc-command.md), [41](41-sany-command.md) to [47](47-completion.md) (one group or command each) |
| [C2](../design/23-command-layout.md#c2-typing-versions) | [29](29-tool-commands.md) |  |
| [C3](../design/23-command-layout.md#c3-completion) | [47](47-completion.md) | [49](49-startup-cost.md) (F9's exception), [52](52-integration-tests.md) (the shell checks) |
| [C4](../design/23-command-layout.md#c4-version-flag) | [48](48-command-tree.md) | [50](50-help-and-messages.md) (the summary text) |
| [C5](../design/23-command-layout.md#c5-help-and-the-cli-reference) | [51](51-cli-reference.md) |  |
| [I1](../design/30-ci-and-release.md#i1-integration-job) | [54](54-integration-job.md) |  |
| [I2](../design/30-ci-and-release.md#i2-unit-job) | [53](53-ci-workflows.md) | [03](03-test-foundation.md) (the old `tools install` step goes), [06](06-lifeline-agent.md), [52](52-integration-tests.md) (the REPL case), [54](54-integration-job.md) (the lifeline job's jar), [55](55-release-tooling.md) (`release.yml`'s `tools install` step) |
| [I3](../design/30-ci-and-release.md#i3-newest-dependencies-job) | [53](53-ci-workflows.md) |  |
| [I4](../design/30-ci-and-release.md#i4-build-check) | [53](53-ci-workflows.md) |  |
| [I5](../design/30-ci-and-release.md#i5-workflow-hygiene) | [53](53-ci-workflows.md) | [01](01-ruff-format.md) (the format commit, Markdown included), [54](54-integration-job.md), [55](55-release-tooling.md) |
| [I6](../design/30-ci-and-release.md#i6-pre-commit-in-ci) | [53](53-ci-workflows.md) |  |
| [I7](../design/30-ci-and-release.md#i7-ruleset-on-main) | not cut | maintainer action: a repository ruleset; it waits on [53](53-ci-workflows.md)'s check name `Test` |
| [I8](../design/30-ci-and-release.md#i8-lint-rules) | [58](58-lint-rules.md) | [03](03-test-foundation.md) (TID251), [17](17-error-handler.md) (`PLC0415`), [44](44-config-commands.md) and [49](49-startup-cost.md) (`shutil.which`) |
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
| [H1](../design/30-ci-and-release.md#h1-pre-commit-hooks) | [57](57-repo-hygiene.md) | [01](01-ruff-format.md) (the format hook, Markdown included), [03](03-test-foundation.md) (the two checks) |
| [H2](../design/30-ci-and-release.md#h2-clean-task-and-gitignore) | [57](57-repo-hygiene.md) |  |
| [H3](../design/30-ci-and-release.md#h3-python-versions) | [57](57-repo-hygiene.md) | [53](53-ci-workflows.md) (the matrix), [56](56-build-and-metadata.md) (the classifiers) |
| [H4](../design/30-ci-and-release.md#h4-security-policy) | [57](57-repo-hygiene.md) |  |

### The preserved-behaviour inventory

The [inventory](../design/preserved-behaviour-2026-11-22.md) of what a user can observe in 0.8.x is the list of requirements of D62. Every row marked kept (or decided and kept) has one owner, which writes the row's test in 01's forms, lists it under "Tests that must pass" and names the row in its pull request; "With" names a package that writes a part. Where a row's note names its owner, this table follows the note; for the other kept rows the owner is the package that writes the test the note's design section names. Rows changed on purpose need no test of the old behaviour; their new behaviour is the cited section's. [59](59-closing.md) closes the wave by checking that every row below has a test that exists and passes, and reports each that has none against its owner.

| Owner | Rows | With |
| --- | --- | --- |
| [02](02-errors-and-paths.md) | C1 |  |
| [08](08-golden-facts.md) | R30 | [13](13-tlc-parser.md) |
| [10](10-framing-and-codes.md) | R29 | [13](13-tlc-parser.md) |
| [11](11-values.md) | R28 |  |
| [12](12-sany-parser.md) | R31 |  |
| [17](17-error-handler.md) | P1 |  |
| [19](19-layered-config.md) | C2, C4, J4, R25 | [33](33-tlc-invocation.md) (R25's builder half: the two options in the built command) |
| [20](20-java-location.md) | J1 |  |
| [23](23-tool-store.md) | T4 (the store half), T14, T30 | [27](27-install-steps.md) (T4's `install` half) |
| [24](24-github-client.md) | T12 |  |
| [25](25-remote-listing.md) | T7, T21 (the cache half), T22, T23, T26 | [29](29-tool-commands.md) (T21's `tool list` half, T22's scenarios) |
| [26](26-download-and-verify.md) | T9 | [27](27-install-steps.md) |
| [27](27-install-steps.md) | T2, T3, T40, T41 |  |
| [29](29-tool-commands.md) | T1, T5, T11, T18, T19, T20, T27, T28, T29, T31, T33, T34, T39 | [25](25-remote-listing.md) (T19's status) |
| [30](30-module-build.md) | M17, M18 |  |
| [31](31-module-commands.md) | M1, M2, M4, M6, M9, M10, M13, M14, M16 | [30](30-module-build.md) (the unit tests of `build_module`) |
| [32](32-spec-resolution.md) | S1 to S5, S9, S13 |  |
| [33](33-tlc-invocation.md) | S7, S10, S11, S12, C6 | [30](30-module-build.md) (S11's first form, with M17), [19](19-layered-config.md) (C6's environment variables), [39](39-tlc-command.md) (C6's feature scenario, in its `tlc_run.feature`) |
| [34](34-override-check.md) | M7, R24 |  |
| [35](35-run-folders.md) | R7 | [39](39-tlc-command.md) (the scenario through `tlaup tlc`) |
| [38](38-terminal-reporter.md) | R9, R15, R16, R18, R19, R20, R21 (decided, D66; for `tlc`) | [41](41-sany-command.md) (R20 and R21 for `sany`), [52](52-integration-tests.md) (R20 and R21 against real SANY) |
| [39](39-tlc-command.md) | R1, R2, R10, R11, R12, R14, M20, J2, J3 | [52](52-integration-tests.md) (R14 with a real JVM), [34](34-override-check.md) (M20's property) |
| [40](40-live-display.md) | R13 (its scenario added to 39's `tlc_run.feature`) |  |
| [45](45-cache-commands.md) | O7 |  |
| [48](48-command-tree.md) | P2, P4 |  |
| [49](49-startup-cost.md) | P3 |  |
| [50](50-help-and-messages.md) | T8 | [29](29-tool-commands.md) (its `VersionNotFound` scenarios) |
| [51](51-cli-reference.md) | P5 | [50](50-help-and-messages.md) (every command's one-line help, every `tlc` option's help) |
| [52](52-integration-tests.md) | R32, R33, R34 |  |
| [57](57-repo-hygiene.md) | P8 |  |

Three rows changed on purpose still have packages that build and test the new behaviour the inventory names; 59 does not check them as kept rows: M5 (decided, D61: the narrow compile classpath of `module add`; [30](30-module-build.md)'s unit test that `build_module` is given it, and [31](31-module-commands.md)'s command-level test of the logged `-cp`), M15 (folders in the module folder that are not modules: `doctor` warns, [46](46-doctor.md)) and O10 (an editor not on `PATH` is `NotSetUp`, code 3, [44](44-config-commands.md)).
