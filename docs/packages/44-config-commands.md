# 44. The `config` commands

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup config` has the five commands of the signed-off tree, `path`, `show`, `get`, `set` and `edit`, built on the layered loader; a broken file leaves `path` and `edit` working and makes the others stop with the reason (D42); `edit` takes its editor from `VISUAL` or `EDITOR`, with arguments, or a default that exists, and checks the file afterwards. `config list` and the positional editor are gone.

## Covers

- Roadmap items ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)):
  - "`config` commands work when the file is broken, and a broken file gives a readable validation message instead of a traceback." (line 268), the commands' part; the message is [19](19-layered-config.md)'s, the absence of a traceback [17](17-error-handler.md)'s.
  - "`config edit`: accept `$VISUAL` and `$EDITOR` values with arguments such as `code --wait`, have a default that exists on the platform, and validate the file after editing." (line 271), in full.
  - "Layered configuration (decision D10): ... No file is written until the user changes a setting." (line 267), in part: `config set` and `config edit` are the only writers.
  - "Review the layout of every command so it follows the most common CLI patterns ..." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 334), in part: the `config` group (`config path`, `show`, `get`, `set`; the editor as a positional argument). The tree as a whole is [48](48-command-tree.md).
- Design sections:
  - [14 F4](../design/14-config-and-cli.md#f4-config-commands-with-a-broken-file), in full apart from its scenario "`tlaup tlc Spec` exits 3 and names the key", which is [39](39-tlc-command.md)'s: 44 can land before the new `tlc` exists, and between packages no old command is promised to keep working (decision D62).
  - [14 F5](../design/14-config-and-cli.md#f5-config-edit), in full.
  - [14 F1](../design/14-config-and-cli.md#f1-layered-configuration): `config set` and its value rules; the two in-process `config.feature` scenarios. The loader is 19's.
  - [23 C1](../design/23-command-layout.md#c1-command-tree): the rows "`config list` becomes `config show`; `config path`, `get`, `set` are new" and "`config edit` loses its positional `EDITOR`". The scenarios that removed names exit 2, and the tree test, are [48](48-command-tree.md)'s.
  - [14 F6](../design/14-config-and-cli.md#f6-messages), in part: the `config` commands' prints become `ui` calls or raised errors.
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes) and [20 G2](../design/20-groundwork.md#g2-domain-errors), in part: the `errors.feature` scenarios for the examples the `config` commands reach.

## Depends on

- [03](03-test-foundation.md): the fake `editor` (`TLAUP_FAKE_EDITOR`, its log) on the isolation fixture's `PATH`, which holds no real editor ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)); the expected-file helper.
- [16](16-ui-messages.md): `Ui` (`note`, `result`, `out`) through the context.
- [17](17-error-handler.md): the root group that prints errors and maps them to codes, `--debug`, `TLAUP_DEBUG`.
- [18](18-feature-harness.md): `tests/test_features.py`, the step vocabulary (`the config file contains:`, `the config file is unchanged`, `the editor writes:`, `the editor exits with code <n>`, `the environment variable "<name>" is "<value>"`, `the file "<path>" exists` / `does not exist` / `contains`, `the editor was started with` / `without`, `stdout matches the expected file`), `errors.feature`.
- [19](19-layered-config.md): `load_settings`, `LoadedSettings` (`settings`, `sources`, `warnings`), `write_user_setting`, `check_setting`, `parse_setting_text`, `setting_keys`, `closest_key`, `CONFIG_HEADER`, `AppPaths.config_file` (02).

## Files

Creates:

- `src/tlaup/cmd/config.py`: the `config` group and its five commands, thin (each parses its arguments, calls the loader or the editor function, prints through `ctx.obj.ui`).
- `src/tlaup/config/editor.py`: `editor_command` (F5 steps 1 and 2) and `edit_file` (steps 3 to 5). Domain code: returns values or raises `TlaupError`, prints nothing.
- `tests/features/config.feature` and its expected files under `tests/features/expected/config/`.
- `tests/unit/config/test_editor.py` (`tests/unit/` holds only new tests after [03](03-test-foundation.md)).

Changes:

- `src/tlaup/cli.py`: the `config` group is registered from `tlaup.cmd.config` with `app.add_typer(...)`, its commands with explicit `command(...)` calls in one block ([23 C1](../design/23-command-layout.md#c1-command-tree), last row: registration is explicit and in one place). One block; the other switch packages each touch their own.
- `src/tlaup/config/loader.py`: `config_path()` is deleted if `cmd/config/` was its last caller (it is today), and with it `config_dir()`, whose only caller is `config_path()` (finding F2).
- `tests/unit/test_context.py` (02's test): the assertion that `config_dir()` follows `TLAUP_HOME` goes with the function, as [02](02-errors-and-paths.md) and [19](19-layered-config.md) hand it here. `cache_dir()` and its assertion are [39](39-tlc-command.md)'s.
- `tests/features/errors.feature`: the scenarios under "Tests".
- `CHANGELOG.md`.

Deletes:

- `src/tlaup/cmd/config/__init__.py`, `src/tlaup/cmd/config/list.py`, `src/tlaup/cmd/config/edit.py`. Their old tests went in 03b with the rest of the old suite (decision D62).

Shared with the packages of its period (period 4 of the index, once 18 and 19 are in), chiefly [29](29-tool-commands.md) (29a and 29b): `src/tlaup/cli.py` (one registration block each), `tests/features/errors.feature` (one block of scenarios each), `CHANGELOG.md`.

## Interfaces

The commands, from [23 C1](../design/23-command-layout.md#c1-command-tree):

```
tlaup config path
tlaup config show
tlaup config get KEY
tlaup config set KEY VALUE
tlaup config edit
```

Written by stage 4, from F4 and F5 in words:

```python
# tlaup/config/editor.py
def editor_command(env: Mapping[str, str], *, os_name: str = os.name,
                   which: Callable[[str], str | None] = shutil.which) -> list[str]
    # VISUAL, else EDITOR (an empty value counts as unset), split with shlex.split, the first word
    # resolved with which; else the first found of notepad (Windows) or sensible-editor, nano, vi.
    # None found: NotSetUp with the hint to set EDITOR. A VISUAL or EDITOR whose first word is not
    # found: NotSetUp naming the variable and the word.
def edit_file(paths: AppPaths, env: Mapping[str, str], argv: Sequence[str]) -> LoadedSettings
    # creates the file holding only CONFIG_HEADER when absent; runs argv + [path] without a shell and
    # waits (check=False); non-zero exit: Failed (5); then removes a file that still holds only the
    # header, and validates with load_settings (ConfigInvalid, 3, propagates; the file stays as saved)
```

`which` and `os_name` are arguments so the default order can be unit-tested on every system; production passes neither.

Output, per command (stdout carries the result, [02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr)):

| Command | stdout | Exit | Reads the file |
| --- | --- | --- | --- |
| `path` | `AppPaths.config_file`, one line, whether or not it exists | 0 | Never; does not load settings ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration)) |
| `show` | The settings in effect as YAML, every leaf key with its source as a trailing comment (`workers: auto  # default`, `min_version: 17  # TLAUP_JAVA_MIN_VERSION`) | 0; 3 for a broken file, nothing on stdout | Yes |
| `get KEY` | The value, as `parse_setting_text` would read it back (`auto`, `4`, `[ghe.example.com]`, `null`) | 0; 4 for an unknown key; 3 for a broken file | Yes |
| `set KEY VALUE` | nothing; a `note` on stderr naming the key, the value and the file | 0; 2 for a value that does not fit; 4 for an unknown key; 3 for a broken file, nothing written | Yes, before writing |
| `edit` | nothing | 0; 3 (no editor; the file invalid afterwards); 5 (the editor failed) | After the editor |

The form of `show` and of `get`, and that `get` and `set` take leaf keys only (a section name such as `tlc` is not a key: `ConfigKeyNotFound`, code 4, with the hint listing the keys of that section), were settled with the maintainer on 2026-11-24 and are written in [14 F1](../design/14-config-and-cli.md#f1-layered-configuration) ("What `config show` prints", "What `config get KEY` prints"); the expected files fix the exact text, and the pull request shows them (finding H5). The order of checks in `set`: the key (4), then the value with `check_setting` (2), then the whole file through `load_settings` (3), then `write_user_setting`; so `config set no.such.key 1` is 4 with a broken file too, and a bad value never touches the file.

Consumes: from 19 the names listed under Depends on; `Ui` (16); `NotSetUp`, `Failed`, `UsageError`, `ConfigKeyNotFound`, `ConfigInvalid` (02).

Used later by: completion of config keys ([47](47-completion.md), `setting_keys`); `doctor`'s config check ([46](46-doctor.md), the loader, not these commands).

## Tests that must pass

`tests/features/config.feature`, in-process (none of T5's five situations applies: no passthrough, no pipe, no signal, no terminal; the editor is a child but its output is not tlaup's), per [01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 10:

F1 and C1:

- `config set tlc.workers many` exits 2 and `the file "{config}/config.yaml" does not exist` afterwards.
- `config set no.such.key 1` exits 4; `config get no.such.key` exits 4; `config get tlc.worker` exits 4 and stderr contains `tlc.workers`; `config get tlc` (a section) exits 4 and stderr names the keys of `tlc`.
- `config path` on a fresh home prints `{config}/config.yaml` and leaves `the file "{config}/config.yaml" does not exist` (the same property F1 states for `tlaup tool path`, whose scenario is 29b's, with the command).
- `config set tlc.refresh_interval 0` exits 0 and `config get tlc.refresh_interval` prints `0`: the schema checks the type only, and the range is `tlc`'s, which gives 2 wherever the value came from ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration), [22 O5](../design/22-reporters.md#o5-refresh-interval)).
- `config show` on a fresh home matches the expected file `config/show-defaults.txt`; with a file holding `tlc.workers: 4` and `TLAUP_JAVA_MIN_VERSION` set to `17`, it matches `config/show-layers.txt`, which shows `user file` and `TLAUP_JAVA_MIN_VERSION` as sources.
- `config get tlc.workers` prints `auto`; after `config set tlc.workers 4`, `config get tlc.workers` prints `4` and the file contains `workers: 4`.
- `config set tool.token_hosts '[GHE.example.com]'`, then `config get tool.token_hosts` prints `[ghe.example.com]`; `config set tool.token_hosts 'https://ghe.example.com'` exits 2.
- `config set java.opts '["-Xmx8g", "-XX:+UseParallelGC"]'`, then `config get java.opts` prints both options.
- A file holding a comment and one key: after `config set`, the file contains the header line and the other key's value, and not the comment.

F4, each with `the config file contains:` invalid YAML, and separately with a wrong type (`tlc:` / `refresh_interval: fast`):

- `config path` exits 0 and prints the path.
- `config edit` starts the editor (`the editor was started with "{config}/config.yaml"`); with the editor leaving the file alone it then exits 3.
- `config show`, `config get tlc.workers`, `config set tlc.workers 4` each exit 3, `stdout is empty`, stderr names the line and column (YAML) or `tlc.refresh_interval` (wrong type), `stderr contains "tlaup config edit"`, `stderr does not contain "Traceback"`; for `set`, `the config file is unchanged`.
- After `the editor writes:` a valid file, `config edit` exits 0 and `config show` exits 0.

F5, with the fake editor:

- `the environment variable "EDITOR" is "editor --wait"`: `config edit` exits 0, `the editor was started with "--wait"` and with the path.
- `VISUAL` set to `editor --visual` and `EDITOR` to `editor --wait`: the editor was started with `--visual` and without `--wait`.
- An edit that writes `tlc:\n  workers: many` exits 3 and stderr names `tlc.workers`; the file holds what the editor wrote.
- Quitting without changes (the editor writes nothing) on a fresh home exits 0 and leaves `the file "{config}/config.yaml" does not exist`.
- `the editor exits with code 1`: exit 5.
- Neither `VISUAL` nor `EDITOR` set: exit 3, stderr contains `EDITOR` (the isolation `PATH` has no `sensible-editor`, `nano` or `vi`).
- `the environment variable "EDITOR" is "nosuch-editor --wait"`: exit 3, stderr contains `EDITOR` and `nosuch-editor`, and the editor was not started. [F5](../design/14-config-and-cli.md#f5-config-edit) step 1 says so: a `$VISUAL` or `$EDITOR` whose first word is not on `PATH` is `NotSetUp`, code 3, naming the program and the variable (inventory row O10, changed on purpose; finding H11).

`tests/features/errors.feature` (in-process), each asserting the code, `stdout is empty` and `stderr contains "error:" 1 times` ([02 X1](../design/02-cross-cutting.md#x1-exit-codes)'s rows 2 to 5 for what `config` reaches):

- Row 2: `config set tlc.workers many` (a value that does not fit its key).
- Row 3: `config show` with an invalid config file; the same with `--debug` before `config`, and with `TLAUP_DEBUG=1`, has `Traceback` on stderr (the broken-config case of [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)'s four).
- Row 4: `config get no.such.key` (a config key).
- Row 5: `config edit` with `the editor exits with code 1` (the editor exited with an error).

`tests/unit/config/test_editor.py`, plain pytest: `editor_command` with `VISUAL`, with `EDITOR`, with both, with an empty `VISUAL`; with neither and `which` answering only `nano`, only `vi`, nothing; with `os_name="nt"` and `which` answering `notepad`; a value with a quoted argument (`'my editor' --wait` is two words). `edit_file` with the fake editor: the file absent before and only the header after is removed; a non-zero exit is `Failed`.

No stateful test applies. The inventory's rows O9 and O10 (`config list`, `config edit EDITOR`) are changed on purpose, so they need no test of their own; the scenarios above are what replaces them.

## Changelog

Under `## [Unreleased]`, word for word unless said.

From [14 F4](../design/14-config-and-cli.md#f4-config-commands-with-a-broken-file):

- Fixed: "With a broken config file every command, including `tlaup config edit`, failed with a traceback. `config path` and `config edit` now work with a broken file; other commands stop with the file, the line and the reason."

From [14 F5](../design/14-config-and-cli.md#f5-config-edit):

- Fixed: "`tlaup config edit` failed for an editor given with arguments (`EDITOR='code --wait'`) and on machines without vim."
- Changed: "It reads `$VISUAL` before `$EDITOR` and checks the file after editing."
- Breaking: "The editor can no longer be given as an argument; set `VISUAL` or `EDITOR`."

From [14 F1](../design/14-config-and-cli.md#f1-layered-configuration):

- Added: "`tlaup config set KEY VALUE` changes one setting. It rewrites the config file and does not keep comments."

From [23 C1](../design/23-command-layout.md#c1-command-tree), Breaking:

- "`tlaup config list` is now `tlaup config show` and prints the settings in effect, not the file."
- C1's row on `config edit` has its entry in F5 (above), and C1 no longer repeats it.

Not in the design, and required by the [conventions](../contributing/conventions.md#changelog) (every user-visible change gets an entry), so written by stage 4: Added: "`tlaup config path` prints the config file's path; `tlaup config get KEY` prints one setting."

## Context for the worker

**Decisions this rests on.** D42 (with a broken file, `path` and `edit` work; `show`, `get` and `set` stop with exit 3; `show` and `get` never fall back to defaults, because their output would describe settings not in effect). D10 (no file is written until the user changes a setting: only `set` and `edit` write, and `edit` removes a file it created that still holds only the header). D14 (no `config list` alias). D29 (2 for a value typed to `set` that does not fit; 3 for the file or the environment; 4 for an unknown key; 5 for the editor failing). D30 (results on stdout, notes on stderr).

**F5, step by step** (restated): the editor is `$VISUAL`, else `$EDITOR`, else the first found on `PATH` of `notepad` on Windows, `sensible-editor`, `nano`, `vi` elsewhere; none: `NotSetUp` with the hint to set `EDITOR`. The value is split with `shlex.split`; the first word is looked up with `shutil.which` (which adds `.exe` on Windows, D15); the path is appended last. If the file does not exist it is created first holding only `CONFIG_HEADER` (not the defaults as comments: `config set` would drop them, and `config show` prints every default). The editor runs without a shell and is waited for; a non-zero exit is `Failed` (5). Then the file is validated with the loader; problems are printed as F1 does and the command exits 3, the file left as the user saved it.

**What F4 asks of the other commands.** "Every other command that needs settings raises the same `ConfigInvalid`", with the hint `tlaup config edit`. That comes from the loader ([19](19-layered-config.md)); this package only has to make sure `path` never loads settings and `edit` loads them only after the editor.

**Traps.**

- `config path` must not touch `ctx.settings`; neither may the code the root callback runs ([17](17-error-handler.md) removed the old load). [49](49-startup-cost.md) later checks the imports.
- Command modules import only `typer`, `tlaup.errors` and `tlaup.context` at the top; `yaml`, the loader and `subprocess` are imported inside the command functions ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)). Follow the rule now so 49 has nothing to move here. Ruff's `PLC0415` flags such imports; the per-file ignore for `src/tlaup/cmd/**` and `src/tlaup/cli.py` is already in `pyproject.toml` ([17](17-error-handler.md) puts it there), so write no `noqa` for them.
- `set` checks the value's type only: `config set tlc.refresh_interval 0` is written, and `tlc` refuses it when it runs (F1, question Q16 as built).
- `show` prints warnings (unknown and removed keys) on stderr through the context, as every command that loads settings does; they are not part of its stdout.
- `show`'s output must be valid YAML that loads back to the same values (the comments carry the sources), so a user can copy it into the file. Print it through `ui.result` with markup off.
- `set` with a value the shell has quoted: the value is one argument read as a YAML scalar or flow value (`'[a, b]'`). A value that does not parse as YAML is a usage error (2), like one that does not fit.
- `set` on a file holding unknown or removed keys keeps them (the writer keeps every other key), and the load before writing prints their warning.
- The fake editor logs its argument list; the path it is given is absolute.
- `$VISUAL` set to an empty string counts as unset (stage 4; F5 does not say).
- Windows: `notepad` blocks until closed when started directly, which is what "waited for" needs; not tried (D15).

**What the old `config` commands did**, for the pull request's description: `config list` printed the raw file and exited 1 when there was none; `config edit [EDITOR]` copied the default file into place, looked the whole editor value up with `shutil.which` (so `code --wait` was "not found"), defaulted to `vim`, and exited 1 for every failure.

**State of `main` when this starts.** The new loader (19) and handler (17), `Ui` (16), the step vocabulary (18). `cmd/config/` holds the old `list` and `edit`, with no tests (03b deleted the old suite). Other old command groups may still be in place; this package touches none of them, and does not keep any of them working (D62).

## Done when

- The five commands behave as in the table; `config list` and `config edit EDITOR` no longer exist (Typer answers them with exit 2; the scenario for that is [48](48-command-tree.md)'s).
- The scenarios and unit tests above pass.
- No `typer.echo`, `print` or `Console(` in `cmd/config.py` or `config/editor.py`.
- The changelog entries are written.
- `config_path()` and `config_dir()` are gone from the loader, and `tests/unit/test_context.py` no longer asserts `config_dir()`.
- The pull request names inventory row O10 (changed on purpose; its new behaviour is the `nosuch-editor` scenario above).
- `uv run poe lint` and `uv run poe test` pass; CI is green.

## Out of scope

- The loader, the schema, `write_user_setting`: [19](19-layered-config.md).
- The removed-name scenarios (`config list`, `config edit EDITOR` exit 2) and the tree test: [48](48-command-tree.md).
- `tlaup tool path` on a fresh home leaving no file (F1's scenario, 29b), and `tool.repository` deciding where requests go: [29](29-tool-commands.md).
- `tlaup tlc Spec` with a broken config file exiting 3 and naming the key (F4's scenario): [39](39-tlc-command.md), with the new `tlc`.
- Completion of config keys: [47](47-completion.md).
- `config unset` (rejected in F1) and the configuration reference page (documentation track).

## Risks

- From F1: a user who keeps comments in the file and runs `config set` loses them; the help of `config set` says "Rewrites the config file. Comments in it are not kept; use `tlaup config edit` to keep them." (F1), and the changelog says so.
- From F5: an editor that returns at once (a GUI editor started without its wait flag) makes `config edit` validate an unchanged file and, on a fresh home, remove it again. That is the user's editor setting; the help names `code --wait` as the form.
- From F1: `show`'s and `get`'s output forms were settled with the maintainer; the exact text is in the expected files, which are the one place it changes.
