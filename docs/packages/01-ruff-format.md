# 01. Format the tree and enforce it

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

Every Python file in the repository, and every Python code block in its Markdown files, is in `ruff format` form, in one commit that holds nothing else, and from then on an unformatted file fails locally (pre-commit) and in the existing test workflow. Every later package branches off after this one.

## Covers

- Roadmap items:
  - "Enforce `ruff format --check`; `uv sync --locked`; an explicit read-only `permissions` block ..." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)), in part: the format check only. `--locked`, permissions, timeouts, concurrency, `shellcheck` and the final `Test` job are package 53.
  - "Pre-commit: move the test hook to pre-push; add a format hook; run mypy on the whole project ..." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)), in part: the format hook only. The rest is package 57.
- Design sections:
  - [30 I5](../design/30-ci-and-release.md#i5-workflow-hygiene), the first bullet ("Format first") only, as revised for question Q1: the commit and the checks cover the Python code blocks in Markdown too. The other bullets are package 53.
  - [30 H1](../design/30-ci-and-release.md#h1-pre-commit-hooks), the `ruff-format` hook only, with its `types_or: [python, pyi, markdown]`. The `pytest` hook's stage, the `mypy` hook and `poe install-hooks` are package 57; the `no-typed-tool-output` hook is package [03](03-test-foundation.md).
  - [00, order of work](../design/00-overview.md#order-of-work), step 1.

## Depends on

Nothing.

## Files

Changes, in the format commit (measured on the tree of 2026-11-24 with the locked ruff 0.17.5; run the formatter and take what it changes, the list is for orientation):

- Eight Python files: `src/tlaup/cmd/tlc.py`, `src/tlaup/config/loader.py`, `src/tlaup/tlc/runner.py`, `tests/unit/cmd/test_tlc_cmd.py`, `tests/unit/test_cli.py`, `tests/unit/test_tlc_show_command.py`, `tests/unit/tlc/test_runner.py`, `tests/unit/tools/test_list.py`. The five test files are deleted with the rest of the old suite in 03b ([03](03-test-foundation.md), decision D62); they are formatted all the same, since the commit is the formatter's output and nothing else.
- The Python code blocks of Markdown files: the design documents and package files that `uv run ruff format --check .` names on the day of the commit. Documents change while the packages are reviewed, so no list or count is given here (finding F8 of the [second review](review-2026-11-24.md)); every other file is already in the formatter's form.

Changes, in the commits around it:

- `pyproject.toml`: unchanged. There is no exclude for Markdown (Q1), `extend-exclude = ["tests/fixtures/research"]` stays as it is, and the task `format = "ruff format ."` exists already.
- `.pre-commit-config.yaml`: one new local hook directly after the hook `ruff` ([30 H1](../design/30-ci-and-release.md#h1-pre-commit-hooks)):

  ```yaml
        - id: ruff-format
          name: ruff format
          entry: uv run ruff format --check --force-exclude
          language: system
          types_or: [python, pyi, markdown]
          require_serial: true
  ```

- `.github/workflows/test.yml`: one step after "Run linting" (`uv run poe lint`) that runs `uv run ruff format --check .`. Nothing else in the workflow changes here.
- `docs/contributing/development.md`: the section "Formatting" (it says formatting is not enforced and that files must not be reformatted) is removed. The command list may gain one line for `uv run poe format`.

Creates:

- `.git-blame-ignore-revs`: one comment line and the full hash of the format commit.

Deletes: nothing.

No other package runs beside this one, so there is no shared file. Package [53](53-ci-workflows.md) rewrites `test.yml` later and keeps the check in its `lint` job; package [57](57-repo-hygiene.md) edits the hooks around the new one.

## Interfaces

None. Provides, for every later package: a tree in which `uv run ruff format --check .` passes, so a worker formats what they touch, Python code blocks in Markdown included, and the diff holds only their change.

## Tests that must pass

No test is added, deleted or rewritten. The checks are:

- `uv run ruff format --check .` exits 0.
- `uv run poe lint` and `uv run poe test` pass exactly as before the format commit. The formatter does not change what the code does, so the number of passing tests is the same (207 collected items in `tests/unit` today; `tests/stateful` skips itself until Hypothesis is installed).
- The format commit is reproducible: on its parent, `uv run ruff format .` gives exactly its tree.
- The new hook fails on a deliberately misformatted staged Python file, and on a staged Markdown file with a misformatted Python code block, and passes after `uv run poe format` (tried by hand once for each, said in the pull request).

## Changelog

None. Nothing a user sees changes.

## Context for the worker

Why first ([00](../design/00-overview.md#order-of-work)): every later package would otherwise conflict with a tree-wide reformat. That is also why this is the only package that may touch files it has no other reason to touch.

**The commits.** The design asks for one commit, `style: apply ruff format`, that "formats the whole tree and nothing else". A commit cannot name its own hash, and the enforcement is not formatting, so the pull request has two commits, in this order:

1. `style: apply ruff format`: exactly what `uv run ruff format .` changes, Markdown included.
2. The enforcement: the hook, the workflow step, the development guide, and `.git-blame-ignore-revs` holding the hash of commit 1.

**The hash must survive the merge.** `.git-blame-ignore-revs` is only right if commit 1 reaches `main` with the hash written in the file. A squash merge or a rebase merge gives it a new hash. Say in the pull request that it must be merged by fast-forward or with a merge commit; if it was merged another way, the fix is one follow-up commit that corrects the hash. GitHub's blame view reads the file by itself; locally it is `git config blame.ignoreRevsFile .git-blame-ignore-revs`.

**The locked ruff also formats Python code blocks in Markdown** (found while cutting this package; settled as question Q1, [30 I5](../design/30-ci-and-release.md#i5-workflow-hygiene) and H1 now say so). The design documents and the package files write signatures in a compact form in places (several fields on one line, comments aligned in a column); the formatter rewrites those blocks, and that is allowed: the blocks are code, and one format for all code is the point. So there is no exclude for Markdown, the format commit rewrites the blocks, and from then on every documentation change passes the formatter like a code change. On 2026-11-24 the check ran over every Markdown file with no error, so no block needs a hand edit first. With `types_or` naming `markdown`, pre-commit hands a staged Markdown file to the hook, so a staged document is checked as the workflow step checks it.

**`tests/fixtures/research` is not formatted.** It holds helper scripts kept as evidence of the investigations, and `extend-exclude` in `[tool.ruff]` keeps both `ruff check` and `ruff format` out of it. pre-commit passes file names explicitly, and ruff ignores excludes for explicitly named files unless `--force-exclude` is given; that is why the hook has the flag (the existing `ruff` hook has it for the same reason). Do not format that folder and do not remove the exclude.

**After formatting, run the linter again.** The formatter can leave a line longer than 120 characters where it cannot split it, and `ruff check` then reports it. `uv run ruff check .` passes on today's tree; if it does not pass after commit 1, the fix goes into commit 2 and the pull request says what it was.

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

- The rest of I5 (`--locked`, permissions, timeouts, concurrency, `shellcheck`, the `Test` job) and the `lint` job itself: package 53.
- The rest of H1 (test hook at pre-push, mypy on the whole project, both hook types installed): package 57.
- Running pre-commit in CI (I6): package 53.
- Any change to what the code does, to a lint rule, or to a file the formatter does not touch.

## Risks

- From the cut: formatting Markdown makes the format check part of every documentation change. A document that changes between this package and the next format run only fails the check if its Python blocks are not in form, which the hook catches at commit time.
- A merge that rewrites the format commit's hash leaves a wrong line in `.git-blame-ignore-revs`; harmless, and fixed by one commit.
- Work that branched off before this package (none is planned) would conflict with it in the eight files.
- A newer ruff may format differently. The lock file pins 0.17.5, so the check is stable until the lock moves; the monthly dependency update (package 56) then carries a small format commit of its own.
