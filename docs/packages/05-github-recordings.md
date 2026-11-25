# 05. GitHub recordings and the `github` fixture

Size: M. Suggested model: mid-tier. Status: ready. The worker needs the network once, for about six unauthenticated GitHub requests (see Context); without it, the maintainer runs one command.

## Goal

Real GitHub answers, trimmed to what tlaup reads, live under `tests/recordings/github/`, one folder per situation; a `github` fixture serves them through `responses`, answers jar downloads with a small real jar it builds, and lists the requests made; `scripts/record_github.py` makes the recordings again. The recorded jar manifests live under `tests/unit/data/manifests/`. Nothing under `src/` changes; no test of tlaup's own code uses the fixture yet.

## Covers

- Roadmap items:
  - "Unit tests cannot reach the network or start an unmocked subprocess; ..." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this), roadmap line 369), in part: the network half (recorded responses at the `requests` adapter). The socket block, the closed-port address and the process fakes are package [03](03-test-foundation.md).
- Design sections:
  - [01 T4](../design/01-testing.md#t4-fakes-at-the-edges), "Network": the recordings, the `github` fixture, the small jar, `scripts/record_github.py`. The socket block and `TLAUP_TOOL_REPOSITORY`'s closed port are in the isolation fixture (03). The tests that use the fixture are the packages of the store track (24, 25, 26, 27, 28) and the GitHub steps of the feature vocabulary, which package 29 writes on it.
  - [01 T3](../design/01-testing.md#t3-golden-files), two rows of "What moves": research 29's `releases-paged` and `rate-limited` to `tests/recordings/github/` ("by T3's rule", T4), and the last row, `03-jar-identity/manifest-*.txt` and `14-jar-manifest/*.MF` to `tests/unit/data/manifests/`. The rest of T3 is packages 07 and 08.
  - Not here: T3's sentence that the old fixtures `tests/fixtures/releases.json` and `tags.json` are superseded by the recordings and deleted. They went with the old suite in 03b (decision D62).

## Depends on

- [03](03-test-foundation.md): `responses` and `pytest-socket` as development dependencies and `--disable-socket` in `addopts`; the autouse `isolated` fixture, which sets `TLAUP_TOOL_REPOSITORY` to a closed local port that this fixture removes; `tests/conftest.py`, where the fixture is registered; the rule that `tests/fixtures` is not collected.

## Files

Moves (with `git mv`, never a copy, T3):

| From | To |
| --- | --- |
| `tests/fixtures/research/29-ci-facts-and-recordings/releases-paged/` (`page1.headers`, `page1.body`, `page2.headers`, `page2.body`) | `tests/recordings/github/releases-paged/`, then recorded again in place (see Context) |
| `tests/fixtures/research/29-ci-facts-and-recordings/rate-limited/` (`response.headers`, `response.body`) | `tests/recordings/github/rate-limited/`, unchanged |
| `tests/fixtures/research/03-jar-identity/manifest-rolling.txt`, `manifest-v174.txt` | `tests/unit/data/manifests/` |
| `tests/fixtures/research/14-jar-manifest/rolling.MANIFEST.MF`, `v1.7.4.MANIFEST.MF`, `v1.8.0.MANIFEST.MF` | `tests/unit/data/manifests/` |

`tags-paged/` stays with the research as evidence: the client never calls the tags endpoint ([12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache)). So do `08-github-api/` and `18-digest/`: trimmed lists with no headers, which `responses` cannot serve (T3).

Creates:

| File | What |
| --- | --- |
| `tests/recordings/github/releases/` | New: the release list as one page (`GET /releases?per_page=100`) and the per-tag release objects for `rolling`, `v1.8.0` and `v1.7.4` (`GET /releases/tags/<tag>`), each a `.headers` and a `.body` file. |
| `tests/recordings/github/<situation>/requests.toml` | One per situation: which request each recorded answer serves (format under Interfaces). |
| `tests/recordings/github/README.md` | Per situation: what was asked, when, what was trimmed, which headers the fixture does not serve, and that `date` and `x-ratelimit-reset` are the values of their day. |
| `scripts/record_github.py` | The recording tool. |
| `tests/github.py` | The fake GitHub: loading a recording, serving it, the request list. |
| `tests/jars.py` | `make_tools_jar`, the small real jar. Shared: package 22 uses it for `read_jar`'s tests instead of a builder of its own (T12 rule 9). |
| `tests/unit/test_github_fixture.py`, `tests/unit/test_jars.py` | Tests of the two. |

Changes:

- `tests/conftest.py`: the `github` fixture.
- `tests/fixtures/research/README.md`: a line for each moved folder saying where it went and when (T3), and for `29-ci-facts-and-recordings/` that `releases-paged` was recorded again with the assets' `updated_at`.
- `tests/fixtures/research/29-ci-facts-and-recordings/README.md`: the same note, since its table describes the moved files.
- `.secrets.baseline`, only if the scan flags a line of a new recording: then an `exclude_lines` pattern for that exact line shape, never a file or a folder ([conventions](../contributing/conventions.md#secrets-and-personal-data)).

Deletes: nothing. `tests/fixtures/releases.json` and `tests/fixtures/tags.json` are already gone (03b).

Shared with packages of the same period: `tests/conftest.py` (one fixture; 03 wrote the file, 18 and 29 add steps elsewhere), `tests/fixtures/research/README.md` (one line per moved folder; package 07 adds its own lines for the golden move). The manifest move is done here and only here: packages 07 and 22, which also need the manifests in their new place, find them moved and must not move them again.

## Interfaces

Provides, written by stage 4 from [01 T4](../design/01-testing.md#t4-fakes-at-the-edges)'s words ("A fixture `github(recording="releases")` ... registers a recording with `responses` and returns an object that lists the requests made"); a worker may adjust names if the behaviour and the tests stay, and says so in the pull request.

```python
# tests/conftest.py
@pytest.fixture
def github(monkeypatch, tmp_path) -> Callable[..., GitHubFake]
    # github(recording="releases") -> GitHubFake. Removes TLAUP_TOOL_REPOSITORY (so the client uses its
    # default, the real API host), starts a responses.RequestsMock for the test, registers the recording,
    # and stops the mock at the end of the test.

# tests/github.py
@dataclass(frozen=True)
class Recorded:
    status: int
    headers: Mapping[str, str]      # as recorded, names lower-cased
    body: bytes

def load_recording(name: str) -> list[tuple[str, str, Recorded]]   # (method, url, answer), from requests.toml

class GitHubFake:
    mock: responses.RequestsMock          # for a test that registers an answer of its own
    @property
    def requests(self) -> list[requests.PreparedRequest]   # every request made, in order, with its headers
    @property
    def downloads(self) -> int            # requests to a jar's download address
    def clear(self) -> None               # forget the requests so far (T5: "I run" counts the last run only)
    def jar(self, tag: str) -> Path       # the small jar served for that tag
    def unreachable(self) -> None         # from now on every request fails with requests.ConnectionError
    def answer(self, status: int, path: str) -> None   # an answer with that status for a path under the base address

# tests/jars.py
def make_tools_jar(dest: Path, manifest: Path | bytes, *, repl: bool = False) -> Path
    # a zip with META-INF/MANIFEST.MF (the bytes as given), an empty tlc2/TLC.class and,
    # with repl=True, an empty tlc2/REPL.class; returns dest
```

`requests.toml`, one table per recorded answer:

```toml
[[answer]]
method = "GET"
url = "https://api.github.com/repos/tlaplus/tlaplus/releases"    # matched with any query string
file = "list"                                                     # list.headers and list.body beside this file
```

What the fixture serves:

- Every recorded answer at its address, with the recorded status, the recorded body, and the recorded headers **except** `content-length`, `content-encoding` and `transfer-encoding`, which `responses` and `requests` compute for the body as served. The bodies are trimmed, so the recorded length is wrong; research 30 found that `responses` keeps a `Content-Length` longer than the body, after which `requests` raises `ChunkedEncodingError` from `.content`.
- `releases-paged`: page 1 for the first request to `/releases` whatever its query (the client asks for `per_page=100`, the recording was made with 10), and page 2 at the address of page 1's `Link` header, as given (`https://api.github.com/repositories/<id>/releases?per_page=10&page=2`).
- `rate-limited`: the recorded 403 for every request to the API host.
- **Jar downloads.** For `rolling`, `v1.8.0` and `v1.7.4`, the asset `tla2tools.jar`'s `browser_download_url` (on `github.com`) answers 200 with a small jar built in `tmp_path` by `make_tools_jar` from that tag's recorded manifest (`rolling.MANIFEST.MF`, `v1.8.0.MANIFEST.MF`, `v1.7.4.MANIFEST.MF` under `tests/unit/data/manifests/`), with `repl=True` for `rolling` and `v1.8.0` (the REPL class is absent from v1.7.4 and present in rolling, [00](../design/00-overview.md#what-a-build-can-do)).
- **Size and digest follow the small jar.** In every release object the fixture serves (the list, the pages, the per-tag objects), the `tla2tools.jar` asset of those three tags carries the small jar's `size` and, where the recording has a `digest`, `sha256:<the small jar's SHA-256>`; where the recording's `digest` is `null` (`v1.7.4`, research 18), it stays `null`. Everything else in the body is served as recorded. Without this no download could verify ([12 V5](../design/12-tools-and-downloads.md#v5-download-and-verify)), and package 26 would have to weaken a check.
- Other tags' jars are not answered: a request for one fails with `responses`' own `ConnectionError`, as every unregistered address does.

Consumes: nothing from `src/`. From 03: `responses`, the isolation fixture.

## Tests that must pass

Plain pytest, new. They use `requests` directly, which is the edge itself, not tlaup's code:

- `tests/unit/test_github_fixture.py`:
  - Each recording loads, and each of its answers is served at its address with its recorded status.
  - `releases`: the list is a JSON list, and its number of releases equals the recording's (17 when research 29 recorded it; the test reads the number from the file, not from a constant); the per-tag objects of `rolling`, `v1.8.0` and `v1.7.4` are served; their jar assets carry the small jar's size, the small jar's digest where the recording had one, and `null` for `v1.7.4`; every asset has `updated_at`.
  - `releases-paged`: a request to `/releases?per_page=100` gets page 1, whose `Link` header names page 2 with `rel="next"`; page 2 is served at that address and its `Link` has no `rel="next"`.
  - `rate-limited`: 403, `x-ratelimit-remaining: 0`, an `x-ratelimit-reset` header, and no `retry-after`.
  - A jar download returns exactly the bytes of `jar(tag)` and counts in `downloads`; an API request does not.
  - `requests` lists method, address and headers; a request sent with an `Authorization` header shows it and one without does not; `clear()` empties the list.
  - An address that is not registered fails with `requests.ConnectionError` under `--disable-socket` (research 30 tried the two libraries together: `responses` 0.23.3 to 0.26.3 with `pytest-socket` 0.8).
  - `unreachable()` makes the next request fail with `requests.ConnectionError`; `answer(404, "/releases/tags/v9.9.9")` serves a 404 there.
  - Inside the fixture `TLAUP_TOOL_REPOSITORY` is not set; outside it (a test without the fixture) it is the closed port of 03.
- `tests/unit/test_jars.py`: the jar is a valid zip (`ZipFile.testzip()` returns `None`), holds `META-INF/MANIFEST.MF` with the given bytes unchanged and `tlc2/TLC.class`, and holds `tlc2/REPL.class` only with `repl=True`.
- The recording script: `uv run python scripts/record_github.py --help` exits 0 (a test that starts it as a child process, with no network needed). Recording itself is not run in CI.

Old tests: none are left (03b). Preserved-behaviour rows: none is this package's; the store track's owners test theirs on this fixture. No stateful test applies. No feature file (the GitHub steps are package 29's, on this fixture).

## Changelog

None. Nothing a user sees changes.

## Context for the worker

Decisions this rests on: D16 and D33 (download and GitHub failures are plain pytest against the real HTTP code, served by recordings; [01 T1](../design/01-testing.md#t1-the-approach)), D7 and T3's rule (evidence is moved, not copied, and the research README says where it went), D41 (the token goes to `api.github.com` and listed hosts only; the fixture serves downloads on `github.com`, a different host, which is what the token tests of package 24 need).

**Why `responses` and not a local server** ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges), Rejected): `responses` answers at the `requests` adapter, below tlaup's own retry, header, redirect and pagination code, so that code runs for real; a local HTTP server would need sockets and plain HTTP, which [12 V7](../design/12-tools-and-downloads.md#v7-github-client) refuses. `responses` and `pytest-socket` work only inside the pytest process: a real-process scenario cannot be served recordings (T4, "Real processes and the network"), which is why those scenarios start from a store that already holds what they need.

**Recording again: why and how.** Research 29 cut the release bodies to the fields tlaup read then (release: `id`, `tag_name`, `name`, `draft`, `prerelease`, `created_at`, `published_at`, `url`, `html_url`; asset: `id`, `name`, `size`, `digest`, `content_type`, `state`, `browser_download_url`). That list leaves out the assets' `updated_at`, which `Asset.updated_at` reads ([12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache), package 25) and which package 27 compares. A real answer always has the field; a parser that accepted its absence would hide a real change. Adding the field by hand would make a recording that GitHub never sent. So `releases` is recorded new, and `releases-paged` is moved and then recorded again in place, both by `scripts/record_github.py`, with the trimmed field list widened by the assets' `created_at` and `updated_at`:

- release: `id`, `tag_name`, `name`, `draft`, `prerelease`, `created_at`, `published_at`, `url`, `html_url`, `assets`;
- asset: `id`, `name`, `size`, `digest`, `content_type`, `state`, `created_at`, `updated_at`, `browser_download_url`.

`rate-limited` is not recorded again: it took about sixty requests within an hour to get, it has no release body, and its headers are what the tests read. It moves as it is.

**The script** (`scripts/record_github.py`), a developer tool, not run in CI ([01 T4](../design/01-testing.md#t4-fakes-at-the-edges)):

- Arguments: the situations to record (`releases`, `releases-paged`, and `rate-limited` only when named, since it spends the unauthenticated allowance as research 29's loop did), and the output folder (default `tests/recordings/github/`).
- It sends no token: it ignores `GH_TOKEN` and `GITHUB_TOKEN`, so a recording never depends on the recorder's account. It sends `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28` and a `User-Agent` with no contact details, and a timeout on every request.
- It keeps the status line and every header as sent, names lower-cased one `name: value` per line as research 29 stored them, drops `set-cookie` if present, trims bodies to the field lists above, and writes bodies as JSON with an indent of one space (research 29's form, which keeps each hash on a line of its own, so that the secrets scan's line patterns can apply).
- It replaces any IP address in a body or a header with `<ip>` (research 29 did so by hand in the 403's body), since the `no-ip-addresses` hook would refuse it.
- It writes `requests.toml` for each situation and prints what it wrote.
- `releases-paged` asks for `per_page=10` and follows `rel="next"` until there is none, as research 29 did; `releases` asks for `per_page=100` and the three per-tag objects.
- It is plain Python on `requests` (a runtime dependency already); it must pass `mypy` in strict mode, which covers `scripts/` today (`mypy .` excludes only `tests/`), and `ruff check`.

About six requests in all, well inside the unauthenticated limit of 60 an hour. If the worker's environment has no network, the worker writes and tests the script, and the maintainer runs `uv run python scripts/record_github.py releases releases-paged` once and commits the result to the branch; the pull request says which happened.

**A new recording is not research 29's list.** Upstream may have published or replaced releases since 2026-11-19 (the `rolling` asset is replaced on every upstream build). Research 29 and the packages written from it say "17 releases", "the stable release is `v1.7.4`", "`v1.8.0` is a prerelease", "`rolling` and `v1.8.0` hold the same jar". The tests of this package read such facts from the recording, and the pull request states what the new recording holds for each of them, so that packages 24 to 29 can check theirs. If `releases-paged` no longer spans exactly two pages at `per_page=10`, keep what GitHub answered and say so: T6's row only needs "two pages with their real Link headers", and the script follows `next` to the end.

**The manifests** are moved here, all five files, keeping their names (both copies of the v1.7.4 manifest and the rolling manifest under their research names are kept; tests use the three `*.MANIFEST.MF`). The `detect-secrets` pattern for `X-Git-Revision` lines is a line shape, not a path, so it keeps working after the move (T3, Risks: "check when moving"); check it with `uv run poe check`.

**Points that are easy to miss.**

- `date` and `x-ratelimit-reset` are real values of the recording day. No test may depend on them being current; a test of the reset time reads the header and compares with what the code derived from it.
- Recorded header names are lower case; read them case-insensitively.
- The fixture's jars are a few hundred bytes; the recorded real sizes are 4.5 MB. A test that wants the real numbers reads the recording file, not the served answer.
- `answer` and `unreachable` must take precedence over the recording for the addresses they name (`responses` uses the first registration that matches; replace or insert before, as the library allows).
- The fixture must not leave the mock running after its test, or the next test's requests would be served by it; stop it in the fixture's teardown.
- The request list is the place to assert on the token: `requests[i].headers.get("Authorization")`. Never print or log a header value in a test.
- `tests/recordings/` holds no Python file and is not collected; `tests/github.py` and `tests/jars.py` are helpers, not tests (no `test_` prefix).

State of `main` when this starts: the test foundation of 03 (isolation, fakes, settings, `responses` installed); the old `versioning/api.py` and `downloader.py` serve the old commands, with no tests left (03b, D62). Package 07 (golden files) and package 22 (jar info) may run at the same time; they need the manifests in `tests/unit/data/manifests/` and get them from this package.

## Done when

- The moves are `git mv` (the pull request's diff shows renames), and the research READMEs say where each folder went and when.
- `tests/recordings/github/` has `releases`, `releases-paged` (with `updated_at` on every asset) and `rate-limited`, each with its `requests.toml`, and the README.
- The new tests pass; `uv run poe lint` (including `mypy` on the script), `uv run ruff format --check .`, `uv run poe test` and `uv run poe check` (the secrets and personal-data hooks over the recordings) pass; CI is green.
- The pull request says whether the worker or the maintainer recorded, and what the new recording holds: the number of releases, the stable tag, which tags are prereleases, whether `rolling` and `v1.8.0` share a digest, and the number of pages at `per_page=10`.

## Out of scope

- `GitHubClient` and every T6 row: packages 24 (client), 25 (listing), 26 (download), 27 (install steps).
- The GitHub steps of the feature vocabulary (`GitHub answers from "<recording>"`, `GitHub answers <status> to "<path>"`, `GitHub is unreachable`, the request and download counts, `no request carried a token to "<host>"`): package 29, on this fixture.
- A synthetic 429: the test of package 24 that needs it writes it itself, saying in its first line that it is synthetic (T4).
- The golden move of T3 and `tests/parse/`: package 07.

## Risks

- From T4: the recordings age. Upstream's list changes with every release and the `rolling` asset with every build; the recordings are a fixed day's answer, which is what tests need. Recording again is one command, and the pull request that does it is reviewed like an expected-file change.
- From the cut: the facts later packages took from research 29 ("17 releases", the stable tag) may not hold in the new recording; the pull request's statement of what it holds is what those packages check against.
- From the cut: the size and digest rewrite means the served release objects are not byte for byte what GitHub sent. It is limited to the jar asset of three tags, documented in the README, and needed for any download to verify; a test of the real numbers reads the files.
- The fixture's jars carry only a manifest and empty classes. Anything that needs a real TLC class (none in the first wave) needs the integration tests.
