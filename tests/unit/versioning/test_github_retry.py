"""The GitHub client's retries, rate limit, paging, bad answers and downloads (design 12 V7, 01 T6).

Against the real client with ``responses``; the error type and the requests made, never the message.
"""

from __future__ import annotations

import hashlib
import io
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import responses

from tests.github import BASE
from tests.unit.versioning.conftest import TOKEN, secret_free
from tlaup.errors import DownloadVerificationError, NetworkError, RateLimited, RemoteDataError
from tlaup.versioning.github import token_from_env

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.clock import FakeClock
    from tests.github import GitHubFake
    from tlaup.versioning.github import GitHubClient

    MakeClient = Callable[..., GitHubClient]
    GitHub = Callable[..., GitHubFake]

ROLLING = BASE + "/releases/tags/rolling"
USER = "someone"  # a user part, written so that no line holds a user@host address
ROLLING_JAR = "https://github.com/tlaplus/tlaplus/releases/download/rolling/tla2tools.jar"
PAGE_2 = "https://api.github.com/repositories/50906927/releases?per_page=10&page=2"


def query(request: requests.PreparedRequest) -> dict[str, list[str]]:
    return parse_qs(urlsplit(request.url or "").query)


def ahead(fake: GitHubFake, *answers: responses.BaseResponse) -> None:
    """Answers that win over the recording, served in the order given."""
    for answer in reversed(answers):
        fake.mock.registered().insert(0, answer)


# --- rate limit ---


def test_the_recorded_rate_limit_is_raised_at_once(github: GitHub, make_client: MakeClient, clock: FakeClock) -> None:
    fake = github("rate-limited")
    with pytest.raises(RateLimited) as caught:
        make_client().get_json("/releases")
    assert caught.value.reset_at == datetime.fromtimestamp(1795078778, tz=UTC)
    assert len(fake.requests) == 1
    assert clock.sleeps == []


def test_a_429_with_retry_after_is_raised_at_once(github: GitHub, make_client: MakeClient, clock: FakeClock) -> None:
    # Synthetic: a real 429 was never obtained (research 29); Retry-After is read against the answer's Date.
    fake = github("releases")
    ahead(
        fake,
        responses.Response(
            "GET", ROLLING, status=429, json={"message": "slow down"},
            headers={"Retry-After": "120", "Date": "Wed, 25 Nov 2026 06:12:14 GMT"},
        ),
    )  # fmt: skip
    with pytest.raises(RateLimited) as caught:
        make_client(token=TOKEN).get_json("/releases/tags/rolling")
    assert caught.value.reset_at == datetime(2026, 11, 25, 6, 14, 14, tzinfo=UTC)
    assert len(fake.requests) == 1
    assert clock.sleeps == []
    assert secret_free(caught.value, TOKEN)


def rate_limited(headers: dict[str, str]) -> responses.Response:
    return responses.Response("GET", ROLLING, status=403, json={"message": "limited"}, headers=headers)


def test_a_date_with_no_zone_is_utc_whatever_the_machine_zone(
    github: GitHub, make_client: MakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is not available on Windows")
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    fake = github("releases")
    ahead(fake, rate_limited({"Retry-After": "120", "Date": "Wed, 25 Nov 2026 06:12:14 -0000"}))
    with pytest.raises(RateLimited) as caught:
        make_client().get_json("/releases/tags/rolling")
    assert caught.value.reset_at == datetime(2026, 11, 25, 6, 14, 14, tzinfo=UTC)


def test_retry_after_wins_while_the_allowance_is_not_used_up(github: GitHub, make_client: MakeClient) -> None:
    # Synthetic: a secondary limit, with the primary allowance left; x-ratelimit-reset is not its reset time.
    fake = github("releases")
    headers = {
        "x-ratelimit-remaining": "12",
        "x-ratelimit-reset": "1795078778",
        "Retry-After": "60",
        "Date": "Wed, 25 Nov 2026 06:12:14 GMT",
    }
    ahead(fake, rate_limited(headers))
    with pytest.raises(RateLimited) as caught:
        make_client().get_json("/releases/tags/rolling")
    assert caught.value.reset_at == datetime(2026, 11, 25, 6, 13, 14, tzinfo=UTC)


def test_a_rate_limit_off_the_token_hosts_hints_at_the_setting(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    other = "https://git.example.org/api/v3/repos/tlaplus/tlaplus"
    fake.mock.add(
        responses.GET, other + "/x", status=403, json={"message": "limited"},
        headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1795078778"},
    )  # fmt: skip
    with pytest.raises(RateLimited) as caught:
        make_client(other, token=TOKEN).get_json("/x")
    assert caught.value.hint is not None
    assert "tool.token_hosts" in caught.value.hint
    assert secret_free(caught.value, TOKEN)


def test_a_403_without_rate_limit_headers_is_a_plain_error(
    github: GitHub, make_client: MakeClient, clock: FakeClock
) -> None:
    fake = github("releases")
    ahead(fake, responses.Response("GET", ROLLING, status=403, json={"message": "secondary limit"}))
    with pytest.raises(NetworkError) as caught:
        make_client().get_json("/releases/tags/rolling")
    assert not isinstance(caught.value, RateLimited)
    assert caught.value.status == 403
    assert len(fake.requests) == 1
    assert clock.sleeps == []


# --- retry ---


def test_a_500_then_a_200_succeeds_after_one_retry(github: GitHub, make_client: MakeClient, clock: FakeClock) -> None:
    fake = github("releases")
    ahead(fake, responses.Response("GET", ROLLING, status=500, body=b""))
    data, _ = make_client().get_json("/releases/tags/rolling")
    assert data["tag_name"] == "rolling"
    assert len(fake.requests) == 2
    assert clock.sleeps == [1]


def test_three_failing_answers_give_two_sleeps_then_network_error(
    github: GitHub, make_client: MakeClient, clock: FakeClock
) -> None:
    fake = github("releases")
    ahead(fake, *(responses.Response("GET", ROLLING, status=503, body=b"") for _ in range(3)))
    with pytest.raises(NetworkError) as caught:
        make_client(token=TOKEN).get_json("/releases/tags/rolling")
    assert caught.value.status == 503
    assert len(fake.requests) == 3
    assert clock.sleeps == [1, 2]
    assert secret_free(caught.value, TOKEN)


def test_the_waits_double_for_more_attempts(github: GitHub, make_client: MakeClient, clock: FakeClock) -> None:
    fake = github("releases")
    ahead(fake, *(responses.Response("GET", ROLLING, body=requests.ConnectionError("down")) for _ in range(5)))
    with pytest.raises(NetworkError):
        make_client(attempts=5).get_json("/releases/tags/rolling")
    assert len(fake.requests) == 5
    assert clock.sleeps == [1, 2, 4, 8]


def test_a_connection_that_fails_before_any_answer_is_retried(
    github: GitHub, make_client: MakeClient, clock: FakeClock
) -> None:
    fake = github("releases")
    ahead(fake, *(responses.Response("GET", ROLLING_JAR, body=requests.ConnectionError("down")) for _ in range(3)))
    with pytest.raises(NetworkError) as caught:
        make_client().download(ROLLING_JAR, io.BytesIO())
    assert caught.value.status is None
    assert len(fake.requests) == 3
    assert clock.sleeps == [1, 2]


def test_a_timeout_is_retried(github: GitHub, make_client: MakeClient, clock: FakeClock) -> None:
    fake = github("releases")
    ahead(fake, responses.Response("GET", ROLLING, body=requests.exceptions.ReadTimeout("slow")))
    data, _ = make_client().get_json("/releases/tags/rolling")
    assert data["tag_name"] == "rolling"
    assert len(fake.requests) == 2
    assert clock.sleeps == [1]


def test_a_404_is_not_retried_and_carries_its_status(github: GitHub, make_client: MakeClient, clock: FakeClock) -> None:
    fake = github("releases")
    fake.answer(404, "/releases/tags/nothing")
    with pytest.raises(NetworkError) as caught:
        make_client().get_json("/releases/tags/nothing")
    assert caught.value.status == 404
    assert len(fake.requests) == 1
    assert clock.sleeps == []


# --- bad answers ---


def test_a_body_that_is_not_json_is_remote_data_error(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    ahead(fake, responses.Response("GET", ROLLING, body=b"<html>a proxy</html>", content_type="text/html"))
    with pytest.raises(RemoteDataError) as caught:
        make_client(token=TOKEN).get_json("/releases/tags/rolling")
    assert len(fake.requests) == 1
    assert secret_free(caught.value, TOKEN)


def test_a_page_that_is_not_a_list_is_remote_data_error(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    ahead(fake, responses.Response("GET", BASE + "/releases", json={"message": "an object"}))
    with pytest.raises(RemoteDataError) as caught:
        make_client(token=TOKEN).get_paged("/releases")
    assert len(fake.requests) == 1
    assert secret_free(caught.value, TOKEN, "per_page")


def test_get_json_returns_a_list_or_an_object_as_it_came(github: GitHub, make_client: MakeClient) -> None:
    github("releases")
    data, headers = make_client().get_json("/releases")
    assert isinstance(data, list)
    assert len(data) == 17
    assert headers["x-ratelimit-limit"] == "60"


# --- paging ---


def test_two_pages_of_releases_are_read_following_the_link_as_given(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases-paged")
    releases = make_client().get_paged("/releases")
    assert len(releases) == 17
    assert len({r["id"] for r in releases}) == 17
    first, second = fake.requests
    assert query(first) == {"per_page": ["100"]}
    assert second.url == PAGE_2


@pytest.mark.parametrize(
    "following",
    [
        "https://elsewhere.example/repositories/50906927/releases?page=2",
        "https://api.github.com:8443/repositories/50906927/releases?page=2",
        "http://api.github.com/repositories/50906927/releases?page=2",
        "https://other.example\\@api.github.com/x",
        f"https://{USER}@api.github.com/x",
    ],
)
def test_a_next_page_off_the_host_or_not_https_is_not_followed(
    following: str, github: GitHub, make_client: MakeClient
) -> None:
    fake = github("releases")
    ahead(fake, responses.Response("GET", BASE + "/releases", json=[], headers={"Link": f'<{following}>; rel="next"'}))
    fake.mock.add(responses.GET, following.replace("\\", ""), json=[])
    with pytest.raises(RemoteDataError) as caught:
        make_client(token=TOKEN).get_paged("/releases")
    assert len(fake.requests) == 1
    assert secret_free(caught.value, TOKEN, "page=2")


def test_more_than_fifty_pages_is_an_error(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")

    def page(request: requests.PreparedRequest) -> tuple[int, dict[str, str], bytes]:
        n = int(query(request).get("page", ["1"])[0])
        return 200, {"Link": f'<{BASE}/many?per_page=100&page={n + 1}>; rel="next"'}, b"[1]"

    fake.mock.add(responses.CallbackResponse("GET", BASE + "/many", callback=page))
    with pytest.raises(RemoteDataError):
        make_client().get_paged("/many")
    assert len(fake.requests) == 50


# --- download ---


def test_a_download_writes_the_body_and_reports_it(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    body = fake.jar("rolling").read_bytes()
    ahead(fake, responses.Response("GET", ROLLING_JAR, body=body, auto_calculate_content_length=True))
    dest = io.BytesIO()
    seen: list[tuple[int, int | None]] = []
    info = make_client().download(ROLLING_JAR, dest, lambda done, total: seen.append((done, total)))
    assert dest.getvalue() == body
    assert info.size == len(body)
    assert info.content_length == len(body)
    assert info.sha256 == hashlib.sha256(body).hexdigest()
    assert seen[-1] == (len(body), len(body))
    assert not hasattr(info, "url")
    assert fake.downloads == 1


def test_a_download_without_content_length_reports_none(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    info = make_client().download(ROLLING_JAR, io.BytesIO())
    assert info.content_length is None
    assert info.size == fake.jar("rolling").stat().st_size


def test_a_download_stops_at_the_limit(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    ahead(fake, responses.Response("GET", ROLLING_JAR, body=b"x" * 200_000, auto_calculate_content_length=True))
    dest = io.BytesIO()
    info = make_client().download(ROLLING_JAR, dest, limit=1001)
    assert info.size == 1001
    assert dest.getvalue() == b"x" * 1001
    assert info.sha256 == hashlib.sha256(b"x" * 1001).hexdigest()
    assert info.content_length == 200_000


def test_a_body_shorter_than_its_content_length_is_verification_error(
    github: GitHub, make_client: MakeClient, clock: FakeClock
) -> None:
    fake = github("releases")
    ahead(
        fake,
        responses.Response(
            "GET", ROLLING_JAR, body=b"short", headers={"Content-Length": "100"}, auto_calculate_content_length=False
        ),
    )
    with pytest.raises(DownloadVerificationError):
        make_client().download(ROLLING_JAR, io.BytesIO())
    assert len(fake.requests) == 1
    assert clock.sleeps == []


# --- the token from the environment ---


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"GH_TOKEN": "a", "GITHUB_TOKEN": "b"}, "a"),
        ({"GITHUB_TOKEN": "b"}, "b"),
        ({"GH_TOKEN": "", "GITHUB_TOKEN": "b"}, "b"),
        ({"GH_TOKEN": "", "GITHUB_TOKEN": ""}, None),
        ({}, None),
    ],
)
def test_token_from_env_prefers_gh_token(env: dict[str, str], expected: str | None) -> None:
    assert token_from_env(env) == expected
