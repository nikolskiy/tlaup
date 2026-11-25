# 24. GitHub client

Size: M. Suggested model: most capable. Status: built, not yet proven on CI. The by-hand request of "Done when" was made on 2026-11-25, through `GitHubClient.get_json("releases/tags/v1.7.4")` against `api.github.com/repos/tlaplus/tlaplus`, once without and once with a token: both answered 200 over TLS through the system trust store; without a token the request carried `Accept`, `Accept-Encoding`, `Connection`, `User-Agent` and `X-GitHub-Api-Version` and the rate limit was 60, with a token it also carried `Authorization` and the limit was 5000; the answer selected API version 2022-11-28. The debug filter (question Q6) is settled: a stand-alone `redact` owned by this package (Interfaces).

This is the security-sensitive package of the store track: it decides where the user's GitHub token goes.

## Goal

`tlaup.versioning.github.GitHubClient` exists and is the only code that talks to GitHub: it scopes the token to the hosts it may reach, sets the headers, retries, reports a rate limit, follows redirects by hand and refuses unencrypted or doubtful addresses, and never uses `.netrc`. It is tested through `responses` with real recordings. `tlaup.versioning.redact.redact` keeps the token and query strings out of `--debug` output, and the root handler of [17](17-error-handler.md) calls it, so the filter is in place before the first command that reads the token (29). No command uses the client yet; the old `versioning/api.py` and `downloader.py` still serve the old commands.

## Covers

- Roadmap items (all [milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust) unless said):
  - "GitHub token support (`GITHUB_TOKEN`, `GH_TOKEN`), `Accept` and `User-Agent` headers, retry with backoff, and a clear message when rate-limited. The token is never printed ..." in part: the client. Package 29 puts it behind the commands and has the scenario that the token appears in neither stream under `--debug`.
  - "Refuse unencrypted addresses and any redirect to one." The whole item at the level of the client; it reaches users at the switch (29).
  - "Do not crash on a non-JSON or non-list API response. Key the remote-version cache on the request ..." in part: the first sentence. The cache is package [25](25-remote-listing.md); "`tools upgrade` ... check the remote again" is packages 25 and 27.
  - "Read all pages of tags and releases ..." in part: following `Link` headers (`get_paged`). Which lists are read, and `stable`, are package 25.
  - "Download and GitHub failure modes are tested ..." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)), in part: the rows of T6 listed under "Tests that must pass". The other rows are packages 25, 26 and 27.
- Design sections:
  - [12 V7](../design/12-tools-and-downloads.md#v7-github-client): all of the client, and the debug filter (`redact`, its unit test, its call in the handler). Not here: the feature scenario on token secrecy and the plain pytest on query strings in the streams and in `build.json`, which need a command and an install (packages 27 and 29); V7's changelog entries (29).
  - [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks), one sentence: "Every line the handler prints under debug ... passes through the debug filter `redact(text, os.environ)`"; the handler itself is 17's.
  - [01 T6](../design/01-testing.md#t6-download-and-github-failure-tests): seven rows, listed below.
  - [01 T4](../design/01-testing.md#t4-fakes-at-the-edges), "Time": the client takes `sleep` as an argument.
- The [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md): row T12 (User-Agent, timeout, the system's trust store), whose owner this package is.

## Depends on

- [02](02-errors-and-paths.md): `NetworkError`, `RateLimited`, `RemoteDataError`, `ConfigInvalid` and `DownloadVerificationError` from `tlaup.errors`.
- [03](03-test-foundation.md): the isolation fixture (it removes `GITHUB_TOKEN`, `GH_TOKEN` and the proxy variables and blocks sockets), the pytest settings, `responses` and `pytest-socket` as development dependencies.
- [05](05-github-recordings.md): the `github` fixture, which registers a recording with `responses` and lists the requests made, and the recordings `releases`, `releases-paged` and `rate-limited` under `tests/recordings/github/`.
- [17](17-error-handler.md): the handler's one debug-printing function in `cli.py`, which this package points at `redact`, and `TlaupGroup`, for the handler test below. **Added** with the settled debug filter (question Q6): the filter's home is this package, and its call goes into the handler here rather than making 17 wait for 24.

Change from the draft: package 19 is dropped. The client takes the repository address and the token hosts as constructor arguments and reads no setting; the settings `tool.repository` and `tool.token_hosts`, their schema and their validation are package 19's, and the commands (package 29) pass their values in. Nothing of 19 is imported here, so this package does not wait for it. 03 is named because it is used directly.

## Files

Creates:

- `src/tlaup/versioning/github.py`
- `src/tlaup/versioning/redact.py`: `redact` (Interfaces). Imports neither `requests` nor `github.py`.
- `tests/unit/versioning/test_github.py` (split into two files if it grows past what reads well: the address and token rules, and retry, rate limit and paging)
- `tests/unit/versioning/test_redact.py`

Changes:

- `src/tlaup/errors.py`, only if package 02 left `RateLimited` without a field for the reset time, or `NetworkError` without a way to carry a status code (see Interfaces). One or two lines; say so in the pull request.
- `src/tlaup/cli.py`: the debug-printing function 17 built returns `redact(text, os.environ)`. One line and an import.

Must not touch: the old `versioning/api.py`, `downloader.py`, `metadata.py`, `paths.py`, `resolver.py`, `schema.py`, `versioning/__init__.py`, `cache/github.py`, `cmd/tools/`, `cmd/fetch_cache/`. Package 29 deletes them. Their old tests and the old fixtures `tests/fixtures/releases.json` and `tags.json` went in 03b (decision D62). `tlaup/versioning/github.py` is a new name: `tlaup/cache/github.py` is the old cache helper in another package and is not replaced by it. The settings schema and the default config file are package 19's.

Deletes: nothing.

Shared with other packages of the track: `tests/unit/versioning/conftest.py` (22 created it; add only what the client tests need). `src/tlaup/errors.py` is shared with every package that finds a class too thin; edits are single lines. `src/tlaup/cli.py` with 17 and the switch packages, one line here.

## Interfaces

Provides, from [12 V7](../design/12-tools-and-downloads.md#v7-github-client):

```python
# tlaup/versioning/github.py
class GitHubClient:
    def __init__(self, base_url: str, *, token: str | None, token_hosts: Collection[str], user_agent: str,
                 sleep: Callable[[float], None] = time.sleep, attempts: int = 3): ...
    def get_json(self, path_or_url: str) -> tuple[Any, Mapping[str, str]]
    def get_paged(self, path: str) -> list[Any]                  # follows Link: rel="next"
    def download(self, url: str, dest: BinaryIO, progress) -> DownloadInfo
```

V7 names four things and gives them no shape. They are written here from what the design says in words; each is marked, and a worker may adjust it if the behaviour and the tests stay.

```python
# written by stage 4

client.sleep: Callable[[float], None]        # the injected sleep, readable: fetch_build (package 26) waits its
                                             # 2 seconds "through the client's injected sleep" (V5, step 4)

Progress = Callable[[int, int | None], None] # bytes written so far, and the total when the answer gave one;
                                             # `progress` may be None. Domain code does not print: the bar is the command's.

@dataclass(frozen=True)
class DownloadInfo:
    size: int                    # bytes written to dest
    content_length: int | None   # the answer's Content-Length, None when absent
    sha256: str                  # of the bytes written, hashed as they were written

def download(self, url, dest, progress=None, *, limit: int | None = None) -> DownloadInfo
    # `limit`: stop reading after this many bytes. fetch_build passes the asset's size plus one, so that a body
    # longer than the asset is seen as a mismatch and a server cannot fill the disk (V5, step 1).

def token_from_env(env: Mapping[str, str]) -> str | None     # GH_TOKEN, else GITHUB_TOKEN; an empty value is no token
```

A status of 400 or above that is not a rate limit: V7 says only that it is "reported as a plain 403 with GitHub's own message text". Two callers need the number: `Remote.release` turns a 404 on a tag into `VersionNotFound` (package 25), and `fetch_build` retries once on a 404 on the asset (package 26). Written by stage 4: the client raises `NetworkError` carrying `status: int | None` (`None` for a failure with no answer), either as a small subclass defined in `github.py` or as a field on package 02's class. The message is GitHub's own `message` text when the body has one, and the address cut at the `?`.

`RateLimited` carries `reset_at` (V7: `RateLimited(reset_at)`); the message leaves out the "Set GITHUB_TOKEN" sentence when a token was sent, so the error also needs to know that.

**The debug filter** (question Q6, settled; [12 V7](../design/12-tools-and-downloads.md#v7-github-client)), one stand-alone function with no state, owned by the client and kept beside it:

```python
# tlaup/versioning/redact.py      imports neither requests nor github.py
def redact(text: str, env: Mapping[str, str]) -> str
```

It replaces the values of `GH_TOKEN` and `GITHUB_TOKEN`, read from `env`, with `***` wherever they appear (an unset or empty variable replaces nothing), and cuts every `http://` or `https://` address in the text at its `?`, an address ending at white space or a quote character. So it needs no record of the tokens or query strings the client met, and nothing is process-wide state ([00](../design/00-overview.md#application-context)). The root handler of [17](17-error-handler.md) passes every line it prints under `--debug`, the one-line message and the traceback, through `redact(text, os.environ)` ([14 F10](../design/14-config-and-cli.md#f10-no-tracebacks)); this package makes that call. It is in place before the first command that reads the token: [29](29-tool-commands.md) depends on this package, and before 29 no command holds a token to print. Separately, and as before, the client never puts the token or a query string into anything it returns or raises (below).

Consumes: the error classes (02); the `github` fixture and the recordings (05); the debug-printing function and `TlaupGroup` (17).

Used later by: `Remote` (25), `fetch_build` (26), `install`, `upgrade` (27), `ensure_tools` (28), the `tool` commands (29); `redact` by the root handler (17's code) from this package on.

## Tests that must pass

Plain pytest in `tests/unit/versioning/test_github.py`, against the real client with `responses` ([01 T1](../design/01-testing.md#t1-the-approach): a piece that sits on an edge, driven with the edge's fake). Each asserts the error type and the requests that were made, never the message (T12 rule 4).

The rows of [01 T6](../design/01-testing.md#t6-download-and-github-failure-tests) that test the client (the full assignment of the table's 22 rows is in the index):

| T6 row | Expectation here |
| --- | --- |
| 403 with rate-limit headers; 429 | `RateLimited` carrying the reset time; one request, no sleep. The 403 is the `rate-limited` recording (`x-ratelimit-remaining: 0`, `x-ratelimit-reset`, no `Retry-After`); the 429 with `Retry-After` is synthetic, and the test's first line says so. |
| 500, then 200 | Succeeds after one retry; the injected sleep was asked for 1 second. |
| Response is not JSON; JSON is an object where a list is expected | `RemoteDataError` from `get_json` for a body that is not JSON, and from `get_paged` for a page that is not a list. |
| Two pages of releases (the `releases-paged` recording) | `get_paged("/releases")` returns the 17 releases; the request for page 2 used the address from the `Link` header as given (`https://api.github.com/repositories/<id>/releases?...&page=2`), and the first request asked for `per_page=100`. |
| A `Link` header whose next address is on another host or is not `https` | Not followed; `RemoteDataError`; no request was sent to it. |
| Redirect to `http://` | `NetworkError`, raised before any request to that address. |
| Token set | The header goes to `api.github.com` and to a host listed in `token_hosts`, and to no other; it is absent from the asset download. The half "absent from every log line and `--debug` output" is asserted here on the client's own errors and `repr`, and through a command by package 29. |

V7's own list, token scope:

- With a token, requests to the `releases` recording go to two hosts: the API requests carry `Authorization: Bearer`, the download from `github.com` does not, and neither does the storage host when the test serves the redirect.
- `base_url` on another host and `token_hosts` empty: no request carries the header. With that host listed: requests to it do.
- A redirect from the API host to an unlisted host is followed without the header.
- A `Link` "next" address on another host, on the same host with port 8443, or with `http`: `RemoteDataError`.
- The API host written in upper case gets the header; the API host with port 8443 does not.
- A `Link` "next" address and a redirect `Location` of the form `https://other.example\@api.github.com/x` are refused with `RemoteDataError`, and no request is sent.
- `base_url` of that form, with a tab in the host, with a user name, with a query string, with a fragment, or with `http`: `ConfigInvalid` from the constructor.
- Three failing answers give exactly two sleeps, of 1 and 2 seconds, and then `NetworkError`.
- More than five redirects, and more than 50 pages: an error, not a loop.

Netrc: with `NETRC` pointing at a file that has entries for the API host and the asset host, and a token, the API request carries the bearer header and the download carries no `Authorization`; with no token, neither request carries one. `bool(session.auth)` is true with and without a token.

Secrecy, at the level of the client:

- The token's value is in neither `repr(client)` nor `str()` of any error the tests above raise, nor in their `hint` or `details`.
- A download that redirects to an address with `?sig=secret-value` and then fails: `secret-value` is in no part of the error. `DownloadInfo` has no address field.
- A `requests` exception never leaves the client as it is: the error raised is a `TlaupError` whose text has no query string.

Also: `download` writes exactly the body to `dest`, reports `size`, `content_length` and `sha256`, stops at `limit`, and calls `progress`; a body that ends before its `Content-Length` (`requests.exceptions.ChunkedEncodingError`) is `DownloadVerificationError`; a connection that fails before any answer is retried and then `NetworkError`; `token_from_env` prefers `GH_TOKEN`; every request has the timeout (10 seconds to connect, 30 between bytes), asserted on what `responses` recorded.

Not tested here and why: TLS through the operating system's trust store. `responses` answers below the adapter, so no test in the suite makes a TLS connection; the first real use is a `tlaup tool install` by hand and in the integration job's set-up ([30 I1](../design/30-ci-and-release.md#i1-integration-job)). Say in the pull request that one real request was made by hand, and against what.

`tests/unit/versioning/test_redact.py`, V7's unit test of the filter: a text holding the values of both variables gives `***` for each; an address with `?sig=x` loses everything from the `?` and the rest of the line stays; with `GH_TOKEN` set to the empty string the text comes back unchanged; a text holding neither a token nor an address comes back unchanged. Also, through the handler: a small app built with `cls=TlaupGroup` (as 17's `test_handler.py` builds them) whose command raises `RuntimeError` with a message holding `GH_TOKEN`'s value (set with `monkeypatch`) and `https://example.org/x?sig=secret`, run under `--debug` through `CliRunner`: stderr holds `***` and neither the token's value nor `secret`, in the `error:` line and in the traceback. And `import tlaup.versioning.redact` in a fresh interpreter does not load `tlaup.versioning.github`. The test asserts that one module only: today's `tlaup/versioning/__init__.py` imports `downloader.py`, which imports `requests` at its top, so importing `redact` loads `requests` until [29](29-tool-commands.md)b empties `__init__.py`, and 29b adds the `requests` half to this test (finding G3 of the [second review](review-2026-11-24.md)).

Row T12 of the [preserved-behaviour inventory](../design/preserved-behaviour-2026-11-22.md) (requests to GitHub carry a User-Agent and a timeout, and TLS uses the operating system's trust store) is this package's (findings F1 and G1 of the [second review](review-2026-11-24.md)). Its test, in `test_github.py`: every request the client makes, the download and a redirect included, carries the `User-Agent` it was given and the timeout (the timeout case above); and, in a fresh interpreter, importing `tlaup.versioning.github` leaves `ssl.SSLContext` as it is, while constructing a `GitHubClient` makes it `truststore.SSLContext` (what `truststore.inject_into_ssl()` does; the child interpreter keeps the change out of the test process).

Old tests: none is left (03b, decision D62). Stateful tests: none applies.

## Changelog

None in this package. V7's entries describe what a user sees once the commands use the client, and package 29 writes them: Added "`GITHUB_TOKEN` or `GH_TOKEN` is used for GitHub API requests ...", Fixed "A GitHub rate limit was reported as a generic failure." and "A non-JSON answer from GitHub (for example from a proxy) caused a traceback.", Changed "Unencrypted addresses, and redirects to them, are refused."

## Context for the worker

Decisions:

- D41: the token goes to `api.github.com` and to the hosts in the user-level setting `tool.token_hosts`, and nowhere else. A repository address can come from the environment, and later from a project file; the token must not follow it.
- "`.netrc` credentials are never used; a jar is downloaded from its public address and carries no token by default; addresses are compared after parsing, and query strings are cut from messages" and "an address with a backslash, a user part or white space is refused, and every host decision is made on the address `requests` prepared" (decisions of the design agent, README). Both came from things that were tried and went wrong.
- D29: `NetworkError`, `RateLimited` and `RemoteDataError` are "failed" (5); `ConfigInvalid` is "not set up" (3).
- D15: nothing here is platform-specific.

The rules, each of which was found the hard way (V7 has the full text; read it twice):

- **Every decision about an address is made on the address `requests` will connect to.** Prepare the request first and read `PreparedRequest.url` with `urllib.parse.urlsplit`. For `https://evil.example\@api.github.com/x`, `urlsplit` on the raw string gives the host `api.github.com`, while `requests` 2.34.2 prepares a request to `evil.example`. The same-host checks for a redirect and for a "next" address prepare the request before they compare.
- **Refused outright, before anything is sent**: an address with a backslash, a user part (`user@` or `user:password@`), white space or a control character, or one `requests` cannot prepare. `ConfigInvalid` for the base address, `RemoteDataError` for an address a server sent.
- **In the prepared address**: the scheme must be `https`; the host is `hostname` (lower-cased, no port, no user part); the port must be absent or 443. Any other port, or an address that does not parse, counts as another host: no token, and it fails the same-host checks. Host names are compared whole, never by suffix.
- **The token is added per request by an auth object set on the session**, and only when the prepared address is `https` on a host in the set. The set is `api.github.com` plus `token_hosts`. A redirect and a "next" address are new requests and are checked the same way.
- **The auth object is always set, also with no token, and must be truthy.** `requests` reads `~/.netrc` (or `$NETRC`) when the session and the request have no auth, and it tests the session's with `not self.auth`: an auth class that defines `__bool__` or `__len__` and comes out false lets netrc back in. Define neither. With a netrc entry and a hand-set header, `requests` replaced the token with `Basic` credentials and sent them to the asset host as well (tried by the design agents on 2.34.2).
- **`trust_env` stays on**, so the proxy and certificate variables of the environment still apply. Netrc is kept out by the auth object, not by switching `trust_env` off.
- **Redirects are followed by hand**: `allow_redirects=False`, at most five, each `Location` checked before a request is made to it. `requests`' own following would have made the request to the unencrypted address before any check, and is the other place `requests` reads netrc.
- **The asset is downloaded from the address the release object gives** (`browser_download_url`, on `github.com`, which redirects to a storage host with a signed query string). With default settings neither request carries the token. The client does not build download addresses.
- **Query strings never leave the client.** Every address in an error message, a note or a return value is cut at the `?`. The exceptions of `requests` quote the full address in their text, so that text is never passed on as it is.
- **The token is held in one private attribute.** `repr` and every error omit it.
- **Retry**: on a connection error, a timeout or a 5xx answer; `attempts` tries in all, waits of 1 and then 2 seconds, doubling for more attempts, through the injected `sleep`. Not `urllib3.Retry`, which sleeps on its own clock.
- **Rate limit**: a 403 or 429 with `x-ratelimit-remaining: 0` or a `Retry-After` is `RateLimited`, raised at once with no retry. The real recording has `x-ratelimit-reset` (seconds since the epoch) and no `Retry-After`. A 403 with neither header (a secondary limit) is a plain error with GitHub's message.
- **Paging**: `per_page=100`; the `rel="next"` address is used as given, not rebuilt (research 8: it is on another path than the request's); before use it must be `https` and on the same host as the request that returned it; at most 50 pages.
- **Headers**: `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, `User-Agent` as given (the commands pass `tlaup/<version>`; no contact details).
- **TLS**: `truststore` is set up in the constructor, not at import ([14 F9](../design/14-config-and-cli.md#f9-startup-cost)). `requests` and `truststore` are imported only by this module, so that a command that does not use the network does not load them once package 29 has removed the old imports.
- **A 401 or 404 from a host that is not in the token set, when a token exists**, carries the hint that the token is not sent to that host and names `tool.token_hosts` (V7, Risks).

Points the design leaves open; decide, and say which in the pull request:

- The client has `sleep` and no clock. A reset time from `x-ratelimit-reset` needs none. One from `Retry-After` in seconds does: take it from the answer's `Date` header, or add a `now` argument as the store has. Nothing may read the wall clock directly.
- Whether `download` retries after bytes have been written to `dest`. V7's retry is written for a request that fails before an answer. If a failure in the middle of the body is retried, `dest` must be truncated and the hash restarted; not retrying it is simpler, and T6's row "connection drops mid-stream" expects `NetworkError` either way.
- `get_json` returns `Any`. Whether a list arrives where an object was expected is checked by the caller that wants the object (package 25); `get_paged` checks its own pages.

What research found that a worker could miss: `responses` 0.23.3 to 0.26.3 and `pytest-socket` work together; an unregistered address gets `responses`' own `ConnectionError`. `responses` keeps a `Content-Length` longer than the body, after which `requests` raises `ChunkedEncodingError` from `iter_content`, while `raw.read()` returns the short body with no error; so a reader of `response.raw` must compare the byte count itself. Under `pytest-socket` with warnings as errors, a blocked socket surfaces as a `UserWarning` raised as an exception, not as `SocketBlockedError`; no test asserts on the latter by type. A real 429 was never obtained.

Not tried by anyone: a private repository, a GitHub Enterprise host, and how a later `requests` decides to read netrc. The netrc unit test is what fails if that changes.

State of `main` when this starts: the 0.8.x code with packages 01 to 03, 05 and 17 on top. The old `versioning/api.py` and `downloader.py` call `requests.get` directly, with no token; they stay and keep serving `tlaup tools install` until package 29. `tlaup/versioning/__init__.py` still imports the old modules (and `requests`) until 29 empties it, so importing `redact` loads them (which is why its import test names `tlaup.versioning.github` only until 29b); today's `cli.py` loads them already, so the handler pays nothing new, and [49](49-startup-cost.md)'s test runs after 29.

## Done when

- The tests above pass; `uv run poe lint` (bandit and mypy strict cover the new module) and `uv run poe test` pass; CI is green.
- No file listed under "Must not touch" is in the diff.
- The pull request states: the three open points above and what was chosen; that one real request through the client was made by hand, with and without a token, and what the headers were; and, per T12 rule 6, that the netrc test and the backslash test fail when the auth object or the prepared-address rule is taken out.
- `redact` exists in `tlaup/versioning/redact.py`, the handler calls it, and its tests pass.
- The pull request names inventory row T12 and its test.

## Out of scope

- `Release`, `Asset`, `Remote`, the lookup cache, `stable_of`, percent-encoding a tag into a path: package [25](25-remote-listing.md).
- `fetch_build`, the size and digest checks, the 2-second retry: package [26](26-download-and-verify.md).
- `install`, `upgrade`, `--force`, concurrent installs (V12, V3, V4, V11): package 27. The first-run prompt (V9): package 28.
- The `tool` commands, reading the token from the real environment and the settings, the feature scenario "the token appears in neither stream under `--debug`", the query-string test over the streams and `build.json`, V7's changelog entries, and deleting `versioning/api.py`, `downloader.py`, `cache/github.py`: package 29.
- The settings `tool.repository` and `tool.token_hosts`, their validation, and the rule that a project layer cannot set them: package 19.
- The handler that prints debug output: package 17 (this package changes one line of it).

## Risks

- From V7: GitHub answers some rate limits with a 403 and no headers; these are a plain error. A user who points `tool.repository` at a GitHub Enterprise host and forgets `tool.token_hosts` gets unauthenticated requests; the hint above is the answer. The netrc rule rests on how one `requests` version reads the file. A user who relied on `.netrc` has to set `GH_TOKEN`; the changelog says so (29).
- From T6: a row can name a state the finished code cannot reach; such a row is removed with a line in the pull request, not bent to fit.
- From the cut: the client is built before anything uses it, so a wrong guess about what `Remote` and `fetch_build` need (the status code, `limit`, `sleep`) shows one package later. Those three are written under Interfaces for that reason.
- From the cut: no test makes a real TLS connection. The by-hand request in "Done when" is the only check before the integration job.
- A mistake here sends a token to the wrong host. The review of this pull request should be done by an agent that reads V7 and the test list side by side, row by row.
