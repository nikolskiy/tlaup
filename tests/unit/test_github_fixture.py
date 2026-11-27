"""The ``github`` fixture, on ``requests`` directly, which is the edge itself (design 01 T4)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from typing import TYPE_CHECKING, Any

import pytest
import requests

from tests.github import BASE, RECORDINGS, load_recording

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.github import GitHubFake

    Github = Callable[..., GitHubFake]

TAGS = ("rolling", "v1.8.0", "v1.7.4")
TIMEOUT = 5


def get(url: str, **kwargs: Any) -> requests.Response:
    return requests.get(url, timeout=TIMEOUT, **kwargs)


def jar_asset(release: dict[str, Any]) -> dict[str, Any]:
    return next(a for a in release["assets"] if a["name"] == "tla2tools.jar")


@pytest.mark.parametrize("name", ["releases", "releases-paged", "rate-limited"])
def test_each_recording_loads_and_is_served_with_its_status(github: Github, name: str) -> None:
    github(name)
    for method, url, recorded in load_recording(name):
        assert requests.request(method, url, timeout=TIMEOUT).status_code == recorded.status


def test_releases_list_and_tag_objects(github: Github) -> None:
    fake = github("releases")
    expected_count = len(json.loads((RECORDINGS / "releases" / "list.body").read_bytes()))
    recorded_digests = {
        tag: jar_asset(json.loads((RECORDINGS / "releases" / f"tag-{tag}.body").read_bytes()))["digest"] for tag in TAGS
    }
    listed = get(f"{BASE}/releases?per_page=100").json()
    assert isinstance(listed, list)
    assert len(listed) == expected_count
    assert all("updated_at" in a for r in listed for a in r["assets"])
    for tag in TAGS:
        release = get(f"{BASE}/releases/tags/{tag}").json()
        asset = jar_asset(release)
        jar = fake.jar(tag)
        assert asset["size"] == jar.stat().st_size
        if recorded_digests[tag] is None:
            assert asset["digest"] is None
        else:
            assert asset["digest"] == "sha256:" + hashlib.sha256(jar.read_bytes()).hexdigest()
        assert all("updated_at" in a for a in release["assets"])
        in_list = next(r for r in listed if r["tag_name"] == tag)
        assert jar_asset(in_list) == asset
    assert recorded_digests["v1.7.4"] is None


def test_releases_paged(github: Github) -> None:
    github("releases-paged")
    first = get(f"{BASE}/releases", params={"per_page": 100})
    link = first.headers["link"]
    assert 'rel="next"' in link
    next_url = link.split(">")[0].lstrip("<")
    second = get(next_url)
    assert second.status_code == 200
    assert 'rel="next"' not in second.headers["link"]
    assert first.json()[0]["tag_name"] != second.json()[0]["tag_name"]
    assert get(next_url).json() == second.json()  # asking again gives page 2 again


def test_rate_limited(github: Github) -> None:
    github("rate-limited")
    response = get(f"{BASE}/releases/tags/rolling")
    assert response.status_code == 403
    assert get("https://api.github.com/repos/other/thing").status_code == 403
    assert response.headers["x-ratelimit-remaining"] == "0"
    assert "x-ratelimit-reset" in response.headers
    assert "retry-after" not in response.headers


def test_jar_download_returns_the_small_jar_and_counts(github: Github) -> None:
    fake = github()
    release = get(f"{BASE}/releases/tags/v1.8.0").json()
    assert fake.downloads == 0
    response = get(jar_asset(release)["browser_download_url"])
    assert response.content == fake.jar("v1.8.0").read_bytes()
    assert fake.downloads == 1


def test_other_tags_jars_are_not_answered(github: Github) -> None:
    github()
    with pytest.raises(requests.ConnectionError):
        get("https://github.com/tlaplus/tlaplus/releases/download/v1.0.0/tla2tools.jar")


def test_requests_list_headers_and_clear(github: Github) -> None:
    fake = github()
    get(f"{BASE}/releases")
    get(f"{BASE}/releases/tags/rolling", headers={"Authorization": "Bearer x"})
    assert [r.method for r in fake.requests] == ["GET", "GET"]
    assert [r.url for r in fake.requests] == [f"{BASE}/releases", f"{BASE}/releases/tags/rolling"]
    assert "Authorization" not in fake.requests[0].headers
    assert "Authorization" in fake.requests[1].headers
    fake.clear()
    assert fake.requests == []


def test_unregistered_address_fails_under_disable_socket(github: Github) -> None:
    github()
    with pytest.raises(requests.ConnectionError):
        get("https://example.invalid/")


def test_unreachable_and_answer(github: Github) -> None:
    fake = github()
    fake.answer(404, "/releases/tags/v9.9.9")
    assert get(f"{BASE}/releases/tags/v9.9.9").status_code == 404
    assert get(f"{BASE}/releases/tags/rolling").status_code == 200
    fake.unreachable()
    with pytest.raises(requests.ConnectionError):
        get(f"{BASE}/releases/tags/rolling")


def test_unreachable_refuses_every_later_request(github: Github) -> None:
    fake = github()
    url = jar_asset(get(f"{BASE}/releases/tags/rolling").json())["browser_download_url"]
    fake.unreachable()
    for address in (f"{BASE}/releases/tags/rolling", f"{BASE}/releases/tags/rolling", url):
        with pytest.raises(requests.ConnectionError):
            get(address)


def test_answer_wins_over_the_recording(github: Github) -> None:
    fake = github()
    fake.answer(500, "/releases/tags/rolling")
    assert get(f"{BASE}/releases/tags/rolling").status_code == 500


def test_tool_repository_is_not_set_inside_the_fixture(github: Github) -> None:
    github()
    assert "TLAUP_TOOL_REPOSITORY" not in os.environ


def test_tool_repository_is_the_closed_port_without_the_fixture() -> None:
    assert os.environ["TLAUP_TOOL_REPOSITORY"].startswith("https://127.0.0.1:9/")


def test_recording_script_help_exits_zero() -> None:
    script = RECORDINGS.parents[2] / "scripts" / "record_github.py"
    done = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, check=False, timeout=60)
    assert done.returncode == 0


def test_served_headers_leave_out_what_requests_computes(github: Github) -> None:
    github()
    response = get(f"{BASE}/releases")
    assert "content-encoding" not in response.headers
    assert "transfer-encoding" not in response.headers
    assert response.json()  # the body reads whole: no ChunkedEncodingError from a recorded length


def test_unreachable_covers_other_methods_and_downloads_and_is_listed(github: Github) -> None:
    fake = github()
    url = jar_asset(get(f"{BASE}/releases/tags/rolling").json())["browser_download_url"]
    fake.clear()
    fake.unreachable()
    for attempt in (
        lambda: requests.head(f"{BASE}/releases", timeout=TIMEOUT),
        lambda: requests.post(f"{BASE}/releases", timeout=TIMEOUT),
        lambda: get(url),
    ):
        with pytest.raises(requests.ConnectionError):
            attempt()
    assert [r.method for r in fake.requests] == ["HEAD", "POST", "GET"]


def test_page_two_query_is_not_answered_with_page_one(github: Github) -> None:
    github("releases-paged")
    page1 = get(f"{BASE}/releases", params={"per_page": 10}).json()
    with pytest.raises(requests.ConnectionError):
        get(f"{BASE}/releases", params={"page": 2})
    assert page1


@pytest.mark.parametrize(("tag", "repl"), [("rolling", True), ("v1.8.0", True), ("v1.7.4", False)])
def test_small_jars_hold_the_repl_class_as_recorded(github: Github, tag: str, repl: bool) -> None:
    with zipfile.ZipFile(github().jar(tag)) as jar:
        assert ("tlc2/REPL.class" in jar.namelist()) is repl
