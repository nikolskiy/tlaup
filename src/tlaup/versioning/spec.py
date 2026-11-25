"""What a user types as a version (design 02 X3). Parsing only: no store, no network, no release list."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tlaup.errors import UsageError

_TAG = re.compile(r"[A-Za-z0-9._/+][A-Za-z0-9._/+-]*")
_COMMIT = re.compile(r"[0-9a-fA-F]{7,40}")
_CALVER = re.compile(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]{6}")
_DIGEST = re.compile(r"[0-9a-fA-F]{8,64}")
_SHA256 = "sha256:"

_FORMS = "A version is a tag such as `v1.7.4`, `stable`, `rolling`, or `name@commit`"


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
