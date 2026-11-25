"""The fake GitHub: recordings served through ``responses`` (design 01 T4, "Network")."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

import requests
import responses

from tests.jars import make_tools_jar

if TYPE_CHECKING:
    from collections.abc import Mapping

RECORDINGS = Path(__file__).resolve().parent / "recordings" / "github"
MANIFESTS = Path(__file__).resolve().parent / "unit" / "data" / "manifests"
BASE = "https://api.github.com/repos/tlaplus/tlaplus"
# Tags whose jar the fixture serves, with the recorded manifest and whether the REPL class is in the jar.
JAR_TAGS = {
    "rolling": ("rolling.MANIFEST.MF", True),
    "v1.8.0": ("v1.8.0.MANIFEST.MF", True),
    "v1.7.4": ("v1.7.4.MANIFEST.MF", False),
}
# The body is trimmed, so these recorded values are wrong for the body as served.
_COMPUTED = {"content-length", "content-encoding", "transfer-encoding"}


@dataclass(frozen=True)
class Recorded:
    status: int
    headers: Mapping[str, str]  # as recorded, names lower-cased
    body: bytes


def _read(folder: Path, file: str) -> Recorded:
    head = (folder / f"{file}.headers").read_text(encoding="utf-8").splitlines()
    status = int(head[0].split()[1])
    headers = {}
    for line in head[1:]:
        if line.strip():
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
    return Recorded(status, headers, (folder / f"{file}.body").read_bytes())


def _entries(name: str, folder: Path | None = None) -> list[dict[str, Any]]:
    folder = (folder or RECORDINGS) / name
    return tomllib.loads((folder / "requests.toml").read_text(encoding="utf-8"))["answer"]


def load_recording(name: str) -> list[tuple[str, str, Recorded]]:
    """(method, url, answer) for every answer of ``tests/recordings/github/<name>/requests.toml``."""
    folder = RECORDINGS / name
    return [(a["method"], a["url"], _read(folder, a["file"])) for a in _entries(name)]


def _page_matcher(request: requests.PreparedRequest) -> tuple[bool, str]:
    """Page 1 answers any query to the list, except one that names another page."""
    page = parse_qs(urlsplit(request.url or "").query).get("page", ["1"])[0]
    return (page == "1", "another page was asked for")


def _fit_jar(release: dict[str, Any], jars: Mapping[str, Path]) -> None:
    """The jar asset of the three tags carries the small jar's size and digest (null stays null)."""
    jar = jars.get(release.get("tag_name", ""))
    for asset in release.get("assets", []):
        if jar is not None and asset.get("name") == "tla2tools.jar":
            asset["size"] = jar.stat().st_size
            if asset.get("digest") is not None:
                asset["digest"] = "sha256:" + hashlib.sha256(jar.read_bytes()).hexdigest()


def _fit_body(body: bytes, jars: Mapping[str, Path]) -> bytes:
    try:
        data = json.loads(body)
    except ValueError:
        return body
    releases = data if isinstance(data, list) else [data]
    if not all(isinstance(r, dict) and "assets" in r for r in releases):
        return body
    for release in releases:
        _fit_jar(release, jars)
    return json.dumps(data, indent=1).encode()


class GitHubFake:
    """A recording registered with ``responses``, the requests made and the small jars."""

    def __init__(self, mock: responses.RequestsMock, tmp_path: Path, recording: str) -> None:
        self.mock = mock
        self._downloads: set[str] = set()
        self._jars = {
            tag: make_tools_jar(tmp_path / "jars" / tag / "tla2tools.jar", MANIFESTS / manifest, repl=repl)
            for tag, (manifest, repl) in JAR_TAGS.items()
        }
        self._register(recording)

    def _register(self, recording: str) -> None:
        folder = RECORDINGS / recording
        for entry in _entries(recording):
            answer = _read(folder, entry["file"])
            body = _fit_body(answer.body, self._jars)
            headers = {k: v for k, v in answer.headers.items() if k not in _COMPUTED}
            content_type = headers.pop("content-type", "application/json")
            self._find_downloads(body)
            url: Any = entry["url"]
            kwargs: dict[str, Any] = {}
            if entry.get("scope") == "host":
                url = re.compile(r"https://api\.github\.com/.*")
            elif url.endswith("/releases") and "?" not in url:
                kwargs["match"] = [_page_matcher]
            self.mock.add(
                entry["method"], url, body=body, status=answer.status, headers=headers,
                content_type=content_type, **kwargs,
            )  # fmt: skip

    def _find_downloads(self, body: bytes) -> None:
        try:
            data = json.loads(body)
        except ValueError:
            return
        for release in data if isinstance(data, list) else [data]:
            if not isinstance(release, dict) or release.get("tag_name") not in self._jars:
                continue
            for asset in release.get("assets", []):
                if asset.get("name") == "tla2tools.jar":
                    tag = release["tag_name"]
                    if asset["browser_download_url"] not in self._downloads:
                        self._downloads.add(asset["browser_download_url"])
                        self.mock.add(
                            "GET", asset["browser_download_url"], body=self._jars[tag].read_bytes(),
                            status=200, content_type="application/zip",
                        )  # fmt: skip

    @property
    def requests(self) -> list[requests.PreparedRequest]:
        """Every request made, in order, with its headers."""
        return [call.request for call in self.mock.calls]

    @property
    def downloads(self) -> int:
        """Requests to a jar's download address."""
        return sum(1 for r in self.requests if (r.url or "").split("?")[0] in self._downloads)

    def clear(self) -> None:
        """Forget the requests so far."""
        self.mock.calls.reset()

    def jar(self, tag: str) -> Path:
        """The small jar served for that tag."""
        return self._jars[tag]

    def unreachable(self) -> None:
        """From now on every request fails with ``requests.ConnectionError``.

        The latest registration wins (inserted ahead).
        """

        def refuse(request: requests.PreparedRequest) -> Any:
            message = f"GitHub is unreachable: {request.method} {request.url}"
            raise requests.ConnectionError(message)

        for method in ("GET", "HEAD", "POST"):
            self.mock.registered().insert(0, responses.CallbackResponse(method, re.compile(r"https://.*"), refuse))

    def answer(self, status: int, path: str) -> None:
        """An answer with that status for a path under the base address; it wins over the recording.

        The latest registration wins (inserted ahead).
        """
        response = responses.Response("GET", BASE + path, body=b"", status=status)
        self.mock.registered().insert(0, response)
