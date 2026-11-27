# Releasing

A release is cut from `main` in this order. Each step says what it checks; stop at the first one that fails.

1. **Refresh the lock file.** Run `uv lock --upgrade`, commit, push (through a pull request once the ruleset on `main` is set), and wait for CI to be green. The weekly `deps-newest` run has usually shown already whether the newest versions work.
2. **Bump the version.** Choose the part by the version rule in [conventions](conventions.md#compatibility-and-versions): from 0.9.0 on, a minor version carries breaking changes and features, a patch version only fixes. Run `uv run poe bump patch`, `minor` or `major`. It moves the version in `pyproject.toml` and `uv.lock` together and prints the new version; it does not touch the changelog and does not commit.
3. **Date the changelog.** Rename `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD`, with today's date; an empty `## [Unreleased]` heading above it may stay. `uv run python scripts/changelog_section.py X.Y.Z` prints the section the release page will show. Commit, push, and wait for CI to be green.
4. **Tag.** Run `scripts/release.sh --check`, then `scripts/release.sh`. Both need `gh` logged in. The script stops at the first check that fails and says what to do:
   1. reads the version with `uv version --short`;
   2. the branch is `main` and the working tree is clean;
   3. after `git fetch origin main --tags`, `HEAD` is `origin/main`;
   4. the tag `vX.Y.Z` exists neither locally nor on `origin`;
   5. `uv lock --check` passes and `uv.lock` has the same version;
   6. `CHANGELOG.md` has a dated section for the version, and nothing is left under `## [Unreleased]`;
   7. the check `Test` of GitHub Actions completed with success on `HEAD`;
   8. `uv run poe check-release` passes;
   9. it makes the annotated tag `vX.Y.Z`;
   10. it pushes `main` and the tag in one atomic push, and deletes the local tag if the push fails.

   `--check` runs steps 1 to 8 and tags nothing.
5. **Publish.** The tag starts `.github/workflows/release.yml`, in three jobs:
   - `build`, with read access only, fails unless the tag is `v` plus the project version and the commit is on `main`; then lint, the unit tests, `poe check-release`, and the changelog section written to `release-notes.md`. It uploads the wheel and the sdist (and nothing else) and the notes.
   - `publish` waits for the maintainer's approval in the `pypi` environment, then publishes the wheel and the sdist to PyPI by trusted publishing. It holds only the id-token permission and runs no project code.
   - `release-page` then creates the GitHub release page, with the changelog section as its text and the wheel and the sdist as its files. It runs no project code either.

   Watch the run. If `build` fails, nothing was published: fix `main` and release the next version, since the tag cannot be moved or deleted. If `publish` succeeded and `release-page` failed, the version is on PyPI; re-run the failed job.

Optional, after the first release made this way: give the older release pages their changelog sections, one command per tag that has a page, for example `gh release edit vX.Y.Z --notes-file <(uv run python scripts/changelog_section.py X.Y.Z)`. Which older tags have pages, and whether those without get one, is the maintainer's choice.

## Repository rules

`main` cannot be deleted or force-pushed; `v*` tags cannot be moved or deleted by anyone, so a bad tag means a new version number; the `pypi` environment deploys only from `v*` tags.

Once the maintainer has set them:

- The ruleset on `main` takes changes only through pull requests whose `Test` check passed; the maintainer can bypass it.
- The `pypi` environment has the maintainer as its required reviewer, with administrator bypass off, so a pushed tag does not publish until the maintainer approves the `publish` job.
