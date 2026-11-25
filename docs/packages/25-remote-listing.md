# 25. Remote listing

Size: M. Suggested model: mid-tier. Status: ready. What is cached was settled with the maintainer (question Q7): the release list as it came back, and never an error answer ([12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache)).

## Goal

`tlaup.versioning.remote` turns GitHub's answers into `Release` and `Asset` values, lists the releases through the client with a lookup cache that carries its own fetch time, looks one tag up fresh, and resolves a version spec to what upstream publishes now. `stable_of` in `tlaup.versioning.order` chooses the stable release by version number. No command uses it yet.

## Covers

- Roadmap items:
  - "Read all pages of tags and releases; choose 'latest stable' by version, not by API order; never install a prerelease while saying 'stable'." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: which list is read (releases only, a listed departure), and `stable`. Paging is the client's (package [24](24-github-client.md)); the commands are package 29.
  - "Do not crash on a non-JSON or non-list API response. Key the remote-version cache on the request, not only the asset name, and write it atomically. `tools upgrade`, and an install of a moving tag, check the remote again ..." ([milestone 1](../roadmap.md#milestone-1-a-runner-you-can-trust)), in part: the cache, and the two functions that never read it (`release`, `resolve`). The first sentence is package 24; upgrade and install using the fresh lookup is package 27.
  - "Adopt upstream's `rolling` release ..." ([milestone 3](../roadmap.md#milestone-3-reproducibility)), in part: `stable` never picks a prerelease, and releases sort with `rolling` first. Package [23](23-tool-store.md) did the same for builds.
  - "Download and GitHub failure modes are tested ..." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)), in part: four rows of T6, listed below.
- Design sections:
  - [12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache): `Release`, `Asset`, `Remote`, the cache, `Freshness`, and V8's unit tests. Not here: "`tool list` in the first wave" (the table, its columns, which releases are rows, `installed, not upstream`, the `warning:` line), `tool_list.feature`, `tlaup cache clean` removing `<cache>/remote/`, and V8's changelog entries; those are packages 29 and 45. The removal of `fetch-cache clear` and its changelog line are [23 C1](../design/23-command-layout.md#c1-command-tree)'s, not V8's.
  - [02 X4](../design/02-cross-cutting.md#x4-rolling): `stable_of`, and the unit test over the shuffled recording. The order of installed builds was package 23.
  - [12 V2](../design/12-tools-and-downloads.md#v2-version-order-and-lookup): `stable_of` only.
  - [01 T6](../design/01-testing.md#t6-download-and-github-failure-tests): four rows.
  - [01 T4](../design/01-testing.md#t4-fakes-at-the-edges), "Time": the cache stores its fetch time inside the file.

## Depends on

- [24](24-github-client.md): `GitHubClient.get_paged`, `get_json`, and the status code on the error for an answer of 400 or above.
- [23](23-tool-store.md): `tlaup/versioning/order.py` with `version_key` and the rule that orders names, to which this package adds `stable_of`.
- [22](22-version-spec-and-jarinfo.md): `VersionSpec`, the argument of `Remote.resolve`.
- [05](05-github-recordings.md): the `github` fixture and the recordings `releases` (the list and the per-tag objects for `rolling`, `v1.8.0`, `v1.7.4`) and `releases-paged`.
- [02](02-errors-and-paths.md): `AppPaths.remote` (the cache folder, `<cache>/remote/`), `VersionNotFound`, `RemoteDataError`.
- [03](03-test-foundation.md): the isolation fixture and the pytest settings.

The draft named 24 and 23. 22, 05, 02 and 03 are added because they are used directly; none changes the order.

## Files

Creates:

- `src/tlaup/versioning/remote.py`
- `tests/unit/versioning/test_remote.py`

Changes:

- `src/tlaup/versioning/order.py`: adds `stable_of`. It needs `Release` for its annotations only; import it under `TYPE_CHECKING`, so that `order.py` does not import `remote.py` and with it the client.
- `tests/unit/versioning/test_order.py`: the tests of `stable_of` and of the order of releases.

Must not touch: the old `versioning/api.py`, `schema.py` (it holds the old `FetchStatus` and `RemoteVersion`; the new `Freshness` and `Release` are separate types in `remote.py`), `paths.py`, `cache/github.py`, `cmd/tools/list.py`, `cmd/fetch_cache/`. Package 29 deletes them with the old code. Their old tests and the old fixtures `releases.json` and `tags.json` went in 03b (decision D62).

Deletes: nothing.

Shared within the track: `order.py` and `test_order.py` with package 23, which is finished before this starts.

## Interfaces

Provides, from [12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache):

```python
# tlaup/versioning/remote.py
@dataclass(frozen=True)
class Release:
    tag: str; prerelease: bool; draft: bool
    created_at: str; published_at: str | None
    asset: Asset | None                 # the tla2tools.jar asset, None if the release has none

@dataclass(frozen=True)
class Asset:
    id: int; size: int; digest: str | None; updated_at: str
    download_url: str                   # the release object's browser_download_url (V7)

class Remote:
    def __init__(self, client: GitHubClient, cache_dir: Path, *, now): ...
    def releases(self, *, max_age: float = 3600) -> tuple[list[Release], Freshness]
    def release(self, tag: str) -> Release          # GET /releases/tags/<tag>; never cached
    def resolve(self, spec: VersionSpec) -> Release # "stable" -> stable_of(releases(max_age=0)); else release(tag)
    def cached(self) -> list[Release] | None        # written by stage 4: the cached list whatever its age; None when
                                                    # there is no readable cache file; never a request (for X3's `latest`)
```

`Freshness` has today's four states: online, cached, stale (the network failed and old data is shown), unavailable.

From [12 V2](../design/12-tools-and-downloads.md#v2-version-order-and-lookup):

```python
# tlaup/versioning/order.py
def stable_of(releases: Sequence[Release]) -> Release | None
```

The field names of `Release` and `Asset` are fixed by `tests/stateful/test_tool_store.py`, which builds both by keyword: `Asset(id=, size=, digest=, updated_at=, download_url=)` and `Release(tag=, prerelease=, draft=, created_at=, published_at=, asset=)`. Keep those names.

Two helpers that later packages need and V8 does not name. Written by stage 4; a worker may rename them:

```python
def parse_release(data: Any, *, url: str) -> Release
    # one release object as GitHub sends it -> Release; RemoteDataError naming `url` when it is not an object
    # or a field tlaup reads is missing or of the wrong type. fetch_build (package 26) uses it when it
    # fetches the release again after a mismatch.

def write_cache(cache_dir: Path, url: str, data: Any, fetched_at: datetime) -> None
    # the one writer of a cache file. The step "the release list is cached from <recording>, <n> minutes old"
    # (01 T5; packages 18 and 29) must write through it, not build the file by hand.
```

The cache file, from V8: `<cache>/remote/<first 16 hexadecimal digits of the SHA-256 of the address>.json`, holding `{"schema": 1, "url": ..., "fetched_at": <UTC>, "data": ...}`.

Consumes: `GitHubClient` (24); `version_key` and the name order (23); `VersionSpec` (22); the errors and `AppPaths.remote` (02).

Used later by: `fetch_build` (26); `Install`, `Upgrade`, `install`, `upgrade`, `same_as_published` (27), whose `Lookup = Callable[[str], Release]` is "what upstream publishes under a name now"; `choose_first_build` (28), which needs the dates of the stable and rolling releases; `tool list` (29); the refusal of `latest`, which names the stable tag of `cached()` ([02 X3](../design/02-cross-cutting.md#x3-version-syntax), 29); `cache clean` (45).

`cached()` is added by stage 4 for X3's refusal of `latest`, whose bracket names "the stable release of the cached release list, whatever its age, when a cache file exists" and makes no request (finding B16). `releases(max_age=...)` cannot serve it: with no cache file or an old one it asks GitHub.

## Tests that must pass

Plain pytest, with `responses` serving the recordings through the `github` fixture and an injected clock.

The rows of [01 T6](../design/01-testing.md#t6-download-and-github-failure-tests) assigned to this package, in `tests/unit/versioning/test_remote.py` unless said:

| T6 row | Expectation here |
| --- | --- |
| 404 on a tag | `Remote.release("nosuch")` raises `VersionNotFound`; nothing is written to the cache folder. |
| Release without `tla2tools.jar` | It is in `releases()` with `asset` `None`; `stable_of` never returns it; `resolve` of its tag raises `VersionNotFound` with the reason. The real list has seven such releases (`v1.4.8` to `v1.5.5`). |
| List shuffled | `tests/unit/versioning/test_order.py`: the recorded list of 17 releases, shuffled 20 ways with seeded shuffles, gives the same order and the same `stable` each time (`v1.7.4` in the recording). |
| All releases are prereleases | `stable_of` returns `None`; `resolve` of `stable` raises `VersionNotFound`; never the first entry. |

V8's own unit tests:

- The cache with an injected clock: at 59 minutes `releases()` makes no request and says cached; at 61 it makes one and says online.
- A corrupt cache file is treated as absent (a request is made; no error).
- Two different base addresses do not share a cache file.
- The network fails with a cache present: the old data and stale. With none: an empty list and unavailable. Neither raises.
- The list is cached as it came back (question Q7, settled): `releases()` over the `releases` recording writes a cache file whose list holds all 17 releases, the seven without a `tla2tools.jar` included (inventory row T21, this package's half; the other half, that `tool list` shows none of the seven, is [29](29-tool-commands.md)'s).
- An error answer is never written to the cache: a 404, a 503 and a rate-limit answer write no cache file when there is none, and leave an existing one byte for byte as it was.
- `cached()`: with no cache file, `None`; with a cache file a day old, its releases, and no request is sent (the `github` fixture's count is 0); with a corrupt one, `None`.
- `release(tag)` neither reads nor writes the cache: with a one-minute-old cache present, one request is sent, and the cache file is unchanged afterwards.
- `resolve` of `stable` refreshes the list even with a one-minute-old cache (one request), and when that request fails it raises the network error; it never answers from stale data.
- A tag with a slash is percent-encoded in the requested path ([02 X3](../design/02-cross-cutting.md#x3-version-syntax) allows `/` in a tag; [V7](../design/12-tools-and-downloads.md#v7-github-client), "Addresses built from names").
- A list where a release object is expected, and a release object without `tag_name` or with an asset without `size`, are `RemoteDataError`.
- `releases()` over the `releases-paged` recording gives the same 17 releases as over `releases` (the paging itself is tested in package 24).
- The cache file is written to a temporary file and moved into place: after a write, the folder holds exactly one file for that address.

`stable_of`, in `test_order.py`, beside the two rows above: a draft is skipped; a release with a higher number that is a prerelease does not win (`v1.8.0` is one in the recording); `v1.5.0rc1` is below `v1.5.0`.

Old tests: none is left (03b). The pull request names the inventory row it covers (T21, the cache half). Stateful tests: `tests/stateful/test_tool_store.py` builds `Release` and `Asset` values, but it also needs `install.py`; its `pending` markers are removed by package 27.

## Changelog

None in this package. Package 29 writes V8's entries (Fixed: "Only the first 30 tags were read from GitHub, so `rolling` would have disappeared at the next upstream release." and the column label; Changed: the two `tool list` lines, the second D64's "`installed, not upstream` (was `local only`)") and X4's (Changed: "`rolling` is listed first in `tlaup tool list`, then versions by number."; Fixed: "`tlaup tool install` could offer a prerelease as the stable version when no stable release was in the first page of results.").

## Context for the worker

Decisions:

- D32: `rolling` is the upstream release tagged `rolling`; it sorts above every numbered version. Nothing sorts by GitHub's order, by `published_at`, or by a file's modification time. No tag is assumed to stay put.
- D31: `stable` is the highest version number among releases that are not prereleases, not drafts, and have the jar. `latest` does not exist.
- "A build's commit comes only from the jar's manifest; the tag's commit is not fetched" (design agent, README): so only releases are read. The tags endpoints are not called at all, which is a listed departure from the roadmap's "read all pages of tags and releases".
- D33 and [01 T4](../design/01-testing.md#t4-fakes-at-the-edges): time is injected; the cache's age is computed from `fetched_at` with the injected clock, not from the file's modification time.

Facts from research that the design restates:

- The release list is 17 releases today, one page at `per_page=100`. Ten have the jar (`rolling`, `v1.8.0`, and `v1.7.4` down to `v1.5.6`); seven do not.
- `rolling` and `v1.8.0` are both marked as prereleases and hold the same jar today. The `rolling` release's `published_at` is the day it was first created and says nothing about the jar; the asset's `updated_at` does.
- Upstream replaces an asset by deleting it and uploading again, so for one to three seconds a release has no jar and its download address answers 404.
- `GET /releases/latest` is not used: it is one release and depends on the maintainers' flag.
- Assets uploaded since mid-2025 have a `digest` (`sha256:` and 64 digits); `v1.7.4` and older have none.

Points that are easy to miss:

- **Install and upgrade ask fresh.** `release(tag)` is never cached and `resolve("stable")` refreshes the list. Only `tool list` uses the cached list. A stale answer here is exactly the bug the roadmap item names ("already up to date" for an hour).
- **`releases()` does not raise when the network fails**; it reports stale or unavailable. `resolve` must not accept either. Keep one inner function that fetches and raises, and build both on it.
- **The cache key is the address of the request**, so two repositories never share a file. Store the address as tlaup built it; it has no secret in it.
- **A cache file that cannot be read, or has another `schema`, is absent.** Never an error, never repaired in place; the next successful fetch replaces it.
- **Which asset.** The one named `tla2tools.jar`. `download_url` is its `browser_download_url`; the asset's API address is not used (V7).
- **`digest` is kept as GitHub wrote it**, or `None`. Reading it (`sha256:` prefix, case) is the downloader's rule (package 26).
- **A release's `prerelease` and `draft` flags are upstream's now.** What an installed build recorded is the store's.
- **The order of releases** for `tool list` and for the shuffled test is X4's rule applied to tags: `rolling`, then numbers highest first, then other names. Use the function package 23 wrote for names; do not write the rule a second time.
- **Who refuses a release without a jar.** V8 says `stable` never offers one and T6 says asking for one is `VersionNotFound` with the reason; neither says which function raises. Here: `release(tag)` returns it with `asset` `None` (a listing must be able to show it), and `resolve` raises. Package 26's `fetch_build` raises the same error if it is handed one anyway.
- **Freshness carries no reason.** V8's `tool list` prints one `warning:` line when the network is unavailable, and the four states alone do not say why. If package 29 will need the reason, keeping the caught error beside the state costs nothing now; the design does not ask for it.
- No printing: the module returns values or raises ([00](../design/00-overview.md#packages-after-the-first-wave)).

What is cached (question Q7, settled; V8 rewritten). **The release list is cached as it came back**: every release GitHub returned, those without a `tla2tools.jar` included, with nothing removed or added. **An error answer is never cached**: a 404, a 5xx, a rate limit, or a body that is not a list of releases writes no cache file and leaves an existing one as it was. A release whose jar is missing only because upstream is between deleting and uploading it is cached that way too, and `tool list` then shows the release without its jar for up to an hour; install and upgrade never read the cache, so they are not affected. Hiding releases without a jar is `tool list`'s ([29](29-tool-commands.md), decision D64), not the cache's: the cache keeps them.

About the recordings. Research 29's `releases-paged` bodies were cut to a field list that leaves out the assets' `updated_at`, which `Asset.updated_at` reads and package 27's `same_as_published` compares. Package 05 owns the recordings and the record script; if the recording on `main` still lacks the field when this package starts, the fix is a recording with the field (05's script), not a parser that accepts its absence: a real answer always has it, and a tolerant parser would hide a real `RemoteDataError` case. Say in the pull request what you found.

State of `main` when this starts: the 0.8.x code with packages 01 to 03, 05 and 22 to 24 on top. The old `versioning/api.py` still reads one page of tags and one of releases into `<cache>/github_cache_tla2tools_jar.json` for the old commands; the new cache lives in `<cache>/remote/` and shares nothing with it.

## Done when

- The tests above pass; `uv run poe lint` and `uv run poe test` pass; CI is green.
- No file listed under "Must not touch" is in the diff.
- The pull request says how `resolve` gets the network error, what the cache's `data` holds, and what was found about `updated_at` in the recordings.

## Out of scope

- The client, paging, the token: package [24](24-github-client.md).
- Downloading and verifying a jar, reading `digest`: package [26](26-download-and-verify.md).
- `same_as_published`, `install`, `upgrade`, the commit comparison (V12, V4): package 27. The first-run prompt and its two dates (V9): package 28.
- `tool list` and its table (hiding releases without a jar, `installed, not upstream`), `tool_list.feature`, the changelog entries, deleting `versioning/api.py`, `cache/github.py` and `cmd/fetch_cache/`: package 29.
- `tlaup cache clean` removing `<cache>/remote/`: package 45.
- Conditional requests with ETags (rejected in V8).

## Risks

- From X4: `stable` among installed builds can lag behind upstream; that is the store's side and accepted.
- From V8: reading only releases means a release whose asset is being replaced looks, for a second, like one with no jar. Install and upgrade answer that with the retry of package 26.
- From T6: a row can name a state the finished code cannot reach; it is then removed with a line in the pull request.
- From the cut: `write_cache` is used by a test step that package 29 writes. If it builds the file by hand instead, the scenario tests a format the code may not read.
