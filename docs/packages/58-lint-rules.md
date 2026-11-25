# 58. Lint rules

Size: M, as six pull requests of size S, one per rule group (58a to 58f; see the last section). Suggested model: mid-tier. Status: ready.

## Goal

ruff's blind-except, naive-datetime and print rule groups are on and the tree passes them; a check forbids `typer.echo` and `Console(` outside `tlaup/ui.py` and the reporters; the global `PLW1510` ignore and the bandit skip `B607` are gone; `tests/fakes/` and `scripts/` are under mypy's strict mode; and no `Any` escape hatch or carried-over complexity `noqa` is left in the rewritten code.

## Covers

- Roadmap items:
  - "Lint rules: enable ruff's blind-except, naive-datetime and print rule groups (BLE, DTZ, T20) and fix what they flag, including the two `except Exception: pass`; review the global `PLW1510` ignore and the bandit skips B404, B603 and B607; replace the `Any` escape hatches in the formatter and models." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this), line 394). In full: most of what the rules flagged on 0.8.x is deleted by the packages that rewrite it; this package switches the rules on and fixes what is left.
  - "Route every message through the one UI helper ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the mechanical guard, "a second check forbids `typer.echo` and `Console(` outside `ui.py` and the reporters" ([14 F6](../design/14-config-and-cli.md#f6-messages)). The helper is [16](16-ui-messages.md); the call sites are the switch packages.
- Design sections:
  - [30 I8](../design/30-ci-and-release.md#i8-lint-rules): every row except `TID251`, which [03](03-test-foundation.md) switched on with the test rules.
  - [14 F6](../design/14-config-and-cli.md#f6-messages): the last paragraph's two checks.

## Depends on

- [48](48-command-tree.md): the full command tree, with every command module switched (29, 31, 39, 41 to 47) and the old `cmd/` modules gone.
- [50](50-help-and-messages.md): the help and wording pass, which deletes the four old message functions of `tlaup/ui.py` and checks by `grep` that no `typer.echo` remains outside `ui.py` and the reporters.
- [40](40-live-display.md): the live layout, the last package that rewrites the display code (`tlc/formatter.py`, `tlc/components.py` and the reporters), where the 0.8.x code's naive `datetime.now()` calls are.
- [49](49-startup-cost.md): the rewrite of `versioning/app_version.py`, the `git` call, which states `check=False` and runs the absolute path `shutil.which` returns.

Changed from the draft (48, 50): 40 and 49 are added. Neither is among 48's dependencies, and each rewrites code these rules read; switching a rule on before them would make this package fix code that is about to be replaced, or make them fail their lint.

## Files

Changes:

- `pyproject.toml`:
  - `[tool.ruff.lint] select` gains `"BLE"`, `"DTZ"`, `"T20"`.
  - `ignore` loses `"PLW1510"`.
  - `[tool.ruff.lint.per-file-ignores]` gains `T20` for `scripts/*` and `tests/fakes/*` (I8: "exempt per file").
  - `[tool.bandit] skips` becomes `["B404", "B603"]` (`B607` goes).
  - `[tool.mypy] exclude`: `tests/` becomes an exclusion of `tests/` except `tests/fakes/`, for example the regular expression `^tests/(?!fakes/)`, so `uv run mypy .` checks the fakes (I8: "`tests/fakes/` and `scripts/` are checked"; [03](03-test-foundation.md) wrote the fakes typed for this). `scripts/` is already checked.
- `.pre-commit-config.yaml`: a local `pygrep` hook, `no-direct-output` (name the worker's), over `^src/.*\.py$`, with the pattern `\btyper\.echo\b|\bConsole\(` and `exclude: ^src/tlaup/(ui\.py|reporters/)`. It runs locally and in CI through the `lint` job's pre-commit step ([53](53-ci-workflows.md), I6).
- Whatever the new rules flag in `src/`, `scripts/` and `tests/` (Context, "What may still be flagged"). Each fix is the smallest that satisfies the rule without changing behaviour; anything larger is reported, not done.

Creates, Deletes: nothing, unless a flagged line can only be fixed by deleting dead code, which is then reported in the pull request.

Shared files: `pyproject.toml` with 51, which may run beside this package (one task line), and 59 (the coverage block; other sections); `.pre-commit-config.yaml` with 57 (other hooks). The six pull requests of this package all edit `[tool.ruff.lint]` or the lines next to it, so they land one at a time. This package does edit `src/`; it comes after the last command package (48), the help package (50), the display (40) and the startup package (49), so no package of the plan rewrites the same lines after it, except 51 (documentation only) and the test packages 52 and 59.

## Interfaces

None. Configuration and fixes only.

The rules as they stand after this package, which every earlier package is expected to follow already (the index puts them among the rules every package follows):

| Rule | What it requires | Allowed exceptions |
| --- | --- | --- |
| `BLE` (blind except) | No `except Exception` or `except BaseException`, and no bare `except:`; name the exceptions. | The two [30 I8](../design/30-ci-and-release.md#i8-lint-rules) allows, each with `noqa: BLE001` and a comment: the last branch of `TlaupGroup.invoke` ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)), which turns any other exception into an internal error (code 5) ([17](17-error-handler.md) writes it); and the guard round each completer, which returns nothing on any failure ([23 C3](../design/23-command-layout.md#c3-completion), [47](47-completion.md) writes it). |
| `DTZ` (naive datetime) | No `datetime.now()`, `utcnow()`, `fromtimestamp()` or `strptime()` that yields a naive time. Times are UTC and aware (`datetime.now(UTC)`, or the injected `now`), or kept as text (the parser keeps TLC's times as text, [10 P3](../design/10-parser.md#p3-result-model)). | None. |
| `T20` (print) | No `print` in `src/`: all output goes through `tlaup.ui` or a reporter's consoles ([14 F6](../design/14-config-and-cli.md#f6-messages)). | `scripts/` and `tests/fakes/`, per file. |
| `typer.echo`, `Console(` | Neither outside `tlaup/ui.py` and `tlaup/reporters/`. | None. |
| `TID251` (03) | No `unittest.mock.patch` in `tests/`. | None. |
| `PLW1510` | Every `subprocess.run` states `check=` explicitly. | None. |
| bandit `B607` | No process started from a partial executable path: every executable is an absolute path, from `locate` for `java` and `javac` ([13 J2](../design/13-modules-and-java.md#j2-finding-java)) and from `shutil.which` for `git` ([49](49-startup-cost.md)) and the editor ([44](44-config-commands.md)) (I8, D15). | None. bandit `B404` and `B603` stay skipped: tlaup starts processes from argument lists by design (roadmap, "Keep"). |
| `Any` | No `Any` in the parser's model or in the reporters; `sany_errors: list[Any]` is `list[Diagnostic]` ([10 P3](../design/10-parser.md#p3-result-model)). | Where a third-party signature forces it, with a comment. |
| Complexity `noqa` | None of the three 0.8.x markers on `tlc`, `run_tlc` and `add_module` is carried over; their replacements are smaller functions. | None. |
| mypy strict | On `src/`, `scripts/` and `tests/fakes/`. | The rest of `tests/` stays unchecked in this wave (I8; milestone 5). |

## Tests that must pass

- `uv run poe lint` passes with the new rules, and `uv run pre-commit run --all-files` passes with the new hook.
- The hook can fail: the pull request shows it failing once on a scratch line `typer.echo("x")` in a command module, and passing on the same line in `src/tlaup/ui.py` (tried by hand; the scratch lines are not committed).
- `uv run poe test` and CI pass unchanged: no fix changes behaviour, so no test changes, except a test line the rules flag (a `datetime.now()` in a test is fixed the same way).
- No new test file. Each pull request (below) passes `uv run poe lint` with its own group on and the groups of the pull requests before it.

## Changelog

None. Nothing a user sees changes.

## Context for the worker

**What the rules flagged on 0.8.x, and where it goes** (counted on 2026-11-21 with the locked ruff over `src/`: 23 findings in all over the tree, 19 in `src/`):

| Finding | Where in 0.8.x | Gone with |
| --- | --- | --- |
| `BLE001`, `except Exception: pass` | `cmd/tlc.py` (`_show_diagnostic_info`) | [04](04-delete-dead-code.md) (O2) and [39](39-tlc-command.md) |
| `BLE001`, `except Exception` reading `module.json` | `cmd/modules/list.py` | [31](31-module-commands.md): it becomes `except (OSError, ValueError)` (I8) |
| `T201`, eight `print` | `cmd/tlc.py` | 39 (the old command is replaced) |
| `DTZ005`, `datetime.datetime.now()` | `cmd/modules/add.py` | [30](30-module-build.md) and 31: build times in UTC ([13 M2](../design/13-modules-and-java.md#m2-build-in-a-temporary-folder)) |
| `DTZ005`, six `datetime.now()` for the elapsed time | `tlc/components.py` | 39 and 40: the elapsed time comes from the reporter's injected clock ([22 O3](../design/22-reporters.md#o3-terminal-reporter)) |
| `DTZ007`, two `strptime` | `tlc/parser.py` | 39 (the old parser is deleted; times are text, P3) |
| `PLW1510` | `subprocess.run` in `versioning/app_version.py`, `versioning/metadata.py`, `java/inspector.py`, `cmd/modules/add.py`, `cmd/config/edit.py`, `tlc/runner.py` | 49, 29, [46](46-doctor.md), 30, [44](44-config-commands.md), 39. After them I8 counts four calls (the Java version, `javac`, `git`, the editor), each with `check=` stated. |
| `Any` | `tlc/models.py`, `tlc/formatter.py`, `versioning/api.py`, `versioning/metadata.py` | 39 and 40 (models and formatter), 29 (the versioning modules) |
| Complexity `noqa` | `cmd/tlc.py::tlc`, `tlc/runner.py::run_tlc`, `cmd/modules/add.py::add_module`; also `java/classpath.py::_resolve_paths` and `cmd/modules/path.py` | 39, 31; `classpath.py` with [33](33-tlc-invocation.md) (G1), `modules/path.py` with 31 (the command goes, C1). |

**What may still be flagged by then.** Code written by the packages between 03 and 50 that missed one of the rules above, since none of them had the rules switched on; the likeliest:

- a `datetime.now()` without `UTC` in the store, the remote cache, run folders or module build (each takes an injected `now`; the production default must be aware);
- a `print` or `typer.echo` left in a command or in `tlaup/cli.py`'s root callback, or a `Console(` built outside `ui.py` and the reporters (for example in `completion` or `doctor`);
- a `subprocess.run` without `check=`;
- a process started by a bare name: I8 now says `git` ([49](49-startup-cost.md)) and the editor ([44](44-config-commands.md)) are resolved with `shutil.which` and started by their absolute path, and both packages build them so; bandit's `B607` finds any that missed it once the skip goes;
- an `except Exception` in a new place other than the two allowed;
- `Any` in a new module.

A finding in code that a package of the plan was meant to delete (an old module still present) is not fixed here: report it to the index as a missed deletion.

**The `Console(` pattern.** `ui.py` defines `_PipeConsole(Console)` and builds its two consoles; reporters build spool consoles on temporary files ([22 O4](../design/22-reporters.md#o4-live-display)). Both are allowed by the hook's `exclude`. A type annotation `Console` without a call does not match. `typer.secho` is not named by the design; if one is found, it is a `typer.echo` with colour and is replaced the same way (report it; do not widen the hook's pattern without the index).

**T20's scope.** I8 says "On for `src/`" and "`scripts/` and `tests/fakes/` are exempt per file". The group is selected for the whole tree with those two folders exempt, so the rest of `tests/` is checked too; a test that prints is rare and is fixed.

**State of `main` when this starts.** Every command is switched and the old domain modules are deleted; `tlaup/ui.py` has only the `Ui` of 16; the reporters are under `tlaup/reporters/`. `pyproject.toml` selects the groups of today plus `TID251` (03) and ignores `PLR2004` and `PLW1510`; bandit skips B404, B603, B607; mypy excludes `build` and `tests/`.

## Done when

- `BLE`, `DTZ` and `T20` are selected; `PLW1510` is no longer ignored; bandit skips only B404 and B603; mypy checks `tests/fakes/`; the hook is in; each in its own pull request.
- After each pull request, `uv run poe lint`, `uv run ruff format --check .`, `uv run poe test` and `uv run pre-commit run --all-files` pass; CI is green.
- Each pull request lists every fix it made in `src/` and any finding reported instead of fixed; 58a lists the two blind-except `noqa` lines with their reasons.

## Out of scope

- `TID251` and the monkeypatch hook: [03](03-test-foundation.md).
- mypy on the rest of `tests/`: milestone 5 (I8).
- Any behaviour change, rename or refactoring beyond what a rule demands.
- The format check: [01](01-ruff-format.md).

## Risks

- From I8: the rules may flag more than the design expects in code written by twenty packages; one pull request per rule group keeps each about one thing.
- From the cut: this package edits `src/` across many files at the end of the plan; it should be built when no other code package is open, so its fixes do not conflict.
- A rule a package did not follow and that this package fixes is a sign the package's review missed it; the index's list of rules every package follows is the prevention.

## Pull requests (decided by stage 4)

[30 I8](../design/30-ci-and-release.md#i8-lint-rules): "one pull request for each row of the table that switches something on" (review finding D15). Six pull requests, each of size S, each switching on one group and fixing only what that group flags, along the seams this file names. They all edit the same few lines of `pyproject.toml`, so they land one at a time; the order below is a suggestion, and any order works.

- **58a**, `BLE`: `"BLE"` in `select`; the fixes; the two allowed `noqa: BLE001` lines checked for their comments.
- **58b**, `DTZ`: `"DTZ"` in `select`; the fixes.
- **58c**, `T20` and F6's check: `"T20"` in `select` with the per-file ignores for `scripts/*` and `tests/fakes/*`; the `no-direct-output` hook against `typer.echo` and `Console(` ([14 F6](../design/14-config-and-cli.md#f6-messages)), shown failing once on a scratch line; the fixes. The two belong together: both keep output inside `tlaup.ui` and the reporters.
- **58d**, `PLW1510`: the global ignore removed; any `subprocess.run` without `check=` fixed.
- **58e**, bandit `B607`: the skip removed; any executable started by a partial path fixed.
- **58f**, mypy on `tests/fakes/`: the `exclude` narrowed; the fakes' type errors fixed. Also the two rows of the table that switch nothing on, checked here once the code is final: no `Any` in the parser's model or the reporters, and none of the 0.8.x complexity `noqa` markers carried over. A finding is fixed if it is a small typing fix, else reported.

Each depends on everything this file lists; none depends on another. A package that names 58 as a dependency waits for all six.
