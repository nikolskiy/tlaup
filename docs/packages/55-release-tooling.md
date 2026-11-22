# 55. Release script, release workflow and version bump

Size: M. Suggested model: most capable. Status: ready.

## Goal

A release can only be tagged from a clean, pushed, green `main` whose lock file, version and changelog agree; the tag is annotated and pushed atomically. The release workflow builds in a read-only job, publishes to PyPI from a job that holds only the id-token permission and runs no project code, and only then creates the release page, whose text is that version's changelog section and whose files are exactly the wheel and the sdist. `poe bump` moves the version in `pyproject.toml` and `uv.lock` together, and the release guide says all of this in order.

## Covers

- Roadmap items ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this), "Release"):
  - "Harden `scripts/release.sh`: on `main`, clean tree, `HEAD` equal to `origin/main` after a fetch, ... an annotated tag (decision D21), an atomic push, and the local tag removed if the push fails. Read the version robustly." (line 398). In full.
  - "Restructure `release.yml` into three jobs: a read-only build ..., then PyPI publish with the id-token permission only, then the release page with write access and no project code. ..." (line 399). In full.
  - "Release pages: each page gets that version's changelog section as its text; backfill the existing pages from the changelog ...; PyPI's changelog link points at the GitHub releases page." (line 400). In part: new pages and the PyPI link. The backfill is a maintainer action after 0.9.0 (Context).
  - "A `poe` task around `uv version --bump`, so `pyproject.toml` and `uv.lock` move together." (line 401). In full.
  - "Before each release, refresh the lock file and let CI run before tagging." (line 403) and "Follow the version rule of decision D27 from 0.9.0 on." (line 404). In part: the steps in the release guide. Each is a step of every release, so neither item is closed by a pull request; the maintainer ticks them.
  - "Enforce ... an explicit read-only `permissions` block, `timeout-minutes` and a concurrency group in each workflow ..." (line 391). In part: the same rules for `release.yml`; `test.yml` is [53](53-ci-workflows.md).
- Design sections:
  - [30 L1](../design/30-ci-and-release.md#l1-release-script): all of it.
  - [30 L2](../design/30-ci-and-release.md#l2-release-workflow): all of it.
  - [30 L3](../design/30-ci-and-release.md#l3-release-pages): new pages (through L2) and `project.urls.Changelog`; not the backfill.
  - [30 L4](../design/30-ci-and-release.md#l4-version-bump-task): all of it.
  - [30 L6](../design/30-ci-and-release.md#l6-lock-refresh-before-a-release) and [30 L7](../design/30-ci-and-release.md#l7-version-rule): what they change in files, the release guide.
  - [30 I5](../design/30-ci-and-release.md#i5-workflow-hygiene): for `release.yml`.
  - [20 G3](../design/20-groundwork.md#g3-java-launcher), "The jar": the release build of the lifeline jar, only if [06](06-lifeline-agent.md) chose to build it per release.

## Depends on

- [53](53-ci-workflows.md): `poe check-release` and `scripts/check_wheel.py` (L1 step 8, and L2's "the wheel check of I4"); the check run named `Test` that L1 step 7 asks GitHub about; `shellcheck scripts/*.sh` in the `lint` job, which checks the new script; the pinned hashes and the way to look them up.
- [06](06-lifeline-agent.md): whether the lifeline jar is checked in (then the release build does nothing more) or built per release (then the release build job sets up Temurin 11 and runs `poe build-lifeline` before `uv build`).

Changed from the draft (53): 06 is added, for that choice.

## Files

Changes:

- `scripts/release.sh`: rewritten (L1).
- `.github/workflows/release.yml`: rewritten (L2).
- `pyproject.toml`: `project.urls.Changelog` becomes the releases page, `https://github.com/<owner>/<repo>/releases`, with the owner and repository of the `Repository` address already in the file (L3); the poe task `bump` (L4).
- `docs/contributing/releasing.md`: rewritten as the procedure (Context).

Creates:

- `scripts/changelog_section.py` (L1): plain Python, standard library only, typed for `mypy --strict`.
- `tests/unit/scripts/test_changelog_section.py`: its unit tests, on sample changelogs written by the test into a temporary folder. The script is loaded from its path (with `importlib` or as a child process of `sys.executable`), since `scripts/` is not a package.
- The bump script, if the worker writes `poe bump` as a script rather than a poe `cmd` (for example `scripts/bump.py`): it needs an argument and prints two lines, which a small script does more plainly than a poe expression.

Deletes: nothing.

Shared files: `pyproject.toml` (one URL line and one task here; [56](56-build-and-metadata.md) writes other parts of `[project]`); `release.yml` with [29](29-tool-commands.md), which changes or removes the step `uv run tlaup tools install` if it is still there when 29 runs. This package removes that step whatever form it has, since the release build's unit tests need no jar after [03](03-test-foundation.md). Nothing under `src/` changes.

## Interfaces

**`scripts/release.sh`** (L1). Stays a shell script, passes shellcheck, `set -euo pipefail`, and does these in order, stopping at the first failure with a message that says what to do:

1. `VERSION=$(uv version --short)`; `TAG="v$VERSION"`.
2. The branch is `main`; `git status --porcelain` is empty.
3. `git fetch origin main --tags`; `HEAD` equals `origin/main`.
4. `refs/tags/$TAG` exists neither locally nor in `git ls-remote --tags origin`.
5. `uv lock --check` passes and the `tlaup` entry in `uv.lock` has version `$VERSION`.
6. `uv run python scripts/changelog_section.py "$VERSION" > /dev/null` succeeds.
7. CI is green for `HEAD`: `gh api repos/{owner}/{repo}/commits/$SHA/check-runs` shows the check `Test` completed with conclusion `success`. If `gh` is missing or not logged in, the script stops and says so; it never skips the check.
8. `uv run poe check-release`.
9. `git tag -a "$TAG" -m "tlaup $VERSION"`.
10. `git push --atomic origin main "$TAG"`; on failure, `git tag -d "$TAG"` and stop.

`scripts/release.sh --check` performs steps 1 to 8 and stops, saying that nothing was tagged. The success line uses no symbol (today's ends with `✓`; [14 F6](../design/14-config-and-cli.md#f6-messages) dropped symbols from tlaup's messages, and the same plainness suits the script; stage 4).

**`scripts/changelog_section.py`** (L1, L2, L3):

```
scripts/changelog_section.py X.Y.Z
```

Prints the body of the section under the heading `## [X.Y.Z] - YYYY-MM-DD` of `CHANGELOG.md` (the repository root's, found from the script's own path) to stdout, without the heading, and exits 0. Fails with a message on stderr and a non-zero exit when the heading is missing, when it is malformed (no date, a date that is not a valid `YYYY-MM-DD`, a version in another form), when the section is empty, or when a `## [Unreleased]` section still has entries. A `## [Unreleased]` heading with nothing under it is allowed (stage 4: L1 says "with nothing left under Unreleased"; an empty heading left in place is nothing left).

**`poe bump`** (L4): `uv run poe bump patch|minor|major` runs `uv version --bump <part>`, which updates `uv.lock` too, and prints the new version and the next step: rename `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - <today>`. It does not edit the changelog and does not commit. Any other argument is refused with the three allowed values named.

**`release.yml`** (L2). Trigger: push of a tag matching `v*`. Workflow-level `permissions: contents: read`. Concurrency group `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: false` (I5). Every action pinned by full commit hash with its release in a comment.

| Job | Permissions | Timeout | Does |
| --- | --- | --- | --- |
| `build` | `contents: read` | 20 (stage 4: it runs lint, the unit tests and the build) | Checkout with `persist-credentials: false` and `fetch-depth: 0`. If 06 builds the lifeline jar per release: Temurin 11 and `uv run poe build-lifeline` before the build. Fail unless `v$(uv version --short)` equals the tag (`$GITHUB_REF_NAME`) and `git merge-base --is-ancestor "$GITHUB_SHA" origin/main`. `uv sync --locked`; `uv run poe lint`; `uv run poe test`; `uv run poe check-release` (build, `twine check`, the wheel check). `uv run python scripts/changelog_section.py "$VERSION" > release-notes.md`. Upload two artifacts with `actions/upload-artifact`: `dist`, exactly the `.whl` and the `.tar.gz`, and `release-notes`. |
| `publish` | `id-token: write` only; `environment: pypi` | 10 (stage 4) | Needs `build`. Download `dist` with `actions/download-artifact`; publish with `pypa/gh-action-pypi-publish`. No checkout, no project code. Waits for the maintainer's approval in the `pypi` environment (L5). |
| `release-page` | `contents: write` | 5 (stage 4) | Needs `publish`. Download both artifacts; then `gh release create "$GITHUB_REF_NAME" dist/*.whl dist/*.tar.gz --title "tlaup $VERSION" --notes-file release-notes.md --verify-tag`, with `GH_TOKEN: ${{ github.token }}` and `GH_REPO: ${{ github.repository }}` in the step's environment, because there is no checkout for `gh` to read the repository from. No checkout, no project code. |

`$VERSION` in the later jobs is the tag without its `v`, passed from `build` as a job output or computed from `$GITHUB_REF_NAME` in the step (no project code is needed for that). The publish action's `verbose: true` of today may stay.

The pins research 29 found on 2026-11-19, to be looked up again on the day (53 gives the method): `pypa/gh-action-pypi-publish` `7245906fb61fa33a13554f9d5fb856fe61758086` (v1.14.3; today's `release/v1` is a branch and can move, so this pin is the largest gain), `actions/download-artifact` `9000827ccba6bdab643e8b6fd33ac0654aef8333` (v8.0.2), `actions/upload-artifact` `cf430e030ddbb5b0abf93d22962f4752f3646cd9` (v7.0.2), and the four of 53's table. `softprops/action-gh-release` and `actions/setup-python` are no longer used.

Consumes: `poe check-release`, `poe lint`, `poe test` (53, 03); `poe build-lifeline` (06), if needed.

## Tests that must pass

- `tests/unit/scripts/test_changelog_section.py`, plain pytest in the default suite (L1): a good heading prints its section and exits 0; a missing heading, a malformed heading (no date; a date such as `2026-13-40`; `## [0.9] - ...` for `0.9.0`), an empty section, and entries left under `## [Unreleased]` each exit non-zero with a message; an empty `## [Unreleased]` heading is allowed; the printed text has no heading line and stops before the next `## [` heading.
- shellcheck on the new `release.sh` (the `lint` job of 53).
- `scripts/release.sh --check` run once by hand on a clean `main` (L1: "run by hand before the first release"); the pull request pastes its output, which stops before tagging. It will fail at step 6 or 7 on an unreleased `main`, which is expected; say at which step and why.
- `uv run poe bump patch` run once on a scratch branch, showing `pyproject.toml` and `uv.lock` both changed and nothing else; the branch is thrown away.
- The workflow (L2, Tests): the tag and ancestry checks are tried once on a throwaway tag in a fork or with `act`; if neither is practical, the first real release is the test and the maintainer watches it. Say in the pull request which was done. Never push a `v*` tag to this repository to test: the tag ruleset forbids moving or deleting one, so a test tag would burn a version number.

## Changelog

None. Release tooling is not something a user of `tlaup` runs.

## Context for the worker

**The release guide**, `docs/contributing/releasing.md`, rewritten as the procedure, in this order:

1. Refresh the lock file: `uv lock --upgrade`, commit, push (through a pull request, once the ruleset of I7 exists), and wait for CI to be green (L6). The weekly `deps-newest` run ([53](53-ci-workflows.md)) means the refresh is rarely a surprise.
2. Choose the part by the version rule ([conventions](../contributing/conventions.md#compatibility-and-versions), D27: from 0.9.0 on, minor versions carry breaking changes and features, patch versions only fixes) and run `uv run poe bump <part>` (L4, L7).
3. Rename `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD`; commit; push; wait for green.
4. `scripts/release.sh --check`, then `scripts/release.sh` (L1).
5. The release workflow builds, waits for the maintainer's approval in the `pypi` environment, publishes, and then creates the release page with the changelog section as its text (L2, L5).

Keep its "Repository rules" section and add what this milestone sets: the ruleset on `main` (I7) and the `pypi` environment's required reviewer (L5), each worded as what holds once the maintainer has set it, so the guide is not wrong before that.

**What the old workflow got wrong, and the reason for each part of the new one** (L2, roadmap): one job built, tested and created the page with write access, and then published; `files: dist/*` put a stray `default.gitignore` on the 0.8.2 page; the release action came from a third party; `release/v1` was a moving branch. Publishing before the page means a page never announces a version that is not on PyPI. The jobs that hold a sensitive permission run no project code (roadmap, "Keep").

**The uv cache in the release workflow.** The design says nothing about caching here. A cache restored into the build job could have been written by another run; since the release workflow runs a few times a year and the cache saves seconds, leave `setup-uv`'s cache off in `release.yml` (stage 4's recommendation; say so in the pull request if you keep it on, and why).

**L3's backfill is a maintainer action, not work for this package.** The design: "Backfill: a maintainer action after 0.9.0, as `gh release edit vX.Y.Z --notes-file <(scripts/changelog_section.py X.Y.Z)` for each tag that has a page"; which tags have pages was not checked (the roadmap notes probably only 0.8.2), and whether older tags get pages is the maintainer's decision then. Put the command in the release guide as an optional step after the first release, and in the pull request description.

**Maintainer actions this package touches** (name them in the pull request; do not do them):

- L5: in the repository settings, environment `pypi`: required reviewers, the maintainer; "allow administrators to bypass" off; deployment branches and tags `v*` (in place since 2026-11-14). Its record is the roadmap item, ticked when done. Until it is set, a pushed tag publishes without approval, and the milestone's exit criterion "a pushed tag does not publish without the maintainer's approval" is not met.
- I7: the ruleset on `main`, which waits on the `Test` check name of [53](53-ci-workflows.md); 53's pull request carries the `gh api` command.
- The roadmap's "Confirm two-factor authentication on the GitHub and PyPI accounts": with trusted publishing, account security is the remaining risk.

**Reading the version.** `uv version --short` replaces today's `grep | sed` on `pyproject.toml` (the roadmap's "Read the version robustly").

**State of `main` when this starts.** `release.sh` checks only that the tag is absent locally and that the changelog mentions the version, makes a lightweight tag and pushes non-atomically. `release.yml` has two jobs: `build-release` with `contents: write` (setup-python, Java 17, `uv run tlaup tools install` or what 29 made of it, lint, tests, build, upload, `softprops/action-gh-release` with `generate_release_notes` and `files: dist/*`), then `pypi-publish`. `project.urls.Changelog` points at `CHANGELOG.md` on `main`.

## Done when

- The new `release.sh`, `release.yml`, `changelog_section.py` and `bump` are in; the unit tests pass; shellcheck passes in the `lint` job.
- `release.sh --check` was run once and its output is in the pull request.
- Every action in `release.yml` is pinned by hash; `publish` has `id-token: write` only and no checkout; `release-page` has no checkout; the build job's checkout has `persist-credentials: false`.
- The release guide is the procedure above; the pull request lists the maintainer actions (L5, I7, the backfill, two-factor authentication).
- `uv run poe lint`, `uv run ruff format --check .` and `uv run poe test` pass; CI is green.

## Out of scope

- `test.yml`, `poe check-release` and `scripts/check_wheel.py`: [53](53-ci-workflows.md).
- The repository settings (L5, I7) and the backfill of old pages (L3): maintainer actions.
- The lifeline jar's build recipe: [06](06-lifeline-agent.md).
- Changing a changelog entry or the version itself: the first release does that, following the guide.
- The documentation track's "Changelog checks: CI warns when code changes without a changelog change" (roadmap line 506): not designed; not built here.

## Risks

- From L1: the script cannot be exercised end to end without making a release; `--check` covers steps 1 to 8.
- From L2: the tag and ancestry checks may be seen for the first time on the real 0.9.0 release.
- From the cut: L1 step 7 reads check runs named `Test`; if 53 or a later change renames the job, the script stops every release. The name is stated in 53 and here, and I7's ruleset requires the same name.
- Until L5 is set, the `pypi` environment does not wait for approval.
