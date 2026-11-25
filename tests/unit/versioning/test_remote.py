"""The release list, its cache and the fresh lookups (design 12 V8, 01 T6, inventory rows T7, T21, T22, T23, T26).

Against the real client with ``responses`` serving the recordings (01 T1) and the injected clock (T4).
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
import responses

from tests.github import BASE
from tests.unit.versioning.conftest import recorded_list
from tlaup.errors import NetworkError, RateLimited, RemoteDataError, VersionNotFound
from tlaup.versioning.remote import Freshness, Remote, parse_release, write_cache
from tlaup.versioning.spec import parse_version_spec

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.clock import FakeClock
    from tests.github import GitHubFake
    from tlaup.versioning.github import GitHubClient

    GitHub = Callable[..., GitHubFake]
    MakeClient = Callable[..., GitHubClient]

URL = f"{BASE}/releases"
MINUTE = 60.0


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "remote"


@pytest.fixture
def remote(make_client: MakeClient, cache_dir: Path, clock: FakeClock) -> Remote:
    return Remote(make_client(), cache_dir, now=clock.now)


def files(cache_dir: Path) -> list[Path]:
    return sorted(cache_dir.iterdir()) if cache_dir.exists() else []


def seed_cache(cache_dir: Path, clock: FakeClock, *, minutes_old: float, url: str = URL) -> Path:
    """The cache file the step "the release list is cached from <recording>, <n> minutes old" writes."""
    write_cache(cache_dir, url, recorded_list(), clock.now() - timedelta(minutes=minutes_old))
    (path,) = files(cache_dir)
    return path


def serve(github: GitHubFake, path: str, body: Any, status: int = 200) -> None:
    """An answer for one path that wins over the recording."""
    github.mock.registered().insert(0, responses.Response("GET", BASE + path, json=body, status=status))


def jarless_entry() -> dict[str, Any]:
    entry = next(item for item in recorded_list() if item["tag_name"] == "v1.5.5")
    assert entry["assets"] and all(a["name"] != "tla2tools.jar" for a in entry["assets"])
    return entry


# ---------------------------------------------------------------------- the list and its cache


def test_the_cache_serves_at_59_minutes_and_asks_again_at_61_row_t22(
    github: GitHub, remote: Remote, clock: FakeClock
) -> None:
    fake = github()
    first, freshness = remote.releases()
    assert (len(first), freshness) == (17, Freshness.ONLINE)
    assert len(fake.requests) == 1
    clock.advance(59 * MINUTE)
    again, freshness = remote.releases()
    assert (again, freshness) == (first, Freshness.CACHED)
    assert len(fake.requests) == 1
    clock.advance(2 * MINUTE)
    _, freshness = remote.releases()
    assert freshness is Freshness.ONLINE
    assert len(fake.requests) == 2


def test_max_age_zero_always_asks(github: GitHub, remote: Remote) -> None:
    fake = github()
    remote.releases()
    _, freshness = remote.releases(max_age=0)
    assert freshness is Freshness.ONLINE
    assert len(fake.requests) == 2


@pytest.mark.parametrize(
    "content", ["not json", "[1, 2]", '{"schema": 2, "url": "u", "fetched_at": "x", "data": []}', ""]
)
def test_a_damaged_cache_file_is_absent_row_t23(
    github: GitHub, remote: Remote, cache_dir: Path, clock: FakeClock, content: str
) -> None:
    fake = github()
    path = seed_cache(cache_dir, clock, minutes_old=1)
    path.write_text(content, encoding="utf-8")
    assert remote.cached() is None
    releases, freshness = remote.releases()
    assert (len(releases), freshness) == (17, Freshness.ONLINE)
    assert len(fake.requests) == 1
    assert remote.cached() == releases  # the next successful fetch replaced the file


def test_a_cache_file_with_an_unreadable_release_is_absent_row_t23(
    github: GitHub, remote: Remote, cache_dir: Path, clock: FakeClock
) -> None:
    github()
    write_cache(cache_dir, URL, [{"tag_name": "v1"}], clock.now())
    assert remote.cached() is None
    assert remote.releases()[1] is Freshness.ONLINE


def test_two_base_addresses_do_not_share_a_cache_file(
    github: GitHub, make_client: MakeClient, cache_dir: Path, clock: FakeClock
) -> None:
    fake = github()
    Remote(make_client(), cache_dir, now=clock.now).releases()
    other = Remote(make_client("https://api.github.com/repos/someone/else"), cache_dir, now=clock.now)
    assert other.cached() is None
    fake.unreachable()
    assert other.releases() == ([], Freshness.UNAVAILABLE)
    assert len(files(cache_dir)) == 1


def test_the_network_failing_with_a_cache_gives_the_old_list_stale_row_t22(
    github: GitHub, remote: Remote, cache_dir: Path, clock: FakeClock
) -> None:
    fake = github()
    seed_cache(cache_dir, clock, minutes_old=120)
    fake.unreachable()
    releases, freshness = remote.releases()
    assert (len(releases), freshness) == (17, Freshness.STALE)


def test_the_network_failing_with_no_cache_gives_an_empty_list_unavailable_row_t22(
    github: GitHub, remote: Remote, cache_dir: Path
) -> None:
    github().unreachable()
    assert remote.releases() == ([], Freshness.UNAVAILABLE)
    assert files(cache_dir) == []


def test_the_list_is_cached_as_it_came_back_row_t21(github: GitHub, remote: Remote, cache_dir: Path) -> None:
    github()
    releases, _ = remote.releases()
    (path,) = files(cache_dir)
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["schema"] == 1
    assert record["url"] == URL
    assert record["fetched_at"] == "2026-11-15T00:00:00Z"
    assert [item["tag_name"] for item in record["data"]] == [item["tag_name"] for item in recorded_list()]
    assert all(set(a) == set(b) for a, b in zip(record["data"], recorded_list(), strict=True))
    assert sum(r.asset is None for r in releases) == 7
    assert sum(not any(a["name"] == "tla2tools.jar" for a in item["assets"]) for item in record["data"]) == 7
    assert remote.cached() == releases


def test_the_cache_file_is_named_by_the_address(github: GitHub, remote: Remote, cache_dir: Path) -> None:
    github()
    remote.releases()
    (path,) = files(cache_dir)
    assert path.name == hashlib.sha256(URL.encode()).hexdigest()[:16] + ".json"


@pytest.mark.parametrize("answer", ["404", "503", "rate-limit", "not a list"])
def test_an_error_answer_is_never_cached(
    github: GitHub, make_client: MakeClient, cache_dir: Path, clock: FakeClock, answer: str
) -> None:
    fake = github("rate-limited" if answer == "rate-limit" else "releases")
    remote = Remote(make_client(attempts=1), cache_dir, now=clock.now)

    def fail() -> None:
        if answer in ("404", "503"):
            fake.answer(int(answer), "/releases")
        elif answer == "not a list":
            serve(fake, "/releases", {"message": "hello"})

    # with no cache file: nothing is written
    fail()
    assert remote.releases() == ([], Freshness.UNAVAILABLE)
    assert files(cache_dir) == []

    # with one: it is left byte for byte
    path = seed_cache(cache_dir, clock, minutes_old=120)
    before = path.read_bytes()
    fake.clear()
    fail()
    releases, freshness = remote.releases()
    assert (len(releases), freshness) == (17, Freshness.STALE)
    assert files(cache_dir) == [path]
    assert path.read_bytes() == before


def test_a_list_with_an_unreadable_release_is_not_cached(github: GitHub, remote: Remote, cache_dir: Path) -> None:
    fake = github()
    serve(fake, "/releases", [{"tag_name": "v1"}])
    assert remote.releases() == ([], Freshness.UNAVAILABLE)
    assert files(cache_dir) == []


def test_cached_without_a_file_is_none(remote: Remote) -> None:
    assert remote.cached() is None


def test_cached_returns_a_day_old_list_without_a_request(
    github: GitHub, remote: Remote, cache_dir: Path, clock: FakeClock
) -> None:
    fake = github()
    seed_cache(cache_dir, clock, minutes_old=24 * 60)
    cached = remote.cached()
    assert cached is not None
    assert len(cached) == 17
    assert len(fake.requests) == 0


def test_the_cache_file_is_one_file_per_address_after_a_write(github: GitHub, remote: Remote, cache_dir: Path) -> None:
    github()
    remote.releases()
    remote.releases(max_age=0)
    remote.releases(max_age=0)
    assert len(files(cache_dir)) == 1
    assert files(cache_dir)[0].suffix == ".json"


def test_the_paged_recording_gives_the_same_releases(
    github: GitHub, make_client: MakeClient, cache_dir: Path, clock: FakeClock, tmp_path: Path
) -> None:
    github()
    plain, _ = Remote(make_client(), cache_dir, now=clock.now).releases()
    other = tmp_path / "other"
    paged_fake = github("releases-paged")
    paged, freshness = Remote(make_client(), other, now=clock.now).releases()
    assert freshness is Freshness.ONLINE
    assert paged == plain
    assert len(paged_fake.requests) >= 2


def test_flags_and_dates_are_those_of_the_recording_row_t26(github: GitHub, remote: Remote) -> None:
    github()
    fresh, _ = remote.releases()
    clock_cached = remote.cached()
    assert clock_cached == fresh
    by_tag = {r.tag: r for r in fresh}
    assert (by_tag["rolling"].prerelease, by_tag["v1.8.0"].prerelease, by_tag["v1.7.4"].prerelease) == (
        True,
        True,
        False,
    )
    for item in recorded_list():
        got = by_tag[item["tag_name"]]
        assert got.published_at == item["published_at"]
        assert got.created_at == item["created_at"]
        assert got.draft is item["draft"]
        jar = next((a for a in item["assets"] if a["name"] == "tla2tools.jar"), None)
        if jar is None:
            assert got.asset is None
        else:
            assert got.asset is not None
            assert got.asset.updated_at == jar["updated_at"]
            assert got.asset.download_url == jar["browser_download_url"]
            assert got.asset.id == jar["id"]


# ---------------------------------------------------------------------- one release, fresh


def test_a_404_on_a_tag_is_version_not_found_and_writes_nothing_row_t6(
    github: GitHub, remote: Remote, cache_dir: Path
) -> None:
    github().answer(404, "/releases/tags/nosuch")
    with pytest.raises(VersionNotFound):
        remote.release("nosuch")
    assert files(cache_dir) == []


def test_release_neither_reads_nor_writes_the_cache(
    github: GitHub, remote: Remote, cache_dir: Path, clock: FakeClock
) -> None:
    fake = github()
    path = seed_cache(cache_dir, clock, minutes_old=1)
    before = path.read_bytes()
    found = remote.release("v1.7.4")
    assert found.tag == "v1.7.4"
    assert len(fake.requests) == 1
    assert files(cache_dir) == [path]
    assert path.read_bytes() == before


def test_a_tag_with_a_slash_is_percent_encoded(github: GitHub, remote: Remote) -> None:
    fake = github()
    entry = dict(jarless_entry(), tag_name="release/1.9")
    serve(fake, "/releases/tags/release%2F1.9", entry)
    assert remote.release("release/1.9").tag == "release/1.9"
    assert fake.requests[-1].url == f"{BASE}/releases/tags/release%2F1.9"


def test_other_errors_of_a_lookup_are_the_clients(github: GitHub, remote: Remote) -> None:
    github().answer(401, "/releases/tags/v1.7.4")
    with pytest.raises(NetworkError):
        remote.release("v1.7.4")


# ---------------------------------------------------------------------- resolve


def test_resolve_stable_refreshes_the_list_even_with_a_young_cache(
    github: GitHub, remote: Remote, cache_dir: Path, clock: FakeClock
) -> None:
    fake = github()
    seed_cache(cache_dir, clock, minutes_old=1)
    chosen = remote.resolve(parse_version_spec("stable"))
    assert chosen.tag == "v1.7.4"
    assert len(fake.requests) == 1


def test_resolve_stable_raises_the_network_error_and_never_answers_from_stale_data(
    github: GitHub, remote: Remote, cache_dir: Path, clock: FakeClock
) -> None:
    fake = github()
    seed_cache(cache_dir, clock, minutes_old=1)
    fake.unreachable()
    with pytest.raises(NetworkError):
        remote.resolve(parse_version_spec("stable"))


def test_resolve_stable_when_rate_limited_raises_rate_limited(
    github: GitHub, make_client: MakeClient, cache_dir: Path, clock: FakeClock
) -> None:
    github("rate-limited")
    remote = Remote(make_client(attempts=1), cache_dir, now=clock.now)
    with pytest.raises(RateLimited):
        remote.resolve(parse_version_spec("stable"))


def test_resolve_a_tag_looks_it_up_fresh(github: GitHub, remote: Remote, cache_dir: Path, clock: FakeClock) -> None:
    fake = github()
    seed_cache(cache_dir, clock, minutes_old=1)
    chosen = remote.resolve(parse_version_spec("rolling"))
    assert chosen.tag == "rolling"
    assert chosen.prerelease is True
    assert [r.url.split("?")[0] for r in fake.requests] == [f"{BASE}/releases/tags/rolling"]


def test_resolve_tries_the_name_as_typed_then_with_v(github: GitHub, remote: Remote) -> None:
    fake = github()
    fake.answer(404, "/releases/tags/1.7.4")
    assert remote.resolve(parse_version_spec("1.7.4")).tag == "v1.7.4"


def test_resolve_tries_foo_then_vfoo_and_the_error_names_foo(github: GitHub, remote: Remote) -> None:
    fake = github()
    fake.answer(404, "/releases/tags/foo")
    fake.answer(404, "/releases/tags/vfoo")
    with pytest.raises(VersionNotFound) as error:
        remote.resolve(parse_version_spec("foo"))
    assert "'foo'" in error.value.message
    assert [r.url.split("/")[-1] for r in fake.requests] == ["foo", "vfoo"]


def test_resolve_a_tag_nobody_published_is_version_not_found(github: GitHub, remote: Remote) -> None:
    fake = github()
    fake.answer(404, "/releases/tags/v9.9.9")
    fake.answer(404, "/releases/tags/vv9.9.9")
    with pytest.raises(VersionNotFound):
        remote.resolve(parse_version_spec("v9.9.9"))


def test_a_release_without_the_jar_is_listed_but_never_resolved_row_t6(github: GitHub, remote: Remote) -> None:
    fake = github()
    listed, _ = remote.releases()
    without = [r for r in listed if r.asset is None]
    assert len(without) == 7
    assert {r.tag for r in without} >= {"v1.4.8", "v1.5.5"}
    serve(fake, "/releases/tags/v1.5.5", jarless_entry())
    assert remote.release("v1.5.5").asset is None
    with pytest.raises(VersionNotFound) as error:
        remote.resolve(parse_version_spec("v1.5.5"))
    assert "tla2tools.jar" in error.value.message


def test_when_every_release_is_a_prerelease_there_is_no_stable_row_t7(github: GitHub, remote: Remote) -> None:
    fake = github()
    everything = [dict(item, prerelease=True) for item in recorded_list()]
    serve(fake, "/releases", everything)
    with pytest.raises(VersionNotFound):
        remote.resolve(parse_version_spec("stable"))


def test_a_build_time_alone_names_no_release(remote: Remote) -> None:
    with pytest.raises(VersionNotFound):
        remote.resolve(parse_version_spec("2026.11.15.002146"))


# ---------------------------------------------------------------------- what GitHub sends


def test_a_list_where_a_release_is_expected_is_remote_data_error(github: GitHub, remote: Remote) -> None:
    serve(github(), "/releases/tags/v1.7.4", recorded_list())
    with pytest.raises(RemoteDataError):
        remote.release("v1.7.4")


def test_a_release_without_a_tag_name_is_remote_data_error() -> None:
    item = {k: v for k, v in recorded_list()[0].items() if k != "tag_name"}
    with pytest.raises(RemoteDataError):
        parse_release(item, url="https://example.invalid/r")


def test_an_asset_without_a_size_is_remote_data_error() -> None:
    item = next(i for i in recorded_list() if i["tag_name"] == "v1.7.4")
    broken = json.loads(json.dumps(item))
    for asset in broken["assets"]:
        if asset["name"] == "tla2tools.jar":
            del asset["size"]
    with pytest.raises(RemoteDataError) as error:
        parse_release(broken, url="https://example.invalid/r")
    assert "https://example.invalid/r" in error.value.message


@pytest.mark.parametrize(
    ("field", "value"), [("draft", "no"), ("assets", None), ("created_at", 5), ("prerelease", None)]
)
def test_a_field_of_the_wrong_type_is_remote_data_error(field: str, value: object) -> None:
    item = dict(recorded_list()[0], **{field: value})
    with pytest.raises(RemoteDataError):
        parse_release(item, url="https://example.invalid/r")


def test_a_flag_is_not_a_size() -> None:
    item = json.loads(json.dumps(next(i for i in recorded_list() if i["tag_name"] == "v1.7.4")))
    for asset in item["assets"]:
        if asset["name"] == "tla2tools.jar":
            asset["size"] = True
    with pytest.raises(RemoteDataError):
        parse_release(item, url="https://example.invalid/r")


# ---------------------------------------------------------------------- the cache's edges


def test_a_cache_write_failing_is_ignored_and_the_list_is_online(
    github: GitHub, make_client: MakeClient, tmp_path: Path, clock: FakeClock
) -> None:
    github()
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where the cache folder should be", encoding="utf-8")
    releases, freshness = Remote(make_client(), blocked, now=clock.now).releases()
    assert (len(releases), freshness) == (17, Freshness.ONLINE)


def test_a_cache_file_for_another_url_is_absent(remote: Remote, cache_dir: Path, clock: FakeClock) -> None:
    path = seed_cache(cache_dir, clock, minutes_old=1)
    record = json.loads(path.read_text(encoding="utf-8"))
    record["url"] = "https://api.github.com/repos/someone/else/releases"
    path.write_text(json.dumps(record), encoding="utf-8")
    assert remote.cached() is None


def test_a_null_or_absent_digest_and_a_null_published_at_parse() -> None:
    item = json.loads(json.dumps(next(i for i in recorded_list() if i["tag_name"] == "v1.7.4")))
    item["published_at"] = None
    jar = next(a for a in item["assets"] if a["name"] == "tla2tools.jar")
    jar["digest"] = None
    assert parse_release(item, url="u").published_at is None
    assert parse_release(item, url="u").asset.digest is None  # type: ignore[union-attr]
    del jar["digest"]
    assert parse_release(item, url="u").asset.digest is None  # type: ignore[union-attr]
