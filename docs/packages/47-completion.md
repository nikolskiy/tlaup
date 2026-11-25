# 47. Shell completion

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup completion bash|zsh|fish` prints the shell's completion script; `main()` switches Typer's completion on (fills its registry of shells) only when `_TLAUP_COMPLETE` is set; installed versions, module names, config keys and spec files are completed from local state only, and a completer that fails returns nothing. The protocol Typer uses is pinned down by three real-process tests and the private half of the Typer contract tests.

## Covers

- Roadmap items:
  - "Shell completion, with completers for installed versions and module names." ([milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout), line 338), in full, apart from the integration check of the bash script ([52](52-integration-tests.md)) and the hand check of zsh and fish before the release (a maintainer action, below).
  - The exit criterion of milestone 1b, "completion works in bash, zsh and fish", in part: the automated tests here and in 52 cover bash; zsh and fish are met by a hand check ([23 C3](../design/23-command-layout.md#c3-completion), Risks).
- Design sections:
  - [23 C3](../design/23-command-layout.md#c3-completion), in full apart from its integration test (52) and the test of Typer's shell registry, which is [14 F9](../design/14-config-and-cli.md#f9-startup-cost)'s ([49](49-startup-cost.md)). C3 as corrected (review finding D1): `import typer` already loads Typer's completion modules, so what stays off on an ordinary start is the shell registry, not a module.
  - [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks): "`main()` also switches Typer's completion on when that variable is set (C3)"; the private half of the contract tests of Typer, `_available_shells` included; the one exception to the test that no module imports a private Typer module.
  - [14 F9](../design/14-config-and-cli.md#f9-startup-cost), in part: its one exception, `tlaup/cmd/completion.py` imported at the top of `cli.py` and of the command modules that name a completer, with the completers importing what they need in their own bodies.
  - [23 C1](../design/23-command-layout.md#c1-command-tree): the `completion bash|zsh|fish` line of the command tree; the tree test is [48](48-command-tree.md)'s (finding H12).

## Depends on

- [17](17-error-handler.md): `main()` and `run_app` in `cli.py`, the program name fixed to `tlaup`, `add_completion=False`; `tests/unit/test_typer_contract.py` (the public half) and `tests/unit/test_no_private_imports.py`, which this package extends.
- [23](23-tool-store.md) and [22](22-version-spec-and-jarinfo.md): `ToolStore.builds()`, `Build.name`; `format_build` for the printed forms ([02 X3](../design/02-cross-cutting.md#x3-version-syntax)), `sort_key` for the order.
- [25](25-remote-listing.md): the lookup cache's file format and `parse_release`, for the tags of the remembered release list (Interfaces).
- [30](30-module-build.md): `Registry` and its `list()`, for module names.
- [19](19-layered-config.md): `setting_keys()`, the dotted keys from the schema.
- The commands whose arguments are completed: [29](29-tool-commands.md) (`tool pin`, `uninstall`, `path`, `upgrade`, `install`), [31](31-module-commands.md) (`module remove`), [44](44-config-commands.md) (`config get`, `config set`), [39](39-tlc-command.md), [41](41-sany-command.md), [42](42-pcal-command.md) (the `SPEC` of `tlc`, `sany`, `pcal`).
- [18](18-feature-harness.md): the steps and `_process.start` (the real-process runner with the SIGINT reset), which the three real-process tests use. [05](05-github-recordings.md): `make_tools_jar` and the recorded manifests, to prepare a store. [03](03-test-foundation.md): the isolation fixture.

Changes from the draft (29, 31, 44): 39, 41 and 42 are added, because C3's `SPEC` completer is declared on their arguments; 17, 19, 22, 23, 25 and 30 are named for what they provide (the brief's note: the store, the registry and the schema); 18, 05 and 03 for the tests.

## Files

Creates:

- `src/tlaup/cmd/completion.py`: the command, the completers, `init_completion`. The only module under `src/` that imports `typer._completion_classes` or `typer._completion_shared` ([23 C3](../design/23-command-layout.md#c3-completion)).
- `tests/features/completion.feature` (in T5's list of feature files).
- `tests/unit/cmd/test_completion.py`: the completers, called directly.
- `tests/unit/cmd/test_completion_process.py`: the three real-process tests.

Changes:

- `src/tlaup/cli.py`: `tlaup.cmd.completion` imported at the top (F9's one exception); in `main()`, before `run_app`, `if "_TLAUP_COMPLETE" in os.environ: init_completion()`; and the registration of `completion` with `app.command(name="completion")` in the one block. `run_app` is not changed: it is also what [17](17-error-handler.md)'s small test apps run.
- `src/tlaup/cmd/tool/` (`pin`, `uninstall`, `path`, `upgrade`, `install`), `src/tlaup/cmd/module/` (`remove`), `src/tlaup/cmd/config.py` (`get`, `set`), `src/tlaup/cmd/tlc.py`, `cmd/sany.py`, `cmd/pcal.py`: each imports its completer from `tlaup.cmd.completion` at the top (F9's one exception) and its argument declaration gains `autocompletion=` (Typer's parameter) naming the completer. One parameter each, and one other edit where `complete_spec` needs it: the `SPEC` argument of `tlc`, `sany` and `pcal` may take a `Path` type so that Typer asks the shell for files (see `complete_spec`); that changes the parameter's type, and [51](51-cli-reference.md)'s reference shows it.
- `src/tlaup/versioning/remote.py`: `cached_tags` (Interfaces).
- `tests/unit/test_typer_contract.py`: the private half (Tests).
- `tests/unit/test_no_private_imports.py`: `tlaup/cmd/completion.py` is the one exception.
- `CHANGELOG.md`: see Changelog.

Deletes: nothing.

Shared with packages that may run beside it (40 to 47 after 39): `src/tlaup/cli.py` (one import, one registration line, and the two lines in `main()`), the command modules above (one import and one `autocompletion=` each; [40](40-live-display.md) also edits `cmd/tlc.py`, for `--plain` and `--refresh-interval`, a different declaration), `CHANGELOG.md`. The `PLC0415` per-file ignore for `src/tlaup/cmd/**` and `src/tlaup/cli.py` is already in `pyproject.toml` ([17](17-error-handler.md)); nothing to add there.

## Interfaces

The command, from [23 C3](../design/23-command-layout.md#c3-completion):

```
tlaup completion SHELL        SHELL: bash | zsh | fish (a required argument with three allowed values)
```

It prints, on stdout, the text `get_completion_script(prog_name="tlaup", complete_var="_TLAUP_COMPLETE", shell=SHELL)` returns, and exits 0. Another value is Typer's usage error, 2. The help shows the line to put in each shell's start-up file (`eval "$(tlaup completion bash)"`, and for zsh and fish their equivalents) and says in one line that in bash a build is completed up to its name and the part after `@` is typed. [50](50-help-and-messages.md) reviews the wording; the content is C3's.

```python
# tlaup/cmd/completion.py
class Shell(str, Enum):
    bash = "bash"; zsh = "zsh"; fish = "fish"

def completion(shell: Shell) -> None
def init_completion() -> None               # typer._completion_classes.completion_init()

# completers: Typer's autocompletion signature, (incomplete: str) -> list[str]; each filters by the prefix
def complete_installed(incomplete: str) -> list[str]    # pin, uninstall, path
def complete_upgrade(incomplete: str) -> list[str]      # upgrade
def complete_install(incomplete: str) -> list[str]      # install
def complete_module(incomplete: str) -> list[str]       # module remove
def complete_config_key(incomplete: str) -> list[str]   # config get, config set (KEY only)
def complete_spec(incomplete: str) -> list[str]         # SPEC of tlc, sany, pcal (see below)
```

What each returns, from C3; every completer reads the store or the registry only, never the network and never the settings:

| Completer | Words |
| --- | --- |
| `complete_installed` | Every installed build in its printed form (`format_build(b, builds)`), each distinct name, and `stable` and `rolling`; no duplicates. |
| `complete_upgrade` | The distinct names of installed builds only: `upgrade` takes a name and rejects `name@commit` ([12 V4](../design/12-tools-and-downloads.md#v4-upgrade-and-pin)). |
| `complete_install` | `stable`, `rolling`, and the tags of the remembered release list if a lookup cache file exists (`cached_tags`); no request is made. |
| `complete_module` | The names of registered modules (`Registry.list()`). |
| `complete_config_key` | `setting_keys()`. |
| `complete_spec` | `*.tla` files, through the shell's file completion (below). |

**Where the paths come from.** During completion Typer parses the command line without running callbacks, so the root callback has not built the context and `ctx.obj` is empty. Each completer builds `AppPaths.from_env(os.environ)` itself, which needs no settings, and from it the store or the registry. Stage 4's reading of "never the settings": the settings are not loaded, so a broken config file cannot break completion.

**A completer that fails returns nothing** (C3: "for any reason ... completion never prints an error into the user's prompt"). Each completer's body is wrapped in one `try` whose `except Exception` returns `[]`. That is the second of the two blind excepts [30 I8](../design/30-ci-and-release.md#i8-lint-rules) allows, beside the last branch of `TlaupGroup.invoke`: it gets `noqa: BLE001` and a comment naming C3 and I8. Write one guard (a decorator or a helper the completers share) rather than one `except` per completer, so there is one such line. The imports a completer needs (the store, `format_build`, the registry, the schema) are inside the `try`, so a failing import also returns nothing. Inside a completer, nothing is printed, also with `--debug` or `TLAUP_DEBUG` set.

**`complete_spec`.** C3 says "through the shell's file completion". Declare the `SPEC` argument so that Typer asks the shell for files (a `Path` type, whose completion item is of kind `file`), if the scripts of the locked Typer act on that for all three shells; check it with the real-process protocol below. If one of them does not, `complete_spec` lists the `*.tla` files and the folders in the current folder that start with `incomplete` (a relative path in `incomplete` is looked up in its folder), which works in every shell. The pull request says which was built and why.

**Written by stage 4**, in `tlaup/versioning/remote.py`:

```python
def cached_tags(cache_dir: Path) -> list[str]
    # every lookup cache file under cache_dir whose "url" is a release list ("/releases", any query) is read
    # with the module's own reader (parse_release on each entry); the tags of releases that have the jar,
    # in X4's order, without duplicates. Age is ignored: completion offers what is remembered. A file that
    # cannot be read is skipped, as the cache already treats it as absent (V8). No request, no settings.
```

C3 says "the remembered release list". The completer cannot know the repository address without the settings, so it reads whatever release lists are remembered; with the default repository that is one file.

**`main()`** calls `init_completion()` before `run_app` when `_TLAUP_COMPLETE` is set in the environment, and not otherwise. That call fills Typer's registry of shells (`typer._click.shell_completion._available_shells`), which is empty until then: that, not a missing module, is what "completion is off unless asked" means on the locked Typer (C3). The probe of C3 called `completion_init()` unconditionally; with the variable set the path is the same. Typer derives the variable's name from the program name, which [17](17-error-handler.md) fixed to `tlaup`. Typer's own `--install-completion` and `--show-completion` stay off (`add_completion=False`).

Consumes: `get_completion_script`, `completion_init` (Typer, private); `ToolStore`, `format_build`, `sort_key` (23, 22); `Registry` (30); `setting_keys` (19); `parse_release` (25); `AppPaths` (02).

## Tests that must pass

**`tests/unit/cmd/test_completion.py`**, plain pytest, the completers called directly, with a store prepared in the isolated cache through `ToolStore.add` and [05](05-github-recordings.md)'s `make_tools_jar` with the recorded manifests (two builds of `rolling` with different commits, and `v1.7.4`):

- `complete_installed("")` returns each build's printed form, `rolling`, `v1.7.4`, `stable` and `rolling` once; `complete_installed("rol")` returns only the words that start with `rol`.
- With a broken `build.json` in the store (a folder whose `build.json` is not JSON), the same call returns the rest (C3).
- `complete_upgrade("")` returns `rolling` and `v1.7.4` and no word with `@`.
- `complete_install("")` with no lookup cache returns `stable` and `rolling`; with a cache file written through [25](25-remote-listing.md)'s `write_cache` from the `releases` recording, also the recorded tags that have the jar; no request is made (the socket block and no `github` fixture: a request would fail the test).
- `complete_module("")` with two registered modules returns both names; with an empty or missing module folder, `[]`.
- `complete_config_key("tlc.")` returns the `tlc` keys of the schema.
- Each completer with `TLAUP_HOME` set to a relative path (`AppPaths.from_env` raises) returns `[]` and prints nothing (capsys).
- `complete_spec`, if built: with `Spec.tla`, `Other.tla`, `notes.txt` and a folder `spec/` in the working folder, `complete_spec("S")` returns `Spec.tla` and `spec/`.

**`tests/features/completion.feature`**, in-process ([23 C3](../design/23-command-layout.md#c3-completion): "A feature (in-process)"):

- `tlaup completion bash`, `zsh` and `fish`, an outline: exit 0, `stdout contains "_TLAUP_COMPLETE"`, `stdout contains "tlaup"`.
- `tlaup completion powershell`: exit 2, `stdout is empty`.

**`tests/unit/cmd/test_completion_process.py`**, real processes, in the default suite on every system, with no shell involved (C3). Each starts `python -m tlaup` through [18](18-feature-harness.md)'s `_process.start` with the isolation fixture's environment plus the variables named, against the prepared store above, and asserts the exit code 0 and the stdout:

- `_TLAUP_COMPLETE=complete_bash`, `COMP_WORDS="tlaup tool pin "`, `COMP_CWORD=3`: stdout is the installed builds' words, one per line (the words of `complete_installed("")`).
- The same with `COMP_WORDS="tlaup tool pin rolling @ "` and `COMP_CWORD=5`: stdout is empty. This pins down the bash limit (bash splits a word at `@`), so a change in it is noticed.
- `_TLAUP_COMPLETE=complete_fish`, `_TYPER_COMPLETE_ARGS="tlaup tool pin "`, `_TYPER_COMPLETE_FISH_ACTION=get-args`: stdout holds each installed build's word.
- `_TLAUP_COMPLETE=complete_zsh`, `_TYPER_COMPLETE_ARGS="tlaup tool pin "`: the output is an `_arguments` call for the shell to evaluate; it names each installed build.

That an ordinary start leaves Typer's shell registry empty, and that `completion_init()` fills it, is F9's third test, written by [49](49-startup-cost.md) with F9's other import tests; it is not repeated here. The old assertion that `sys.modules` holds no completion module cannot hold on the locked Typer, where `import typer` loads `typer._completion_classes` and `typer._completion_shared` (review finding D1).

These use the variables the generated scripts use, read from the script text; they are what fails first if a Typer release changes the protocol.

**`tests/unit/test_typer_contract.py`**, the private half ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)): `typer._completion_classes.completion_init` can be called with no argument; `typer._completion_shared.get_completion_script` accepts the keyword arguments `prog_name`, `complete_var` and `shell` (checked with `inspect.signature`); the script it returns names `COMP_WORDS`, `COMP_CWORD` and `complete_bash` for bash, `_TYPER_COMPLETE_ARGS` and `complete_zsh` for zsh, and `_TYPER_COMPLETE_ARGS`, `_TYPER_COMPLETE_FISH_ACTION` and `complete_fish` for fish; `typer._click.shell_completion._available_shells` exists and is a dictionary (the name F9's test reads). Each check names the Typer name in its failure message.

**`tests/unit/test_no_private_imports.py`**: still no module under `src/tlaup` imports `click` or a private Typer module, except `tlaup/cmd/completion.py`; and `cli.py` reaches completion only through `tlaup.cmd.completion`.

**Integration, not here.** C3's integration test (Linux job only: the bash script sourced in a non-interactive bash and its function called with `COMP_WORDS` and `COMP_CWORD` as bash would set them, asserting `COMPREPLY` holds the installed builds; for zsh and fish the script loaded with `zsh -n` and `fish --no-execute` where the shell is on the runner, skipped with the reason otherwise) is [52](52-integration-tests.md)'s, beside the other integration tests and run by [54](54-integration-job.md)'s job.

No stateful test applies.

## Changelog

Under `## [Unreleased]`, word for word from [23 C3](../design/23-command-layout.md#c3-completion):

- Added: "`tlaup completion bash|zsh|fish` prints a shell completion script. Installed versions, module names and config keys are completed. In bash, a build is completed up to its name; the part after `@` is typed."

## Context for the worker

**Facts the design tried** (Typer 0.29.1, and research 23 on every release from 0.22.0 to 0.29.2), restated so the research is not needed. Typer carries a private copy of Click and replaces its completion with its own; Click's `<shell>_source` instruction does not exist here. With `add_completion=False`, a start with `_TLAUP_COMPLETE=complete_bash` prints "Shell bash not supported." and exits 1, because Typer registers its shell classes only when completion is switched on; after `typer._completion_classes.completion_init()` the same start with `COMP_WORDS="tlaup tool pin "` and `COMP_CWORD=3` prints the completer's words, one per line, and exits 0. `get_completion_script(prog_name=..., complete_var=..., shell=...)` returns a script for bash, zsh and fish, which calls the program back with `COMP_WORDS`, `COMP_CWORD` and `_TLAUP_COMPLETE=complete_bash` (bash), `_TYPER_COMPLETE_ARGS` and `complete_zsh` (zsh), and `_TYPER_COMPLETE_ARGS`, `_TYPER_COMPLETE_FISH_ACTION` and `complete_fish` (fish). Both modules exist with the same signatures in all 26 wheels from 0.22.0 to 0.29.2. Without `completion_init()` Typer 0.22.0 to 0.25.1 answer in Click's format, which the bash script cannot read; tlaup always calls it when the variable is set.

**The bash `@` limit.** Bash splits the word under the cursor at the characters of `COMP_WORDBREAKS`, which by default include `@` and `:`, before Typer's script runs. For the word `rol` the completer's words come back whole (`rolling`, `rolling@bc1b506`, ...); after a typed `rolling@` bash passes `rolling`, `@` and an empty word, and nothing comes back. So in a default bash a build is completed only up to its name. zsh and fish pass the whole word. Working around it needs a bash script of tlaup's own in place of Typer's, which C3 did not do; do not do it here.

**Rejected in C3, not to be revived:** switching Typer's completion on and pointing users at `--show-completion` (it detects the shell from the parent process and brings `--install-completion`, which writes into the user's shell files); hand-written scripts (they must match the installed Typer's protocol); a `completion install` command.

**Decisions this rests on.** D15: PowerShell is not offered, though Typer could generate it; Windows has no CI. D38: no short forms, so no `completion -s`. D14: nothing old to keep.

**Startup cost** ([14 F9](../design/14-config-and-cli.md#f9-startup-cost), as corrected). `tlaup/cmd/completion.py` is imported at the top of `cli.py` and of the command modules that name a completer: a completer is named when the command is declared, so it cannot wait. That costs nothing Typer has not already loaded, as long as the module itself imports nothing heavy at its top: only `typer`, `enum` and what Typer's private completion modules need, which `import typer` has loaded anyway. The completers import the store, `format_build`, the registry and the schema inside their bodies. F9's import test (49) still finds none of its listed modules after `import tlaup.cli`, so a heavy import added here fails there. The config schema imports pydantic; that cost is paid only while completing a config key.

**Maintainer action before the release** (not a package, C3's Risks): completion in a real interactive zsh and fish is checked by hand once. Name it in the pull request so the index carries it.

**State of `main` when this starts.** The `tool`, `module` and `config` groups and the `tlc`, `sany` and `pcal` commands exist on the new code (29, 31, 44, 39, 41, 42); `main()` is 17's. Packages 40 to 46 may be in flight beside this one.

## Done when

- The tests above pass on Linux and macOS in CI; `uv run poe lint` and `uv run poe test` pass.
- `tlaup completion bash` output, `eval`ed in a bash by hand once by the worker, completes `tlaup tool pin ` with the installed builds; the pull request says so (the automated check of this is 52's).
- `typer._completion_*` is imported only in `tlaup/cmd/completion.py`, and `init_completion()` runs only when `_TLAUP_COMPLETE` is set; `tlaup/cmd/completion.py` imports nothing at its top that F9's list names.
- The changelog entry is written.

## Out of scope

- The bash integration check, and the `zsh -n` and `fish --no-execute` checks: [52](52-integration-tests.md).
- Completion in a real interactive zsh and fish: the maintainer's hand check before the release.
- A bash script of tlaup's own that completes past `@`: not designed.
- Help wording: [50](50-help-and-messages.md). The tree test, which counts `completion`: [48](48-command-tree.md).

## Risks

- From C3: the command is built on two private Typer modules. A Typer release can rename them or change the variables; the guards are the version bound (`typer>=0.27.2,<1.0.0`), the contract tests, the three real-process tests, and the newest-dependencies job ([30 I3](../design/30-ci-and-release.md#i3-newest-dependencies-job)). If Typer drops them, the fallback is the rejected `--show-completion`.
- From C3: the exit criterion is met for zsh and fish by a hand check, not by the automated tests.
- From C3 and F9: a later change that adds a heavy import at the top of `tlaup/cmd/completion.py` puts it on every start, since the module is imported by `cli.py`; F9's import test (49) is the guard.
- From the cut: `complete_spec` depends on what the locked Typer's scripts do with a file-typed argument, which nobody tried; the fallback completer is written out above.
