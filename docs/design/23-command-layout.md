# 23. Milestone 1b: command layout

Covers "Command layout (notes 44 to 46)". The roadmap's exit criterion is that "the command tree is reviewed and signed off"; C1 is the tree to sign off. Relies on decisions D1, D14, D23, D24, D31, D38, D42, D43.

Guiding rule from the roadmap: follow the most common command-line patterns, so that commands can be guessed from other tools. Where a choice was needed, `uv`, `cargo`, `rustup` and `git` were the models, in that order. No aliases for old names (D14) and no short forms (D38).

## C1 Command tree

**Today.**

```
tlaup [-v|--version]
  tlc [SPEC] [--version] [--show-command] [--cleanup] [--refresh-interval F] [--coverage] [--raw] [--cfg TEXT]
  check-java
  modules   add PATH | list | remove MODULE_NAME | path
  tools     dir | install [VERSION] [-f] | list | path [VERSION] | pin VERSION
            | uninstall [VERSIONS]... [--all] [-y] | upgrade [VERSION] | meta sync
  fetch-cache clear
  config    edit [EDITOR] | list
```

**Proposed.**

```
tlaup [-V|--version] [--debug] [--help]            (--debug goes before the command; TLAUP_DEBUG=1 works anywhere)

Run
  tlc SPEC [--cfg FILE] [--workers N|auto] [--coverage] [--raw] [--plain] [--keep] [--show-command]
           [--refresh-interval SECONDS] [--java-opt OPT]... [--auto-install stable|rolling] [-- TLC ARGS...]
  sany SPEC [--java-opt OPT]... [--auto-install ...] [-- SANY ARGS...]
  pcal SPEC [--java-opt OPT]... [--auto-install ...] [-- PCAL ARGS...]
  repl      [--java-opt OPT]... [--auto-install ...] [-- REPL ARGS...]

Manage
  tool     list [--installed]
           install [VERSION] [--force]
           upgrade [VERSION]
           uninstall [VERSION]... [--all] [--yes]      (one of VERSION or --all is needed)
           pin VERSION
           current
           path [VERSION]
           dir
  module   add PATH
           list
           remove NAME
           dir
  config   path
           show
           get KEY
           set KEY VALUE
           edit
  cache    dir
           list
           clean [RUN_ID] [--runs] [--remote] [--all]

Maintenance
  doctor
  completion bash|zsh|fish
```

**Every change, with its reason.** The roadmap lists the points to settle; each is a row.

| Change | Reason |
| --- | --- |
| `check-java` becomes `doctor`. | `doctor` checks everything a run needs, and is the name `brew`, `flutter` and `mise` use. It prints one line per check with `ok`, `warning` or `error`: `java` and `javac` (path, version, whether from `JAVA_HOME` or `PATH`); the pinned build (present, jar matches its recorded SHA-256); leftovers in the tools folder, and folders in the module folder that are not modules (no valid name or no readable `module.json`, [13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder); the registry's own `.tmp/` and `.lock` are not counted, as the tools folder's `.tmp/`, `.lock` and `pin` are not), each a warning; the config file (valid, unknown keys); each folder (path, exists, writable); whether a GitHub token is set (yes or no, never the value). It re-runs the Java version check and refreshes the remembered answer. The levels follow one rule: an **error** is what makes `tlaup tlc Spec` stop with 3 ("not set up", [02 X1](02-cross-cutting.md#x1-exit-codes)) or what a run cannot do without (a damaged pinned jar, a cache folder that cannot be written); a **warning** is what a run survives, but something else will trip on or is off. So a missing or too old `javac` is a warning, since only `module add` with Java sources needs it, and nothing pinned is an error, since a run with nothing pinned stops with 3 wherever it cannot ask. Exit 0 when nothing is an error, else 3; warnings never change the code. |
| `fetch-cache clear` and `tlc --cleanup` become `cache clean`; `cache dir` and `cache list` are new. | One cache command, named as in `uv`. `--cleanup` was an action disguised as an option and forced `SPEC` to be optional. The rule for run folders is [11 R6](11-runner.md#r6-run-folders)'s, in its words: `cache clean` by default removes every run folder whose lock is free and that the sweep would remove, an unsettled folder that is not resumable; it never removes a kept folder, an unsettled one that asked to be kept and holds a complete checkpoint, or one without a `run.json` (D49, D53); with `--all` it also removes those. A run in progress holds its folder's lock, parsed and `--raw` alike, so it is never removed. A lock file is removed together with its folder; a lock file whose folder is gone is removed only when it is more than one hour old, because a run that is just starting has made its lock file and not yet its folder. Besides run folders, `cache clean` with no option removes the remembered GitHub lookups; `--runs` or `--remote` limits it to one of the two kinds. `--all` widens the kind that is cleaned rather than adding one: `--runs --all` removes every run folder whose lock is free, kept ones included, and nothing else; `--remote --all` is `--remote`, since every remembered lookup goes anyway. Only `--all` with no kind named also removes the remembered Java check (`<cache>/java.json`, [13 J3](13-modules-and-java.md#j3-one-java-start)), which belongs to neither kind. Finding nothing to remove is not an error: `cache clean` on a fresh home, or run twice, says that nothing was removed and exits 0. It never touches installed tools or modules, which live under the cache folder until milestone 3; the help says so. It prints what it removed and the space freed. Top-up (decision D53): `cache clean` without `--all` never removes a kept run folder, nor an unsettled one that asked to be kept and holds a complete checkpoint; `cache clean RUN_ID` removes that one run folder, whatever it is, when its lock is free, and touches nothing else (an id that names no folder is code 4, one in use code 5). A run id excludes the other options: `cache clean RUN_ID` with `--runs`, `--remote` or `--all` is a usage error, code 2 (review finding TU6). With D53 the sweep at every run removes the rest, so a plain `cache clean` seldom finds a run folder to remove. |
| `cache list` is new. | The note printed when a checkpoint is kept names a run folder, and R6 refers to "what `tlaup cache` lists"; without a command there was nothing to look at before `cache clean --all` removes it. `cache list` prints one line per run folder, from R6's `list_runs`, which returns `RunRecord` values: the run's id, the spec and cfg, the build recorded in `run.json` (the build a checkpoint was written by), when it started and when it last changed, its size, whether it is in use (its lock is held), whether it is kept and why (interrupted, tlaup failed, TLC crashed, or unsettled after a kill), and whether its checkpoint is complete. A last line gives the total size of the kept folders. A folder without a `run.json` is listed with what is known, its id, size and last change. No network, no Java. Added in this design after the second check; the README lists it. Top-up (D53): it is where the reminder line printed at every `tlaup tlc` start points ([11 R6](11-runner.md#r6-run-folders)). |
| `tlc --no-keep` (D48) is replaced by `tlc --keep` (D53). | Not keeping is now the default: a run deletes its folder at its end however it ended, and `--keep` (or the setting `tlc.keep`, or `TLAUP_TLC_KEEP`) asks for a resumable checkpoint to be kept. Research 25 found that every breadth-first run stopped after half an hour has a checkpoint, of up to gigabytes, so keeping must be asked for ([11 R6](11-runner.md#r6-run-folders)). |
| `config list` becomes `config show`; `config path`, `get`, `set` are new. | `list` printed the raw file. `show` prints the effective settings, each with where it came from (default, user file, variable, option), as YAML on stdout, the source as a trailing comment. `get KEY` prints one value, in the form `set` reads; a section name is not a key (code 4). Both forms are [14 F1](14-config-and-cli.md#f1-layered-configuration)'s, settled with the maintainer on 2026-11-24. `set KEY VALUE` validates one value and rewrites the file with it; comments in the file are not kept, and a list is given as one YAML value, `'[a, b]'` ([14 F1](14-config-and-cli.md#f1-layered-configuration)). `path` prints the file's path whether or not it exists. Keys are dotted: `tlc.workers`. With a config file that does not parse, `path` and `edit` work and `show`, `get` and `set` exit 3 with the reason (decision D42, [14 F4](14-config-and-cli.md#f4-config-commands-with-a-broken-file)). |
| `config edit` loses its positional `EDITOR`. | Unusual; `VISUAL` and `EDITOR` are the convention ([14 F5](14-config-and-cli.md#f5-config-edit)). |
| `tools meta sync` is removed. | It sat three levels deep and overwrote a build's metadata with the current remote build's, which is wrong for an older rolling build (roadmap, milestone 3). With the version store, metadata is read from the jar at install and never needs syncing ([12 V1](12-tools-and-downloads.md#v1-version-store)). The milestone 3 item "fix it, or remove the command" is thereby done: removed. |
| `dir` always prints a folder; `path` always prints a file. | Three meanings before. `tool dir`, `module dir`, `cache dir`: one line, the folder. `tool path [VERSION]`, `config path`: one line, the file. `tool dir` no longer lists the builds (`tool list --installed` does). |
| `modules path` is removed; `module dir` is new. | `modules path` printed a three-part report of what would go on the classpath for a run with no project. That question is answered exactly, for a real spec, by `tlaup tlc SPEC --show-command`, and the folders are shown by `doctor`. |
| `tool current` is new (D38). | Shows the pinned build without starting Java: `rolling@bc1b506 (2026.11.15.002146)` and the jar's path on a second line. Exit 3 when nothing is pinned. |
| `tlc --version` is removed. | It printed the jar path and started Java for a version line. `tool current` and `doctor` replace it ([13 J3](13-modules-and-java.md#j3-one-java-start)). One `--version` is left, the tool's own (C4). |
| `tool list --installed` is new. | Lists installed builds only, with no network. The fuller display of the milestone 4 item builds on it. |
| `tools` becomes `tool` and `modules` becomes `module` (decision D47). | A group names a kind of thing and its subcommand says what is done to one: `tool install rolling`, `module remove Foo`. The common form in `uv` (`tool`, `python`, `cache`), `git` (`remote`, `branch`), `gh` (`repo`, `release`) and Docker (`container`, `image`), and the same as tlaup's own `config` and `cache`. Settled with the maintainer 2026-11-17, during the sign-off. The config section (`tool.repository`, `tool.token_hosts`) and the cache folders (`tool/`, `module/`) follow, so the names match everywhere; `runs/` and `remote/` name no command and stay. |
| `tlc`, `sany`, `pcal`, `repl` are top-level, not under a `run` group. | They are what the tool is for; `tlaup tlc Spec` is already the habit and the README's first line. |
| `sany`, `pcal`, `repl`, `--workers`, `--java-opt`, `--auto-install`, `--` passthrough, `--debug` are new. | Designed in [21](21-other-tools.md), [11 R8](11-runner.md#r8-passthrough-and-workers), [13 J1](13-modules-and-java.md#j1-java-options), [12 V9](12-tools-and-downloads.md#v9-first-run-prompt), [14 F10](14-config-and-cli.md#f10-no-tracebacks). |
| `SPEC` is a required argument of `tlc`, `sany` and `pcal`; `VERSION` of `pin`; `NAME` of `module remove`. | Removes the hand-written "Missing argument" checks, which exited 1; Typer reports a missing argument in its own form and exits 2 ([02 X1](02-cross-cutting.md#x1-exit-codes), rule 7). |
| `uninstall` keeps an optional `VERSION...` and checks by hand. | `VERSION...` cannot be a required argument, because `uninstall --all` has none. The command raises tlaup's own `UsageError` (code 2, one `error:` line) when neither a version nor `--all` is given, and when both are. The hand-written check at `cmd/tools/uninstall.py` stays in that form; what changes is its exit code, 2 instead of 1, and that it goes through the error handler. |
| The short options `-f` (`install --force`) and `-y` (`uninstall --yes`) are removed. | Today `install` has `--force, -f` and `uninstall` has `--yes, -y`. D38 says no short forms; it was asked about command names (`ls`, `rm`), and this design applies it to these two options as well, so that the only one-letter options in the tool are `-V` and, in milestone 4, `-v` and `-q`. The README lists this as a decision made in the design; if the maintainer wants them kept, it is two declarations. |
| With several installed builds of one name, `uninstall NAME` asks which on a terminal and removes all of them with `--yes` or without a terminal (decision D43). | [12 V3](12-tools-and-downloads.md#v3-uninstall). |
| No `ls`, `rm` or other short forms (D38). | One name per command; Typer already answers a mistyped `ls` with "did you mean `list`". |
| `pin` keeps its name. | The roadmap, the pin file and milestone 3's `pin --local` all use it; it matches `uv python pin`. |
| `uninstall` keeps its name; `remove` stays for modules. | A tool build is installed and uninstalled; a module is added and removed. Each pair is the usual one for its verb. |
| Registration is explicit and in one place. | `cli.py` lists every command and group with `app.command(...)` and `app.add_typer(...)`; the import-for-side-effect style of `cmd/tools/__init__.py` goes (roadmap, milestone 5 housekeeping, done here because every command file is touched). |

Root options: `--debug` now; `--quiet`, `--verbose` and `--color` in milestone 4 ([40](40-later-milestones.md#milestone-4-automation-surface)). A root option is written before the command (`tlaup --debug tlc Spec`); after the command Typer rejects it as an unknown option (tried on Typer 0.29.1, [14 F10](14-config-and-cli.md#f10-no-tracebacks)). `TLAUP_DEBUG=1` has no position. Whether milestone 4's three options should also be accepted after the command is a question for that design.

With no command, `tlaup` prints the root help on stdout and exits 2, and a group alone (`tlaup tool`, `tlaup cache`) does the same with its own help; that is Typer's behaviour and is kept ([02 X1](02-cross-cutting.md#x1-exit-codes), rule 7).

**Rejected.** A `run` command with `tlc` as its alias (the analysis report's sketch): an alias for an old name is what D14 excludes, and a new name for the main command has no benefit. `tools use` instead of `pin`: `pin` is established here. `tools sync-metadata`: the command has no job left. `cache prune` beside `clean`: one command with options is enough at this size. Keeping `check-java` beside `doctor`: an alias for an old name.

**Tests.** `doctor.feature`, `cache.feature`, `config.feature` and the `tool_*` features (in-process, apart from the scenarios on a terminal named in [12 V3 and V4](12-tools-and-downloads.md#v3-uninstall)) cover each new command's result and exit code. `cache.feature`: `cache list` with no run folders prints nothing and exits 0; with a kept folder made by the checkpoint-writing fake `java` under `--keep` it prints one line holding the run id, the spec's name, the build, its size and why it was kept, and a total line; `cache clean` leaves that folder, `cache clean <its id>` removes it and its lock file and nothing else, and `cache clean --all` removes every one; `cache clean nosuch` exits 4, and `cache clean <its id> --all` exits 2. `cache clean --runs --all` removes the kept folder and leaves a remembered lookup and `java.json`; `cache clean --all` removes `java.json` too. On a fresh home `cache clean` exits 0 with no `error:` line. `doctor.feature` asserts the level of each finding the rule above places: no `javac` gives `javac: warning` and exit 0, nothing pinned gives an error and exit 3. A unit test walks the Typer app and asserts the set of command paths equals the tree above, so a command added or removed without updating this document fails; the same test asserts that no option has a one-letter form except `-V`. `tlaup` and `tlaup tool` with nothing after them exit 2 with help on stdout. For each removed name (`tools`, `modules`, `check-java`, `fetch-cache`, `tools meta`, `modules path`, `config list`, `tlc --cleanup`, `tlc --version`, `install -f`, `uninstall -y`) a scenario asserts exit 2, which is all that is left of it. `tlc --no-keep` was never released, so it needs no such scenario. `tool uninstall` with no argument, and with a version and `--all` together, exits 2 with one `error:` line.

**Changelog.** Under Breaking and Removed, one line per row, each with before and after, for example: "`tlaup check-java` is now `tlaup doctor`, which also checks the pinned build, the config and the folders." "`tlaup fetch-cache clear` and `tlaup tlc --cleanup` are now `tlaup cache clean`; `tlaup cache list` shows the run folders, and `tlaup cache clean RUN_ID` removes one." "`tlaup config list` is now `tlaup config show` and prints the settings in effect, not the file." "`tlaup tools meta sync` is removed; metadata is read from the jar at install." "`tlaup modules path` is removed; `tlaup tlc SPEC --show-command` shows the classpath in use and `tlaup module dir` the folder." "`tlaup tlc --version` is removed; use `tlaup tool current`." "`tlaup tools dir` is now `tlaup tool dir` and prints only the folder; use `tlaup tool list --installed` for the builds." "`tlaup tools install -f` and `tlaup tools uninstall -y` are now `tlaup tool install --force` and `tlaup tool uninstall --yes`." "`tlaup tools` and `tlaup modules` are now `tlaup tool` and `tlaup module`; every subcommand keeps its name." The row on `config edit` has its entry in [14 F5](14-config-and-cli.md#f5-config-edit), and is not repeated here. (Stage 4 review, 2026-11-24: `doctor`'s levels, an error being what stops a run with 3, question Q15; `cache clean --all` with a kind widens that kind, and the Java check goes only when no kind is named, question Q14; nothing to clean exits 0, preserved-behaviour row O7; their scenarios; the duplicate `config edit` entry dropped, index "Clerical"; the module folder's `.tmp/` and `.lock` are not leftovers, finding H1; the forms of `config show` and `config get` point to 14 F1, settled with the maintainer on 2026-11-24.)

**Depends on.** Everything it names; the tree is cut into packages per group. **Risks.** This is the second of the release's two large user-visible changes. It lands once, in 0.9.0 (D6), with the changelog as the upgrade guide.

## C2 Typing versions

Roadmap: "Typing versions: accept a version without the `v`; the shortcuts `latest`, `stable` and `rolling`; a command that shows what is pinned; fix the 'Tag/SHA' column label, which holds a commit."

| Point | Design |
| --- | --- |
| Without the `v` | [02 X3](02-cross-cutting.md#x3-version-syntax). |
| Shortcuts | `stable` and `rolling`. `latest` is refused with a message naming both (D31); this departs from the roadmap's list. D31 also names `tag@commit` and `tag@CalVer`. Two more forms are this design's additions: a build time alone (`2026.11.15.002146`), and `name@sha256:...` for an installed build that neither a commit nor a build time tells apart ([02 X3](02-cross-cutting.md#x3-version-syntax)). |
| What is pinned | `tool current` (C1). |
| The column label | "Build" ([12 V8](12-tools-and-downloads.md#v8-remote-listing-and-its-cache)). |

Every command that takes a version takes a version spec: `install`, `upgrade` (a name only), `uninstall`, `pin`, `path`. All five parse it with `parse_version_spec` and look it up through the store or the remote, so the accepted forms cannot differ between commands.

**Tests.** A scenario outline (in-process) runs `tool pin` with `v1.7.4`, `1.7.4`, `stable`, `v1.7.4@5a47802` against the same store and asserts the same pinned build each time; the same outline for `path` and `uninstall`. `tool upgrade v1.7.4@5a47802` exits 2. `tool install https://example.org/tla2tools.jar` exits 2.

## C3 Completion

Roadmap: "Shell completion, with completers for installed versions and module names." Exit criterion: "completion works in bash, zsh and fish."

**Facts (tried on the locked Typer 0.29.1; other versions were not tried).** The first version of this design said the command would use "Click's built-in completion" and its `<shell>_source` instruction. That does not exist here: Typer carries a private copy of Click and replaces its completion with its own.

- With `add_completion=False`, as tlaup has today, starting the program with `_TLAUP_COMPLETE=complete_bash` prints "Shell bash not supported." and exits 1. Typer's shell classes are registered only when completion is switched on.
- After a call to `typer._completion_classes.completion_init()` before the app runs, the same start with `COMP_WORDS="tlaup tool pin "` and `COMP_CWORD=3` printed the words a completer function returned, one per line, and exited 0.
- `typer._completion_shared.get_completion_script(prog_name="tlaup", complete_var="_TLAUP_COMPLETE", shell=...)` returns a script for `bash`, `zsh` and `fish`. Read from the installed Typer, the scripts call the program back like this: bash with `COMP_WORDS`, `COMP_CWORD` and `_TLAUP_COMPLETE=complete_bash`; zsh with `_TYPER_COMPLETE_ARGS` and `_TLAUP_COMPLETE=complete_zsh`; fish with `_TYPER_COMPLETE_ARGS`, `_TYPER_COMPLETE_FISH_ACTION` and `_TLAUP_COMPLETE=complete_fish`.
- Both modules are private (their names start with an underscore). Typer's public way to get the same script is the root option `--show-completion`, which exists only with `add_completion=True`.
- `import typer` alone loads `typer._completion_classes` and `typer._completion_shared`, so every start of tlaup has them in `sys.modules` (tried: `python -c "import typer, sys; ..."` lists both, and so does `import tlaup.cli` today). What stays empty until `completion_init()` runs is Typer's registry of shells, `typer._click.shell_completion._available_shells`: `{}` before the call, five shells after.

**Design.**

- `tlaup completion bash|zsh|fish` prints the completion script for that shell on stdout: the text `get_completion_script` returns for the program name `tlaup` and the variable `_TLAUP_COMPLETE`. The help shows the one line to put in the shell's start-up file for each (`eval "$(tlaup completion bash)"` and its equivalents). The shell is a required argument with three allowed values; another value is a usage error (2).
- `main()` calls `completion_init()` before the app runs when the variable `_TLAUP_COMPLETE` is set in the environment, and not otherwise, so an ordinary start has completion switched off: the shell registry stays empty. It does not keep a module from loading; Typer has loaded its completion modules by then (above). The probe above called it unconditionally; with the variable set the path is the same.
- `tlaup/cmd/completion.py`, which holds the `completion` command and the completers, is imported at the top: by `cli.py`, which registers the command, and by each command module that names a completer in `autocompletion=`. That costs nothing Typer has not already loaded, as long as the completers import the store, the registry and the settings schema inside their own bodies, which they do. It is the one exception to [14 F9](14-config-and-cli.md#f9-startup-cost)'s rule that a command module imports only `typer`, `tlaup.errors` and `tlaup.context` at the top, and F9 names it.
- The app's program name is fixed to `tlaup` ([14 F10](14-config-and-cli.md#f10-no-tracebacks)), because Typer derives the variable's name from it.
- The two private names are imported in one module, `tlaup/cmd/completion.py`, and nowhere else.
- Typer's own `--install-completion` and `--show-completion` stay off (`add_completion=False`): they add two options to the root help of every invocation, and the first writes into the user's shell files, which a tool should not do unasked.
- Completers, each reading the store or the registry only, never the network and never the settings:
  - installed versions, for `pin`, `uninstall`, `path`: every installed build in its printed form ([02 X3](02-cross-cutting.md#x3-version-syntax)), plus each distinct name, plus `stable` and `rolling`;
  - `upgrade`: the distinct names of installed builds only, since `upgrade` takes a name and rejects `name@commit` ([12 V4](12-tools-and-downloads.md#v4-upgrade-and-pin));
  - `install`: `stable`, `rolling`, and the tags of the remembered release list if a lookup cache file exists (no request is made);
  - module names, for `module remove`;
  - config keys, for `config get` and `config set`: from the schema;
  - `SPEC`: `*.tla` files, through the shell's file completion.
- A completer that fails for any reason returns nothing; completion never prints an error into the user's prompt.
- **In bash, completion of a build stops at the `@`.** Bash splits the word under the cursor at the characters of `COMP_WORDBREAKS` before Typer's script is called, and by default these include `@` and `:` (read from bash on one Linux machine: a plain bash had both; an interactive one there had `@` taken out by its start-up files). Tried with the calls the generated script makes: for the word `rol` the completer's words come back, whole printed forms included (`rolling`, `rolling@bc1b506`, `rolling@1a2b3c4`); with the words as bash splits them after a typed `rolling@` (`rolling`, `@`, and an empty word) nothing comes back; with the word unsplit (`rolling@`), as when `@` is not a word break, the two builds come back. So in a default bash, names complete, and a build is completed only up to the name; the rest is typed, or copied from `tlaup tool list --installed`. zsh and fish pass the whole word. Working around the split, as some bash completions do for `:`, needs a script of tlaup's own in place of Typer's; not done. The help of `completion` says so in one line.

**Rejected.** *Switching Typer's completion on and telling users to run `tlaup --show-completion`*: public API, but it detects the shell from the parent process instead of taking it as an argument, cannot print the script for another shell, and brings `--install-completion` with it. *Writing the three shell scripts by hand*: they must match the protocol of the installed Typer, which is exactly what its own templates do. *A `completion install` command*: writes into shell start-up files.

**Checked by research 23** (top-up, [result](../research/23-typer-versions.md)). `typer._completion_classes.completion_init()` and `typer._completion_shared.get_completion_script(*, prog_name, complete_var, shell)` exist with the same signatures in every release from 0.22.0 to 0.29.2 (all 26 wheels read), and the three protocols gave the same words on every version run. Without `completion_init()` Typer 0.22.0 to 0.25.1 answer in Click's own format, which the generated bash script cannot read; tlaup always calls it when the variable is set, so it is not affected. The bash `@` limit above holds on all of them. So the three real-process tests and the contract test hold on the chosen bound, `typer>=0.27.2,<1.0.0` ([30 B2](30-ci-and-release.md#b2-build-fixes)), which `typer.TyperException` sets ([14 F10](14-config-and-cli.md#f10-no-tracebacks)), not completion.

**Tests.** Unit: each completer with a prepared store, called directly, returns the expected words; that Typer's registry of shells stays empty on an ordinary start and is filled only by `completion_init()` is the test of [14 F9](14-config-and-cli.md#f9-startup-cost), with the name checked by the Typer contract tests of [14 F10](14-config-and-cli.md#f10-no-tracebacks), and is not repeated here; F9's import test still finds none of its listed modules after `import tlaup.cli`; with a broken `build.json` in the store it returns the rest; the `upgrade` completer returns no `name@commit`. A feature (in-process) asserts `tlaup completion bash`, `zsh` and `fish` each exit 0 with a stdout that contains `_TLAUP_COMPLETE` and `tlaup`, and an unknown shell exits 2. Real process, in the default suite on every system, with no shell involved: `python -m tlaup` started with `_TLAUP_COMPLETE=complete_bash`, `COMP_WORDS="tlaup tool pin "` and `COMP_CWORD=3` against a prepared store prints the installed builds, one per line, and exits 0; the same with `COMP_WORDS="tlaup tool pin rolling @ "` and `COMP_CWORD=5` prints nothing and exits 0, which pins down the bash limit above so that a change in it is noticed; the same for fish with `_TYPER_COMPLETE_ARGS="tlaup tool pin "` and `_TYPER_COMPLETE_FISH_ACTION=get-args`; for zsh with `_TYPER_COMPLETE_ARGS="tlaup tool pin "` the output is an `_arguments` call for the shell to evaluate, and the test asserts it names each installed build. All three calls were tried on Typer 0.29.1 with a small app and gave those results. They use the variables the generated scripts use, read from the script text, and they are what fails first if a Typer release changes the protocol. The names and signatures of the two private modules are also checked on their own by the Typer contract tests ([14 F10](14-config-and-cli.md#f10-no-tracebacks)), which name the one that changed. Integration (Linux job only): the bash script is sourced in a non-interactive bash, and the function it defines is called with `COMP_WORDS` and `COMP_CWORD` set as bash would set them, asserting `COMPREPLY` holds the installed builds; for zsh and fish the script is loaded with the shell's syntax check (`zsh -n`, `fish --no-execute`) when the shell is present on the runner, and skipped with a reason otherwise.

**Changelog.** Added: "`tlaup completion bash|zsh|fish` prints a shell completion script. Installed versions, module names and config keys are completed. In bash, a build is completed up to its name; the part after `@` is typed."

**Depends on.** C1, V1, M2, F10. **Risks.** The command is built on two private Typer modules. A Typer release can rename them or change the variables; the guards are the version bound, the Typer contract tests of F10, the three real-process tests above, and the newest-dependencies job ([30 I3](30-ci-and-release.md#i3-newest-dependencies-job)), which runs them against each new Typer. If Typer drops them, the fallback is the rejected `--show-completion`. Completion in a real interactive zsh and fish is checked by hand once before the release; the automated checks cover syntax, the protocol and the completers, not the shell's behaviour. So the exit criterion "completion works in bash, zsh and fish" is met by automated tests for bash and by a hand check for the other two. PowerShell is not offered (D15), though Typer could generate it. (Stage 4 review, 2026-11-24: the first wording said an ordinary start does not import the completion module, which is false on the locked Typer, since `import typer` loads it; what stays off is the shell registry, and `tlaup/cmd/completion.py` is imported at the top as F9's one exception; review finding D1, not decision D1.)

## C4 Version flag

Roadmap: "Move the version flag to `-V` so `-v` can mean verbose."

**Design.** The root option is `--version` and `-V`. `-v` is left free for `--verbose` in milestone 4; until then `-v` is an unknown option. `tlaup --version` prints two lines: `tlaup 0.9.0` (with `+<commit>` for an editable install, [14 F9](14-config-and-cli.md#f9-startup-cost)) and the package's one-line summary, which is the same text the root help shows ([14 F7](14-config-and-cli.md#f7-help-text)).

**Tests.** Plain pytest: `-V` and `--version` print the same and exit 0 (two results compared with each other, [01 T5](01-testing.md#t5-feature-files-and-steps)). A scenario in `errors.feature`: `-v` exits 2. (Stage 4 review, 2026-11-24: the first form was a feature, which no step can compare; finding H7.)

**Changelog.** Breaking: "The version flag is `-V` (was `-v`). `-v` is reserved for `--verbose`."

## C5 Help and the CLI reference

Roadmap (milestone 1): the help text item ([14 F7](14-config-and-cli.md#f7-help-text)). Roadmap (documentation track): "CLI reference generated from the code, with CI failing when the checked-in copy drifts." The second is a documentation-track item; its mechanism is designed here because it is how help text is reviewed and tested without asserting on wording ([01 T12](01-testing.md#t12-rules-for-writing-tests), rule 4).

**Design.**

- `uv run poe docs-cli` writes `docs/reference/cli.md` from the Typer app: for every command, its usage line, description, arguments, options and epilog, walking the Click command tree at a fixed width of 100 columns with colour off. A small script, `scripts/gen_cli_reference.py`, does it. Typer has a documentation generator of its own (`python -m typer <module> utils docs`). Research 23 found its output the same at any width and colour setting and on a second run, but its notation changes between Typer releases (four different files over thirteen versions), it writes quotes as `&#x27;` and it ignores `rich_help_panel` groups; the checked-in reference should change when help text changes, not when Typer changes its notation, so the script stays the plan (agreed in the walk-through of the top-up results, 2026-11-20), and it uses only `typer.main.get_command(app)` and the public attributes of the commands it walks.
- A test regenerates the reference in memory and compares it with the checked-in file through the expected-file helper ([01 T8](01-testing.md#t8-expected-output-files)). A change to any help string therefore shows up as a diff of `docs/reference/cli.md` in the pull request, where it is read.
- The file starts with a line saying it is generated and how.

**Tests.** The drift test above, in the default suite.

**Changelog.** None (documentation).

**Depends on.** C1, F7. **Risks.** The command objects the script walks are Typer's copy of Click's. On Typer 0.29.1, `typer.main.get_command` returns a group with `commands`, `params`, `help` and `epilog` (tried on a small app); another Typer version may differ, and the drift test fails loudly if it does.
