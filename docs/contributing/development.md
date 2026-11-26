# Development

How to set up, run the checks, and find your way around the code as it is today. The code described here is release 0.8.x; the design documents in [`../design/`](../design/README.md) describe the code as it will be, and their packages, commands and test layout do not exist until the work packages are built.

## Environment and commands

Use `uv` for everything; do not call `pip` or a global Python.

```bash
uv sync --all-extras --dev     # set up the environment
uv run poe test                # the test suite with branch coverage, in random order
uv run poe test-clean          # the suite under an empty temporary home, then fail if tlaup wrote there
uv run poe test-integration    # tests/integration; fails until package 52 writes the folder
uv run poe lint                # ruff check, bandit, mypy (strict)
uv run poe format              # ruff format, Python files and Python blocks in Markdown
uv run poe build-lifeline      # rebuild src/tlaup/java/lifeline.jar from its source (needs a JDK)
uv run poe test-lifeline       # tests/lifeline: the agent with a real JVM (needs a JDK; not part of poe test)
uv run poe check               # all pre-commit hooks on all files
uv run poe check-release       # hooks, build, twine check
```

`tests/integration/` does not exist until work package 52 writes it, so until then `poe test-integration` fails with pytest's exit 4 and "file or directory not found"; 52 also adds the `TLAUP_TEST_JARS` variable that names the real jars it needs. A single test runs without coverage: `uv run pytest tests/unit/test_fakes.py::test_java_exit_code`. `pytest-randomly` prints the seed of each run; `--randomly-seed=<n>` repeats an order, and `-p no:randomly` switches it off.

Run `uv run poe lint` and `uv run poe test` before committing.

## The lifeline agent

`src/tlaup/java/lifeline/Lifeline.java` is the source of the agent that ends a JVM when tlaup is gone ([design 20 G3](../design/20-groundwork.md#g3-java-launcher)); `src/tlaup/java/lifeline.jar` is built from it and checked in, and both are package data of `tlaup.java`. After changing the source, run `uv run poe build-lifeline` and commit the source and the jar together. Build with the JDK the lifeline job uses (Temurin 11): two JDKs need not write the same class-file bytes, and `tests/lifeline/test_jar_matches_source.py` compares them. `uv run poe test-lifeline` needs a JDK on `PATH` or in `JAVA_HOME`; a missing JDK is an error. The reused-process-id test needs `unshare --pid --fork --mount-proc` to work (root, or `--user --map-root-user`); it skips with a reason where it cannot, and fails instead when `CI` is set. `tests/unit/java/test_lifeline_jar.py` checks the jar without Java in `uv run poe test`.

## CI

`.github/workflows/test.yml` runs lint, the format check (`uv run ruff format --check .`) and the test suite on every push to `main` and on every pull request, without Java and without a jar, and then checks that no tlaup folder or `.tlaplus` was left in the runner's home (`scripts/test_clean.py --home`).

## Code map

- `src/tlaup/`: the package. `cli.py` builds the Typer app; `cmd/` holds one module per command or command group; `tlc/` runs TLC and parses its output; `versioning/` downloads and tracks jar builds; `java/` finds Java and builds classpaths; `config/` loads settings.
- `src/tlaup_parse/`: the second import package in the same wheel: the TLC output parsers and the result model ([design 10 P2](../design/10-parser.md#p2-the-tlaup_parse-package)). Standard library only; it imports nothing from `tlaup` and does no I/O.
- `src/tlaup/resources/default_config.yaml`: packaged defaults. Its top-level `tla:` key holds upstream TLA+ download URLs; it is not the application name.
- `tests/`: `conftest.py` (the isolation fixture, the `fakes` fixture, the Hypothesis profiles), `test_isolation.py`, `expected.py` (`assert_matches`) and `clock.py` (`FakeClock`). `tests/unit/`: plain pytest tests. `tests/stateful/`: the stateful tests of the formal check, with their throwaway `reference_*.py` models. `tests/fakes/`: the fake `java`, `javac`, `git` and editor, their launchers, the prepared classes and the module sources of the `module` scenarios (`module-src/`). `tests/fixtures/`: `naming_fixed/` (until package 52 moves it) and `research/`, captured evidence from the investigations, each folder with its own README.
- `tests/parse/golden/`: the golden files, real TLC, SANY and PlusCal output filed by tool and by build, each build folder with `cases.toml` and `build.toml`, the specs they ran in `specs/` and the hand-made framing cases in `synthetic/` ([design 01 T3](../design/01-testing.md#t3-golden-files)); `tests/parse/test_golden_files.py` checks they agree. `tests/parse/drive.py` reads and feeds a golden file as the runner does, `tests/parse/facts.py` holds the hand-written facts about the TLC captures and `tests/parse/test_facts.py` runs them, pending until the parser exists (package 08).
- `scripts/capture_golden.py`: captures a build's golden files again with a given jar; a developer tool that needs Java and is not run in CI.
- Test folders that arrive later: the rest of the parser's tests in `tests/parse/`, `tests/recordings/` with the GitHub recordings (package 05), `tests/integration/` with package 52, `tests/lifeline/` with package 06.
- `docs/examples/`: example specs, some with custom Java modules.

## Writing tests

- **Isolation is automatic.** The autouse fixture `isolated` in `tests/conftest.py` gives every test a temporary home, working folder and `TLAUP_HOME`, a fixed terminal (`NO_COLOR`, `TERM=dumb`, 100 by 40), the time zone `TZ=UTC` (so no expected output depends on the machine's zone), a `PATH` holding only the four fake launchers, and a closed port as the tool repository; sockets are blocked. A test asks for `isolated` by name when it needs those paths ([design 01 T2](../design/01-testing.md#t2-isolation)).
- **Processes are fakes.** The `fakes` fixture scripts the fake `java`, `javac`, `git` and editor and reads what they logged; an unscripted start fails with exit 127. Their script fields are in [design 01 T4](../design/01-testing.md#t4-fakes-at-the-edges) and in work package 03's contract ([`../packages/03-test-foundation.md`](../packages/03-test-foundation.md#interfaces)). Time is a `FakeClock` passed in.
- **Expected files.** `assert_matches(actual, path, request)` compares with a file under `expected/` beside the test. `uv run pytest --update-expected` writes the files instead and lists every file it wrote at the end of the run; read each one before committing it ([design 01 T8](../design/01-testing.md#t8-expected-output-files)).
- **Feature files.** Command-line behaviour is tested by the scenarios of `tests/features/*.feature`, which `tests/test_features.py` collects; their expected files are in `tests/features/expected/`. The steps are in `tests/steps/` (`given.py`, `when.py`, `then.py`, thin wrappers over `Scenario` in `_scenario.py`, for the store and GitHub steps over `_store.py`, and for the module steps over `_modules.py`), made visible by `pytest_plugins` in `tests/conftest.py`. The vocabulary is closed: a scenario uses the steps of [design 01 T5](../design/01-testing.md#t5-feature-files-and-steps) in their words, and a new step needs a reason in its pull request; a scenario that would need a one-off step is usually a plain pytest test instead. Paths in steps may use the placeholders `{home}`, `{work}`, `{tools}`, `{modules}`, `{runs}`, `{config}` and `{kept}`.
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
