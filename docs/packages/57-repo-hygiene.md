# 57. Repository hygiene

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

The test hook runs at push time and not on every commit, mypy checks the whole project from its hook, both hook types install with one task; `poe clean` removes every build and coverage leftover on any system; `.gitignore` covers the coverage and environment files; one rule ties `.python-version`, the type checker and linter targets, the classifiers and the CI matrix together, with a test that fails when they drift; and `SECURITY.md` says how to report a vulnerability.

## Covers

- Roadmap items ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this), "Repository hygiene"):
  - "Pre-commit: move the test hook to pre-push; add a format hook; run mypy on the whole project instead of on staged files." (line 418). In full, with [01](01-ruff-format.md), which added the format hook.
  - "`poe clean` also removes `build` and the egg-info folder ...; add `htmlcov/`, `coverage.xml`, `.direnv/` and editor folders to `.gitignore`." (line 419). In full.
  - "One story for Python versions: `.python-version`, the CI matrix, the classifiers and the mypy and ruff targets agree, and every advertised version is tested." (line 420). In full, with [53](53-ci-workflows.md) (the matrix) and [56](56-build-and-metadata.md) (the classifiers).
  - "A two-line `SECURITY.md` pointing at GitHub private vulnerability reporting ..." (line 421). In full.
  - "Run the pre-commit hooks in CI, without the test hook ..." (line 392). In part: removing the temporary `SKIP: pytest` that 53 put on the CI step.
- Design sections:
  - [30 H1](../design/30-ci-and-release.md#h1-pre-commit-hooks): the `pytest` hook's stage, the `mypy` hook, `poe install-hooks`. The `ruff-format` hook is [01](01-ruff-format.md)'s and the `no-typed-tool-output` hook [03](03-test-foundation.md)'s; both exist when this starts.
  - [30 H2](../design/30-ci-and-release.md#h2-clean-task-and-gitignore): all of it.
  - [30 H3](../design/30-ci-and-release.md#h3-python-versions): all of it except the classifier list itself (56) and the matrix itself (53).
  - [30 H4](../design/30-ci-and-release.md#h4-security-policy): all of it.

## Depends on

- [03](03-test-foundation.md): the pre-commit configuration with 03's hooks, and `.coverage.*` in `.gitignore`.
- [53](53-ci-workflows.md): the `unit` matrix in `test.yml`, which the H3 test reads, and the `SKIP: pytest` line on the `lint` job's pre-commit step, which this package removes.
- [56](56-build-and-metadata.md): the classifiers (3.11 and the newest tested version), which the H3 test reads.

Changed from the draft (03): 53 and 56 are added. The H3 test asserts that the matrix, the classifiers and `.python-version` agree, so it can only be written once the first two are in their final form; and H1's stage change is what lets 53's skip go, so the two belong in one pull request.

## Files

Changes:

- `.pre-commit-config.yaml` (H1): the `pytest` hook gets `stages: [pre-push]`; the `mypy` hook gets `entry: uv run mypy .` and `pass_filenames: false`, and loses `exclude: ^tests/`, since mypy's own `exclude` in `pyproject.toml` now decides what is checked; it keeps `types: [python]`, so it runs whenever a Python file is staged. Nothing else in the file.
- `.github/workflows/test.yml`: the `SKIP: pytest` line, and its comment, on the `lint` job's pre-commit step go (I6: "After H1 moves the test hook to the pre-push stage, that excludes it without a skip list"). Nothing else in the file.
- `pyproject.toml`: `install-hooks = "pre-commit install --install-hooks -t pre-commit -t pre-push"`; `clean` becomes a Python task (H2; below).
- `.gitignore` (H2): adds `htmlcov/`, `coverage.xml`, `.direnv/`. `.hypothesis/`, `.idea/` and `.vscode/` are there already (checked on 2026-11-21), and 03 added `.coverage.*`.
- `.python-version` (H3): `3.11` (was `3.13`).
- `docs/contributing/development.md`: one line each, in the commands list or a short section: hooks install with `uv run poe install-hooks` (both types; the tests run at `git push`); local development uses Python 3.11, the lowest supported, and why (H3).

Creates:

- `scripts/clean.py`, if the worker writes `clean` as a script rather than a poe `script` task calling a function (either is fine; H2 says "a small Python task (not `rm -rf`, so it works on Windows)").
- `tests/unit/test_python_versions.py` (H3).
- `SECURITY.md` (H4).

Deletes: nothing.

Shared files: `.pre-commit-config.yaml` with [58](58-lint-rules.md) (a new hook) and [59](59-closing.md) (may remove `no-new-mocker`); `test.yml` with [54](54-integration-job.md) (another job); `pyproject.toml` with 53, 55, 56 (other entries). Nothing under `src/` changes.

## Interfaces

**`poe clean`** (H2): removes `dist/`, `build/`, `src/*.egg-info/`, `.coverage`, `htmlcov/`, `coverage.xml`, and also the `.coverage.*` files that coverage writes per process with `parallel = true` ([01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings); H2 predates that setting, so stage 4 adds them to the list). Each only if present; nothing else. Uses `pathlib` and `shutil.rmtree`, from the repository root found from the file's own path, so it works from any folder and on Windows. [53](53-ci-workflows.md)'s `check-release` starts with it.

**The H3 rule**: the lowest supported version is the target, and the edges are tested.

| Place | Value |
| --- | --- |
| `requires-python` | `>=3.11` |
| ruff `target-version`, mypy `python_version` | `py311`, `3.11` (already so) |
| `.python-version` | `3.11` |
| CI `unit` matrix ([53](53-ci-workflows.md)) | 3.11 and the newest |
| Classifiers ([56](56-build-and-metadata.md)) | 3.11 and the newest, nothing in between |

**`tests/unit/test_python_versions.py`**, plain pytest, in the default suite. It reads `pyproject.toml` (`tomllib`), `.python-version` and `.github/workflows/test.yml` (`yaml`, a runtime dependency already), found from the test file's own path, and asserts:

- `.python-version`, ruff's `target-version`, mypy's `python_version` and the lower bound of `requires-python` all name the same version;
- the set of `Programming Language :: Python :: 3.N` classifiers equals the set of Python versions in the `unit` job's matrix;
- the lowest of that set is the version above.

So adding a classifier without a matrix cell, or a cell without a classifier, fails. Each assertion's message names the two places that disagree.

**`SECURITY.md`** (H4): two lines in substance. Report a vulnerability through GitHub's private vulnerability reporting (the "Report a vulnerability" button on the repository's Security tab; on since 2026-11-14). Only the latest release is supported. No email address: the `no-email-addresses` hook would refuse one, rightly.

## Tests that must pass

- `tests/unit/test_python_versions.py`, plain pytest: passes on the repository; fails when given a matrix with one more version than the classifiers (the test builds that case from the parsed data in a second test, so the comparison can be seen failing, T12 rule 6).
- `uv run poe install-hooks` installs both hook types (`.git/hooks/pre-commit` and `.git/hooks/pre-push` exist afterwards; run once, say so).
- `uv run pre-commit run --all-files --hook-stage pre-commit` does not run the `pytest` hook; `uv run pre-commit run --all-files --hook-stage pre-push` does.
- `uv run poe clean` removes a `build/lib/` and an `src/tlaup.egg-info/` made for the purpose, and leaves everything else (tried once by hand; say so).
- CI: the `lint` job passes without the skip.

No old test file changes.

## Changelog

None. Nothing a user of `tlaup` sees changes.

## Context for the worker

**Why the test hook moves** (H1). A commit should not wait for the whole suite; a push should not reach CI with a broken one. CI runs the hooks without it (I6), and the unit job runs the suite anyway.

**Why mypy runs on the whole project** (H1). On staged files only, mypy checks a module without the modules it imports from other files, and misses errors a change causes elsewhere. `uv run mypy .` reads `[tool.mypy]` in `pyproject.toml`, which today excludes `build` and `tests/`. [58](58-lint-rules.md) narrows that exclude so that `tests/fakes/` is checked (I8); leave the exclude alone here.

**Why `.python-version` moves to 3.11** (H3). Local work then catches the use of anything newer: syntax, which ruff's target also catches, and the standard library, which it does not (`os.process_cpu_count`, new in 3.13, is the example the stage 3 review found in the design). `uv` downloads 3.11 on a machine that lacks it. The CI `lint` and `deps-newest` jobs follow the file too, so after this they run on 3.11. Two consequences the design lists as its own choices: local development moves from 3.13 to 3.11, and the classifiers between the two tested edges are no longer advertised, though `requires-python` still admits those versions.

**If 53's matrix fell back** from 3.15 to 3.14 (I2, Risks), the test reads whatever the matrix and the classifiers say; it only demands that they agree.

**State of `main` when this starts.** `.pre-commit-config.yaml` has the hooks of today plus 01's `ruff-format`, 03's `no-typed-tool-output`, `no-patching-own-code` and `no-new-mocker`; the `pytest` hook has no `stages`; the `mypy` hook passes file names and excludes `^tests/`. `poe clean` is `rm -rf dist`; `poe install-hooks` installs the pre-commit type only. `.python-version` says `3.13`. `test.yml` is 53's, with `SKIP: pytest` on the pre-commit step.

## Done when

- The hook, task, ignore-file and version changes above are in; `SECURITY.md` exists.
- The tests above pass; `uv run poe lint`, `uv run ruff format --check .` and `uv run poe test` pass on Python 3.11 locally.
- CI is green, the `lint` job without `SKIP`.

## Out of scope

- The format hook: [01](01-ruff-format.md). The `no-typed-tool-output` and monkeypatch hooks: [03](03-test-foundation.md).
- The classifiers, keywords and other metadata: [56](56-build-and-metadata.md). The matrix: [53](53-ci-workflows.md).
- mypy on `tests/fakes/` and the lint rule groups: [58](58-lint-rules.md). mypy on the rest of `tests/` stays off in this wave (I8; milestone 5).
- Testing every Python from 3.11 up: rejected (H3).

## Risks

- From H3: a contributor on a machine without 3.11 waits for a download the first time.
- From the cut: 53 and 56 each fix one half of what the H3 test compares; if either changes later (a new newest Python), the same pull request must change the other, and this test is what says so.
- A slow pre-push hook may tempt `--no-verify`; CI's unit job is the backstop.
