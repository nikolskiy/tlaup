"""The GitHub client's address and token rules, netrc, secrecy and inventory row T12 (design 12 V7, 01 T6).

Against the real client with ``responses`` (01 T1). Each test asserts the error type and the requests made,
never the message (T12 rule 4). The token is asserted on through ``has_token`` and ``has_authorization``, which
return a bool, so a failing assert never prints a header value.
"""

from __future__ import annotations

import io
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest
import requests
import responses

from tests.github import BASE
from tests.unit.versioning.conftest import (
    TOKEN,
    USER_AGENT,
    has_authorization,
    has_token,
    printable_only,
    secret_free,
)
from tlaup.errors import ConfigInvalid, NetworkError, RemoteDataError, TlaupError

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.github import GitHubFake
    from tlaup.versioning.github import GitHubClient

    MakeClient = Callable[..., GitHubClient]
    GitHub = Callable[..., GitHubFake]

USER = "someone"  # a user part, written so that no line holds a user@host address
USER_INFO = "someone:made-up-part"  # a user and password part, the same way
ROLLING_JAR = "https://github.com/tlaplus/tlaplus/releases/download/rolling/tla2tools.jar"
STORAGE = "https://release-assets.githubusercontent.com/github-production-release-asset/1/abc"
OTHER = "https://git.example.org/api/v3/repos/tlaplus/tlaplus"


def hosts(fake: GitHubFake) -> list[str]:
    return [(r.url or "").split("/")[2] for r in fake.requests]


def serve_redirect(fake: GitHubFake, source: str, target: str, status: int = 302) -> None:
    fake.mock.replace(responses.GET, source, status=status, headers={"Location": target}, body=b"")


# --- the token's hosts (D41) ---


def test_with_a_token_the_api_gets_it_and_the_download_does_not(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    client = make_client(token=TOKEN)
    release, _ = client.get_json("/releases/tags/rolling")
    client.download(release["assets"][0]["browser_download_url"], io.BytesIO())
    assert hosts(fake) == ["api.github.com", "github.com"]
    api, download = fake.requests
    assert has_token(api)
    assert not has_authorization(download)


def test_the_storage_host_of_a_redirect_gets_no_token(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    serve_redirect(fake, ROLLING_JAR, STORAGE + "?sig=secret-value")
    fake.mock.add(responses.GET, STORAGE, body=b"jar bytes")
    client = make_client(token=TOKEN)
    client.get_json("/releases")
    client.download(ROLLING_JAR, io.BytesIO())
    assert hosts(fake) == ["api.github.com", "github.com", "release-assets.githubusercontent.com"]
    assert has_token(fake.requests[0])
    assert not any(has_authorization(r) for r in fake.requests[1:])


def test_another_base_host_gets_no_token_unless_listed(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    fake.mock.add(responses.GET, OTHER + "/releases/tags/rolling", json={"tag_name": "rolling"})
    make_client(OTHER, token=TOKEN).get_json("/releases/tags/rolling")
    make_client(OTHER, token=TOKEN, token_hosts=["git.example.org"]).get_json("/releases/tags/rolling")
    unlisted, listed = fake.requests
    assert not has_authorization(unlisted)
    assert has_token(listed)


def test_a_redirect_to_an_unlisted_host_is_followed_without_the_token(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    serve_redirect(fake, BASE + "/releases/tags/rolling", "https://elsewhere.example/moved", status=301)
    fake.mock.add(responses.GET, "https://elsewhere.example/moved", json={"tag_name": "rolling"})
    data, _ = make_client(token=TOKEN).get_json("/releases/tags/rolling")
    assert data == {"tag_name": "rolling"}
    first, second = fake.requests
    assert has_token(first)
    assert not has_authorization(second)


@pytest.mark.parametrize(
    ("base", "carries"),
    [
        ("https://API.GitHub.com/repos/tlaplus/tlaplus", True),
        ("https://api.github.com:443/repos/tlaplus/tlaplus", True),
        ("https://api.github.com:8443/repos/tlaplus/tlaplus", False),
        ("https://api.github.com.evil.example/repos/tlaplus/tlaplus", False),
        ("https://github.com/repos/tlaplus/tlaplus", False),
    ],
)
def test_the_api_host_is_compared_whole_after_parsing(
    base: str, carries: bool, github: GitHub, make_client: MakeClient
) -> None:
    fake = github("releases")
    fake.mock.add(responses.GET, base.lower() + "/x", json={})
    make_client(base, token=TOKEN).get_json("/x")
    (request,) = fake.requests
    assert has_token(request) is carries
    assert has_authorization(request) is carries


def test_without_a_token_no_request_carries_authorization(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    client = make_client(token_hosts=["github.com"])
    client.get_json("/releases/tags/rolling")
    client.download(ROLLING_JAR, io.BytesIO())
    assert len(fake.requests) == 2
    assert not any(has_authorization(r) for r in fake.requests)


def test_the_auth_object_reads_the_address_requests_prepared(make_client: MakeClient) -> None:
    # Bypasses the client's refusal on purpose: what the auth object sees is the host requests connects to.
    client = make_client(token=TOKEN)
    prepared = client._session.prepare_request(requests.Request("GET", "https://other.example\\@api.github.com/x"))
    assert (prepared.url or "").split("/")[2] != "api.github.com"
    assert not has_authorization(prepared)


# --- addresses a server sent ---


@pytest.mark.parametrize(
    "location",
    [
        "https://other.example\\@api.github.com/x",
        f"https://{USER}@api.github.com/x",
        f"https://{USER_INFO}@api.github.com/x",
        "https://api.github.com/a b",
        "https://api.github.com/a\tb",
    ],
)
def test_a_redirect_location_refused_outright_sends_nothing(
    location: str, github: GitHub, make_client: MakeClient
) -> None:
    fake = github("releases")
    serve_redirect(fake, BASE + "/releases/tags/rolling", location)
    with pytest.raises(RemoteDataError):
        make_client(token=TOKEN).get_json("/releases/tags/rolling")
    assert len(fake.requests) == 1


def test_control_characters_never_reach_an_error(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    serve_redirect(fake, BASE + "/releases/tags/rolling", "https://api.github.com/a\x1b[31mb")
    fake.mock.add(responses.GET, BASE + "/gone", status=404, json={"message": "Not \x1b[31mFound\x07 at all"})
    client = make_client(token=TOKEN)
    with pytest.raises(RemoteDataError) as refused:
        client.get_json("/releases/tags/rolling")
    with pytest.raises(NetworkError) as answered:
        client.get_json("/gone")
    assert printable_only(refused.value)
    assert printable_only(answered.value)
    assert answered.value.status == 404


def test_a_redirect_to_http_is_refused_before_it_is_sent(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    serve_redirect(fake, ROLLING_JAR, "http://release-assets.githubusercontent.com/x?sig=secret-value")
    fake.mock.add(responses.GET, "http://release-assets.githubusercontent.com/x", body=b"plain")
    with pytest.raises(NetworkError) as caught:
        make_client(token=TOKEN).download(ROLLING_JAR, io.BytesIO())
    assert hosts(fake) == ["github.com"]
    assert secret_free(caught.value, "secret-value", TOKEN)


def test_an_unencrypted_address_is_refused(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    fake.mock.add(responses.GET, "http://github.com/x", body=b"plain")
    with pytest.raises(NetworkError):
        make_client().download("http://github.com/x", io.BytesIO())
    assert fake.requests == []


def test_more_than_five_redirects_is_an_error(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    serve_redirect(fake, ROLLING_JAR, "https://hop.example/1")
    for n in range(1, 7):
        fake.mock.add(responses.GET, f"https://hop.example/{n}", status=302, headers={"Location": f"/{n + 1}"})
    with pytest.raises(NetworkError):
        make_client().download(ROLLING_JAR, io.BytesIO())
    assert len(fake.requests) == 6


# --- the base address ---


@pytest.mark.parametrize(
    "base",
    [
        "https://other.example\\@api.github.com/repos/tlaplus/tlaplus",
        "https://api.git\thub.com/repos/tlaplus/tlaplus",
        f"https://{USER}@api.github.com/repos/tlaplus/tlaplus",
        f"https://{USER_INFO}@api.github.com/repos/tlaplus/tlaplus",
        "https://api.github.com/repos/tlaplus/tlaplus?per_page=1",
        "https://api.github.com/repos/tlaplus/tlaplus#top",
        "http://api.github.com/repos/tlaplus/tlaplus",
        "api.github.com/repos/tlaplus/tlaplus",
        "https:///repos",
    ],
)
def test_a_base_address_that_is_not_plain_https_is_config_invalid(base: str, make_client: MakeClient) -> None:
    with pytest.raises(ConfigInvalid) as caught:
        make_client(base, token=TOKEN)
    assert secret_free(caught.value, "made-up-part", TOKEN)


def test_a_token_that_cannot_be_a_header_is_config_invalid(make_client: MakeClient) -> None:
    with pytest.raises(ConfigInvalid) as caught:
        make_client(token=TOKEN + "\n")
    assert secret_free(caught.value, TOKEN)


# --- netrc ---


@pytest.mark.parametrize("token", [TOKEN, None])
def test_netrc_is_never_used(
    token: str | None, github: GitHub, make_client: MakeClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    netrc = tmp_path / "netrc"
    netrc.write_text(
        "machine api.github.com login someone password netrc-password\n"
        "machine github.com login someone password netrc-password\n",
        encoding="utf-8",
    )
    netrc.chmod(0o600)
    monkeypatch.setenv("NETRC", str(netrc))
    fake = github("releases")
    client = make_client(token=token)
    client.get_json("/releases/tags/rolling")
    client.download(ROLLING_JAR, io.BytesIO())
    api, download = fake.requests
    assert has_token(api) is (token is not None)
    assert has_authorization(api) is (token is not None)
    assert not has_authorization(download)


@pytest.mark.parametrize("token", [TOKEN, None])
def test_the_auth_object_is_always_set_and_truthy(token: str | None, make_client: MakeClient) -> None:
    client = make_client(token=token)
    assert bool(client._session.auth)


# --- secrecy ---


def test_the_token_is_not_in_the_repr(make_client: MakeClient) -> None:
    client = make_client(token=TOKEN)
    assert TOKEN not in repr(client)
    assert TOKEN not in repr(client._session.auth)


def test_a_failed_download_after_a_signed_redirect_names_no_query(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    serve_redirect(fake, ROLLING_JAR, STORAGE + "?sig=secret-value")
    fake.mock.add(
        responses.GET, STORAGE, status=403, json={"message": f"Request has expired: {STORAGE}?sig=secret-value"}
    )
    with pytest.raises(NetworkError) as caught:
        make_client(token=TOKEN).download(ROLLING_JAR, io.BytesIO())
    assert caught.value.status == 403
    assert secret_free(caught.value, "secret-value", TOKEN)


def test_a_cut_short_download_after_a_signed_redirect_names_no_query(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    serve_redirect(fake, ROLLING_JAR, STORAGE + "?sig=secret-value")
    fake.mock.add(
        responses.GET, STORAGE, body=b"short", headers={"Content-Length": "100"}, auto_calculate_content_length=False
    )
    with pytest.raises(TlaupError) as caught:
        make_client(token=TOKEN).download(ROLLING_JAR, io.BytesIO())
    assert secret_free(caught.value, "secret-value", TOKEN)


def test_a_requests_exception_never_leaves_the_client_as_it_is(github: GitHub, make_client: MakeClient) -> None:
    # responses' own ConnectionError for an unregistered address quotes it whole, query string included.
    fake = github("releases")
    serve_redirect(fake, ROLLING_JAR, STORAGE + "?sig=secret-value")  # STORAGE is not registered
    with pytest.raises(NetworkError) as caught:
        make_client(token=TOKEN).download(ROLLING_JAR, io.BytesIO())
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ or caught.value.__context__ is None
    assert secret_free(caught.value, "secret-value", "?", TOKEN)


def test_a_404_off_the_token_hosts_hints_at_the_setting(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    fake.mock.add(responses.GET, OTHER + "/releases/tags/rolling", status=404, json={"message": "Not Found"})
    with pytest.raises(NetworkError) as caught:
        make_client(OTHER, token=TOKEN).get_json("/releases/tags/rolling")
    assert caught.value.status == 404
    assert caught.value.hint is not None
    assert "tool.token_hosts" in caught.value.hint
    assert secret_free(caught.value, TOKEN)


# --- inventory row T12: User-Agent, the timeout, the system's trust store ---


def test_every_request_carries_the_user_agent_and_the_timeout(github: GitHub, make_client: MakeClient) -> None:
    fake = github("releases")
    serve_redirect(fake, ROLLING_JAR, STORAGE + "?sig=x")
    fake.mock.add(responses.GET, STORAGE, body=b"jar bytes")
    client = make_client()
    client.get_paged("/releases")
    client.get_json("/releases/tags/rolling")
    client.download(ROLLING_JAR, io.BytesIO())
    assert len(fake.requests) == 4
    for request in fake.requests:
        assert request.headers["User-Agent"] == USER_AGENT
        assert request.req_kwargs["timeout"] == (10, 30)  # type: ignore[attr-defined]
    api = fake.requests[:2]
    assert all(r.headers["Accept"] == "application/vnd.github+json" for r in api)
    assert all(r.headers["X-GitHub-Api-Version"] == "2022-11-28" for r in api)


def test_truststore_is_set_up_by_the_constructor_not_by_the_import() -> None:
    # tlaup/__init__.py still injects truststore until package 29 or 49 removes it, so the child takes it out
    # first; what is asserted is that importing the client changes nothing and constructing one sets it up.
    code = (
        "import ssl, truststore, tlaup\n"
        "truststore.extract_from_ssl()\n"
        "plain = ssl.SSLContext\n"
        "from tlaup.versioning.github import GitHubClient\n"
        "assert ssl.SSLContext is plain, 'the import set up truststore'\n"
        "GitHubClient('https://api.github.com/repos/a/b', token=None, token_hosts=(), user_agent='t')\n"
        "assert ssl.SSLContext is truststore.SSLContext, 'the constructor did not set up truststore'\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
