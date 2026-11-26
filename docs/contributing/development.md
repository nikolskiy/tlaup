# Development

How to set up, run the checks, and find your way around the code as it is today. The code described here is release 0.8.x; the design documents in [`../design/`](../design/README.md) describe the code as it will be, and their packages, commands and test layout do not exist until the work packages are built.

## Environment and commands

Use `uv` for everything; do not call `pip` or a global Python.

```bash
uv sync --all-extras --dev     # set up the environment
uv run poe test                # the test suite with branch coverage, in random order
uv run poe test-clean          # the suite under an empty temporary home, then fail if tlaup wrote there
uv run poe test-integration    # tests/integration: real Java and real jars (needs TLAUP_TEST_JARS and a JDK)
uv run poe lint                # ruff check, bandit, mypy (strict)
uv run poe format              # ruff format, Python files and Python blocks in Markdown
uv run poe build-lifeline      # rebuild src/tlaup/java/lifeline.jar from its source (needs a JDK)
uv run poe test-lifeline       # tests/lifeline: the agent with a real JVM (needs a JDK; not part of poe test)
uv run poe docs-cli            # rewrite docs/reference/cli.md from the help strings; run it after changing any help string (the drift test fails otherwise)
uv run poe check               # all pre-commit hooks on all files
uv run poe check-release       # clean, build, twine check, then scripts/check_wheel.py (the hooks are `poe check`)
```

A single test runs without coverage: `uv run pytest tests/unit/test_fakes.py::test_java_exit_code`. `pytest-randomly` prints the seed of each run; `--randomly-seed=<n>` repeats an order, and `-p no:randomly` switches it off.

Run `uv run poe lint` and `uv run poe test` before committing.

## The integration tests

`tests/integration/` runs real TLC, SANY, the PlusCal translator and the REPL ([design 01 T9](../design/01-testing.md#t9-integration-tests)). It needs a JDK (`java` and `javac`, found through `JAVA_HOME`, then `PATH`) and the variable `TLAUP_TEST_JARS`, which names a folder holding one subfolder per build, each with its `tla2tools.jar`:

```
<folder>/v1.7.4/tla2tools.jar     the stable release; a jar without a build time is named by its folder, which must be its tag
<folder>/rolling/tla2tools.jar    a rolling build; any folder name, its build time picks the rolling expectations
```

A store's own tool folder (the one `tlaup tool dir` prints) has that shape too: there the name is read from each build's `build.json`, and `pin`, `.lock` and `.tmp/` are skipped. Each jar is checked against the golden folder of its release line under `tests/parse/golden/tlc/`; a jar that matches none stops the run, naming it. Every test that takes a build runs once per jar, each in its own temporary `TLAUP_HOME` with the jar copied into its store; no test uses the network.

```bash
TLAUP_TEST_JARS=<folder> uv run poe test-integration
```

The task refuses to run, with exit 1, when the variable is unset (it then prints how to set it), names no jar, or no `java` is found, so that nothing passes with nothing run; a plain `uv run pytest tests/integration` skips every test with the reason instead. Both builds together take about six and a half minutes on a desktop machine, three of them in `test_runner.py::test_keep_and_resume_exact` (rolling builds only), whose run must outlast TLC's first checkpoint, a minute after the JVM starts, and is then resumed to its end. The signal tests use `pgrep` to find the JVM tlaup started, and `test_workers_auto_one_cpu` uses `taskset`; each is skipped with the reason where its tool is missing, as the zsh and fish syntax checks are where those shells are. Each test's temporary folder, where TLC writes its states, is under pytest's base folder, which follows `TMPDIR`: where `/tmp` is small, point `TMPDIR` at a folder on a real disk.

`uv run poe test-lifeline` also runs the REPL on a pseudo-terminal (`tests/lifeline/test_repl_terminal.py`), and only when `TLAUP_TEST_JARS` holds a build with the REPL (a rolling build); otherwise that test is skipped with the reason.

## The lifeline agent

`src/tlaup/java/lifeline/Lifeline.java` is the source of the agent that ends a JVM when tlaup is gone ([design 20 G3](../design/20-groundwork.md#g3-java-launcher)); `src/tlaup/java/lifeline.jar` is built from it and checked in, and both are package data of `tlaup.java`. After changing the source, run `uv run poe build-lifeline` and commit the source and the jar together. Build with the JDK the lifeline job uses (Temurin 11): two JDKs need not write the same class-file bytes, and `tests/lifeline/test_jar_matches_source.py` compares them. `uv run poe test-lifeline` needs a JDK on `PATH` or in `JAVA_HOME`; a missing JDK is an error. The reused-process-id test needs `unshare --pid --fork --mount-proc` to work (root, or `--user --map-root-user`); it skips with a reason where it cannot, and fails instead when `CI` is set. `tests/unit/java/test_lifeline_jar.py` checks the jar without Java in `uv run poe test`.

## CI

`.github/workflows/test.yml` runs on every push to `main` and to a `build/**` branch (a stage's build branch runs CI before its pull request), on every pull request, and every Monday at 04:17 UTC. It is read-only (`contents: read`), every job has a timeout, and every action is pinned by commit hash with its release in a comment. The pinned hashes are research 29's values of 2026-11-19; Dependabot moves them.

- `lint`: `uv run poe lint`, `uv run ruff format --check .`, `shellcheck scripts/*.sh`, and the pre-commit hooks (`--hook-stage pre-commit`, with the test hook skipped through `SKIP: pytest` until it moves to `pre-push`).
- `unit`: `uv run poe test` on Python 3.11 and 3.15 on Linux and on 3.15 on macOS, the Python chosen through `uv` (`UV_PYTHON`), without Java and without a jar; each cell ends by checking that no tlaup folder or `.tlaplus` was left in the runner's home (`scripts/test_clean.py --home`).
- `lifeline`: `uv run poe test-lifeline` with Temurin 11, on Linux and macOS.
- `build`: `uv run poe check-release`: build, `twine check`, and `scripts/check_wheel.py`, which checks the files in the wheel and installs it into a new environment to run `tlaup --version`, `--help`, `tool dir` and `import tlaup_parse`.
- `deps-newest`: `uv sync --upgrade`, then the suite, to see what the newest versions the ranges allow do. It is not required and may be red.
- `Test`: waits for `lint`, `unit`, `lifeline` and `build` and fails unless all succeeded. It is the one status check the ruleset on `main` requires, so a new required job is added to its `needs`.

## Code map

- `src/tlaup/`: the package. `cli.py` builds the Typer app; `cmd/` holds one module per command or command group; `tlc/` resolves and runs TLC (its output is parsed by `src/tlaup_parse/`); `tools/` holds the table of main classes and what `sany`, `pcal` and `repl` share (the invocation, SANY's run); `reporters/` shows a run; `versioning/` downloads and tracks jar builds; `java/` finds Java and builds classpaths; `config/` loads settings.
- `src/tlaup_parse/`: the second import package in the same wheel: the TLC output parsers and the result model ([design 10 P2](../design/10-parser.md#p2-the-tlaup_parse-package)). Standard library only; it imports nothing from `tlaup` and does no I/O.
- `src/tlaup/resources/default_config.yaml`: packaged defaults. Its top-level `tla:` key holds upstream TLA+ download URLs; it is not the application name.
- `tests/`: `conftest.py` (the isolation fixture, the `fakes` fixture, the Hypothesis profiles), `test_isolation.py`, `expected.py` (`assert_matches`) and `clock.py` (`FakeClock`). `tests/unit/`: plain pytest tests. `tests/stateful/`: the stateful tests of the formal check, with their throwaway `reference_*.py` models. `tests/fakes/`: the fake `java`, `javac`, `git` and editor, their launchers, the prepared classes and the module sources of the `module` scenarios (`module-src/`). `tests/fixtures/research/`: captured evidence from the investigations, each folder with its own README. `tests/integration/`: the integration tests ([above](#the-integration-tests)); `discovery.py` finds the jars, `live.py` runs the tools through the API or as a process, and `specs/` holds the inputs no golden spec provides, among them `naming_fixed/`, a project with its own `TLCOverrides`.
- `tests/parse/golden/`: the golden files, real TLC, SANY and PlusCal output filed by tool and by build, each build folder with `cases.toml` and `build.toml`, the specs they ran in `specs/` and the hand-made framing cases in `synthetic/` ([design 01 T3](../design/01-testing.md#t3-golden-files)); `tests/parse/test_golden_files.py` checks they agree. `tests/parse/drive.py` reads and feeds a golden file as the runner does, `tests/parse/facts.py` holds the hand-written facts about the TLC captures and `tests/parse/test_facts.py` runs them, pending until the parser exists (package 08).
- `scripts/capture_golden.py`: captures a build's golden files again with a given jar; a developer tool that needs Java and is not run in CI.
- Test folders that arrive later: the rest of the parser's tests in `tests/parse/`, `tests/recordings/` with the GitHub recordings (package 05), `tests/lifeline/` with package 06.
- `docs/examples/`: example specs, some with custom Java modules.

## Writing tests

- **Isolation is automatic.** The autouse fixture `isolated` in `tests/conftest.py` gives every test a temporary home, working folder and `TLAUP_HOME`, a fixed terminal (`NO_COLOR`, `TERM=dumb`, 100 by 40), the time zone `TZ=UTC` (so no expected output depends on the machine's zone), a `PATH` holding only the four fake launchers, and a closed port as the tool repository; sockets are blocked. A test asks for `isolated` by name when it needs those paths ([design 01 T2](../design/01-testing.md#t2-isolation)).
- **Processes are fakes.** The `fakes` fixture scripts the fake `java`, `javac`, `git` and editor and reads what they logged; an unscripted start fails with exit 127. Their script fields are in [design 01 T4](../design/01-testing.md#t4-fakes-at-the-edges) and in work package 03's contract ([`../packages/03-test-foundation.md`](../packages/03-test-foundation.md#interfaces)). Time is a `FakeClock` passed in.
- **Expected files.** `assert_matches(actual, path, request)` compares with a file under `expected/` beside the test. `uv run pytest --update-expected` writes the files instead and lists every file it wrote at the end of the run; read each one before committing it ([design 01 T8](../design/01-testing.md#t8-expected-output-files)).
- **Feature files.** Command-line behaviour is tested by the scenarios of `tests/features/*.feature`, which `tests/test_features.py` collects; their expected files are in `tests/features/expected/`. The steps are in `tests/steps/` (`given.py`, `when.py`, `then.py`, thin wrappers over `Scenario` in `_scenario.py`, for the store and GitHub steps over `_store.py`, for the module steps over `_modules.py`, and for the steps on the signals the fake `java` received and its process group over `_signals.py`), made visible by `pytest_plugins` in `tests/conftest.py`. The vocabulary is closed: a scenario uses the steps of [design 01 T5](../design/01-testing.md#t5-feature-files-and-steps) in their words, and a new step needs a reason in its pull request; a scenario that would need a one-off step is usually a plain pytest test instead. Paths in steps may use the placeholders `{home}`, `{work}`, `{tools}`, `{modules}`, `{runs}`, `{config}` and `{kept}`.
- **In-process unless T5 says otherwise.** `I run "<command>"` calls the app in-process; a scenario uses a real-process step only in one of T5's five situations (passthrough, a pipe whose reader goes, a signal, a terminal, a variable the interpreter reads at start). The in-process step refuses the two its words cannot show: a fake `java` started without a pipe for stdout, and a `PYTHON*`, `LC_ALL`, `LC_CTYPE` or `LANG` variable set by the scenario (T12 rule 10). A failing result step prints the run's stdout and stderr.
- **Real processes and terminals.** The `as a process` and `I start ... and send <signal>` steps start `python -m tlaup` with the isolation fixture's environment and SIGINT at its default (`tests/steps/_process.py`); the `in a terminal <w> by <h>` steps run it as the leader of a new session on a pty of that size, with `TERM=xterm-256color` and no `COLUMNS` or `LINES`, and read the screen through `pyte` (`tests/steps/_terminal.py`). On a terminal a stream that is on the pty reads as the screen's text. Every wait is for a condition with a timeout: a line in the fake's log or a text on stderr or the screen (10 seconds), the process's end (60 seconds). When a wait runs out the step kills the process and fails with its stdout and stderr, or for a terminal with the last screen it saw; a step that waited for the fake's log prints the log so far. The signal and terminal steps skip on Windows with the reason (D15).
- **Rules.** The rules for writing tests are [design 01 T12](../design/01-testing.md#t12-rules-for-writing-tests). Ruff bans `unittest.mock.patch`, and the pre-commit hooks `no-patching-own-code` and `no-typed-tool-output` check rules 2 and 3. Warnings are errors.
- **What 0.8.x did.** The old suite was deleted (decision D62). The behaviour of 0.8.x that is kept is specified by the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md); a package that writes the test for a row names the row.

## Where tlaup keeps its files

Config, toolsets, modules and the run cache live in the platform's user folders under the name `tlaup` (on Linux `~/.config/tlaup` and `~/.cache/tlaup`), set in `src/tlaup/paths.py`.

## Running tlaup without touching your own folders

A `tlaup` command run by hand, or by an agent checking something, uses those real folders: `tool uninstall` or a cache cleanup there removes the maintainer's own toolchain. Point tlaup at temporary folders instead, on the `tlaup` command only:

```bash
TLAUP_HOME=<tmp>/tlaup uv run tlaup tool list
```

`TLAUP_HOME` is tlaup's own variable, so it moves config, cache and data together and no other tool (`gh`, `git`, `uv`) reads it; `TLAUP_CONFIG_DIR`, `TLAUP_CACHE_DIR` and `TLAUP_DATA_DIR` move one folder each ([design 14 F2](../design/14-config-and-cli.md#f2-folder-overrides)). The test isolation uses it too ([design 01 T2](../design/01-testing.md#t2-isolation)).
