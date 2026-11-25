# 16. The messages helper (`Ui`)

Size: S. Suggested model: mid-tier. Status: built.

## Goal

`tlaup/ui.py` holds `Ui`, the one place that builds consoles: two `_PipeConsole`s, the message methods, the only prompt reader and the interactivity test, all built from streams passed in. The application context carries one. Old commands still print as they do today; each switch package moves its own commands onto `Ui`.

## Covers

- Roadmap items:
  - "Route every message through the one UI helper; there are 21 hand-written error prints and a warning printed to stdout in `tools list`." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the helper itself. The call sites are converted by the packages that rewrite them (29 `tool`, 31 `module`, 39 `tlc`, 44 `config`, 41 to 43 and 45 to 47 for the new commands). The `tools list` warning goes with 29. Package 58 turns on the lint rules that forbid `print`, `typer.echo` and `Console(` outside `ui.py` and the reporters.
  - "Do not crash on non-UTF-8 bytes in TLC output." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: `errors="replace"` on tlaup's own two streams ([11 R3](../design/11-runner.md#r3-non-utf-8-output), last sentence of its Design). The launcher's side is [21](21-java-launcher.md), the hint [33](33-tlc-invocation.md).
- Design sections:
  - [14 F6](../design/14-config-and-cli.md#f6-messages): `_PipeConsole`, `Ui` with every method, `ask`, `is_interactive`, the message format, `NO_COLOR`, the constructor as the one seam for tests, and the unit tests. Not here: converting the call sites (see above), the real-pty scenario of `tool uninstall rolling` (29), the changelog entries (see Changelog).
  - [00, application context](../design/00-overview.md#application-context): the `ui` field of `AppContext`.
  - [01 T5, "Prompts have one mechanism"](../design/01-testing.md#t5-feature-files-and-steps): the constructor that tests and production both use.

## Depends on

- [02](02-errors-and-paths.md): `CannotAsk` (code 3) from `tlaup/errors.py`; `tlaup/context.py` with `AppContext` and `get_context`, which this package extends by one field.
- [03](03-test-foundation.md): the isolation fixture (it sets `NO_COLOR=1`, `TERM=dumb`, `COLUMNS=100`); the expected-file helper `assert_matches` and `--update-expected` ([01 T8](../design/01-testing.md#t8-expected-output-files)).

## Files

Creates:

- `tests/unit/test_ui.py` and its expected files under `tests/unit/expected/ui/` (one per message kind, colour off and colour on).

Changes:

- `src/tlaup/ui.py`: adds `ColorPolicy`, `_PipeConsole` and `Ui`. The four functions of today's module (`warn`, `error`, `info`, `success`) stay, unchanged; see "What the old commands print through" below.
- `src/tlaup/context.py`: `AppContext` gets `ui: Ui`; `get_context()` builds it with `Ui.for_process()`.
- `tests/unit/test_context.py` (package 02's): one assertion that the context's `ui` exists, if 02's test builds `AppContext` by hand and now needs the field.
- `pyproject.toml` and `uv.lock`: the Rich floor becomes `rich>=13.8.0`, the first release with `Console.on_broken_pipe` ([30 B2](../design/30-ci-and-release.md#b2-build-fixes)). The cap `<14` is left for [56](56-build-and-metadata.md), which owns the bounds; the lock already holds 13.9.4, so the lock changes only in its recorded requirement.

Deletes: nothing.

Shared with packages of the same group: `src/tlaup/context.py` with [17](17-error-handler.md) (the context builder) and [19](19-layered-config.md) (the `settings` field), one field or function each; `pyproject.toml` and `uv.lock` with [17](17-error-handler.md) (the Typer floor) and [56](56-build-and-metadata.md), one dependency line each.

## Interfaces

Provides, from [14 F6](../design/14-config-and-cli.md#f6-messages):

```python
# tlaup/ui.py
ColorPolicy = bool | None           # written by stage 4: None decides per stream; True always; False never

class _PipeConsole(Console):         # rich.console.Console; the only console class tlaup builds
    def on_broken_pipe(self) -> None:
        raise BrokenPipeError        # Rich's own version points stdout at the null device and exits 1 (F10)

class Ui:
    def __init__(self, stdout: TextIO, stderr: TextIO, stdin: TextIO, *, color: ColorPolicy,
                 env: Mapping[str, str], interactive: bool | None = None,
                 terminal: bool | None = None, size: tuple[int, int] | None = None): ...
    @classmethod
    def for_process(cls) -> "Ui"                # the real three streams and os.environ; needs no settings, raises nothing
    out: Console                 # results; a _PipeConsole on stdout
    err: Console                 # everything else; a _PipeConsole on stderr
    def error(self, message: str, *, hint: str | None = None, details: str | None = None) -> None
    def warning(self, message: str) -> None
    def note(self, message: str) -> None        # what tlaup did: "Pinned v1.7.4@5a47802"
    def result(self, renderable) -> None        # to stdout
    def ask(self, question: str, *, choices, default) -> str      # prompt on stderr, answer from stdin
    def is_interactive(self) -> bool            # the argument if given; else stdin and stderr are both terminals
```

`ColorPolicy` is named in F6 and defined nowhere. [01 T5](../design/01-testing.md#t5-feature-files-and-steps) builds a `Ui` with `color=False`, so stage 4 makes it `bool | None`: `None` (what `for_process` passes) colours a stream only when it is a terminal and `NO_COLOR` is unset in `env`; `False` never colours; `True` always does. Milestone 4's `--color auto|always|never` maps onto the three values. For `ask`, stage 4 writes the types `choices: Sequence[str]` and `default: str | None`.

`AppContext.ui: Ui` (field added to 02's dataclass).

Consumes: `CannotAsk` (02); `AppContext`, `get_context` (02).

Used later by: the handler (17), the settings warnings (19), the first-run prompt (28), every command package, the reporters (36, 38, 40), which take `ui.out` and `ui.err` and build no console of their own ([22 O1](../design/22-reporters.md#o1-reporter-interface)).

## Tests that must pass

Plain pytest in `tests/unit/test_ui.py`, every `Ui` built on `io.StringIO` streams through the constructor (no patching, [01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 2):

- Each kind of message (`error` alone, `error` with `hint`, `error` with `details` of two lines, `warning`, `note`, `result`) rendered with `color=False` and with `color=True, terminal=True`, compared with expected files through `assert_matches`. The colour-on files hold the escape sequences; they are reviewed as files.
- With `NO_COLOR=1` in `env`, `color=None` and `terminal=True`: the output of every kind has no escape sequence at all (no colour and no bold).
- Text from outside tlaup is not markup: an `error` whose message is `[red]x[/red] [bold]` prints those characters as they are ([10 P11](../design/10-parser.md#p11-tlc-text-and-rich-markup)).
- A message longer than the console width stays on one line (see Context).
- `ask`, on in-memory streams: a valid answer is returned; an invalid one and then a valid one asks twice (the question appears twice on stderr); a line holding only a newline gives the default; an empty read raises `CannotAsk`; the question is on stderr and stdout stays empty.
- `is_interactive()` is false on in-memory streams and true with `interactive=True`.
- A `_PipeConsole` writing to a file object whose `write` raises `BrokenPipeError` lets `BrokenPipeError` out (and does not raise `SystemExit`).
- `Ui.for_process()` raises nothing with `TERM=dumb`, and its streams are the process's `sys.stdout`, `sys.stderr` and `sys.stdin` at the time of the call.

The real-pty scenario of F6 (`tool uninstall rolling` with two builds asks on a pty, and with stderr redirected to a file does not ask) needs the new `tool uninstall`; it is [29](29-tool-commands.md)'s. "Feature assertions on stream and content throughout" is every command package's.

Old tests: none. The old suite was deleted in 03b ([03](03-test-foundation.md), [01 T11](../design/01-testing.md#t11-the-existing-tests), decision D62). No row of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) names this package as its owner; P6 (the symbols) is changed on purpose by F6, and its entries are written where the user first sees them (Changelog).

No stateful test applies.

## Changelog

None in this package. F6's entries describe what a user sees once the commands print through `Ui`, which happens command group by command group:

- "A warning from `tool list` went to stdout." (Fixed): [29](29-tool-commands.md).
- "Messages have the form `error: ...`, `warning: ...`, `hint: ...` on stderr, without symbols." (Changed) and "`NO_COLOR` is honoured everywhere." (Fixed): [50](50-help-and-messages.md), the package after the last command is converted.

## Context for the worker

**What the old commands print through after this package.** Today's `ui.py` has four functions, `warn`, `error`, `info` and `success`, which print with a symbol and a capitalised word through `typer.echo` on stderr; eight modules call them, and many other places call `typer.echo` or build a `Console()` directly. **Keep the four functions exactly as they are, beside `Ui`.** Do not route them through `Ui`. Reasons:

- Routing them through `Ui` is work on code that is about to go: each old command is rewritten by its switch package, and nothing promises that an old command keeps its output until then (decision D62, [00, "What every package must respect"](../design/00-overview.md#what-every-package-must-respect)). Leaving them as they are keeps this package small and its review about `Ui` alone.
- The build-beside rule: the old commands are rewritten by their switch packages, which convert their own call sites to `ctx.ui` or to a raised error ([00](../design/00-overview.md), "What every package must respect"; the brief's cut). A switch package deletes each old function when it deletes the function's last caller. Today's callers: `versioning/paths.py`, `versioning/api.py`, `versioning/metadata.py`, `cache/github.py`, `cmd/tools/uninstall.py`, `cmd/tools/meta/sync.py` (all gone with 29), `java/inspector.py` (gone with its last user, 39 or 46), `cmd/tlc.py` (39).
- So between this package and the last switch, `main` mixes two message forms. That is allowed: `main` need only be green between packages, and nothing is released in between (D6, D62).

**The message format** (F6):

```
error: no version pinned
hint: run `tlaup tool pin v1.7.4`
warning: config.yaml: unknown key "workspace" (ignored)
```

- Lower-case prefixes, no symbols (`✖ ⚠ ✔` go). `error:` red, `warning:` yellow, `hint:` cyan. Only the prefix is coloured.
- One line per message; `details` follow, each line indented by two spaces. `note` has no prefix and no "Success:".
- All four of `error`, `warning`, `hint` and `note` go to stderr; `result` to stdout ([02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr)).

**Traps.**

- **No markup from outside.** Print every message with markup, emoji and highlighting off, building the coloured prefix as a styled `rich.text.Text` rather than as markup in a string. A file name with `[` in it or TLC text must print as it is.
- **One line means one line.** Rich wraps at the console width (100 columns under the isolation fixture). A long path in a message must not be broken across lines; print messages with `soft_wrap=True` (or the equivalent) so the line is left for the terminal to wrap.
- **"No escape sequences" means none.** Rich's `no_color` removes colours and keeps bold and other styles. With colour off, build the console so that it emits no style at all (`color_system=None`), and test it.
- **Rich reads the process environment itself.** It reads `NO_COLOR`, `FORCE_COLOR`, `TERM`, `COLUMNS` and `LINES` from `os.environ`, not from the `env` argument. Pass `no_color`, `color_system`, `force_terminal`, `width` and `height` explicitly from what `Ui` decided, so `env` is what decides. The isolation fixture sets `NO_COLOR=1`; a colour-on test removes it with `monkeypatch.delenv` as well, because tlaup does not use Rich's private `_environ` argument for the sake of a test (F6). `terminal=True` and `size` become Rich's public `force_terminal`, `width` and `height` on both consoles.
- **`ask` reads with `readline` from the `stdin` it was given.** No `typer.prompt`, `typer.confirm` or Rich prompt: Typer's raise `typer.Abort` at end of input, which F10 maps to 130, and they read the process's real stdin. An empty read is end of input and raises `CannotAsk`; a line that is only a newline takes the default; an answer that is not one of the choices is asked again; `KeyboardInterrupt` is not caught (F10 turns it into 130). Compare an answer to the choices after stripping surrounding white space, and say in the pull request what else was decided (case, how the choices and the default are shown in the question).
- **`is_interactive`** is the `interactive` argument when given; otherwise both stdin and stderr are terminals (the question goes to stderr, the answer comes from stdin). A command that would ask and finds it false raises `CannotAsk`, a usage error naming the option, or takes its documented non-interactive path; that is the caller's choice, not `Ui`'s.
- **`for_process` takes the streams at call time** (`sys.stdout`, `sys.stderr`, `sys.stdin` as they are when it is called), so a context built inside a `CliRunner` call prints into that call's captured streams. It passes none of the three test arguments, so in a real process a stream is never treated as a terminal when it is not one. It also sets `errors="replace"` on the real stdout and stderr where the stream supports `reconfigure` (R3), so a character the output encoding lacks prints as a replacement instead of raising. Guard it: under `CliRunner` the streams are not `TextIOWrapper`s.
- **`for_process` needs no settings and raises nothing.** The handler of [17](17-error-handler.md) uses it when the context could not be built (for example `TLAUP_HOME` is a relative path).
- **The context.** `get_context()` builds `Ui.for_process()` when it builds the context. Package 17 adds a builder that the root callback calls once per run of the app; that is what gives each in-process test call its own streams. Do not cache a `Ui` anywhere else.
- **Startup cost** ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)): `ui.py` may import `rich.console` and `rich.text` at the top; it must not import `rich.live`, `rich.progress` or `typer` beyond what the old functions already need. Package 49's test checks the list.

**Decisions this rests on.** D30 (stdout carries the result, stderr everything else, prompts on stderr with the answer from stdin). The design agent's decision to drop the symbols (they cannot be encoded on some terminals; [README, decisions the design agent made](../design/README.md#decisions-the-design-agent-made)). D15: nothing here is platform-specific; `isatty` works on Windows.

**State of `main` when this starts.** Release 0.8.x commands; `tlaup/errors.py`, `tlaup/paths.py` and `tlaup/context.py` (02); the isolation fixture and the fakes (03), and no old test under `tests/unit/` or `tests/integration/` (03b). No handler maps errors yet (17).

## Done when

- `Ui` and `_PipeConsole` exist as above; `AppContext.ui` exists; `mypy` strict passes.
- The tests above pass.
- The four old functions in `ui.py` are byte-for-byte unchanged.
- `uv run poe lint` and `uv run poe test` pass; CI is green.

## Out of scope

- Converting any old call site: the switch and command packages (29, 31, 39, 44, and 41 to 47 for new commands).
- The error handler and how it prints an error: [17](17-error-handler.md).
- The `print` and `Console(` lint rules: [58](58-lint-rules.md) (58c).
- `--color`, `--quiet`, `--verbose`: milestone 4.
- The live layout's use of the consoles: [38](38-terminal-reporter.md), [40](40-live-display.md).

## Risks

- From F6: scripts that matched `Error:` with a capital; the changelog entry (written by 50) covers it.
- From the cut: two message forms live side by side until the last old command is converted. The old functions are deleted one by one with their callers; if one survives the last switch, [58](58-lint-rules.md)'s rule against `typer.echo` outside the reporters still allows it in `ui.py`, so [48](48-command-tree.md) checks that none is left, and [50](50-help-and-messages.md) deletes any it finds.
- Rich decides some things from the process environment whatever tlaup passes; a Rich release that reads a new variable can change the expected files. The expected files and the newest-dependencies job ([30 I3](../design/30-ci-and-release.md#i3-newest-dependencies-job)) show it.
