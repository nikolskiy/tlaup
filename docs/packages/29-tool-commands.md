# 29. The `tool` commands: switch to the new store

Size: L as a whole, delivered as two pull requests (29a, L; 29b, M; see the end of this file). Suggested model: most capable. Status: built, not yet proven on CI. The debug filter is [24](24-github-client.md)'s `redact`, in place before this package (question Q6); the uninstall race is answered by the design (question Q8, [27](27-install-steps.md)).

This is the switch package of the store track.

## Goal

`tlaup tool` (D47) is the command group for TLA+ tools builds: `list`, `install`, `upgrade`, `uninstall`, `pin`, `current`, `path` and `dir`, each a thin module under `src/tlaup/cmd/tool/` over the domain code of packages 22 to 28, with version specs everywhere, questions only on a terminal, and the exit codes of [02 X1](../design/02-cross-cutting.md#x1-exit-codes). The old `tools` and `fetch-cache` groups and the old store code are gone (their old tests went in 03b, decision D62); five feature files state the behaviour; the changelog says what a user sees. The old `tlaup tlc` and the old module commands still type-check: their jar lookup reads the new store's pin.

## Covers

- Roadmap items, milestone 1 ([link](../roadmap.md#milestone-1-a-runner-you-can-trust)):
  - "Fix `tools uninstall --all`, which stops after removing the pinned version ..." and "A failed uninstall exits non-zero and does not move the pin; the build-selection prompt rejects negative indexes." Closed here: the command, its prompt and its feature file; the domain part was 27.
  - "Concurrent installs: write the pin and metadata atomically and take a lock ...", in part: its changelog entry. The work was 23 and 27.
  - "Remove installs from a URL (decision D13). ...", in part: `tool install https://...` exits 2 through the version grammar (22); the removal was 04.
  - "Download to a temporary file, check it is a valid jar, then rename. ...", in part: what a user sees (`tool_install.feature`, the changelog). The work was 23, 26 and 27.
  - "After download, compare the commit the jar reports about itself with the expected commit ...", in part: the user-visible rows and the changelog.
  - "Read all pages of tags and releases; choose 'latest stable' by version, not by API order; never install a prerelease while saying 'stable'. ...", in part: `tool list` and the changelog. The listing was 25.
  - "GitHub token support (`GITHUB_TOKEN`, `GH_TOKEN`), ... The token is never printed, including by `--show-command` and `--debug`, and is sent only to the GitHub API host. ...", in part: reading the token and the settings, the feature scenario that it is never printed, the changelog. The client and the debug filter were 24.
  - "Refuse unencrypted addresses and any redirect to one.", in part: the changelog. The work was 24.
  - "Do not crash on a non-JSON or non-list API response. Key the remote-version cache on the request ... `tools upgrade`, and an install of a moving tag, check the remote again ...", in part: `tool upgrade`, `tool install` and the changelog.
  - "First-run prompt (decision D4): ...", in part: `tool install` with no version asks the same question. The run commands are 39 and 41 to 43.
  - "Remove the legacy fallback jar path ... A pin that points at a missing build is a clear error with a hint, not a silent fallback.", in part: `tool current` and `tool path` show `PinnedBuildMissing`; the old `get_tlc_jar_path` reads the new store's pin once the old pin functions go. 04 removed the fallback; 39 deletes the function.
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
  - [12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache): "`tool list` in the first wave" (releases without a jar hidden, `installed, not upstream`; decision D64), `tool_list.feature`, the changelog.
  - [02 X3](../design/02-cross-cutting.md#x3-version-syntax): "When a spec matches several installed builds" and its scenarios; "What is printed" as the commands use it; the tag in the refusal of `latest`, from the cached list or the installed builds with no request (finding B16); the changelog.
  - [02 X4](../design/02-cross-cutting.md#x4-rolling): the order of `tool list`, the changelog.
  - [12 V1](../design/12-tools-and-downloads.md#v1-version-store), [V5](../design/12-tools-and-downloads.md#v5-download-and-verify), [V7](../design/12-tools-and-downloads.md#v7-github-client), [V11](../design/12-tools-and-downloads.md#v11-concurrent-installs): the feature scenarios and plain pytest tests the sections give to the commands, and every changelog entry of these sections. V2: the deletion of `resolve_latest_version`. V10: the rest of package 04's work on `get_tlc_jar_path`, as far as this switch reaches.
  - [13 J3](../design/13-modules-and-java.md#j3-one-java-start): the `tool_install.feature` scenario with no Java, the deletion of `_extract_tlc_version`, the entry "Installing tools without Java present recorded an empty version."
  - [14 F6](../design/14-config-and-cli.md#f6-messages): the entry "A warning from `tool list` went to stdout.", which a user first sees here.
  - [14 F3](../design/14-config-and-cli.md#f3-settings-that-go-and-settings-that-stay): the feature "`tool.repository` set to another `https` address is the host the requests go to", and the Added entry for `tool.token_hosts` (findings B6, D4).
  - [14 F1](../design/14-config-and-cli.md#f1-layered-configuration): the scenario "`tlaup tool path` on a fresh home leaves `the file "{config}/config.yaml" does not exist`" (findings B5, D3).
  - [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks): the unreadable pin file, one of its four cases, as a scenario (finding B4).
  - [02 X1](../design/02-cross-cutting.md#x1-exit-codes) and [20 G2](../design/20-groundwork.md#g2-domain-errors): the `errors.feature` scenarios of the classes these commands reach, `NetworkError` and `RemoteDataError` included (finding B17).
  - The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md): rows T1, T5, T11, T18, T19, T20, T27, T28, T29, T31, T33, T34 and T39, whose owner this package is, and its halves of T21 (the `tool list` half; 25 the cache half), T22 (the scenarios; 25 the unit tests) and T8 (the `VersionNotFound` scenarios of these commands; [50](50-help-and-messages.md) owns the row). Each row's test is named in the table under Tests (findings F1 and G1 of the [second review](review-2026-11-24.md)).

## Depends on

- [27](27-install-steps.md): `install`, `upgrade`, `uninstall` (with its groups and `missing`), `pin`, `choose_build`, their reports, `same_as_published`.
- [28](28-first-run.md): `choose_first_build`, `read_auto_install`.
- [23](23-tool-store.md), [25](25-remote-listing.md), [26](26-download-and-verify.md), [24](24-github-client.md), [22](22-version-spec-and-jarinfo.md): `ToolStore`, `Build`, `format_build`, `sort_key`; `Remote`, `Remote.cached`, `Freshness`, `write_cache`, `stable_of`; `fetch_build`; `GitHubClient`, `token_from_env`, `Progress`, and `redact` already called by the handler; `parse_version_spec`, `latest_refused`.
- [17](17-error-handler.md): the root group that maps `TlaupError` to its code and Typer's usage errors to 2, `--debug`, the 141 rules, and the `PLC0415` per-file ignore for `src/tlaup/cmd/**`.
- [18](18-feature-harness.md): `tests/test_features.py`, the generic steps (`the folder ... is read-only`, `java is not installed` and `a file ... containing:` among them), the real-process and pty helpers, the placeholders (`{tools}`, `{home}`, `{config}`), the expected-file helper.
- [19](19-layered-config.md): the settings `tool.repository` and `tool.token_hosts` with their validation; `AppContext.settings`.
- [16](16-ui-messages.md): `Ui` (`note`, `warning`, `result`, `ask`, `is_interactive`, `out`, `err`).
- [05](05-github-recordings.md): the `github` fixture and the recordings.
- [04](04-delete-dead-code.md): `get_tlc_jar_path` without its fallback, returning `Path | None`.
- [02](02-errors-and-paths.md), [03](03-test-foundation.md): `AppContext`, `AppPaths`, the errors; the isolation fixture and the fakes.

Changes from the draft (27, 28, 17, 18, 19): 16, 22 to 26, 05, 04, 02 and 03 are named because the commands and the tests use them directly; none changes the order.

## Files

Each entry names its pull request (finding B3). The old tests these modules had went in 03b, so no entry here deletes, keeps or patches an old test (decision D62).

Creates:

- 29a: `src/tlaup/cmd/tool/__init__.py`: the Typer group `tool` with `no_args_is_help=True`, each command registered explicitly with `app.command(...)`, never by importing a module for its side effect ([23 C1](../design/23-command-layout.md#c1-command-tree), last row). 29a registers its six commands; 29b adds `list` and `path`.
- 29a: `src/tlaup/cmd/tool/install.py`, `upgrade.py`, `uninstall.py`, `pin.py`, `current.py`, `dir.py`. 29b: `list.py`, `path.py`.
- 29a: `src/tlaup/cmd/tool/_shared.py`: building the store, the client and the remote from the context, the download progress bar, and the tag for the refusal of `latest` (Interfaces).
- 29a: `tests/features/tool_install.feature`, `tool_uninstall.feature`, `tool_upgrade.feature`, `tool_pin.feature` (without its `tool path` scenarios), and their expected files under the expected-file folder package 18 set up. 29b: `tool_list.feature`, and the `tool path` scenarios in `tool_pin.feature`.
- 29a: the store and GitHub steps listed under Tests, in `tests/steps/given.py` and `tests/steps/then.py`.
- 29a: `tests/recordings/github/not-json/`, one synthetic recording whose answer to the release list is an HTML page (package 05's layout; its README line says it is synthetic), for the `RemoteDataError` scenario.
- 29a: `tests/unit/test_tool_commands.py`: the plain pytest tests named under Tests (29b adds the `/dev/full` case of `tool list`).

Changes:

- 29a: `src/tlaup/cli.py`: register the group as `app.add_typer(tool_app, name="tool")`; remove the `tools` registration and its import.
- 29b: `src/tlaup/cli.py`: remove the `fetch-cache` registration and its import; import `get_app_version` from `tlaup.versioning.app_version`, since `versioning/__init__.py` is emptied.
- 29b: `src/tlaup/versioning/__init__.py`: the docstring only. Until now it imports `requests` and the old modules whenever any `tlaup.versioning` module is imported (package 22 noted it).
- 29b: `src/tlaup/versioning/paths.py`: delete the tool functions (`get_tools_dir`, `get_pinned_path`, `get_pinned_version_dir`, `set_pin`, `clear_pin`, `clear_cache`, and what else in it only the deleted modules call); keep `get_modules_dir`, `get_run_dir`, `get_tlc_run_dir`, which `java/classpath.py`, `cmd/modules/` and `tlc/run_cache.py` still read until packages 31 and 39.
- 29b: `src/tlaup/tlc/compiler.py`: `get_tlc_jar_path` imports `get_pinned_version_dir`, which goes, so it gets the body under "The old `tlaup tlc` meanwhile".
- 29a: `tests/features/errors.feature`: the scenarios of this group (Tests), and in package 18's two scenarios `tools dir` and `tools pin` become `tool dir` and `tool pin` (finding B14); the `tool pin` scenario's `stderr contains "version"` (the old command's lower-case argument, written so by 18a) becomes the new command's argument name, `VERSION` if it is named so.
- 29a: `tests/unit/test_handler.py` (package 17's): its relative-`TLAUP_HOME` case runs `tools dir`; it becomes `tool dir`.
- 29a: `README.md`, the section "Toolset Management (`tlaup tools`)": the new names of the commands 29a builds; 29b the rest (`list`, `path`). Only the lines that name the old commands.
- 29a: `docs/contributing/development.md`: the `tlaup tools list` example becomes `tlaup tool list`, if 03 has not changed the line (29b's command; the line is a doc, so it may name it ahead).
- 29a: `scripts/check_wheel.py`, if [53](53-ci-workflows.md) merged first: its smoke test runs `tlaup tools dir`, which this package removes; change it to `tlaup tool dir` (I4 names the new form).
- 29b: `tests/unit/test_context.py` (02's new test): its assertion that `tlaup.versioning.paths.get_tools_dir()` follows `TLAUP_HOME` goes with that function (02 hands it here).
- 29b: `tests/unit/versioning/test_redact.py` (24's test): its import test gains the `requests` half. Once `versioning/__init__.py` is emptied, `import tlaup.versioning.redact` in a fresh interpreter loads neither `tlaup.versioning.github` nor `requests` ([24](24-github-client.md) asserts only the first until then; finding G3 of the [second review](review-2026-11-24.md)).
- 29a and 29b: `CHANGELOG.md`, the entries under Changelog, each in the pull request named there.

Not here: the `tlaup tools install` steps of the workflows. 03b removes the one in `test.yml` with the old tests (D62); the one in `release.yml` is [55](55-release-tooling.md)'s alone. Between 29a and 55 the release workflow would fail at that step, which matters only on a tag push, and nothing is released in between (D6).

Deletes:

- 29a: `src/tlaup/cmd/tools/` with `meta/`.
- 29b: `src/tlaup/cmd/fetch_cache/` (its last reader of old code is `clear_cache`, which goes; the cache it cleared is written by nothing after 29a, and `cache clean` is package 45); `src/tlaup/cache/` (read only by `versioning/api.py`).
- 29b: `src/tlaup/versioning/api.py`, `downloader.py`, `metadata.py` (with `_extract_tlc_version`, J3), `resolver.py` (with `resolve_latest_version`, V2, and `list_local_versions`), `schema.py`. Keep `app_version.py` (F9, package 49). After 29a nothing but these modules themselves and `fetch-cache` imports them; they go together in 29b, untested meanwhile (D62).

Shared with other packages: `cli.py` (31, 44, 45, 46, 47 each change one or two registration lines; 48 rewrites the registration block as a whole), `CHANGELOG.md` (every package with an entry), `tests/steps/given.py` and `then.py` (31, 39, 44, 45 add steps; each adds its own functions), `tests/features/errors.feature` (18 and every command package), `README.md` (31 and 39 change their own lines; 56 the rest), `scripts/check_wheel.py` (53). Each conflict is a few lines.

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

Each command module imports only `typer`, `tlaup.errors` and `tlaup.context` at the top and everything else inside the function ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)); ruff's `PLC0415` is already ignored for `src/tlaup/cmd/**` ([17](17-error-handler.md)), so no command needs a `noqa`. Each keeps the Typer function to argument parsing and calls one plain function that takes the store, the client and remote where needed, the `Ui` and the parsed arguments, and returns the exit code or raises a `TlaupError`; the plain pytest tests call that function with a `Ui` on in-memory streams ([12 V12](../design/12-tools-and-downloads.md#v12-install), Tests). `tool dir`, `current`, `path`, `pin`, `uninstall` and `list --installed` load no settings and make no request; `tool path` in particular never loads settings ([14 F1](../design/14-config-and-cli.md#f1-layered-configuration)).

Written by stage 4, for the shared construction (a worker may rename):

```python
# tlaup/cmd/tool/_shared.py
def open_store(ctx: AppContext) -> ToolStore                       # ToolStore(ctx.paths, now=<the real UTC clock>)
def open_remote(ctx: AppContext) -> tuple[GitHubClient, Remote]
    # GitHubClient(settings.tool.repository, token=token_from_env(ctx.env), token_hosts=settings.tool.token_hosts,
    #              user_agent=f"tlaup/{version}")  and  Remote(client, ctx.paths.remote, now=...)
def download_progress(ui: Ui) -> ContextManager[Progress]          # a bar on ui.err; Rich imported here only
def latest_tag(ctx: AppContext, store: ToolStore) -> str | None
    # the tag for the refusal of `latest` (02 X3): stable_of(remote.cached()) when a cache file exists, whatever
    # its age; else the highest-numbered installed build that is not a prerelease; else None. Never a request.
```

Every command that takes a version parses it through one helper of `_shared.py`: when the text, or its name before `@`, is `latest`, it raises `latest_refused(latest_tag(ctx, store))` ([22](22-version-spec-and-jarinfo.md)) instead of the parser's plain refusal. Building the remote for `cached()` reads the settings (the cache file is named from the repository address, [12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache)); a `ConfigInvalid` there is caught and the tag then comes from the installed builds, so that a broken config file does not hide the usage error. That costs nothing on the commands that load no settings otherwise, since it happens only on this refusal.

Package 39 builds the same three for the run commands and should use these, so that the token and the repository are read in one place.

What each command does, beyond the domain function it calls:

- **`tool install [VERSION] [--force]`.** With a version: `parse_version_spec`, `install(...)`, the progress bar on stderr. Notes on stderr: the "already installed" line `v1.7.4@5a47802 is already installed (use --force to download it again)` with nothing after it; for several matches, one line naming each in its printed form; `warning: could not check GitHub for a newer build of v1.7.4: <reason>` when `could_not_check` is set (exit 0); `Pinned <build>` when this call pinned; for a second build of the pinned name, `rolling@1a2b3c4 installed; rolling@bc1b506 is still pinned (tlaup tool pin rolling@1a2b3c4)`. With no version: `read_auto_install(None, env)`; when it is unset and `ui.is_interactive()` is false, `UsageError` (2) asking for `stable` or `rolling`; otherwise `choose_first_build`, then as with that version. It asks whether or not builds are installed.
- **`tool upgrade [VERSION]`.** `upgrade(...)`. Notes: up to date; the new build and where the pin moved; how many older builds of the name remain, naming `tlaup tool uninstall`; a pin left on an older build; for `stable`, which builds remain.
- **`tool uninstall [VERSION]... [--all] [--yes]`.** Neither or both of `VERSION` and `--all`: `UsageError` (2), one `error:` line. With versions: resolve every argument before anything is removed; any that matches no installed build gives `VersionNotFound` (4) naming each such argument, and nothing is removed, with no question asked first. An argument matching several builds of one name: on a terminal without `--yes`, `choose_build(..., allow_all=True)`; with `--yes`, or not on a terminal, all of them. With `--all`: nothing installed is the note `no builds are installed` and exit 0, before any other rule and with no question; else `--yes` removes all; on a terminal, a yes-or-no question (answered no: note `nothing removed`, exit 0); not on a terminal without `--yes`: `UsageError` (2) "`--all` asks for confirmation and there is no terminal; add `--yes`", not `CannotAsk`. Then `uninstall(store, builds, groups=...)`, one group per argument with the builds it matched (or, after the question, the one chosen); for `--all`, one group of every build. Each removed build noted; each failure printed and exit 5 if any; when the pinned build was removed, `rolling@bc1b506 was pinned; nothing is pinned now` with the hint `tlaup tool pin <name>` listing what is left. A non-empty `missing` means another tlaup removed builds between the look and the lock, and nothing was removed: for named versions it is `VersionNotFound` (4) naming the arguments whose builds have all gone; for `--all` it is the note `no builds are installed` and exit 0 ([12 V3](../design/12-tools-and-downloads.md#v3-uninstall), question Q8, settled).
- **`tool pin VERSION`.** `pin(...)`, note `Pinned <build>`.
- **`tool current`.** On stdout, two lines: the pinned build as `rolling@bc1b506 (2026.11.15.002146)` (the printed form, with the CalVer in brackets where the build has one and the printed form does not already end in it), and the jar's path. Nothing pinned: `NoPinnedBuild` (3) with builds installed, `NoToolsInstalled` (3) without; a pin naming a missing build: `PinnedBuildMissing` (3). No Java, no network.
- **`tool path [VERSION]`.** One line on stdout, the jar's path. No version: the pinned build's, with `tool current`'s errors. A version: `find`; none, `VersionNotFound`; several, `AmbiguousVersion` (2) with the candidates in their printed form. It never asks ([02 X3](../design/02-cross-cutting.md#x3-version-syntax), the several-builds table).
- **`tool dir`.** One line on stdout, `AppPaths.tools`, whether or not it exists. It no longer lists builds.
- **`tool list [--installed]`.** One table on stdout through `ui.result` ([12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache), "`tool list` in the first wave"): the releases **that have a `tla2tools.jar`**, in X4's order, each directly followed by the installed builds of that name (decision D64). A release without the jar has no row, as in 0.8.x, though the cached list still holds it (25). An installed build of a name whose release has no jar at the moment (upstream's upload gap) keeps its place in X4's order, with the status `installed`. Installed builds whose name upstream no longer lists come last, with the status `installed, not upstream`, and no hint against uninstalling them is printed (decision D65). Columns Version, Build, Published (the asset's update date), Status, Pinned. The release list may come from the lookup cache (`Remote.releases()`, the one-hour default); when it is unavailable the installed builds are listed and one `warning:` line goes to stderr. With `--installed`: the installed builds only, in store order, no request.

  Status (a reading of V8, settled with the maintainer at the stage 4 sign-off, 2026-11-24; the expected files fix the result and the review reads them, [01 T8](../design/01-testing.md#t8-expected-output-files)): a release row is `available` when no installed build of its name is what upstream publishes (`same_as_published`), `installed` when one is; the row of the newest installed build of a name is `installed, update available` when it is not what upstream publishes, a build whose name upstream no longer lists is `installed, not upstream`, and every other installed row `installed`. V8's sentence ("`installed, update available` when the newest installed build of that name differs from the published one") and its test ("an older installed rolling build shows `update available` on its own row, directly under the `rolling` row") both hold under this reading. V8 does not write what a release row shows under Build, since no commit is read from a tag (V8, Rejected), nor how a cached or stale list is marked; the expected files decide both, and the pull request says what it chose.

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
- with `tool.repository` set to another `https` address, the requests go to that host (F3);
- `tlaup --debug tool install rolling` with `GH_TOKEN` set and GitHub failing: the token's value appears in neither stream (V7; the filter is 24's `redact`);
- `tool install latest` exits 2 and `0 request(s) were sent to GitHub`: with `the release list is cached from "releases", 600 minutes old` stderr names `v1.7.4` after `stable`; with nothing cached and `v1.7.4` installed it names `v1.7.4`; with neither, stderr holds `stable` and no tag in brackets (X3, finding B16).

`tool_uninstall.feature` (V3, C1, C2):

- three builds with the middle one pinned, `--all --yes` leaves none and `no build is pinned`;
- two named builds with the pinned one first: both removed;
- one build named that is not the pinned one: it is removed and `the pinned build is` still the other (T31);
- two builds named, the pinned one made impossible to remove (`the folder "<its folder>" is read-only`; the tools folder stays writable): exit 5, the other build gone, the stuck one intact and still pinned;
- on a terminal: two builds of `rolling`, `tool uninstall rolling` answered `-1, 7, 2`: `stderr contains "<question>" 3 times`, the second build removed, the first left; the same answered `all`; the same answered with an empty line removes both, `all` being the default answer (T33);
- the same store with `--yes` removes both without asking; with no terminal and no `--yes` removes both;
- `rolling@<commit>` removes one, in every mode;
- removing the pinned build leaves `no build is pinned`, and the next `tlaup tool current` exits 3 (V3's test names `tlaup tlc`, which is still the old command here, so the scenario uses `tool current`, and package 39 adds the `tlc` form to `tlc_errors.feature`);
- on a terminal: `--all` answered `n` removes nothing and exits 0;
- `--all` with no terminal and no `--yes` exits 2 and removes nothing; `--all` with nothing installed and no terminal exits 0 with the note, with and without `--yes`;
- `v1.8.0 nosuch` with `v1.8.0` installed exits 4, names `nosuch`, and `v1.8.0` is still installed;
- on a terminal with stderr redirected to a file: two builds of `rolling`, `tool uninstall rolling` removes both without asking (the question could not be seen; this is also V9's case "stdin a terminal and stderr not");
- `tool uninstall` with no argument, and with a version and `--all`, exits 2 with one `error:` line (C1);
- the C2 outline: `v1.7.4`, `1.7.4`, `stable`, `v1.7.4@5a47802` against the same store each remove the same build.

`tool_pin.feature` (V4, X3, C2, C1's `tool current` and `tool path`):

- by tag without `v` (`tool pin 1.7.4`, X3); `tag@commit`;
- ambiguous without a terminal exits 2 and lists the candidates;
- `tool pin v1.8.0` with only `v1.7.4` installed exits 4, and stderr names `tlaup tool install` (T27); (29b) `tool path v1.8.0` on the same store exits 4 (T29);
- on a terminal: ambiguous, the typed answer is pinned; with stderr redirected to a file, exits 2;
- the C2 outline: `v1.7.4`, `1.7.4`, `stable`, `v1.7.4@5a47802` give the same pinned build; the same outline for `tool path`;
- two builds of `rolling`, `tool path rolling` exits 2 and lists both (X3);
- `tool current` with a build pinned prints the printed form and the jar path; with nothing pinned exits 3; with the pinned build's folder removed exits 3;
- `tool dir` prints one line, the tools folder, and nothing else;
- (29b) F1's no-file rule: on a fresh home, `tlaup tool path` (exit 3, nothing installed) leaves `the file "{config}/config.yaml" does not exist`. F1 names `config.feature`; the scenario sits here because it is about `tool path`, and [44](44-config-commands.md), which writes `config.feature`, may land before or after 29b (findings B5, D3).

`tool_upgrade.feature` (V4, C2):

- the installed build equals the published digest: nothing downloaded and `1 request(s) were sent to GitHub` although `the release list is cached from "releases", 1 minutes old`;
- `tool upgrade` with no argument and `rolling` pinned upgrades `rolling`, and says it is up to date when it is (T39);
- a different digest installs the new build, moves the pin, removes the old;
- two installed builds of `rolling`: compared with the newer, and afterwards the older is still installed; the same with the older one pinned leaves the pin on it;
- upgrading a name that is not installed installs it;
- no argument with nothing pinned exits 3, with and without builds installed;
- a bare CalVer and `rolling@<commit>` exit 2 with no request; `tool upgrade v1.7.4@5a47802` exits 2 (C2);
- `stable` with `v1.7.4` installed and pinned and `v1.8.0` published as stable installs `v1.8.0`, moves the pin, and leaves `v1.7.4` installed.

`tool_list.feature` (V8, X4, C1):

- online, cached (`the release list is cached from "releases", 1 minutes old`, no request), stale (cached 3 hours old and GitHub unreachable) and unavailable (no cache, GitHub unreachable: the installed builds and one `warning:` on stderr), each against an expected file;
- an older installed rolling build shows `update available` on its own row, directly under the `rolling` row;
- no release of the `releases` recording that lacks a jar (the seven from `v1.4.8` to `v1.5.5`) has a row (inventory row T21, this package's half; D64);
- a build installed under a tag the recording does not list is the last row, with the status `installed, not upstream`, and neither stdout nor stderr holds a `hint:` or a word about uninstalling (inventory row T20; D64, D65);
- the row order of X4 against an expected file;
- `--installed` lists the installed builds and makes no request.

`errors.feature`, the scenarios [17](17-error-handler.md) handed to this package (18 wrote none of them), each asserting the code, an empty stdout and one `error:` line where stderr can be read:

- (29a) `tlaup tool pin nosuch` with stdout and stderr on a closed pipe exits 141 (real process, [02 X1](../design/02-cross-cutting.md#x1-exit-codes)).
- (29a) The unreadable pin file of [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks) (finding B4): with `a file "{tools}/pin/x" containing:` (so that `pin` is a folder, which no reader can read as a file, root included), `tlaup tool current` exits 5 (`FileOperationError`) and `stderr does not contain "Traceback"`; `tlaup --debug tool current`, and `tlaup tool current` with `TLAUP_DEBUG` set to `1`, exit 5 with `stderr contains "Traceback"`.
- (29a) `NetworkError` and `RemoteDataError` ([20 G2](../design/20-groundwork.md#g2-domain-errors), finding B17): `GitHub is unreachable` and `tlaup tool install v1.7.4` with nothing installed exits 5; `GitHub answers from "not-json"` and `tlaup tool install stable` exits 5 with `stderr does not contain "Traceback"` (the user side of V7's Fixed entry on a non-JSON answer).
- (29a) `tlaup tool` with nothing after it exits 2, the help on stdout, nothing on stderr (X1 rule 7, C1).
- (29b) `tlaup tool list` with two builds installed, with stdout on a closed pipe, exits 141 with no `Traceback` (real process). Likewise the plain pytest of X1, `tlaup tool list` with stdout on `/dev/full` (Linux only) exits 5 with `cannot write output` on stderr.

**Steps this package adds**, all from T5's fixed vocabulary, unless package 18 already has them (then use 18's):

- Given, the store: `the build "<spec>" is installed` (optionally `and pinned`), `no build is installed`, `the release list is cached from "<recording>", <n> minutes old` (written through package 25's `write_cache`, never by hand), `the jar of the build "<spec>" is truncated` (cut to half its size).
- Given, the rest: `GitHub answers from "<recording>"`, `GitHub answers <status> to "<path>"`, `GitHub is unreachable` (in-process only). `the folder "<path>" is read-only` and `java is not installed` are 18's.
- Then, the store: `the pinned build is "<spec>"`, `no build is pinned`, `the installed builds are:` (a table with one column, the printed form of each build, in store order: written by stage 4, as T5 gives no columns).
- Then, GitHub: `<n> request(s) were sent to GitHub`, `<n> jar download(s) were made`, `no request carried a token to "<host>"` (in-process only; they count the last `I run`).

`the build "<spec>" is installed` installs through `ToolStore.add` exactly the jar the `github` fixture publishes under that name, with the `Source` and `prerelease` its recorded release gives, so that `same_as_published` holds for it; with `@<commit>` or `@<calver>` in the spec it installs another build of that name with that commit or build time (a jar from the same helper with that manifest), which upstream does not publish. Both use package 22's small-jar helper and the recorded manifests. A new step needs a reason in the pull request (T5); none is expected beyond this list.

**Plain pytest**, `tests/unit/test_tool_commands.py`:

- `tool install` with no version, the question answered on in-memory streams (`interactive=True`, the answer in stdin), with one build installed and `responses` serving GitHub: the chosen build is installed ([12 V12](../design/12-tools-and-downloads.md#v12-install), Tests). It calls the command's plain function, not the Typer app, since in-process `CliRunner` has no terminal.
- T11, the download's progress bar: `tool install v1.7.4`'s plain function with a `Ui` whose stderr is a terminal (Rich forced to terminal mode, a fixed size, as 16's tests build it) and `responses` serving GitHub: stderr holds the bar with the jar's size and a transfer speed, and stdout holds nothing. Written by stage 4: the inventory row names no test, and in-process scenarios have no terminal.
- V7's query strings: `responses` serves a download that redirects to an address with `?sig=secret-value`. When the download succeeds, no `build.json` under the store contains `secret-value`. When the body then fails, under `--debug`, `secret-value` is in neither captured stream.

**Old tests:** none to delete, keep or change; the old suite went in 03b (D62). No test is written for the old `tlc`'s jar lookup in between (29b's edit below): the old command goes in 39, and its behaviour meanwhile is not promised.

**Inventory rows** ([preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md)) this package owns, and the test that holds each; each pull request names its rows:

| Row | Test | Pull request |
| --- | --- | --- |
| T1 (install downloads and installs a release's jar) | `tool_install.feature`, the rows of V12's table | 29a |
| T5 (already installed: no download, says so; `--force` downloads again) | `tool_install.feature`, V12's rows "already installed" and `--force`, and `tool install v1.7.4` run twice | 29a |
| T11 (a progress bar with size and speed) | the plain pytest above | 29a |
| T18 (`tool list`'s table and columns) | `tool_list.feature`, the four states against expected files | 29b |
| T19 (an installed build beside the current upstream build of its tag; with [25](25-remote-listing.md) for the status) | `tool_list.feature`, the older installed rolling build under the `rolling` row | 29b |
| T20 (`installed, not upstream`, decided by D64) | `tool_list.feature`, the build under a tag the recording does not list | 29b |
| T21, the `tool list` half (releases without a jar hidden) | `tool_list.feature`, the seven releases without a jar | 29b |
| T22, the scenarios (offline, cached, stale, unavailable) | `tool_list.feature`, the four states | 29b |
| T27 (pin an installed build; not installed is code 4 naming `tool install`) | `tool_pin.feature`, `tool pin 1.7.4` and `tool pin v1.8.0` | 29a |
| T28 (several builds of one name: `pin` asks which) | `tool_pin.feature`, on a terminal, the typed answer pinned | 29a |
| T29 (`tool path` prints one path; fails when nothing is pinned or not installed) | `tool_pin.feature`, the `tool path` scenarios | 29b |
| T31 (uninstall removes the named builds; a build not pinned leaves the pin) | `tool_uninstall.feature`, the two-build and the not-pinned scenarios | 29a |
| T33 (several builds: asks which, `all` the default) | `tool_uninstall.feature`, the terminal scenarios | 29a |
| T34 (`--all` asks; `--yes` skips it) | `tool_uninstall.feature`, the `--all` scenarios | 29a |
| T39 (upgrade with no argument upgrades the pinned name; up to date; not installed is installed) | `tool_upgrade.feature` | 29a |
| T8, this package's part (an unknown version is `VersionNotFound` naming it; [50](50-help-and-messages.md) owns the row) | `tool_uninstall.feature`'s `v1.8.0 nosuch`, `tool_pin.feature`'s `tool pin v1.8.0` | 29a |

No stateful test applies: the store machine is package 27's.

## Changelog

Every entry below is written in this package, word for word from its section, because a user first sees each change through the `tool` commands. Packages 22 to 28 write none of them. 29a writes the entries of V1, V3, V4, V5, V7, V11, V12, J3, F3, the C1 rows of its commands and X3's Added entry; 29b those of V8 (with D64's), X4, X3's Breaking entry and F6.

Breaking:

- V1: "Installed tools are stored in a new layout with a `build.json` beside each jar. They live in the cache's `tool` folder (was `tools`). Builds installed by earlier versions are not recognised: run `tlaup tool install` again. The old `tools` folder can be deleted."
- V3: "Uninstalling the pinned build clears the pin; it no longer switches to another installed build. Pin one with `tlaup tool pin`." "With several installed builds of one name, `tlaup tool uninstall NAME` without a terminal, or with `--yes`, removes all of them; name one build as `NAME@COMMIT`."
- V12: "`tlaup tool install` with no version asks which build to install (stable or rolling), or takes the answer from `TLAUP_AUTO_INSTALL`, and fails without either; it used to install the latest stable release."
- X3: "With several builds of one tag installed, `tlaup tool path TAG` now fails and lists them (it printed the first)."
- C1: "`tlaup tools dir` is now `tlaup tool dir` and prints only the folder; use `tlaup tool list --installed` for the builds." "`tlaup tools install -f` and `tlaup tools uninstall -y` are now `tlaup tool install --force` and `tlaup tool uninstall --yes`." "`tlaup tools` and `tlaup modules` are now `tlaup tool` and `tlaup module`; every subcommand keeps its name." (This line covers `module` too, which package 31 switches; it is written once, here, and 31 writes no second line for the rename.)

Removed:

- C1: "`tlaup tools meta sync` is removed; metadata is read from the jar at install."

The removal of `fetch-cache clear` is C1's line "`tlaup fetch-cache clear` and `tlaup tlc --cleanup` are now `tlaup cache clean`; ...", which [45](45-cache-commands.md) writes; V8 no longer has an entry of its own for it.

Added:

- V7: "`GITHUB_TOKEN` or `GH_TOKEN` is used for GitHub API requests, which raises the rate limit. The token is sent only to `api.github.com`, and to hosts you list in `tool.token_hosts`; it is never printed. Credentials in `.netrc` are not used."
- X3: "Versions can be typed without the `v`, as `stable` or `rolling`, and as `tag@commit` to name one build."
- C1, written by stage 4 from its rows (C1 gives no text for them): "`tlaup tool current` shows the pinned build and its jar without starting Java." "`tlaup tool list --installed` lists the installed builds only, with no network."
- F3: "`tool.token_hosts` lists extra hosts that may receive the GitHub token." (29a, where the token is first sent; findings B6, D4.)

Changed:

- V4: "`upgrade` compares the installed jar with the published one by SHA-256 where GitHub provides it."
- V5: "The commit shown for a build is read from the jar itself."
- V7: "Unencrypted addresses, and redirects to them, are refused."
- V8: "`tool list` keeps installed builds next to their upstream release and marks one that has a newer build available." "`tool list` marks an installed build whose release upstream no longer lists as `installed, not upstream` (was `local only`)." (decision D64)
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
- F6: "A warning from `tool list` went to stdout." (16 writes no entry)

Not here: V6's Removed entry (package 04 wrote it), V9's Added entry (39), X1's Breaking entry (48), F7's help-text entry and F11's (50), C1's rows of the other groups (31, 39, 44, 45, 46, 47), C1's `fetch-cache clear` line (45).

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

**The old `tlaup tlc` meanwhile** (29b). `tlaup tlc` stays on the old runner until package 39, and the old module commands on `cmd/modules/` until package 31. Nothing promises that they keep working in between (decision D62; no CI job runs real TLC through them), but `main` must type-check, and they find the tool jar through `get_tlc_jar_path` in `tlc/compiler.py` (five call sites when 29b starts: `cmd/tlc.py` once, `tlc/runner.py` twice, `cmd/modules/add.py`, `cmd/modules/path.py`; today there are six, and the second in `cmd/tlc.py`, inside `_show_diagnostic_info`, went with that function in package 04, which also made it return `Path | None`; finding G4 of the [second review](review-2026-11-24.md)), which imports `get_pinned_version_dir`. When 29b deletes that function, the body that type-checks and costs least is a read of the new store's pin:

```python
def get_tlc_jar_path() -> Path | None:
    build = ToolStore(AppPaths.from_env(os.environ), now=lambda: datetime.now(UTC)).pinned()
    return build.jar if build is not None else None  # PinnedBuildMissing passes up to the handler (3)
```

That is the whole edit; no other line of the old runner or commands changes, and no test is written for it (Tests). It is also why the old `tlc` runs on the new store from here until 39, which the design accepts as a gap of D62 ([01 T11](../design/01-testing.md#t11-the-existing-tests), Risks). Between 29a and 29b the old `tlc` reads the old pin, which nothing writes any more; that is allowed, since nothing is released in between (D6). The messages of the old code that name `tlaup tools install` are left as they are; their packages (31, 39) replace them.

Points a worker could miss:

- **The order of the uninstall checks** (V3): "nothing installed" first for `--all`; every named argument resolved before anything is removed and before any question; then the questions; then the removal. A question about "which build" is never asked when another argument matches nothing.
- **Not on a terminal is not an error for `uninstall NAME`**: it removes every build of the name. It is an error for `pin` (2), for `uninstall --all` without `--yes` (2, a usage error, not `CannotAsk`), and for `tool install` with no version and no variable (2).
- **`tool path` never asks**, on a terminal either: its output is for scripts.
- **The `--all` question.** Ask it through `Ui.ask` with the choices `y` and `n` and the default `n`, so that pressing Enter removes nothing: settled with the maintainer on 2026-11-24 and written into [12 V3](../design/12-tools-and-downloads.md#v3-uninstall). V3 gives no wording; the pull request says how the question reads.
- **`tool list` warns once.** The old code printed a warning glyph to stdout; the new one prints one `warning:` line to stderr through `ui.warning`, and only when the list is unavailable.
- **Candidates and builds are always printed by `format_build` with every installed build as `others`**, so the form typed back finds exactly that build (X3).
- **Imports.** `versioning/__init__.py` emptied means `import tlaup.versioning.store` no longer drags in `requests`; keep it so. Package 49's test runs `tlaup tool dir` in-process and asserts that `requests`, `yaml`, `truststore`, `rich.progress`, the settings schema and `tlaup.versioning.github` were not imported.
- **Dangling imports.** After each deletion `uv run mypy` and `ruff` name every import in `src/` that points at a deleted name; there is no old test left to show it (03b).

State of `main` when this starts: packages 01 to 28 merged (the store track complete, `redact` in the handler; 16 to 19 of the groundwork track: `Ui`, the handler, the feature harness, the layered config). The old `tools` group (`cmd/tools/`), `fetch-cache`, the old `versioning/` modules, `cache/github.py`, the old `tlc` and `modules` commands are all still there, with no old test (03b). Package 04 removed URL installs and the legacy layouts.

## Done when

- The feature scenarios and plain tests above pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- After 29a: `tlaup tools` and `tlaup tools meta sync` no longer exist. After 29b: `tlaup fetch-cache` no longer exists, and nothing under `src/` imports `tlaup.versioning.api`, `downloader`, `metadata`, `resolver`, `schema` or `tlaup.cache`.
- The changelog entries are written, each in its pull request; `README.md` and `docs/contributing/development.md` name the new commands.
- Each pull request names the inventory rows of the table under Tests that it covers, each with its test: 29a T1, T5, T11, T27, T28, T31, T33, T34, T39 and its `VersionNotFound` scenarios of T8; 29b T18, T19, T20, T29, and the halves of T21 and T22.
- The pull request says what the expected files of `tool list` chose for a release row's Build column and for the cached and stale lists, and how the `--all` question reads.

## Out of scope

- The domain functions: packages 22 to 28.
- The command tree test, the root options, `tlaup` alone, explicit registration of the other groups, and the "exit 2" scenarios of every removed name (`tools`, `fetch-cache`, `tools meta`, `install -f`, `uninstall -y`): package 48.
- `cache dir`, `cache list`, `cache clean` (which removes `<cache>/remote/`): package 45. `doctor`, which reports leftover folders in the store and checks the pinned jar's SHA-256: package 46. Completion of versions: package 47.
- The `--auto-install` option of the run commands, `first_run.feature`, wrapping `ensure_tools` for a run, deleting `tlc/compiler.py`, `get_tlc_version`, `tlc --version`: package 39. The `module` group and the deletion of `versioning/paths.py`'s module functions: package 31.
- The debug filter itself (`redact` and its call in the handler): package 24.
- Help text as a whole, the CLI reference, F11's messages ("did you mean" for a version): packages 50 and 51.
- The milestone 4 `tool list` display, `--yes` for every prompt, `pin --local`: later milestones.

## Risks

- *An upgrade can finish and still fail* (settled while building 27b, 2026-11-25, a low-impact choice by the stage 5 lead). When the old build cannot be removed after the new one is added and the pin moved, `upgrade()` returns its `UpgradeReport` with `failed` set and `removed` None, rather than raising. `tool upgrade` prints what was done (the pin moved) as notes and the failure as one `error:` line with its hint (F6's classification, settled at 29a's review), and exits 5, as V3 does for a failed removal.
- *`choose_build` takes `every=`, required*: pass `store.builds()`, so the printed forms are worked out among every installed build.

- *The download's progress can go back once* (noted while building 26, 2026-11-25). When the size or digest does not match, `fetch_build` downloads once more and its `progress` callback starts again from 0, so the progress display must accept a count that drops once.

- From V3: a script that ran `tool uninstall rolling` expecting one build to go now removes every rolling build; the changelog says so, and an older rolling build cannot be downloaded again (research 5).
- From V12: older builds of a moving tag pile up; `tool list --installed` shows them and `tool upgrade` or `tool uninstall` removes them.
- From C1: this is the first of the release's two large user-visible changes, landing in 0.9.0 with the changelog as the upgrade guide.
- From the cut: the real-process scenarios on a pty depend on the platform's `pty` module and are skipped on Windows (T5); the prompt paths are not run there.
- From the cut, size. Eight commands, five feature files with about seventy scenarios, the steps, the deletions and some forty changelog lines are more than one review sitting, so the package is two pull requests (below). After 29a a user can install, upgrade, remove and pin builds in the new store and see the pin with `tool current`; `tool list` and `tool path` are absent for a while, which is a missing command, not a half-built one, and nothing is released in between (D6).

## Pull requests (decided by stage 4)

This package is delivered as two pull requests; the index lists them as 29a and 29b. Readers first does not work (two stores would be live, or nothing could install), so the split is by command. Each entry under Files names its pull request.

- **29a** (L): `tool install`, `upgrade`, `uninstall`, `pin`, `current` and `dir`; deletion of the old `tools` group (`cmd/tools/`) and its registration; the store and GitHub steps and the `not-json` recording; four feature files and 29a's `errors.feature` scenarios; the renamed commands in 18's scenarios and 17's handler test; the changelog entries of V1, V3, V4, V5, V7, V11, V12, J3, F3, the C1 rows of these commands and X3's Added entry. Depends on everything this file lists.
- **29b** (M): `tool list` (with `--installed`) and `tool path`, `tool_list.feature`, the `tool path` scenarios and F1's no-file scenario; deletion of `cmd/fetch_cache/`, `src/tlaup/cache/`, the old versioning modules and the tool functions of `versioning/paths.py`; `versioning/__init__.py` emptied and `cli.py`'s `get_app_version` import; the `requests` half of 24's import test in `test_redact.py`; the `get_tools_dir` assertion of `test_context.py`; `get_tlc_jar_path`'s new body; the entries of V8 (with D64's), X4, X3's Breaking entry and F6's `tool list` entry. Depends on 29a.

A package that names 29 as a dependency waits for 29b.
