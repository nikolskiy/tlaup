# 51. The generated CLI reference and its drift test

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

`uv run poe docs-cli` writes `docs/reference/cli.md` from the Typer app; a test in the default suite regenerates it in memory and fails when the checked-in copy differs, so every change to help text shows up as a diff of that file in its pull request. The first checked-in copy is the help text [50](50-help-and-messages.md) wrote and its review read.

## Covers

- Roadmap items:
  - "CLI reference generated from the code, with CI failing when the checked-in copy drifts. Run the README quick start commands in CI." ([documentation track](../roadmap.md#documentation-track-parallel-start-with-milestone-1), line 497), in part: the first sentence. The second, running the README quick start in CI, is not in [23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference) and has no package in this cut (the report says so).
  - "Help text (raised list): ... the generated reference is built from help." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust), line 268), in part: the generated reference. The help text is [50](50-help-and-messages.md).
- Design sections:
  - [23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference), in full.
  - [01 T8](../design/01-testing.md#t8-expected-output-files): the generated CLI reference is one of the expected files the helper compares.
  - [14 F7](../design/14-config-and-cli.md#f7-help-text), Tests: "The generated reference is an expected file; CI fails when it drifts."
  - The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md), row P5 (owner 51): help shows every command with a one-line description, and `tlc --help` lists its options. The checked-in reference and its drift test hold it.

## Depends on

- [50](50-help-and-messages.md): the reviewed help text of every command, the three `rich_help_panel` groups of the root, the epilogs, the summary line from the metadata. Through 50, [48](48-command-tree.md): the complete, explicitly registered tree.
- [03](03-test-foundation.md): `assert_matches` and `--update-expected` (`tests/expected.py`).
- [17](17-error-handler.md): `tlaup.cli.app` built with `TlaupGroup`.

Change from the draft (50): 03 and 17 are named for what the script and the test use; 48 through 50. 50's pull request carries a full help dump for review, and this package's first checked-in reference is that reviewed text (the index's "Why the cut is this way" settles the order).

## Files

Creates:

- `scripts/gen_cli_reference.py`: `render_reference(app) -> str` and a `main()` that writes `docs/reference/cli.md`.
- `docs/reference/cli.md`: the generated reference, checked in.
- `tests/unit/test_cli_reference.py`: the drift test.

Changes:

- `pyproject.toml`: the poe task `docs-cli` (`python scripts/gen_cli_reference.py`, run through `uv run poe docs-cli`). Nothing else: the `T20` exemption for `scripts/` is [58](58-lint-rules.md)'s (58c, which switches `T20` on) (review finding D12), and the script writes its file rather than printing, so it needs none. mypy checks `scripts/` (I8).
- `docs/README.md`: one row for `reference/`, saying what it holds (the command-line reference, generated from the code by `uv run poe docs-cli`; do not edit by hand) and when to read it (you need a command's exact arguments and options) ([conventions](../contributing/conventions.md#documentation): a new document gets a line in the index above it).
- `docs/contributing/development.md`: the command `uv run poe docs-cli` in its commands list, with one line on when to run it (after changing any help string; the drift test fails otherwise).

Deletes: nothing.

Shared: `pyproject.toml` (one task line; [58](58-lint-rules.md), which may run beside this package, and the CI packages edit other lines), `docs/README.md` (one row).

## Interfaces

```python
# scripts/gen_cli_reference.py
WIDTH = 100
def render_reference(app: typer.Typer) -> str
    # typer.main.get_command(app), walked depth first in the registered order; plain text, colour off
def main() -> None     # writes <repo>/docs/reference/cli.md from tlaup.cli.app; the path from the script's own location
```

From [23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference):

- For every command and group: its usage line, description, arguments, options and epilog, at a fixed width of 100 columns, with colour off. The root's commands are listed under their `rich_help_panel` names in [14 F7](../design/14-config-and-cli.md#f7-help-text)'s order (Run, Manage, Maintenance): Typer's own generator ignores the panels, which is one reason it is not used.
- The script uses only `typer.main.get_command(app)` and the public attributes of the commands it walks (`commands`, `params`, `help`, `short_help`, `epilog`, `name`, and of each parameter `opts`, `secondary_opts`, `help`, `required`, `default`, `nargs`, `is_flag`, `metavar`); no private Typer module and no Rich rendering. Usage lines come from each command's own `get_usage` on a context made with its public `make_context(..., resilient_parsing=True)`, or are composed from the parameters, the worker's choice; the pull request says which.
- The file starts with one line saying it is generated and how: that `scripts/gen_cli_reference.py` writes it, that `uv run poe docs-cli` (or `pytest --update-expected`) updates it, and not to edit it by hand.
- Text is written as the help strings hold it. Lines are wrapped at `WIDTH`; no line ends in white space and the file ends with one newline, so the pre-commit hooks (trailing white space, end of file) pass on it unchanged.
- Nothing in it may depend on the machine: no default that is read from the environment, the home folder or the settings at the time the app is built. The isolation fixture makes such a value a temporary path, which differs on every run, so the drift test fails on it at once.

Rejected in C5, not to be revived: Typer's own generator (`python -m typer <module> utils docs`), whose notation changed between Typer releases (four different files over thirteen versions, research 23), writes quotes as `&#x27;` and ignores `rich_help_panel`; the reference should change when help text changes, not when Typer changes its notation (agreed in the walk-through of the top-up results, 2026-11-20).

Consumes: `tlaup.cli.app` (17, 48); `assert_matches` (03).

## Tests that must pass

**`tests/unit/test_cli_reference.py`**, in the default suite (C5): loads `scripts/gen_cli_reference.py` with `importlib.util.spec_from_file_location` (the folder is not a package), calls `render_reference(tlaup.cli.app)`, and compares the text with `docs/reference/cli.md` through `assert_matches`. On a mismatch it fails with the unified diff; with `--update-expected` it rewrites the file, which is the same text `uv run poe docs-cli` writes (one function makes both). The test also asserts the first line is the generated-file line, and that the text holds no path of the isolation fixture's temporary folder.

T12 rule 6: the pull request shows the test failing on a help string changed by hand and passing after `uv run poe docs-cli`.

No feature file, no stateful test. The pull request names inventory row P5 as covered: the reference lists every command with its one-line description and `tlc`'s options, and the drift test fails when one goes missing.

## Changelog

None (C5: documentation).

## Context for the worker

**Why it exists.** Help text is reviewed by reading it, not by assertions on wording ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 4). With this file and its test, any change to a help string is a diff of `docs/reference/cli.md` in the pull request that makes it, where the reviewer reads it ([01 T8](../design/01-testing.md#t8-expected-output-files): an updated expected file is a change to review).

**Facts the design tried.** On Typer 0.29.1, `typer.main.get_command(app)` returns a group with `commands`, `params`, `help` and `epilog` (tried on a small app). Another Typer version may differ; the drift test then fails loudly, and the newest-dependencies job ([30 I3](../design/30-ci-and-release.md#i3-newest-dependencies-job)) is where that shows first. Typer's own documentation generator gave the same output at any width and colour setting and on a second run (research 23); the script is still preferred, for the reasons above.

**Rich markup in help strings.** The app's help strings may carry backticks or Rich markup; the script writes them as stored. If [50](50-help-and-messages.md) used markup that reads badly as plain text, raise it in the pull request rather than stripping it in the script, so the reference shows what the strings hold.

**`docs/reference/`** is a new folder. [50](50-help-and-messages.md) does not create it under the order as cut. The documentation track's reference pages (configuration and the like) will live beside it later; only `cli.md` is written here.

**State of `main` when this starts.** The tree is complete and registered in one place (48); every help string is the reviewed one (50); the startup-cost work (49) may be merged or beside this package. `scripts/` holds `release.sh` and the developer scripts of earlier packages (`capture_golden.py`, `record_github.py`, `test_clean.py`).

## Done when

- `uv run poe docs-cli` writes `docs/reference/cli.md`; a second run changes nothing.
- The drift test passes in the default suite and fails, with a diff, after any help string is changed without regenerating.
- `docs/README.md` has the row for `reference/`; `docs/contributing/development.md` names the task.
- `uv run poe lint` (mypy and ruff on `scripts/`), `uv run poe test` and `uv run pre-commit run --all-files` pass; CI is green.
- The pull request shows the red run of T12 rule 6 and says how usage lines are made.

## Out of scope

- The help text itself: [50](50-help-and-messages.md).
- Running the README quick start in CI (the roadmap item's second sentence): not designed in C5; no package in this cut.
- Other reference pages (configuration, exit codes): the documentation track.

## Risks

- From C5: the command objects the script walks are Typer's copy of Click's; a Typer release that reshapes them fails the drift test, and the script is then changed in the pull request that raises the bound.
- From the cut: until this package lands, nothing stops a later pull request from changing help text unreviewed ([50](50-help-and-messages.md)'s Risks); the order 50 then 51 accepts that gap for the length of one package.
