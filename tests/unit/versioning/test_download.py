"""Download and verify (design 12 V5, the download rows of 01 T6, inventory row T9).

Against the real client and ``fetch_build`` with ``responses`` serving the ``releases`` recording (01 T1, T4).
Each test holds a real store with a build of the tag already in it, downloads into a temporary folder of
that store, and asserts the error type and the state afterwards, never the message (T12 rule 4). The
state assertions of the failing rows are row T9's test: ``store.builds()`` is what it was, the earlier
build's jar keeps its SHA-256, and nothing was written outside the folder ``fetch_build`` was given.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import zipfile
from typing import TYPE_CHECKING, Any

import pytest
import responses

from tests.github import BASE
from tests.jars import make_tools_jar
from tests.unit.versioning.conftest import commit, manifest
from tlaup.errors import DownloadVerificationError, FileOperationError, NetworkError, VersionNotFound
from tlaup.versioning.download import fetch_build, usable_digest
from tlaup.versioning.remote import Asset, Release, parse_release

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from tests.clock import FakeClock
    from tests.github import GitHubFake
    from tests.unit.versioning.conftest import Downloads
    from tlaup.versioning.github import GitHubClient
    from tlaup.versioning.store import Build, TmpFolder, ToolStore

    GitHub = Callable[..., GitHubFake]
    MakeClient = Callable[..., GitHubClient]

ROLLING_JAR = "https://github.com/tlaplus/tlaplus/releases/download/rolling/tla2tools.jar"
HTML = b"<!DOCTYPE html>\n<html><head><title>Proxy</title></head><body>Access denied</body></html>\n"
WRONG_DIGEST = "sha256:" + "0" * 64


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def other_jar(tmp_path: Path, name: str) -> bytes:
    """A small tools jar unlike the one the fixture serves."""
    return make_tools_jar(tmp_path / "other" / name / "tla2tools.jar", manifest(commit("ab"), extra=name)).read_bytes()


class Setup:
    """The fake GitHub, the client, a store holding an earlier build of the tag, and the download's folder."""

    def __init__(
        self, fake: GitHubFake, client: GitHubClient, store: ToolStore, earlier: Build, tmp: TmpFolder, root: Path
    ) -> None:
        self.fake = fake
        self.client = client
        self.store = store
        self.earlier = earlier
        self.tmp = tmp
        self.builds_before = store.builds()
        self.root = root  # the test's folder, which holds the store, the fixture's jars and the home folder
        self.outside_before = self._outside()

    @property
    def dest(self) -> Path:
        return self.tmp.path

    def release(self, tag: str = "rolling") -> dict[str, Any]:
        """The release object the recording serves for ``tag``, as JSON, fetched without counting the request."""
        data, _ = self.client.get_json(f"/releases/tags/{tag}")
        self.fake.clear()
        assert isinstance(data, dict)
        return data

    def serve_release(self, data: dict[str, Any], tag: str = "rolling") -> None:
        """One answer for the release object of ``tag``, ahead of the recording."""
        response = responses.Response("GET", f"{BASE}/releases/tags/{tag}", json=data, status=200)
        self.fake.mock.registered().insert(0, response)

    def serve_jar(self, body: bytes, *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        """One answer at the rolling jar's address, ahead of earlier ones and the recording."""
        response = responses.Response(
            "GET", ROLLING_JAR, body=body, status=status, headers=headers, content_type="application/octet-stream"
        )
        self.fake.mock.registered().insert(0, response)

    def release_requests(self, tag: str = "rolling") -> int:
        return sum(1 for r in self.fake.requests if r.url == f"{BASE}/releases/tags/{tag}")

    def _outside(self) -> dict[str, tuple[int, str]]:
        """Every file under the test's folder outside ``dest``, with its size and the SHA-256 of its bytes."""
        found = {}
        for path in self.root.rglob("*"):
            if path.is_file() and self.dest not in path.parents:
                data = path.read_bytes()
                found[str(path)] = (len(data), sha256(data))
        return found

    def assert_unchanged(self) -> None:
        """Row T9: the store as it was, the earlier jar intact, nothing written outside ``dest``."""
        assert self.store.builds() == self.builds_before
        assert sha256(self.earlier.jar.read_bytes()) == self.earlier.sha256
        assert self._outside() == self.outside_before


def as_release(data: dict[str, Any]) -> Release:
    return parse_release(data, url=f"{BASE}/releases/tags/{data['tag_name']}")


def with_jar(data: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """The release object with the jar asset's fields changed (``digest=None`` makes it null)."""
    changed = dict(data)
    changed["assets"] = [{**asset, **fields} if asset["name"] == "tla2tools.jar" else asset for asset in data["assets"]]
    return changed


def without_jar(data: dict[str, Any]) -> dict[str, Any]:
    changed = dict(data)
    changed["assets"] = [asset for asset in data["assets"] if asset["name"] != "tla2tools.jar"]
    return changed


@pytest.fixture
def setup(
    github: GitHub, make_client: MakeClient, store: ToolStore, downloads: Downloads, tmp_path: Path
) -> Iterator[Setup]:
    fake = github()
    earlier = downloads.add(manifest(commit("e1"), extra="earlier"), name="rolling")
    tmp = store.new_tmp()
    tmp.lock()
    tmp.make()
    try:
        yield Setup(fake, make_client(), store, earlier, tmp, tmp_path)
    finally:
        tmp.release()


# ---------------------------------------------------------------------- the jar is returned


def test_the_happy_path_returns_the_jar_with_the_manifests_commit(setup: Setup, clock: FakeClock) -> None:
    release = as_release(setup.release())
    counts: list[tuple[int, int | None]] = []
    path, info = fetch_build(setup.client, release, setup.dest, lambda done, total: counts.append((done, total)))
    served = setup.fake.jar("rolling").read_bytes()
    assert path == setup.dest / "tla2tools.jar"
    assert path.read_bytes() == served
    assert info.sha256 == sha256(served)
    assert info.size == len(served)
    assert info.commit is not None
    assert info.commit == commit_of_served(setup)
    assert setup.fake.downloads == 1
    assert setup.release_requests() == 0
    assert clock.sleeps == []
    assert counts
    assert [done for done, _ in counts] == sorted(done for done, _ in counts)
    assert counts[-1][0] == len(served)


def commit_of_served(setup: Setup) -> str | None:
    with zipfile.ZipFile(setup.fake.jar("rolling")) as jar:
        text = jar.read("META-INF/MANIFEST.MF").decode()
    revision = next(line for line in text.splitlines() if line.startswith("X-Git-Revision:"))
    return revision.split(":", 1)[1].strip()


def test_a_release_without_a_jar_is_version_not_found_and_makes_no_request(setup: Setup) -> None:
    release = dataclasses.replace(as_release(setup.release()), asset=None)
    with pytest.raises(VersionNotFound):
        fetch_build(setup.client, release, setup.dest, None)
    assert setup.fake.requests == []
    setup.assert_unchanged()


def test_a_release_with_no_digest_is_checked_by_size_zip_and_class(setup: Setup) -> None:
    release = as_release(setup.release("v1.7.4"))
    assert release.asset is not None
    assert release.asset.digest is None
    path, info = fetch_build(setup.client, release, setup.dest, None)
    assert info.sha256 == sha256(setup.fake.jar("v1.7.4").read_bytes())
    assert path.read_bytes() == setup.fake.jar("v1.7.4").read_bytes()


def test_an_upper_case_digest_compares_equal(setup: Setup) -> None:
    data = setup.release()
    upper = "SHA256:" + sha256(setup.fake.jar("rolling").read_bytes()).upper()
    _, info = fetch_build(setup.client, as_release(with_jar(data, digest=upper)), setup.dest, None)
    assert info.sha256 == sha256(setup.fake.jar("rolling").read_bytes())
    assert setup.fake.downloads == 1


def test_a_digest_with_another_prefix_is_no_digest(setup: Setup) -> None:
    other = "sha512:" + "1" * 128
    release = as_release(with_jar(setup.release(), digest=other))
    assert release.asset is not None
    assert usable_digest(release.asset) is None
    _, info = fetch_build(setup.client, release, setup.dest, None)
    assert info.sha256 == sha256(setup.fake.jar("rolling").read_bytes())
    assert setup.fake.downloads == 1


def test_a_digest_with_another_prefix_still_has_its_size_checked(setup: Setup, clock: FakeClock) -> None:
    data = with_jar(setup.release(), digest="md5:" + "1" * 32)
    data = with_jar(data, size=data["assets"][0]["size"] + 7)
    setup.serve_release(data)  # the fresh lookup says the same
    with pytest.raises(DownloadVerificationError):
        fetch_build(setup.client, as_release(data), setup.dest, None)
    assert setup.fake.downloads == 2
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


def test_a_404_then_200_returns_the_jar_after_one_retry(setup: Setup, clock: FakeClock) -> None:
    setup.serve_jar(b"Not Found", status=404)
    _, info = fetch_build(setup.client, as_release(setup.release()), setup.dest, None)
    assert info.sha256 == sha256(setup.fake.jar("rolling").read_bytes())
    assert setup.fake.downloads == 2
    assert setup.release_requests() == 1
    assert clock.sleeps == [2.0]


def test_a_digest_that_differs_once_then_matches_returns_the_second_body(
    setup: Setup, clock: FakeClock, tmp_path: Path
) -> None:
    looked_up = other_jar(tmp_path, "looked-up1")  # what the release said before upstream replaced it
    first_body = other_jar(tmp_path, "first-body")
    assert len(first_body) == len(looked_up)  # so that the size passes and the digest is what fails
    assert sha256(first_body) != sha256(looked_up)
    data = setup.release()
    stale = with_jar(data, size=len(first_body), digest="sha256:" + sha256(looked_up))
    setup.serve_jar(first_body)  # then the recording's jar, which the refreshed release (the recording) describes
    _, info = fetch_build(setup.client, as_release(stale), setup.dest, None)
    second_body = setup.fake.jar("rolling").read_bytes()
    assert info.sha256 == sha256(second_body)
    assert "sha256:" + info.sha256 == data["assets"][0]["digest"]
    assert (setup.dest / "tla2tools.jar").read_bytes() == second_body
    assert setup.fake.downloads == 2
    assert setup.release_requests() == 1
    assert clock.sleeps == [2.0]


# ---------------------------------------------------------------------- the download fails


def test_a_connection_that_drops_mid_stream_is_a_network_error(setup: Setup, clock: FakeClock) -> None:
    class Drops(io.RawIOBase):
        """Ten bytes, then the connection times out."""

        def __init__(self) -> None:
            self.sent = False

        def readable(self) -> bool:
            return True

        def readinto(self, buffer: Any) -> int:
            if self.sent:
                raise TimeoutError
            self.sent = True
            buffer[:10] = b"PK\x03\x04" + b"\0" * 6
            return 10

    setup.fake.mock.registered().insert(0, responses.Response("GET", ROLLING_JAR, body=io.BufferedReader(Drops())))
    with pytest.raises(NetworkError):
        fetch_build(setup.client, as_release(setup.release()), setup.dest, None)
    assert setup.fake.downloads == 1
    assert setup.release_requests() == 0
    assert clock.sleeps == []
    setup.assert_unchanged()


def test_a_body_cut_short_under_a_full_content_length_fails_after_one_retry(setup: Setup, clock: FakeClock) -> None:
    served = setup.fake.jar("rolling").read_bytes()
    for _ in range(2):
        setup.serve_jar(served[: len(served) // 2], headers={"Content-Length": str(len(served))})
    with pytest.raises(DownloadVerificationError):
        fetch_build(setup.client, as_release(setup.release()), setup.dest, None)
    assert setup.fake.downloads == 2
    assert setup.release_requests() == 1
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


def test_a_complete_answer_shorter_than_the_release_size_fails_after_one_retry(setup: Setup, clock: FakeClock) -> None:
    data = setup.release()
    data = with_jar(data, size=data["assets"][0]["size"] + 100)
    setup.serve_release(data)
    with pytest.raises(DownloadVerificationError):
        fetch_build(setup.client, as_release(data), setup.dest, None)
    assert setup.fake.downloads == 2
    assert setup.release_requests() == 1
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


def test_a_body_longer_than_the_size_is_cut_one_byte_past_it_and_fails(setup: Setup, clock: FakeClock) -> None:
    data = setup.release()
    size = data["assets"][0]["size"] - 50
    data = with_jar(data, size=size)
    setup.serve_release(data)
    with pytest.raises(DownloadVerificationError):
        fetch_build(setup.client, as_release(data), setup.dest, None)
    assert (setup.dest / "tla2tools.jar").stat().st_size <= size + 1
    assert setup.fake.downloads == 2
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


def test_a_longer_body_under_an_honest_content_length_fails_on_the_release_size(setup: Setup, clock: FakeClock) -> None:
    served = setup.fake.jar("rolling").read_bytes()
    data = setup.release()
    size = len(served) - 50
    data = with_jar(data, size=size)
    setup.serve_release(data)
    for _ in range(2):
        setup.serve_jar(served, headers={"Content-Length": str(len(served))})
    with pytest.raises(DownloadVerificationError) as caught:
        fetch_build(setup.client, as_release(data), setup.dest, None)
    # The release's size check fired, not the Content-Length one: the error names the release's size.
    assert str(size) in caught.value.message
    assert str(len(served)) not in caught.value.message
    assert (setup.dest / "tla2tools.jar").stat().st_size == size + 1
    assert setup.fake.downloads == 2
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


def test_a_404_on_the_release_fetched_again_is_version_not_found(setup: Setup, clock: FakeClock) -> None:
    first = setup.release()
    setup.serve_jar(b"Not Found", status=404)
    setup.fake.answer(404, "/releases/tags/rolling")
    with pytest.raises(VersionNotFound):
        fetch_build(setup.client, as_release(first), setup.dest, None)
    assert setup.fake.downloads == 1
    assert setup.release_requests() == 1
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


def test_a_second_404_on_the_asset_is_a_network_error(setup: Setup, clock: FakeClock) -> None:
    first = setup.release()
    for _ in range(2):
        setup.serve_jar(b"Not Found", status=404)
    with pytest.raises(NetworkError) as caught:
        fetch_build(setup.client, as_release(first), setup.dest, None)
    assert caught.value.status == 404
    assert setup.fake.downloads == 2
    assert setup.release_requests() == 1
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


def test_a_jar_that_cannot_be_written_is_a_file_operation_error(setup: Setup, clock: FakeClock) -> None:
    release = as_release(setup.release())
    with pytest.raises(FileOperationError):
        fetch_build(setup.client, release, setup.dest / "missing", None)
    assert setup.fake.requests == []
    assert clock.sleeps == []
    setup.assert_unchanged()


def test_an_html_page_fails_the_content_check(setup: Setup, clock: FakeClock) -> None:
    data = with_jar(setup.release(), size=len(HTML), digest="sha256:" + sha256(HTML))
    setup.serve_jar(HTML)
    with pytest.raises(DownloadVerificationError):
        fetch_build(setup.client, as_release(data), setup.dest, None)
    assert setup.fake.downloads == 1  # size and digest agree: no retry
    assert clock.sleeps == []
    setup.assert_unchanged()


def test_a_zip_without_the_tlc_class_fails_the_content_check(setup: Setup, clock: FakeClock) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("META-INF/MANIFEST.MF", manifest(commit("cd")))
        archive.writestr("tlc2/Other.class", b"")
    body = buffer.getvalue()
    data = with_jar(setup.release(), size=len(body), digest="sha256:" + sha256(body))
    setup.serve_jar(body)
    with pytest.raises(DownloadVerificationError):
        fetch_build(setup.client, as_release(data), setup.dest, None)
    assert setup.fake.downloads == 1
    assert clock.sleeps == []
    setup.assert_unchanged()


def test_a_digest_that_differs_twice_fails_after_one_lookup_and_one_retry(setup: Setup, clock: FakeClock) -> None:
    data = with_jar(setup.release(), digest=WRONG_DIGEST)
    setup.serve_release(data)
    with pytest.raises(DownloadVerificationError):
        fetch_build(setup.client, as_release(data), setup.dest, None)
    assert setup.fake.downloads == 2
    assert setup.release_requests() == 1
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


def test_the_retry_is_once_in_all_a_404_then_a_wrong_digest_fails(setup: Setup, clock: FakeClock) -> None:
    first = setup.release()
    setup.serve_release(with_jar(first, digest=WRONG_DIGEST))  # the fresh lookup
    setup.serve_jar(b"Not Found", status=404)
    with pytest.raises(DownloadVerificationError):
        fetch_build(setup.client, as_release(first), setup.dest, None)
    assert setup.fake.downloads == 2
    assert setup.release_requests() == 1
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


def test_a_refreshed_release_without_the_jar_fails_with_no_second_download(setup: Setup, clock: FakeClock) -> None:
    data = setup.release()
    setup.serve_release(without_jar(data))
    with pytest.raises(DownloadVerificationError):
        fetch_build(setup.client, as_release(with_jar(data, digest=WRONG_DIGEST)), setup.dest, None)
    assert setup.fake.downloads == 1
    assert setup.release_requests() == 1
    assert clock.sleeps == [2.0]
    setup.assert_unchanged()


# ---------------------------------------------------------------------- usable_digest


def asset(digest: str | None) -> Asset:
    return Asset(id=1, size=1, digest=digest, updated_at="2026-11-15T00:30:00Z", download_url=ROLLING_JAR)


@pytest.mark.parametrize(
    ("digest", "usable"),
    [
        ("sha256:" + "ab" * 32, "ab" * 32),
        ("SHA256:" + "AB" * 32, "ab" * 32),
        ("sha256:" + "Ab" * 32, "ab" * 32),
        ("sha512:" + "ab" * 64, None),
        ("md5:" + "ab" * 16, None),
        ("ab" * 32, None),
        (None, None),
    ],
)
def test_usable_digest(digest: str | None, usable: str | None) -> None:
    assert usable_digest(asset(digest)) == usable


@pytest.mark.parametrize("digest", ["sha256:" + "ab" * 31, "sha256:" + "ab" * 33, "sha256:" + "g" * 64, "sha256:"])
def test_a_sha256_digest_of_the_wrong_shape_matches_no_hash(digest: str) -> None:
    usable = usable_digest(asset(digest))
    assert usable is not None
    assert len(usable) != 64 or not all(c in "0123456789abcdef" for c in usable)
