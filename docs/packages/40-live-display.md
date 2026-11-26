# 40. The live display

Size: L. Suggested model: most capable. Status: 40a built, 40b ready. Delivered as two pull requests, 40a and 40b (see the end).

## Goal

On a terminal, `tlaup tlc` shows the full-screen layout of [22 O4](../design/22-reporters.md#o4-live-display) on stderr while TLC runs, redrawn at `--refresh-interval`, and when the run ends, however it ends, the layout closes and the complete result is printed as plain output. `--plain` and `tlc.plain` give plain output on a terminal. The old, never-rendered layout code is gone (its tests went with the old suite in [03](03-test-foundation.md), decision D62).

## Covers

- Roadmap items, [milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout):
  - "Live terminal reporter: render the layout on a terminal; fall back to plain streamed output when stdout is not a terminal or `--raw` is given." (line 324). In part: the layout and the rule that chooses it; the plain output is [38](38-terminal-reporter.md)'s. Also the milestone's exit criterion "a long TLC run shows a live status on a terminal and clean line output when piped".
  - "Make `--refresh-interval` and the matching config key take effect." (line 328). In full.
  - "Fix the per-line re-rendering cost, which grows with the square of the output, and the unbounded list of output lines kept in memory." (line 329). In part: the layout-mode test and the changelog entry; the plain-mode tests are 38's.
  - "Snapshot tests through a fixed-width, colourless console with an injected clock, replacing assertions on Rich internals." (line 330). In part: the layout half; the plain half is 38's.
  - "Delete display code that nothing in `src/` references ..." (line 323). In part: nothing of the item's own list (package 04 deleted that), but the rows of O2's table marked O4, which this package finishes or replaces and then deletes.
- Design sections:
  - [22 O4](../design/22-reporters.md#o4-live-display): all of it, the waiting line in the Status panel included (question Q12, settled: shown in place of the hint and copied to stderr on close).
  - [22 O5](../design/22-reporters.md#o5-refresh-interval): all of it.
  - [22 O6](../design/22-reporters.md#o6-snapshot-tests): "Drawing without a terminal", "Layout frames", "The two modes give one text", "The two streams", "`close`", the markup test in layout mode, and the waiting line in layout mode. The plain-mode parts are 38's.
  - [22 O7](../design/22-reporters.md#o7-rendering-cost-and-memory): the layout-mode test and the changelog entry.
  - [22 O2](../design/22-reporters.md#o2-delete-dead-display-code): the rows marked O4 (`HeaderComponent`, `StatusInfoComponent`, `LogsComponent`, `StatsTableComponent`, `StatusInfoRenderable`; `TlcDisplay`, `_Section`, the layout functions of `TlcFormatter`; `LogDeduplicator`).
  - [22 O1](../design/22-reporters.md#o1-reporter-interface): the rule inside `make_reporter`; `notice` in layout mode (the protocol method is [36](36-reporter-interface.md)'s, the plain mode [38](38-terminal-reporter.md)'s).
  - [02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr), "Where the live layout is drawn".
  - [01 T5](../design/01-testing.md#t5-feature-files-and-steps), situation 4 for the layout: the screen steps that need a terminal emulator, and `tlc_live.feature`. [01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 5: the one test that depends on the real clock.
  - [14 F1](../design/14-config-and-cli.md#f1-layered-configuration), [F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay): `tlc.plain` and `tlc.refresh_interval` take effect, with their flags; F1's rule that the schema checks the type only and a range is the command's (question Q16, kept as built).
- Rows of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) this package owns: R13 (`--refresh-interval` is accepted, and `tlc.refresh_interval` defaults to 1.0), with its test under part A (finding G1).

## Depends on

- [39](39-tlc-command.md): the new `cmd/tlc.py` (this package adds two options), `make_reporter` and `ReporterOptions` in `reporters/__init__.py`, `tlc/runner.py` (the renamed `run.py`), `tlc_run.feature`'s expected file for `violation`, and the old layout code it left for this package.
- [38](38-terminal-reporter.md): `TerminalReporter` (plain), `render_event`, `render_status`, `header_lines`, `render_summary`, the replay helper and the plain expected files.
- [37](37-run-tlc.md): the frame, unchanged, whose `on_held` already hands the waiting line to `reporter.notice`.
- [36](36-reporter-interface.md): `Reporter` (with `notice`), `RunInfo`, `CollectingReporter`.
- [16](16-ui-messages.md): `Ui` with `terminal` and `size`.
- [18](18-feature-harness.md): the steps, the pty helper (`in a terminal <w> by <h>`, which sets `TERM`, the window size and removes `COLUMNS` and `LINES`), the real-process helpers.
- [19](19-layered-config.md): the settings `tlc.plain` and `tlc.refresh_interval`, `TLAUP_TLC_PLAIN`, `TLAUP_TLC_REFRESH_INTERVAL`.
- [07](07-golden-files.md): the captures `success`, `violation`, `big-states` and their specs.

The draft listed 39 only; the others are what this package uses directly. All are below 39, so the order does not change.

## Files

Creates:

- `src/tlaup/reporters/layout.py`: `LayoutView`, `render_layout`, the four panels, the phase words, `format_clock`.
- `tests/unit/reporters/test_layout.py`; `tests/unit/reporters/expected/layout/<case>-<n>.txt` and the 60 by 15 frame; `tests/unit/reporters/test_make_reporter.py` (or in `test_layout.py`; the worker's choice).
- `tests/features/tlc_live.feature` and its expected files under `tests/features/expected/tlc_live/`.
- In `tests/steps/`: the screen steps of T5 that need `pyte`, unless [18](18-feature-harness.md) wrote them: `the terminal showed the layout`, `the last layout frame contains "<text>"`, `the terminal stayed on the main screen`, `the terminal ends with the expected file "<name>"`, and the When form `I start "<command>" in a terminal <w> by <h> and press Ctrl-C once the terminal has shown "<text>" and then an elapsed time <n> seconds later`.

Changes:

- `src/tlaup/reporters/terminal.py`: the constructor gains `mode`, `interval`, `refresh_thread`, with defaults (below); layout mode with its spools, `Live`, `refresh()`, the `atexit` hook and its `close`; `notice` in layout mode (38's plain `notice` is unchanged).
- `src/tlaup/reporters/__init__.py`: `ReporterOptions` gains `plain` and `refresh_interval`; `make_reporter` gets the rule.
- `src/tlaup/cmd/tlc.py`: the options `--plain` and `--refresh-interval SECONDS`, their help lines, the range check, and the two values passed in `ReporterOptions`.
- `src/tlaup/config/schema.py` and `src/tlaup/resources/default_config.yaml`: only if [19](19-layered-config.md) left out `tlc.plain` (false) or `tlc.refresh_interval` (1.0), or gave the latter a range (see Context, "The range").
- `pyproject.toml` and `uv.lock`: `pyte` as a development dependency, if 18 did not add it.
- `tests/features/tlc_errors.feature` ([39](39-tlc-command.md)'s): O5's usage-error scenarios are added to it. `tests/features/tlc_run.feature` (39's): one scenario for inventory row R13.
- `CHANGELOG.md`.

Deletes ([22 O2](../design/22-reporters.md#o2-delete-dead-display-code)), in the pull request that adds the layout frames:

- `src/tlaup/tlc/formatter.py`, `src/tlaup/tlc/components.py`, `src/tlaup/tlc/models.py`, whole: what [39](39-tlc-command.md) left (`_Section`, `TlcDisplay`, the layout part of `TlcFormatter`, `StatusInfoRenderable`; `LogDeduplicator` and the four panel components; the old models they import). Nothing else imports them by then; mypy and ruff confirm. `LogDeduplicator` goes with them, since the finished Output panel shows the same lines plain mode prints without folding repeats. Their old tests (`tests/unit/tlc/test_formatter.py`) went with the old suite in 03 (D62).

**What this package starts from.** It writes `layout.py` fresh from O4. O2's table says the old components are "rewritten against `RunResult` as the four panels" and `TlcDisplay` is "replaced by `render_layout`, built on Rich's own `Layout`": the old classes read `ModelCheckResult`, compute the elapsed time from the wall clock, fold repeated log lines and grow sections as data appears, and none of that survives a full-screen frame drawn from a `LayoutView`. Read them for what they sketched (the four panel titles, the progress table's columns), import nothing from them, and delete them. After this package `src/tlaup/tlc/` holds only the new modules.

Shared with packages of the same period (41 to 47 run beside this one): `src/tlaup/cmd/tlc.py` with [47](47-completion.md), which adds `autocompletion=` to `SPEC` (finding D9; different lines); `tests/steps/*.py` (each package adds functions); `CHANGELOG.md`; `pyproject.toml` and `uv.lock` (one development dependency line).

## Interfaces

Provides, from [22 O4](../design/22-reporters.md#o4-live-display). Marks say what stage 4 wrote.

```python
# tlaup/reporters/layout.py
@dataclass(frozen=True)
class LayoutView:                       # everything a frame needs; replaced whole on each event
    run: RunInfo
    phase: Phase
    started_at: float                   # reporter's clock
    errors: int
    warnings: int
    progress: tuple[Progress, ...]      # newest 50
    tail: tuple[Text, ...]              # newest 200 lines of the result text and of TLC's stderr
    notice: str | None = None           # the waiting line (O1), shown in place of the hint
    header: tuple[Text, ...] = ()       # stage 4: the header lines (two, or three with TLC's version line)
    interrupted: bool = False           # stage 4: finish got an outcome stopped by a signal

def render_layout(view: LayoutView, now: float, width: int, height: int) -> RenderableType
def format_clock(seconds: float) -> str          # stage 4: "00:02:13", the Status panel's elapsed

# tlaup/reporters/terminal.py
class TerminalReporter:
    def __init__(self, ui: Ui, *, mode: Literal["plain", "layout"] = "plain", interval: float = 1.0,
                 clock: Callable[[], float], refresh_thread: bool = True): ...
                                        # stage 4: defaults for mode and interval, so 38's helper and tests stand
    live: Live | None                   # public, for O5's one test that reads a Rich object
    def refresh(self) -> None           # tests with refresh_thread=False draw a frame themselves
    # start, handle, stderr_line, notice, finish, close as in 38; layout mode below

# tlaup/reporters/__init__.py
@dataclass(frozen=True)
class ReporterOptions:
    plain: bool = False                 # --plain given
    refresh_interval: float | None = None   # --refresh-interval given

def make_reporter(ctx: AppContext, options: ReporterOptions) -> Reporter
```

**The rule in `make_reporter`** (O4, "When it is on"; X2). Layout mode when all hold, else plain mode:

- stdout and stderr are terminals (`ctx.ui.out.is_terminal` and `ctx.ui.err.is_terminal`);
- `TERM` in `ctx.env` is not `dumb`;
- plain output was not asked for: `options.plain` is false and `ctx.settings.tlc.plain` is false (the flag wins over the setting; there is no `--no-plain`, and `TLAUP_TLC_PLAIN=false` is how an environment undoes a `tlc.plain: true` for one run).

O4's interface says the flag is "already merged into" `settings.tlc.plain`, as F1's flags layer would do it. Here `--plain` and `--refresh-interval` travel in `ReporterOptions` and the rule reads both, as [33](33-tlc-invocation.md) does for `--workers` and `--keep` (stage 4's choice, finding C8): what the user sees is the same either way, and the range check has to know whether the value came from the option, the environment or the file to name it. Low impact: internal, and a change later touches no user.

`--raw` never reaches `make_reporter`. The interval is `options.refresh_interval` if given, else `ctx.settings.tlc.refresh_interval`. The clock is `time.monotonic`. The fourth condition of O4, at least 60 columns and 15 lines, is checked by the reporter at `start`, because O4 says the size "is the stderr console's, read once, at `start`": a reporter made in layout mode whose stderr console is smaller writes plain output for the whole run.

**Layout mode** (O4, "How it is built" and the stream table):

- `start` writes `header_lines` to stderr (before the layout opens), makes the two spools (consoles with stdout's width and colour setting, each on a `tempfile.SpooledTemporaryFile` held in memory up to 1 MiB), registers the `atexit` hook, and starts `Live(console=ui.err, screen=True, get_renderable=..., refresh_per_second=1 / interval, redirect_stdout=False, redirect_stderr=False)`, recording each thing as it takes it. With `refresh_thread=False` the `Live` does not refresh by itself.
- `get_renderable` calls `render_layout(self.view, clock(), width, height)` with the size read at `start`; the refresh thread only reads the current view and the clock. The reporter replaces `self.view` with a new frozen `LayoutView` on each event and never changes one in place.
- `handle`: the lines of `render_event` go to the stdout spool and into the view's `tail`; `render_status`'s lines go to the stderr spool (TLC's version line also into `header`); `ProgressMade` goes into `progress` and the Status panel and is not printed; phase, errors and warnings come from the live result.
- `stderr_line`: to the stderr spool, and into `tail` marked `stderr:`.
- `notice` (O1, O4's stream table): into the view's `notice` (the Status panel shows it in place of the Ctrl-C hint) and to the stderr spool, in arrival order with the tool's stderr lines, so it is copied to stderr with them when the layout closes and is still on the terminal after the layout is gone. In plain mode it is written to stderr at once ([38](38-terminal-reporter.md)).
- `finish`: `render_summary` into the stdout spool and the tail, the view's phase to `FINISHED` or `interrupted` set when `outcome.stopped_by` is set, one `refresh()` (Rich does not refresh on stop on the alternate screen, so this draws the last frame), then `close()`.
- `close`, idempotent and never raising: stop `Live` (which leaves the alternate screen), copy the stderr spool to stderr, then the stdout spool to stdout, delete the spools, remove the `atexit` hook. It releases only what `start` recorded. A write that fails while copying stops writes to that stream, the rest is still released, and the first such error is kept in `write_error`. Without `finish` (the middle of `run_tlc` raised) it does the same three steps with what the spools hold: the layout is gone before the `error:` line is printed, and no statistics or result line are written.
- Copy the spools as text, unchanged, to the underlying streams of `ui.err` and `ui.out`; do not print them through the consoles again, which would re-render them.

**The four panels** (O4's mock-up is the reference; `render_layout` builds them on Rich's `Layout`):

- Header: `view.header`.
- Status, four lines: the phase word, `elapsed` and `format_clock(now - started_at)`, `errors N   warnings M`; the latest progress numbers; the hint `Ctrl-C to interrupt`, or `view.notice` when set. Phase words: `PARSING` `Parsing`, `INITIAL_STATES` `Computing initial states`, `CHECKING` `Checking`, `LIVENESS` `Checking liveness`, `FINISHED` `Finished`, and `Interrupted` when `view.interrupted`. Before TLC reports anything (`NOT_STARTED` and `STARTING`) the word is `Starting`, as settled with the maintainer on 2026-11-24 and written into O4.
- State space progress, up to a third of the height: one row per progress message, newest that fit, columns `Time`, `Diameter`, `Generated`, `Distinct`, `Queue`, numbers with thousands separators.
- Output, the rest: the newest lines of `tail` that fit, each cut with an ellipsis when longer than the panel (only here is anything cut).

**The waiting line under the layout** (question Q12, settled; [22 O1](../design/22-reporters.md#o1-reporter-interface), O4). [14 F6](../design/14-config-and-cli.md#f6-messages) says nothing prints through `ui` while a reporter is between `start` and `close`, and under the alternate screen a line printed there would be lost. So the line goes through the reporter: [36](36-reporter-interface.md) put `notice` in the protocol, [37](37-run-tlc.md)'s `on_held` calls `reporter.notice(waiting_line(name))`, [38](38-terminal-reporter.md)'s plain mode writes it on stderr at once, and this package's layout mode shows it in the Status panel and copies it to stderr on close. The reminder line stays on the command's `notice`, since it is printed before `reporter.start`.

**`--refresh-interval SECONDS`** (O5): default from `tlc.refresh_interval` (1.0); how often the layout is redrawn and the elapsed time ticks. Below 0.1 or above 60 is a usage error, exit 2, from the option (Typer's own range check) and from the environment variable or the config key (tlaup's `UsageError`, naming where the value came from, raised before the preflight with the other command-line checks of [11 R11](../design/11-runner.md#r11-preflight), step 0). The schema checks only that the value is a number ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration), question Q16, kept as built): `fast` in the file is `ConfigInvalid` (3), `100` is the command's 2. No effect in plain mode or with `--raw`; the help says so in one line. **`--plain`**: plain output on a terminal; with `--raw` no effect, and the help says so.

Consumes: listed under Depends on.

## Tests that must pass

### A. In-process: the reporter, the layout, `make_reporter`

Plain pytest, a reporter driven with events and in-memory consoles ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests), rule 1). **Drawing without a terminal** (O6): every test named "layout mode" builds its `Ui` with `terminal=True, size=(100, 30)` (or the size it names) on `StringIO` streams, colour off, and sets `TERM=xterm-256color` with `monkeypatch`; under the isolation fixture's `TERM=dumb` Rich's `Live` writes no enter sequence and no frame at all, even on a console forced to terminal mode (tried on the locked Rich 13.9.4: 0 frames against 4). They use [38](38-terminal-reporter.md)'s replay helper, `refresh_thread=False` and a clock that advances one second per event.

`tests/unit/reporters/test_layout.py`:

- **Layout frames** (O6): for `success`, `violation` and `big-states`, `render_layout` is called on the reporter's view after `start`, after half the events and after the last event, each frame printed to a `StringIO` console of 100 by 30 with colour off and compared with `expected/layout/<case>-<n>.txt`; one frame at 60 by 15. O6 names no build for these files; use the v1.7.4 captures, since the rolling folder is replaced whenever a newer rolling capture lands (01 T3).
- **The two modes give one text** (O6): for the same three cases, a reporter in layout mode run to `finish` writes to stdout exactly 38's plain expected stdout file of the case. No second expected file exists for it.
- **The two streams** (O6, D30, D40): in the same runs, the stdout stream holds no escape sequence and nothing before `close`; the stderr stream holds the header before the enter sequence of the alternate screen, the enter and leave sequences once each, the panel titles between them, and after the leave sequence the tool's stderr lines and nothing of the result text. With two literal lines given to `stderr_line` (plain text, not TLC output, so rule 3 allows them), they stand after the leave sequence, in order, unmarked.
- **`close`** (O6), in layout mode: after `start` and a few events with no `finish`, it writes the leave sequence, then the result text so far to stdout, and no result line; a second call, and a call on a reporter never started, write nothing. With a stderr stream that raises on the first write of the enter sequence (so `start` fails after the spools exist and before the display starts), `close` returns, no spool file is left in the temporary folder (point `tempfile.tempdir` at a test folder with `monkeypatch`, or list the folder; the spools must be on disk for that, so write more than 1 MiB first or use a small `max_size` through a constructor argument that production does not pass, and say which in the pull request), and no leave sequence is written. With a stdout stream that raises `BrokenPipeError`, `close` returns, the leave sequence is in the stderr stream, and `write_error` is that error. Through `run_tlc` ([37](37-run-tlc.md)) with a Java command whose executable does not exist: the leave sequence is in the stderr stream when the `ToolStartError` leaves `run_tlc`.
- **The markup test of [10 P11](../design/10-parser.md#p11-tlc-text-and-rich-markup)** in layout mode: the four strings of 38's test, as `OutputLine` events; the Output panel of a frame shows them as text, and the stdout written at `close` equals the input.
- **O5**: started with `interval=0.5` and then with `interval=2`, `reporter.live.refresh_per_second` is 2 and then 0.5. This is the one place a test reads a Rich object (O5, O6). Inventory row R13: with no option and no setting (19's defaults), `make_reporter` in layout mode gives `refresh_per_second` 1, and `--refresh-interval 0.5` is accepted: an in-process scenario added to [39](39-tlc-command.md)'s `tlc_run.feature`, `tlaup tlc Spec --refresh-interval 0.5`, exits with the replayed case's code. With the injected clock, two `refresh()` calls one clock-second apart show `elapsed` values one second apart.
- **O7**, layout mode: 300,000 numbered lines (`line 1` ...) through a `TlcParser` into the reporter leave a view whose `tail` has 200 lines; the stderr stream holds only the frames drawn by `start`, the test's own two `refresh()` calls and `finish`, a number that does not grow with the events (count them by Rich's frame start in the stream, without reading Rich internals); and the stdout written at `close` has 300,000 lines. No test measures time.
- **The size, read at `start`**: a layout-mode reporter on 59 by 15 and on 60 by 14 writes plain output (no enter sequence; the output equals plain mode's); 60 by 15 draws the layout.
- **The waiting line** (O6): in layout mode a `notice` shows the line in the Status panel of the next frame, in place of the hint, and after the leave sequence it is in the stderr stream with the tool's stderr lines, in arrival order; stdout has nothing of it. The plain-mode half is 38's test.

`tests/unit/reporters/test_make_reporter.py`: an `AppContext` built in the test with a `Ui` forced to terminal mode on both streams and `TERM=xterm-256color` gives layout mode; each of these gives plain mode: `--plain` (`ReporterOptions(plain=True)`), `tlc.plain: true` in the settings, the same from `TLAUP_TLC_PLAIN=1`, stdout not a terminal, stderr not a terminal, `TERM=dumb`. The interval comes from the option when given, else the setting.

`tests/features/tlc_errors.feature`, in-process (O5): `tlaup tlc Spec --refresh-interval 0` and `--refresh-interval 100` exit 2; with no option, `TLAUP_TLC_REFRESH_INTERVAL=0` and a config file with `tlc.refresh_interval: 100` exit 2. Each starts no Java (`java was not started`).

### B. Real processes on a terminal: `tests/features/tlc_live.feature`

Real processes on a pty ([01 T5](../design/01-testing.md#t5-feature-files-and-steps), situation 4), Linux and macOS; skipped with the reason where there is no `pty` module (Windows). The pty steps set `TERM=xterm-256color` and the window size and remove `COLUMNS` and `LINES` from the child's environment (T2): the fixture's `TERM=dumb` would switch the layout off, and Rich would take `COLUMNS=100` and `LINES=40` over the pty's size, so the "too small" scenario would pass or fail for the wrong reason. The screen steps replay the bytes through `pyte` (0.8.2 was tried by research 30), cut at the enter and leave sequences of the alternate screen, which `pyte` does not model.

- **The last frame and the scrollback.** `violation` on a pty of 100 by 30: `the terminal showed the layout` (the enter sequence, at least one screen between the two sequences with the four panel titles, the leave sequence; nothing about how the run ended); `the last layout frame contains "Finished"` and the same step for the final counts; `the terminal ends with the expected file "tlc_live/violation.txt"` (the screen after the leave sequence: the header, TLC's stderr lines if any, and the plain result text).
- **The display updates while TLC is silent.** The one test whose result depends on the real clock (T12, rule 5, names it). `java replays "tlc/v1.7.4/big-states" with exit code 0`, `java pauses 20 ms between lines`, `java hangs after line 31` (line 26 starts 2190, which sets `Checking`; lines 29 to 31 are the first progress message; the fake is silent from about 0.6 seconds in). `I start "tlaup tlc Big --refresh-interval 0.2" in a terminal 100 by 30 and press Ctrl-C once the terminal has shown "Checking" and then an elapsed time 2 seconds later`. Then: the exit code is 130; the terminal showed the layout; the last layout frame contains `Interrupted`; the terminal ends with the result line `Result: incomplete, interrupted after ...` (see Context, "The interrupted line"). Each wait has a timeout of ten seconds and fails with the last screen it saw. The interval is 0.2 seconds so that a display stuck at one frame per event cannot pass by luck; comparing two `elapsed` values read from the screen, not a literal `00:00:02`, keeps it true on a slow runner.
- **Stdout redirected.** `I run "tlaup tlc Violation" in a terminal 100 by 30 with stdout redirected to "out.txt"`: `the terminal stayed on the main screen`, the terminal has the header and plain progress lines, and `the file "out.txt" matches the expected file "tlc_run/violation.txt"` (39's) and holds no escape sequence.
- **Too small.** A pty of 50 by 10: plain output, `the terminal stayed on the main screen`.
- **Plain asked for.** 100 by 30 with `--plain`: `the terminal stayed on the main screen`, the header and plain progress lines are on it. The same with `TLAUP_TLC_PLAIN=1` and no flag. With `--raw --plain` the run is a raw run: the exit code is the fake's and the terminal holds the raw stdout.

An error raised while the layout is up has no pty scenario: with the fake `java` every way to make `run_tlc` fail after `start` fails the preflight first, and a step that reached into the process would be a seam (O4). It is the `close` test through `run_tlc` in part A.

Old tests: none (D62). No stateful test applies.

## Changelog

Added (O4): "On a terminal `tlaup tlc` shows a full-screen live view while TLC runs: the build and spec, the current phase and elapsed time, the state-space progress table and the newest output. When the run ends the view closes and the complete result is printed, so it stays in the scrollback. When output is redirected or piped, output is plain as before; `--plain`, or the setting `tlc.plain`, gives plain output on a terminal too."

Fixed (O5): "`--refresh-interval` and `tlc.refresh_interval` had no effect. They now set how often the live view is redrawn."

Fixed (O7): "Runs with a lot of printed output became slower and slower and used more and more memory."

O7's entry is written here rather than at [39](39-tlc-command.md), whose list does not have it: plain output stopped re-rendering at 39, and the layout is the other half of the fix. Nothing is released in between (D6). O6 has no entry.

## Context for the worker

**Decisions.**

- D3, D40: the full-screen layout, finished, as one reporter mode among several; not a one-line footer (the first design's, rejected by the maintainer).
- D30: the layout is a live status, so it is drawn on stderr; it also takes over the screen the result would scroll on, so it needs stdout to be the terminal too. With stdout redirected the user gets plain progress lines and the result in the file.
- D9: nothing is lost. The spools keep every line while the layout is up, and `close` prints them on every way out, before the application prints an `error:` line.
- D8: the reporter holds its own state; the layout reads nothing the result does not carry.
- D15: no pty and no Windows console in CI; `Live` on a Windows console was not tried.

**What was tried, and on what** (O4's opening paragraph, restated). On the locked Rich 13.9.4, in memory, forced to terminal mode: `Live(screen=True)` writes the enter and leave sequences and frames between them; its refresh thread redraws a changed `get_renderable` value with no call from outside; `Live.stop` does not refresh on the alternate screen; the console takes its size from `COLUMNS` and `LINES` when set; `Live.refresh_per_second` holds the constructor's value. Research 30 ran the first three on a real pty with Rich 13.8.0, 13.9.4, 14.0.0, 14.3.4 and 15.0.0 on Linux, and all but 14.0.0 on macOS, and `pyte` 0.8.2 followed each: four panel titles on one screen, 12 to 14 frames from the refresh thread in 1.5 seconds, the `…` of a cut line, the plain text after the leave sequence. Colours: `pyte` calls bold green `brightgreen`. Not tried: resizing while the layout is up, a Windows console.

**The range** of `--refresh-interval` (question Q16, settled as [19](19-layered-config.md) and this package build it). O5 makes 0 and 100 usage errors (2) also when they come from the environment or the config file, and F1 now says the schema checks the type only and a rule beyond it is the command's, which gives 2 wherever the value came from. So the schema carries no range; if [19](19-layered-config.md) gave it one, move it to the command and say so.

**`TERM`.** O4 says "`TERM` is not `dumb`". Rich treats `unknown` like `dumb` too; check the locked Rich, and if a `Live` writes no frames under `TERM=unknown`, treat it as `dumb` in `make_reporter`, or the layout would be chosen and draw nothing.

**The interrupted line.** O4's pty scenario and O3's table agree now (index "Clerical"): the terminal ends with the result line of an interrupted run, which starts `Result: incomplete, interrupted after`.

**Who may print while the layout is up.** Between `start` and `close` only the reporter writes, and only `Live` reaches a real stream. The preflight's warnings and the kept-folders reminder come before `start`; the waiting line goes through `reporter.notice` (above); "Checkpoint kept", the dropped checkpoint of a raw run and the disagreement warning are printed by `print_run_notes` after `close`; the application's `error:` line after the frame has closed the reporter.

**Leaving the alternate screen in every case.** `close` runs on every path out of `run_tlc`: a normal end, one or two Ctrl-Cs, SIGTERM, any exception. It stops `Live` first and only then writes. The `atexit` hook registered at `start` stops `Live` if it is still running, for a caller other than `run_tlc` that forgets `close`; `close` removes it. With D60 a Ctrl-C typed at the terminal reaches tlaup alone in a parsed run, so the layout stays up until `finish` draws `Interrupted`.

**Thread rule.** The refresh thread reads `self.view` and the clock only. Replacing one reference to a frozen value is safe in CPython; never mutate a view in place, and never let the thread touch the spools or the parser.

**Traps.**

- `pyte` does not model the alternate screen; the steps cut the byte stream at the two sequences and replay the parts separately.
- The pty steps remove `COLUMNS` and `LINES`; an in-process test that forgets `TERM=xterm-256color` sees no frames at all and its expected files would be empty.
- The two-modes test compares with 38's plain expected file: a change to plain output regenerates that file and this test follows it, with no second file to update.
- `refresh_per_second` is a float: `1 / 0.2` is `5.0`, `1 / 60` is small; Rich accepts both (O5 tried the attribute on the locked version only).
- A spool console must not be one of `Ui`'s: it writes to a temporary file, and a closed pipe cannot happen there. The copy at `close` is where a closed pipe shows, and it is held in `write_error`.

**State of `main` when this starts.** `tlaup tlc` runs on the new chain with plain output everywhere (39); the waiting line already reaches `reporter.notice` and is on stderr in plain mode. `src/tlaup/tlc/` holds the new modules plus the three old files 39 left for this package, with no test; `--plain` and `--refresh-interval` are not declared.

**Known gaps the design postpones.** Keys for scrolling the Output panel (rejected: stdin in raw mode fights Ctrl-C and piped input); a progress bar (TLC does not know the total); resizing while the layout is up; `--json` on a terminal (milestone 4 decides whether it draws the layout). Ctrl-Z under the alternate screen (SIGTSTP is not forwarded, a postponed gap of the launcher).

## Done when

- Parts A and B pass; part B on Linux and macOS in CI. `uv run poe lint` and `uv run poe test` pass; CI is green; `uv run poe test-clean` leaves the home folder empty.
- `src/tlaup/tlc/formatter.py`, `components.py` and `models.py` are gone; nothing imports them.
- The three changelog entries are under `## [Unreleased]`.
- The pull request shows the "updates while silent" scenario failing with the refresh thread switched off (`refresh_thread=False` passed by `make_reporter` for one run of the red build), which is the defect only that scenario catches (T12 rule 6); lists the steps it added with the reason for each; says which build the layout frames use, how the spool-file test makes the spools reach the disk, and whether `TERM=unknown` needed the rule above, and names the inventory row it owns (R13).
- A reviewer can read every frame file and `tlc_live/violation.txt` as what a user sees.

## Out of scope

- Plain output, the result line, `render_event` and the plain expected files: [38](38-terminal-reporter.md).
- The command's other options, `print_run_notes`, the switch and the tlc feature files other than the O5 scenarios added to `tlc_errors.feature`: [39](39-tlc-command.md).
- The frame of `run_tlc`, `on_held` and `waiting_line`: [37](37-run-tlc.md). `notice` in the protocol and in plain mode: [36](36-reporter-interface.md), [38](38-terminal-reporter.md).
- The tree test that checks `tlc`'s options: [48](48-command-tree.md). Help wording beyond the two lines named above: [50](50-help-and-messages.md).
- The JSON reporter and `--json`: milestone 4.

## Risks

From O4:

- A process killed with SIGKILL, or a crash of the interpreter, leaves the terminal on the alternate screen and loses the spools; the lines were on screen when they arrived, and `reset` restores the terminal. Not avoidable from inside the process.
- A run that prints gigabytes writes them twice, to the spool and to stdout at the end. Accepted: such a run is normally redirected, which is plain mode.
- During the run a long trace is visible only as the tail that fits the Output panel; `--plain` is for whoever wants the whole text as it arrives.
- The refresh thread reads a value another thread replaces; the code must not mutate a view in place.
- Resizing and a Windows console were not tried; the newest-dependencies job and the pty scenarios guard a later Rich.
- The layout can be idle for up to a minute between progress rows (research 31), longer during a checkpoint or a slow state; the elapsed time ticks from the refresh thread, so a silence never reads as a hang.
- TLC's stderr lines lose their place among the output lines in the scrollback; during the run the Output panel shows them where they arrived.

From O5, O6, O7: frame files change whenever the layout is adjusted, which is their purpose. The temporary file of a very long run can fill the temporary folder; the write error is reported like any other failed write and the run's own exit code is kept.

From the cut:

- The package is large: a new reporter mode with spools and a thread, a module of panels, `make_reporter`'s rule, two options and a setting, a new development dependency, five pty scenarios with new screen steps, and a deletion. It is two pull requests (below); the protocol and the frame already carry the waiting line, so neither touches 36's or 37's files.
- The "updates while silent" scenario runs for about three seconds of real time and depends on the runner's scheduling within ten-second timeouts; it is the only such test.

## Pull requests (decided by stage 4)

This package is delivered as two pull requests, along the line between parts A and B of its Tests section; the index lists them as 40a and 40b.

- **40a**: layout mode and `layout.py`, the rule in `make_reporter`, `--plain` and `tlc.plain`, the waiting line in the Status panel, the deletion of the old layout code, and the O4 and O7 entries (the reporter takes `interval` from `tlc.refresh_interval` already).
- **40b**: `--refresh-interval` with its check, scenarios and O5 entry; `pyte`, the screen steps and `tlc_live.feature` (the silent-display scenario needs the option, so it is here). Depends on 40a.

A package that names 40 as a dependency waits for 40b.
