# 03. Test foundation

Size: L. Suggested model: most capable. Status: ready, except one point that waits on question `pytest-mock-removal` of the index (the removal of `pytest-mock` and of the patch fixtures that stand for the network and TLC; the package is written with the recommended answer, marked where it applies).

## Goal

Every test runs isolated: its folders, home, working folder, terminal and `PATH` are temporary and fixed, sockets are blocked, and only fake `java`, `javac`, `git` and an editor can be started. The fakes, the expected-file helper and an injected clock exist for every later package. The pytest and coverage settings of the design are on, the new development dependencies are in, the first dead tests are gone, the kept old tests run under the isolation, and the mechanical checks of the test rules are in place. Nothing a user sees changes.

## Covers

- Roadmap items ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)):
  - "Isolation is automatic and total: every test runs with the tool's folders pointed at a temporary folder ..." (roadmap line 359). Closed here, apart from the clean-home check on every system of the unit matrix, which comes with the matrix (package 53).
  - "Unit tests cannot reach the network or start an unmocked subprocess; the 23 real subprocess starts in the unit suite (22 `java`, one `git`) go away." (line 360), in part: the processes and the socket block. The GitHub recordings and the `github` fixture are package [05](05-github-recordings.md).
  - "Coverage policy: branch coverage on; a `fail_under` near the current 83 percent; ..." (line 375), in part: everything except the final `fail_under`, which package 59 measures and sets.
  - "Unit job on Python 3.11 and the newest release ...; remove Java and the jar download from the unit job once the suite no longer needs them." (line 386), in part: the two steps go here, as [30 I2](../design/30-ci-and-release.md#i2-unit-job) says ("in the pull request that lands the isolation and the fakes"). The matrix is package 54.
  - "Design the testing approach from scratch ..." (line 351), in part: the mechanical checks of T12's rules 2, 3 and 10's prerequisites; the approach itself is carried by every later package.
  - "Pre-commit: move the test hook to pre-push; add a format hook; ..." (line 418), in part: the hook `no-typed-tool-output` that [30 H1](../design/30-ci-and-release.md#h1-pre-commit-hooks) names. The format hook was package [01](01-ruff-format.md); the rest is package 57.
  - "Snapshot tests through a fixed-width, colourless console with an injected clock ..." (milestone 1b, line 321), in part: the expected-file helper of T8. The reporter snapshots are package 38.
- Design sections:
  - [01 T1](../design/01-testing.md#t1-the-approach): the three edges as fixtures and fakes.
  - [01 T2](../design/01-testing.md#t2-isolation): all of it. The integration folder's own `isolated` (real `PATH`, the JVM's folders) is package 52; here that folder only keeps working as it does today.
  - [01 T4](../design/01-testing.md#t4-fakes-at-the-edges): "Processes" and "Time". "Network" is package 05, except the socket block and the closed-port address, which the isolation fixture sets here.
  - [01 T8](../design/01-testing.md#t8-expected-output-files): all of it.
  - [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings): all of it except the final `fail_under` and the removal of `pending` (package 59).
  - [01 T11](../design/01-testing.md#t11-the-existing-tests): the first list of deletions, bringing the kept files under the isolation, and the development guide. Every other row belongs to the package its "Until" names.
  - [01 T12](../design/01-testing.md#t12-rules-for-writing-tests): the mechanical checks of rules 2 and 3. Rule 10's check sits in the steps (package 18).
  - [30 I8](../design/30-ci-and-release.md#i8-lint-rules), the `TID251` row only. The other rows are package 58.
  - [30 B2](../design/30-ci-and-release.md#b2-build-fixes), the row "Development dependencies of 00" only. The other rows are package 56.

## Depends on

- [01](01-ruff-format.md): the formatted tree and the format check.
- [02](02-errors-and-paths.md): `AppPaths.from_env` and its derived folders (the isolation fixture returns one and its own test writes through every folder), `tlaup.context.reset()` (the fixture calls it; it also clears the old loader's cache), and the old loader's `config_dir()` and `cache_dir()` following `TLAUP_HOME`, which is what makes the old tests isolated without a patch.

## Files

This package is large. A reviewer should read, in this order: `pyproject.toml` (settings and dependencies), `tests/conftest.py` (the isolation fixture), `tests/fakes/java.py` with its tests, `.pre-commit-config.yaml`, then the table of old tests below, which is mechanical.

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
| `pyproject.toml` | The pytest and coverage blocks of T10, with the adjustments under Context; the development dependencies; `TID251` and its banned name; the poe tasks `test`, `test-clean`, `test-integration`. |
| `uv.lock` | From `uv lock` after the dependency change. |
| `tests/conftest.py` | Rewritten: the `isolated` fixture, the `fakes` fixture, the `--update-expected` option and the list of rewritten files at the end of a run, the Hypothesis profiles (moved from `tests/stateful/conftest.py`), and of the old fixtures only `runner`, `fixtures_dir` and `make_installed_version` (rewritten on the isolated cache). |
| `tests/stateful/test_run_folders.py`, `test_signals.py`, `test_tool_store.py`, `reference_*.py` | Resource handling only, so they pass under `filterwarnings = error` (see Context). No rule, precondition or invariant changes. |
| `tests/integration/conftest.py` | Receives the old fixtures its tests request (`base_settings`, `mock_cache`, `java_available`, `javac_available`) and an `isolated` fixture that does nothing, so the folder behaves exactly as today. Package 52 rewrites the folder. |
| The old unit tests | As the table "Old tests" below says. |
| `.pre-commit-config.yaml` | The local hooks `no-typed-tool-output`, `no-patching-own-code` and, under the recommended answer, `no-new-mocker` (below). |
| `.github/workflows/test.yml` | The steps "Set up Java" and "Download tla2tools.jar" go; a last step runs the clean-home check on the runner's home. |
| `.gitignore` | `.coverage.*`: with `parallel = true` coverage writes one data file per process, named with the host name, which must never be committed. |
| `docs/contributing/development.md` | Commands, code map and a short testing section (below). |

Deletes:

- `tests/stateful/conftest.py` (its profiles move to `tests/conftest.py`).
- The old tests of T11's first list (table below).

Shared with packages of the same period: `pyproject.toml` and `uv.lock` with [06](06-lifeline-agent.md), which can run beside 02 and 03 (its marker `lifeline`, its folder `tests/lifeline/` in `norecursedirs`, its poe tasks; a few lines each, and whichever merges second keeps both); `docs/contributing/development.md` with 02 (a different section). Later: `tests/conftest.py` gains the `github` fixture in 05; `.pre-commit-config.yaml` and `test.yml` are edited again by 57 and 54.

### Old tests

What happens to each old test file here ([01 T11](../design/01-testing.md#t11-the-existing-tests)). "Mechanical port" means: the parameters `mock_load_config` (a no-op), `mock_cache` and `base_settings` go, `mock_cache` becomes `isolated.paths.cache` (the old layout lives there: `paths.cache / "tools"`, never `paths.tools`, see 02), and `base_settings` becomes the settings the old loader reads from the isolated config folder (`load_config()`), or, where a test depends on a value that differs from the packaged file, that file written into `isolated.paths.config` with the one value changed. The old schema has required sections without defaults, so a hand-written partial file does not load.

Deleted (T11's first list; they test code that is deleted, or cannot fail):

| File or test | Items |
| --- | --- |
| `tests/unit/cmd/test_tlc_rich.py` | 2 |
| `tests/unit/tools/test_meta.py` | 2 |
| `tests/unit/tools/test_version_manager_url.py` | 4 |
| `tests/unit/version_manager/test_migration.py` | 3 |
| `tests/unit/version_manager/test_urls.py` | 9 (two parametrised functions) |
| `tests/unit/tlc/test_formatter.py`: `test_status_footer_component`, `test_display_composer`, and `StatusFooterComponent`, `TlcDisplayComposer` in its import list | 2 |
| `tests/unit/tools/test_uninstall.py::test_tlc_uninstall_default` | 1 |
| `tests/unit/test_config.py::test_save_config` | 1 |
| `tests/unit/version_manager/test_resolution.py::test_no_metadata_falls_back_to_mtime` (T11 keeps the ordering cases "with no modification times") | 1 |

"The legacy-folder tests in `tools/test_path.py`": the only legacy-folder content in that file is the line `(mock_cache / "tlc").mkdir(...)` at the top of `test_tlc_path_not_found` and `test_tlc_path_no_pinned`, which creates the old `tlc` folder before testing "not found" and "nothing pinned". Delete those two lines and keep the two tests, which then test what their names say; say so in the pull request (the index carries it as a clerical point).

Kept as plain unit tests and brought under the isolation (T11's second table, as far as it is this package's):

| File | Here | Until |
| --- | --- | --- |
| `tests/unit/spec/test_project.py` | Unchanged. | 32 (R10) |
| `tests/unit/java/test_classpath.py` | Mechanical port; `test_cached_modules_resolved` writes its two modules under `isolated.paths.cache / "modules"` instead of replacing `get_modules_dir`, so the file uses no `mocker`. Six of its seven tests read the real modules folder today; isolation ends that. | 33 (G1), which also merges `spec/test_classpath.py` and `test_tlc_modules_path.py` into it |
| `tests/unit/spec/test_classpath.py`, `tests/unit/test_tlc_modules_path.py` | Mechanical port only. They go through the old `tlc` command with `mock_tlc_env` (a replaced `Popen`), which stays under the recommended answer. | 33 |
| `tests/unit/tlc/test_values.py` | Unchanged. | 39 |
| `tests/unit/check_java/test_check_java.py` | All of it driven by the fake `java`: `test_get_java_version_success` with a script whose version is `11.0.2`; `test_get_java_version_not_found` with the launcher removed; the four `check-java` tests with versions `11.0.2` and `1.8.0_202` and with no `java`, and the minimum version written into the isolated config file. The file then has no `mocker`. These four tests asserted nothing they set: they replaced `tlaup.cli.load_config` and `tlaup.java.inspector.get_java_version`, which `check-java` does not look up, so they started the real `java`. T11 names only the first three tests; the other four are kept too, as the only tests of `check-java` until it goes. | 46 |
| `tests/unit/version_manager/test_resolution.py` | All but the deleted case, unchanged. | 29 |
| `tests/unit/version_manager/test_app_version.py` | Unchanged; it runs under the isolation and keeps its `mocker` lines. Package 49 rewrites it with the fake `git`. | 49 |
| `tests/unit/test_settings.py` | The two lines that delete `JAVA_OPTS` from `os.environ` go (rule 7); the fixture removes the variable already. | 33 (J1) |

The rest stay until the package that rewrites what they test (T11's "Become feature files", "Replaced by ..."), with the mechanical port and nothing else:

| Files | Until |
| --- | --- |
| `tests/unit/tools/*` with its `conftest.py` (`mock_github_api`, `mock_download`, `installed_v180` on the isolated cache) | 29 |
| `tests/unit/version_manager/test_download.py`, `test_local.py`, `test_metadata.py`, `test_remote.py` | 29 |
| `tests/unit/cmd/test_modules.py` | 31 |
| `tests/unit/spec/conftest.py` (`mock_tlc_env`), `spec/test_resolution_scenarios.py`, `cmd/test_tlc_cmd.py`, `test_tlc_show_command.py`, `tlc/test_raw.py`, `tlc/test_runner.py`, `tlc/test_run_cache.py`, `tlc/test_tlc_version.py`, `tlc/test_parser.py`, `tlc/test_sany.py` | 39 (32 moves the resolution cases first) |
| `tests/unit/tlc/test_formatter.py` (the 16 left) | 39 and 40 |
| `tests/unit/test_config.py` (three tests, after 02 and the deletion above) | 19 |
| `tests/unit/test_config_suite.py` | 44 |
| `tests/unit/test_cli.py` | 48 |
| `tests/integration/*` | 52 |

### What the real starts and the network become

Measured for this cut on 2026-11-21: the 207 collected items of `tests/unit`, run with logging stand-ins for `java`, `javac` and `git` on an otherwise empty `PATH`, a socket guard and an empty home folder, started `java` 20 times and `git` once, attempted no connection, and wrote `~/.config/tlaup/config.yaml` and four folders under `~/.cache/tlaup/run/tlc/`. The starts were:

- four `java -version` from the `check-java` tests (above): ported to the fake with a script;
- sixteen `java -cp tla2tools.jar tlc2.TLC -version` from `tools/test_install.py` (12), `test_pin.py` (2) and `test_upgrade.py` (2). `mock_download` replaces a name the command does not look up, so the real downloader runs on a `requests.get` that `mock_github_api` replaced, and `write_version_metadata` asks Java for the version. After this package these reach the fake `java`, which has no script in those tests and answers 127 with "fake java: no script"; the old code ignores the answer and records an empty version string, which no test asserts on. They go with the files in package 29;
- one `git rev-parse --short HEAD` from `test_cli.py::test_version_callback_exits`: it reaches the fake `git`, which also has no script there and answers 127; the old code then adds no commit suffix, which the test does not assert on.

No test reached the network, so none needs a change for `--disable-socket`; confirm it with the full run.

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

Package 18's Given and Then steps about Java, `javac`, `git` and the editor are written on this object.

**The fakes' contract.** Each fake reads its script from the file named by `TLAUP_FAKE_JAVA`, `TLAUP_FAKE_JAVAC`, `TLAUP_FAKE_GIT` or `TLAUP_FAKE_EDITOR` (T4 names the first and the last; the middle two follow the same pattern), or from the script baked into its launcher. With no script, every fake writes `fake <tool>: no script` to stderr and exits 127, so an unplanned start fails loudly (T4 says this of `java`; it is extended to the four, written by stage 4). Each writes the log of T4, one JSON line per event, flushed at once: `start` (process id, process group id where the system has one, the launcher's own path, the argument list, the working folder, the main class or `-version`, whether stdout is a pipe), `signal` (the name, also for a signal it ignores), `exit` (the code, on every way out the fake controls).

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
- **`version`, `version_delay_ms`**: the version request is answered on stderr, after the delay, with a banner in the real three-line form, for example `openjdk version "11.0.33" 2026-10-20`, `OpenJDK Runtime Environment Temurin-11.0.33+10 (build 11.0.33+10)`, `OpenJDK 64-Bit Server VM Temurin-11.0.33+10 (build 11.0.33+10, mixed mode)` (research 28 captured these three lines on a GitHub runner). It uses up no entry of `runs`. Written by stage 4, for [13 J3](../design/13-modules-and-java.md#j3-one-java-start)'s two rows that are not a version (packages 20 and 39): `version` may instead be an object `{"stderr": "<text>", "stdout": "<text>", "exit": <n>}`, printed as given, so that `Unable to locate a Java Runtime.` with exit 1 and an answer that is not a version can be scripted.
- **Which run answers.** A start of a main class takes the first entry of `runs` with that `main` that no earlier `start` line in the log has taken; the `start` line records the index it took. With none left, the fake exits 127 with `fake java: no script for <main>`. Written by stage 4: T4 says "the first entry that matches", and [T5](../design/01-testing.md#t5-feature-files-and-steps)'s scenarios with two runs of the same main class ("Two runs in one scenario") need each declared run used once. The main classes are `tlc2.TLC`, `tla2sany.SANY`, `pcal.trans` and `tlc2.REPL` alike.
- **`stdout`, `stderr`**: `null`; a file, given as a path relative to `tests/parse/golden/` (the golden files arrive with package 07) or as an absolute path (a file a test wrote itself, for example lines with the bytes `FF FE` for the launcher's decoding tests of package 21); or literal text, given as `{"text": "..."}` (written by stage 4: T4 allows "a golden file ... or literal text" in one field without saying how they are told apart). Bytes are written exactly as they are in the file. The `stderr` text is written whole before the `stdout` replay starts (the design does not fix an order; in `-tool` mode TLC writes almost nothing to stderr).
- **`generate_lines`**: instead of a replay, `line 1` to `line <n>` on stdout.
- **`exit`**, **`line_delay_ms`**, **`hang_after_line`**: as T4. Lines are counted on stdout. A hang waits for a signal; as a guard against a leaked process, a hang ends by itself after 120 seconds with an `exit` line and code 124 (written by stage 4; no test may rely on it).
- **`on_sigint`, `on_sigterm`**: a code, or `"ignore"`. Written by stage 4: SIGQUIT is logged and the fake runs on (the JVM prints a thread dump and runs on, [20 G3](../design/20-groundwork.md#g3-java-launcher)); SIGHUP is logged and the fake exits 129. A signal that is already ignored when the fake starts stays ignored and gets no handler, and the `start` line lists the signals that were ignored at start; [20 G3](../design/20-groundwork.md#g3-java-launcher)'s `nohup` rule is what the tests of packages 21 and 39 check through this. Signal code is guarded with `hasattr(signal, ...)` (D15).
- **`write_into_metadir`**, **`checkpoint`**: in a folder the fake makes under the folder given after `-metadir`, named as TLC names it (a timestamp such as `26-11-14-22-32-49`), as T4 says since the review finding TU5. `checkpoint` writes `queue.tmp` and `vars.tmp` after line `begin_after_line` and renames them to `queue.chkpt` and `vars.chkpt` after line `commit_after_line`. Either field without `-metadir` among the arguments is a script error: exit 127 with a message.
- **`echo_stdin`**: stdin to stdout line by line until it closes, then `exit`.
- **`replace`**: plain substitution in every replayed line, keys and values as UTF-8 bytes. The fake does not expand `{work}` or other placeholders; whoever writes the script does (package 18's steps).

The fake `javac` (T4: "copies prepared class files ... or prints a recorded compiler error and exits 1"):

```json
{"version": "25.0.5", "classes": "<repo>/tests/fakes/classes", "fail_with": null, "delay_ms": 0,
 "log": "<tmp>/javac.jsonl"}
```

- `-version` prints `javac <version>` on stdout and exits 0 (written by stage 4: T4 gives `javac` no version answer, and [13 M3](../design/13-modules-and-java.md#m3-module-build-details)'s version check, package 30, needs one; JDK 25 prints that line on stdout).
- A compile copies, for each source `X.java` among the arguments, every `X.class` and `X$*.class` under `classes` into the folder given after `-d`, keeping their path below `classes`; a source with no prepared class is `fake javac: no prepared class for X.java` and exit 2.
- `fail_with`: a file (absolute, or a name under `tests/fakes/javac-errors/`) printed to stderr, then exit 1. Recordings of real `javac` errors are added by the package that first needs one (31).
- `delay_ms`: wait before doing anything (written by stage 4, for [13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder)'s timeout test, package 30).

The fake `git`: `{"stdout": "abc1234\n", "exit": 0, "log": ...}`, defaults as shown: prints a fixed short hash. The fake `editor`: `{"write": "<text>" | null, "exit": 0, "log": ...}`: writes the text into the file named by its last argument, or leaves it alone, then exits.

**The expected-file helper**, `tests/expected.py`, from [01 T8](../design/01-testing.md#t8-expected-output-files):

```python
def assert_matches(actual: str, expected: Path, request: pytest.FixtureRequest) -> None
```

Compares after normalising line endings; on a mismatch fails with a unified diff; with `pytest --update-expected` writes the file instead (creating it and its folder if needed) and records it; a missing file without the option fails and names the option. At the end of a run with the option, the terminal summary lists every file it wrote (T8's only guard against a wrong change riding along). Expected files live beside the tests that use them, under `expected/`.

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

**Settings**, `pyproject.toml`, from [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings), with the adjustments explained under Context:

```toml
[tool.pytest.ini_options]
addopts = "--strict-markers --strict-config --disable-socket -p no:cacheprovider -m 'not pending'"
testpaths = ["tests"]
norecursedirs = ["tests/integration", "tests/fakes", "tests/fixtures", "tests/lifeline"]
filterwarnings = ["error"]
markers = [
    "integration: needs Java and real jars (TLAUP_TEST_JARS)",
    "pending: written before the code it tests (03); the work package that builds the code removes the marker",
    "lifeline: ...",   # package 06's line, kept as 06 wrote it
]

[tool.coverage.run]
branch = true
parallel = true
patch = ["subprocess"]
source = ["tlaup"]          # package 09 adds "tlaup_parse"

[tool.coverage.report]
fail_under = 80
show_missing = true
```

poe tasks: `test = "pytest --cov --cov-report=term-missing"`; `test-clean` runs `scripts/test_clean.py`; `test-integration` runs `pytest tests/integration --no-cov` (package 52 adds the `TLAUP_TEST_JARS` check and message).

Consumes: `AppPaths`, `tlaup.context.reset()` (02).

## Tests that must pass

Plain pytest, new:

- `tests/test_isolation.py` ([01 T2](../design/01-testing.md#t2-isolation), "Tests"): one test writes a file through every folder of `AppPaths` (`config`, `cache`, `data` and the seven derived paths) and asserts each is under `tmp_path`; the pair of tests on `TLAUP_LEAK_CHECK`, each asserting it is absent and then setting it with `os.environ` directly (the one deliberate break of rule 7), so whichever runs second fails if the fixture did not clean up. Also: `PATH` holds only `bin`; `shutil.which` finds exactly the four fakes there; `HOME` and the working folder are under `tmp_path`.
- `tests/unit/test_fakes.py`: each launcher started as a real child with `subprocess.run` from an argument list. For `java`: no script gives 127; the version banner and its delay; a version object; main class found behind `-javaagent:x=pid=1`, three `-D` options and `-cp a b`; a replay from an absolute path reproduces the file byte for byte, including invalid UTF-8; `{"text": ...}` on each stream; `generate_lines`; `exit`; two declared runs of one main class answer two starts in order and a third gets 127; `replace`; `echo_stdin`; `write_into_metadir` and `checkpoint` (the `.tmp` files, then the `.chkpt` files, in the timestamped folder); `hang_after_line` with a signal from the test, waited for through the log, never by sleeping: SIGTERM gives `on_sigterm`, `"ignore"` keeps it running and logs the signal, SIGQUIT is logged and does not end it; a signal ignored at start stays ignored; the `start` line's fields, including the pipe flag both ways. For `javac`: `-version`; a compile that copies `Plain.class`; a missing class; `fail_with`. For `git` and `editor`: the default answer, the logged arguments, the editor's write and exit code. For `Fakes`: `remove`, `not_executable` (then `shutil.which` finds nothing), and a `jdk` folder whose `java` logs its own path. The signal tests are skipped on Windows with the reason.
- `tests/unit/test_expected.py`: a match passes; a mismatch fails with a diff; `\r\n` against `\n` matches; with the option a file is written and listed in the summary; a missing file fails naming the option. Drive the option through pytest itself (pytest's `pytester` plugin, or a child `pytest` in `tmp_path`).
- `tests/unit/test_clock.py`: `sleep` records and advances; `now()` is aware UTC and moves with `advance`.

Old tests: as the tables under Files say. Every old test that is not deleted passes, under the isolation and with the settings above, in random order: run the suite at least three times with different seeds of `pytest-randomly` and say in the pull request that it passed each time.

Stateful tests: with `hypothesis` installed, the reference-model tests of `tests/stateful/` (the `..._reference_model` tests and the plain tests without `pending`) start running in the default suite; they must pass under `filterwarnings = error` (see Context). The `pending` tests stay deselected; their packages (21, 23, 35) remove the markers.

Mechanical checks that must hold on the branch:

- `uv run ruff check .` with `TID251` on and `unittest.mock.patch` banned.
- `uv run pre-commit run --all-files` with the new hooks.
- `uv run poe test-clean` passes.
- CI's clean-home step passes.

## Changelog

None. Nothing a user sees changes.

## Context for the worker

Decisions this rests on: D16 (the test approach was designed first), D33 (feature files later, plain pytest here), D25 (one variable moves every folder, so isolation needs no patch), D15 (no Windows CI, but `.cmd` launchers, `pathlib`, `hasattr(signal, ...)`), D6 (one release; `main` stays green between packages).

**The question `pytest-mock-removal` and what this package does under the recommended answer.** [01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 2 says `pytest-mock` is removed, and [01 T2](../design/01-testing.md#t2-isolation) lists among the removed fixtures "the three sub-folder conftests' patch lists". [01 T11](../design/01-testing.md#t11-the-existing-tests) says a test file is deleted in the same pull request that rewrites what it tests, never earlier. About twenty old files that stay until the switch packages use `mocker`, and `mock_github_api`, `mock_download` and `mock_tlc_env` stand for GitHub and for TLC's output, which only the recordings (05) and the golden files (07) can replace. Both rules cannot hold in this package. Recommended answer, used here:

- Removed now, because the isolation makes them unnecessary: `mock_load_config`, `mock_cache`, `base_settings`, `java_available`, `javac_available` from `tests/conftest.py` (the last two move to `tests/integration/conftest.py`, the only folder that uses them, with `base_settings` and `mock_cache`).
- Kept until the files that use them go: `pytest-mock` itself, `mocker` in the files of the tables above, and the fixtures `mock_github_api`, `mock_download` (tools conftest) and `mock_tlc_env` (spec conftest), each rewritten on the isolated folders.
- A local pre-commit hook `no-new-mocker` (pygrep `\bmocker\b`, files `^tests/.*\.py$`) whose `exclude` lists exactly the old files that may still use it, one per line, so the list can only shrink. Each package that deletes or rewrites one of them removes its line; the package that removes the last line also removes `pytest-mock` from the development dependencies and the hook (by today's cut, the later of 49 and 52).
- `TID251` bans `unittest.mock.patch` from the start; no old file imports it (checked: `ruff check` with the ban passes on today's tree). `from unittest.mock import MagicMock` in old files is not banned.

The other answer is to port every old test that uses `mocker` in this package: the tools and `tlc` tests would need the recordings and the golden files of later packages, so it cannot be done here without moving 05 and 07 before 03.

**The mechanical checks** (rules 2 and 3), local pygrep hooks in `.pre-commit-config.yaml`, which package 53 then runs in CI:

- `no-patching-own-code`: `monkeypatch\.(setattr|setitem|delattr)\b` in `^tests/.*\.py$`, excluding every `conftest.py` and `tests/fixtures/research/`. Today no test file has one (checked).
- `no-typed-tool-output` (the name [30 H1](../design/30-ci-and-release.md#h1-pre-commit-hooks) gives): `@!@!@STARTMSG` in `^tests/.*\.(py|feature)$`. Its `exclude` names, each with a comment: `tests/fixtures/research/` (evidence; two scripts there hold the marker), and `tests/unit/tlc/test_parser.py`, which holds typed marker text and tests the old parser until package 39 deletes both. Rule 3's other exceptions (`synthetic/`, the Hypothesis printer and strategies) are a later package's to add, by exact path with a comment, when it writes such a file (package 10's framing strategies). Do not dodge the check by splitting the marker in a string.
- `TID251` in `[tool.ruff.lint]` `select`, with `[tool.ruff.lint.flake8-tidy-imports.banned-api] "unittest.mock.patch".msg = "..."` naming rule 2. It applies to `src/` too, where nothing uses the name. Try whether `patch.object` and `patch.dict` through `from unittest import mock` are caught; if not, ban them by name as well and say so.

**Why the settings differ from T10's block in three places.**

- `norecursedirs` also names `tests/lifeline`: package [06](06-lifeline-agent.md) keeps its lifeline tests out of the default run there, with the marker `lifeline` and the task `poe test-lifeline`. Whichever of 03 and 06 merges second keeps both the folder and the marker line; `--strict-markers` makes a forgotten marker fail.
- `source = ["tlaup"]`, not `["tlaup", "tlaup_parse"]`: `tlaup_parse` does not exist until package 09. Tried for this cut (pytest-cov 7.1.0, coverage 7.17.3, 2026-11-21): naming a package that is never imported makes coverage print `CoverageWarning: Module tlaup_parse was never imported. (module-not-imported)` at the end of the run, and the run does not fail under `filterwarnings = error`, because the warning comes after the tests. It would be noise on every run until 09, so 09 adds the name (its file says so).
- The `pending` marker's line says "(03)" in T10 and means design 03; keep T10's text.

**What `filterwarnings = error` does to `tests/stateful`.** `hypothesis` becomes a development dependency here, and `filelock` is already in `uv.lock` (through `pre-commit` and `virtualenv`; package 23 makes it a runtime dependency), so the files stop skipping themselves and their reference-model tests run in the default suite from this package on. Tried for this cut: all of them pass without `-W error`; with it, six fail on `ResourceWarning` (pipes of child processes left open, and `Popen` objects collected while their child still runs), in `test_signals.py` (the machine, the three `test_child_ends_with_tlaup_reference_model` cases, `test_without_the_lifeline_the_child_runs_on_reference_model`) and `test_tool_store.py` (the machine). The fix is in those files and the reference models: wait for every child they start and close its pipes, in a `finally` or the machine's teardown. It is resource hygiene, not a change to what a machine checks; a `filterwarnings` `ignore` line is not the fix (T10 allows those only for third-party warnings that cannot be fixed). The folder took 2 minutes 43 seconds on the machine that tried it with the development profile; in CI, where `CI` is set and the `ci` profile runs 200 examples, expect the unit job to grow by two to three minutes.

**The Hypothesis profiles** move from `tests/stateful/conftest.py` to `tests/conftest.py` unchanged (`ci`: `derandomize=True`, 200 examples, `deadline=None`, no example database; `dev`: 50 examples; `ci` when `CI` is set), so that `tests/parse/` (packages 10 and 11) gets them too. The `try`/`except ImportError` can go now that the library is installed.

**Development dependencies** ([30 B2](../design/30-ci-and-release.md#b2-build-fixes), [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings); research 30 ran the first five as the design uses them):

- `pytest-bdd>=9.0.1,<10` (the only version that runs on the locked pytest 9.2; it reaches into pytest's private fixture manager).
- `coverage>=7.10.6` (the subprocess patch; pytest-cov 7.1.0 needs it). Locked today: 7.17.3.
- `responses>=0.23.3,<1`, `pytest-socket>=0.8.1,<1`, `pyte>=0.8.2,<1`.
- `hypothesis` and `pytest-randomly`: the design gives no bounds. Use the file's convention, the version that `uv` locks as the floor and the next major as the cap, and say so in the pull request. `pytest-randomly` was not run by anyone for the design.
- `pytest-mock` stays under the recommended answer (above).

All six new ones are added here, although only `hypothesis` and `pytest-socket` are used at once, so that `pyproject.toml` and the lock change once for the whole test design.

**The isolation fixture, points that are easy to miss.**

- `PATH` holds only `bin`. A test may still start `sys.executable` by its absolute path; the stateful tests and the fakes' own tests do.
- `TLAUP_TOOL_REPOSITORY` points at a closed port. Nothing reads it until package 19 (the old code reads `tla.urls` from its config); from then on every test that passes the real environment sees it as a source.
- With 02, `tlaup.context.reset()` also clears the old loader's `lru_cache`. That is what makes the old tests independent of order; without it, `pytest-randomly` would show the leak T2 describes.
- `tmp_path` now holds `home`, `work` and `bin`. An old test that makes its own folder of one of those names under `tmp_path` collides; check by search.
- The launchers' first line names `sys.executable`. A very long interpreter path can pass the kernel's limit for a `#!` line (it was 127 bytes on old Linux kernels, 255 since 5.1); if it does, write the launcher as `#!/bin/sh` and an `exec` line, and say so.
- `coverage`'s subprocess patch also starts in the fakes' Python processes; research 30 found that a file outside `source` is not measured and that its stderr stays empty. The fakes must stay quiet on stderr unless scripted, because tests compare streams.

**The clean-home check** ([01 T2](../design/01-testing.md#t2-isolation), "Proof that it holds"; [30 I2](../design/30-ci-and-release.md#i2-unit-job)). `scripts/test_clean.py` makes an empty temporary folder, runs `sys.executable -m pytest` with `HOME` and `USERPROFILE` set to it and the `XDG_*` variables removed, then lists everything in it and fails if a tlaup folder (`.config/tlaup`, `.cache/tlaup`, `.local/share/tlaup`, `Library/Application Support/tlaup`, `Library/Caches/tlaup`) or `.tlaplus` is there. Written in Python, not shell, so it runs on every system. The same check without the run is the last step of the test job, on the runner's real home, after `uv run poe test`; the two Java and jar steps must go in the same pull request, because the jar step installs into the runner's home and would make the check fail.

**The development guide** ([01 T11](../design/01-testing.md#t11-the-existing-tests), last paragraph). In `docs/contributing/development.md`: the commands list gains `uv run poe test-clean` and replaces `uv run pytest tests/integration` with `uv run poe test-integration`, saying that until package 52 the folder holds the old integration tests (Java and an installed jar, not run by CI) and that `TLAUP_TEST_JARS` comes with 52; the code map names the test folders that exist (`tests/unit`, `tests/stateful`, `tests/fakes`, `tests/fixtures`, `tests/integration`) and those that arrive later (`tests/parse` with the parser, `tests/features` with the feature harness, `tests/recordings` with 05). Add a short section on how tests are written now: the isolation fixture is automatic; the fakes and the `fakes` fixture; `--update-expected` and that every rewritten file is reviewed; the rules of [01 T12](../design/01-testing.md#t12-rules-for-writing-tests), linked, not copied. Keep the guide's rule: say what was checked.

**What this package must not do.** It changes no file under `src/`. It writes no step definitions or feature files (package 18), no recordings and no `github` fixture (05), and moves no golden file (07).

**Proposed split, if the reviewer finds one pull request too large** (the stage 4 index decides): 03a adds `tests/fakes/`, `tests/expected.py`, `tests/clock.py` and their tests, with the launchers written in each test's own `tmp_path`, and switches nothing on; 03b turns on the settings, the dependencies, the isolation fixture and the checks, and does the deletions and the ports. 03a first; 03b depends on it.

State of `main` when this starts: release 0.8.x code, formatted (01), with `errors.py`, `paths.py` and `context.py` (02). The old loader takes its two root folders from `AppPaths`. The suite has the old fixtures and writes to the developer's real config and cache folders; `tests/stateful` skips itself because `hypothesis` is not installed. Package 06 may already be merged.

## Done when

- The settings, dependencies and fixtures above are in place; every new test passes; the old tests that stay pass in random order (three seeds, said in the pull request).
- `uv run poe lint`, `uv run ruff format --check .`, `uv run poe test` (coverage with `fail_under = 80`) and `uv run poe test-clean` pass; `uv run pre-commit run --all-files` passes with the new hooks; CI is green, without Java or a jar in the job, and its clean-home step passes.
- No test file outside the `no-new-mocker` list uses `mocker`; no test file imports `unittest.mock.patch`; the fake `java`'s log shows no start that a test did not script, apart from the sixteen old tools starts named above.
- The development guide is updated.
- The pull request gives the branch coverage figure before and after, the time the stateful folder adds to the run, and the list of old tests deleted and changed.

## Out of scope

- The step vocabulary, `test_features.py`, the real-process and terminal helpers: package 18.
- `tests/recordings/github/`, the `github` fixture, `scripts/record_github.py`, the manifest move: package [05](05-github-recordings.md).
- Golden files, `cases.toml`, `facts.py`: packages 07 and 08.
- The integration tests' rewrite and their `isolated`: package 52. The CI matrix, `--locked`, `permissions`, pre-commit in CI: package 54. The other pre-commit changes of H1: package 57. The other lint rules of I8, and mypy on `tests/fakes/`: package 58 (write the fakes typed so that it can be switched on).
- The final `fail_under` and the removal of `pending`: package 59.
- Every old test that T11 gives to a later package.

## Risks

- From T2 and T4: the fake `java` can drift from the real one; the integration job (54) is the check. A field added to the fake needs the same kind of reason as a new step. This package adds six behaviours T4 does not state (marked "written by stage 4"); each has its reason beside it.
- From T10: `filterwarnings = error` makes a new deprecation in any dependency fail the suite on the day it is released; the `ignore` line naming the exact message is the way out.
- From the cut: coverage. Measured for this cut on 2026-11-21 with branch coverage on: about 83 percent for today's suite, about 81 percent after this package's deletions with no new test. The new modules of 02 are well covered, and the fakes and helpers are outside `source`, so the figure should stay above 80. If it does not, do not lower `fail_under` and do not add tests of old code to lift it; stop and report the figure.
- From the cut: the unit job grows by the stateful folder (two to three minutes in CI).
- From the cut: the question `pytest-mock-removal`; with the recommended answer the dependency lives on until the last old test that uses it is deleted, and the hook keeps the number of such files from growing.
- From the cut: `pytest-randomly` may expose order dependence in old tests that no one has seen; the fix is isolation in the fixture, never a fixed order.

## Pull requests (decided by stage 4)

This package is delivered as two pull requests, each reviewed on its own; the index lists them as 03a and 03b.

- **03a** (M): `tests/fakes/` with the four fakes, their launchers and `java-src/` and `classes/`; the `Fakes` API, `FakeClock` and `assert_matches` with `--update-expected`; `scripts/test_clean.py`; each with its own tests. It switches nothing on: the pytest settings, the dependencies and the isolation fixture stay as they are, so the old suite runs unchanged. Depends on 01 and 02.
- **03b** (M to L): the pytest and coverage settings, the development dependencies, the autouse isolation fixture, the Hypothesis profiles moved to `tests/conftest.py`, the T12 checks, the first deletions and ports of T11, the resource fixes of the stateful tests, the development guide. Depends on 03a.

A package that names 03 as a dependency waits for 03b.
