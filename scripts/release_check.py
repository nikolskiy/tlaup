#!/usr/bin/env python3
"""Is this commit a release, and if so, is it releasable? (design 30 L8)

    scripts/release_check.py --tags FILE [--mode pr|publish]

FILE holds the output of ``git ls-remote --tags --refs origin``. A commit whose project version has
a ``v*`` tag is not a release, and the check passes. Otherwise it is a release candidate, and the
check fails unless the version is higher than every tag, uv.lock has the same version, CHANGELOG.md
has a dated section for it with nothing under Unreleased, and PyPI does not have it yet.

``--mode pr`` (the default) is the release-check job of test.yml and scripts/release.py.
``--mode publish`` is the first job of the release workflow; there an untagged version that PyPI
already has means an earlier run uploaded and did not tag. When ``GITHUB_OUTPUT`` is set, the
check writes ``release=true|false`` and ``version=X.Y.Z`` to it. Standard library only.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPI_URL = "https://pypi.org/pypi/tlaup/{version}/json"
_TAG = re.compile(r"[0-9a-f]+\trefs/tags/v(\d+)\.(\d+)\.(\d+)")
_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_HTTP_NOT_FOUND = 404
_HTTP_OK = 200


class CheckError(Exception):
    """A fact the check needs could not be read; the message says which."""


class Verdict:
    """The version, whether the commit is a release, and what keeps a release from being releasable."""

    def __init__(self, version: str, *, release: bool) -> None:
        self.version = version
        self.release = release
        self.problems: list[str] = []


def _changelog_section() -> ModuleType:
    path = Path(__file__).resolve().parent / "changelog_section.py"
    spec = importlib.util.spec_from_file_location("changelog_section", path)
    if spec is None or spec.loader is None:  # pragma: no cover - the file is in the repository
        message = f"cannot load {path}"
        raise CheckError(message)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_tags(text: str) -> set[tuple[int, int, int]]:
    """The versions of the ``vX.Y.Z`` tags in ``git ls-remote --tags --refs`` output."""
    found: set[tuple[int, int, int]] = set()
    for line in text.splitlines():
        match = _TAG.fullmatch(line.strip())
        if match:
            found.add((int(match[1]), int(match[2]), int(match[3])))
    return found


def _numbers(version: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(version)
    if match is None:
        message = f"the project version {version!r} is not of the form X.Y.Z"
        raise CheckError(message)
    return int(match[1]), int(match[2]), int(match[3])


def read_versions(root: Path) -> tuple[str, str | None]:
    """The version in pyproject.toml, and tlaup's version in uv.lock (None if it has no entry)."""
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        message = f"cannot read pyproject.toml or uv.lock: {error}"
        raise CheckError(message) from error
    version = project.get("project", {}).get("version")
    if not isinstance(version, str):
        message = "pyproject.toml has no [project] version"
        raise CheckError(message)
    locked = next((p.get("version") for p in lock.get("package", []) if p.get("name") == "tlaup"), None)
    return version, locked if isinstance(locked, str) else None


def pypi_has(version: str, urlopen: Callable[..., Any] = urllib.request.urlopen) -> bool:
    """Whether PyPI has tlaup at ``version``: 200 is yes, 404 is no, anything else is an error."""
    url = PYPI_URL.format(version=version)
    try:
        with urlopen(url, timeout=30) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()  # it holds the response; Python 3.15 warns when one is left open
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        message = f"could not ask PyPI about {version} ({url}): {error}"
        raise CheckError(message) from error
    if status == _HTTP_NOT_FOUND:
        return False
    if status == _HTTP_OK:
        return True
    message = f"PyPI answered {status} for {url}; neither 200 nor 404, so whether it has {version} is unknown"
    raise CheckError(message)


def evaluate(
    root: Path,
    tags: set[tuple[int, int, int]],
    mode: str,
    on_pypi: Callable[[str], bool] = pypi_has,
) -> Verdict:
    """The verdict on the tree at ``root``; PyPI is asked only for an untagged version."""
    version, locked = read_versions(root)
    numbers = _numbers(version)
    if numbers in tags:
        return Verdict(version, release=False)
    verdict = Verdict(version, release=True)
    problems = verdict.problems
    if tags and numbers <= max(tags):
        latest = ".".join(str(n) for n in max(tags))
        problems.append(f"{version} is not higher than the latest tag v{latest}; bump the version.")
    if locked != version:
        problems.append(f"uv.lock has tlaup {locked or '<none>'}, pyproject.toml has {version}; run uv lock.")
    module = _changelog_section()
    try:
        text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        module.section(text, version)
    except OSError as error:
        problems.append(f"cannot read CHANGELOG.md: {error.strerror}.")
    except module.ChangelogError as error:
        problems.append(f"CHANGELOG.md: {error}")
    if on_pypi(version):
        if mode == "publish":
            problems.append(
                f"PyPI has {version} already, but it has no tag v{version}: an earlier release run uploaded it and"
                " then failed. Re-run the failed jobs of that run in the Actions tab."
            )
        else:
            problems.append(f"PyPI has {version} already, and a version cannot be uploaded twice; bump the version.")
    return verdict


def _write_outputs(verdict: Verdict) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(f"release={'true' if verdict.release else 'false'}\nversion={verdict.version}\n")


def main(argv: list[str] | None = None, root: Path = REPO_ROOT, on_pypi: Callable[[str], bool] = pypi_has) -> int:
    args = sys.argv[1:] if argv is None else argv
    usage = "usage: scripts/release_check.py --tags FILE [--mode pr|publish]\n"
    options = dict(zip(args[::2], args[1::2], strict=False))
    if len(args) % 2 or set(options) - {"--tags", "--mode"} or "--tags" not in options:
        sys.stderr.write(usage)
        return 2
    mode = options.get("--mode", "pr")
    if mode not in {"pr", "publish"}:
        sys.stderr.write(usage)
        return 2
    try:
        tags = parse_tags(Path(options["--tags"]).read_text(encoding="utf-8"))
        verdict = evaluate(root, tags, mode, on_pypi)
    except OSError as error:
        sys.stderr.write(f"release check: cannot read {options['--tags']}: {error.strerror}.\n")
        return 1
    except CheckError as error:
        sys.stderr.write(f"release check: {error}.\n")
        return 1
    if not verdict.release:
        sys.stdout.write(f"{verdict.version} is tagged v{verdict.version} already: this commit is not a release.\n")
    elif verdict.problems:
        sys.stderr.write(f"{verdict.version} has no tag, so this commit is a release, and it is not releasable:\n")
        sys.stderr.writelines(f"- {problem}\n" for problem in verdict.problems)
        return 1
    else:
        sys.stdout.write(f"{verdict.version} has no tag: this commit is a release, and every release check passed.\n")
    _write_outputs(verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
