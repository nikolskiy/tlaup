# Releasing

A release is a pull request. When its tests pass it merges by itself, the merge publishes the version to PyPI, and the commit gets its `v*` tag only after the upload succeeded, so every tag names a commit whose build is on PyPI ([design 30 L8](../design/30-ci-and-release.md#l8-release-by-pull-request)).

## Making a release

On your machine, on an up-to-date `main` with a clean tree, with git, uv and a logged-in `gh`, run:

```bash
uv run poe release
```

It asks two questions, then for a go-ahead:

1. **Which part of the version to bump.** It shows what patch, minor and major would each give. The version rule is in [conventions](conventions.md#compatibility-and-versions): from 0.9.0 on, a minor version carries breaking changes and features, a patch version only fixes.
2. **Whether to refresh `uv.lock`** (`uv lock --upgrade`, yes by default). The weekly `deps-newest` run has usually shown already whether the newest versions work.
3. **Whether to go ahead.** Before asking, it has made the release commit's changes on a branch `release/vX.Y.Z`: the version in `pyproject.toml` and `uv.lock`, and `## [Unreleased]` in `CHANGELOG.md` renamed to `## [X.Y.Z] - <today>`, with an empty `## [Unreleased]` above it. It has also run the release check (below). It shows the changelog section and the changed files. A no puts `main` back as it was; nothing has been pushed.

On a yes it pushes the branch, opens the pull request `chore(release): X.Y.Z` and turns on auto-merge. From there nothing needs you:

- The push runs the tests. When `Test` is green, GitHub squash-merges the pull request; its text, which is the changelog section, becomes the commit's message on `main`.
- The merge starts the "Release" workflow. `build` runs lint, the unit tests and `poe check-release`; `publish` uploads the wheel and the sdist to PyPI by trusted publishing; `tag-and-page` checks that PyPI holds exactly those files, then creates the annotated tag `vX.Y.Z` on the merged commit and the release page.

The script follows both and ends by printing the PyPI page, or what failed. Ctrl-C stops only the following; the release goes on.

It refuses to start when you are not on a clean `main` equal to `origin/main`, when Unreleased has no entries, or when a release pull request is already open.

## The release check

`scripts/release_check.py` decides, for any commit, whether it is a release: it is one when its version has no `v*` tag. For such a commit it fails unless all of these hold:

- the version is higher than every tag;
- `uv.lock` has the same version;
- the changelog has a dated section for it with nothing under Unreleased;
- PyPI does not have it yet.

It runs in the release script before anything is pushed, as the `release-check` job inside `Test` (so a release pull request cannot merge while it fails), and as the first job of "Release". Any pull request that changes the version is a release pull request, however it was made, and merging it publishes with no further approval.

## When something fails

- **Before the merge:** the pull request waits. Push a fix to its branch, like any other; auto-merge stays on. If `main` moved on, update the branch.
- **After the merge but before the upload** (for example a flaky test in `build`): re-run the failed jobs of the "Release" run. After a fix merged into `main`, the next push starts a new "Release" run, since the version is still untagged; "Run workflow" on "Release" does the same by hand. The fix's own `release-check` sees that untagged version too, so give the fix no new Unreleased entry: describe it in the dated section of the release, or not at all.
- **After the upload, if `tag-and-page` failed:** re-run that job. A tag or page it already made on the same commit is kept.
- **If an upload stopped half way:** re-run `publish`; it sends only the files PyPI does not have yet.

PyPI never takes a version number twice, so a version that reached PyPI broken is fixed by the next patch release.

**While a release is unfinished,** that is, merged but not yet tagged, `main`'s version is untagged, so every commit on `main` is still that release. The next merge into `main` would start the release again and publish that newer commit, with changes the dated changelog section does not list. Feature branches cut from `main` meanwhile fail their `release-check`, because their Unreleased section has entries again. Finish the release before merging other work.

Optional, after the first release made this way: give the older release pages their changelog sections, one command per tag that has a page, for example `gh release edit vX.Y.Z --notes-file <(uv run python scripts/changelog_section.py X.Y.Z)`. Which older tags have pages, and whether those without get one, is the maintainer's choice.

## Repository rules

`main` cannot be deleted or force-pushed; `v*` tags cannot be moved or deleted by anyone, so a bad tag means a new version number.

Once the maintainer has set them:

- The ruleset on `main` takes changes only through pull requests whose `Test` check passed (the check of GitHub Actions), squash-merged, from a branch that is up to date with `main`; force pushes and deletion are blocked; nobody can bypass it, the maintainer included.
- The repository allows squash merging only (merge commits and rebase merging off) and allows auto-merge; the squash commit's default message is the pull request's title and description (`PR_TITLE`, `PR_BODY`); "Automatically delete head branches" is off, so the archive workflow can rename the merged branch.
- Actions' workflow permissions are read-only by default, with "Allow GitHub Actions to create and approve pull requests" on, so the draft pull request workflow can open its pull requests.
- The `pypi` environment deploys only from the branch `main` and has no required reviewer: the go-ahead is the release script's question and the green `Test` that the merge needs.

These are the maintainer actions of [design 30 I7](../design/30-ci-and-release.md#i7-ruleset-on-main), [L5](../design/30-ci-and-release.md#l5-pypi-environment) and [L8](../design/30-ci-and-release.md#l8-release-by-pull-request).
