"""What a user types as a version, and how a build is printed so that it can be typed back (design 02 X3).

No store, no network, no release list: `format_build` is given the installed builds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tlaup.errors import UsageError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tlaup.versioning.store import Build

_TAG = re.compile(r"[A-Za-z0-9._/+][A-Za-z0-9._/+-]*")
_COMMIT = re.compile(r"[0-9a-fA-F]{7,40}")
_CALVER = re.compile(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]{6}")
_DIGEST = re.compile(r"[0-9a-fA-F]{8,64}")
_SHA256 = "sha256:"

_FORMS = (
    "A version is a tag such as `v1.7.4`, `stable` or `rolling`, optionally followed by `@commit`, `@build-time` "
    "or `@sha256:digest`, or a build time such as `2026.11.15.002146`"
)


@dataclass(frozen=True)
class VersionSpec:
    name: str | None  # "stable", "rolling" or a tag as typed; None when only a CalVer was given
    commit: str | None  # lower-case hex prefix
    calver: str | None
    sha256: str | None  # lower-case hex prefix, from "@sha256:..."


def latest_refused(stable_tag: str | None = None) -> UsageError:
    """X3's refusal of `latest`; the tag after `stable` is left out when the caller does not know it."""
    stable = f"`stable` ({stable_tag})" if stable_tag else "`stable`"
    return UsageError(
        "`latest` is not a version here",
        hint=f"Use {stable} or `rolling` (the newest build).",
    )


def _refused(text: str, name: str, build: str) -> UsageError:
    if "://" in text or ":" in name or (":" in build and not build.startswith(_SHA256)):
        return UsageError(
            f"{text!r} is not a version",
            hint="Installing from an address is not supported; install a release by its tag",
        )
    return UsageError(f"{text!r} is not a version", hint=_FORMS)


def parse_version_spec(text: str) -> VersionSpec:
    """Turn typed text into a `VersionSpec`; raise `UsageError` for anything outside the grammar."""
    if _CALVER.fullmatch(text):
        return VersionSpec(None, None, text, None)
    name, at, build = text.partition("@")
    if name == "latest":
        raise latest_refused()
    if not _TAG.fullmatch(name):
        raise _refused(text, name, build)
    if not at:
        return VersionSpec(name, None, None, None)
    if _CALVER.fullmatch(build):
        return VersionSpec(name, None, build, None)
    if build.startswith(_SHA256):
        digest = build[len(_SHA256) :]
        if _DIGEST.fullmatch(digest):
            return VersionSpec(name, None, None, digest.lower())
    elif _COMMIT.fullmatch(build):
        return VersionSpec(name, build.lower(), None, None)
    raise _refused(text, name, build)


_SHORTEST_COMMIT = 7
_SHORTEST_DIGEST = 12


def _shortest(value: str, start: int, taken: list[str]) -> str:
    """The shortest prefix of ``value``, ``start`` digits or more, that none of ``taken`` starts with."""
    for length in range(start, len(value)):
        prefix = value[:length]
        if not any(other.startswith(prefix) for other in taken):
            return prefix
    return value


def format_build(build: Build, others: Sequence[Build] = ()) -> str:
    """X3's printing table: a form that finds exactly this build among ``others``, every installed build.

    Only the other builds with the build's name are looked at, and the rows are tried in order.
    """
    same = [other for other in others if other.name == build.name and other.id != build.id]
    commit = build.commit
    if commit is not None and all(other.commit != commit for other in same):
        commits = [other.commit for other in same if other.commit is not None]
        return f"{build.name}@{_shortest(commit, _SHORTEST_COMMIT, commits)}"
    if build.calver is not None and all(other.calver != build.calver for other in same):
        return f"{build.name}@{build.calver}"
    if not same:
        return build.name
    digest = _shortest(build.sha256, _SHORTEST_DIGEST, [other.sha256 for other in same])
    return f"{build.name}@{_SHA256}{digest}"
