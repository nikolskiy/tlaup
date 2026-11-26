# 50. Help text, wording and error messages

Size: M. Suggested model: mid-tier. Status: built.

## Goal

Every command's help says what the raised list asks for, the root help is grouped in three panels and shares its one summary line with `--version`, a stopped run is "interrupted" everywhere, module times carry their time zone, the two changelog typos are fixed, and each error message of the raised list is shown by a scenario to carry the fact that matters. Also, now that every command prints through `Ui`, the changelog says so.

## Covers

- Roadmap items ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)):
  - "Help text (raised list): what `upgrade` means ...; examples or a longer description on the main commands, since none has any and the generated reference is built from help." (line 277), in full apart from the generated reference ([51](51-cli-reference.md)).
  - "Wording: one word for a stopped run ('canceled' and 'stopped' are both used); module timestamps with a time zone; the typos listed in the report." (line 278), in full: most of it is built by earlier packages, which this one checks and completes.
  - "Error messages (raised list): list the locations searched when a spec is not found; 'did you mean v1.8.0' for a version typed without the `v`; say when GitHub rate-limited the request and how to give a token; add the next command to 'no pinned version' errors; drop 'Successfully installed' after 'already installed' and mention `--force`; show the classpath when `javac` fails." (line 275), in full: each message is built where it is raised; this package adds the scenarios and closes what is missing.
  - "Route every message through the one UI helper; ..." (line 276), in part: the check that nothing is left and the two changelog entries (see Changelog).
- Design sections:
  - [14 F7](../design/14-config-and-cli.md#f7-help-text), in full.
  - [14 F8](../design/14-config-and-cli.md#f8-wording), in full (the parts built by 09, 30, 31, 38 and 40 are checked here).
  - [14 F11](../design/14-config-and-cli.md#f11-error-messages), in full: the checklist and its scenarios.
  - [14 F6](../design/14-config-and-cli.md#f6-messages), in part: the Changed and Fixed entries and the check that no old message helper is left (proposed by stage 4; see Changelog).
  - [23 C4](../design/23-command-layout.md#c4-version-flag), in part: "the package's one-line summary, which is the same text the root help shows". `-V` itself is [48](48-command-tree.md).
  - The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md), row T8 (an unknown version name is an error naming it), whose owner this package is: its `errors.feature` scenario is F11's "closest tag" row below; the row's "With" part is [29](29-tool-commands.md)'s `VersionNotFound` scenarios (`tool_uninstall.feature`'s `v1.8.0 nosuch`, `tool_pin.feature`'s `tool pin v1.8.0`). Row P5 (help shows every command with a one-line description, and `tlc --help` lists its options), with [51](51-cli-reference.md), its owner: this package writes the one-line help of every command and the help of each `tlc` option, and 51's test asserts that none is missing (finding H13).

## Depends on

- [48](48-command-tree.md): every command of the tree exists, is registered in `cli.py`, and has its options; through 48, every package that raises the errors of F11 ([32](32-spec-resolution.md) `SpecNotFound` and `CfgNotFound` with the paths tried, [25](25-remote-listing.md) and [27](27-install-steps.md) `VersionNotFound` and "already installed", [24](24-github-client.md) `RateLimited`, [28](28-first-run.md) and [33](33-tlc-invocation.md) `NoPinnedBuild`, `NoToolsInstalled`, `PinnedBuildMissing`, [30](30-module-build.md) `ModuleBuildError.details`), the step vocabulary and `errors.feature` ([18](18-feature-harness.md)). Not a dependency, though numbered later (reconciled by stage 4): the package description of [56](56-build-and-metadata.md) (B3), the one sentence shared with the root help. 56 runs in the CI group, which can start from 03, so it is normally merged by now; if it is not, this package writes the sentence into `pyproject.toml`'s `description` itself and 56 keeps it.

## Files

Changes:

- Every command module under `src/tlaup/cmd/` and `src/tlaup/cli.py`: help strings, `rich_help_panel` on each top-level command, epilogs, argument and option help. Nothing else in them.
- `src/tlaup/cli.py`: the root help's summary is read from the package metadata (`importlib.metadata.metadata("tlaup")["Summary"]`), the same text `--version` prints; no second copy in the code.
- `CHANGELOG.md`: the entries below, and the two one-word corrections in the history (F8): in 0.7.0, "compiles Java overrides and copy subfolders" becomes "copies subfolders"; in 0.5.0, "The TLC output now parsed" becomes "is now parsed".
- `tests/features/errors.feature`: the F11 scenarios.
- Any `src/` file where a user-visible "canceled", "cancelled" or "stopped" for a run, or a module time without its zone, is still found (expected: none; see Context).

Creates: nothing, unless an F11 message turns out to lack its fact, in which case the raising module is changed (see Context).

Deletes: any of the four old functions of `tlaup/ui.py` (`warn`, `error`, `info`, `success`) still present ([16](16-ui-messages.md) kept them for the old commands; they should have gone with their last caller).

Shared: the command modules with [49](49-startup-cost.md), which runs beside this package after 48 (imports against help strings; small). `CHANGELOG.md`.

## Interfaces

None new. The help texts, from [14 F7](../design/14-config-and-cli.md#f7-help-text):

| Point | Text or change |
| --- | --- |
| What `upgrade` means | "Replace an installed version with the newest build of the same name. Rolling builds are rebuilt often; this fetches the current one. It does not move to a different version: use `install` for that." |
| `install` with no version; first install is pinned | "With no VERSION, asks whether to install `stable` or `rolling`. The first build installed is pinned." |
| `module` wording | "Manage your own TLA+ modules, with optional Java operator overrides." |
| The layout `module add` expects | A long description: `modules/*.tla`, `modules/tlc2/overrides/*.java` or `tlc2/overrides/*.java`, `lib/*.jar`; the folder's name becomes the module's name; an existing module of that name is replaced. |
| `SPEC` | "A TLA+ spec: a name (`Spec`), a file (`Spec.tla`) or a path. `spec/Spec.tla` is tried too." |
| `--raw` | "Print TLC's own output unchanged, with no parsing or formatting." |
| Scope of `--yes` | "Answer every question of this command with yes." |
| `tool path VERSION` | Gets a help string. |
| "TLC" where the toolset is meant | "TLA+ tools" in every `tool` help string. |
| One summary line | The package summary in `pyproject.toml` is the one source; the root help reads it from the metadata. |
| Root help order | Three panels: Run (`tlc`, `sany`, `pcal`, `repl`), Manage (`tool`, `module`, `config`, `cache`), Maintenance (`doctor`, `completion`). |
| Examples | `tlc`, `tool install`, `module add` and `sany` get an epilog with two or three example commands. |

Help strings other packages already fixed, which this package keeps and does not rewrite: `config set` ("Rewrites the config file. Comments in it are not kept; use `tlaup config edit` to keep them.", [14 F1](../design/14-config-and-cli.md#f1-layered-configuration), [44](44-config-commands.md)); `--refresh-interval` has no effect in plain mode or with `--raw` ([22 O5](../design/22-reporters.md#o5-refresh-interval)); `--raw` on Windows does not stop TLC when the reader goes ([11 R1](../design/11-runner.md#r1-run-errors-reported-as-what-they-are)); `completion`'s line on bash and `@` ([23 C3](../design/23-command-layout.md#c3-completion)); `cache clean` never touches tools or modules ([23 C1](../design/23-command-layout.md#c1-command-tree)). Where one of those sentences and an F7 text belong to the same option, both are kept.

## Tests that must pass

F7: "No test asserts a help sentence." The help is checked by reading it ([23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference)); see "How 50 and 51 divide the review".

F8: through the reporter's expected files ([38](38-terminal-reporter.md), [40](40-live-display.md)) and `modules.feature`'s check that `module list` shows `UTC` ([31](31-module-commands.md)); this package adds no test for them, and fails its own check (Done when) if one of them is missing.

F11: one scenario each in `tests/features/errors.feature`, in-process, asserting the fact that matters and not the sentence ([01 T12](../design/01-testing.md#t12-rules-for-writing-tests) rule 4), each also asserting the code and `stdout is empty`:

| Point | Scenario |
| --- | --- |
| Locations searched for a spec | `tlaup tlc Nope` in a folder with no such spec: exit 4, `stderr contains` the path `{work}/Nope.tla` and the path under `{work}/spec/`. |
| Locations searched for a cfg | With a spec present, `tlaup tlc Spec --cfg nope.cfg`: exit 4, `stderr contains` one of the paths tried ([11 R4](../design/11-runner.md#r4-spec-cfg-and-working-folder)). |
| A version typed without `v` | No longer an error ([02 X3](../design/02-cross-cutting.md#x3-version-syntax)); `tool pin 1.7.4` pinning `v1.7.4` is [29](29-tool-commands.md)'s scenario. For a name that matches nothing (inventory row T8): `GitHub answers from "releases"`, `tlaup tool install v1.7.5`: exit 4, `stderr contains "v1.7.5"` (the name typed) and `stderr contains "v1.7.4"` (the closest tag; if 25 or 27 built the suggestion for installed builds only, use `the build "v1.7.4" is installed` and `tool pin v1.7.5`, and say so in the pull request). |
| Rate limit and token | `GitHub answers from "rate-limited"`, `tlaup tool install stable`: exit 5, `stderr contains "GITHUB_TOKEN"`. |
| Next command for "no pinned version" | `the build "v1.7.4" is installed` (not pinned) and a spec: `tlaup tlc Spec`: exit 3, `stderr contains "tlaup tool pin"`. `no build is installed`, `tlaup tlc Spec --show-command`: exit 3, `stderr contains "tlaup tool install"`. |
| "Already installed" | `the build "v1.7.4" is installed`, `GitHub answers from "releases"`, `tlaup tool install v1.7.4`: exit 0, `stderr contains "--force"`, `stderr does not contain "Successfully"`. |
| Classpath when `javac` fails | `javac fails with "<recording>"`, `tlaup module add` on a module source with an override: exit 5, `stderr contains "tla2tools.jar"` (the classpath is in the details). |

If one of these scenarios already exists in another feature file, it is still added to `errors.feature`, as F11 says; keep the two identical.

No stateful test applies. The pull request names inventory row T8 as covered.

## Changelog

Under `## [Unreleased]`, word for word unless said.

From [14 F7](../design/14-config-and-cli.md#f7-help-text):

- Changed: "Help text rewritten for `tool`, `module` and `tlc`; root help is grouped."

From [14 F8](../design/14-config-and-cli.md#f8-wording):

- Changed: "A run stopped with Ctrl-C is called 'interrupted' everywhere."

F8's other entry, "`module list` shows build times in UTC.", is [31](31-module-commands.md)'s, where the user first sees it (review findings D5, B15); it is not written here.

From [14 F11](../design/14-config-and-cli.md#f11-error-messages):

- Changed: "Error messages name what was searched and the command to run next."

From [14 F6](../design/14-config-and-cli.md#f6-messages), written here because this is the first package after the last command was moved onto `Ui` (proposed by stage 4; [16](16-ui-messages.md) wrote none):

- Changed: "Messages have the form `error: ...`, `warning: ...`, `hint: ...` on stderr, without symbols."
- Fixed: "`NO_COLOR` is honoured everywhere."

F6's third entry, "A warning from `tool list` went to stdout.", is [29](29-tool-commands.md)'s.

## Context for the worker

**How 50 and 51 divide the review of help text.** F7 says the review reads the generated CLI reference, not assertions on wording. In the cut, [51](51-cli-reference.md) (the generator `scripts/gen_cli_reference.py`, `uv run poe docs-cli`, `docs/reference/cli.md` and its drift test, [23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference)) comes after this package. So:

- **50 owns the text.** Every string of the F7 table, the panels, the epilogs, the summary. Its pull request carries the full help of every command, at 100 columns with colour off (`COLUMNS=100 NO_COLOR=1 uv run tlaup <command> --help` for the root, each group and each command), pasted into the description or attached as one file, so the reviewer reads every string in its place. That dump is not committed.
- **51 owns the generator, the drift test and the first checked-in reference.** Its reviewer reads `docs/reference/cli.md` as a whole against F7's table once, and from then on any help change shows up as a diff of that file in its own pull request. The index settles this order under "Why the cut is this way" (help text before the reference), so the text is reviewed once.

**F8, piece by piece, and who built it.**

- "interrupted": `CheckState.Stopped` became `Status.INTERRUPTED` ([10 P3](../design/10-parser.md#p3-result-model), [09](09-parse-package-and-model.md)); the summary line "Interrupted after 02:13." ([38](38-terminal-reporter.md)); the live layout's key hint "Ctrl-C to interrupt" and the phase "Interrupted" ([40](40-live-display.md)). Here: `grep -rniE "cancel+ed|cancelling|stopped"` over `src/` and the help, and change any user-visible text about a run to "interrupted". Words that mean something else (a process "stopped by a signal tlaup did not send" in a comment, TLC's own text passed through) stay.
- Module times: stored in UTC with `Z` and shown as `2026-11-15 10:00 UTC` ([13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder), [30](30-module-build.md), [31](31-module-commands.md)). Check `module list` once by hand.
- Typos: the comment in `java/inspector.py` ("might minimal output") and its reference to a document that does not exist went with the rewrite of that file ([13 J2](../design/13-modules-and-java.md#j2-finding-java), [20](20-java-location.md)); check that `java/inspector.py` is gone or the comment is. The two changelog typos are corrected here, two one-word edits to the history, and not handed to the documentation track's changelog item, which leaves the rest of the history alone.

**F11, piece by piece.** Each message is designed where its error is raised ([14 F11](../design/14-config-and-cli.md#f11-error-messages)'s table). The scenarios above are the check. If one fails because the fact is missing from the message (for example `ModuleBuildError` without the classpath in its details), fix it in the raising module, in this pull request, and say which; do not reword messages that already carry their fact. Do not add a "did you mean" for a missing `v`: a version without `v` is accepted (X3).

**The summary line.** [30 B3](../design/30-ci-and-release.md#b3-package-metadata) ([56](56-build-and-metadata.md)) writes `description` in `pyproject.toml` as one sentence shared with the root help. `--version` (48) already prints it from the metadata; the root help must read the same field, not a string in `cli.py`. In a development checkout the metadata is that of the editable install, refreshed by `uv sync`.

**Panels.** Typer's `rich_help_panel` on `app.command(...)` and `app.add_typer(...)` gives the three panels. Panels appear in the order of first use, so the registration order in `cli.py` decides it (Run, Manage, Maintenance, and the commands inside each in F7's order). Typer's own documentation generator ignores panels ([23 C5](../design/23-command-layout.md#c5-help-and-the-cli-reference)); 51's script must show them, which is 51's concern.

**Traps.**

- Help strings are Typer's docstrings and `help=` arguments; Typer renders them with Rich markup on by default (`rich_markup_mode`). Backticks and square brackets in the F7 texts must come out as typed; check the rendered help, not the source.
- An epilog's example lines must not be re-wrapped into one paragraph; use Typer's way of keeping lines (a blank line between them, or the `\b` marker Click understands) and check the rendered result.
- No test asserts a help sentence (F7; T12 rule 4). Do not add one.
- `docs/reference/cli.md` does not exist before 51; do not create it here.

**Decisions this rests on.** D47 (singular group names). D38 (no short forms; nothing in the help offers `ls` or `rm`). The design agent's decision that a stopped run is "interrupted" (one word, the usual one for exit 130).

**State of `main` when this starts.** The command tree of [23 C1](../design/23-command-layout.md#c1-command-tree) is complete (48); every command prints through `Ui` or raises; `-V` prints `tlaup 0.9.0` and the summary. [49](49-startup-cost.md) may be in progress on the same files.

## Done when

- Every row of the F7 table is in the rendered help; the root help shows three panels in F7's order and the summary from the metadata; the pull request carries the help dump.
- The F11 scenarios pass.
- No user-visible "canceled", "cancelled" or "stopped" for a run is left in `src/`; `module list` shows `UTC`; the two changelog typos are corrected.
- No old message function is left in `tlaup/ui.py`; no `typer.echo` remains outside `ui.py` and the reporters (`grep`, ahead of [58](58-lint-rules.md)'s rule).
- The changelog entries are written.
- The pull request names inventory row T8, which it owns, and its part of P5 (every command's one-line help, every `tlc` option's help; 51's test holds the row).
- `uv run poe lint` and `uv run poe test` pass; CI is green.

## Out of scope

- The CLI reference, its generator and its drift test: [51](51-cli-reference.md).
- Building the errors of F11: the packages named under Depends on.
- `-V`, the removed names, the tree test: [48](48-command-tree.md).
- The lint rules against `print`, `typer.echo` and `Console(`: [58](58-lint-rules.md).
- The README, the reference pages and the guides: the documentation track.

## Risks

- From F7: help text is reviewed by reading it, so a wrong sentence is caught only by a reader. The dump in the pull request is what makes every string visible at once.
- From the cut: until 51 lands, nothing stops a later pull request from changing help text unreviewed; 51's drift test closes that.
- From F11: a scenario that asserts a fact can pass while the sentence around it is poor; so the pull request also pastes the stderr of each F11 scenario, and the reviewer reads those lines as text.
