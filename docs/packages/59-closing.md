# 59. Closing the first wave

Size: M (was S: the closing check of decision D62 walks the whole preserved-behaviour inventory). Suggested model: mid-tier. Status: built.

## Goal

Every row of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) that is kept has a test that exists and passes (decision D62's closing check); the coverage threshold is set from the measured figure for the first time, or the figure goes to the maintainer; the `pending` marker and its deselection are gone because nothing carries them; nothing of the old test suite, its fixtures or the throwaway reference models is left; and the exit criteria of milestones 1, 1b and 2 have been checked one by one, with a report of each that holds, each that does not, and each that waits on the maintainer. This package changes only the settings it owns; everything else it finds is reported.

## Covers

- Roadmap items:
  - "Coverage policy: branch coverage on; a `fail_under` near the current 83 percent; coverage only in the full-suite task ...; randomised test order; warnings as errors." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this), line 384). In part: the final `fail_under`. Everything else is [03](03-test-foundation.md)'s.
  - The exit criteria of [milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust) (line 284), [milestone 1b](../roadmap.md#milestone-1b-other-tools-reporters-command-layout) (line 350) and [milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this) (line 436): checked, not built.
- Design sections:
  - [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings): "No `fail_under` until the end of milestone 2": "The last milestone 2 work package measures it and sets `fail_under` to it, rounded down to a whole number", and a figure below 80 "goes to the maintainer instead of being set"; "When the last package has removed its marker, the marker and the `-m` option go."
  - [03, Order](../design/03-run-stages-and-specs.md#order) and "Specs and their tests": that every `pending` marker was removed by the package that built its code, and that "the work package that builds the code deletes the throwaway model".
  - [01 T11](../design/01-testing.md#t11-the-existing-tests) and decision D62: "Package 59, the last of milestone 2, walks the list: for every kept row it names the test that holds it and checks that the test exists and passes. A kept row with no such test is a finding against its owner and holds up the close of the wave."
  - The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md), as the list it walks.

## Depends on

Every other package, 01 to 58. In particular:

- [08](08-golden-facts.md) and [13](13-tlc-parser.md): the facts' `PENDING` tuple in `tests/parse/test_facts.py`, which 13 empties.
- [21](21-java-launcher.md), [23](23-tool-store.md), [27](27-install-steps.md), [35](35-run-folders.md): the `pending` markers of `tests/stateful/` and the deletion of `reference_launcher.py`, `reference_store.py`, `reference_rundirs.py` with their `*_reference_model` tests.
- Every owner named in the inventory's notes, since each writes its rows' tests (D62).
- [52](52-integration-tests.md), [54](54-integration-job.md), [55](55-release-tooling.md), [58](58-lint-rules.md): the checks the exit criteria rest on.

## Files

Changes:

- `pyproject.toml`: `[tool.coverage.report]` gains `fail_under`, the measured figure, if it is at least 80 (Context), in place of the comment T10 left there; the `pending` line of `markers` and `-m 'not pending'` in `addopts` go, if no test carries the marker.
- `tests/parse/test_facts.py`: the `PENDING` constant and the code that applies it go, if the tuple is empty.

Creates: nothing. The report, the table of inventory rows included, is the pull request description, not a file.

Deletes: nothing else. A file this package finds that should have been deleted is reported, not deleted (Context).

Shared files: none in practice; it runs last.

## Interfaces

None.

## Tests that must pass

No new test. The closing check (Context) finds, for every kept row of the inventory, a test that exists and passes. `uv run poe test` passes with the new `fail_under`; `uv run pytest --collect-only -q -m pending` collects nothing before the marker is removed (paste the output); after the change `uv run poe test`, `uv run poe lint`, `uv run poe test-integration` (with both builds) and CI pass.

## Changelog

None.

## Context for the worker

**The closing check** (D62, [01 T11](../design/01-testing.md#t11-the-existing-tests)). Read `docs/design/preserved-behaviour-2026-11-22.md` row by row. Every row whose status is "kept, specified", "kept, not specified", or "decided (Dnn)" with a kept outcome ("kept" or "kept, changed") is a requirement; rows "changed on purpose" are not (their replacement is the section they cite). For each requirement, name the test that holds it: the file and the test or scenario, in the forms of 01 (unit, feature, integration, stateful). The owner is the one the row's note names, else the package that owns the section the note cites (the index's traceability table says which). Check that the test exists, that it tests what the row says (read it; a test of the same name that asserts something else does not count), and that it passed on the last full run (`uv run poe test`, `uv run poe test-integration` with both builds, `uv run poe test-lifeline`). Write the result as a table in the pull request: row, owner, test, result. A kept row with no such test is a finding against its owner and holds up the close of the wave: report it to the index; do not write the missing test here.

**The coverage figure** (T10). There is no `fail_under` before this package: the old tests went at the start of the wave (D62) and the figure climbed back as packages landed. Run `uv run poe test` on a clean `main` (the real-process scenarios count, through coverage's subprocess patch) and read the total, with branch coverage, from the report. Run it twice; if the two totals differ (real-process data can be lost for a reason outside tlaup, T10, Risks), use the lower and say so. If that figure is at least 80, set `fail_under` to it rounded down to a whole number. If it is below 80, set nothing: report the figure to the maintainer with the files that pull it down, as T10 says (a departure, listed in the design README); the maintainer decides.

**Removing `pending`.** Only when nothing carries it:

- `grep -rn "pending" tests/` finds no marker use, and `uv run pytest --collect-only -m pending` collects nothing;
- the facts' `PENDING` tuple (08) is empty;
- `tests/stateful/` holds no `reference_*.py` and no `*_reference_model` test.

Then the marker line, `-m 'not pending'` and the `PENDING` constant go in one commit. If any of the three is not true, report which package left it and change nothing.

**What must be gone** (check and report; do not delete):

- The old test suite, which [03](03-test-foundation.md) (03b) deleted at once (D62): nothing of 0.8.x's `tests/unit/` and `tests/integration/` is left, none of its fixtures (`mock_load_config`, `mock_cache`, `base_settings`, `java_available`, `javac_available`, `mock_github_api`, `mock_download`, `installed_v180`, `mock_tlc_env`), no `mocker` use, and `pytest-mock` is not among the development dependencies. A file of the same name written new by a package is fine; the check is that the old content is gone.
- `tests/fixtures/releases.json`, `tags.json`, `naming_dynamic/` (03b) and `tests/fixtures/naming_fixed/`, which [52](52-integration-tests.md) moved to `tests/integration/specs/`. `tests/fixtures/research/` stays: it is evidence (T3).
- The old source modules: every 0.8.x module that a package's Files listed under Deletes, for example `tlc/parser.py`, `tlc/sany.py`, `tlc/run_cache.py`, `tlc/compiler.py`, `tlc/models.py`, `tlc/formatter.py`, `tlc/components.py` (39, 40), `java/inspector.py`, `cmd/check_java.py` (46), `cmd/fetch_cache/` (45), `versioning/downloader.py` (26), `versioning/api.py` and `cache/github.py` (24, 25, 29). Collect the list from the package files' Deletes sections, then check the tree; a survivor is a missed deletion.

**The exit criteria**, as a checklist. For each, say how it was checked (the test, the CI run, or a step by hand) and the result. Nothing is built for any of them; a criterion that does not hold is a finding for the index.

Milestone 1 (line 284):

| Criterion | How to check |
| --- | --- |
| Golden-file tests pass for both TLC versions | `tests/parse/` passes with no `pending` (15's expected results, 08's facts) |
| A spec with a violated invariant shows its message and its full trace | `tlc_run.feature`'s violation scenario (39); and once by hand with `tlaup tlc` on a copy of the `Violation` golden spec, both builds, in a temporary `TLAUP_HOME` |
| `tlaup tlc Spec -- -workers 4 -deadlock` runs | 39's scenario (the logged Java command) and once by hand on a real build |
| No listed failure path prints a traceback | `errors.feature`, `tlc_errors.feature`, the closed-pipe and signal scenarios (02 X1, 14 F10) |
| A truncated download is never reported as installed | T6's short-body and mid-stream rows (26) and the `install --force` scenario (29) |

Milestone 1b (line 350):

| Criterion | How to check |
| --- | --- |
| `sany`, `pcal` and `repl` run against the pinned jar | 52's `test_tools.py` on both builds (the REPL on rolling only; v1.7.4 has none) |
| A long TLC run shows a live status on a terminal and clean line output when piped | 40's terminal scenarios and the reporter's expected files; once by hand on a real terminal |
| The command tree is reviewed and signed off | Signed off with the design (2026-11-18, decision D47); check that 48's tree test matches [23 C1](../design/23-command-layout.md#c1-command-tree) |
| Completion works in bash, zsh and fish | bash: 47's tests and 52's `test_completion.py`; zsh and fish: a hand check before the release, a maintainer action ([23 C3](../design/23-command-layout.md#c3-completion), Risks). Report it as waiting if not done. |

Milestone 2 (line 436):

| Criterion | How to check |
| --- | --- |
| A clean checkout passes unit tests with no jar installed and no writes outside temporary folders | The unit job's cells and their clean-home check (53); `uv run poe test-clean` locally |
| A pull request that breaks trace parsing fails CI | The golden tests and the integration job are required through `Test` (53, 54). Shown for good only with the ruleset of I7 in place and one throwaway pull request that breaks trace parsing; that is the maintainer's check (I5, I7). Report whether the ruleset exists. |
| A release cannot be tagged from a red commit | `scripts/release.sh` step 7 (55); `release.sh --check` on a commit whose `Test` failed, if one is at hand, else by reading the script |
| A pushed tag does not publish without the maintainer's approval | The `pypi` environment's required reviewer (L5), a maintainer action; report whether it is set |

**What to report rather than fix**: every kept inventory row without a test that holds it, with its owner; the coverage figure and the files that pull it down if it is below 80; any `pending` marker, reference model, old test, old fixture or old module left, with the package that should have removed it; every exit criterion that does not hold, or holds only after a maintainer action not yet done (I7, L5, the zsh and fish hand check, the GitHub topics of B3, the release-page backfill of L3); and any roadmap item of milestones 1, 1b and 2 still open that no package covered.

## Done when

- The pull request has the table of every kept inventory row with its test and result, and no row lacks a test (or each that does is reported to the index as a finding against its owner, which holds up the close).
- `fail_under` is the measured figure rounded down, if it is at least 80; else nothing is set and the figure is with the maintainer. The `pending` marker, its `-m` option and the facts' `PENDING` are gone, or the pull request says what keeps them.
- The other checks above are done and the pull request lists each result.
- `uv run poe lint`, `uv run ruff format --check .`, `uv run poe test`, `uv run poe test-integration` and CI pass.

## Out of scope

- Fixing a missed deletion, a failing criterion or anything found by the checks: reported to the index, which hands it to the owning package or a new one.
- The release itself, 0.9.0: the maintainer, through [55](55-release-tooling.md)'s procedure.
- Maintainer actions (I7, L5, the zsh and fish check, topics, backfill): named, not done.
- Ticking roadmap items: the maintainer's.

## Risks

- From T10: the coverage figure moves when real-process data is lost; using the lower of two runs keeps the threshold honest.
- From D62: a row whose test was never written shows only here, at the end of the wave; the fix is a small package for its owner's code, which delays the close. The inventory's notes name each owner, so the gap is one test, not a search.
- From the cut: this package is the only place that sees the whole; a missed deletion found here means a package was merged incomplete, and the fix is a new small package, not a change to a merged one.
