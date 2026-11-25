"""Download a release's jar into a temporary folder and verify it (design 12 V5). Nothing here touches the store.

The release says what the bytes should be (its ``size`` and, where GitHub gives one, its ``digest``); the jar
says what it is (``read_jar``). A mismatch, or a 404 on the asset, is retried once in all, against the release
object fetched again, since upstream replaces an asset by delete-then-upload (research 7).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from tlaup.errors import DownloadVerificationError, FileOperationError, NetworkError, VersionNotFound
from tlaup.versioning.jarinfo import read_jar
from tlaup.versioning.remote import JAR_NAME, parse_release

if TYPE_CHECKING:
    from pathlib import Path

    from tlaup.versioning.github import DownloadInfo, GitHubClient, Progress
    from tlaup.versioning.jarinfo import JarInfo
    from tlaup.versioning.remote import Asset, Release

RETRY_WAIT = 2.0  # seconds; upstream's gap between deleting an asset and uploading its replacement is 1 to 3
_SHA256_PREFIX = "sha256:"
_HINT = "try again in a minute: upstream may be replacing the file, or a proxy or a cut connection got in between"


def usable_digest(asset: Asset) -> str | None:
    """The part after ``sha256:`` (prefix in any case) in lower case; None for no digest or another prefix.

    A ``sha256:`` digest that is not 64 hexadecimal digits is returned as written, lower-cased: it equals no
    hash, so a download compared with it fails rather than going unchecked.
    """
    digest = asset.digest
    if digest is None or digest[: len(_SHA256_PREFIX)].lower() != _SHA256_PREFIX:
        return None
    return digest[len(_SHA256_PREFIX) :].lower()


def fetch_build(
    client: GitHubClient, release: Release, dest_dir: Path, progress: Progress | None
) -> tuple[Path, JarInfo]:
    """Download ``release``'s jar to ``dest_dir / "tla2tools.jar"`` and return it once verified.

    Raises ``VersionNotFound`` for a release without the jar (before any request), ``DownloadVerificationError``
    when the bytes are not what the release describes after the one retry or are not a TLA+ tools jar, and the
    client's errors otherwise. Writes only inside ``dest_dir``; what is left there is the caller's to discard.
    """
    if release.asset is None:
        message = f"the release {release.tag!r} has no {JAR_NAME} to install"
        raise VersionNotFound(message, hint="run `tlaup tool list` to see the releases that have one")
    jar = dest_dir / JAR_NAME
    downloaded = _first_attempt(client, release.tag, release.asset, jar, progress)
    if downloaded is None:
        client.sleep(RETRY_WAIT)
        fresh = _fetch_release(client, release.tag)
        if fresh.asset is None:
            message = f"the release {release.tag!r} no longer has a {JAR_NAME}"
            raise DownloadVerificationError(message, hint=_HINT)
        downloaded = _attempt(client, release.tag, fresh.asset, jar, progress)
    info = read_jar(jar)
    if (info.sha256, info.size) != (downloaded.sha256, downloaded.size):
        message = f"{JAR_NAME} changed on disk between its download and its check"
        raise DownloadVerificationError(message, hint=_HINT)
    return jar, info


def _first_attempt(
    client: GitHubClient, tag: str, asset: Asset, jar: Path, progress: Progress | None
) -> DownloadInfo | None:
    """The first download; None when it is worth the one retry: a mismatch, or a 404 (the upload gap)."""
    try:
        return _attempt(client, tag, asset, jar, progress)
    except DownloadVerificationError:
        return None
    except NetworkError as error:
        if error.status == 404:
            return None
        raise  # a connection that failed is not the upload gap


def _attempt(client: GitHubClient, tag: str, asset: Asset, jar: Path, progress: Progress | None) -> DownloadInfo:
    """One download from nothing, checked against ``asset``; DownloadVerificationError on a mismatch."""
    try:
        with jar.open("wb") as out:
            got = client.download(asset.download_url, out, progress, limit=asset.size + 1)
    except OSError as error:
        message = f"cannot write {jar}: {error.strerror or error}"
        raise FileOperationError(message) from error
    what = f"the download of {JAR_NAME} for {tag!r}"
    # A body longer than the asset was cut at size + 1, so its Content-Length can be honest and still differ:
    # that case is the release's size check below.
    if got.content_length is not None and got.size != got.content_length and got.size <= asset.size:
        message = f"{what} has {got.size} bytes, but the server announced {got.content_length}"
        raise DownloadVerificationError(message, hint=_HINT)
    if got.size != asset.size:
        shown = f"more than {asset.size}" if got.size > asset.size else str(got.size)
        message = f"{what} has {shown} bytes, but the release says {asset.size}"
        raise DownloadVerificationError(message, hint=_HINT)
    expected = usable_digest(asset)
    if expected is not None and got.sha256 != expected:
        message = f"{what} does not match the SHA-256 digest the release gives"
        details = f"expected {expected}, got {got.sha256}"
        raise DownloadVerificationError(message, hint=_HINT, details=details)
    return got


def _fetch_release(client: GitHubClient, tag: str) -> Release:
    """The release object of ``tag`` as upstream publishes it now; VersionNotFound when the tag is gone."""
    path = f"/releases/tags/{quote(tag, safe='')}"
    try:
        data, _ = client.get_json(path)
    except NetworkError as error:
        if error.status == 404:
            message = f"no release is tagged {tag!r}"
            raise VersionNotFound(message, hint="run `tlaup tool list` to see the releases") from None
        raise
    return parse_release(data, url=f"{client.base_url}{path}")
