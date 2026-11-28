#!/usr/bin/env python3
"""Start a release from a clean, up-to-date main, and follow it to PyPI (design 30 L8).

    uv run poe release

Asks which part of the version to bump and whether to refresh uv.lock, makes the release commit
on a branch release/vX.Y.Z (scripts/prepare_release.py), runs the release check, shows the
changelog section and asks to go ahead. Then it pushes the branch with your own login, so the
push runs the tests like any other, opens the release pull request and turns on auto-merge.
GitHub squash-merges it once Test is green, and the merge runs the release workflow, which
uploads to PyPI and then tags the commit. The script follows both and prints the outcome;
stopping it (Ctrl-C) stops only the following, not the release.

Needs git, uv and gh (logged in). Nothing is pushed before you say yes, and a no puts main back
as it was.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
PARTS = ("patch", "minor", "major")
FILES = ("pyproject.toml", "uv.lock", "CHANGELOG.md")  # all a release commit changes
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_WAIT_SECONDS = 10
_WAIT_TRIES = 60  # ten minutes for GitHub to merge or to start the release run


class ReleaseError(Exception):
    """The release cannot start or go on; the message says why and what to do."""


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    if spec is None or spec.loader is None:  # pragma: no cover - the files are in the repository
        message = f"cannot load scripts/{name}.py"
        raise ReleaseError(message)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def next_versions(version: str) -> dict[str, str]:
    """What each part's bump makes of ``version``, as ``uv version --bump`` does."""
    match = _VERSION.fullmatch(version)
    if match is None:
        message = f"the project version {version!r} is not of the form X.Y.Z"
        raise ReleaseError(message)
    major, minor, patch = (int(n) for n in match.groups())
    return {
        "patch": f"{major}.{minor}.{patch + 1}",
        "minor": f"{major}.{minor + 1}.0",
        "major": f"{major + 1}.0.0",
    }


def ask_part(version: str, ask: Callable[[str], str] = input) -> str | None:
    """Ask for patch, minor or major until one is given; None when the answer is empty (stop)."""
    choices = next_versions(version)
    shown = ", ".join(f"{part} {choices[part]}" for part in PARTS)
    while True:
        try:
            answer = ask(f"Version {version}. Bump which part? ({shown}; empty to stop): ").strip().lower()
        except EOFError:  # Ctrl-D stops, like Ctrl-C
            raise KeyboardInterrupt from None
        if not answer:
            return None
        if answer in PARTS:
            return answer
        sys.stdout.write("Answer patch, minor or major.\n")


def ask_yes(question: str, *, default: bool, ask: Callable[[str], str] = input) -> bool:
    """A yes or no question; an empty answer is ``default``, and Ctrl-D stops, like Ctrl-C."""
    hint = "Y/n" if default else "y/N"
    while True:
        try:
            answer = ask(f"{question} [{hint}] ").strip().lower()
        except EOFError:
            raise KeyboardInterrupt from None
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        sys.stdout.write("Answer y or n.\n")


def pr_body(version: str, section: str) -> str:
    """The release pull request's text, which becomes the squash commit's message on main."""
    return (
        f"Release tlaup {version}. Once Test is green, auto-merge squash-merges this into main, and the"
        f" Release workflow builds it, publishes it to PyPI, and then tags the commit v{version} and"
        " creates its release page.\n\n" + section
    )


def _tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        message = f"{name} is not on PATH; it is needed to release."
        raise ReleaseError(message)
    return path


def run(*args: str, capture: bool = True) -> str:
    """Run a command in the repository; ReleaseError with its own words if it fails."""
    result = subprocess.run(
        [_tool(args[0]), *args[1:]],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        said = (result.stderr or result.stdout or "").strip() if capture else ""
        message = f"`{' '.join(args)}` failed (exit {result.returncode})" + (f": {said}" if said else "")
        raise ReleaseError(message)
    return (result.stdout or "").strip() if capture else ""


def preflight() -> str:
    """Check the starting point and return the project version."""
    branch = run("git", "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch != "main":
        message = f"on {branch}, not main. Switch to main (git switch main) and pull."
        raise ReleaseError(message)
    if run("git", "status", "--porcelain"):
        message = "the working tree is not clean. Commit or stash the changes (git status lists them)."
        raise ReleaseError(message)
    run("git", "fetch", "--quiet", "origin", "main")
    if run("git", "rev-parse", "HEAD") != run("git", "rev-parse", "origin/main"):
        message = "main is not origin/main. Pull (git pull --ff-only) so they are the same."
        raise ReleaseError(message)
    run("gh", "auth", "status")
    open_releases = json.loads(run("gh", "pr", "list", "--state", "open", "--json", "number,headRefName"))
    for pr in open_releases:
        if str(pr.get("headRefName", "")).startswith("release/"):
            message = f"pull request #{pr['number']} ({pr['headRefName']}) is a release in progress. Finish it first."
            raise ReleaseError(message)
    module = _load("prepare_release")
    try:
        module.unreleased_entries((REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    except module.PrepareError as error:
        raise ReleaseError(str(error)) from error
    return run("uv", "version", "--short")


def _changes() -> str:
    """The release files' changes against HEAD, to see whether anything moved while a question waited."""
    return run("git", "diff", "HEAD", "--", *FILES)


def _only_release_files_changed() -> bool:
    changed = {line[3:] for line in run("git", "status", "--porcelain").splitlines()}
    return changed <= set(FILES)


class Local:
    """The release branch while it exists only on this machine: the run can still be taken back."""

    def __init__(self, branch: str) -> None:
        self.branch = branch
        self.created = False  # this run made the branch, so this run may delete it
        self.pushed = False
        self.changes = ""  # the release check's tree, once it passed

    def undo(self) -> str:
        """Put main back as it was, unless files were edited after the check; say what was done."""
        if not self.created:
            return "nothing was changed."
        if self.pushed:
            return (
                f"{self.branch} is pushed already. Open its pull request on GitHub, or delete it"
                f" (git push origin --delete {self.branch}); then git switch main."
            )
        try:
            if self.changes and _changes() != self.changes:
                return (
                    f"files changed while the question waited, so nothing was undone: you are on {self.branch}"
                    " with the release changes and your edits. Look at git diff, then git switch main."
                )
            # Only the release files go back; an edit to any other file comes along to main untouched.
            run("git", "checkout", "HEAD", "--", *FILES)
            run("git", "switch", "--quiet", "main")
            if run("git", "branch", "--list", self.branch):
                run("git", "branch", "--quiet", "-D", self.branch)
        except ReleaseError as error:
            return f"main could not be put back ({error}). Look at git status; the release branch is {self.branch}."
        return "main is as it was, and nothing was pushed."


def _bump(part: str, expected: str) -> str:
    """Bump and date the changelog with prepare_release.py; ReleaseError unless it gave ``expected``."""
    version = run(sys.executable, str(SCRIPTS / "prepare_release.py"), part)
    if version != expected:
        message = f"uv bumped to {version}, not {expected} as expected; stopping."
        raise ReleaseError(message)
    return version


def prepare(local: Local, part: str, *, refresh: bool, expected: str) -> str:
    """Make the release commit's tree on the local branch; return the changelog section."""
    if run("git", "ls-remote", "--heads", "origin", local.branch):
        message = (
            f"the branch {local.branch} exists on GitHub already. If no release pull request is open for it,"
            f" delete it (git push origin --delete {local.branch}) and run this again."
        )
        raise ReleaseError(message)
    if run("git", "branch", "--list", local.branch):
        message = f"a local branch {local.branch} exists already. Delete it (git branch -D {local.branch}) first."
        raise ReleaseError(message)
    if run("git", "status", "--porcelain"):
        message = "files changed while the questions waited. Commit or stash them, then run this again."
        raise ReleaseError(message)
    local.created = True  # set first: the branch did not exist a moment ago, so any branch by that name is ours
    run("git", "switch", "--quiet", "-c", local.branch)
    version = _bump(part, expected)
    if refresh:
        sys.stdout.write("Refreshing uv.lock (uv lock --upgrade)...\n")
        run("uv", "lock", "--upgrade")
    with tempfile.TemporaryDirectory() as tmp:
        tags = Path(tmp) / "tags.txt"
        tags.write_text(run("git", "ls-remote", "--tags", "--refs", "origin") + "\n", encoding="utf-8")
        run(sys.executable, str(SCRIPTS / "release_check.py"), "--tags", str(tags))
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section: str = _load("changelog_section").section(text, version)
    local.changes = _changes()
    return section


def commit_and_push(local: Local, version: str) -> None:
    """Commit and push the release branch; ReleaseError, with the branch still local, if either fails."""
    if _changes() != local.changes or not _only_release_files_changed():
        message = "files changed while the question waited, after the release check; run the release again."
        raise ReleaseError(message)
    local.changes = ""  # from here the changes are the run's own commit, which undo may delete
    run("git", "commit", "--quiet", "-m", f"chore(release): {version}", "--", *FILES)
    try:
        run("git", "push", "--quiet", "-u", "origin", local.branch, capture=False)
    except (ReleaseError, KeyboardInterrupt):
        # A push cut short may still have reached GitHub; ask before saying anything about it.
        try:
            local.pushed = bool(run("git", "ls-remote", "--heads", "origin", local.branch))
        except ReleaseError:
            local.pushed = True  # unknown, so the message must not claim nothing was pushed
        raise
    local.pushed = True
    run("git", "switch", "--quiet", "main")


def open_pr(version: str, section: str) -> int:
    """Open the release pull request and turn on auto-merge; return its number."""
    branch = f"release/v{version}"
    title = f"chore(release): {version}"
    with tempfile.TemporaryDirectory() as tmp:
        body = Path(tmp) / "body.md"
        body.write_text(pr_body(version, section), encoding="utf-8")
        try:
            url = run(
                "gh", "pr", "create", "--base", "main", "--head", branch, "--title", title, "--body-file", str(body)
            )  # fmt: skip
        except ReleaseError as error:
            message = (
                f"{branch} is pushed, but its pull request could not be opened ({error}). Open it on GitHub with the"
                f" title {title!r}, or delete the branch (git push origin --delete {branch}) and run this again."
            )
            raise ReleaseError(message) from error
        number = int(url.rstrip("/").rsplit("/", 1)[-1])
        sys.stdout.write(f"Opened {url}\n")
        try:
            # The squash commit's subject and message, given so they do not rest on the repository's defaults.
            run(
                "gh", "pr", "merge", str(number), "--auto", "--squash",
                "--subject", f"{title} (#{number})", "--body-file", str(body),
            )  # fmt: skip
        except ReleaseError as error:
            message = (
                f'could not turn on auto-merge for #{number} ({error}). Is "Allow auto-merge" on in the repository'
                " settings? The pull request is open: merge it by hand when Test is green, and the release goes on."
            )
            raise ReleaseError(message) from error
    return number


def _gh_json(*args: str) -> object:
    try:
        return json.loads(run("gh", *args))
    except ReleaseError as error:
        message = f"{error}. Only the following stopped; the release goes on, so follow it on GitHub."
        raise ReleaseError(message) from error


def follow(number: int, version: str, sleep: Callable[[float], None] = time.sleep) -> None:
    """Wait for the merge and the release run, and say how they ended."""
    sys.stdout.write("Waiting for Test and the merge. Ctrl-C stops waiting; the release goes on.\n")
    merged = ""
    for _ in range(_WAIT_TRIES * 6):  # Test takes about fifteen minutes
        state = _gh_json("pr", "view", str(number), "--json", "state,mergeCommit")
        assert isinstance(state, dict)  # gh's --json gives an object here
        if state["state"] == "MERGED":
            merged = state["mergeCommit"]["oid"]
            break
        if state["state"] == "CLOSED":
            message = f"#{number} was closed without merging; nothing was released."
            raise ReleaseError(message)
        sleep(_WAIT_SECONDS)
    if not merged:
        message = f"#{number} has not merged yet. Look at its checks; if main moved on, update the branch."
        raise ReleaseError(message)
    sys.stdout.write(f"Merged as {merged[:12]}. Waiting for the Release run...\n")
    for _ in range(_WAIT_TRIES):
        runs = _gh_json("run", "list", "--workflow", "release.yml", "--commit", merged, "--json", "databaseId")
        if isinstance(runs, list) and runs:
            run_id = str(runs[0]["databaseId"])
            try:
                run("gh", "run", "watch", run_id, "--exit-status", capture=False)
            except ReleaseError:
                ended = _gh_json("run", "view", run_id, "--json", "conclusion")
                if isinstance(ended, dict) and ended.get("conclusion") == "cancelled":
                    message = f"the Release run {run_id} was cancelled; a newer push to main runs the release instead."
                else:
                    message = f"the Release run {run_id} failed. Open it in the Actions tab and re-run its failed jobs."
                raise ReleaseError(message) from None
            if run("git", "ls-remote", "--tags", "origin", f"refs/tags/v{version}"):
                sys.stdout.write(f"Released {version}: https://pypi.org/project/tlaup/{version}/\n")
                return
            message = f"the Release run {run_id} ended without tagging v{version}. Open it in the Actions tab."
            raise ReleaseError(message)
        sleep(_WAIT_SECONDS)
    message = f"no Release run started for {merged[:12]}. Look in the Actions tab."
    raise ReleaseError(message)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        sys.stderr.write("usage: uv run poe release (it asks for everything it needs)\n")
        return 2
    local: Local | None = None  # set while the release branch exists only here
    stage = ""  # after the push: how far the run got
    try:
        version = preflight()
        part = ask_part(version)
        if part is None:
            sys.stdout.write("Stopped; nothing was changed.\n")
            return 0
        expected = next_versions(version)[part]
        refresh = ask_yes("Refresh uv.lock to the newest versions the ranges allow?", default=True)
        local = Local(f"release/v{expected}")
        section = prepare(local, part, refresh=refresh, expected=expected)
        sys.stdout.write(f"\nThe changelog section of {expected}:\n\n{section}\n")
        sys.stdout.write(run("git", "diff", "--stat") + "\n\n")
        question = (
            f"Push release/v{expected} and open its pull request? Once Test is green it merges and publishes"
            " to PyPI by itself."
        )
        if not ask_yes(question, default=False):
            sys.stdout.write(f"Stopped; {local.undo()}\n")
            return 0
        commit_and_push(local, expected)
        local = None
        stage = f"release/v{expected} is pushed"
        number = open_pr(expected, section)
        stage = "auto-merge is on"
        follow(number, expected)
    except ReleaseError as error:
        sys.stderr.write(f"release: {error}\n")
        if local is not None:
            sys.stderr.write(f"release: {local.undo()}\n")
        return 1
    except KeyboardInterrupt:
        if local is not None:
            sys.stderr.write(f"\nrelease: stopped; {local.undo()}\n")
        elif stage == "auto-merge is on":
            sys.stderr.write("\nrelease: stopped following; the release goes on by itself on GitHub.\n")
        elif stage:
            sys.stderr.write(
                f"\nrelease: stopped; {stage}. Check on GitHub that its pull request is open with auto-merge on,"
                " or delete the branch.\n"
            )
        else:
            sys.stderr.write("\nrelease: stopped; nothing was changed.\n")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
