# 28. First run: `ensure_tools` and the choice of build

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

`tlaup.versioning.first_run` decides what build a run uses when the user has not said: the pinned one, an error that names the next command, or, with nothing installed, the stable-or-rolling question (or its answer from `--auto-install` or `TLAUP_AUTO_INSTALL`) followed by an install. Every case in which the question is asked is tested in plain pytest with a `Ui` on in-memory streams and GitHub served by `responses`. No command calls it yet.

## Covers

- Roadmap items:
  - "First-run prompt (decision D4): when nothing is pinned, ask once between stable and rolling, then install the choice. A flag and an environment variable answer it; error with a hint when there is no terminal. ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the domain code and its plain pytest tests. The preflight that calls it for `tlc` is package 33's `get_build` seam, wired by package 39 with `first_run.feature`; `sany`, `pcal` and `repl` call it from packages 41 to 43; `tool install` with no version uses `choose_first_build` in package 29.
- Design sections:
  - [12 V9](../design/12-tools-and-downloads.md#v9-first-run-prompt): `choose_first_build`, `ensure_tools`, the table of states, the prompt, where `auto_install` comes from, and the plain pytest cases of V9's Tests. Not here: the `--auto-install` option on the four run commands (39, 41 to 43), `first_run.feature` (39), the changelog entry (39, below).
  - [11 R11](../design/11-runner.md#r11-preflight), step 3, the rows "Nothing installed", "Builds installed, none pinned", "The pin names a build that is gone": the errors and their hints, as `ensure_tools` raises them. The order of the preflight is package 33's.

## Depends on

- [27](27-install-steps.md): `install()` and `InstallReport`; it pins the first build installed.
- [25](25-remote-listing.md): `Remote`, `Release` and `stable_of`, for the two dates of the prompt; the raising list fetch below.
- [23](23-tool-store.md): `ToolStore.builds`, `pinned`, `format_build`.
- [16](16-ui-messages.md): `Ui` with `ask`, `is_interactive`, `note`, and its constructor on in-memory streams.
- [24](24-github-client.md): `GitHubClient` (passed through to `install`), the `Progress` type.
- [22](22-version-spec-and-jarinfo.md): `VersionSpec`.
- [05](05-github-recordings.md): the `github` fixture and the `releases` recording.
- [02](02-errors-and-paths.md), [03](03-test-foundation.md): `NoToolsInstalled`, `NoPinnedBuild`, `PinnedBuildMissing`, `CannotAsk`, `UsageError`; the isolation fixture.

Changes from the draft (27, 16): 25, 23, 24, 22, 05, 02 and 03 are added because they are used directly; none changes the order.

## Files

Creates:

- `src/tlaup/versioning/first_run.py` (written by stage 4: V9 names no module, and 00's tree has none for it; `install.py` is package 27's and holds install, upgrade and uninstall)
- `tests/unit/versioning/test_first_run.py`

Changes:

- `src/tlaup/versioning/remote.py` (package 25's), only if it has no public way to fetch the release list fresh and raise when that fails: one method, below.
- `tests/unit/versioning/test_remote.py`, one test for that method, in the same case.

Must not touch: the old modules under `src/tlaup/versioning/` and `cmd/`.

## Interfaces

Provides, from [12 V9](../design/12-tools-and-downloads.md#v9-first-run-prompt):

```python
# tlaup/versioning/first_run.py
def choose_first_build(remote, ui, *, auto_install: str | None) -> VersionSpec      # "stable" or "rolling"
def ensure_tools(store, remote, client, ui, *, auto_install: str | None, may_install: bool = True) -> Build
```

Written by stage 4, from V9's words:

```python
def ensure_tools(store, remote, client, ui, *, auto_install: str | None, may_install: bool = True,
                 progress: Progress | None = None) -> Build
    # `progress` is handed to install(): the command that calls it draws the bar (29, 39)

def read_auto_install(option: str | None, env: Mapping[str, str]) -> str | None
    # the option, else TLAUP_AUTO_INSTALL; "stable" or "rolling"; an empty variable counts as unset.
    # Anything else is UsageError (2) naming where the value came from. The run commands and `tool install`
    # call it; `tool install` has no option and passes None.
```

`ensure_tools`, in V9's order (the first matching row wins):

| State | Result |
| --- | --- |
| A build is pinned | `store.pinned()` is returned. A pin that names a missing build raises `PinnedBuildMissing` from `pinned()`, with its hint; no question. |
| Builds installed, none pinned | `NoPinnedBuild` (3), the hint naming the builds to pin (`tlaup tool pin <one of: ...>`, in their printed form). No question. |
| Nothing installed, `may_install` false | `NoToolsInstalled` (3), hint `tlaup tool install stable` or `rolling`. Nothing is asked and nothing installed, whatever `auto_install` and `interactive` are: this is `--show-command`. |
| Nothing installed, `auto_install` set | `install(store, remote, client, <that>)`, with one notice on stderr through `ui.note` naming what is being installed and from where. |
| Nothing installed, `ui.is_interactive()` | `choose_first_build`, then `install` of the answer. |
| Nothing installed, neither | `CannotAsk` (3): "no TLA+ tools installed" / "run `tlaup tool install stable` or `tlaup tool install rolling`, or set TLAUP_AUTO_INSTALL". |

After an install, `ensure_tools` returns `store.pinned()`: the build just installed, unless another tlaup pinned one first, in which case the pin is what runs ("the choice is installed and pinned, and the command carries on", read so; the pin is the default once something is pinned, V9 Rejected). Settled with the maintainer at the stage 4 sign-off, 2026-11-24 (index, "Settled since").

`choose_first_build`: `auto_install` set returns it with no request and no question. Otherwise, when `ui.is_interactive()`, it fetches the release list fresh (one request), and asks on stderr, through `ui.ask` with the choices `1` and `2` and the default `1`:

```
No TLA+ tools are installed. Which build should tlaup install?
  1) stable   v1.7.4, released 2024-08-05
  2) rolling  the newest development build, updated 2026-11-15
Choice [1]:
```

The stable line names `stable_of(releases)` and its `published_at` date; the rolling line the `rolling` release's asset `updated_at` date, since `rolling`'s `published_at` is the day it was first created and says nothing about the jar (research 8). It returns `VersionSpec(name="stable")` or `VersionSpec(name="rolling")`. When it cannot ask (not interactive, no answer) it raises `CannotAsk`; the caller decides what that means (`ensure_tools` passes it on; `tool install` checks first and raises `UsageError` itself, package 29).

The raising list fetch. V9: "If the network is unavailable the prompt is not shown and the error is the network error." `Remote.releases()` does not raise; it reports stale or unavailable data with no reason (package 25, "Freshness carries no reason"), and keeps one inner function that fetches and raises, which `resolve` uses. If that function is not public on `main`, make it so, written by stage 4: `Remote.fetch_releases(self) -> list[Release]`, fresh, writing the cache as `releases()` does, raising the client's error. Do not raise a new `NetworkError` of this module's own from a stale or unavailable state: the user should see why the network failed.

Consumes: `install`, `InstallReport` (27); `Remote`, `stable_of` (25); `ToolStore`, `format_build` (23); `Ui` (16); `VersionSpec` (22); the errors (02).

Used later by: package 33's tests through a stand-in `get_build`, and package 39, which wraps `ensure_tools` as the `get_build` of a run and `ensure_tools(..., may_install=False)` as that of `--show-command` ([20 G1](../design/20-groundwork.md#g1-tlc-invocation), [12 V9](../design/12-tools-and-downloads.md#v9-first-run-prompt); finding B23); packages 41 to 43 the same for `sany`, `pcal`, `repl`; package 29, which calls `choose_first_build` and `read_auto_install` for `tool install` with no version.

## Tests that must pass

Plain pytest, `tests/unit/versioning/test_first_run.py`. Each test builds `Ui(io.StringIO(), io.StringIO(), io.StringIO(<answers>), color=..., env={}, interactive=...)` and a real store in `tmp_path`, and serves GitHub through the `github` fixture ([01 T5](../design/01-testing.md#t5-feature-files-and-steps), "What is a plain pytest test instead"). No patching.

V9's cases in which the question is asked, all this package's:

- the prompt answered `2` installs and pins rolling and returns that build;
- an empty line takes the default, stable;
- `9` and then `1` asks twice (`stderr contains` the question twice) and installs stable;
- an empty read (end of input) raises `CannotAsk`, and nothing is installed;
- the network failing before the prompt raises the network error and writes no question to stderr;
- no stable release available: with `interactive` true and a release list whose every release is a prerelease (the `releases` recording with each `prerelease` set to true, served with `responses`, as [25](25-remote-listing.md)'s row "All releases are prereleases" builds it), `choose_first_build` raises `VersionNotFound` and stderr holds no question (Context, "No stable release available"; finding G11 of the [second review](review-2026-11-24.md));
- `may_install=False` raises `NoToolsInstalled` and asks nothing, with `interactive` true and false and with `auto_install` set and unset (no request is made).

The other rows of the table, also here, since they are the function's: a pinned build is returned with no request; builds installed and none pinned raise `NoPinnedBuild` whose hint names them; a pin naming a missing build raises `PinnedBuildMissing`; `auto_install="rolling"` installs and pins rolling with no question and one notice on stderr; nothing installed, not interactive and no answer raises `CannotAsk`. `read_auto_install`: the option wins over the variable; an empty variable is unset; `nightly` from either is `UsageError`. The question goes to stderr and nothing to stdout.

The tests that wait for other packages:

- `first_run.feature` (in-process) is package 39's: the rows that ask no question; `TLAUP_AUTO_INSTALL=rolling tlaup tlc Spec` installs and runs, the fake `java` started for the original command; `--auto-install nightly` exits 2; nothing installed and a spec that does not exist exits 4 with no request to GitHub and nothing installed, also with `TLAUP_AUTO_INSTALL` set; `tlc Spec --show-command` with nothing installed exits 3 with no request, also with `TLAUP_AUTO_INSTALL` set; nothing installed and no variable exits 3. And the one real-process scenario on a pty: nothing installed and a spec that does not exist exits 4 and the screen shows no question.
- `tool_install.feature` is package 29's: no version with `TLAUP_AUTO_INSTALL=stable` installs stable without asking; no version, no terminal and no variable exits 2. Also 29's: the plain pytest of `tool install` with no version, the question answered on in-memory streams with one build installed ([12 V12](../design/12-tools-and-downloads.md#v12-install), Tests).
- "stdin a terminal and stderr not" is covered by V3's uninstall scenario on a pty with stderr redirected, package 29.

Old tests: none (03b deleted the old suite). No row of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) names this package as its owner. Stateful tests: none apply.

## Changelog

None in this package. V9's entry is written by package 39, where `tlaup tlc` first asks: Added "With no tools installed, `tlaup tlc` (and `sany`, `pcal`, `repl`) asks whether to install the stable release or the rolling build, installs it and carries on. `--auto-install stable|rolling` or `TLAUP_AUTO_INSTALL` answers the question for scripts. The spec is checked first, and `--show-command` never asks or installs." The part about `tool install` with no version is V12's Breaking entry, package 29.

## Context for the worker

Decisions:

- D4: ask once, on the first run, between stable and rolling, then install the choice; a flag and a variable answer it; without a terminal and without an answer it is an error with a hint.
- D45: the preflight checks the spec and a named cfg before it calls this, so a typo is reported with code 4 before any question or download. That order is the caller's (33, 39); `ensure_tools` must not look at the spec.
- D32: `rolling` is the release tagged `rolling`; nothing picks it unless the user typed it or chose it here. `stable` is the highest-numbered release that is not a prerelease or a draft and has the jar.
- The names `--auto-install` and `TLAUP_AUTO_INSTALL` are the design agent's (README, "Decisions the design agent made").
- [14 F6](../design/14-config-and-cli.md#f6-messages): `ui.is_interactive()` needs stdin and stderr both to be terminals, because the question goes to stderr and the answer comes from stdin. `Ui.ask` is the only place that reads an answer; it raises `CannotAsk` at end of input and asks again for an answer outside the choices. Never Typer's or Rich's prompt functions.

Points a worker could miss:

- **The order of the table is the design.** `may_install` false comes before `auto_install`: `--show-command` never installs, also with `TLAUP_AUTO_INSTALL` set.
- **No prompt when builds are installed and none is pinned.** That user needs `tool pin`, not stable-or-rolling (V9, Rejected).
- **A pin naming a missing build is not "nothing installed".** `ensure_tools` reports it; only `install` repairs it (V12, D50).
- **Domain code prints only through the `ui` it was given**: the question and the one notice. Nothing else.
- **No stable release available** (every release a prerelease, which V8 tests): the prompt cannot name one. The error `Remote.resolve` gives for `stable` ("no stable release is available", `VersionNotFound`) comes out before the question; a unit test with a list of prereleases only shows it, and that no question was written (under Tests). Settled with the maintainer at the stage 4 sign-off, 2026-11-24 (index, "Settled since").
- **Two list requests on a first run that picks stable**: one for the prompt's dates, one when `install` resolves `stable` fresh. V9 counts one request for the prompt; nothing counts the install's. Leave it.
- **A first run downloads 4.5 MB in the middle of a command** (V9, Risks); the notice names what and where, and the caller's progress bar shows the download.

State of `main` when this starts: packages 22 to 27 and 16 merged; `tlaup tlc` is still the old runner, which knows no first run, and the old `tools` commands still exist.

## Done when

- The tests above pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- The pull request says whether `remote.py` needed the raising list fetch.

## Out of scope

- The `--auto-install` option of `tlc`, `sany`, `pcal` and `repl`, and wrapping `ensure_tools` as their `get_build`: packages 39, 41, 42, 43. The preflight order: package 33.
- `first_run.feature` and V9's changelog entry: package 39.
- `tool install` with no version, its `UsageError`, its feature scenarios and its plain pytest: package 29.
- `install` itself: package 27.

## Risks

- From V9: a first run downloads 4.5 MB during a command the user expected to be quick.
- From the cut: until package 39, nothing calls `ensure_tools`; its behaviour through a command is first seen there. The unit tests above are the only check before it.
