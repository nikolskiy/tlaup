# Releasing

1. Set the version: `uv version X.Y.Z`. Choose the part by the version rule in [conventions](conventions.md#compatibility-and-versions).
2. Rename `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD`.
3. Run `uv run poe check-release` and the tests; commit on `main`.
4. Run `scripts/release.sh` from a clean `main`. It checks the changelog entry, tags `vX.Y.Z` and pushes `main` and the tag.
5. `.github/workflows/release.yml` builds, creates the GitHub Release and publishes to PyPI through trusted publishing (environment `pypi`).

## Repository rules

`main` cannot be deleted or force-pushed; `v*` tags cannot be moved or deleted by anyone, so a bad tag means a new version number; the `pypi` environment deploys only from `v*` tags.
