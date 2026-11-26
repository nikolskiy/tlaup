"""What upstream publishes: the release list with its cache, one release looked up fresh (design 12 V8)."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlsplit

from tlaup.errors import NetworkError, RateLimited, RemoteDataError, VersionNotFound
from tlaup.versioning.order import name_key, stable_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from tlaup.versioning.github import GitHubClient
    from tlaup.versioning.spec import VersionSpec

JAR_NAME = "tla2tools.jar"
SCHEMA = 1
_TIME = "%Y-%m-%dT%H:%M:%SZ"


class Freshness(Enum):
    ONLINE = "online"  # asked GitHub just now
    CACHED = "cached"  # the cache was young enough
    STALE = "stale"  # the network failed; old data is shown
    UNAVAILABLE = "unavailable"  # the network failed and there is nothing to show


@dataclass(frozen=True)
class Asset:
    id: int
    size: int
    digest: str | None  # as GitHub wrote it
    updated_at: str
    download_url: str  # the release object's browser_download_url (V7)


@dataclass(frozen=True)
class Release:
    tag: str
    prerelease: bool
    draft: bool
    created_at: str
    published_at: str | None
    asset: Asset | None  # the tla2tools.jar asset, None if the release has none


def _field(data: dict[str, Any], key: str, kind: type, url: str, *, optional: bool = False) -> Any:
    value = data.get(key)
    if value is None and optional:  # absent or null: a digest older assets lack, a draft's publication date
        return None
    # bool is an int in Python; a flag where a number is expected is as wrong as a string
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        message = f"{url} answered with {key!r} missing or of the wrong type"
        raise RemoteDataError(message)
    return value


def _parse_asset(data: Any, url: str) -> Asset:
    if not isinstance(data, dict):
        message = f"{url} answered a release whose asset is not an object"
        raise RemoteDataError(message)
    return Asset(
        id=_field(data, "id", int, url),
        size=_field(data, "size", int, url),
        digest=_field(data, "digest", str, url, optional=True),
        updated_at=_field(data, "updated_at", str, url),
        download_url=_field(data, "browser_download_url", str, url),
    )


def parse_release(data: Any, *, url: str) -> Release:
    """One release object as GitHub sends it; RemoteDataError naming ``url`` when it is not one tlaup can read."""
    if not isinstance(data, dict):
        message = f"{url} did not answer with a release object"
        raise RemoteDataError(message)
    assets = _field(data, "assets", list, url)
    jar = next((a for a in assets if isinstance(a, dict) and a.get("name") == JAR_NAME), None)
    return Release(
        tag=_field(data, "tag_name", str, url),
        prerelease=_field(data, "prerelease", bool, url),
        draft=_field(data, "draft", bool, url),
        created_at=_field(data, "created_at", str, url),
        published_at=_field(data, "published_at", str, url, optional=True),
        asset=None if jar is None else _parse_asset(jar, url),
    )


def _cache_file(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha256(url.encode()).hexdigest()[:16]}.json"


def write_cache(cache_dir: Path, url: str, data: Any, fetched_at: datetime) -> None:
    """The one writer of a cache file: a temporary file in the folder, then one rename."""
    text = json.dumps(
        {"schema": SCHEMA, "url": url, "fetched_at": fetched_at.astimezone(UTC).strftime(_TIME), "data": data},
        indent=1,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = _cache_file(cache_dir, url)
    handle, tmp = tempfile.mkstemp(dir=cache_dir, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(tmp).replace(target)
    except BaseException:
        with suppress(OSError):
            Path(tmp).unlink()
        raise


def _read_cache(cache_dir: Path, url: str) -> tuple[list[Release], datetime] | None:
    """The cached list and when it was fetched; None for a file that is absent, unreadable or of another shape."""
    try:
        record = json.loads(_cache_file(cache_dir, url).read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("url") != url:
            return None
        fetched_at = datetime.strptime(record["fetched_at"], _TIME).replace(tzinfo=UTC)
        data = record["data"]
        if not isinstance(data, list):
            return None
        return [parse_release(item, url=url) for item in data], fetched_at
    except (OSError, ValueError, KeyError, TypeError, RemoteDataError):
        return None


def cached_tags(cache_dir: Path) -> list[str]:
    """The tags of the remembered release lists' releases that have the jar, in X4's order, without duplicates.

    Every lookup cache file under ``cache_dir`` whose ``url`` is a release list (a path ending in ``/releases``,
    any query) is read with this module's reader. Age is ignored: shell completion offers what is remembered. A
    file that cannot be read is skipped, as ``_read_cache`` treats it as absent (V8). No request, no settings.
    """
    try:
        files = sorted(cache_dir.glob("*.json"))
    except OSError:
        return []
    tags: set[str] = set()
    for file in files:
        try:
            url = json.loads(file.read_text(encoding="utf-8"))["url"]
            if not isinstance(url, str) or not urlsplit(url).path.endswith("/releases"):
                continue
        except (OSError, ValueError, KeyError, TypeError):
            continue
        cached = _read_cache(cache_dir, url) if _cache_file(cache_dir, url) == file else None
        if cached is not None:
            tags.update(release.tag for release in cached[0] if release.asset is not None)
    return sorted(tags, key=name_key)


class Remote:
    """The releases of one repository, through ``client``; ``now`` is the injected clock."""

    def __init__(self, client: GitHubClient, cache_dir: Path, *, now: Callable[[], datetime]) -> None:
        self._client = client
        self._cache_dir = cache_dir
        self._now = now
        self._url = f"{client.base_url}/releases"

    def fetch_releases(self) -> list[Release]:
        """Ask GitHub for the list and cache what came back. Raises the client's errors; an error is never cached."""
        data = self._client.get_paged("/releases")
        releases = [parse_release(item, url=self._url) for item in data]
        with suppress(OSError):  # a cache that cannot be written only costs the next request
            write_cache(self._cache_dir, self._url, data, self._now())
        return releases

    def releases(self, *, max_age: float = 3600) -> tuple[list[Release], Freshness]:
        """The list, from the cache when it is younger than ``max_age`` seconds. Never raises for the network."""
        cached = _read_cache(self._cache_dir, self._url)
        if cached is not None and 0 <= (self._now() - cached[1]).total_seconds() < max_age:
            return cached[0], Freshness.CACHED
        try:
            return self.fetch_releases(), Freshness.ONLINE
        except (NetworkError, RateLimited, RemoteDataError):
            if cached is not None:
                return cached[0], Freshness.STALE
            return [], Freshness.UNAVAILABLE

    def cached(self) -> list[Release] | None:
        """The cached list whatever its age; None without a readable cache file. Never a request."""
        cached = _read_cache(self._cache_dir, self._url)
        return None if cached is None else cached[0]

    def release(self, tag: str) -> Release:
        """What upstream publishes under ``tag`` now. Never cached; VersionNotFound for a 404."""
        path = f"/releases/tags/{quote(tag, safe='')}"
        try:
            data, _ = self._client.get_json(path)
        except NetworkError as error:
            if error.status == 404:
                message = f"no release is tagged {tag!r}"
                raise VersionNotFound(message, hint="run `tlaup tool list` to see the releases") from None
            raise
        return parse_release(data, url=f"{self._client.base_url}{path}")

    def _with_closest_tag(self, error: VersionNotFound, name: str) -> VersionNotFound:
        """The same error with the closest tag of the cached release list in its hint (F11); no request is made for it.

        Unchanged when no list is cached or no tag is close."""
        tags = [release.tag for release in self.cached() or [] if release.asset is not None]
        close = difflib.get_close_matches(name, tags, n=1)
        if not close:
            return error
        return VersionNotFound(
            error.message, hint=f"did you mean {close[0]}? run `tlaup tool list` to see the releases"
        )

    def resolve(self, spec: VersionSpec) -> Release:
        """``stable`` is the stable release of a fresh list; any other name is looked up by tag (then with ``v``)."""
        name = spec.name
        if name is None:
            message = "a build time does not name a release"
            raise VersionNotFound(message)
        if name == "stable":
            chosen = stable_of(self.fetch_releases())
            if chosen is None:
                message = "no stable release is available"
                raise VersionNotFound(message, hint="run `tlaup tool list` to see the releases")
            return chosen
        try:
            found = self.release(name)
        except VersionNotFound as first:
            if name.startswith("v"):
                raise self._with_closest_tag(first, name) from None
            try:
                found = self.release(f"v{name}")
            except VersionNotFound:
                raise self._with_closest_tag(first, name) from None  # names the name as the user typed it
        if found.asset is None:
            message = f"the release {found.tag!r} has no {JAR_NAME} to install"
            raise VersionNotFound(message, hint="run `tlaup tool list` to see the releases that have one")
        return found
