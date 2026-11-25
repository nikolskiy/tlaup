# 18. The feature harness: steps, processes, terminals and the first scenarios

Size: L as a whole, delivered as two pull requests of size M each (18a and 18b, see the end of this file). Suggested model: most capable. Status: ready.

## Goal

`tests/test_features.py` collects every `.feature` file under `tests/features/`; the step vocabulary of [01 T5](../design/01-testing.md#t5-feature-files-and-steps) exists in `tests/steps/` for every step that needs nothing built after this package, with the in-process runner, the real-process runner (pipes, closed pipes, signals, the foreground group) and the terminal runner (a pty read through `pyte`); each step of T5 has one named owner; and `errors.feature` holds the scenarios that today's commands can already show.

## Covers

- Roadmap items:
  - "The `tlaup tlc` command path is tested end to end: exit codes, raw mode, missing Java and Ctrl-C. ..." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this), line 364), in part: the harness and the steps the `tlc` features are written in. The `tlc` features themselves are [39](39-tlc-command.md).
- Design sections:
  - [01 T5](../design/01-testing.md#t5-feature-files-and-steps): the layout (`tests/features/`, `tests/steps/given.py`, `when.py`, `then.py`, `tests/test_features.py`), how a command is run (in-process, real process, terminal), the notes on the steps, "Prompts have one mechanism" as far as the steps reach it, the placeholders. The steps listed as owned by later packages in the table under Interfaces are not built here.
  - [01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 10: the two refusals of the in-process step (passthrough, startup-only variables), mechanically, in the steps.
  - [01 T2](../design/01-testing.md#t2-isolation): "The environment the fixture builds is also the environment of every real process a step starts", and the terminal steps' own `TERM`, window size and removal of `COLUMNS` and `LINES`.
  - [01 T8](../design/01-testing.md#t8-expected-output-files): the `matches the expected file` steps, on [03](03-test-foundation.md)'s `assert_matches`.
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes), Tests, in part: the scenarios of `errors.feature` that need no later command (listed under Tests), taken from [17](17-error-handler.md)'s list. The rest wait for the packages named in the table "Where the other X1 and G2 scenarios go".
  - [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks), Tests, in part: the feature scenarios 17 left to the harness (17, "What the step vocabulary's packages must add", first bullet).
  - [22 O4](../design/22-reporters.md#o4-live-display), in part: the terminal emulator the terminal steps feed (`pyte`). The layout steps are [40](40-live-display.md).

## Depends on

- [17](17-error-handler.md): `tlaup.cli.app` (the in-process runner calls it), `python -m tlaup` (`src/tlaup/__main__.py`, which the real-process runner starts), the error mapping inside the root group (so in-process runs show D29's codes), `build_context` (a fresh context per run of the app).
- [16](16-ui-messages.md): `Ui.for_process()`, which a run under `CliRunner` builds on `CliRunner`'s streams, so each in-process run prints into its own captured output.
- [03](03-test-foundation.md): the `isolated` fixture and its environment; the `fakes` fixture (`Fakes.script`, `log`, `remove`, `not_executable`, `jdk`) and the four fakes' contract; `assert_matches` and `--update-expected`; `pytest-bdd`, `pyte` and the other development dependencies; coverage of child processes ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)).
- [07](07-golden-files.md): the golden specs and captures under `tests/parse/golden/`, with their `cases.toml` (the `stderr` key names a case's `.err` file), which `a spec ... from the golden specs` and `java replays ...` read.
- [02](02-errors-and-paths.md): `AppPaths` (`tools`, `modules`, `runs`, `config`), `tlaup.context.reset()`.

Change from the draft (17): 16, 03, 07 and 02 are named because the steps use them directly; none changes the order. [05](05-github-recordings.md) is not a dependency: the GitHub steps are [29](29-tool-commands.md)'s (see the ownership table).

## Files

Creates:

- `tests/test_features.py`: `scenarios("features")`, nothing else ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings): no `bdd_features_base_dir`; the path is relative to the test file's folder).
- `tests/steps/__init__.py`, `tests/steps/given.py`, `tests/steps/when.py`, `tests/steps/then.py`: the step definitions this package owns. Each is a thin wrapper over the helpers below, so the helpers can be unit-tested without a feature file.
- `tests/steps/_scenario.py`: `Scenario` (the state one scenario carries between its steps), the placeholder expansion, `STARTUP_ONLY` (T12 rule 10's list).
- `tests/steps/_process.py`: the real-process runner.
- `tests/steps/_terminal.py`: the terminal runner and the screen helpers.
- `tests/features/errors.feature`: the scenarios under Tests.
- `tests/features/expected/`: the folder where `matches the expected file "<name>"` looks (created with the first expected file; [29](29-tool-commands.md), [39](39-tlc-command.md) and [44](44-config-commands.md) put theirs there).
- `tests/unit/test_harness.py`: the plain pytest tests of the helpers and of the steps no scenario of this package uses (Tests).

Changes:

- `tests/conftest.py`: the step modules are made visible to the scenarios, either by `pytest_plugins = ["tests.steps.given", "tests.steps.when", "tests.steps.then"]` or by importing them in `tests/test_features.py`; one of the two, the worker's choice, said in the pull request. The `scenario` fixture (below) is defined there or in `tests/steps/_scenario.py`.
- `docs/contributing/development.md`: a short part of the testing section ([03](03-test-foundation.md) wrote it): where feature files and steps live; that the vocabulary is closed and a new step needs a reason in the pull request (T5); in-process unless one of T5's five situations applies (T12 rule 10); how to read a failing real-process or terminal scenario (the step prints the process's output and, for a terminal, the last screen).

Deletes: nothing. The old suite is gone already: 03b deleted `tests/unit/` and `tests/integration/` as they were ([01 T11](../design/01-testing.md#t11-the-existing-tests), decision D62). No row of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) names this package as its owner.

Shared with later packages: `tests/steps/given.py` and `then.py` (29, 31, 39, 40, 43 add their own step functions, listed below; none edits this package's), `tests/features/errors.feature` (every command package adds one block of scenarios; 29 also changes `tools` to `tool` in two of this package's scenarios, see Context), `tests/steps/_scenario.py` (29 registers a hook in it, below). Each conflict is a few lines.

## Interfaces

Everything here is test code, written by stage 4 from T5's words where T5 gives no form; a worker may adjust a name or a parameter if the behaviour and the tests stay, and says so in the pull request.

### The scenario state

```python
# tests/steps/_scenario.py
STARTUP_ONLY: Callable[[str], bool]     # True for any name starting with "PYTHON", and for LC_ALL, LC_CTYPE, LANG (T12 rule 10)

@dataclass
class Outcome:                          # what the last When step left
    exit_code: int                      # as a shell reports it: a process ended by signal s is 128 + s
    stdout: str | None                  # None: the stream could not be read (a closed pipe, the null device)
    stderr: str | None
    terminal: bytes | None              # everything read from the pty, for the terminal steps
    terminal_size: tuple[int, int] | None
    pid: int | None                     # tlaup's process id (real processes only)
    pgid: int | None                    # tlaup's process group (real processes only; 39's group steps compare with it)

class Scenario:
    isolated: Isolated                  # from 03
    fakes: Fakes                        # from 03
    env_set: dict[str, str]             # what "the environment variable ..." set, for rule 10's second check
    config_written: bytes | None        # what "the config file contains:" wrote, for "the config file is unchanged"
    java_runs: list[dict]               # the declared runs of the fake java, in order; written to its script on change
    outcome: Outcome | None
    before_run: list[Callable[[], None]]    # called by every When step before it runs tlaup (29: github.clear)
    def expand(self, text: str) -> str      # the placeholders below
    def words(self, command: str) -> list[str]   # shlex.split, then expand each word; the first word must be "tlaup"

@pytest.fixture
def scenario(isolated, fakes) -> Scenario
```

**Placeholders.** `{home}` is the isolation fixture's home; `{work}` its working folder; `{tools}`, `{modules}`, `{runs}` and `{config}` are `AppPaths.tools`, `modules`, `runs` and `config` (the folder; the file is `{config}/config.yaml`); `{kept}` is the one folder under `{runs}` whose `run.json` holds `"kept": true` at the moment the step runs, and with none or more than one the step fails and says which. Only these seven names in braces are replaced here; T5's eighth, `{kept-id}` (the last part of `{kept}`, the run id alone, for `cache clean <run-id>`), is added to the same expansion by [45](45-cache-commands.md), its first user; any other brace is left alone, so a YAML flow mapping in a doc string survives. Placeholders are expanded in every quoted argument of a step and in doc strings. A command is split with `shlex.split` first and each word expanded after, so a path with a space stays one word. Run ids are random; `{kept}` (and 45's `{kept-id}`) are the only ways a scenario names a run folder (T5).

### When: in-process

`I run "<command>"`:

1. Fails at once, naming `as a process`, if `env_set` holds a name for which `STARTUP_ONLY` is true (T12 rule 10, second check).
2. Calls each `before_run` hook; remembers how many lines the fake `java`'s log has.
3. `tlaup.context.reset()`, then `CliRunner().invoke(tlaup.cli.app, words[1:])`. No `env=` (it would assign to `os.environ`, T12 rule 7); the environment is the one `monkeypatch` built. No `input`: stdin is empty, so nothing is ever answered in-process.
4. If `result.exception` is set and is not a `SystemExit`, fails with its traceback: with the mapping inside the app ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)) that can only be a fault of the harness or of the mapping, never a scenario's result.
5. Reads the fake `java`'s log from the remembered line on: a `start` line whose stdout was not a pipe means the command reached `run_passthrough`, and the scenario fails with "this command passes the terminal through; use `as a process`" (T12 rule 10, first check; it holds under pytest's default capture, where tlaup's stdout is a temporary file, T12).
6. Stores `Outcome(exit_code=result.exit_code, stdout=result.stdout, stderr=result.stderr, ...)`.

### When: a real process

```python
# tests/steps/_process.py
def start(argv: Sequence[str], *, stdin, stdout, stderr, new_group: bool = False,
          reset_sigint: bool = True, env: Mapping[str, str] | None = None) -> subprocess.Popen
    # argv is [sys.executable, "-m", "tlaup", *words[1:]] for the steps; the unit tests pass small programs.
    # env defaults to a copy of os.environ as it is now (the isolation fixture's, T2).
    # reset_sigint: SIGINT set back to SIG_DFL in the child before exec (T5, research 23's rule), through
    #   preexec_fn; new_group: os.setpgid(0, 0) in the same preexec_fn. Test code only: the rule against
    #   preexec_fn is the launcher's (20 G3).
def closed_pipe() -> int                    # os.pipe(), the read end closed at once; returns the write end
def exit_code_of(returncode: int) -> int    # a negative return code -s becomes 128 + s
def wait_for_log(fakes: Fakes, tool: str, predicate, *, after: int, timeout: float = 10.0) -> dict
    # polls the fake's log for a line, from line `after` on, that satisfies predicate; fails with the log so far
```

The steps, each starting `start(...)` and storing an `Outcome` with `pid` and `pgid`:

| Step | Arrangement |
| --- | --- |
| `I run "<command>" as a process` | stdin the null device; stdout and stderr captured (temporary files, so a large output cannot deadlock). |
| `... as a process with input:` (doc string) | stdin a pipe: the doc string is written, then the pipe is closed. |
| `... as a process whose reader closes after <n> line(s)` | stdout a pipe: the step reads `n` lines, then closes its end; stderr captured; then waits. For output far larger than a pipe's buffer (T5: the one case where the reader certainly closes first). |
| `... as a process with stdout on a closed pipe` | stdout `closed_pipe()`: the read end is closed before the process starts, so the first write fails whatever the size and timing (T5, research 23's first rule). `Outcome.stdout` is `None`. |
| `... with stdout and stderr on a closed pipe` | Both on one closed pipe; both `None`. |
| `... with stdout on the null device and stderr on a closed pipe` | stdout `os.devnull`, stderr `closed_pipe()`; both `None`. |
| `I start "<command>" and send <signal> once java is running` | stdin a pipe held open until the process has ended (T5, "Stdin of the real-process steps"); waits with `wait_for_log` for a `start` line whose main class is a tool's (not `-version`, T5); sends the signal to tlaup alone (`os.kill`). |
| `I start "<command>" and send <signal> twice` | As above; after the first signal waits for a `signal` line of the fake's own (tlaup has passed it on), then sends the second. Used with `java ignores <signal>` (T5). |
| `I start "<command>" and send <signal> once java has begun its checkpoint` | As `once java is running`, but waits with `wait_for_log` for the fake's `checkpoint` line ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)), which it writes once the 2195 line is flushed and the `.tmp` files exist; then sends the signal. The one way to place a signal between 2195 and 2196 (question Q10, settled). |
| the same, ending `, and again once stderr contains "<text>"` | After the first signal, waits until the captured stderr file holds the text (tlaup has printed the waiting line, so the first signal was held), then sends the second. |
| each `send` form `... to the foreground group` | Started with `new_group=True`; the signals go to the group (`os.killpg`), as Ctrl-C in a terminal does. |

Every real-process step waits for the process with a timeout of 60 seconds, then kills it and fails with what it printed. The pipe the `I start` steps hold is closed after the process has exited. `<signal>` is `SIGINT`, `SIGTERM` or `SIGHUP` (and `SIGQUIT` for 39's `Ctrl-\` form); on a platform without the signal, or on Windows, the step skips the scenario with the reason (D15).

### When: on a terminal

```python
# tests/steps/_terminal.py
ENTER_ALT = b"\x1b[?1049h"; LEAVE_ALT = b"\x1b[?1049l"   # the alternate screen; 40's steps use them too
@dataclass
class TerminalRun:
    process: subprocess.Popen
    master: int                                     # the pty's master end
    output: bytearray                               # everything read so far
    def feed_until(self, text: str, *, timeout: float = 10.0) -> pyte.Screen
        # reads the master, feeds a pyte.ByteStream on a Screen of the pty's size, and returns when the
        # screen shows `text`; fails with the last screen it saw
    def type(self, text: str) -> None               # writes to the master
    def finish(self, *, timeout: float = 60.0) -> Outcome   # reads to end of output (EIO on Linux), waits
def run_on_terminal(argv, *, size: tuple[int, int], redirect: dict[str, Path] = {}) -> TerminalRun
    # os.openpty(), window size set with TIOCSWINSZ; the child is the leader of a new session with the pty
    # as its controlling terminal (setsid and TIOCSCTTY in preexec_fn, with the SIGINT reset); stdin and
    # both streams on the pty unless redirected to a file; TERM=xterm-256color; COLUMNS and LINES removed (T2)
def screen_text(data: bytes, size: tuple[int, int]) -> str
    # the bytes replayed through pyte (a HistoryScreen, so lines that scrolled off count), each line with
    # trailing spaces removed, trailing empty lines dropped
```

| Step | What it does |
| --- | --- |
| `I run "<command>" in a terminal <w> by <h>` | `run_on_terminal`, then `finish`. |
| the same `with <stream> redirected to "<file>"` | That stream goes to the file (`stdout` or `stderr`); the other and stdin stay on the pty. |
| the same `and answer "<text>"` | The answers, split at commas and stripped, are typed into the pty, each followed by a newline, before the step waits (see Context, "Typing the answers"). |
| `I start "<command>" in a terminal <w> by <h> and press Ctrl-C once the terminal has shown "<a>" and then "<b>"` | `feed_until(a)`, then `feed_until(b)`, then types the interrupt character (`\x03`), so the terminal itself sends SIGINT to the foreground group, tlaup and the fake `java` alike (T5); then `finish`. |
| `I start "<command>" in a terminal <w> by <h> and press Ctrl-C once java has begun its checkpoint` | `run_on_terminal`; reads the master meanwhile (so the child never blocks on a full pty) until `wait_for_log` sees the fake's `checkpoint` line; then types `\x03` and `finish`. D60's terminal scenario ([20 G3](../design/20-groundwork.md#g3-java-launcher), [39](39-tlc-command.md)). |

On a terminal both streams are the pty, so for the result steps a stream that is on the pty reads as the terminal's output with escape sequences removed (`screen_text` of all bytes), and a stream that was redirected reads as its file. That is what lets a terminal scenario say `stderr contains "<question>" 3 times` ([29](29-tool-commands.md)). On a platform without `pty` (Windows) the steps skip the scenario with the reason (T5).

### Then: what this package's steps assert

- **Result.** `the exit code is <n>`; `<stream> contains "<text>"`, `... "<text>" <n> times` (occurrences that do not overlap, `str.count`), `does not contain`, `is exactly "<text>"` (equal after one trailing newline is removed from the stream), `is empty`, `matches the expected file "<name>"` (`assert_matches` against `tests/features/expected/<name>`). A step on a stream that could not be read (`None`) fails and says the stream was a closed pipe or the null device.
- **Files.** `the file "<path>" exists` / `does not exist` / `contains "<text>"` / `matches the expected file "<name>"`; `the config file is unchanged` (byte for byte against `config_written`; fails if no `the config file contains:` ran).
- **Run folders.** `the cache holds no run folders` / `<n> run folder(s)` (folders directly under `{runs}`); `the cache holds no lock files` (no `*.lock` directly under `{runs}`, T5).
- **The fakes.** `<tool> was started <n> time(s)` / `was not started` / `was started with "<argument>"` / `without "<argument>"` (`<tool>` is `java`, `javac`, `git` or `the editor`; every `start` line of the scenario's log, the version check included, T5); `java ran "<main class>" <n> time(s)` / `did not run "<main class>"`; `java was started in the folder "<path>"` (the last tool start's working folder); `java ran from JAVA_HOME` / `from PATH` (the last start's own path against `$JAVA_HOME/bin/java` and the `PATH` launcher); `the java command matches the expected file "<name>"` (below); `the java process has exited` (every process id of a `start` line no longer exists, waited for up to 10 seconds). The fakes' steps read the whole log of the scenario, both runs of a two-run scenario included; the result steps speak about the last run (T5).
- **The terminal.** `the terminal contains "<text>"` / `does not contain "<text>"`; `the terminal ends with the expected file "<name>"`. `contains` looks in `screen_text` of the bytes after the last `LEAVE_ALT` if there is one, else of all bytes (what stays on the user's terminal); `does not contain` requires the text to be absent from that screen and from the whole output with escape sequences removed; `ends with` compares that screen with the expected file.

`the java command matches the expected file "<name>"` writes the last tool start's argument list one argument per line, with the scenario's folders written back as their placeholders (longest path first), and with two values that differ on every run replaced: the lifeline agent's process id (`-javaagent:...=pid=<n>` becomes `pid=<pid>`) and the run id in the `-metadir` path (`<run-id>`), as T5's note on the step says. T8's rule against normalising applies to the helper, which stays untouched; the step does it before the helper, for these values only.

### Step ownership: every step of T5, and who writes it

The rule: **this package writes a step when it reads or writes only files, folders and environment variables, the scripts and logs of [03](03-test-foundation.md)'s four fakes, and the processes and terminals the harness starts itself.** A step that has to go through a domain interface built later (the store and `format_build`, the module registry, `write_cache`), the `github` fixture (whose only users, the commands that ask GitHub, arrive with 29), or the live layout's sequences and panel titles, belongs to the first package whose scenarios use it. Steps written here that no scenario of this package uses are tested in `tests/unit/test_harness.py`.

| T5 kind | Step | Owner |
| --- | --- | --- |
| Given: the store | `the build "<spec>" is installed` (and `and pinned`) | [29](29-tool-commands.md) |
| | `no build is installed` | 29 |
| | `the module "<name>" is registered` | [31](31-module-commands.md) |
| | `the release list is cached from "<recording>", <n> minutes old` | 29 (through [25](25-remote-listing.md)'s `write_cache`) |
| | `the jar of the build "<spec>" is truncated` | 29 |
| Given: files | `a spec "<name>" from the golden specs` | 18 |
| | `a file "<path>" containing:` | 18 |
| | `a module source "<name>" from the fake sources` | 31 (the sources it copies are 30's and 31's) |
| | `the config file contains:` | 18 |
| | `the folder "<path>" is read-only` | 18 |
| | `I am in the folder "<path>"` | 18 |
| Given: what Java does | `java replays "<case>" with exit code <n>`; `java prints <n> lines`; `java writes "<text>" to stdout and "<text>" to stderr`; `java echoes its input` | 18 |
| Given: changes to the run declared last | `java hangs after line <n>`; `java pauses <n> ms between lines`; `java writes "<file>, ..." into its metadir`; `java begins a checkpoint after line <n> and commits it before line <m>`; `java ignores <signal>`; `java exits with <n> on <signal>` | 18 |
| Given: which Java there is | `java is not installed`; `java is not executable`; `java is version "<v>"`; `java is replaced by version "<v>"`; `java takes <n> seconds to report its version`; `java answers its version check with "<text>" on <stream> and exit code <n>`; `JAVA_HOME is a JDK of version "<v>"`; `JAVA_HOME is an empty folder`; `javac is not installed`; `javac is version "<v>"` | 18 |
| | `javac fails with "<recording>"` | 31 (the recordings of real `javac` errors are 31's, [03](03-test-foundation.md)) |
| Given: the editor | `the editor writes:`; `the editor exits with code <n>` | 18 |
| Given: the rest | `GitHub answers from "<recording>"`; `GitHub answers <status> to "<path>"`; `GitHub is unreachable` | 29 |
| | `the environment variable "<name>" is "<value>"` | 18 |
| When: in-process | `I run "<command>"` | 18 |
| When: a real process | every form of T5's row: the three `send` forms (`once java is running`, `twice`, `once java has begun its checkpoint` with its `and again once stderr contains` ending) and `to the foreground group` | 18 |
| When: on a terminal | `in a terminal <w> by <h>`, `with <stream> redirected to "<file>"`, `and answer "<text>"`, `press Ctrl-C once the terminal has shown "<a>" and then "<b>"`, `press Ctrl-C once java has begun its checkpoint` | 18 |
| | the form ending `and then an elapsed time <n> seconds later` | [40](40-live-display.md) (it reads the layout's `elapsed` value) |
| Then: result | all thirteen | 18 |
| Then: files and store | `the file ...` (four forms); `the config file is unchanged`; `the cache holds no run folders`; `<n> run folder(s)`; `no lock files` | 18 |
| | `the pinned build is "<spec>"`; `no build is pinned`; `the installed builds are:` | 29 |
| | `the registered modules are:` | 31 |
| Then: the fakes | all of T5's row | 18 |
| Then: GitHub | `<n> request(s) were sent to GitHub`; `<n> jar download(s) were made`; `no request carried a token to "<host>"` | 29 |
| Then: the terminal | `the terminal contains` / `does not contain`; `the terminal ends with the expected file` | 18 |
| | `the terminal showed the layout`; `the last layout frame contains "<text>"`; `the terminal stayed on the main screen` | 40 |
| Placeholders | seven of T5's eight, `{kept}` included | 18 |
| | `{kept-id}` | [45](45-cache-commands.md) |

Steps outside T5's table, added by later packages with their reason in their pull request: [39](39-tlc-command.md)'s `java received <signal>`, `java received no signal`, `java ran in its own process group`, `java ran in tlaup's process group` (on `Outcome.pgid` and the `start` line's process group) and the `press Ctrl-\` form of the terminal step. `{kept-id}` is in T5's list now and stays [45](45-cache-commands.md)'s, which adds it to `Scenario.expand`. The steps T5 added on 2026-11-24 (the checkpoint forms, `java answers its version check with ...`, `javac is version`) follow the rule above and are this package's too: each reads or writes only a fake's script or log.

Notes on the steps this package writes, where T5 leaves the form open (stage 4):

- **Declaring runs.** Each declaring step appends one entry to `java_runs` and rewrites the fake's script through `Fakes.script("java", ...)`; each modifier step changes the entry declared last, and fails if there is none. `java replays "<case>"` takes `<case>` as a path under `tests/parse/golden/` without `.out` (`tlc/v1.7.4/violation`); the `stdout` field is that `.out` file and, when the case's `cases.toml` table has a `stderr` key, the `stderr` field is that `.err` file. The run's `main` is the tool the case's folder names (`tlc` to `tlc2.TLC`, `sany` to `tla2sany.SANY`, `pcal` to `pcal.trans`); `java prints`, `java writes` and `java echoes` declare a `tlc2.TLC` run unless a later step of the owner says otherwise ([43](43-repl-command.md) declares its echo for `tlc2.REPL`; see Context, "The echo step"). `replace` is filled with the placeholders expanded, so a capture's `<tmp>/...` can be mapped onto `{work}`.
- **`java is version "<v>"`** sets the PATH `java`'s `version` field. **`java answers its version check with "<text>" on <stream> and exit code <n>`** sets that field to T4's object form instead (`{"stdout": ..., "stderr": ..., "exit": n}`, the text on the stream named and nothing on the other), for J3's answer that is not a version and the macOS stub (`Unable to locate a Java Runtime.`, exit 1). **`javac is version "<v>"`** sets the `version` of the PATH `javac`'s script, which it prints for `-version` (T4; M3's check). **`java begins a checkpoint after line <n> and commits it before line <m>`** sets the run's `checkpoint` field to `{"begin_after_line": n, "commit_before_line": m}` (T4). **`JAVA_HOME is a JDK of version "<v>"`** makes a JDK folder with `Fakes.jdk` whose `java` and `javac` both answer that version, and sets `JAVA_HOME` to it; **`JAVA_HOME is an empty folder`** makes an empty folder and sets the variable. **`java is replaced by version "<v>"`** rewrites the PATH launcher (a new file, so its size and time change) with a script of that version. **`java takes <n> seconds to report its version`** sets `version_delay_ms`. **`java is not installed`**, **`java is not executable`**, **`javac is not installed`** are `Fakes.remove` and `Fakes.not_executable`.
- **The editor steps** write the fake editor's script: `the editor writes:` sets `write` to the doc string; `the editor exits with code <n>` sets `exit`.
- **`the config file contains:`** writes the doc string to `{config}/config.yaml` (creating the folder) and remembers the bytes.
- **`the folder "<path>" is read-only`** removes the write bits and gives them back when the scenario ends (a finalizer), so the temporary folder can be deleted; skipped with the reason when the suite runs as root (T5).
- **`I am in the folder "<path>"`** changes the working folder with `monkeypatch.chdir`, creating it if needed.
- **`the environment variable "<name>" is "<value>"`** sets it with `monkeypatch.setenv` and records it in `env_set`. An empty value is set as empty, not removed.

### Where the other X1 and G2 scenarios go

[02 X1](../design/02-cross-cutting.md#x1-exit-codes) asks `errors.feature` for one scenario per example of rows 2 to 5, and [20 G2](../design/20-groundwork.md#g2-domain-errors) for one per subclass a command can reach. This package writes those today's commands reach without a later change (Tests). The rest wait for the command that raises them:

| Row or class | Example | Package |
| --- | --- | --- |
| 2 | Unknown option; missing argument; unknown command; no command | 18 |
| 2 | An invalid module name (`InvalidName`) | 31 |
| 2 | A version matching several builds where tlaup does not ask (`AmbiguousVersion`: `tool path`, `pin` without a terminal); `latest`; an address given as a version; `uninstall --all` without a terminal and `--yes` | 29 |
| 2 | `--workers` together with `-workers` after `--` (`ConflictingOptions`) | 39 |
| 2 | A value given to `config set` that does not fit | 44 |
| 2 | `cache clean RUN_ID` with `--all` | 45 |
| 3 | No tools installed, nothing pinned, the pinned build missing or damaged (`NoToolsInstalled`, `NoPinnedBuild`, `PinnedBuildMissing`) | 29 (`tool current`, `tool path`), 39 (`tlc`) |
| 3 | Java not found or too old (`JavaNotFound`, `JavaTooOld`); the first-run question cannot be asked (`CannotAsk`) | 39 |
| 3 | `javac` not found (`JavacNotFound`) | 31 |
| 3 | The config file is invalid (`ConfigInvalid`); also a relative `TLAUP_HOME` | 44; the second here |
| 3 | The pinned build has no REPL (`ToolNotInBuild`) | 43 |
| 4 | The spec, the cfg (`SpecNotFound`, `CfgNotFound`) | 39 |
| 4 | A version, locally or upstream (`VersionNotFound`) | 29 |
| 4 | A module; a path given to `module add` (`ModuleNotFound`, `PathNotFound`) | 31 |
| 4 | A config key (`ConfigKeyNotFound`) | 44 |
| 4 | A run id that names no run folder | 45 |
| 5 | Network error, rate limit, a download that does not verify (`NetworkError`, `RateLimited`, `DownloadVerificationError`, `RemoteDataError`); a file that cannot be removed or read (`FileOperationError`: the read-only uninstall, and the unreadable pin file of F10) | 29 (the download and GitHub cases also as T6's plain pytest, 24 to 27) |
| 5 | A `javac` error (`ModuleBuildError`) | 31 |
| 5 | The editor exited with an error | 44 |
| 5 | The store is locked by another tlaup (`StoreLocked`); a run folder in use | Plain pytest ([27](27-install-steps.md), [35](35-run-folders.md)): a scenario cannot hold a lock while tlaup runs (T5) |
| 5 | A file that is found and cannot be started (`ToolStartError`); an internal error (`InternalError`) | Plain pytest ([21](21-java-launcher.md), [17](17-error-handler.md)) |
| 141 | `--help`, an unknown option twice (the closed-pipe forms) | 18 |
| 141 | `tool list` and `tool pin nosuch` on closed pipes | 29 |
| 141 | A parsed run whose reader closes after one line | 39 |
| 130, 143, 129 | The signal scenarios of [11 R2](../design/11-runner.md#r2-signals) | 39 |

## Tests that must pass

**`tests/features/errors.feature`**, this package's part. In-process unless marked; each error scenario asserts the code and `stdout is empty`.

- `tlaup` alone: exit 2, `stdout contains "Usage"`, `stderr is empty` ([02 X1](../design/02-cross-cutting.md#x1-exit-codes) rule 7).
- `tlaup config` alone: the same. `config` is the one group whose name the final tree keeps, so the scenario never changes; [29](29-tool-commands.md) adds `tlaup tool` and [48](48-command-tree.md) the rest.
- `tlaup --nosuch` (an unknown option): exit 2, `stdout is empty`, `stderr contains "--nosuch"`. No assertion on Typer's layout (X1, Tests).
- `tlaup tools pin` (a missing argument): exit 2, `stdout is empty`, `stderr contains "VERSION"`.
- `tlaup nosuch` (an unknown command): exit 2, `stdout is empty`, `stderr contains "nosuch"`.
- `tlaup config --debug` (`--debug` after the subcommand): exit 2, `stderr contains "--debug"` ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)).
- An outline with `the environment variable "TLAUP_HOME" is "relative/path"`: `tlaup tools dir` exits 3, `stdout is empty`, `stderr contains "error:" 1 times`, `stderr does not contain "Traceback"`; `tlaup --debug tools dir`, and `tlaup tools dir` with `TLAUP_DEBUG` set to `1`, each exit 3 with `stderr contains "Traceback"` (the error before the context exists, F10).
- Real process: `tlaup --help` `as a process with stdout on a closed pipe`: exit 141, `stderr does not contain "Traceback"`.
- Real process: `tlaup --nosuch` `as a process with stdout and stderr on a closed pipe`: exit 141.
- Real process: `tlaup --nosuch` `as a process with stdout on the null device and stderr on a closed pipe`: exit 141.

**`tests/unit/test_harness.py`**, plain pytest, for the helpers and for every step of this package that no scenario here uses. The steps are called through their helper functions on a real `Scenario` (no patching, T12 rule 2):

- Placeholders: each of the seven expands to its folder; `{kept}` with one kept folder (a folder and a `run.json` holding `"kept": true` made by the test) gives its path, and with none and with two fails with a message; a `{` that is not a placeholder is left alone; a command word holding a path with a space stays one word.
- Rule 10: `I run` with `PYTHONIOENCODING` (and with `LC_ALL`) set through the environment step fails naming `as a process`; with a fake `java` log line whose stdout was not a pipe (made by running the fake `java` from the test with stdout on a file) it fails with the passthrough message. `STARTUP_ONLY` on `PYTHONPATH`, `LANG`, `TLAUP_HOME`.
- In-process: an exception other than `SystemExit` escaping `CliRunner` makes the step fail with its traceback (an app built in the test with a command that raises past the mapping, for instance by being invoked without `TlaupGroup`).
- Declaring runs: after `java replays "tlc/v1.7.4/violation" with exit code 12`, `java hangs after line 40` and `java writes "queue.chkpt, vars.chkpt" into its metadir`, the fake's script holds one run with the three properties; running the fake `java` from the test with `tlc2.TLC` replays the golden file byte for byte up to line 40 (stopping it with SIGTERM). A modifier with no declared run fails. `java prints 3 lines`, `java writes "a" to stdout and "b" to stderr` and `java echoes its input`, each run from the test, give what T5 says.
- Which Java: each step of the row, checked through what the fake then does when the test starts it (`-version` answers the version; `java answers its version check with "Unable to locate a Java Runtime." on stderr and exit code 1` makes `-version` print exactly that on stderr, nothing on stdout, and exit 1; `javac is version "21.0.2"` makes `javac -version` print `javac 21.0.2`; a removed or non-executable launcher is not found by `shutil.which` on the isolation `PATH`; the JDK folder's `bin/java` and `bin/javac` answer their version).
- The checkpoint modifier: after `java replays ...`, `java begins a checkpoint after line 3 and commits it before line 5` and `java hangs after line 4`, the fake started from the test logs a `checkpoint` line after line 3 with `.tmp` files in its timestamped folder, and, once sent SIGTERM with `java exits with 143 on SIGTERM` declared, leaves them as `.tmp`.
- The editor steps and `the config file contains:` / `is unchanged`; `the folder ... is read-only` (skipped as root) gives the write bit back after the test.
- The real-process runner, with small programs as `argv` (`sys.executable -c ...`): `closed_pipe()` makes a write fail with `BrokenPipeError` in the child; `exit_code_of(-15)` is 143; a child killed by SIGTERM reports 143; the `reader closes after 1 line` arrangement ends a child that prints 100,000 lines; `reset_sigint` gives a child SIGINT at its default even when the test process ignores it (the test ignores SIGINT around the start and restores it); the `send ... once java is running` wait, on a child that starts the fake `java` itself, sends only after the fake's tool `start` line and not after its `-version` start; `twice` waits for the fake's `signal` line; `once java has begun its checkpoint`, on a child that starts the fake `java` with a checkpoint declared, sends only after the fake's `checkpoint` line, and its `and again once stderr contains "x"` ending sends the second signal only after the child has written `x` to stderr; `to the foreground group` reaches a grandchild in the group.
- The terminal runner, Linux and macOS (skipped where `pty` is missing): a child that prints its terminal size (`os.get_terminal_size()`) prints the step's size, and its environment has `TERM=xterm-256color` and no `COLUMNS` or `LINES`; a child that asks two questions with `input()` gets both typed answers; `press Ctrl-C once the terminal has shown "a" and then "b"` ends a child that prints `a`, `b` and then sleeps in a loop, with 130; `press Ctrl-C once java has begun its checkpoint` types the interrupt only after the fake `java` the child starts has logged its `checkpoint` line; `screen_text` of bytes holding `ENTER_ALT`, a frame and `LEAVE_ALT` followed by text gives that text for `the terminal ends with the expected file`; `does not contain` sees text that was drawn and then overwritten.
- The fakes' Then steps on a log the test produces by starting the fakes itself: `was started n times` counts the version start; `ran "tlc2.TLC"` does not; `java ran from JAVA_HOME` after a start from the JDK folder; `the java command matches the expected file` writes placeholders for the folders and `<pid>` and `<run-id>` for an argument list that holds them; `the java process has exited` waits for an orphaned fake to go.

No stateful test applies.

## Changelog

None. Nothing a user sees changes.

## Context for the worker

**Decisions this rests on.** D33 (command-line behaviour is tested with pytest-bdd feature files). The design agent's decision "scenarios that pass output through, or need a pipe, a signal or a terminal, run tlaup as a real process; the rest run in-process" (an in-process runner cannot see a child's inherited streams), made a rule by T12 rule 10 at the sign-off. D29 (the codes the scenarios assert). D15 (no Windows CI: the pty and signal steps skip on Windows with the reason; the rest should work there).

**Facts from research the design restates, so the research files are not needed.** pytest-bdd 9.0.1 is the only version that runs with the locked pytest 9.2.0; doc strings reach a step as the reserved `docstring` argument with the common indent removed; a Given may follow a When; `scenarios("features")` resolves against the test file's folder (research 30). `CliRunner` on Typer 0.29.1 returns `result.stdout` and `result.stderr` apart with no extra argument, and with the mapping inside the root group every D29 code is visible in-process except 141 (T5). A test run started from a background job of a non-interactive shell has SIGINT ignored, the child inherits that across `exec`, and Python keeps it; without the reset every SIGINT scenario timed out in research 23's first run. With output shorter than a pipe's buffer, `| head -1` is a race that gives 0 or 141 from run to run, which is why the closed-pipe forms close the read end before the process starts (research 23). `pyte` 0.8.2 follows what Rich writes on a 100 by 30 pty, does not model the alternate screen (hence cutting the stream at the two sequences), and research 30 read a pty to the child's end without losing bytes on Linux and macOS. Rich takes `COLUMNS` and `LINES` over the terminal's own size, so the terminal steps remove both, or every terminal scenario would run at 100 by 40.

**Typing the answers** (T5's note, settled 2026-11-24). Nothing outside the process shows the moment it waits for input portably without a seam or a wait for time (rule 5). On a pty in canonical mode the terminal holds typed lines and hands the reader one line per read, and `Ui.ask` reads with `readline` ([14 F6](../design/14-config-and-cli.md#f6-messages)), so the step types all answers at once, each with its newline, right after the start, and the process takes them one at a time as it asks. The only visible difference is that the terminal echoes the answers before the questions appear; no scenario asserts that order.

**The java command file** (T5's note, settled 2026-11-24). `the java command matches the expected file` cannot work without replacing the folders of the scenario, the lifeline agent's process id and the run id: all three differ on every run, and T8 removes volatile parts "where they arise", which for these is impossible (the agent carries tlaup's process id by design, D51; the run id is random, R6). The step replaces exactly those, before `assert_matches`, and the helper itself stays as T8 has it.

**The checkpoint steps** (T5, question Q10, settled). The fake logs `checkpoint` after the 2195 line is in tlaup's pipe, not after tlaup has read it. A signal that lands while the line is still in the pipe or in the launcher's queue is sent on at once ([20 G3](../design/20-groundwork.md#g3-java-launcher), finding FC8), so a deferral scenario could fail. The fake's writing of the `.tmp` files and the step's own wait for the log line come between, which should be far longer than tlaup's read of one line; not tried. If 39's scenarios turn out flaky, the remedy T5 names is in the fake (wait until its stdout pipe is empty before it logs the marker; on Linux `FIONREAD` gives the unread byte count), never a seam in the product; that edit is 03's fake and goes in the pull request that sees the flake, which says so.

**The echo step.** `java echoes its input` declares a run like the other three; T5 does not say for which main class. Its only user is the REPL ([43](43-repl-command.md), [21 S3](../design/21-other-tools.md#s3-repl)). The fake takes the first run whose `main` matches the class it was started with ([03](03-test-foundation.md)), so the step declares `tlc2.REPL` for `echoes` and `tlc2.TLC` for the other three. If 43 needs a `sany` or `pcal` declaration it writes the case through `java replays`, whose folder names the tool.

**Two runs in one scenario** (T5): `I run` resets the context before each call; the Then steps on the result speak about the last run; the fakes' logs hold both. A Given between two Whens changes the fake's script for the second run: a declared run is used once ([03](03-test-foundation.md), "Which run answers").

**What later packages hook in.** 29's `GitHub ...` Given steps request the `github` fixture of [05](05-github-recordings.md) through `request.getfixturevalue("github")` and append its `clear` to `Scenario.before_run`, so `I run` counts the last run only (T5, "Counting"). 39's group steps read `Outcome.pgid`. 40's layout steps use `ENTER_ALT`, `LEAVE_ALT` and `screen_text`. None of them edits this package's step functions.

**Scenarios that use old command names.** Two scenarios above go through the old `tools` group, the cheapest command that runs the root callback (`tools dir`) and the cheapest required argument (`tools pin VERSION`). [29](29-tool-commands.md)a deletes the group and changes them to `tool dir` and `tool pin` in the same pull request (its Files says so). Every other scenario here names only the root and `config`, which the final tree keeps.

**Traps.**

- Step texts overlap (`stdout contains "x"` and `stdout contains "x" 3 times`; `as a process` and its longer forms; `time(s)`, `line(s)`): use `parsers.re` anchored at both ends, and test each pair in `test_harness.py`.
- Doc strings are the reserved `docstring` argument in pytest-bdd 9; do not name a step parameter `docstring` otherwise.
- `CliRunner(env=...)` assigns to `os.environ`; never use it (rule 7). `CliRunner(mix_stderr=...)` does not exist on Typer 0.29.1; the streams are already apart.
- The fake `java` is a script, so its version is never remembered and every tool run starts it twice ([13 J3](../design/13-modules-and-java.md#j3-one-java-start)): `java was not started` counts the version check too, and `java did not run "tlc2.TLC"` is the step for scenarios where the check may run.
- A real-process scenario cannot be served recordings. The isolation fixture's closed-port repository address is what keeps it off the network; do not remove it in the process runner.
- Read the pty with a loop that ends on end of output (`OSError` `EIO` on Linux, an empty read on macOS) after the child has exited, as research 30 did, so the last bytes are not lost.
- No `sleep` and no wait for an amount of time (rule 5): every wait is for a condition with a timeout (a log line, a screen text, a process end).
- Coverage counts the real processes through [03](03-test-foundation.md)'s subprocess patch; the environment the runner passes must keep the variables coverage sets (it passes `os.environ` as it is).

**State of `main` when this starts.** Release 0.8.x commands, with the handler, `main()`, `__main__.py` and `build_context` (17), `Ui` (16), the isolation fixture, the fakes with T4's checkpoint marker, `version` object form and `javac -version`, and the expected-file helper (03), no old test (03b), the golden files (07). No `tests/features/` and no `tests/steps/` exist. The old commands still exit 1 for their own errors (17, Context); no scenario here depends on that.

## Done when

- `uv run poe test` collects `tests/test_features.py` and runs `errors.feature`; the scenarios and `tests/unit/test_harness.py` pass on Linux and macOS in CI, the pty and signal ones included.
- Every step the ownership table gives to 18 exists in `tests/steps/`, and none of the steps it gives to another package does.
- `uv run poe lint` and `uv run poe test` pass; `uv run poe test-clean` leaves the home folder empty; CI is green.
- The pull request lists the step definitions with their T5 wording and says how the steps are made visible (`pytest_plugins` or import).

## Out of scope

- The steps the table gives to 29, 31, 40, and 39's four added steps and `Ctrl-\` form.
- Every feature file other than this package's part of `errors.feature`: the command packages.
- The fakes themselves, the isolation fixture and `assert_matches`: [03](03-test-foundation.md). The `github` fixture and the recordings: [05](05-github-recordings.md).
- The plain pytest cases of F10 and X1 that start child processes themselves (`/dev/full`, the interrupted flush, two calls of `main()`): [17](17-error-handler.md) and [29](29-tool-commands.md).
- Integration tests with real Java: [52](52-integration-tests.md).

## Risks

- From T5: the step list is long (about ninety forms) and closed; a scenario that needs a one-off step is usually a plain pytest test instead.
- From T5 and research 30: the pty steps depend on the platform's `pty` module and are skipped on Windows; macOS is first seen in CI.
- From T5: real-process scenarios cost a few hundred milliseconds each for the interpreter to start; they are counted in tens, which is why in-process stays the default.
- From T12 rule 10: the passthrough check relies on pytest's default capture; with capture switched off and the run's own output piped it would not fire, and the scenario would fail on its empty output instead (not tried).
- From the cut: most of the vocabulary written here is first used by later packages. A step whose meaning turns out wrong is fixed in the package that first uses it, in the same pull request, and the pull request says so.
- From the cut: the package is too large for one review as a whole (the in-process and file steps, the real-process runner, the terminal runner), so it is delivered as 18a and 18b below.
- From T5 (question Q10): the checkpoint steps leave a small race between the fake's marker and tlaup's read of the 2195 line (Context, "The checkpoint steps"); their unit tests here cannot show it, since they do not run tlaup.

## Pull requests (decided by stage 4)

This package is delivered as two pull requests; the index lists them as 18a and 18b.

- **18a**: the scenario state, the seven placeholders, the in-process When step with the two refusals of T12 rule 10, the file, environment, fake and result steps (the checkpoint modifier, `java answers its version check with ...` and `javac is version` included), and the in-process scenarios of `errors.feature`. Depends on 02, 03, 07, 16, 17.
- **18b**: the real-process runner, the signal steps (the checkpoint forms included), the pseudo-terminal runner with `pyte` (with its checkpoint Ctrl-C form), and the three closed-pipe scenarios. Depends on 18a.

A package that names 18 as a dependency waits for 18b.
