# 17. The error handler, `main()` and `--debug`

Size: M. Suggested model: most capable. Status: built. The debug filter that `--debug` output passes through is [24](24-github-client.md)'s (`redact`, question Q6, settled); this package builds the one function it goes into (see Interfaces).

## Goal

Every exception that leaves a command, the root callback or the parsing of the root options is mapped to one `error:` line and an exit code inside the application's root group, so in-process tests see the same codes as a real process; `main()` turns Typer's own exit after a closed pipe into 141 and flushes both streams itself; `--debug` and `TLAUP_DEBUG=1` show the traceback; `python -m tlaup` works. The helpers that judge the standard streams live in a small module the launcher can import.

## Covers

- Roadmap items:
  - "No tracebacks for users: missing Java, missing jar with `--raw` or `--show-command`, a broken config, an unreadable pin file. Turn off Typer's decorated crash reports, add one top-level handler that prints a one-line error, and add `--debug` to show the full traceback." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust), line 247), in part: the handler, `--debug`, `TLAUP_DEBUG`, the crash reports off. The four cases are each a `TlaupError` raised by the code that builds them, with their scenarios: missing Java and the missing jar with `--raw` or `--show-command` ([39](39-tlc-command.md)), a broken config ([19](19-layered-config.md) raises, [44](44-config-commands.md) has the scenarios), an unreadable pin file ([23](23-tool-store.md) raises `FileOperationError`, code 5; [29](29-tool-commands.md)a has the scenario).
  - "A small family of domain errors (spec not found, tool not installed, Java missing or too old) mapped to exit codes in one place." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 293), in part: the one place that maps them. The classes are [02](02-errors-and-paths.md)'s.
  - "Report run errors as what they are." (milestone 1), in part: exit 141 at the top and the stream helpers the launcher polls. The rest is [21](21-java-launcher.md), [37](37-run-tlc.md), [39](39-tlc-command.md).
  - "Exit codes: documented; ... 2 for usage errors that are hand-written today; non-zero when an operation failed" ([milestone 4](../roadmap.md#milestone-4-automation-surface), line 481), in part: the mapping. Each command's codes come with its switch.
- Design sections:
  - [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks), all of its Design, the contract tests of Typer (the public half), and the Tests that can be written without the step vocabulary (see "Tests that must pass" for where each of F10's tests goes). Not here: completion in `main()` ([47](47-completion.md), [23 C3](../design/23-command-layout.md#c3-completion)), the private-name half of the contract tests (47), the scenarios that need steps ([18](18-feature-harness.md) and later).
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes): rules 1, 6, 7 and 8 as far as the handler and `main()` make them true (its Breaking changelog entry is [48](48-command-tree.md)'s). The table's examples are raised by the packages that build each command.
  - [20 G2](../design/20-groundwork.md#g2-domain-errors): "mapped to exit codes in one place", and the printing of an exception's notes.
  - [00, application context](../design/00-overview.md#application-context): the root callback builds the context from the environment and the root options and stores it on Typer's context object.
- The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md): row P1 (the installed command is `tlaup`), whose owner this package is (findings F1 and G1 of the [second review](review-2026-11-24.md)).

## Depends on

- [02](02-errors-and-paths.md): `TlaupError` with `message`, `hint`, `details` and `exit_code`; `CannotAsk`, `Failed`; `AppPaths.from_env` (which raises `ConfigInvalid` for a relative folder); `tlaup/context.py`.
- [03](03-test-foundation.md): the isolation fixture (its environment is also the child processes' environment) and coverage of child processes ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)). No fake is needed: the pipes and `/dev/full` are opened by the tests themselves.
- [16](16-ui-messages.md): `Ui`, `Ui.for_process()`, `ui.error`, `ui.err`, `_PipeConsole`.

## Files

Creates:

- `src/tlaup/stdio.py`: the stream helpers (see Interfaces). Imports only the standard library.
- `src/tlaup/__main__.py`: calls `main()`.
- `tests/unit/test_handler.py`: the small apps under `CliRunner`.
- `tests/unit/test_stdio.py`: the stream helpers.
- `tests/unit/test_main_process.py`: real child processes started by the test.
- `tests/unit/handler_apps.py`: the small apps the child processes run (a module the test starts with `sys.executable`, taking the case name as its argument; it calls `run_app` on an app built with `cls=TlaupGroup`).
- `tests/unit/test_typer_contract.py`: the public half.
- `tests/unit/test_no_private_imports.py`: no module under `src/tlaup` imports `click` or a Typer module whose name starts with an underscore.

Changes:

- `src/tlaup/cli.py`: `TlaupGroup`, `mapped`, `reported`, `report`, `report_internal_error`, `own_exit`, `run_app`, `main`; `app` built with `cls=TlaupGroup`, `name="tlaup"`, `add_completion=False`, `no_args_is_help=True`, `pretty_exceptions_enable=False`; the root callback gains `--debug`, builds the context and stores it on `ctx.obj`, and no longer calls `load_config()` ([14 F4](../design/14-config-and-cli.md#f4-config-commands-with-a-broken-file): nothing loads settings in the root callback). The `-v`/`--version` flag and its text stay as they are ([48](48-command-tree.md) moves it to `-V`); only its printing moves to `Ui.for_process()`. The registrations of the old commands do not change.
- `src/tlaup/context.py`: `build_context` (see Interfaces).
- `pyproject.toml` and `uv.lock`: `typer>=0.27.2,<1.0.0` ([30 B2](../design/30-ci-and-release.md#b2-build-fixes), D59), because `typer.TyperException` is public from 0.27.2 only. One dependency line; [56](56-build-and-metadata.md) owns the other bounds.
- `pyproject.toml`, `[tool.ruff.lint.per-file-ignores]`: `"src/tlaup/cmd/**" = ["PLC0415"]` and `"src/tlaup/cli.py" = ["PLC0415"]`, with a comment naming [14 F9](../design/14-config-and-cli.md#f9-startup-cost). F9 makes function-level imports the rule in command modules, and ruff's `PLC0415` (in the `PL` group the project selects, active on the locked ruff 0.17.5) flags them; F9 wants the ignore in place before the first command module written that way, and every command package (29, 31, 39, 41 to 47) comes after this one. [49](49-startup-cost.md) checks that it is there.
- `CHANGELOG.md`: see Changelog.

Deletes: nothing.

Shared with packages of the same group: `src/tlaup/cli.py` with [19](19-layered-config.md) (19 does not touch it; listed because both work near the root callback), with [24](24-github-client.md) (one call in the debug-printing function) and with the switch packages later (one registration block each); `src/tlaup/context.py` with 16 and 19; `pyproject.toml` and `uv.lock` with 16 and 56, one line each; `CHANGELOG.md`.

## Interfaces

Provides.

`tlaup/stdio.py`, **written by stage 4**: F10 defines `reader_gone`, `is_pipe`, `is_null_device`, `silence`, `closed_pipe_on_windows` and `WRITE_ERRNOS` beside `main()` and names no module, but the launcher ([21](21-java-launcher.md), `run_streaming` and `run_passthrough`) polls `reader_gone(1)` ([20 G3](../design/20-groundwork.md#g3-java-launcher), [11 R1](../design/11-runner.md#r1-run-errors-reported-as-what-they-are)) and must not import `tlaup.cli` (it would pull Typer in and point the dependency the wrong way). So they live here, and the module imports neither Typer nor Rich.

```python
# tlaup/stdio.py
WRITE_ERRNOS: frozenset[int]          # {errno.ENOSPC, errno.EDQUOT, errno.EFBIG, errno.EIO}
def is_pipe(fd: int) -> bool          # stat.S_ISFIFO(os.fstat(fd).st_mode); False on any OSError
def is_null_device(fd: int) -> bool   # same device and inode as os.devnull; False on any OSError
def poll_says_gone(revents: int) -> bool   # written by stage 4: POLLERR or POLLHUP -> True; POLLNVAL -> False; POLLOUT alone -> False
def reader_gone(fd: int) -> bool      # select.poll, registered for POLLOUT, timeout 0; False where poll does not exist (Windows)
def silence(stream: TextIO) -> None   # os.dup2 of the null device onto the stream's descriptor; no-op without a descriptor
def closed_pipe_on_windows(e: OSError, *, os_name: str = os.name,
                           pipe: Callable[[int], bool] = is_pipe) -> bool
    # os_name == "nt" and e.errno == EINVAL and e.filename is None and (pipe(1) or pipe(2)); the two
    # keyword arguments are written by stage 4 so the unit test can give "Windows" without patching
```

`tlaup/cli.py`, from F10 (copy the code block there; it is the intended shape):

```python
@contextmanager
def mapped(*, ctx: typer.Context | None = None, args: Sequence[str] = ()) -> Iterator[None]
def reported(code: int, report_it, *args) -> int
def report(error: TlaupError, ctx: typer.Context | None, args: Sequence[str]) -> None
def report_internal_error(error: BaseException, ctx: typer.Context | None, args: Sequence[str]) -> None
class TlaupGroup(TyperGroup):
    def make_context(self, info_name, args, parent=None, **extra): ...   # wrapped in mapped(args=args)
    def invoke(self, ctx: typer.Context) -> Any: ...                     # wrapped in mapped(ctx=ctx)
app: typer.Typer
def run_app(app: typer.Typer) -> NoReturn    # the body of main(), written in F10's block as main() inline
def main() -> None                           # run_app(tlaup's app); the console script and __main__.py
```

`own_exit` is a module-level object with one attribute, `seen`, set by `mapped` for every `typer.Exit` and reset at the top of `run_app`.

`tlaup/context.py`, **written by stage 4** (02 left "the builder for the root options" to this package):

```python
def build_context(env: Mapping[str, str], *, debug: bool) -> AppContext
    # builds paths (AppPaths.from_env, may raise ConfigInvalid), Ui.for_process(), and replaces the cached
    # context, so get_context() returns this one for the rest of the run; debug is the flag or TLAUP_DEBUG=1
```

The root callback calls it once per run of the app and stores the result on `ctx.obj`. A fresh context per run of the app is what makes each in-process call (`I run`, a second `CliRunner.invoke`) print into its own captured streams.

**The debug filter** (question Q6, settled; [12 V7](../design/12-tools-and-downloads.md#v7-github-client), [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)). Every line the handler prints under debug, the one-line message and the traceback, passes through `redact(text, os.environ)` of `tlaup/versioning/redact.py`, a stand-alone function with no state that [24](24-github-client.md) owns. Build the debug printing so that all of it goes through one function of `cli.py` (for example `_debug_text(text: str) -> str`, which returns its argument unchanged here); 24 adds `redact.py` and turns that function into the call, one line. No token can leak before then: no command reads `GH_TOKEN` or `GITHUB_TOKEN` until [29](29-tool-commands.md) switches the `tool` commands to the new client, and 29 waits for 24.

Consumes: `Ui`, `Ui.for_process` (16); `TlaupError` and subclasses, `AppContext`, `get_context`, `AppPaths` (02). Not `redact`: 24 wires it in.

Used later by: the GitHub client ([24](24-github-client.md): the debug-printing function, which it points at `redact`); the launcher ([21](21-java-launcher.md): `reader_gone`); the feature harness ([18](18-feature-harness.md): `python -m tlaup` and the in-process `app`); every command (errors raised are printed here; notes added with `add_note` are printed here, [11 R6](../design/11-runner.md#r6-run-folders)); completion ([47](47-completion.md): `main()` switches completion on).

## Tests that must pass

Where each of F10's and X1's tests goes. Feature scenarios need the step vocabulary, which is [18](18-feature-harness.md) and depends on this package. So this package tests everything it builds with plain pytest, starting child processes itself where a real process is needed; 18 and later packages add the scenarios, listed at the end of this section so nothing is lost.

**`tests/unit/test_handler.py`** (in-process, `CliRunner`, small apps built with `cls=TlaupGroup`; no hidden test command is added to tlaup):

- A command raising `RuntimeError`: exit 5, stderr is one `error: internal error: RuntimeError: ...` line and the `hint:` line naming `tlaup --debug` and `TLAUP_DEBUG=1`; no `Traceback`.
- A command raising `EOFError`: exit 3 (`CannotAsk`).
- A command raising a `TlaupError` subclass from a nested subgroup: its family's code, one `error:` line, then `hint:`, then the details indented.
- A command raising `KeyboardInterrupt`: 130. `typer.Abort`: 130. A missing argument, an unknown command, an unknown option and `typer.BadParameter`: 2, in Typer's form, stdout empty.
- An eager option callback raising `RuntimeError`, then a `TlaupError`, then `BrokenPipeError`: 5, the error's code, 141 (the `make_context` wrapper).
- `report`: an error with a hint, details and two notes added with `add_note` prints the `error:` line, the hint, the details, then the two notes, in that order.
- A command that adds a note to a `BrokenPipeError` and raises it: 141, and the note alone on stderr.
- `--debug` before the command, and separately `TLAUP_DEBUG=1` set with `monkeypatch`: the same `TlaupError` and the same `RuntimeError` print the line and then a traceback. `--debug` after a subcommand: 2.
- `TLAUP_HOME` set to a relative path with `monkeypatch`, then tlaup's own `app` with the old `tools dir` command: exit 3, one `error:` line, no traceback; with `--debug` a traceback. This is the error before the context exists ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks), "In-process"). The test resets the context. [29](29-tool-commands.md)a, which removes `tools dir`, changes the command in this test to `tool dir`.
- `tlaup` alone and a group alone (`tlaup config`): exit 2, help on stdout, stderr empty ([02 X1](../design/02-cross-cutting.md#x1-exit-codes) rule 7).
- D57: an app built with a subclass of `TlaupGroup` whose closed-pipe test answers "Windows and a pipe" (see Context, "Testing the Windows rule"): a command whose print raises `OSError(errno.EINVAL, ...)` exits 141 with nothing printed; with tlaup's own rule on Linux the same error is 5.
- A command whose write raises `OSError(errno.ENOSPC, ...)` with no file name: 5 and `error: cannot write output: ...`; the same error with a file name: an internal error (5, `internal error:`).
- A command that raises `typer.Exit(1)`: 1 (the old commands' form; see Context).

**`tests/unit/test_stdio.py`**: `poll_says_gone` for `POLLERR`, `POLLHUP`, `POLLOUT` alone and `POLLNVAL` gives true, true, false, false; `reader_gone` on a real pipe whose read end is closed is true, with the read end open and empty is false, on a regular file is false (Linux and macOS; skipped with the reason where `select.poll` is missing); `is_pipe` and `is_null_device` on a pipe, a file and the null device; `closed_pipe_on_windows` for the four combinations of `os_name` (`"nt"`, `"posix"`) and `pipe` (true, false), and for an error with a file name; `silence` on a stream with no descriptor does nothing. Also a test that `import tlaup.stdio` in a fresh interpreter loads neither `typer` nor `rich`.

**`tests/unit/test_main_process.py`**, real processes started by the test with the isolation fixture's environment, SIGINT reset to its default in the child before `exec` ([01 T5](../design/01-testing.md#t5-feature-files-and-steps), the two rules from research 23), and pipes whose read end is closed before the child starts (never `| head -1`, which is a race for short output). Each case gives the exit code; where stderr can still be read it also has no `Traceback`.

| Case | Child | Expected |
| --- | --- | --- |
| Help into a closed stdout | `python -m tlaup --help` | 141 |
| A subcommand's help into a closed stdout | `python -m tlaup config --help` | 141 |
| No arguments into a closed stdout | `python -m tlaup` | 141 |
| Unknown option, both streams on the closed pipe | `python -m tlaup --nosuch` | 141 |
| Unknown option, stdout on the null device, stderr on the closed pipe | `python -m tlaup --nosuch` | 141 |
| Unknown option, nothing closed | `python -m tlaup --nosuch` | 2 |
| `--help` into an open pipe the test reads | `python -m tlaup --help` | 0 |
| A domain error with stderr's reader gone (stdout open; then both on the same dead pipe; then stdout on the null device) | small app | 141, 141, 141 |
| An internal error, the same three arrangements | small app | 141 each |
| A domain error with only stdout's reader gone | small app | its code, message on stderr |
| A command printing three lines, and one printing 200,000 lines, through `Ui` into a dead reader | small app | 141 |
| A command exiting 1, 12 and 0 through `typer.Exit` with both readers gone | small app | 1, 12, 0 |
| A command's output onto `/dev/full` (Linux only, skipped elsewhere) | small app | 5, `cannot write output` on stderr |
| `--help` onto `/dev/full` (Linux only) | `python -m tlaup --help` | 5 |
| Unknown option with stderr onto `/dev/full` (Linux only) | `python -m tlaup --nosuch` | 5 |
| A domain error with stderr onto `/dev/full` (Linux only) | small app | its own code |
| A command printing without end into a pipe whose reader is alive and not reading, then SIGINT; once with stdout alone on that pipe, once with both streams | small app | 130 within the step's timeout of a few seconds |
| Two calls of `run_app` in one process: a command exiting 1 through `typer.Exit`, then `--help` into a pipe with no reader | small app | the second gives 141 |
| `--version` | `python -m tlaup --version` and the console script | the same stdout |

The console script for the last row is found beside `sys.executable` (the isolation fixture's `PATH` holds only the fakes). That row is the test of [preserved-behaviour row](../design/preserved-behaviour-2026-11-22.md) P1 (the installed command is `tlaup`), which this package owns: the console script beside `sys.executable` is named `tlaup` (`tlaup.exe` on Windows) and answers as `python -m tlaup` does. No test measures time; "within a few seconds" is the wait's timeout.

**`tests/unit/test_typer_contract.py`** (public half of F10's contract tests): `typer.Exit`, `typer.Abort`, `typer.BadParameter` and `typer.TyperException` exist; the error Typer raises for an unknown option is a `TyperException`; `typer.core.TyperGroup` has `make_context(info_name, args, parent=None, **extra)` and `invoke(ctx)`, checked with `inspect.signature`. Each check names the Typer name in its failure message. The private half (completion) is added by [47](47-completion.md).

**`tests/unit/test_no_private_imports.py`**: no module under `src/tlaup` imports `click` or a Typer module whose name starts with an underscore. [47](47-completion.md) adds the one exception, `tlaup/cmd/completion.py`.

**What the step vocabulary's packages must add, so nothing of F10 and X1 is lost:**

- [18](18-feature-harness.md), `errors.feature`, with the commands that exist then (old names until their switch): the three real-process 141 scenarios that need no new command (`tlaup --help` with stdout on a closed pipe, no `Traceback`; an unknown option with stdout and stderr on a closed pipe; an unknown option with stdout on the null device and stderr on a closed pipe); the no-command pair (`tlaup`, and a group alone) exit 2, help on stdout, stderr empty; one in-process scenario each for an unknown option, a missing argument and an unknown command (exit 2, stdout empty, stderr names the problem, no assertion on Typer's layout); `--debug` after the subcommand exits 2; `TLAUP_HOME=relative/path` with the cheapest command exits 3 with one `error:` line, and with `--debug` and with `TLAUP_DEBUG=1` has a `Traceback`.
- [29](29-tool-commands.md): `tlaup tool list` with two builds installed and stdout on a closed pipe, 141 and no `Traceback`; `tlaup tool pin nosuch` with both streams on a closed pipe, 141; the plain pytest `tlaup tool list` with stdout on `/dev/full` (Linux), 5 and `cannot write output`; an unreadable pin file exits 5 (`FileOperationError`) with no `Traceback`, with one under `--debug` and under `TLAUP_DEBUG=1` (one of F10's four cases); `tlaup tool` alone exits 2 with help on stdout; the X1 examples its commands reach.
- [39](39-tlc-command.md) (already in its file): the parsed run whose reader closes after one line, 141; missing Java and the missing jar with `--raw` and `--show-command`, each with and without `--debug` and `TLAUP_DEBUG=1`.
- [44](44-config-commands.md): a broken config with and without `--debug` and `TLAUP_DEBUG=1`.
- Every switch and command package: the X1 table's examples and the G2 subclasses its commands can reach, in `errors.feature`, each asserting the code, an empty stdout and exactly one `error:` line.

No stateful test applies.

## Changelog

Under `## [Unreleased]`, word for word.

From [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks):

- Fixed: "Several failures printed a Python traceback. tlaup now prints one `error:` line; `tlaup --debug ...` or `TLAUP_DEBUG=1` shows the traceback."
- Added: "`--debug`, and `python -m tlaup`."

Not here: [02 X1](../design/02-cross-cutting.md#x1-exit-codes)'s Breaking entry on exit codes ("Exit codes changed. tlaup's own errors now return 2 ... instead of 1; ..."). [48](48-command-tree.md) writes it, where tlaup's own exit 1 ends and the entry becomes true (finding B10); [39](39-tlc-command.md) and the other switch packages do not repeat it.

## Context for the worker

**Decisions this rests on.** D29 (2, 3, 4, 5; tlaup never returns 1; 130, 143, 129 and 141 set by tlaup; the wrapped tool's code passes through). D57 (a closed pipe on Windows, `OSError` with `EINVAL` on a pipe, is 141). D59 (`typer>=0.27.2,<1.0.0`, `rich>=13.8.0`). D15 (no Windows CI: the Windows rule is unit-tested with the platform given, and `stat.S_ISFIFO` on a Windows pipe descriptor follows Python's documentation and was not tried; the pull request says whether it was checked by hand on Windows, as F10 asks).

**The facts F10 rests on**, restated so the research files are not needed. On Typer 0.29.1 (and every version from 0.27.2 to 0.29.2) Typer carries a private copy of Click; `import click` fails. Typer's own entry code turns an `EOFError` into "Aborted." and exit 1, a `KeyboardInterrupt` into 130, a usage error into 2, an `OSError` with `EPIPE` into 1, and lets any other exception out through `sys.excepthook`. `CliRunner` sees only what happens inside the app, which is why the mapping is in the root group and not in `main()`. Rich 13.8.0 and later catch `BrokenPipeError` inside `Console.print` and call `on_broken_pipe`, whose default points stdout's descriptor at the null device and raises `SystemExit(1)`; a stderr console on a closed stderr points descriptor 1, never 2, at the null device. Typer prints help and its usage errors through a console tlaup does not own, so those still leave as `SystemExit(1)`, which `main()` recognises. `select.poll` reports `POLLERR` on Linux and `POLLHUP` alone on macOS for a pipe whose reader has gone, and nothing at all on macOS for a descriptor registered with an empty mask, which is why `POLLOUT` is asked for; a full pipe whose reader is alive reports neither. Without the final flush in `main()` the interpreter's own flush at exit can fail and exit 120.

**The closed pipe in three parts** (F10, X1 rule 8): tlaup's consoles raise `BrokenPipeError` up to `mapped` (16's `_PipeConsole`); `main()` turns a 1 that came with a closed pipe into 141 (descriptor 1 now the null device and not at the start, or `reader_gone(1)` or `reader_gone(2)`), unless `mapped` saw a `typer.Exit`; `main()` flushes both streams in a guard and exits with the code it holds. After 129, 130 or 143 `main()` points stdout at the null device before the flush, so a Ctrl-C while a pager is not reading does not block.

**The cannot-write case.** A full disk is not a closed pipe: an `OSError` with no file name and one of `WRITE_ERRNOS` inside a command is `error: cannot write output: <reason>` and 5; in Typer's printing outside the group it reaches `main()`, which sets 5; at the final flush it makes a 0 into 5 and leaves any other code alone. Any other `OSError` that reaches the root is an internal error: domain code wraps its own.

**Reporting is guarded** (`reported`): with stderr on the closed pipe, printing the error raises `BrokenPipeError` from inside an `except` branch; `reported` silences stderr and returns 141. On a full disk it silences stderr and the error keeps its code. `report` takes `ctx.obj.ui` when a context exists and `Ui.for_process()` otherwise; the eager `--version` callback prints through `Ui.for_process()` too, because it runs before the root callback.

**How debug is decided.** Not from the context, because the failure may have happened while it was built: `ctx.params["debug"]` when a context exists; `TLAUP_DEBUG=1` in the environment always; when the failure was in `make_context` and no context exists yet, whether `--debug` stands among the arguments before the first word that does not start with `-`. `--debug` is a root option, so it goes before the subcommand; after it Typer says "No such option" (exit 2).

**What the old commands do after this package.** They still raise `typer.Exit(1)` for their own errors until their switch (29 `tools`, 31 `modules`, 39 `tlc`, 44 `config`, 46 and 48 for `check-java` and `fetch-cache`). `mapped` lets a `typer.Exit` through unchanged and notes it, so those runs keep exiting 1, also with a closed pipe: a 1 a command asked for is never turned into 141, because it may be the wrapped tool's own 1 (X1 rule 1's exception). So X1's "tlaup never returns 1 itself" holds only once [48](48-command-tree.md) is in. Two more changes the old commands see at once: an exception they do not catch is an internal error, 5 with one line, instead of a traceback and 1; and the old prompts (`typer.prompt`, `typer.confirm` in `tools pin` and `tools uninstall`) raise `typer.Abort` at end of input or when declined, which `mapped` turns into 130 instead of Typer's "Aborted." and 1. Both are accepted until 29 replaces those prompts with `Ui.ask`: `main` need only be green between packages (decision D62).

**Testing the Windows rule.** F10 asks for "the platform given as Windows and a pipe as stdout". Rule 2 of [01 T12](../design/01-testing.md#t12-rules-for-writing-tests) forbids patching tlaup, and setting `os.name` breaks `pathlib`. So `closed_pipe_on_windows` takes `os_name` and `pipe` as keyword arguments, unit-tested directly, and `TlaupGroup` calls it through one overridable static method, so the in-process test builds its small app with a subclass that answers true. That is a subclass in the test, not a patch. Say in the pull request how it was done.

**Traps.**

- The order of `mapped`'s branches matters: `typer.Exit` first, then `(typer.TyperException, KeyboardInterrupt)`, then `typer.Abort`. Check that `typer.Abort` is not a `TyperException` on the locked Typer; if it were, the `Abort` branch would be dead. Add that check to the contract test if it holds.
- `own_exit.seen` is reset at the top of `run_app`, since a successful `--help` sets it too and `main()` can run twice in a process. In-process tests call `app`, never `main()`, and never read the flag.
- `prog_name="tlaup"` is fixed, so usage lines and completion's variable do not depend on how the program was started.
- The last `except Exception` in `mapped` is the one blind except the BLE rules will allow ([30 I8](../design/30-ci-and-release.md#i8-lint-rules)); give it the `noqa` and a comment now.
- Notes are Python's own (`__notes__`, Python 3.11 and later). Print them after the `error:` line and hint of a `TlaupError`, after the internal-error line, and alone for a closed pipe.
- `report_internal_error`'s hint names the issues address; take it from the package metadata's project URLs, not a second copy.
- `silence` is guarded for a stream with no descriptor (`CliRunner`'s).
- The child processes of `test_main_process.py` are counted by coverage's subprocess patch, set up by [03](03-test-foundation.md). Use `os.pipe()` and close the read end before starting the child; Python ignores SIGPIPE at start, so the child's write raises `BrokenPipeError`.
- `/dev/full` exists on Linux only; skip those rows elsewhere with the reason.
- `CliRunner(env=...)` assigns to `os.environ`; set variables with `monkeypatch.setenv` instead (T12 rule 7).

**State of `main` when this starts.** Release 0.8.x commands; `errors.py`, `paths.py`, `context.py` (02); the isolation fixture, and no old test under `tests/unit/` or `tests/integration/` (03b); `Ui` (16). `cli.py` has today's root callback with `-v` and a `load_config()` call. Settings may or may not have been replaced yet ([19](19-layered-config.md) runs beside this package); removing the `load_config()` call from the root callback is right in both cases.

## Done when

- The tests above pass on Linux and macOS in CI; the `/dev/full` rows run on Linux.
- `python -m tlaup --help` works; `uv run tlaup --debug tools dir` and `TLAUP_DEBUG=1 uv run tlaup tools dir` run.
- `tlaup/stdio.py` imports nothing from `typer` or `rich` (its test).
- F10's two changelog entries are written.
- `uv run poe lint` and `uv run poe test` pass; CI is green.
- The pull request names the one function the debug printing goes through, which [24](24-github-client.md) points at `redact`.
- The `PLC0415` per-file ignores are in `pyproject.toml`.
- The pull request names inventory row P1 and its test (the `--version` row through the console script).

## Out of scope

- The scenarios that need the step vocabulary: [18](18-feature-harness.md) and the packages listed above.
- `-V` and the version text `tlaup 0.9.0`: [48](48-command-tree.md) ([23 C4](../design/23-command-layout.md#c4-version-flag)).
- Completion in `main()` and the private half of the contract tests: [47](47-completion.md).
- The filter for debug output, `redact`, and its call in the debug-printing function: [24](24-github-client.md).
- Raising the right `TlaupError` in each command: the command packages.
- Signals during a run: the launcher ([21](21-java-launcher.md)); this handler sees only a `KeyboardInterrupt` outside a run.
- A raw run stopping TLC when its reader goes (D58): [21](21-java-launcher.md) and [37](37-run-tlc.md), with `reader_gone` from here.

## Risks

- From F10: the handler subclasses `typer.core.TyperGroup`, overrides two of its methods and relies on the order in which Typer handles exceptions; a Typer release can change any of these. Part 2 of the closed-pipe handling relies on what Rich does in a console tlaup does not own. The guards are the version bounds, the contract tests, the real-process tests above and the newest-dependencies job ([30 I3](../design/30-ci-and-release.md#i3-newest-dependencies-job)).
- From X1: the codes rest on one Typer and one Rich behaviour each; macOS is first seen in CI.
- From the cut: until [24](24-github-client.md) is in, debug output is unfiltered. Harmless until [29](29-tool-commands.md) makes a command read the token, and 29 depends on 24.
- From the cut: between this package and 48 the old commands still exit 1, and their prompts now give 130 at end of input.
