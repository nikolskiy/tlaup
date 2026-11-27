#!/usr/bin/env bash
# Check that main is ready to release, then tag it and push main and the tag (design 30 L1).
#
# Usage:
#   scripts/release.sh          run steps 1 to 10: the checks, the annotated tag, the atomic push
#   scripts/release.sh --check  run the checks (steps 1 to 8) only; nothing is tagged or pushed
#
# The procedure around it is docs/contributing/releasing.md.

set -euo pipefail

CHECK_ONLY=0
case "${1-}:$#" in
  ":0") ;;
  "--check:1") CHECK_ONLY=1 ;;
  *)
    echo "usage: scripts/release.sh [--check]" >&2
    exit 2
    ;;
esac

cd "$(dirname "${BASH_SOURCE[0]}")/.."

fail() {
  echo "release: $*" >&2
  echo "release: stopped; nothing was tagged or pushed." >&2
  exit 1
}

step() {
  echo "[$1] $2"
}

# 1. The version, read by uv rather than from the file's text.
VERSION=$(uv version --short) || fail "could not read the version with 'uv version --short'."
TAG="v$VERSION"
step 1 "version $VERSION, tag $TAG"

# 2. On main, with a clean tree.
BRANCH=$(git symbolic-ref --quiet --short HEAD || true)
[ "$BRANCH" = main ] || fail "on '${BRANCH:-a detached HEAD}', not main. Switch to main: git switch main."
[ -z "$(git status --porcelain)" ] || fail "the working tree is not clean. Commit or stash the changes (git status lists them)."
step 2 "on main, working tree clean"

# 3. HEAD is what origin has.
git fetch --quiet origin main --tags || fail "git fetch origin main --tags failed. Check the network and the remote."
SHA=$(git rev-parse HEAD)
REMOTE_SHA=$(git rev-parse origin/main)
[ "$SHA" = "$REMOTE_SHA" ] ||
  fail "HEAD ($SHA) is not origin/main ($REMOTE_SHA). Push or pull main until they are the same."
step 3 "HEAD equals origin/main ($SHA)"

# 4. The tag exists nowhere yet.
if git rev-parse --quiet --verify "refs/tags/$TAG" >/dev/null; then
  fail "the tag $TAG already exists locally. Tags cannot be moved: bump the version (uv run poe bump <part>)."
fi
REMOTE_TAGS=$(git ls-remote --tags origin "refs/tags/$TAG") ||
  fail "git ls-remote --tags origin failed. Check the network and the remote."
[ -z "$REMOTE_TAGS" ] ||
  fail "the tag $TAG already exists on origin. Tags cannot be moved: bump the version (uv run poe bump <part>)."
step 4 "tag $TAG is free locally and on origin"

# 5. The lock file is current and names the same version.
uv lock --check || fail "uv.lock is out of date. Run uv lock, commit and push, and wait for CI."
LOCK_VERSION=$(awk '
  /^\[\[package\]\]$/ { in_tlaup = 0 }
  /^name = "tlaup"$/ { in_tlaup = 1 }
  in_tlaup && /^version = / { gsub(/"/, "", $3); print $3; exit }
' uv.lock)
[ "$LOCK_VERSION" = "$VERSION" ] ||
  fail "uv.lock has tlaup ${LOCK_VERSION:-<none>}, pyproject.toml has $VERSION. Run uv lock, commit and push."
step 5 "uv.lock is current and has tlaup $VERSION"

# 6. The changelog has a dated section for the version and nothing left under Unreleased.
uv run python scripts/changelog_section.py "$VERSION" >/dev/null ||
  fail "CHANGELOG.md is not ready for $VERSION (the line above says why). Fix it, commit and push."
step 6 "CHANGELOG.md has a section for $VERSION"

# 7. CI is green for HEAD: the check run named Test, from GitHub Actions, completed with success.
command -v gh >/dev/null ||
  fail "gh (the GitHub CLI) is not installed; it is needed to see that CI is green. Install it; this check is never skipped."
gh auth status >/dev/null 2>&1 ||
  fail "gh is not logged in; it is needed to see that CI is green. Run gh auth login; this check is never skipped."
RUNS=$(gh api "repos/{owner}/{repo}/commits/$SHA/check-runs?check_name=Test" \
  --jq '.check_runs[] | select(.app.slug == "github-actions") | "\(.status) \(.conclusion)"') ||
  fail "could not read the check runs of $SHA from GitHub."
[ -n "$RUNS" ] || fail "no check run named Test for $SHA. Wait for the Test workflow to start, then run this again."
while read -r STATUS CONCLUSION; do
  [ "$STATUS" = completed ] ||
    fail "the Test check of $SHA is $STATUS. Wait for it to finish, then run this again."
  [ "$CONCLUSION" = success ] ||
    fail "the Test check of $SHA ended with $CONCLUSION. Fix main first."
done <<<"$RUNS"
step 7 "CI is green for $SHA"

# 8. The build, twine check and the wheel check (design 30 I4).
uv run poe check-release || fail "uv run poe check-release failed (its output above says why)."
step 8 "poe check-release passed"

if [ "$CHECK_ONLY" = 1 ]; then
  echo "All checks passed for $TAG. Nothing was tagged (--check)."
  exit 0
fi

# 9. An annotated tag (decision D21).
git tag -a "$TAG" -m "tlaup $VERSION" || fail "git tag -a $TAG failed."
step 9 "tagged $TAG"

# 10. main and the tag in one atomic push; the local tag goes if the push fails.
if ! git push --atomic origin main "$TAG"; then
  git tag -d "$TAG" >/dev/null
  fail "git push --atomic origin main $TAG failed; the local tag $TAG was deleted. Fix the cause and run this again."
fi
step 10 "pushed main and $TAG"

echo "Released $TAG. The release workflow builds it, waits for approval in the pypi environment, publishes and creates the release page."
