"""The store and GitHub steps of design 01 T5 that package 29 owns, as helpers over the store and the fake GitHub.

``given.py`` and ``then.py`` wrap these. The store is read and written through ``ToolStore`` only, with an
injected clock; GitHub is package 05's ``github`` fixture, started by the first GitHub step of a scenario.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import weakref
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from tests.clock import FakeClock
from tests.github import JAR_TAGS, MANIFESTS, RECORDINGS, fit_body
from tests.jars import make_tools_jar
from tests.steps._scenario import fail
from tlaup.config.loader import load_settings
from tlaup.errors import PinnedBuildMissing, TlaupError
from tlaup.paths import AppPaths
from tlaup.versioning.jarinfo import read_jar
from tlaup.versioning.remote import write_cache
from tlaup.versioning.spec import format_build, parse_version_spec
from tlaup.versioning.store import Source, ToolStore

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.github import GitHubFake
    from tests.steps._scenario import Scenario
    from tlaup.versioning.store import Build

# A build installed by a step that upstream does not publish: an upload time no release has.
UNPUBLISHED_UPLOAD = "2026-01-01T00:00:00Z"
STEP_GAP = timedelta(minutes=1)  # each installed build is a minute newer than the one before
_CALVER = re.compile(r"([0-9]{4})\.([0-9]{2})\.([0-9]{2})\.([0-9]{2})([0-9]{2})([0-9]{2})")


@dataclass
class ToolState:
    """What the store and GitHub steps keep for one scenario."""

    clock: FakeClock = field(default_factory=FakeClock)
    github: GitHubFake | None = None


_STATES: weakref.WeakKeyDictionary[Scenario, ToolState] = weakref.WeakKeyDictionary()


def state(scenario: Scenario) -> ToolState:
    if scenario not in _STATES:
        _STATES[scenario] = ToolState()
    return _STATES[scenario]


def paths() -> AppPaths:
    try:
        return AppPaths.from_env(os.environ)
    except TlaupError as error:
        fail(f"tlaup's folders cannot be worked out from the environment: {error}")


def store(scenario: Scenario) -> ToolStore:
    """The store as a step sees it, with the scenario's clock."""
    return ToolStore(paths(), now=state(scenario).clock.now)


# The recorded releases


def recorded_releases(recording: str, jars: dict[str, Path]) -> list[dict[str, Any]]:
    """The release list of a recording, its jar assets fitted to the small jars, as the fixture serves it."""
    body = (RECORDINGS / recording / "list.body").read_bytes()
    data: list[dict[str, Any]] = json.loads(fit_body(body, jars))
    return data


def published_jars(folder: Path) -> dict[str, Path]:
    """The small jars the fixture publishes, built the same way, so their bytes and digests are the same."""
    return {
        tag: make_tools_jar(folder / tag / "tla2tools.jar", MANIFESTS / manifest, repl=repl)
        for tag, (manifest, repl) in JAR_TAGS.items()
    }


def _jar_asset(release: dict[str, Any]) -> dict[str, Any] | None:
    return next((a for a in release.get("assets", []) if a.get("name") == "tla2tools.jar"), None)


# Given: the store


def _manifest(name: str, commit: str | None, calver: str | None) -> bytes:
    """The recorded manifest of a published name (v1.7.4's for any other), changed to that commit or build time.

    Worked on as bytes, so that the published names keep the recorded file exactly (its line ends included).
    """
    manifest_name, _ = JAR_TAGS.get(name, JAR_TAGS["v1.7.4"])
    data = (MANIFESTS / manifest_name).read_bytes()
    if name not in JAR_TAGS and commit is None:
        commit = hashlib.sha1(name.encode(), usedforsecurity=False).hexdigest()  # another name, another build
    if commit is not None:
        full = (commit + "0" * 40)[:40].encode()
        data = re.sub(rb"(?m)^X-Git-Revision: [^\r\n]*", b"X-Git-Revision: " + full, data)
        data = re.sub(rb"(?m)^X-Git-ShortRevision: [^\r\n]*", b"X-Git-ShortRevision: " + full[:7], data)
    if calver is not None:
        match = _CALVER.fullmatch(calver)
        if match is None:
            fail(f"{calver!r} is not a build time")
        year, month, day, hour, minute, second = match.groups()
        stamp = f"Build-TimeStamp: {year}-{month}-{day}T{hour}:{minute}:{second}Z".encode()
        if b"Build-TimeStamp:" in data:
            data = re.sub(rb"(?m)^Build-TimeStamp: [^\r\n]*", stamp, data)
        else:
            end = b"\r\n" if b"\r\n" in data else b"\n"
            data = data.replace(b"Implementation-Title:", stamp + end + b"Implementation-Title:", 1)
    return data


def install(scenario: Scenario, spec_text: str, *, pinned: bool = False) -> Build:
    """``the build "<spec>" is installed``, into the scenario's store with its clock, a minute after the last."""
    build = add_build(store(scenario), scenario.folder, spec_text, pinned=pinned)
    state(scenario).clock.advance(STEP_GAP.total_seconds())
    return build


def add_build(tools: ToolStore, folder: Path, spec_text: str, *, pinned: bool = False) -> Build:
    """Install through ``ToolStore.add`` the jar the fixture publishes under the name, with its recorded source.

    ``NAME@COMMIT`` or ``NAME@CALVER`` is another build of that name, which upstream does not publish. A name
    the fixture serves no jar for gets a jar of its own. ``folder`` holds the jars made on the way.
    """
    spec = parse_version_spec(spec_text)
    if spec.name is None or spec.name in ("stable", "latest") or spec.sha256 is not None:
        fail(f'"the build ... is installed" takes a tag, optionally with @commit or @build-time, not {spec_text!r}')
    name = spec.name
    jars = published_jars(folder / "published")
    release = next((r for r in recorded_releases("releases", jars) if r["tag_name"] == name), None)
    other = spec.commit is not None or spec.calver is not None or name not in JAR_TAGS
    jar = make_tools_jar(
        folder / "installed" / spec_text.replace("/", "_") / "tla2tools.jar",
        _manifest(name, spec.commit, spec.calver),
        repl=JAR_TAGS.get(name, ("", False))[1],
    )
    asset = _jar_asset(release) if release is not None else None
    if asset is not None:
        source = Source(
            kind="github-release",
            url=asset["browser_download_url"],
            asset_id=asset["id"],
            asset_updated_at=UNPUBLISHED_UPLOAD if other else asset["updated_at"],
            digest_checked=asset.get("digest") is not None,
        )
    else:
        source = Source(
            kind="github-release",
            url=f"https://github.com/tlaplus/tlaplus/releases/download/{name}/tla2tools.jar",
            asset_id=None,
            asset_updated_at=UNPUBLISHED_UPLOAD,
            digest_checked=False,
        )
    prerelease = bool(release["prerelease"]) if release is not None else False
    with tools.locked():
        tmp = tools.new_tmp()
        tmp.lock()
        try:
            tmp.make()
            target = tmp.path / "tla2tools.jar"
            shutil.copyfile(jar, target)
            build = tools.add(target, read_jar(target), name=name, prerelease=prerelease, source=source)
        finally:
            tmp.release()
        if pinned:
            tools.pin(build)
    return build


def no_build(scenario: Scenario) -> None:
    """``no build is installed``: every build's folder is removed; a pin, if any, is left naming a build gone."""
    folder = paths().tools
    for build in store(scenario).builds():
        shutil.rmtree(build.path)
    if store(scenario).builds():
        fail(f"{folder} still holds builds")


def one_build(scenario: Scenario, spec_text: str) -> Build:
    found = store(scenario).find(parse_version_spec(spec_text))
    if len(found) != 1:
        every = store(scenario).builds()
        names = ", ".join(format_build(build, every) for build in found) or "none"
        fail(f"{spec_text!r} names {len(found)} installed builds, not one: {names}")
    return found[0]


def build_folder(scenario: Scenario, path: str) -> str | None:
    """``{tools}/<version>`` naming exactly one installed build: that build's folder; else None.

    A build's folder is named from its jar's digest, which no feature file can know, and never a bare version
    (V1), so the form cannot mean a folder of that name.
    """
    prefix = "{tools}/"
    if not path.startswith(prefix) or "/" in path[len(prefix) :]:
        return None
    try:
        spec = parse_version_spec(path[len(prefix) :])
    except TlaupError:
        return None
    return str(one_build(scenario, path[len(prefix) :]).path) if store(scenario).find(spec) else None


def build_jar(scenario: Scenario, text: str) -> str | None:
    """``{tools}/<version>/tla2tools.jar`` with ``{tools}/<version>`` naming one installed build: its jar; else None.

    The same reading as ``build_folder``, for the one line ``tool path`` prints (package 29b).
    """
    suffix = "/tla2tools.jar"
    if not text.endswith(suffix):
        return None
    folder = build_folder(scenario, text.removesuffix(suffix))
    return None if folder is None else str(Path(folder) / suffix.lstrip("/"))


def truncate(scenario: Scenario, spec_text: str) -> None:
    """``the jar of the build "<spec>" is truncated``: cut to half its size."""
    jar = one_build(scenario, spec_text).jar
    data = jar.read_bytes()
    jar.write_bytes(data[: len(data) // 2])


def cache_releases(scenario: Scenario, request: Any, recording: str, minutes: int) -> None:
    """``the release list is cached from "<recording>", <n> minutes old``, through package 25's ``write_cache``.

    Starts the fake GitHub first, so that the address is the one the commands will use.
    """
    github(scenario, request)
    folder = paths()
    repository = load_settings(folder, os.environ).settings.tool.repository.rstrip("/")
    jars = published_jars(scenario.folder / "published")
    # A command reads the cache with the real clock, so the age is counted back from it; the ages the scenarios
    # use are far from the one-hour limit (T5's note), which is a unit test with an injected clock (25).
    fetched = datetime.now(UTC) - timedelta(minutes=minutes)
    write_cache(folder.remote, f"{repository}/releases", recorded_releases(recording, jars), fetched)


# Given: GitHub


def github(scenario: Scenario, request: Any, recording: str | None = None) -> GitHubFake:
    """The scenario's fake GitHub, started once; ``I run`` forgets its requests before each run (T5)."""
    tool_state = state(scenario)
    if tool_state.github is None:
        start: Callable[..., GitHubFake] = request.getfixturevalue("github")
        tool_state.github = start(recording or "releases")
        scenario.before_run.append(tool_state.github.clear)
    elif recording is not None:
        fail('"GitHub answers from" is given once in a scenario, before the other GitHub steps')
    return tool_state.github


def started_github(scenario: Scenario) -> GitHubFake:
    fake = state(scenario).github
    if fake is None:
        fail('no fake GitHub in this scenario: "Given GitHub answers from ..." comes first')
    return fake


# Then: the store


def check_pinned(scenario: Scenario, spec_text: str) -> None:
    wanted = one_build(scenario, spec_text)
    try:
        pinned = store(scenario).pinned()
    except PinnedBuildMissing as error:
        fail(f"the pin names a missing build: {error.message}")
    if pinned is None or pinned.id != wanted.id:
        every = store(scenario).builds()
        shown = format_build(pinned, every) if pinned is not None else "nothing"
        fail(f"the pinned build is {shown}, not {format_build(wanted, every)}")


def check_nothing_pinned(scenario: Scenario) -> None:
    try:
        pinned = store(scenario).pinned()
    except PinnedBuildMissing as error:
        fail(f"the pin names a missing build: {error.message}")
    if pinned is not None:
        fail(f"{format_build(pinned, store(scenario).builds())} is pinned")


def check_installed(scenario: Scenario, datatable: list[list[str]]) -> None:
    """``the installed builds are:``: one column, headed ``build``, the printed forms in store order."""
    if not datatable or [cell.strip() for cell in datatable[0]] != ["build"]:
        fail('"the installed builds are:" takes a table of one column headed "build"')
    wanted = [row[0].strip() for row in datatable[1:]]
    every = store(scenario).builds()
    actual = [format_build(build, every) for build in every]
    if actual != wanted:
        fail(f"the installed builds are {actual}, not {wanted}")


# Then: GitHub


def check_requests(scenario: Scenario, count: int) -> None:
    fake = started_github(scenario)
    if len(fake.requests) != count:
        sent = [f"{r.method} {r.url}" for r in fake.requests]
        fail(f"{len(fake.requests)} requests were sent to GitHub, not {count}: {sent}")


def check_downloads(scenario: Scenario, count: int) -> None:
    fake = started_github(scenario)
    if fake.downloads != count:
        fail(f"{fake.downloads} jar downloads were made, not {count}")


def check_no_token_to(scenario: Scenario, host: str) -> None:
    fake = started_github(scenario)
    carried = [r.url for r in fake.requests if urlsplit(r.url or "").hostname == host and "Authorization" in r.headers]
    if carried:
        fail(f"requests to {host} carried a token: {carried}")
