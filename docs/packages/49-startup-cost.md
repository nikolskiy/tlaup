# 49. Startup cost

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

`import tlaup.cli`, `tlaup --help` and a command that needs neither the network nor the settings load none of `requests`, `yaml`, `truststore`, `rich.progress`, `rich.live`, `tlaup.config.schema` or `tlaup.versioning.github`; `tlaup --version` starts `git` only for an editable install, with a timeout. Two tests in fresh interpreters keep it so.

## Covers

- Roadmap items:
  - "Skip the `git rev-parse` call on normal installs; load heavy libraries (requests, Rich progress, pydantic schema) only in the commands that need them; set up the OS trust store where the network is used, not as a side effect of importing the package. `tlaup --help` took about a third of a second when measured." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust), line 273), in full, with the design's correction that `pydantic` itself cannot be kept out.
- Design sections:
  - [14 F9](../design/14-config-and-cli.md#f9-startup-cost), in full: the empty `tlaup/__init__.py`, function-level imports in command modules and the lint configuration that says so, `get_app_version`, the import tests, `test_app_version` with the fake `git`. `truststore` in `GitHubClient.__init__` is [24](24-github-client.md)'s; this package checks it.
  - [01 T11](../design/01-testing.md#t11-the-existing-tests): `version_manager/test_app_version.py` ("the editable-install and version-string cases, with the fake `git`. Until F9").

## Depends on

- [48](48-command-tree.md): the final command tree, so that every command module exists and every import site is the one that ships. 48 depends on every command package, and through it on [24](24-github-client.md) (`truststore` in the client's constructor), [19](19-layered-config.md) (settings loaded lazily by the context), [16](16-ui-messages.md) (`ui.py`) and [03](03-test-foundation.md) (the fake `git`, the isolation fixture).

## Files

Changes:

- `src/tlaup/__init__.py`: only the docstring. The `truststore.inject_into_ssl()` call and its import go (if [29](29-tool-commands.md) did not already remove them with the old network code).
- `src/tlaup/cli.py`: imports at the top only what registration needs (`typer`, `tlaup.errors`, `tlaup.context`, `tlaup.ui` for the handler, and the command modules).
- Every command module under `src/tlaup/cmd/` as [48](48-command-tree.md) left the tree: the `tool`, `module`, `config` and `cache` groups, `tlc`, `sany`, `pcal`, `repl`, `doctor` and `completion`. Each imports only `typer`, `tlaup.errors` and `tlaup.context` at the top; everything else (the store, the GitHub client, `tlaup.versioning.*`, `tlaup.tlc.*`, `tlaup.tools`, `tlaup.reporters`, `tlaup.modules`, the loader, `yaml`, `subprocess`, Rich beyond `rich.console`) is imported inside the command function. Many of these files will already follow the rule, because the command packages were told to; this package makes it hold everywhere.
- `src/tlaup/context.py`, `src/tlaup/ui.py`, `src/tlaup/errors.py`, `src/tlaup/stdio.py`: checked; changed only if one imports something on the list at its top (the context imports the loader inside `settings`, [19](19-layered-config.md)).
- `src/tlaup/versioning/app_version.py`: `get_app_version` as below.
- `src/tlaup/cmd/` and `pyproject.toml`: the lint configuration says that function-level imports are the rule in command modules. Ruff's `PLC0415` (`import-outside-top-level`) is in the `PL` group the project selects; if it is active on the ruff in the lock, add a per-file ignore for `src/tlaup/cmd/**` with a comment naming F9, and for any other file where F9 needs a local import (`cli.py`'s completion import, [47](47-completion.md)). If it is not active, add the comment beside the `PL` selection so a later ruff upgrade does not surprise anyone.
- `tests/unit/versioning/test_app_version.py`: rewritten from `tests/unit/version_manager/test_app_version.py` with the fake `git`.

Creates:

- `tests/unit/test_startup.py`: the two import tests.

Deletes:

- `tests/unit/version_manager/test_app_version.py` (moved and rewritten above; [01 T11](../design/01-testing.md#t11-the-existing-tests)).

Shared: none within a parallel group; this package runs after 48 alone, beside [50](50-help-and-messages.md), which edits help strings in the same command modules. The conflict is small (imports at the top against strings in decorators); land one, rebase the other.

## Interfaces

Provides, from [14 F9](../design/14-config-and-cli.md#f9-startup-cost), with the parameters stage 4 adds so the tests need no patching (marked):

```python
# tlaup/versioning/app_version.py
def is_editable_install(dist: importlib.metadata.Distribution | None = None) -> bool
    # dist: written by stage 4; None means importlib.metadata.distribution("tlaup")
def get_app_version(base_version: str | None = None, *, editable: bool | None = None) -> str
    # editable: written by stage 4; None means is_editable_install(). Returns the metadata version,
    # with "+<short commit>" only when editable is true and git answers within 2 seconds.
def get_git_commit_hash(base_dir: Path | None = None) -> str | None
    # ["git", "rev-parse", "--short", "HEAD"], found through PATH, check=False, timeout=2;
    # None on a non-zero exit, a timeout, OSError, or an answer shorter than 7 characters
```

Today's other conditions for adding the suffix (`base_dir is not None`, a `.git` folder three levels up) go: only `is_editable_install()` decides (F9).

Consumes: the command modules of 48; `GitHubClient` (24), whose constructor sets up `truststore`.

## Tests that must pass

`tests/unit/test_startup.py`, each in a fresh interpreter started by the test with `sys.executable` and the isolation fixture's environment:

- `python -c "import tlaup.cli, sys; print(sorted(m for m in ('requests','yaml','truststore','rich.progress','rich.live','tlaup.config.schema','tlaup.versioning.github') if m in sys.modules))"` prints `[]`.
- The same list is empty after running `tlaup tool dir` in-process in that interpreter (`typer.testing.CliRunner().invoke(app, ["tool", "dir"])`), a command that needs neither settings nor the network; the child also checks that the command exited 0.
- `pydantic` is not in the list, on purpose: on the locked Typer 0.29.1 Typer itself imports `pydantic` when any command runs (it is absent after `import typer` and after `--help`). Do not add it.

`tests/unit/versioning/test_app_version.py`, plain pytest with the fake `git` of [01 T4](../design/01-testing.md#t4-fakes-at-the-edges) (it prints a fixed short hash and logs each start):

- `get_app_version("0.9.0", editable=False)`: `"0.9.0"`, and the fake's log is empty (a normal install does not start `git`).
- `get_app_version("0.9.0", editable=True)`: `"0.9.0+<the fake's hash>"`, one start logged with `rev-parse --short HEAD`.
- `editable=True` with no `git` on `PATH`: `"0.9.0"`.
- `is_editable_install` on real distributions built by the test: a `tlaup-0.9.0.dist-info` folder under `tmp_path` with `METADATA` and a `direct_url.json` saying `{"dir_info": {"editable": true}}`, then one saying `{"url": "file:///x"}`, then one with none, each read with `importlib.metadata.PathDistribution`: true, false, false. No stand-in object and no patch ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 2).
- The version-string cases of today's file that still apply (a base version taken from the metadata when none is given).

No test measures time ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)).

**Measurements, not tests.** The pull request reports, as information and not as a pass mark: the wall time of `tlaup --help` and of `tlaup tool dir` before and after (best of ten runs on one machine, with the machine's description left out), and `python -X importtime -c "import tlaup.cli"`'s top entries after. The roadmap's "about a third of a second" was measured on 0.8.x; the cost of `pydantic` was not measured by the design, so say what is left once tlaup's own imports are lazy.

No stateful test applies.

## Changelog

Under `## [Unreleased]`, word for word from [14 F9](../design/14-config-and-cli.md#f9-startup-cost):

- Changed: "`tlaup --help` and other commands that need neither the network nor the config start faster."
- Fixed: "`tlaup --version` started `git` on every call."

## Context for the worker

**Why after 48.** It touches every import site, and the import sites are only final once every command is in the tree. Earlier, each new command package would have to keep the rule by itself, and the test would be added against a tree that is still changing.

**What F9 found, restated.**

- `tlaup/__init__.py` and the top-level imports of the command modules pulled in `requests`, `rich.progress`, the settings schema and the trust-store setup for every command.
- `get_app_version` started `git rev-parse` before deciding whether the install is a development one.
- `pydantic` cannot be kept out: on Typer 0.29.1 Typer imports it when any command runs. tlaup can keep its own schema module (`tlaup.config.schema`) from loading, not `pydantic`. What that costs was not measured.
- `truststore.inject_into_ssl()` belongs in `GitHubClient.__init__` ([12 V7](../design/12-tools-and-downloads.md#v7-github-client), [24](24-github-client.md)): set up where the network is used.
- Completion's private module is imported by `main()` only when `_TLAUP_COMPLETE` is set ([23 C3](../design/23-command-layout.md#c3-completion), [47](47-completion.md)); check it is still so.

**Traps.**

- Rich: `rich.console` and `rich.text` are fine at the top of `ui.py`; `rich.live` and `rich.progress` are not (the live layout and download progress import them inside the reporter and the download).
- `from __future__ import annotations` and `TYPE_CHECKING` blocks let a module name a type in a signature without importing it at run time; ruff's `TCH` rules, which the project selects, push in that direction already.
- Typer reads a command function's annotations when the app is built, so a type used in an option's annotation must exist at that moment; keep option types to built-ins and `typer` types, and import domain types inside the function.
- The second test runs a command in-process inside the child interpreter; run it with the isolation fixture's environment so it reads the test's `TLAUP_HOME`.
- The fake `git` is found through `PATH`; `get_git_commit_hash` must find `git` the same way (`shutil.which` or the bare name in an argument list), not by an absolute path.
- `check=False` is stated explicitly on the `subprocess.run` call: the `PLW1510` ignore goes in [58](58-lint-rules.md) ([30 I8](../design/30-ci-and-release.md#i8-lint-rules)).

**State of `main` when this starts.** Every command of [23 C1](../design/23-command-layout.md#c1-command-tree) exists and is registered explicitly in `cli.py` (48); no old command module is left; `-V` prints `tlaup 0.9.0` and the summary (48, [23 C4](../design/23-command-layout.md#c4-version-flag)), through `get_app_version`.

## Done when

- The two import tests and the version tests pass; the old test file is gone.
- `tlaup/__init__.py` holds only a docstring.
- The lint configuration states the function-level import rule for `src/tlaup/cmd/`.
- The pull request gives the measurements described above.
- The changelog entries are written.
- `uv run poe lint` and `uv run poe test` pass; CI is green.

## Out of scope

- `truststore` in the client's constructor: [24](24-github-client.md).
- Lazy settings: [19](19-layered-config.md).
- Completion's lazy import: [47](47-completion.md).
- The `print` and `PLW1510` lint changes: [58](58-lint-rules.md).
- Making `pydantic` lazy: not possible on the locked Typer (F9).

## Risks

- From F9: a later change adds a top-level import and nobody notices; the import tests are the guard.
- From the cut: [50](50-help-and-messages.md) edits the same command modules at the same time; the overlap is mechanical.
- A Typer release that imports more at startup (or stops importing `pydantic`) changes what the tests see; the list is tlaup's own heavy modules plus `requests`, `yaml` and `truststore`, which Typer does not import, so the tests should hold.
