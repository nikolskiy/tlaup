"""The one piece of code that talks to GitHub (design 12 V7).

Every decision about an address is made on the address ``requests`` prepared, read with ``urlsplit``. The token
is added per request by the session's auth object, only for ``https`` on a host in the token set; the auth
object is always set, so ``requests`` never reads ``.netrc``. Redirects are followed by hand. No address with
its query string, and never the token, goes into anything this module returns or raises.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, BinaryIO
from urllib.parse import urljoin, urlsplit

import requests
import requests.auth
import requests.utils

from tlaup.errors import ConfigInvalid, DownloadVerificationError, NetworkError, RateLimited, RemoteDataError
from tlaup.versioning.redact import redact

if TYPE_CHECKING:
    from collections.abc import Iterator

API_HOST = "api.github.com"
ACCEPT = "application/vnd.github+json"
ACCEPT_DOWNLOAD = "application/octet-stream"
API_VERSION = "2022-11-28"
TIMEOUT = (10, 30)  # seconds to connect, seconds between bytes
MAX_REDIRECTS = 5
MAX_PAGES = 50
PER_PAGE = 100
_CHUNK = 64 * 1024
_ERROR_BODY = 64 * 1024  # read at most this much of an error answer, for GitHub's message
_REDIRECTS = frozenset({301, 302, 303, 307, 308})
# Refused outright in any address: a backslash, white space, a control character (C0, DEL, C1).
_REFUSED_CHARS = re.compile(r"[\\\s\x00-\x1f\x7f-\x9f]")
_TOKEN_CHARS = re.compile(r"[\x21-\x7e]+")

Progress = Callable[[int, int | None], None]


@dataclass(frozen=True)
class DownloadInfo:
    size: int  # bytes written to dest
    content_length: int | None  # the answer's Content-Length, None when absent
    sha256: str  # of the bytes written, hashed as they were written


def token_from_env(env: Mapping[str, str]) -> str | None:
    """GH_TOKEN, else GITHUB_TOKEN (the order of the ``gh`` tool); an empty value is no token."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = env.get(name)
        if value:
            return value
    return None


def shown(url: str) -> str:
    """An address as it may be printed: cut at ``?`` and ``#``, no user part, control characters escaped."""
    cut = re.split(r"[?#]", url, maxsplit=1)[0]
    cut = re.sub(r"^([A-Za-z][A-Za-z0-9+.-]*://)[^/]*@", r"\1***@", cut)
    return cut.encode("ascii", "backslashreplace").decode("ascii").replace("\t", "\\t").replace("\n", "\\n")


def _host(url: str) -> str:
    """The host of an address for a message, or the cut address when it has none."""
    try:
        host = urlsplit(url).hostname
    except ValueError:
        host = None
    return host or shown(url)


def _origin(url: str | None) -> str | None:
    """The host of a prepared ``https`` address on port 443, lower-cased; None for anything else."""
    if url is None:
        return None
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or "@" in parts.netloc or port not in (None, 443):
        return None
    return parts.hostname or None


def _has_user_part(url: str) -> bool:
    try:
        return "@" in urlsplit(url).netloc
    except ValueError:
        return True


class _TokenAuth(requests.auth.AuthBase):
    """Adds the token to a prepared request on a host of the set, and only there.

    Always set on the session, also with no token, so that ``requests`` never falls back to ``.netrc``. It
    defines neither ``__bool__`` nor ``__len__``: ``requests`` tests it with ``not self.auth``.
    """

    def __init__(self, token: str | None, hosts: frozenset[str]) -> None:
        self._token = token
        self.hosts = hosts

    @property
    def has_token(self) -> bool:
        return self._token is not None

    def allows(self, url: str | None) -> bool:
        return _origin(url) in self.hosts

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        request.headers.pop("Authorization", None)
        if self._token is not None and self.allows(request.url):
            request.headers["Authorization"] = f"Bearer {self._token}"
        return request

    def __repr__(self) -> str:
        return f"_TokenAuth(token={'set' if self.has_token else None}, hosts={sorted(self.hosts)})"


def _github_message(response: requests.Response) -> str | None:
    """GitHub's own ``message`` from an error answer, on one line; None when the body has none."""
    try:
        body = b"".join(_limited(response.iter_content(_CHUNK), _ERROR_BODY))
        data = json.loads(body)
    except (requests.RequestException, ValueError):
        return None
    message = data.get("message") if isinstance(data, dict) else None
    if not isinstance(message, str) or not message.strip():
        return None
    return redact(" ".join(message.split())[:200], {})  # an address in it loses its query string


def _limited(chunks: Iterator[bytes], limit: int) -> Iterator[bytes]:
    total = 0
    for chunk in chunks:
        yield chunk[: limit - total]
        total += len(chunk)
        if total >= limit:
            return


def _reset_at(response: requests.Response) -> datetime | None:
    """From ``x-ratelimit-reset`` (seconds since the epoch), else ``Retry-After`` read against ``Date``."""
    headers = response.headers
    reset = headers.get("x-ratelimit-reset", "").strip()
    if reset.isdigit():
        try:
            return datetime.fromtimestamp(int(reset), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    retry_after = headers.get("retry-after", "").strip()
    if not retry_after:
        return None
    try:
        if retry_after.isdigit():
            return parsedate_to_datetime(headers.get("date", "")).astimezone(UTC) + timedelta(seconds=int(retry_after))
        return parsedate_to_datetime(retry_after).astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _is_rate_limit(response: requests.Response) -> bool:
    headers = response.headers
    return response.status_code in (403, 429) and (
        headers.get("x-ratelimit-remaining", "").strip() == "0" or "retry-after" in headers
    )


class GitHubClient:
    """Requests to GitHub with the token scoped to its hosts, retries through ``sleep`` and checked addresses."""

    def __init__(  # noqa: PLR0913  the signature of design 12 V7
        self,
        base_url: str,
        *,
        token: str | None,
        token_hosts: Collection[str],
        user_agent: str,
        sleep: Callable[[float], None] = time.sleep,
        attempts: int = 3,
    ) -> None:
        import truststore  # noqa: PLC0415  set up where the network is used, not at import (14 F9)

        truststore.inject_into_ssl()
        token = token or None
        if token is not None and not _TOKEN_CHARS.fullmatch(token):
            message = "the GitHub token holds white space or a character that cannot be sent"
            raise ConfigInvalid(message, hint="check the value of GH_TOKEN or GITHUB_TOKEN")
        self.base_url = self._checked_base(base_url)
        self.sleep = sleep
        self.attempts = max(1, attempts)
        self._auth = _TokenAuth(token, frozenset({API_HOST, *(h.strip().lower() for h in token_hosts)}))
        self._session = requests.Session()
        self._session.auth = self._auth
        self._session.headers.update({"Accept": ACCEPT, "X-GitHub-Api-Version": API_VERSION, "User-Agent": user_agent})

    def __repr__(self) -> str:
        return f"GitHubClient({self.base_url!r}, token={'set' if self._auth.has_token else None})"

    @staticmethod
    def _checked_base(base_url: str) -> str:
        """``https``, no user part, no query string, no fragment, nothing refused outright; else ConfigInvalid."""
        hint = "set tool.repository to an https address such as https://api.github.com/repos/tlaplus/tlaplus"
        reason = None
        if _REFUSED_CHARS.search(base_url):
            reason = "it holds a backslash, white space or a control character"
        elif "?" in base_url or "#" in base_url:
            reason = "it has a query string or a fragment"
        else:
            try:
                prepared = requests.Request("GET", base_url).prepare().url or ""
            except (requests.RequestException, ValueError):
                reason = "it is not an address"
            else:
                parts = urlsplit(prepared)
                if _has_user_part(base_url) or _has_user_part(prepared):
                    reason = "it has a user name or a password"
                elif parts.scheme != "https":
                    reason = "it is not https"
                elif parts.query or parts.fragment:
                    reason = "it has a query string or a fragment"
                elif not parts.hostname:
                    reason = "it has no host"
        if reason is not None:
            message = f"the repository address {shown(base_url)} is refused: {reason}"
            raise ConfigInvalid(message, hint=hint)
        return base_url.rstrip("/")

    # --- the public calls ---

    def get_json(self, path_or_url: str) -> tuple[Any, Mapping[str, str]]:
        """The answer's JSON and its headers; RemoteDataError for a body that is not JSON."""
        data, headers, _ = self._get_json(self._address(path_or_url))
        return data, headers

    def get_paged(self, path: str) -> list[Any]:
        """Every item of a list read 100 at a time, following ``Link: rel="next"`` as given, at most 50 pages."""
        address = self._address(path)
        url = f"{address}{'&' if '?' in address else '?'}per_page={PER_PAGE}"
        items: list[Any] = []
        for _ in range(MAX_PAGES):
            data, headers, answered_at = self._get_json(url)
            if not isinstance(data, list):
                message = f"{shown(url)} did not answer with a list"
                raise RemoteDataError(message)
            items.extend(data)
            following = self._next_page(headers, answered_at)
            if following is None:
                return items
            url = following
        message = f"{shown(address)} has more than {MAX_PAGES} pages"
        raise RemoteDataError(message)

    def download(
        self, url: str, dest: BinaryIO, progress: Progress | None = None, *, limit: int | None = None
    ) -> DownloadInfo:
        """Stream the body at ``url`` into ``dest``, hashing as it is written; stop after ``limit`` bytes.

        Not retried once the answer has started: bytes may already be in ``dest``.
        """
        response = self._request(url, stream=True, accept=ACCEPT_DOWNLOAD)
        with response:
            length_header = response.headers.get("content-length", "").strip()
            content_length = int(length_header) if length_header.isascii() and length_header.isdigit() else None
            digest = hashlib.sha256()
            size = 0
            try:
                for chunk in response.iter_content(_CHUNK):
                    if limit is not None:
                        chunk = chunk[: limit - size]  # noqa: PLW2901
                    dest.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                    if progress is not None:
                        progress(size, content_length)
                    if limit is not None and size >= limit:
                        break
            except requests.exceptions.ChunkedEncodingError:
                message = f"the download from {shown(url)} ended before its end"
                raise DownloadVerificationError(message, details=f"{size} bytes received") from None
            except requests.RequestException as exc:
                message = f"the download from {shown(url)} failed after {size} bytes"
                raise NetworkError(message, details=type(exc).__name__) from None
        return DownloadInfo(size=size, content_length=content_length, sha256=digest.hexdigest())

    # --- addresses ---

    def _address(self, path_or_url: str) -> str:
        if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", path_or_url):
            return path_or_url
        return self.base_url + ("" if path_or_url.startswith("/") else "/") + path_or_url

    def _prepare(self, url: str, accept: str | None = None) -> requests.PreparedRequest:
        """The request ``requests`` would send; RemoteDataError for an address refused outright."""
        if _REFUSED_CHARS.search(url) or _has_user_part(url):
            message = f"refused the address {shown(url)}: it has a backslash, white space or a user part"
            raise RemoteDataError(message)
        headers = {"Accept": accept} if accept is not None else None
        try:
            prepared = self._session.prepare_request(requests.Request("GET", url, headers=headers))
        except (requests.RequestException, ValueError):
            message = f"refused the address {shown(url)}: it is not an address"
            raise RemoteDataError(message) from None
        if prepared.url is None or _has_user_part(prepared.url):
            message = f"refused the address {shown(url)}: it has a user part"
            raise RemoteDataError(message)
        return prepared

    def _next_page(self, headers: Mapping[str, str], answered_at: str) -> str | None:
        """The ``rel="next"`` address as given, once checked: https and on the host that answered."""
        links = requests.utils.parse_header_links(headers.get("link", ""))
        following = next((link.get("url") for link in links if link.get("rel") == "next"), None)
        if not following:
            return None
        prepared = self._prepare(following)
        origin = _origin(prepared.url)
        if origin is None or origin != _origin(answered_at):
            message = f"refused the next page {shown(following)}: not https on the host that answered"
            raise RemoteDataError(message)
        return following

    # --- requests ---

    def _get_json(self, url: str) -> tuple[Any, Mapping[str, str], str]:
        response = self._request(url, stream=False)
        with response:
            try:
                data = response.json()
            except (requests.RequestException, ValueError):
                message = f"{shown(url)} did not answer with JSON"
                raise RemoteDataError(message) from None
            return data, response.headers, response.url

    def _request(self, url: str, *, stream: bool, accept: str | None = None) -> requests.Response:
        """A successful answer, after following at most five redirects by hand, each checked before it is sent."""
        prepared = self._prepare(url, accept)
        if urlsplit(prepared.url or "").scheme != "https":
            message = f"refused the unencrypted address {shown(url)}"
            raise NetworkError(message)
        for _ in range(MAX_REDIRECTS + 1):
            response = self._send(prepared, stream=stream)
            location = response.headers.get("location")
            if response.status_code not in _REDIRECTS or not location:
                return self._successful(response, prepared)
            response.close()
            target = location if _REFUSED_CHARS.search(location) else urljoin(prepared.url or "", location)
            prepared = self._prepare(target, accept)
            if urlsplit(prepared.url or "").scheme != "https":
                message = "refused a redirect to an unencrypted address"
                raise NetworkError(message, details=shown(target))
        message = f"more than {MAX_REDIRECTS} redirects from {shown(url)}"
        raise NetworkError(message)

    def _send(self, prepared: requests.PreparedRequest, *, stream: bool) -> requests.Response:
        """Send with retries on a connection error, a timeout or a 5xx; a rate limit is raised at once."""
        settings = self._session.merge_environment_settings(prepared.url or "", {}, stream, None, None)
        failure = NetworkError(f"could not reach {_host(prepared.url or '')}")
        for attempt in range(1, self.attempts + 1):
            try:
                response = self._session.send(prepared, allow_redirects=False, timeout=TIMEOUT, **settings)
            except (requests.ConnectionError, requests.Timeout) as exc:
                failure = NetworkError(f"could not reach {_host(prepared.url or '')}", details=type(exc).__name__)
            except requests.RequestException as exc:
                message = f"the request to {_host(prepared.url or '')} failed"
                raise NetworkError(message, details=type(exc).__name__) from None
            else:
                if _is_rate_limit(response):
                    response.close()
                    raise self._rate_limited(response, prepared)
                if response.status_code < 500:
                    return response
                failure = self._failed(response, prepared)
            if attempt < self.attempts:
                self.sleep(float(2 ** (attempt - 1)))
        raise failure

    # --- errors ---

    def _rate_limited(self, response: requests.Response, prepared: requests.PreparedRequest) -> RateLimited:
        reset_at = _reset_at(response)
        when = f" (resets at {reset_at.astimezone().strftime('%H:%M')})" if reset_at is not None else ""
        message = f"GitHub's rate limit is used up{when}."
        if "Authorization" not in prepared.headers:
            message += " Set GITHUB_TOKEN to raise it from 60 to 5,000 requests an hour."
        error = RateLimited(message)
        error.reset_at = reset_at
        return error

    def _failed(self, response: requests.Response, prepared: requests.PreparedRequest) -> NetworkError:
        """A status of 400 or above: GitHub's own message, the address cut at the ``?``, and the status."""
        status = response.status_code
        url = prepared.url or ""
        github_says = _github_message(response)
        response.close()
        message = f"{shown(url)} answered {status}" + (f": {github_says}" if github_says else "")
        hint = None
        if status in (401, 404) and self._auth.has_token and not self._auth.allows(url):
            hint = f"the GitHub token is not sent to {_host(url)}; list that host in tool.token_hosts to send it"
        error = NetworkError(message, hint=hint)
        error.status = status
        return error

    def _successful(self, response: requests.Response, prepared: requests.PreparedRequest) -> requests.Response:
        if 200 <= response.status_code < 300:
            return response
        raise self._failed(response, prepared)
