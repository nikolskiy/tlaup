# 03. Test foundation

Size: L, as two pull requests of size M (03a, 03b). Suggested model: most capable. Status: ready.

## Goal

Every test runs isolated: its folders, home, working folder, terminal and `PATH` are temporary and fixed, sockets are blocked, and only fake `java`, `javac`, `git` and an editor can be started. The fakes, the expected-file helper and an injected clock exist for every later package. The pytest settings of the design are on, the new development dependencies are in, the mechanical checks of the test rules are in place, and the whole old suite is gone: every test under `tests/unit/` and `tests/integration/` of release 0.8.x, its conftests, the old fixtures and `pytest-mock` (decision D62). What the old tests protected is carried by the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md), each kept row with its owner package. Nothing a user sees changes.

## Covers

- Roadmap items ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)):
  - "Isolation is automatic and total: every test runs with the tool's folders pointed at a temporary folder ..." (roadmap line 359). Closed here, the hand-kept patch lists and the wrong patch targets included (they go with the old tests), apart from the clean-home check on every system of the unit matrix, which comes with the matrix (package [53](53-ci-workflows.md)).
  - "Unit tests cannot reach the network or start an unmocked subprocess; the 23 real subprocess starts in the unit suite (22 `java`, one `git`) go away." (line 360), in part: the processes and the socket block; the 23 starts go with the old tests. The GitHub recordings and the `github` fixture are package [05](05-github-recordings.md).
  - "Coverage policy: branch coverage on; a `fail_under` near the current 83 percent; ..." (line 375), in part: everything except `fail_under`, which package 59 measures and sets ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings): no threshold until then).
  - "Unit job on Python 3.11 and the newest release ...; remove Java and the jar download from the unit job once the suite no longer needs them." (line 386), in part: the two steps go here, as [30 I2](../design/30-ci-and-release.md#i2-unit-job) says ("in the pull request that lands the isolation and the fakes and deletes the old tests"). The matrix is package 53.
  - "Design the testing approach from scratch ..." (line 351), in part: the mechanical checks of T12's rules 2, 3 and 10's prerequisites; the approach itself is carried by every later package.
  - "Pre-commit: move the test hook to pre-push; add a format hook; ..." (line 418), in part: the hook `no-typed-tool-output` that [30 H1](../design/30-ci-and-release.md#h1-pre-commit-hooks) names. The format hook was package [01](01-ruff-format.md); the rest is package 57.
  - "Snapshot tests through a fixed-width, colourless console with an injected clock ..." (milestone 1b, line 321), in part: the expected-file helper of T8. The reporter snapshots are package 38.
- Design sections:
  - [01 T1](../design/01-testing.md#t1-the-approach): the three edges as fixtures and fakes.
  - [01 T2](../design/01-testing.md#t2-isolation): all of it, the removed fixtures included. The integration folder's own `isolated` (real `PATH` and `JAVA_HOME`, the JVM's folders) is package 52, which writes the new `tests/integration/`.
  - [01 T4](../design/01-testing.md#t4-fakes-at-the-edges): "Processes" and "Time", with the fields and the log line of the stage 4 review (the `version` object, SIGQUIT, `checkpoint` with `commit_before_line` and its log line, `javac -version`). "Network" is package 05, except the socket block and the closed-port address, which the isolation fixture sets here.
  - [01 T8](../design/01-testing.md#t8-expected-output-files): all of it.
  - [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings): all of it except the removal of `pending` and the final `fail_under` (package 59).
  - [01 T11](../design/01-testing.md#t11-the-existing-tests): all of it: the deletion of the old tests and their fixtures, and the development guide. The inventory's rows are tested by their owners; 59 checks that every kept row has its test.
  - [01 T12](../design/01-testing.md#t12-rules-for-writing-tests): the mechanical checks of rules 2 and 3. Rule 10's check sits in the steps (package 18).
  - [03, "Specs and their tests"](../design/03-run-stages-and-specs.md#specs-and-their-tests): the second of the "Edits settled 2026-11-24" (resources under warnings as errors, question Q17). The first, SIGQUIT in the signals machine (Q5), is package [21](21-java-launcher.md)'s.
  - [30 I2](../design/30-ci-and-release.md#i2-unit-job): the removal of the Java and jar steps, and with them the one old command CI runs (`tlaup tools install`, D62's exception, which ends here).
  - [30 I8](../design/30-ci-and-release.md#i8-lint-rules), the `TID251` row only. The other rows are package 58.
  - [30 B2](../design/30-ci-and-release.md#b2-build-fixes), the row "Development dependencies of 00" only. The other rows are package 56.

## Depends on

- [01](01-ruff-format.md): the formatted tree and the format check.
- [02](02-errors-and-paths.md): `AppPaths.from_env` and its derived folders (the isolation fixture returns one and its own test writes through every folder), and `tlaup.context.reset()` (the fixture calls it).

## Files

This package is large in files and small in judgement. A reviewer should read, in this order: `pyproject.toml` (settings and dependencies), `tests/conftest.py` (the isolation fixture), `tests/fakes/java.py` with its tests, `.pre-commit-config.yaml`, then the deletions, which are whole folders and files.

Creates:

| File | What |
| --- | --- |
| `tests/fakes/java.py`, `javac.py`, `git.py`, `editor.py` | The four fakes of T4 (contract under Interfaces). Standard library only; no import of `tlaup` or `pytest`. |
| `tests/fakes/_fakelib.py` | What the four share: reading the script, writing the log. |
| `tests/fakes/__init__.py`, `tests/fakes/control.py` | The launcher writer `fake_bin_dir` and the `Fakes` object the `fakes` fixture returns. |
| `tests/fakes/java-src/plain/Plain.java`, `tests/fakes/classes/plain/Plain.class`, `tests/fakes/classes/README.md` | One prepared class for the fake `javac`, compiled once with `javac --release 11`; the README gives the command and the compiler's version. Packages 30 and 31 add the classes they need beside it, by the same command. |
| `tests/expected.py` | `assert_matches` (T8). |
| `tests/clock.py` | `FakeClock`, the injected time of T4. |
| `tests/test_isolation.py` | T2's two tests. |
| `tests/unit/test_fakes.py`, `tests/unit/test_expected.py`, `tests/unit/test_clock.py` | Tests of the fakes and the two helpers. |
| `scripts/test_clean.py` | The body of `poe test-clean` and of the CI step (below). |

Changes:

| File | What |
| --- | --- |
| `pyproject.toml` | The pytest and coverage blocks of T10, with the one adjustment under Context; the development dependencies (six added, `pytest-mock` removed); `TID251` and its banned name; the poe tasks `test`, `test-clean`, `test-integration`. |
| `uv.lock` | From `uv lock` after the dependency change. |
| `tests/conftest.py` | Rewritten: the `isolated` fixture, the `fakes` fixture, the `--update-expected` option and the list of rewritten files at the end of a run, and the Hypothesis profiles (moved from `tests/stateful/conftest.py`). None of the old fixtures stays (`runner`, `fixtures_dir`, `make_installed_version`, `base_settings`, `mock_load_config`, `mock_cache`, `java_available`, `javac_available`): nothing new uses them. |
| `tests/stateful/test_run_folders.py`, `test_signals.py`, `test_tool_store.py`, `reference_*.py` | Resource handling only, so they pass under `filterwarnings = error` (see Context). No rule, precondition, invariant or step changes. |
| `.pre-commit-config.yaml` | The local hooks `no-typed-tool-output` and `no-patching-own-code` (below). |
| `.github/workflows/test.yml` | The steps "Set up Java" and "Download tla2tools.jar" (`uv run tlaup tools install`) go; a last step runs the clean-home check on the runner's home. |
| `.gitignore` | `.coverage.*`: with `parallel = true` coverage writes one data file per process, named with the host name, which must never be committed. |
| `docs/contributing/development.md` | Commands, code map and a short testing section (below). |

Deletes ([01 T11](../design/01-testing.md#t11-the-existing-tests), decision D62), in 03b, in one commit of its own:

- Every old test under `tests/unit/`: the files at its top (`test_cli.py`, `test_config.py`, `test_config_suite.py`, `test_settings.py`, `test_tlc_modules_path.py`, `test_tlc_show_command.py`) and the folders `check_java/`, `cmd/`, `java/`, `spec/`, `tlc/`, `tools/` and `version_manager/` whole, with their conftests (`tools/conftest.py` with `mock_github_api`, `mock_download` and `installed_v180`; `spec/conftest.py` with `mock_tlc_env`) and `__init__.py` files. `tests/unit/__init__.py` stays, and so do the new tests of 02 (`test_errors.py`, `test_paths.py`, `test_context.py`) and of 03a.
- `tests/integration/` whole: its three test files, `conftest.py` and `__init__.py`. Package 52 writes the new folder.
- The old fixtures `tests/fixtures/releases.json`, `tests/fixtures/tags.json` and `tests/fixtures/naming_dynamic/` (T3). `tests/fixtures/naming_fixed/` stays: 52 moves it beside its T9 row (inventory row R33). `tests/fixtures/research/` stays as evidence.
- `tests/stateful/conftest.py` (its profiles move to `tests/conftest.py`).
- `pytest-mock` from the development dependencies (T12 rule 2).

No test outside the new ones of 02 and 03a is kept, ported or extended, and no later package deletes an old test: there are none left.

Shared with packages of the same period: `pyproject.toml` and `uv.lock` with [06](06-lifeline-agent.md), which can run beside 02 and 03 (its marker `lifeline`, its folder `tests/lifeline/` in `norecursedirs`, its poe tasks; a few lines each, and whichever merges second keeps both); `docs/contributing/development.md` with 02 (a different section). Later: `tests/conftest.py` gains the `github` fixture in 05; `.pre-commit-config.yaml` and `test.yml` are edited again by 57 and 53.

### What the real starts and the network become

Measured for this cut on 2026-11-21: the 207 collected items of `tests/unit`, run with logging stand-ins for `java`, `javac` and `git` on an otherwise empty `PATH`, a socket guard and an empty home folder, started `java` 20 times and `git` once, attempted no connection, and wrote `~/.config/tlaup/config.yaml` and four folders under `~/.cache/tlaup/run/tlc/`. Every one of those starts and writes came from old test files (`check-java`'s tests, `tools/test_install.py`, `test_pin.py`, `test_upgrade.py`, `test_cli.py`), which go here. So after 03b the fake `java`'s log shows only starts a test scripted, and the clean-home check has nothing to find.

## Interfaces

Provides, all "written by stage 4" where the design gives only words; a worker may adjust a name or a parameter if the behaviour and the tests stay, and says so in the pull request.

**The isolation fixture**, `tests/conftest.py`, from [01 T2](../design/01-testing.md#t2-isolation) (copy the body there):

```python
@dataclass(frozen=True)
class Isolated:
    home: Path          # tmp_path / "home"; HOME and USERPROFILE
    work: Path          # tmp_path / "work"; the working folder, created
    bin: Path           # tmp_path / "bin"; the whole PATH: the four launchers   (added by stage 4)
    paths: AppPaths     # AppPaths.from_env(os.environ) after the fixture's changes

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch) -> Isolated
```

It removes every `TLAUP_*` variable and the list of T2, sets `TLAUP_HOME=<home>/tlaup`, `HOME`, `USERPROFILE`, `NO_COLOR=1`, `TERM=dumb`, `COLUMNS=100`, `LINES=40`, `PATH=<bin>`, `TLAUP_TOOL_REPOSITORY=https://127.0.0.1:9/repos/tlaplus/tlaplus`, changes into `work`, and calls `tlaup.context.reset()`. Everything through `monkeypatch`, so it is undone after the test.

**The launchers**, `tests/fakes/control.py`:

```python
def fake_bin_dir(tmp_path: Path) -> Path    # writes bin/java, bin/javac, bin/git, bin/editor; returns bin
def write_launcher(path: Path, fake: str, *, script: Path | None = None) -> Path
    # one launcher: a file whose first line is "#!" and the running interpreter (sys.executable), which runs
    # tests/fakes/<fake>.py with its own path as argv[0]; on Windows a .cmd file beside it.
    # script: a script file baked into this launcher, read instead of TLAUP_FAKE_<TOOL> (for a JDK folder)
```

**The `fakes` fixture** (not autouse), `tests/conftest.py`, returning `tests.fakes.control.Fakes`:

```python
class Fakes:
    bin: Path
    def script(self, tool: Tool, data: Mapping[str, Any]) -> Path
        # writes the tool's script (JSON) under tmp_path, sets TLAUP_FAKE_<TOOL> with monkeypatch,
        # and fills "log" with the tool's log file unless given; Tool = Literal["java", "javac", "git", "editor"]
    def log(self, tool: Tool) -> list[dict[str, Any]]        # the log's lines, parsed; [] when nothing ran
    def remove(self, tool: Tool) -> None                    # "java is not installed"
    def not_executable(self, tool: Tool) -> None            # the launcher loses its execute bits
    def jdk(self, folder: Path, data: Mapping[str, Any]) -> Path
        # a JDK folder: folder/bin/java and folder/bin/javac, launchers with a script of their own (data),
        # logging to the same logs as the PATH launchers; returns folder (for JAVA_HOME)
```

Package 18's Given and Then steps about Java, `javac`, `git` and the editor are written on this object, among them the new steps of [01 T5](../design/01-testing.md#t5-feature-files-and-steps) that the stage 4 review added (`java begins a checkpoint after line <n> and commits it before line <m>`, `java answers its version check with ...`, `javac is version "<v>"`, and the wait `once java has begun its checkpoint`, which polls `log("java")` for the `checkpoint` line). None of them is this package's; it gives them the fields and the log line they script and read.

**The fakes' contract.** Each fake reads its script from the file named by `TLAUP_FAKE_JAVA`, `TLAUP_FAKE_JAVAC`, `TLAUP_FAKE_GIT` or `TLAUP_FAKE_EDITOR` (T4 names the first and the last; the middle two follow the same pattern), or from the script baked into its launcher. With no script, every fake writes `fake <tool>: no script` to stderr and exits 127, so an unplanned start fails loudly (T4 says this of `java`; it is extended to the four, written by stage 4). Each writes the log of T4, one JSON line per event, flushed at once: `start` (process id, process group id where the system has one, the launcher's own path, the argument list, the working folder, the main class or `-version`, whether stdout is a pipe), `signal` (the name, also for a signal it ignores), `checkpoint` (`java` only, below), `exit` (the code, on every way out the fake controls).

The fake `java`, every field of [T4](../design/01-testing.md#t4-fakes-at-the-edges), with what the design leaves open settled:

```json
{"version": "25.0.5",
 "version_delay_ms": 0,
 "log": "<tmp>/java.jsonl",
 "runs": [{"main": "tlc2.TLC", "stdout": "tlc/v1.7.4/violation.out", "stderr": null,
           "generate_lines": null,
           "exit": 12, "line_delay_ms": 0, "hang_after_line": null,
           "on_sigint": 130, "on_sigterm": 143,
           "write_into_metadir": [], "checkpoint": null, "echo_stdin": false, "replace": {}}]}
```

- **Arguments** are read as `java` reads them: everything before the main class that starts with `-` is a JVM option; `-cp`, `-classpath` and `--class-path` take the next argument as their value; every other option is one argument (`-javaagent:<jar>=pid=<n>`, `-Dname=value`, `-X...`, `-XX:...`). The first argument that is not an option is the main class; the rest are its arguments. So the lifeline agent and the three encoding options that [20 G3](../design/20-groundwork.md#g3-java-launcher) puts first (packages 21 and 33) do not hide the main class. `-version` before any main class is the version request.
- **`version`, `version_delay_ms`** (T4): the version request is answered on stderr, after the delay, with a banner in the real three-line form, for example `openjdk version "11.0.33" 2026-10-20`, `OpenJDK Runtime Environment Temurin-11.0.33+10 (build 11.0.33+10)`, `OpenJDK 64-Bit Server VM Temurin-11.0.33+10 (build 11.0.33+10, mixed mode)` (research 28 captured these three lines on a GitHub runner). It uses up no entry of `runs`. `version` may instead be an object `{"stdout": "<text>", "stderr": "<text>", "exit": <n>}`, printed as given, so that the macOS stub's `Unable to locate a Java Runtime.` with exit 1 and [13 J3](../design/13-modules-and-java.md#j3-one-java-start)'s answer that is not a version can be scripted (packages 20 and 39).
- **Which run answers** (T4, T5 "Where a declared run's output comes from"): a start of a main class takes the first entry of `runs` with that `main` that no earlier `start` line in the log has taken, so each declared run answers one start; the `start` line records the index it took. With none left, the fake exits 127 with `fake java: no script for <main>`. The main classes are `tlc2.TLC`, `tla2sany.SANY`, `pcal.trans` and `tlc2.REPL` alike.
- **`stdout`, `stderr`**: `null`; a file, given as a path relative to `tests/parse/golden/` (the golden files arrive with package 07) or as an absolute path (a file a test wrote itself, for example lines with the bytes `FF FE` for the launcher's decoding tests of package 21); or literal text, given as `{"text": "..."}` (written by stage 4: T4 allows "a golden file ... or literal text" in one field without saying how they are told apart). Bytes are written exactly as they are in the file. The `stderr` text is written whole before the `stdout` replay starts (the design does not fix an order; in `-tool` mode TLC writes almost nothing to stderr).
- **`generate_lines`**: instead of a replay, `line 1` to `line <n>` on stdout.
- **`exit`**, **`line_delay_ms`**, **`hang_after_line`**: as T4. Lines are counted on stdout. A hang waits for a signal; as a guard against a leaked process, a hang ends by itself after 120 seconds with an `exit` line and code 124 (written by stage 4; no test may rely on it).
- **`on_sigint`, `on_sigterm`**: a code, or `"ignore"`. SIGQUIT needs no field (T4): it is logged and the fake carries on, as the JVM does after its thread dump ([20 G3](../design/20-groundwork.md#g3-java-launcher)'s Ctrl-\ scenario). Written by stage 4: SIGHUP is logged and the fake exits 129. A signal that is already ignored when the fake starts stays ignored and gets no handler, and the `start` line lists the signals that were ignored at start; [20 G3](../design/20-groundwork.md#g3-java-launcher)'s `nohup` rule is what the tests of packages 21 and 39 check through this. Signal code is guarded with `hasattr(signal, ...)` (D15).
- **`write_into_metadir`**: file names created before the output, in a folder the fake makes under the folder given after `-metadir`, named as TLC names it (a timestamp such as `26-11-14-22-32-49`), as T4 says since the review finding TU5.
- **`checkpoint`** (T4, question Q10): `{"begin_after_line": n, "commit_before_line": m}`. After replaying line `n` (written and flushed) the fake writes `queue.tmp` and `vars.tmp` into its timestamped folder and then logs a `checkpoint` line holding that folder; before it writes line `m` it renames the two to `queue.chkpt` and `vars.chkpt`. The rename comes before line `m` because TLC commits its checkpoint before it prints 2196: tlaup sends its held SIGTERM on at 2196, and a fake that printed first would let the signal race the rename. With the 2195 line at `n`, the 2196 line at `m` and `hang_after_line` between them, this is the checkpoint the deferral scenarios of [11 R6](../design/11-runner.md#r6-run-folders) and G3 need; a signal that ends the fake between `n` and `m` leaves the `.tmp` files, as TLC does. `checkpoint` or `write_into_metadir` without `-metadir` among the arguments is a script error: exit 127 with a message.
- **`echo_stdin`**: stdin to stdout line by line until it closes, then `exit`.
- **`replace`**: plain substitution in every replayed line, keys and values as UTF-8 bytes. The fake does not expand `{work}` or other placeholders; whoever writes the script does (package 18's steps).

The `checkpoint` log line has one known window (T5, Risks): it is logged once line `n` is in tlaup's pipe, not once tlaup has read it, and a signal that lands while 2195 is still in the pipe or the launcher's queue is sent on at once (G3, finding FC8). Writing the `.tmp` files and the step's wait for the log line come between, which should be far longer than tlaup's read of one line; not tried. If the deferral scenarios of 39 turn out flaky, the remedy the design names is in this fake: wait until its stdout pipe is empty before logging the line (on Linux `FIONREAD` gives the unread byte count of a pipe; not tried). A seam in the product is not the answer.

The fake `javac` (T4: "answers `-version` ... copies prepared class files ... or prints a recorded compiler error and exits 1"):

```json
{"version": "25.0.5", "classes": "<repo>/tests/fakes/classes", "fail_with": null, "delay_ms": 0,
 "log": "<tmp>/javac.jsonl"}
```

- `-version` prints `javac <version>` on stdout and exits 0, as JDK 25 does (T4; [13 M3](../design/13-modules-and-java.md#m3-module-build-details)'s version check, package 30, reads it).
- A compile copies, for each source `X.java` among the arguments, every `X.class` and `X$*.class` under `classes` into the folder given after `-d`, keeping their path below `classes`; a source with no prepared class is `fake javac: no prepared class for X.java` and exit 2.
- `fail_with`: a file (absolute, or a name under `tests/fakes/javac-errors/`) printed to stderr, then exit 1. Recordings of real `javac` errors are added by the package that first needs one (31).
- `delay_ms`: wait before doing anything (written by stage 4, for [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder)'s timeout test, package 30).

The fake `git`: `{"stdout": "abc1234\n", "exit": 0, "log": ...}`, defaults as shown: prints a fixed short hash. The fake `editor`: `{"write": "<text>" | null, "exit": 0, "log": ...}`: writes the text into the file named by its last argument, or leaves it alone, then exits.

**The expected-file helper**, `tests/expected.py`, from [01 T8](../design/01-testing.md#t8-expected-output-files):

```python
def assert_matches(actual: str, expected: Path, request: pytest.FixtureRequest) -> None
```

Compares after normalising line endings; on a mismatch fails with a unified diff; with `pytest --update-expected` writes the file instead (creating it and its folder if needed) and records it; a missing file without the option fails and names the option. At the end of a run with the option, the terminal summary lists every file it wrote (T8's only guard against a wrong change riding along). Expected files live beside the tests that use them, under `expected/`, except a golden case's `<case>.json`, which sits beside its `.out` (T8's one exception; package 15).

**The injected time**, `tests/clock.py` ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges), Time):

```python
class FakeClock:
    def __init__(self, start: datetime = datetime(2026, 11, 15, tzinfo=UTC)) -> None
    def __call__(self) -> float               # seconds, for clock: Callable[[], float] (reporters, 38)
    def now(self) -> datetime                 # aware UTC, for now: Callable[[], datetime] (store 23, remote 25)
    def sleep(self, seconds: float) -> None   # records the request and advances; for sleep: (client 24, download 26)
    def advance(self, seconds: float) -> None
    sleeps: list[float]
```

**Settings**, `pyproject.toml`, T10's block as written, with the one adjustment explained under Context:

```toml
[tool.pytest.ini_options]
addopts = "--strict-markers --strict-config --disable-socket -p no:cacheprovider -m 'not pending'"
testpaths = ["tests"]
norecursedirs = ["tests/integration", "tests/lifeline", "tests/fakes", "tests/fixtures"]
filterwarnings = ["error"]
markers = [
    "integration: needs Java and real jars (TLAUP_TEST_JARS)",
    "lifeline: needs a real JDK; run by the lifeline job (30 I2), not the unit job",
    "pending: written before the code it tests (03); the work package that builds the code removes the marker",
]

[tool.coverage.run]
branch = true
parallel = true
patch = ["subprocess"]
source = ["tlaup"]          # package 09 adds "tlaup_parse"

[tool.coverage.report]
show_missing = true
# fail_under: set by the last milestone 2 package, see below
```

No `fail_under` (T10: none until package 59 measures the figure; the deletion here drops it to almost nothing, and D62 asks of `main` only that it be green). The comment line is T10's and stays.

poe tasks: `test = "pytest --cov --cov-report=term-missing"`; `test-clean` runs `scripts/test_clean.py`; `test-integration` runs `pytest tests/integration --no-cov`. Until package 52 writes the folder there is nothing there, so the task reports that no tests ran; 52 adds the `TLAUP_TEST_JARS` check and message.

Consumes: `AppPaths`, `tlaup.context.reset()` (02).

## Tests that must pass

Plain pytest, new:

- `tests/test_isolation.py` ([01 T2](../design/01-testing.md#t2-isolation), "Tests"): one test writes a file through every folder of `AppPaths` (`config`, `cache`, `data` and the seven derived paths) and asserts each is under `tmp_path`; the pair of tests on `TLAUP_LEAK_CHECK`, each asserting it is absent and then setting it with `os.environ` directly (the one deliberate break of rule 7), so whichever runs second fails if the fixture did not clean up. Also: `PATH` holds only `bin`; `shutil.which` finds exactly the four fakes there; `HOME` and the working folder are under `tmp_path`.
- `tests/unit/test_fakes.py`: each launcher started as a real child with `subprocess.run` (or `Popen` where the test signals it) from an argument list. For `java`: no script gives 127; the version banner and its delay; a version object on each stream with its exit code; main class found behind `-javaagent:x=pid=1`, three `-D` options and `-cp a b`; a replay from an absolute path reproduces the file byte for byte, including invalid UTF-8; `{"text": ...}` on each stream; `generate_lines`; `exit`; two declared runs of one main class answer two starts in order and a third gets 127; `replace`; `echo_stdin`; `write_into_metadir` (the files in the timestamped folder); `checkpoint` with `hang_after_line` between `begin_after_line` and `commit_before_line`: the `checkpoint` log line names the timestamped folder and appears only after line `n` could be read from the pipe, the `.tmp` files exist when it does, a SIGTERM during the hang leaves the `.tmp` files and no `.chkpt`, and without the signal the `.chkpt` files exist by the time line `m` can be read and the `.tmp` files are gone; `hang_after_line` with a signal from the test, waited for through the log, never by sleeping: SIGTERM gives `on_sigterm`, `"ignore"` keeps it running and logs the signal, SIGQUIT is logged and does not end it, SIGHUP gives 129; a signal ignored at start stays ignored; the `start` line's fields, including the pipe flag both ways. For `javac`: `-version`; a compile that copies `Plain.class`; a missing class; `fail_with`. For `git` and `editor`: the default answer, the logged arguments, the editor's write and exit code. For `Fakes`: `remove`, `not_executable` (then `shutil.which` finds nothing), and a `jdk` folder whose `java` logs its own path. The signal tests are skipped on Windows with the reason.
- `tests/unit/test_expected.py`: a match passes; a mismatch fails with a diff; `\r\n` against `\n` matches; with the option a file is written and listed in the summary; a missing file fails naming the option. Drive the option through pytest itself (pytest's `pytester` plugin, or a child `pytest` in `tmp_path`).
- `tests/unit/test_clock.py`: `sleep` records and advances; `now()` is aware UTC and moves with `advance`.

Old tests: none remain after 03b. The tests that stay (02's, 03a's, `tests/stateful/`) pass in random order: run the suite at least three times with different seeds of `pytest-randomly` and say in the pull request that it passed each time.

Stateful tests: with `hypothesis` installed, the reference-model tests of `tests/stateful/` (the `..._reference_model` tests and the plain tests without `pending`) start running in the default suite; they must pass under `filterwarnings = error` (see Context). The `pending` tests stay deselected; their packages (21, 27a, 35a) remove the markers.

Preserved-behaviour rows: this package owns none. It deletes the tests that held them; each kept row's owner writes its test ([inventory](../design/preserved-behaviour-2026-11-22.md), 01 T11).

Mechanical checks that must hold on the branch:

- `uv run ruff check .` with `TID251` on and `unittest.mock.patch` banned.
- `uv run pre-commit run --all-files` with the new hooks.
- `uv run poe test-clean` passes.
- CI's clean-home step passes.

## Changelog

None. Nothing a user sees changes.

## Context for the worker

Decisions this rests on: D16 (the test approach was designed first), D33 (feature files later, plain pytest here), D25 (one variable moves every folder, so isolation needs no patch), D62 (the old tests go here, all at once; between packages `main` need only be green), D15 (no Windows CI, but `.cmd` launchers, `pathlib`, `hasattr(signal, ...)`), D6 (one release).

**The deletion and what replaces it** ([01 T11](../design/01-testing.md#t11-the-existing-tests), decision D62). The old suite patches names by hand, feeds the parser invented TLC output and asserts on mocked calls; porting it would be work on tests whose code is about to go. So 03b deletes it whole, and with it every reason to keep `pytest-mock`, the patch fixtures that stood for GitHub and TLC (`mock_github_api`, `mock_download`, `mock_tlc_env`) and a hook against new `mocker` calls (question Q2, answered by D62). What the old tests protected is the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md): each row a user can observe, each kept row with an owner package that writes its test. From 03b until an owner lands, its rows have no test; that gap is accepted under D62, and package 59 checks that every kept row has a test that exists and passes. Do not keep an old test "for safety" and do not port one: the inventory, not the old file, is the requirement.

Make the deletion one commit of its own in 03b, holding nothing else, so that the reviewer checks it by `git show --stat`.

**Between packages.** `main` need only be green: it builds, lint and the type checks pass, and the tests still in the suite pass (D62, [00, "What every package must respect"](../design/00-overview.md#what-every-package-must-respect)). The one old command a CI job runs is the `uv run tlaup tools install` step of `test.yml`, which fetched a jar for the old tests; it goes here with them ([30 I2](../design/30-ci-and-release.md#i2-unit-job)), so from this package on no CI job runs an old command. `release.yml` has the same step but runs only on a tag, and nothing is tagged between packages.

**The mechanical checks** (rules 2 and 3), local pygrep hooks in `.pre-commit-config.yaml`, which package 53 then runs in CI:

- `no-patching-own-code`: `monkeypatch\.(setattr|setitem|delattr)\b` in `^tests/.*\.py$`, excluding every `conftest.py` and `tests/fixtures/research/`. No test file has one once the old suite is gone (today none has one either; checked).
- `no-typed-tool-output` (the name [30 H1](../design/30-ci-and-release.md#h1-pre-commit-hooks) gives): `@!@!@STARTMSG` in `^tests/.*\.(py|feature)$`. Its `exclude` names, with a comment, `tests/fixtures/research/` (evidence; two scripts there hold the marker). The old `tests/unit/tlc/test_parser.py`, which held typed marker text, is deleted here, so it needs no exclude. Rule 3's other exceptions (`synthetic/` holds `.out` files, which the hook does not read; the Hypothesis printer and strategies) are a later package's to add, by exact path with a comment, when it writes such a file: package [10](10-framing-and-codes.md) adds `tests/parse/test_framing_props.py`. Do not dodge the check by splitting the marker in a string.
- `TID251` in `[tool.ruff.lint]` `select`, with `[tool.ruff.lint.flake8-tidy-imports.banned-api] "unittest.mock.patch".msg = "..."` naming rule 2. It applies to `src/` too, where nothing uses the name. Try whether `patch.object` and `patch.dict` through `from unittest import mock` are caught; if not, ban them by name as well and say so.

**Why the settings differ from T10's block in one place.** `source = ["tlaup"]`, not `["tlaup", "tlaup_parse"]`: `tlaup_parse` does not exist until package 09. Tried for this cut (pytest-cov 7.1.0, coverage 7.17.3, 2026-11-21): naming a package that is never imported makes coverage print `CoverageWarning: Module tlaup_parse was never imported. (module-not-imported)` at the end of the run, and the run does not fail under `filterwarnings = error`, because the warning comes after the tests. It would be noise on every run until 09, so 09 adds the name (its file says so). The `lifeline` marker line and `tests/lifeline` in `norecursedirs` are T10's; package [06](06-lifeline-agent.md) needs the same two lines, and whichever of 03b and 06 merges second keeps one copy of each; `--strict-markers` makes a forgotten marker fail. The `pending` marker's "(03)" means design 03; keep T10's text.

**What `filterwarnings = error` does to `tests/stateful`** (question Q17, settled: [03, "Edits settled 2026-11-24"](../design/03-run-stages-and-specs.md#specs-and-their-tests)). `hypothesis` becomes a development dependency here, and `filelock` is already in `uv.lock` (through `pre-commit` and `virtualenv`; package 23 makes it a runtime dependency), so the files stop skipping themselves and their reference-model tests run in the default suite from this package on. Tried for this cut: all of them pass without `-W error`; with it, six fail on `ResourceWarning` (pipes of child processes left open, and `Popen` objects collected while their child still runs): the signals machine, the three `test_child_ends_with_tlaup_reference_model` cases and `test_without_the_lifeline_the_child_runs_on_reference_model` in `test_signals.py`, and the store machine in `test_tool_store.py`. The maintainer agreed to the fix on 2026-11-24: every child those tests start is waited for and its pipes are closed, in a `finally` or the machine's teardown, in those files and the reference models. It is resource hygiene; no rule, invariant or step changes, and the pull request shows that. A `filterwarnings` `ignore` line is not the fix (T10 allows those only for third-party warnings that cannot be fixed). The folder took 2 minutes 43 seconds on the machine that tried it with the development profile; in CI, where `CI` is set and the `ci` profile runs 200 examples, expect the unit job to grow by two to three minutes. The other settled edit of the same paragraph, the SIGQUIT handler of the signals machine's fake child (Q5), is not this package's: package [21](21-java-launcher.md) makes it when it takes the machine off `pending`.

**The Hypothesis profiles** move from `tests/stateful/conftest.py` to `tests/conftest.py` unchanged (`ci`: `derandomize=True`, 200 examples, `deadline=None`, no example database; `dev`: 50 examples; `ci` when `CI` is set), so that `tests/parse/` (packages 10 and 11) gets them too. The `try`/`except ImportError` can go now that the library is installed.

**Development dependencies** ([30 B2](../design/30-ci-and-release.md#b2-build-fixes), [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings); research 30 ran the first five as the design uses them):

- `pytest-bdd>=9.0.1,<10` (the only version that runs on the locked pytest 9.2; it reaches into pytest's private fixture manager).
- `coverage>=7.10.6` (the subprocess patch; pytest-cov 7.1.0 needs it). Locked today: 7.17.3.
- `responses>=0.23.3,<1`, `pytest-socket>=0.8.1,<1`, `pyte>=0.8.2,<1`.
- `hypothesis` and `pytest-randomly`: the version `uv` locks as the floor and the next major version as the cap (T10). `pytest-randomly` was not run by anyone for the design.
- `pytest-mock` is removed (T12 rule 2): nothing uses it once the old suite is gone.

All six new ones are added here, although only `hypothesis`, `pytest-socket` and `pytest-randomly` are used at once, so that `pyproject.toml` and the lock change once for the whole test design.

**The isolation fixture, points that are easy to miss.**

- `PATH` holds only `bin`. A test may still start `sys.executable` by its absolute path; the stateful tests and the fakes' own tests do.
- `TLAUP_TOOL_REPOSITORY` points at a closed port. Nothing reads it until package 19; from then on every test that passes the real environment sees it as a source.
- `tmp_path` now holds `home`, `work` and `bin`. A test that makes its own folder of one of those names under `tmp_path` collides; check the stateful tests by search.
- The launchers' first line names `sys.executable`. A very long interpreter path can pass the kernel's limit for a `#!` line (it was 127 bytes on old Linux kernels, 255 since 5.1); if it does, write the launcher as `#!/bin/sh` and an `exec` line, and say so.
- `coverage`'s subprocess patch also starts in the fakes' Python processes; research 30 found that a file outside `source` is not measured and that its stderr stays empty. The fakes must stay quiet on stderr unless scripted, because tests compare streams.

**The clean-home check** ([01 T2](../design/01-testing.md#t2-isolation), "Proof that it holds"; [30 I2](../design/30-ci-and-release.md#i2-unit-job)). `scripts/test_clean.py` makes an empty temporary folder, runs `sys.executable -m pytest` with `HOME` and `USERPROFILE` set to it and the `XDG_*` variables removed, then lists everything in it and fails if a tlaup folder (`.config/tlaup`, `.cache/tlaup`, `.local/share/tlaup`, `Library/Application Support/tlaup`, `Library/Caches/tlaup`) or `.tlaplus` is there. Written in Python, not shell, so it runs on every system. The same check without the run is the last step of the test job, on the runner's real home, after `uv run poe test`; the two Java and jar steps must go in the same pull request, because the jar step installs into the runner's home and would make the check fail.

**The development guide** ([01 T11](../design/01-testing.md#t11-the-existing-tests), last paragraph). In `docs/contributing/development.md`: the commands list gains `uv run poe test-clean` and replaces `uv run pytest tests/integration` with `uv run poe test-integration`, saying that the folder is empty until package 52 and that `TLAUP_TEST_JARS` comes with it; the code map names the test folders that exist (`tests/unit`, `tests/stateful`, `tests/fakes`, `tests/fixtures`) and those that arrive later (`tests/parse` with the parser, `tests/features` with the feature harness, `tests/recordings` with 05, `tests/integration` with 52, `tests/lifeline` with 06 if it has not merged yet). Add a short section on how tests are written now: the isolation fixture is automatic; the fakes and the `fakes` fixture; `--update-expected` and that every rewritten file is reviewed; the rules of [01 T12](../design/01-testing.md#t12-rules-for-writing-tests), linked, not copied; and that behaviour 0.8.x had is specified by the inventory, whose rows a package names when it writes their tests. Keep the guide's rule: say what was checked.

**What this package must not do.** It changes no file under `src/`. It writes no step definitions or feature files (package 18), no recordings and no `github` fixture (05), moves no golden file (07), and writes no test for an inventory row.

State of `main` when this starts: release 0.8.x code, formatted (01), with `errors.py`, `paths.py` and `context.py` (02). The old loader takes its two root folders from `AppPaths`. The suite has the old fixtures and writes to the developer's real config and cache folders; `tests/stateful` skips itself because `hypothesis` is not installed. Package 06 may already be merged.

## Done when

- The settings, dependencies and fixtures above are in place; every new test passes; the remaining suite passes in random order (three seeds, said in the pull request).
- `uv run poe lint`, `uv run ruff format --check .`, `uv run poe test` and `uv run poe test-clean` pass; `uv run pre-commit run --all-files` passes with the new hooks; CI is green, without Java or a jar in the job, and its clean-home step passes.
- No file under `tests/unit/` or `tests/integration/` is left from 0.8.x; `releases.json`, `tags.json` and `naming_dynamic/` are gone and `naming_fixed/` is there; `pytest-mock` is not in `pyproject.toml` or `uv.lock`; no test file imports `unittest.mock.patch` or uses `mocker`; the fake `java`'s log shows no start that a test did not script.
- The development guide is updated.
- The pull request of 03b gives the branch coverage figure after it (no threshold is set), the time the stateful folder adds to the run, and the deletion commit's file list.

## Out of scope

- The step vocabulary, `test_features.py`, the real-process and terminal helpers, and every step T5 names, the checkpoint wait included: package 18.
- `tests/recordings/github/`, the `github` fixture, `scripts/record_github.py`, the manifest move: package [05](05-github-recordings.md).
- Golden files, `cases.toml`, `facts.py`: packages 07 and 08.
- The new `tests/integration/` and its `isolated`, and the move of `naming_fixed/`: package 52. The CI matrix, `--locked`, `permissions`, pre-commit in CI: package 53. The other pre-commit changes of H1: package 57. The other lint rules of I8, and mypy on `tests/fakes/`: package 58 (write the fakes typed so that it can be switched on).
- The SIGQUIT edit of the signals machine (Q5): package 21.
- The tests of the inventory's rows: their owner packages. The closing check that every kept row has one, the final `fail_under` and the removal of `pending`: package 59.

## Risks

- From T2 and T4: the fake `java` can drift from the real one; the integration job (54) is the check. A field added to the fake needs the same kind of reason as a new step. This package adds five behaviours T4 does not state (marked "written by stage 4": the no-script answer of all four fakes, `{"text": ...}`, the hang guard, SIGHUP, `javac`'s `delay_ms`); each has its reason beside it.
- From T4 and T5: the `checkpoint` log line leaves one small window (under the fake's contract above); the remedy is in the fake, not the product.
- From T10: `filterwarnings = error` makes a new deprecation in any dependency fail the suite on the day it is released; the `ignore` line naming the exact message is the way out.
- From T11 and D62: from 03b until each inventory row's owner lands, nothing tests that row, and a package that edits old code before its owner rewrites it can break it unnoticed (the classpath, and the old `tlc` on the new store from 29 to 39). Accepted with D62; 59's check is where a dropped row shows.
- From the cut: coverage falls to almost nothing in 03b and climbs back as packages land. That is expected and gates nothing until 59.
- From the cut: the unit job grows by the stateful folder (two to three minutes in CI).
- From the cut: `pytest-randomly` may expose order dependence in the stateful tests that no one has seen; the fix is isolation in the fixture, never a fixed order.

## Pull requests (decided by stage 4)

This package is delivered as two pull requests, each reviewed on its own; the index lists them as 03a and 03b.

- **03a** (M): `tests/fakes/` with the four fakes, their launchers and `java-src/` and `classes/`; the `Fakes` API, `FakeClock` and `assert_matches` with `--update-expected`; `scripts/test_clean.py`; each with its own tests. It switches nothing on: the pytest settings, the dependencies and the isolation fixture stay as they are, so the old suite runs unchanged. The fakes' tests write the launchers into each test's own `tmp_path`. Depends on 01 and 02.
- **03b** (M): the pytest and coverage settings, the development dependencies, the autouse isolation fixture, the Hypothesis profiles moved to `tests/conftest.py`, the T12 checks, the deletion of the old suite and its fixtures and `pytest-mock` (one commit of its own), the removal of the Java and jar steps and the clean-home step in CI, the resource fixes of the stateful tests, the development guide. Depends on 03a. Large in files, small in judgement: the deletion is whole folders.

A package that names 03 as a dependency waits for 03b.
