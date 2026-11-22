# 01. Format the tree and enforce it

Size: S. Suggested model: mid-tier. Status: waiting on question `format-markdown` of the index (one configuration line depends on it; everything else is ready).

## Goal

Every Python file in the repository is in `ruff format` form, in one commit that holds nothing else, and from then on an unformatted file fails locally (pre-commit) and in the existing test workflow. Every later package branches off after this one.

## Covers

- Roadmap items:
  - "Enforce `ruff format --check`; `uv sync --locked`; an explicit read-only `permissions` block ..." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)), in part: the format check only. `--locked`, permissions, timeouts, concurrency, `shellcheck` and the final `Test` job are package 54.
  - "Pre-commit: move the test hook to pre-push; add a format hook; run mypy on the whole project ..." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)), in part: the format hook only. The rest is package 57.
- Design sections:
  - [30 I5](../design/30-ci-and-release.md#i5-workflow-hygiene), the first bullet ("Format first") only. The other bullets are package 54.
  - [30 H1](../design/30-ci-and-release.md#h1-pre-commit-hooks), the `ruff-format` hook only. The `pytest` hook's stage, the `mypy` hook and `poe install-hooks` are package 57; the `no-typed-tool-output` hook is package [03](03-test-foundation.md).
  - [00, order of work](../design/00-overview.md#order-of-work), step 1.

## Depends on

Nothing.

## Files

Changes, in the format commit (measured on the tree of 2026-11-21 with the locked ruff 0.17.5; run the formatter and take what it changes, the list is for orientation):

- `src/tlaup/cmd/tlc.py`, `src/tlaup/config/loader.py`, `src/tlaup/tlc/runner.py`
- `tests/unit/cmd/test_tlc_cmd.py`, `tests/unit/test_cli.py`, `tests/unit/test_tlc_show_command.py`, `tests/unit/tlc/test_runner.py`, `tests/unit/tools/test_list.py`

Eight Python files; the other Python files are already in the formatter's form.

Changes, in the commits around it:

- `pyproject.toml`: the line that keeps the formatter away from Markdown, if the question is answered as recommended (see Context). `extend-exclude = ["tests/fixtures/research"]` stays as it is. The task `format = "ruff format ."` exists already; no task is added.
- `.pre-commit-config.yaml`: one new local hook directly after the hook `ruff`:

  ```yaml
        - id: ruff-format
          name: ruff format
          entry: uv run ruff format --check --force-exclude
          language: system
          types: [python]
          require_serial: true
  ```

- `.github/workflows/test.yml`: one step after "Run linting" (`uv run poe lint`) that runs `uv run ruff format --check .`. Nothing else in the workflow changes here.
- `docs/contributing/development.md`: the section "Formatting" (it says formatting is not enforced and that files must not be reformatted) is removed. The command list may gain one line for `uv run poe format`.

Creates:

- `.git-blame-ignore-revs`: one comment line and the full hash of the format commit.

Deletes: nothing.

No other package runs beside this one, so there is no shared file. Package 53 rewrites `test.yml` later and keeps the check in its `lint` job; package 57 edits the hooks around the new one.

## Interfaces

None. Provides, for every later package: a tree in which `uv run ruff format --check .` passes, so a worker formats what they touch and the diff holds only their change.

## Tests that must pass

No test is added, deleted or rewritten. The checks are:

- `uv run ruff format --check .` exits 0.
- `uv run poe lint` and `uv run poe test` pass exactly as before the format commit. The formatter does not change what the code does, so the number of passing tests is the same (207 collected items in `tests/unit` today; `tests/stateful` skips itself until Hypothesis is installed).
- The format commit is reproducible: on its parent, `uv run ruff format .` gives exactly its tree.
- The new hook fails on a deliberately misformatted staged file and passes after `uv run poe format` (tried by hand once, said in the pull request).

## Changelog

None. Nothing a user sees changes.

## Context for the worker

Why first ([00](../design/00-overview.md#order-of-work)): every later package would otherwise conflict with a tree-wide reformat. That is also why this is the only package that may touch files it has no other reason to touch.

**The commits.** The design asks for one commit, `style: apply ruff format`, that "formats the whole tree and nothing else". A commit cannot name its own hash, and the enforcement is not formatting, so the pull request has up to three commits, in this order:

1. If needed, the configuration line about Markdown (below), so that the format commit is the formatter's output and nothing else.
2. `style: apply ruff format`: exactly what `uv run ruff format .` changes.
3. The enforcement: the hook, the workflow step, the development guide, and `.git-blame-ignore-revs` holding the hash of commit 2.

**The hash must survive the merge.** `.git-blame-ignore-revs` is only right if commit 2 reaches `main` with the hash written in the file. A squash merge or a rebase merge gives it a new hash. Say in the pull request that it must be merged by fast-forward or with a merge commit; if it was merged another way, the fix is one follow-up commit that corrects the hash. GitHub's blame view reads the file by itself; locally it is `git config blame.ignoreRevsFile .git-blame-ignore-revs`.

**The locked ruff also formats Python code blocks in Markdown** (found while cutting this package; the design did not know). With ruff 0.17.5, `ruff format --check .` reports 16 files today: the eight Python files above, seven design documents (`docs/design/01-testing.md`, `10-parser.md`, `11-runner.md`, `14-config-and-cli.md`, `20-groundwork.md`, `21-other-tools.md`, `22-reporters.md`) and a package file under `docs/packages/`. The design documents write signatures in a compact form on purpose (several fields on one line, comments aligned in a column), and the formatter would rewrite them. Both of these were tried and leave exactly the eight Python files: `[tool.ruff.format] exclude = ["*.md"]`, and adding `"docs"` to `extend-exclude`. This is question `format-markdown`:

- Recommended: the formatter covers Python files only (`exclude = ["*.md"]` under `[tool.ruff.format]`). The design documents are signed off and stay byte for byte; "the whole tree" in I5 is read as "every Python file".
- The other answer: Markdown is formatted too. Then the format commit also rewrites the code blocks of the documents above and of every package file, and every later documentation change must pass the formatter.

Whichever is chosen, `types: [python]` on the hook means pre-commit never hands it a Markdown file; the workflow step is what would check Markdown.

**`tests/fixtures/research` is not formatted.** It holds helper scripts kept as evidence of the investigations, and `extend-exclude` in `[tool.ruff]` keeps both `ruff check` and `ruff format` out of it. pre-commit passes file names explicitly, and ruff ignores excludes for explicitly named files unless `--force-exclude` is given; that is why the hook has the flag (the existing `ruff` hook has it for the same reason). Do not format that folder and do not remove the exclude.

**After formatting, run the linter again.** The formatter can leave a line longer than 120 characters where it cannot split it, and `ruff check` then reports it. `uv run ruff check .` passes on today's tree; if it does not pass after commit 2, the fix goes into commit 3 and the pull request says what it was.

**Not `poe lint`.** The design keeps the format check as its own command beside `uv run poe lint` ([30 I2](../design/30-ci-and-release.md#i2-unit-job): "`uv run poe lint` and `uv run ruff format --check .`"). Do not add it to the `lint` task.

Decisions this rests on: D6 (one release; the order of work), D14 does not apply (nothing user-visible).

State of `main` when this starts: release 0.8.x code and tests, the design documents, `specs/`, `tests/stateful/` and `docs/packages/`. The test workflow has one job; pre-commit runs `ruff check`, bandit, mypy and pytest at commit time.

The repository's rules for commits hold as always ([conventions](../contributing/conventions.md)): Conventional Commits, no attribution trailers, commit and push only when the maintainer asks.

## Done when

- `uv run ruff format --check .` exits 0 on the branch, and CI runs it and is green.
- The format commit holds only formatter output and is reproducible from its parent.
- The hook `ruff-format` is in `.pre-commit-config.yaml` after `ruff`; `uv run poe check` passes.
- `docs/contributing/development.md` no longer says formatting is not enforced.
- `.git-blame-ignore-revs` names the format commit, and the pull request says how it must be merged.
- `uv run poe lint` and `uv run poe test` pass.

## Out of scope

- The rest of I5 (`--locked`, permissions, timeouts, concurrency, `shellcheck`, the `Test` job) and the `lint` job itself: package 54.
- The rest of H1 (test hook at pre-push, mypy on the whole project, both hook types installed): package 57.
- Running pre-commit in CI (I6): package 54.
- Any change to what the code does, to a lint rule, or to a file the formatter does not touch.

## Risks

- From the cut: the Markdown finding above. If the question is answered late, this package blocks every other one; the recommended answer changes one line and can be reversed later by one more format commit.
- A merge that rewrites the format commit's hash leaves a wrong line in `.git-blame-ignore-revs`; harmless, and fixed by one commit.
- Work that branched off before this package (none is planned) would conflict with it in the eight files.
- A newer ruff may format differently. The lock file pins 0.17.5, so the check is stable until the lock moves; the monthly dependency update (package 56) then carries a small format commit of its own.
