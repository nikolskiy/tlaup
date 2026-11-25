# 48. The command tree as a whole, `-V`, and the end of tlaup's own exit 1

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

The registered commands are exactly the signed-off tree of [23 C1](../design/23-command-layout.md#c1-command-tree), registered explicitly in one place in `cli.py`, with no one-letter option but `-V`, and a unit test fails when the tree and the design differ; `tlaup -V` and `tlaup --version` print the two lines of [23 C4](../design/23-command-layout.md#c4-version-flag); every removed name exits 2; nothing old is left registered or importable; and a test makes "tlaup never returns 1 itself" ([02 X1](../design/02-cross-cutting.md#x1-exit-codes) rule 1) a checked fact.

## Covers

- Roadmap items:
  - "Review the layout of every command so it follows the most common CLI patterns and users can guess commands from other tools. No aliases for old command names (decision D14). ..." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 334), in part: the tree as a whole, its test, the removed names, the root options. Each group's commands are their packages' (29, 31, 39, 41 to 47).
  - "Move the version flag to `-V` so `-v` can mean verbose (note 42)." (line 341), in full.
  - "Housekeeping (raised list), done when each area is touched: ... one command registration style, the explicit one; ..." ([milestone 5](../roadmap.md#milestone-5-structure), line 500), in part: the explicit registration style.
  - "Exit codes: documented; ... 2 for usage errors that are hand-written today; non-zero when an operation failed; ..." ([milestone 4](../roadmap.md#milestone-4-automation-surface), line 481), in part: the check that no own exit 1 is left. The mapping is [17](17-error-handler.md)'s.
- Design sections:
  - [23 C1](../design/23-command-layout.md#c1-command-tree): the tree; the root options paragraph; "With no command, `tlaup` prints the root help on stdout and exits 2, and a group alone ... does the same"; the rows "Registration is explicit and in one place", "No `ls`, `rm` or other short forms", "The short options `-f` and `-y` are removed" (the check), "`SPEC` is a required argument ... `VERSION` of `pin`; `NAME` of `module remove`" (the check); the Tests' unit test, the no-command scenarios and the removed-name scenarios; the Changelog's rule "one line per row" as a check.
  - [23 C4](../design/23-command-layout.md#c4-version-flag), in full apart from the summary line's source, which is [50](50-help-and-messages.md)'s ("the same text the root help shows").
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes), rule 1: the check that it holds everywhere; and X1's Breaking changelog entry on exit codes, which becomes true here, where tlaup's own exit 1 ends (review finding B10).
  - The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md), rows P2 (`--version` prints two lines from the package metadata, C4) and P4 (`tlaup` or a group with nothing after it prints help, X1 rule 7 and C1): their tests are here.

## Depends on

- Every command package, so the tree is complete: [29](29-tool-commands.md) (`tool`), [31](31-module-commands.md) (`module`), [39](39-tlc-command.md) (`tlc`), [40](40-live-display.md) (`tlc --plain` and `--refresh-interval`, which the tree lists and the test counts), [41](41-sany-command.md), [42](42-pcal-command.md), [43](43-repl-command.md) (`sany`, `pcal`, `repl`), [44](44-config-commands.md) (`config`), [45](45-cache-commands.md) (`cache`), [46](46-doctor.md) (`doctor`), [47](47-completion.md) (`completion`).
- [17](17-error-handler.md): the root callback with `--debug`, the eager version callback printing through `Ui.for_process()`, `own_exit`, `main()`.
- [16](16-ui-messages.md): `Ui`; the four old functions of `ui.py` (`warn`, `error`, `info`, `success`) that it kept for the old commands and that this package checks are gone.
- [18](18-feature-harness.md): the steps and `errors.feature`, where the scenarios go.

Change from the draft (29, 31, 39, 41, 42, 43, 44, 45, 46, 47): 40 is added, since the tree test counts its two options; 17, 16 and 18 are named for what this package uses.

## Files

Creates:

- `tests/unit/test_command_tree.py`: the tree test, the one-letter test, the version test, the registration test (Tests).
- `tests/unit/test_no_own_exit_1.py`: the exit-1 check (Tests).

Changes:

- `src/tlaup/cli.py`: one registration block, in the tree's order (Run, Manage, Maintenance), that lists every group with `app.add_typer(...)` and every command with `app.command(...)` or `<group>_app.command(...)`, including the subcommands that the switch packages registered inside their group modules; the root option `--version` with `-V` (and no `-v`); the version callback prints the two lines of C4.
- `src/tlaup/cmd/tool/__init__.py`, `cmd/module/__init__.py`, `cmd/cache.py`, `cmd/config.py` and any other group module: they define their `typer.Typer` objects and command functions only; any `app.command(...)` call or side-effect import (`from . import x  # noqa: F401`) they still hold moves to `cli.py` ([23 C1](../design/23-command-layout.md#c1-command-tree), last row).
- `tests/features/errors.feature`: the scenarios under Tests.
- `CHANGELOG.md`: see Changelog.

Deletes:

- Anything old still registered or present, if a switch package left it: `src/tlaup/cmd/tools/`, `cmd/modules/`, `cmd/fetch_cache/`, `cmd/check_java.py`, `cmd/config/` (the old package), `tlc/run_cache.py`, `tlc/compiler.py`, `java/inspector.py`, and `versioning/paths.py` once nothing imports it. Each is expected gone already (29, 31, 39, 44, 46); for any that is not, the pull request says which package left it and why.
- Any of `warn`, `error`, `info`, `success` still in `tlaup/ui.py`, with their callers converted to `Ui` calls or raised errors; expected: none ([16](16-ui-messages.md): each goes with its last caller). [50](50-help-and-messages.md) checks again.

Shared: `src/tlaup/cli.py` and the group modules with no other package at this point (48 lands after every command package; [49](49-startup-cost.md) and [50](50-help-and-messages.md) come after it). `CHANGELOG.md`.

## Interfaces

No new function. The tree, from [23 C1](../design/23-command-layout.md#c1-command-tree), as the test writes it out (command path: arguments; long options):

| Command | Arguments | Options |
| --- | --- | --- |
| `tlaup` (root) | | `--version`/`-V`, `--debug` |
| `tlc` | `SPEC`, `TLC_ARGS...` | `--cfg`, `--workers`, `--coverage`, `--raw`, `--plain`, `--keep`, `--show-command`, `--refresh-interval`, `--java-opt`, `--auto-install` |
| `sany` | `SPEC`, `SANY_ARGS...` | `--java-opt`, `--auto-install` |
| `pcal` | `SPEC`, `PCAL_ARGS...` | `--java-opt`, `--auto-install` |
| `repl` | `REPL_ARGS...` | `--java-opt`, `--auto-install` |
| `tool list` | | `--installed` |
| `tool install` | `VERSION` (optional) | `--force` |
| `tool upgrade` | `VERSION` (optional) | |
| `tool uninstall` | `VERSION...` (optional) | `--all`, `--yes` |
| `tool pin` | `VERSION` (required) | |
| `tool current`, `tool dir` | | |
| `tool path` | `VERSION` (optional) | |
| `module add` | `PATH` | |
| `module list`, `module dir` | | |
| `module remove` | `NAME` (required) | |
| `config path`, `config show`, `config edit` | | |
| `config get` | `KEY` | |
| `config set` | `KEY`, `VALUE` | |
| `cache dir`, `cache list` | | |
| `cache clean` | `RUN_ID` (optional) | `--runs`, `--remote`, `--all` |
| `doctor` | | |
| `completion` | `SHELL` (`bash`, `zsh`, `fish`) | |

`--help` is Typer's on every command and is not listed. The argument names are the test's; where a package chose another metavar (`TLC_ARGS` and the like), the test follows the code and the pull request names the difference. The groups `tool`, `module`, `config` and `cache` have no options of their own and `no_args_is_help=True`.

**`--version`** ([23 C4](../design/23-command-layout.md#c4-version-flag)): `-V` and `--version`, eager, on the root. Two lines on stdout through `Ui.for_process()`: `tlaup <version>`, the metadata version with `+<commit>` for an editable install (through `get_app_version`, which [49](49-startup-cost.md) makes start `git` only then), and the package's one-line summary from the metadata (`importlib.metadata.metadata("tlaup")["Summary"]`; [50](50-help-and-messages.md) makes the root help read the same field). Today's first line is `tlaup v0.8.x`; the `v` goes, as C4 writes the line. `-v` is not declared, so it is Typer's unknown option, 2; it stays free for `--verbose` in milestone 4.

## Tests that must pass

**`tests/unit/test_command_tree.py`**, plain pytest, on `typer.main.get_command(tlaup.cli.app)` and the public attributes of what it returns (`commands`, `params`, `opts`, `secondary_opts`, `required`, `nargs`, `name`):

- The set of command paths equals the tree above, so a command added or removed without updating [23 C1](../design/23-command-layout.md#c1-command-tree) fails (C1, Tests). The test's tree is written out by hand in the test, not derived from the code.
- For each command, its arguments (name, required or not, variadic or not) and its long options equal the table's.
- No option anywhere has a one-letter form except `-V` on the root (C1, Tests): every name in `opts` and `secondary_opts` that is a dash and one letter is `-V`. This is also what keeps `-f`, `-y` and `-v` out.
- `-V` and `--version` through `CliRunner` exit 0 and give the same stdout, of two lines; the first is `tlaup ` followed by the version `get_app_version` returns for the installed metadata version, the second equals the metadata's `Summary` (C4: "print the same"; two results compared with each other are plain pytest, [01 T5](../design/01-testing.md#t5-feature-files-and-steps); inventory row P2). `-v` exiting 2 is the `errors.feature` row below. There is no `version.feature`: C4's Tests and T5's layout now name plain pytest for the comparison and `errors.feature` for `-v` (finding H7).
- Registration is in one place: an AST walk of every module under `src/tlaup/cmd/` finds no call of `.command(`, `.add_typer(` or `.callback(` on a Typer object and no import whose only purpose is a side effect (an `import` or `from . import` marked `noqa: F401`); `src/tlaup/cli.py` holds them all.
- No command or group is registered under a second name: the registered names are unique, and no Typer `name` differs from its path in the table (no alias, D14; no short form, D38).

**`tests/unit/test_no_own_exit_1.py`**, plain pytest: what makes "tlaup never returns 1 itself" ([02 X1](../design/02-cross-cutting.md#x1-exit-codes) rule 1) true now that every command is on the new code. An AST walk of `src/tlaup` and `src/tlaup_parse` asserts:

- no `typer.Exit(1)`, `typer.Exit(code=1)`, `sys.exit(1)`, `SystemExit(1)` or `exit(1)` with the literal `1` (or `True`); a `typer.Exit(<expression>)` is allowed, because that is how the wrapped tool's code passes through (rule 2), and the test lists the places it occurs so the review sees each;
- no call of `typer.prompt`, `typer.confirm` or Rich's `Prompt`/`Confirm`: Typer's raise `Abort` at end of input and give 1 in a bare app ([14 F6](../design/14-config-and-cli.md#f6-messages)); every question goes through `Ui.ask`;
- no `typer.echo(..., err=True)` followed by an exit, and no `typer.echo` outside `ui.py` and the reporters (ahead of [58](58-lint-rules.md)'s lint rule, which forbids it);
- `tlaup.ui` has none of `warn`, `error`, `info`, `success` as module-level functions.

Together with what exists already: every `TlaupError` subclass has a code in 2 to 5 ([02](02-errors-and-paths.md)'s test); an exception that escapes a command is 5 ([17](17-error-handler.md)); Typer's own usage errors are 2; `main()` turns Rich's closed-pipe 1 into 141 (17). The one 1 left is a wrapped tool's own, passed through `typer.Exit(outcome.exit_code)`.

**`tests/features/errors.feature`**, in-process, each asserting exit 2 (C1: "for each removed name ... a scenario asserts exit 2, which is all that is left of it"); an outline over:

| Command | Removed name |
| --- | --- |
| `tlaup tools list` | `tools` |
| `tlaup modules list` | `modules` |
| `tlaup check-java` | `check-java` |
| `tlaup fetch-cache clear` | `fetch-cache` |
| `tlaup tool meta sync` | `tools meta` (under its group's new name; `tlaup tools meta sync` is already the `tools` row) |
| `tlaup module path` | `modules path` |
| `tlaup config list` | `config list` |
| `tlaup config edit vim` | `config edit EDITOR` ([44](44-config-commands.md) left it here) |
| `tlaup tool install -f v1.7.4` | `install -f` |
| `tlaup tool uninstall -y v1.7.4` | `uninstall -y` |
| `tlaup -v` | the old version flag (C4: "`-v` exits 2") |

`tlc --cleanup` and `tlc --version` are already in [39](39-tlc-command.md)'s `tlc_errors.feature`; `tlc --no-keep` was never released and needs none (C1). For each row also `stdout is empty`.

No-command scenarios (C1, [02 X1](../design/02-cross-cutting.md#x1-exit-codes) rule 7, inventory row P4), an outline: `tlaup module` and `tlaup cache` alone exit 2, `stdout contains "Usage"`, `stderr is empty`. `tlaup` and `tlaup config` are [18](18-feature-harness.md)'s, `tlaup tool` is [29](29-tool-commands.md)'s, and [45](45-cache-commands.md) may have written `tlaup cache`: add only those missing, so each group has one such scenario.

`tool uninstall` with no argument, and with a version and `--all` together, exiting 2 with one `error:` line (C1, Tests) is [29](29-tool-commands.md)'s scenario; the tree test above asserts its `VERSION...` is optional, which is why the hand-written check exists.

No stateful test applies. The pull request names inventory rows P2 and P4 as covered.

## Changelog

Under `## [Unreleased]`, word for word from [23 C4](../design/23-command-layout.md#c4-version-flag):

- Breaking: "The version flag is `-V` (was `-v`). `-v` is reserved for `--verbose`."

From [02 X1](../design/02-cross-cutting.md#x1-exit-codes), word for word, written here because this is where tlaup's own exit 1 ends and the test above makes rule 1 true (review finding B10; [17](17-error-handler.md) built the mapping, but the old commands kept their 1 until their switches):

- Breaking: "Exit codes changed. tlaup's own errors now return 2 (usage), 3 (not set up), 4 (not found) or 5 (failed) instead of 1; Ctrl-C returns 130 (was 143 or 130); a closed output pipe returns 141 (was 1); `tlaup tool uninstall` returns 5 when a build could not be removed (was 0)."

[23 C1](../design/23-command-layout.md#c1-command-tree) asks for one line per row of its table, each with before and after. As far as the files of the command packages say, the rows are written there; this package checks each is under `## [Unreleased]` once, and writes any that is missing:

| C1 row | Line | Written by |
| --- | --- | --- |
| `check-java` becomes `doctor` | "`tlaup check-java` is now `tlaup doctor`, which also checks the pinned build, the config and the folders." | [46](46-doctor.md) |
| `fetch-cache clear` and `tlc --cleanup` become `cache clean`; `cache dir` and `cache list` are new | "`tlaup fetch-cache clear` and `tlaup tlc --cleanup` are now `tlaup cache clean`; `tlaup cache list` shows the run folders, and `tlaup cache clean RUN_ID` removes one." (once; V8 and R6 no longer carry Removed entries of their own) | [45](45-cache-commands.md) |
| `cache list` is new | In the row above | 45 |
| `tlc --no-keep` replaced by `--keep` | None: `--no-keep` was never released; R6's Changed entry names `--keep` | 39 |
| `config list` becomes `config show`; `path`, `get`, `set` new | "`tlaup config list` is now `tlaup config show` and prints the settings in effect, not the file." | [44](44-config-commands.md) |
| `config edit` loses `EDITOR` | F5's Breaking "The editor can no longer be given as an argument; set `VISUAL` or `EDITOR`."; C1 gives this row no line of its own | 44 |
| `tools meta sync` removed | "`tlaup tools meta sync` is removed; metadata is read from the jar at install." | 29 |
| `dir` prints a folder, `path` a file | "`tlaup tools dir` is now `tlaup tool dir` and prints only the folder; use `tlaup tool list --installed` for the builds." | 29 |
| `modules path` removed; `module dir` new | "`tlaup modules path` is removed; `tlaup tlc SPEC --show-command` shows the classpath in use and `tlaup module dir` the folder." | [31](31-module-commands.md) |
| `tool current` new | "`tlaup tool current` shows the pinned build and its jar without starting Java." (stage 4) | 29 |
| `tlc --version` removed | J3's Removed "`tlaup tlc --version`; use `tlaup tool current`." stands for C1's line | 39 |
| `tool list --installed` new | "`tlaup tool list --installed` lists the installed builds only, with no network." (stage 4) | 29 |
| `tools` and `modules` become `tool` and `module` | "`tlaup tools` and `tlaup modules` are now `tlaup tool` and `tlaup module`; every subcommand keeps its name." (once, covering both) | 29 |
| `tlc`, `sany`, `pcal`, `repl` top-level | None (no change for `tlc`; the other three are new) | |
| `sany`, `pcal`, `repl`, `--workers`, `--java-opt`, `--auto-install`, `--`, `--debug` new | Each package's Added entries: 41, 42, 43 (the three commands), 39 (`--workers`, `--java-opt`, `--auto-install` with V9, `--`), 17 (`--debug`) | those packages |
| `SPEC`, `VERSION`, `NAME` required | Covered by X1's Breaking entry on exit codes | 48 (above) |
| `uninstall` keeps optional `VERSION...` | Covered by X1's entry (2 instead of 1) | 48 (above) |
| `-f` and `-y` removed | "`tlaup tools install -f` and `tlaup tools uninstall -y` are now `tlaup tool install --force` and `tlaup tool uninstall --yes`." | 29 |
| `uninstall NAME` with several builds | V3's Breaking entry | 29 |
| No `ls`, `rm`; `pin`, `uninstall`, `remove` keep their names | None | |
| Registration explicit | None (internal) | |

Left for this package: C4's and X1's entries above, and any row the check finds missing.

## Context for the worker

**Decisions this rests on.** D14 (no alias, shim or migration: a removed name is an unknown command or option, exit 2, and nothing else). D38 (no short forms of commands, and, by the design agent's decision, of options: the only one-letter option is `-V`, with `-v` and `-q` reserved for milestone 4). D47 (`tool`, `module`). D29 and [02 X1](../design/02-cross-cutting.md#x1-exit-codes) rule 7 (no command: help on stdout, exit 2; a root option alone, `tlaup --debug`, is Typer's "Missing command", stderr only, exit 2).

**Root options go before the command.** `tlaup --debug tlc Spec`; after the command Typer rejects them as unknown (tried on Typer 0.29.1, [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)). `TLAUP_DEBUG=1` has no position. Whether milestone 4's `--quiet`, `--verbose` and `--color` are also accepted after the command is that design's question; do not add anything for it.

**Why the exit-1 check is here.** [17](17-error-handler.md) made the handler; the old commands kept raising `typer.Exit(1)` and calling `typer.prompt` until their switch packages replaced them, so on `main` between 17 and the last switch tlaup could still return 1 itself (17, Context). This package lands after every command package, so it is the first point where the rule can be checked across `src/` without an exception list. If the test finds a literal 1, fix it in the module where it is, in this pull request, with the error class that fits (D29's table), and say which package left it.

**Registration in one place.** The switch packages registered their groups' commands explicitly but in different places (29 inside `cmd/tool/__init__.py`, 44 in `cli.py`). C1's row says `cli.py` lists every command and group. Move the calls; change nothing else in the command modules. Keep each command's import inside `cli.py` cheap: [14 F9](../design/14-config-and-cli.md#f9-startup-cost) wants command modules to import only `typer`, `tlaup.errors` and `tlaup.context` at the top, which [49](49-startup-cost.md) then checks; importing a command module to register it is fine as long as that holds.

**The version line.** `get_app_version` is still today's (it starts `git` before deciding whether the install is a development one) until [49](49-startup-cost.md) rewrites it after this package. The test compares `-V` with `--version` and the first line's shape, not a fixed version, so it holds before and after 49. Under the isolation fixture `git` is the fake, which with no script answers 127; today's code then adds no suffix.

**State of `main` when this starts.** Every command of the tree exists on the new code (29, 31, 39 to 47). The old groups are expected gone; `cli.py` has one registration block per package, in the order they were merged; `-v` is still the version flag (17 kept it), and no test covers it (03b deleted `test_cli.py` with the old suite, decision D62).

## Done when

- The tests above pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- `tlaup --help` lists exactly the tree's top-level commands; `tlaup -V` prints the two lines; `tlaup -v` exits 2.
- Every row of the changelog table is under `## [Unreleased]` once; C4's and X1's entries are written.
- The pull request lists the `typer.Exit(<expression>)` places the exit-1 test found, and anything old it had to delete or fix, with the package that left it, and names the inventory rows it owns (P2, P4).

## Out of scope

- Each command's behaviour and its own scenarios: the command packages.
- Help text, the root help's three panels and its summary line: [50](50-help-and-messages.md). The generated CLI reference: [51](51-cli-reference.md).
- Startup cost and `get_app_version`: [49](49-startup-cost.md).
- The lint rules (`T20`, `BLE`, the check against `typer.echo` and `Console(`): [58](58-lint-rules.md); the AST checks here are their forerunner for one rule.
- `--quiet`, `--verbose`, `--color`: milestone 4.

## Risks

- From C1: this is the second of the release's two large user-visible changes; it lands once, in 0.9.0 (D6), with the changelog as the upgrade guide.
- From the cut: the tree test fixes option names; a package that renamed one deliberately (and said so in its pull request) makes the test and the design disagree. The test follows the design; a real rename is a design change, reported to the index.
- From the cut: AST checks can be dodged (a 1 held in a variable). They catch the forms the old code used; review covers the rest.
