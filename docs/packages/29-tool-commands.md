# 29. The `tool` commands: switch to the new store

Size: L. Suggested model: most capable. Status: ready, except two tests that wait on question "debug filter" of the index (the token-secrecy scenario and the `--debug` half of the query-string test, marked under Tests), and the command side of question "uninstall race" (package 27).

This is the switch package of the store track. It is large for one pull request; a split that keeps `main` releasable is proposed under Risks.

## Goal

`tlaup tool` (D47) is the command group for TLA+ tools builds: `list`, `install`, `upgrade`, `uninstall`, `pin`, `current`, `path` and `dir`, each a thin module under `src/tlaup/cmd/tool/` over the domain code of packages 22 to 28, with version specs everywhere, questions only on a terminal, and the exit codes of [02 X1](../design/02-cross-cutting.md#x1-exit-codes). The old `tools` and `fetch-cache` groups, the old store code and its tests are gone; five feature files state the behaviour; the changelog says what a user sees. The old `tlaup tlc` and the old module commands still work and find the pinned jar in the new store.

## Covers

- Roadmap items, milestone 1 ([link](../roadmap.md#milestone-1-a-runner-you-can-trust)):
  - "Fix `tools uninstall --all`, which stops after removing the pinned version ..." and "A failed uninstall exits non-zero and does not move the pin; the build-selection prompt rejects negative indexes." Closed here: the command, its prompt and its feature file; the domain part was 27.
  - "Concurrent installs: write the pin and metadata atomically and take a lock ...", in part: its changelog entry. The work was 23 and 27.
  - "Remove installs from a URL (decision D13). ...", in part: `tool install https://...` exits 2 through the version grammar (22); the removal was 04.
  - "Download to a temporary file, check it is a valid jar, then rename. ...", in part: what a user sees (`tool_install.feature`, the changelog). The work was 23, 26 and 27.
  - "After download, compare the commit the jar reports about itself with the expected commit ...", in part: the user-visible rows and the changelog.
  - "Read all pages of tags and releases; choose 'latest stable' by version, not by API order; never install a prerelease while saying 'stable'. ...", in part: `tool list` and the changelog. The listing was 25.
  - "GitHub token support (`GITHUB_TOKEN`, `GH_TOKEN`), ... The token is never printed, including by `--show-command` and `--debug`, and is sent only to the GitHub API host. ...", in part: reading the token and the settings, the feature scenario that it is never printed (waiting, see Status), the changelog. The client was 24.
  - "Refuse unencrypted addresses and any redirect to one.", in part: the changelog. The work was 24.
  - "Do not crash on a non-JSON or non-list API response. Key the remote-version cache on the request ... `tools upgrade`, and an install of a moving tag, check the remote again ...", in part: `tool upgrade`, `tool install` and the changelog.
  - "First-run prompt (decision D4): ...", in part: `tool install` with no version asks the same question. The run commands are 39 and 41 to 43.
  - "Remove the legacy fallback jar path ... A pin that points at a missing build is a clear error with a hint, not a silent fallback.", in part: `tool current` and `tool path` show `PinnedBuildMissing`; the old `get_tlc_jar_path` reads the new store. 04 removed the fallback; 39 deletes the function.
  - "Route every message through the one UI helper; there are 21 hand-written error prints and a warning printed to stdout in `tools list`.", in part: every print of the old `tools` commands goes, and the `tool list` warning is on stderr. The helper is 16.
- Milestone 1b ([link](../roadmap.md#milestone-1b-other-tools-reporters-command-layout)):
  - "Review the layout of every command so it follows the most common CLI patterns ...", in part: the `tool` group, `tools meta sync` removed, `dir` and `path` with one meaning each, no `-f` and `-y`. The tree test and the removed names' scenarios are 48; the other groups 31, 39, 44, 45, 46, 47.
  - "Typing versions (note 45): accept a version without the `v`; the shortcuts `latest`, `stable` and `rolling`; a command that shows what is pinned; fix the 'Tag/SHA' column label, which holds a commit." Closed here.
- Milestone 3, done in milestone 1 ([link](../roadmap.md#milestone-3-reproducibility)): "Version identity as a type, not a parsed folder name. ...", in part (the store is used by every command and the old folder-name code is deleted); "Adopt upstream's `rolling` release ...", in part (`tool list` order); "`tools meta sync` matches by tag name only ... Fix it, or remove the command ..." (removed); "`tools upgrade` by name compares only the first of several installed builds of that tag." (the command).
- Milestone 4, in part ([link](../roadmap.md#milestone-4-automation-surface)): "Non-interactive version selection: accept `tag@sha` ... error instead of prompting when stdin is not a terminal ... `tools path` checks that the jar exists and does not silently pick the first of several builds." The `tool` group's part; `--yes` for every prompt is the milestone's.
- Design sections:
  - [23 C1](../design/23-command-layout.md#c1-command-tree): the `tool` rows of the tree; the rows "`tools meta sync` is removed", "`dir` always prints a folder; `path` always prints a file", "`tool current` is new", "`tool list --installed` is new", "`tools` becomes `tool`" (D47), "`uninstall` keeps an optional `VERSION...` and checks by hand", "The short options `-f` and `-y` are removed", D43's row; explicit registration for this group. Not here: the tree test, the removed names' "exit 2" scenarios (48), the other groups.
  - [23 C2](../design/23-command-layout.md#c2-typing-versions): all of it.
  - [12 V3](../design/12-tools-and-downloads.md#v3-uninstall), [V4](../design/12-tools-and-downloads.md#v4-upgrade-and-pin), [V12](../design/12-tools-and-downloads.md#v12-install): the command side (selection, the `--all` table, notes, exit codes), the feature files, the changelog. The domain side was 27.
  - [12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache): "`tool list` in the first wave", `tools_list.feature`, the changelog.
  - [02 X3](../design/02-cross-cutting.md#x3-version-syntax): "When a spec matches several installed builds" and its scenarios; "What is printed" as the commands use it; the changelog.
  - [02 X4](../design/02-cross-cutting.md#x4-rolling): the order of `tool list`, the changelog.
  - [12 V1](../design/12-tools-and-downloads.md#v1-version-store), [V5](../design/12-tools-and-downloads.md#v5-download-and-verify), [V7](../design/12-tools-and-downloads.md#v7-github-client), [V11](../design/12-tools-and-downloads.md#v11-concurrent-installs): the feature scenarios and plain pytest tests the sections give to the commands, and every changelog entry of these sections. V2: the deletion of `resolve_latest_version`. V10: the rest of package 04's work on `get_tlc_jar_path`, as far as this switch reaches.
  - [13 J3](../design/13-modules-and-java.md#j3-one-java-start): the `tool_install.feature` scenario with no Java, the deletion of `_extract_tlc_version`, the entry "Installing tools without Java present recorded an empty version."
  - [14 F6](../design/14-config-and-cli.md#f6-messages): the entry "A warning from `tool list` went to stdout.", which a user first sees here.
  - [14 F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay): the feature "`tool.repository` set to another `https` address is the host the requests go to", unless package 19 already has it.

## Depends on

- [27](27-install-steps.md): `install`, `upgrade`, `uninstall`, `pin`, `choose_build`, their reports, `same_as_published`.
- [28](28-first-run.md): `choose_first_build`, `read_auto_install`.
- [23](23-tool-store.md), [25](25-remote-listing.md), [26](26-download-and-verify.md), [24](24-github-client.md), [22](22-version-spec-and-jarinfo.md): `ToolStore`, `Build`, `format_build`, `sort_key`; `Remote`, `Freshness`, `write_cache`; `fetch_build`; `GitHubClient`, `token_from_env`, `Progress`; `parse_version_spec`.
- [17](17-error-handler.md): the root group that maps `TlaupError` to its code and Typer's usage errors to 2, `--debug`, the 141 rules.
- [18](18-feature-harness.md): `tests/test_features.py`, the generic steps, the real-process and pty helpers, the placeholders (`{tools}`, `{home}`), the expected-file helper.
- [19](19-layered-config.md): the settings `tool.repository` and `tool.token_hosts` with their validation; `AppContext.settings`.
- [16](16-ui-messages.md): `Ui` (`note`, `warning`, `result`, `ask`, `is_interactive`, `out`, `err`).
- [05](05-github-recordings.md): the `github` fixture and the recordings.
- [04](04-delete-dead-code.md): `get_tlc_jar_path` without its fallback, returning `Path | None`.
- [02](02-errors-and-paths.md), [03](03-test-foundation.md): `AppContext`, `AppPaths`, the errors; the isolation fixture and the fakes.

Changes from the draft (27, 28, 17, 18, 19): 16, 22 to 26, 05, 04, 02 and 03 are named because the commands and the tests use them directly; none changes the order.

## Files

Creates:

- `src/tlaup/cmd/tool/__init__.py`: the Typer group `tool` with `no_args_is_help=True`, each command registered explicitly with `app.command(...)`, never by importing a module for its side effect ([23 C1](../design/23-command-layout.md#c1-command-tree), last row).
- `src/tlaup/cmd/tool/list.py`, `install.py`, `upgrade.py`, `uninstall.py`, `pin.py`, `current.py`, `path.py`, `dir.py`.
- `src/tlaup/cmd/tool/_shared.py`: building the store, the client and the remote from the context, and the download progress bar (Interfaces).
- `tests/features/tool_install.feature`, `tool_uninstall.feature`, `tool_pin.feature`, `tool_upgrade.feature`, `tool_list.feature`, and their expected files under the expected-file folder package 18 set up.
- The store and GitHub steps listed under Tests, in `tests/steps/given.py` and `tests/steps/then.py`.
- `tests/unit/test_tool_commands.py`: the plain pytest tests named under Tests.
- `tests/unit/test_jar_path_from_store.py`: the re-pointed `get_tlc_jar_path` reads the new store. Package 39 deletes it with `tlc/compiler.py`.

Changes:

- `src/tlaup/cli.py`: register the group as `app.add_typer(tool_app, name="tool")`; remove the `tools` and `fetch-cache` registrations and their imports; import `get_app_version` from `tlaup.versioning.app_version`, since `versioning/__init__.py` is emptied.
- `src/tlaup/versioning/__init__.py`: the docstring only. Today it imports `requests` and the old modules whenever any `tlaup.versioning` module is imported (package 22 noted it).
- `src/tlaup/versioning/paths.py`: delete the tool functions (`get_tools_dir`, `get_pinned_path`, `get_pinned_version_dir`, `set_pin`, `clear_pin`, `clear_cache`); keep `get_modules_dir`, `get_run_dir`, `get_tlc_run_dir`, which `java/classpath.py`, `cmd/modules/` and `tlc/run_cache.py` still read until packages 31 and 39.
- `src/tlaup/tlc/compiler.py`: `get_tlc_jar_path` reads the new store (below, "The old `tlaup tlc` meanwhile").
- `src/tlaup/tlc/runner.py`, `src/tlaup/cmd/tlc.py`, `src/tlaup/cmd/modules/add.py`: each message that names `tlaup tools install` names `tlaup tool install`. Nothing else in them changes.
- `tests/unit/spec/conftest.py`, `tests/unit/test_tlc_modules_path.py`, `tests/unit/tlc/test_tlc_version.py`: they patch `tlaup.tlc.compiler.get_pinned_version_dir`, which no longer exists. Replace each such patch with patches of `get_tlc_jar_path` in the modules that imported it (`tlaup.tlc.runner`, `tlaup.cmd.tlc`, `tlaup.cmd.modules.add`, `tlaup.cmd.modules.path`), returning the same jar path, as their neighbours already do. These old tests are not rewritten: they go with the old `tlc` and module commands in packages 39 and 31.
- `tests/unit/version_manager/test_app_version.py`: its import, if it imports through `tlaup.versioning` rather than `tlaup.versioning.app_version`.
- `tests/conftest.py`: delete fixtures that only the deleted test files used (`make_installed_version`, `installed_v180` and the like), if package 03 left any.
- `tests/features/errors.feature`: the two X1 scenarios that need this group, if package 17 did not write them (Tests).
- `README.md` (the section "Toolset Management (`tlaup tools`)") and `docs/contributing/development.md` (two commands): the new names. Only the lines that name the old commands.
- `.github/workflows/test.yml` and `release.yml` run `uv run tlaup tools install` before the tests. If that step is still there when this starts (01 T2 wants the unit job to run with no jar installed; packages 03 and 53 may have removed it), remove it from `test.yml`, and in `release.yml` change it to `uv run tlaup tool install stable` if the release job still needs a jar, or remove it; otherwise CI fails on the removed group.
- `CHANGELOG.md`: the entries under Changelog.

Deletes:

- `src/tlaup/cmd/tools/` with `meta/`; `src/tlaup/cmd/fetch_cache/` (its last reader of old code is `clear_cache`, which goes; the cache it cleared is written by nothing after this package, and `cache clean` is package 45); `src/tlaup/cache/` (read only by `versioning/api.py`).
- `src/tlaup/versioning/api.py`, `downloader.py`, `metadata.py` (with `_extract_tlc_version`, J3), `resolver.py` (with `resolve_latest_version`, V2, and `list_local_versions`), `schema.py`. Keep `app_version.py` (F9, package 49).
- `tests/unit/tools/` entirely: `test_install.py`, `test_pin.py`, `test_uninstall.py`, `test_upgrade.py`, `test_path.py`, `test_dir.py`, `test_list.py`, `test_fetch_cache.py`, `conftest.py`, `__init__.py` ([01 T11](../design/01-testing.md#t11-the-existing-tests): they become the `tool_*` features; `test_fetch_cache.py` tests `fetch-cache clear` and the old cache, both deleted here, and what replaces it is 25's unit tests and 45's `cache.feature`).
- `tests/unit/version_manager/test_resolution.py`, `test_download.py`, `test_remote.py`, `test_metadata.py`, `test_local.py` (T11: replaced by T6 and by package 23's `test_order.py`). `test_app_version.py` and the folder's `__init__.py` stay.
- `tests/fixtures/releases.json`, `tests/fixtures/tags.json` (01 T3: superseded by the recordings).

Shared with other packages: `cli.py` (31, 44, 45, 46, 47 each change one or two registration lines; 48 rewrites the registration block as a whole), `CHANGELOG.md` (every package with an entry), `tests/steps/given.py` and `then.py` (31, 39, 44, 45 add steps; each adds its own functions), `README.md` (31 and 39 change their own lines), the two workflows (package 53 rewrites them; if 53 is merged first, the step is already gone). Each conflict is a few lines.

- `scripts/check_wheel.py`, if [53](53-ci-workflows.md) merged first: its smoke test runs `tlaup tools dir`, which this package removes; change it to `tlaup tool dir` (I4 names the new form; reconciled by stage 4).

## Interfaces

Provides: the commands of [23 C1](../design/23-command-layout.md#c1-command-tree), as Typer declarations, with no one-letter option:

```
tool  list [--installed]
      install [VERSION] [--force]
      upgrade [VERSION]
      uninstall [VERSION]... [--all] [--yes]
      pin VERSION                          (required argument)
      current
      path [VERSION]
      dir
```

Each command module imports only `typer`, `tlaup.errors` and `tlaup.context` at the top and everything else inside the function ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)). Each keeps the Typer function to argument parsing and calls one plain function that takes the store, the client and remote where needed, the `Ui` and the parsed arguments, and returns the exit code or raises a `TlaupError`; the plain pytest tests call that function with a `Ui` on in-memory streams ([12 V12](../design/12-tools-and-downloads.md#v12-install), Tests). `tool dir`, `current`, `path`, `pin`, `uninstall` and `list --installed` load no settings and make no request; `tool path` in particular never loads settings ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration)).

Written by stage 4, for the shared construction (a worker may rename):

```python
# tlaup/cmd/tool/_shared.py
def open_store(ctx: AppContext) -> ToolStore                       # ToolStore(ctx.paths, now=<the real UTC clock>)
def open_remote(ctx: AppContext) -> tuple[GitHubClient, Remote]
    # GitHubClient(settings.tool.repository, token=token_from_env(ctx.env), token_hosts=settings.tool.token_hosts,
    #              user_agent=f"tlaup/{version}")  and  Remote(client, ctx.paths.remote, now=...)
def download_progress(ui: Ui) -> ContextManager[Progress]          # a bar on ui.err; Rich imported here only
```

Package 39 builds the same three for the run commands and should use these, so that the token and the repository are read in one place.

What each command does, beyond the domain function it calls:

- **`tool install [VERSION] [--force]`.** With a version: `parse_version_spec`, `install(...)`, the progress bar on stderr. Notes on stderr: the "already installed" line `v1.7.4@5a47802 is already installed (use --force to download it again)` with nothing after it; for several matches, one line naming each in its printed form; `warning: could not check GitHub for a newer build of v1.7.4: <reason>` when `could_not_check` is set (exit 0); `Pinned <build>` when this call pinned; for a second build of the pinned name, `rolling@1a2b3c4 installed; rolling@bc1b506 is still pinned (tlaup tool pin rolling@1a2b3c4)`. With no version: `read_auto_install(None, env)`; when it is unset and `ui.is_interactive()` is false, `UsageError` (2) asking for `stable` or `rolling`; otherwise `choose_first_build`, then as with that version. It asks whether or not builds are installed.
- **`tool upgrade [VERSION]`.** `upgrade(...)`. Notes: up to date; the new build and where the pin moved; how many older builds of the name remain, naming `tlaup tool uninstall`; a pin left on an older build; for `stable`, which builds remain.
- **`tool uninstall [VERSION]... [--all] [--yes]`.** Neither or both of `VERSION` and `--all`: `UsageError` (2), one `error:` line. With versions: resolve every argument before anything is removed; any that matches no installed build gives `VersionNotFound` (4) naming each such argument, and nothing is removed, with no question asked first. An argument matching several builds of one name: on a terminal without `--yes`, `choose_build(..., allow_all=True)`; with `--yes`, or not on a terminal, all of them. With `--all`: nothing installed is the note `no builds are installed` and exit 0, before any other rule and with no question; else `--yes` removes all; on a terminal, a yes-or-no question (answered no: note `nothing removed`, exit 0); not on a terminal without `--yes`: `UsageError` (2) "`--all` asks for confirmation and there is no terminal; add `--yes`", not `CannotAsk`. Then `uninstall(...)`: each removed build noted; each failure printed and exit 5 if any; when the pinned build was removed, `rolling@bc1b506 was pinned; nothing is pinned now` with the hint `tlaup tool pin <name>` listing what is left; `gone` is `VersionNotFound` (4) for named versions and ignored for `--all` (question "uninstall race", package 27).
- **`tool pin VERSION`.** `pin(...)`, note `Pinned <build>`.
- **`tool current`.** On stdout, two lines: the pinned build as `rolling@bc1b506 (2026.11.15.002146)` (the printed form, with the CalVer in brackets where the build has one and the printed form does not already end in it), and the jar's path. Nothing pinned: `NoPinnedBuild` (3) with builds installed, `NoToolsInstalled` (3) without; a pin naming a missing build: `PinnedBuildMissing` (3). No Java, no network.
- **`tool path [VERSION]`.** One line on stdout, the jar's path. No version: the pinned build's, with `tool current`'s errors. A version: `find`; none, `VersionNotFound`; several, `AmbiguousVersion` (2) with the candidates in their printed form. It never asks ([02 X3](../design/02-cross-cutting.md#x3-version-syntax), the several-builds table).
- **`tool dir`.** One line on stdout, `AppPaths.tools`, whether or not it exists. It no longer lists builds.
- **`tool list [--installed]`.** One table on stdout through `ui.result` ([12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache), "`tool list` in the first wave"): the releases in X4's order, each directly followed by the installed builds of that name; installed builds whose name is no longer upstream last. Columns Version, Build, Published (the asset's update date), Status, Pinned. The release list may come from the lookup cache (`Remote.releases()`, the one-hour default); when it is unavailable the installed builds are listed and one `warning:` line goes to stderr. With `--installed`: the installed builds only, in store order, no request.

  Status, stage 4's reading of V8 (the expected files fix the result and the review reads them, [01 T8](../design/01-testing.md#t8-expected-output-files)): a release row is `available` when no installed build of its name is what upstream publishes (`same_as_published`), `installed` when one is; the row of the newest installed build of a name is `installed, update available` when it is not what upstream publishes, and every other installed row `installed`. V8's sentence ("`installed, update available` when the newest installed build of that name differs from the published one") and its test ("an older installed rolling build shows `update available` on its own row, directly under the `rolling` row") both hold under this reading. V8 does not write what a release row shows under Build, since no commit is read from a tag (V8, Rejected), nor how a cached or stale list is marked; the expected files decide both, and the pull request says what it chose.

Consumes: everything named under Depends on. `AppContext` from the Typer context object (02, 17).

## Tests that must pass

**Feature files** ([01 T5](../design/01-testing.md#t5-feature-files-and-steps)). In-process unless a scenario says "on a terminal" or "closed pipe", which are real processes (T12 rule 10, situations 2 and 4). GitHub is served from recordings in-process only; real-process scenarios start from a store that already holds what they need and never ask GitHub. Every scenario states its starting point through the store steps (`Given the build ... is installed`), so every feature exercises reading (V1).

`tool_install.feature` (V12, V5, V7, X3, C2, J3, F3):

- each row of V12's table, asserting `the installed builds are:`, the pin, the note or error, and the number of requests and downloads;
- `rolling` installed, then `tool install v1.8.0` with the same recorded jar: two builds, and `tool pin v1.8.0` succeeds;
- `tool install v1.7.4` run twice: after the second `I run`, `0 jar download(s) were made` and `1 request(s) were sent to GitHub`; the same with GitHub unreachable the second time exits 0 with one `warning:`;
- `--force` whose download fails: `the installed builds are:` unchanged and the pin still names the build (T6's row, as a user sees it; V5's "after a failed download");
- `--force` on a build whose jar was truncated (`Given the jar of the build ... is truncated`) repairs it;
- the first install pins, the second does not;
- no version with `TLAUP_AUTO_INSTALL=stable` installs stable without asking; no version, no terminal, no variable exits 2;
- `--force v1.7.4@<commit>` with that build installed and published repairs it, and with another build published exits 4 and changes nothing;
- a release with no digest whose asset has a new upload time and the same bytes makes one download, leaves one build, and a second install makes none;
- a bare CalVer installed under two names exits 0 and names both; `rolling@<prefix>` matching two installed builds exits 0, names both and sends no request, and with `--force` exits 2;
- `tool install latest` exits 2; `tool install https://example.org/tla2tools.jar` exits 2 with no request (X3, C2, V6);
- with `java is not installed`, `tool install rolling` succeeds and `tool current` shows commit and CalVer (J3);
- with `tool.repository` set to another `https` address, the requests go to that host (F3), unless package 19 already has the scenario;
- **waits on question "debug filter":** `tlaup --debug tool install rolling` with `GH_TOKEN` set and GitHub failing: the token's value appears in neither stream (V7). Write the scenario marked `pending` with the question's name if the filter is not on `main`, and leave the marker to the package that answers it.

`tool_uninstall.feature` (V3, C1, C2):

- three builds with the middle one pinned, `--all --yes` leaves none and `no build is pinned`;
- two named builds with the pinned one first: both removed;
- two builds named, the pinned one made impossible to remove (`the folder "<its folder>" is read-only`; the tools folder stays writable): exit 5, the other build gone, the stuck one intact and still pinned;
- on a terminal: two builds of `rolling`, `tool uninstall rolling` answered `-1, 7, 2`: `stderr contains "<question>" 3 times`, the second build removed, the first left; the same answered `all`;
- the same store with `--yes` removes both without asking; with no terminal and no `--yes` removes both;
- `rolling@<commit>` removes one, in every mode;
- removing the pinned build leaves `no build is pinned`, and the next `tlaup tool current` exits 3 (V3's test names `tlaup tlc`; the old `tlc` of this period exits 1 for no pinned jar, so the scenario uses `tool current`, and package 39 adds the `tlc` form to `tlc_errors.feature`);
- on a terminal: `--all` answered `n` removes nothing and exits 0;
- `--all` with no terminal and no `--yes` exits 2 and removes nothing; `--all` with nothing installed and no terminal exits 0 with the note, with and without `--yes`;
- `v1.8.0 nosuch` with `v1.8.0` installed exits 4, names `nosuch`, and `v1.8.0` is still installed;
- on a terminal with stderr redirected to a file: two builds of `rolling`, `tool uninstall rolling` removes both without asking (the question could not be seen; this is also V9's case "stdin a terminal and stderr not");
- `tool uninstall` with no argument, and with a version and `--all`, exits 2 with one `error:` line (C1);
- the C2 outline: `v1.7.4`, `1.7.4`, `stable`, `v1.7.4@5a47802` against the same store each remove the same build.

`tool_pin.feature` (V4, X3, C2, C1's `tool current` and `tool path`):

- by tag without `v` (`tool pin 1.7.4`, X3); `tag@commit`;
- ambiguous without a terminal exits 2 and lists the candidates;
- on a terminal: ambiguous, the typed answer is pinned; with stderr redirected to a file, exits 2;
- the C2 outline: `v1.7.4`, `1.7.4`, `stable`, `v1.7.4@5a47802` give the same pinned build; the same outline for `tool path`;
- two builds of `rolling`, `tool path rolling` exits 2 and lists both (X3);
- `tool current` with a build pinned prints the printed form and the jar path; with nothing pinned exits 3; with the pinned build's folder removed exits 3.

`tool_upgrade.feature` (V4, C2):

- the installed build equals the published digest: nothing downloaded and `1 request(s) were sent to GitHub` although `the release list is cached from "releases", 1 minutes old`;
- a different digest installs the new build, moves the pin, removes the old;
- two installed builds of `rolling`: compared with the newer, and afterwards the older is still installed; the same with the older one pinned leaves the pin on it;
- upgrading a name that is not installed installs it;
- no argument with nothing pinned exits 3, with and without builds installed;
- a bare CalVer and `rolling@<commit>` exit 2 with no request; `tool upgrade v1.7.4@5a47802` exits 2 (C2);
- `stable` with `v1.7.4` installed and pinned and `v1.8.0` published as stable installs `v1.8.0`, moves the pin, and leaves `v1.7.4` installed.

`tool_list.feature` (V8, X4, C1):

- online, cached (`the release list is cached from "releases", 1 minutes old`, no request), stale (cached 3 hours old and GitHub unreachable) and unavailable (no cache, GitHub unreachable: the installed builds and one `warning:` on stderr), each against an expected file;
- an older installed rolling build shows `update available` on its own row, directly under the `rolling` row;
- the row order of X4 against an expected file;
- `--installed` lists the installed builds and makes no request;
- `tlaup tool` with nothing after it exits 2, the help on stdout, nothing on stderr (X1 rule 7, C1);
- `tool dir` prints one line, the tools folder, and nothing else.

`errors.feature`, unless package 17 wrote them (then only their command names change): `tlaup tool list` with two builds installed, with stdout on a closed pipe, exits 141 with no `Traceback`; `tlaup tool pin nosuch` with stdout and stderr on a closed pipe exits 141 (real processes, [02 X1](../design/02-cross-cutting.md#x1-exit-codes)). Likewise the plain pytest of X1, `tlaup tool list` with stdout on `/dev/full` (Linux only) exits 5 with `cannot write output` on stderr.

**Steps this package adds**, all from T5's fixed vocabulary, unless package 18 already has them (then use 18's):

- Given, the store: `the build "<spec>" is installed` (optionally `and pinned`), `no build is installed`, `the release list is cached from "<recording>", <n> minutes old` (written through package 25's `write_cache`, never by hand), `the jar of the build "<spec>" is truncated` (cut to half its size).
- Given, the rest: `GitHub answers from "<recording>"`, `GitHub answers <status> to "<path>"`, `GitHub is unreachable` (in-process only); and `the folder "<path>" is read-only` and `java is not installed` if 18 does not have them.
- Then, the store: `the pinned build is "<spec>"`, `no build is pinned`, `the installed builds are:` (a table with one column, the printed form of each build, in store order: written by stage 4, as T5 gives no columns).
- Then, GitHub: `<n> request(s) were sent to GitHub`, `<n> jar download(s) were made`, `no request carried a token to "<host>"` (in-process only; they count the last `I run`).

`the build "<spec>" is installed` installs through `ToolStore.add` exactly the jar the `github` fixture publishes under that name, with the `Source` and `prerelease` its recorded release gives, so that `same_as_published` holds for it; with `@<commit>` or `@<calver>` in the spec it installs another build of that name with that commit or build time (a jar from the same helper with that manifest), which upstream does not publish. Both use package 22's small-jar helper and the recorded manifests. A new step needs a reason in the pull request (T5); none is expected beyond this list.

**Plain pytest**, `tests/unit/test_tool_commands.py`:

- `tool install` with no version, the question answered on in-memory streams (`interactive=True`, the answer in stdin), with one build installed and `responses` serving GitHub: the chosen build is installed ([12 V12](../design/12-tools-and-downloads.md#v12-install), Tests). It calls the command's plain function, not the Typer app, since in-process `CliRunner` has no terminal.
- V7's query strings: `responses` serves a download that redirects to an address with `?sig=secret-value`. When the download succeeds, no `build.json` under the store contains `secret-value`. **Waits on question "debug filter":** when the body then fails, under `--debug`, `secret-value` is in neither captured stream.

`tests/unit/test_jar_path_from_store.py`: with a build installed and pinned in the new store, `get_tlc_jar_path()` is its jar; with nothing pinned, `None`; with the pin naming a missing build, `PinnedBuildMissing`.

**Old tests deleted** (01 T11, and as handed over by packages 23 to 26): listed under Files. **Old tests changed, not rewritten:** the three patch targets under Files.

No stateful test applies: the store machine is package 27's.

## Changelog

Every entry below is written in this package, word for word from its section, because a user first sees each change through the `tool` commands. Packages 22 to 28 write none of them.

Breaking:

- V1: "Installed tools are stored in a new layout with a `build.json` beside each jar. They live in the cache's `tool` folder (was `tools`). Builds installed by earlier versions are not recognised: run `tlaup tool install` again. The old `tools` folder can be deleted."
- V3: "Uninstalling the pinned build clears the pin; it no longer switches to another installed build. Pin one with `tlaup tool pin`." "With several installed builds of one name, `tlaup tool uninstall NAME` without a terminal, or with `--yes`, removes all of them; name one build as `NAME@COMMIT`."
- V12: "`tlaup tool install` with no version asks which build to install (stable or rolling), or takes the answer from `TLAUP_AUTO_INSTALL`, and fails without either; it used to install the latest stable release."
- X3: "With several builds of one tag installed, `tlaup tool path TAG` now fails and lists them (it printed the first)."
- C1: "`tlaup tools dir` is now `tlaup tool dir` and prints only the folder; use `tlaup tool list --installed` for the builds." "`tlaup tools install -f` and `tlaup tools uninstall -y` are now `tlaup tool install --force` and `tlaup tool uninstall --yes`." "`tlaup tools` and `tlaup modules` are now `tlaup tool` and `tlaup module`; every subcommand keeps its name." (This line covers `module` too, which package 31 switches; it is written once, here, and 31 writes no second line for the rename.)

Removed:

- V8: "`tlaup fetch-cache clear`; use `tlaup cache clean`."
- C1: "`tlaup tools meta sync` is removed; metadata is read from the jar at install."

Added:

- V7: "`GITHUB_TOKEN` or `GH_TOKEN` is used for GitHub API requests, which raises the rate limit. The token is sent only to `api.github.com`, and to hosts you list in `tool.token_hosts`; it is never printed. Credentials in `.netrc` are not used."
- X3: "Versions can be typed without the `v`, as `stable` or `rolling`, and as `tag@commit` to name one build."
- C1, written by stage 4 from its rows (C1 gives no text for them): "`tlaup tool current` shows the pinned build and its jar without starting Java." "`tlaup tool list --installed` lists the installed builds only, with no network."

Changed:

- V4: "`upgrade` compares the installed jar with the published one by SHA-256 where GitHub provides it."
- V5: "The commit shown for a build is read from the jar itself."
- V7: "Unencrypted addresses, and redirects to them, are refused."
- V8: "`tool list` keeps installed builds next to their upstream release and marks one that has a newer build available."
- V12: "Installing a newer build of a name that is already installed keeps the older build and leaves the pin where it is; `tlaup tool upgrade` replaces the older build and moves the pin."
- X4: "`rolling` is listed first in `tlaup tool list`, then versions by number."

Fixed:

- V3: "`tlaup tool uninstall --all` stopped after removing the pinned version." "A failed uninstall now exits 5 and leaves the pin alone."
- V4: "`tlaup tool upgrade` could report 'already up to date' for up to an hour after upstream published a new build."
- V5: "A download that was cut short, or a proxy's error page, could be recorded as an installed build. Downloads are now checked for length, for being a TLA+ tools jar, and against GitHub's SHA-256 where it provides one, before anything is installed." "`tool install --force` deleted the installed build before the new download had succeeded."
- V7: "A GitHub rate limit was reported as a generic failure." "A non-JSON answer from GitHub (for example from a proxy) caused a traceback."
- V8: "Only the first 30 tags were read from GitHub, so `rolling` would have disappeared at the next upstream release." "The 'Tag/SHA' column of `tool list` is now 'Build'."
- V11: "Two `tlaup tool install` commands running at once could leave a damaged install."
- V12: "`tlaup tool install` printed 'Successfully installed' after 'already installed'." "`tlaup tool install` could treat a moving tag such as `rolling` as up to date for an hour after upstream published a new build; it now asks GitHub every time and compares the installed jar with the published one."
- X4: "`tlaup tool install` could offer a prerelease as the stable version when no stable release was in the first page of results."
- J3: "Installing tools without Java present recorded an empty version."
- F6: "A warning from `tool list` went to stdout." (unless package 16 has written it; then not twice)

Not here: V6's Removed entry (package 04 wrote it), V9's Added entry (39), X1's Breaking entry (17), F7's help-text entry and F11's (50), C1's rows of the other groups (31, 39, 44, 45, 46, 47).

## Context for the worker

Decisions:

- D47: `tool`, singular, also in the config section (`tool.repository`, `tool.token_hosts`) and the cache folder (`<cache>/tool/`).
- D14: no alias, shim or migration. `tlaup tools ...` is an unknown command after this package (exit 2; the scenarios that say so are package 48's); builds in the old `<cache>/tools/` folder are not read; the changelog says to install again.
- D38 and the design agent's decision on short options: no `ls` or `rm`, no `-f` or `-y`.
- D23, D43: naming a version is the confirmation; the which-build question is asked only on a terminal (stdin and stderr both, [14 F6](../design/14-config-and-cli.md#f6-messages)); `--yes` answers it with "all"; `--all` keeps its confirmation.
- D29 and [02 X1](../design/02-cross-cutting.md#x1-exit-codes): 2 usage, 3 not set up, 4 not found, 5 failed; tlaup never returns 1. Errors are raised, and package 17's handler prints and maps them.
- D30 and [02 X2](../design/02-cross-cutting.md#x2-stdout-and-stderr): results on stdout (the table, the path, the folder, `tool current`'s two lines), everything else on stderr (notes, warnings, questions, the progress bar).
- D41: the token goes to `api.github.com` and to the hosts in `tool.token_hosts`, nowhere else; `tool.repository` can come from the environment and does not carry the token with it.
- D31 and the design agent's two extra forms: `stable`, `rolling`, `tag@commit`, `tag@CalVer`, a bare CalVer, `name@sha256:...`; `latest` refused.

Help text: write each command's help in the words of [14 F7](../design/14-config-and-cli.md#f7-help-text) where it has them (what `upgrade` means; `install` with no version and the first build pinned; the scope of `--yes`; a help string for `tool path VERSION`; "TLA+ tools", not "TLC", in every help string of the group). Package 50 owns F7 as a whole, its changelog entry and the reference.

**The old `tlaup tlc` meanwhile.** `tlaup tlc` stays on the old runner until package 39, and the old module commands on `cmd/modules/` until package 31. Both find the tool jar through `get_tlc_jar_path` in `tlc/compiler.py` (five call sites: `cmd/tlc.py` twice, `tlc/runner.py` twice, `cmd/modules/add.py`, `cmd/modules/path.py`; package 04 made it return `Path | None`). The smallest edit that keeps them working is the function's body:

```python
def get_tlc_jar_path() -> Path | None:
    build = ToolStore(AppPaths.from_env(os.environ), now=lambda: datetime.now(UTC)).pinned()
    return build.jar if build is not None else None     # PinnedBuildMissing passes up to the handler (3)
```

So the old `tlc` runs the jar pinned in the new store; with nothing pinned it prints its old message, now naming `tlaup tool install`, and exits 1 as before (mixed codes are allowed between packages, since nothing is released, D6); a pin that names a missing build is `PinnedBuildMissing` through the handler, code 3. `AppPaths.from_env(os.environ)` is used because the old code has no context to read; it is the same folder the context gives. No other line of the old runner or command changes. The old `tlc --version` keeps printing the jar path, now the new store's, and the first line of `java -cp <jar> tlc2.TLC -version`; it is removed in 39. The old `tlc` has no first-run question and still has none: with nothing installed it prints the message and exits 1; the question arrives in 39. The old module commands build their classpath with the jar from the new store.

Points a worker could miss:

- **The order of the uninstall checks** (V3): "nothing installed" first for `--all`; every named argument resolved before anything is removed and before any question; then the questions; then the removal. A question about "which build" is never asked when another argument matches nothing.
- **Not on a terminal is not an error for `uninstall NAME`**: it removes every build of the name. It is an error for `pin` (2), for `uninstall --all` without `--yes` (2, a usage error, not `CannotAsk`), and for `tool install` with no version and no variable (2).
- **`tool path` never asks**, on a terminal either: its output is for scripts.
- **The `--all` question** has no wording, choices or default in V3. Ask it through `Ui.ask` with the choices `y` and `n` and the default `n`, the usual for a question that deletes, and say so in the pull request (stage 4's reading; listed in the index).
- **`tool list` warns once.** The old code printed a warning glyph to stdout; the new one prints one `warning:` line to stderr through `ui.warning`, and only when the list is unavailable.
- **Candidates and builds are always printed by `format_build` with every installed build as `others`**, so the form typed back finds exactly that build (X3).
- **Imports.** `versioning/__init__.py` emptied means `import tlaup.versioning.store` no longer drags in `requests`; keep it so. Package 49's test runs `tlaup tool dir` in-process and asserts that `requests`, `yaml`, `truststore`, `rich.progress`, the settings schema and `tlaup.versioning.github` were not imported.
- **Old tests that patch removed names fail at the patch**, not at the assertion. Run the whole suite after each deletion; `uv run mypy` and `ruff` name every dangling import in `src/`.
- **The integration tests** under `tests/integration/` place jars in the old layout and are outside the default run and CI; package 39 deletes them and 52 writes new ones. Leave them.

State of `main` when this starts: packages 01 to 28 merged (the store track complete; 16 to 19 of the groundwork track: `Ui`, the handler, the feature harness, the layered config). The old `tools` group (`cmd/tools/`), `fetch-cache`, the old `versioning/` modules, `cache/github.py`, the old `tlc` and `modules` commands are all still there. Package 04 removed URL installs and the legacy layouts.

## Done when

- The feature scenarios and plain tests above pass, except the two marked as waiting, which are written and marked `pending` with the question's name if the debug filter is not on `main`; `uv run poe lint` and `uv run poe test` pass; CI is green.
- `tlaup tools`, `tlaup fetch-cache` and `tlaup tools meta sync` no longer exist; nothing under `src/` imports `tlaup.versioning.api`, `downloader`, `metadata`, `resolver`, `schema` or `tlaup.cache`.
- The old `tlaup tlc Spec` runs the build pinned by `tlaup tool pin` (checked once by hand with a real jar, and said so in the pull request; the old runner has no feature file of its own).
- The changelog entries are written; `README.md` and `docs/contributing/development.md` name the new commands; the workflows no longer call `tlaup tools`.
- The pull request says what the expected files of `tool list` chose for a release row's Build column and for the cached and stale lists, and how the `--all` question reads.

## Out of scope

- The domain functions: packages 22 to 28.
- The command tree test, the root options, `tlaup` alone, explicit registration of the other groups, and the "exit 2" scenarios of every removed name (`tools`, `fetch-cache`, `tools meta`, `install -f`, `uninstall -y`): package 48.
- `cache dir`, `cache list`, `cache clean` (which removes `<cache>/remote/`): package 45. `doctor`, which reports leftover folders in the store and checks the pinned jar's SHA-256: package 46. Completion of versions: package 47.
- The `--auto-install` option of the run commands, `first_run.feature`, wrapping `ensure_tools` for a run, deleting `tlc/compiler.py`, `get_tlc_version`, `tlc --version`: package 39. The `module` group and the deletion of `versioning/paths.py`'s module functions: package 31.
- The debug filter itself (where it lives, its signature): question "debug filter"; packages 17 and 24.
- Help text as a whole, the CLI reference, F11's messages ("did you mean" for a version): packages 50 and 51.
- The milestone 4 `tool list` display, `--yes` for every prompt, `pin --local`: later milestones.

## Risks

- From V3: a script that ran `tool uninstall rolling` expecting one build to go now removes every rolling build; the changelog says so, and an older rolling build cannot be downloaded again (research 5).
- From V12: older builds of a moving tag pile up; `tool list --installed` shows them and `tool upgrade` or `tool uninstall` removes them.
- From C1: this is the first of the release's two large user-visible changes, landing in 0.9.0 with the changelog as the upgrade guide.
- From the cut: the real-process scenarios on a pty depend on the platform's `pty` module and are skipped on Windows (T5); the prompt paths are not run there.
- From the cut, size. Eight commands, five feature files with about seventy scenarios, the steps, the deletions and some forty changelog lines are more than one review sitting. Proposed split, if the index agrees, into two pull requests:
  - **29a**, the commands that write: the `tool` group with `install`, `upgrade`, `uninstall`, `pin`, `current` and `dir`; the deletion of the whole old `tools` group and its tests; `get_tlc_jar_path` re-pointed; the store and GitHub steps; `tool_install`, `tool_uninstall`, `tool_upgrade` and `tool_pin` (without its `tool path` scenarios); the changelog entries of V1, V3, V4, V5, V7, V11, V12, J3, the C1 rows of the group and X3's Added. After 29a a user can install, upgrade, remove and pin builds in the new store, see the pin with `tool current`, and run the old `tlaup tlc` on it; `tool list` and `tool path` are simply absent for a while, which is a missing command, not a half-built one, and nothing is released in between (D6).
  - **29b**, the commands that read and the clean-up: `tool list` with `--installed`, `tool path`, `tool_list.feature` and the `tool path` scenarios; the deletion of `fetch-cache`, `cache/`, the old `versioning/` modules (dead code after 29a, still tested by their old tests until they go together here), the old `version_manager` tests and fixtures; the entries of V8, X4, X3's Breaking and F6.
  - The other order (readers first) does not keep `main` usable: the old `tools install` would write the old layout while the new `tool list` and the old `tlc` read the new one, or, with the old group deleted, nothing could install a build at all.

## Pull requests (decided by stage 4)

This package is delivered as two pull requests, as proposed under Risks; the index lists them as 29a and 29b. Readers first does not work (two stores would be live, or nothing could install), so the split is by command.

- **29a**: `tool install`, `upgrade`, `uninstall`, `pin`, `current` and `dir`; deletion of the whole old `tools` group; the old jar lookup pointed at the new store; the store and GitHub steps; four feature files; the changelog entries of V1, V3, V4, V5, V7, V11, V12, J3, the C1 rows of these commands and X3's Added entry. Between the two pull requests `tlaup tool list` and `tlaup tool path` are absent, not half-built. Depends on everything this file lists.
- **29b**: `tool list` (with `--installed`) and `tool path`, `tool_list.feature`, deletion of `cmd/fetch_cache/`, `src/tlaup/cache/`, the dead old versioning modules and their tests and fixtures, and the entries of V8, X4, X3's Breaking entry and F6's `tool list` entry. Depends on 29a.

A package that names 29 as a dependency waits for 29b.
