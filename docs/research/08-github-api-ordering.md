# 08: GitHub tags and releases API ordering and pagination

## Question

How do `GET /repos/tlaplus/tlaplus/releases` and `GET /repos/tlaplus/tlaplus/tags` order and paginate their results, what do the prerelease, draft and `make_latest` fields look like, what does `GET /releases/latest` return, and which of tlaup's current assumptions (in `src/tlaup/versioning/`) hold or break?

## Source

- Live API, observed with `gh api` and `curl` on 2026-11-14 (server dates show 2026-11-15 UTC).
- Captured data: `tests/fixtures/research/08-github-api/` (trimmed; see its `README.md`).
- GitHub REST docs:
  - Releases: https://docs.github.com/en/rest/releases/releases (List releases, Get the latest release, Create a release / `make_latest`)
  - Repository tags: https://docs.github.com/en/rest/repos/repos#list-repository-tags
  - Pagination: https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api
  - Rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- tlaup code: `src/tlaup/versioning/api.py`, `src/tlaup/versioning/resolver.py`, `src/tlaup/cmd/tools/install.py`, `src/tlaup/resources/default_config.yaml`.

## Short answer

- Releases come back newest first by `created_at` (the commit date, not the publish date), with one observed inversion. Tags come back newest first by a version-aware name sort, not by commit date. Names that are not versions sort after `v1.x` in reverse lexical order: `v1.x` tags, then `rolling`, then the CalVer tags `2026.MM.DD.HHMMSS`.
- Default `per_page` is 30, the maximum is 100. Upstream today has 17 releases (1 page at any size) and 114 tags (4 pages at 30, 2 pages at 100).
- `prerelease` and `draft` are booleans on each release object. `make_latest` is a request-only parameter and never appears in responses. `rolling` and `v1.8.0` are both `prerelease: true`.
- `GET /releases/latest` returns the newest non-prerelease, non-draft release by `created_at`: today `v1.7.4`.
- tlaup fetches one page of 30 for each list. Today that happens to cover everything it uses, but it breaks as soon as one more `v1.x` tag appears: `rolling` falls to page 2 and disappears.

## Confidence

Verified for the observed ordering, counts, flags, `latest` and rate limits. Partly verified for the general tag-sort rule: observed on three repositories, not documented by GitHub, and I cannot create tags to test edge cases such as `v1.10.0` versus `v1.9.0` on this repository (I checked it on other repositories).

## Evidence

### Releases ordering

`gh api 'repos/tlaplus/tlaplus/releases?per_page=100' --paginate --slurp` returned 17 releases, one page, no `Link` header. In API order:

```
v1.8.0  created 2026-11-15T00:05:18Z published 2026-11-15T00:29:14Z prerelease=true  jar
rolling created 2026-11-15T00:05:18Z published 2026-10-23T14:04:03Z prerelease=true  jar
v1.7.4  created 2024-08-08T13:25:09Z published 2024-08-05T20:16:41Z prerelease=false jar
v1.7.3  created 2023-03-20           published 2024-08-05T19:53:43Z
v1.7.2  created 2022-02-02           v1.7.1 created 2020-12-30 (published 2022-02-23)
v1.7.0 v1.6.0 v1.5.7 v1.5.6   (jar present)
v1.5.5 v1.5.4 v1.5.3 v1.5.2 v1.5.1 v1.5.0 v1.4.8   (no tla2tools.jar asset)
```

Checking adjacent pairs in the saved data:

- `created_at` is descending everywhere except one pair: `v1.5.1` (2015-06-01T10:37) is listed before `v1.5.0` (2015-06-01T10:52).
- `published_at` is not the order key: five inversions (`v1.7.2`/`v1.7.1`, `v1.5.3`/`v1.5.2`, `v1.5.2`/`v1.5.1`, `v1.5.1`/`v1.5.0`, `v1.5.0`/`v1.4.8`).
- The GitHub docs for List releases do not state an order. The "latest" docs say `created_at` is "the date of the commit used for the release, and not the date when the release was drafted or published." That matches what is seen.
- `rolling` shows the trap: its `created_at` is 2026-11-15 (moves with the tag), but `published_at` is 2026-10-23 (the first publish). `updated_at` is 2026-11-15T00:32:15Z. The `tla2tools.jar` asset on `rolling` is replaced on each build; today it is 4510884 bytes, the same size as the jar on `v1.8.0`, and the tag points at the same commit `bc1b506` as `v1.8.0`.
- No release is a draft. Drafts are visible only to users with push access (docs, List releases), so an unauthenticated client never sees them.
- Release object keys (checked on one item): `assets, assets_url, author, body, created_at, draft, html_url, id, immutable, name, node_id, prerelease, published_at, reactions, tag_name, tarball_url, target_commitish, updated_at, upload_url, url, zipball_url`. There is no `make_latest` key (zero matches in the 17-release dump).
- `make_latest` (true / false / legacy) is only a parameter of "Create a release" and "Update a release". Per the docs, drafts and prereleases cannot be set as latest, and `legacy` means "determined based on the release creation date and higher semantic version".

### Tags ordering

`gh api 'repos/tlaplus/tlaplus/tags?per_page=100' --paginate --slurp`: 114 tags. In API order:

```
v1.8.0 v1.7.4 v1.7.3 v1.7.2 v1.7.1 v1.7.0 v1.6.1 v1.6.0 v1.5.7 ... v1.5.1 v1.5.0 v1.5.0rc1
v1.4.8 ... v1.4.3c v1.4.3b v1.4.3a v1.4.2 ... v1.3.1        (29 v1.x tags)
rolling
2026.11.15.002146 2026.11.06.222357 ... 2026.04.27.203507    (84 CalVer tags, descending)
```

- Not commit date: `rolling`, `v1.8.0` and `2026.11.15.002146` all point at `bc1b506`, but `rolling` and CalVer tags come after all the `v1.x` tags regardless of age.
- Not pure reverse lexical: `v1.5.0` is listed before `v1.5.0rc1`. In plain reverse lexical order `v1.5.0rc1` would come first.
- Other repositories show the same rule. `cli/cli`: `v2.104.0 v2.103.3 ... v2.100.0 v2.99.0` (so `v2.100.0` sorts above `v2.99.0`, which is numeric, not lexical). `tlaplus/vscode-tlaplus`: `v2024.8.151650 ... v1.6.0-alpha.2 v1.6.0-alpha.1 v1.5.5-beta.1 v1.5.4 v1.5.4-beta.1`, so a prerelease suffix sorts below its release, and `v2024.8...` sorts above `v1.x` as a number. `tlaplus/CommunityModules`: `outdated latest 20200107.1 ...`, where non-version names come first in reverse lexical order.
- Working rule (observation only, undocumented): names are sorted descending by a version-aware comparison (numeric parts compared as numbers, a suffix such as `rc1` or `-beta.1` sorts below the bare version), and names that do not start like a version fall into reverse lexical order. In this repository `v...` beats `rolling` beats `2026...`, which is why CalVer tags come last. The docs for List repository tags state no order.
- The roadmap should not rely on this order at all (see Implications).

### Pagination and sizes

- `GET .../tags` with no parameters returns 30 items (`gh api repos/tlaplus/tlaplus/tags --jq length` = 30) and `Link: <...tags?page=2>; rel="next", <...tags?page=4>; rel="last"`.
- `per_page=30`: next page 2, last page 4 (114 / 30 = 3.8). `per_page=100`: next page 2, last page 2. `per_page=500` silently becomes 100 (100 items returned, `last` is page 2). The pagination docs confirm values above the maximum are reduced without any error.
- `page=2&per_page=100`: `Link` has `rel="prev"` and `rel="first"` only. `page=3` returns `[]`.
- Releases: `per_page=100` gives 17 items and no `Link` header; the default gives 17 as well.
- The next/last URLs are on `api.github.com/repositories/50906927/...`, not the repo path. A client should follow `rel="next"` rather than rebuild URLs.

### `GET /releases/latest`

`gh api repos/tlaplus/tlaplus/releases/latest` returned: `tag_name v1.7.4`, name "The Xenophanes release", `prerelease false`, `draft false`, `created_at 2024-08-08T13:25:09Z`, 6 assets including `tla2tools.jar`. Newer `v1.8.0` and `rolling` exist but are prereleases and are skipped. Docs: "the most recent non-prerelease, non-draft release, sorted by the created_at attribute." Saved as `releases-latest.trimmed.json`. It does not need pagination, but it returns one release only, so it cannot answer "which versions exist". It also depends on `created_at`, which for a retagged release moves, and on the maintainers marking prereleases correctly.

### `rolling` and `v1.8.0`

- Both are `prerelease: true`, `draft: false` (`gh api repos/tlaplus/tlaplus/releases/tags/rolling` and `.../tags/v1.8.0`).
- `v1.8.0` carries `tla2tools.jar` (4510884 bytes) and Toolbox zips; it is a prerelease today, so it is not "stable" until upstream clears the flag. `rolling` has only `tla2tools.jar`.
- `v1.8.0` is not "newest by `created_at`" in a way that matters: it ties `rolling` at 2026-11-15T00:05:18Z.

### Rate limits

Unauthenticated: 60 requests per hour per IP (`x-ratelimit-limit: 60` seen by `curl -I`); authenticated: 5,000 per hour (`X-Ratelimit-Limit: 5000` seen with `gh`). Docs: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api. A full read costs 1 (releases) + 2 (tags at per_page=100) = 3 requests.

### How tlaup uses this today

`src/tlaup/versioning/api.py` and `default_config.yaml`:

| Assumption in code | Holds? |
| --- | --- |
| One request per list is enough (`requests.get(url, params={"per_page": 30})`, no `Link` handling). | Holds by luck today, breaks soon. Tags page 1 at 30 = 29 `v1.x` tags + `rolling`, exactly full. The next `v1.x` tag pushes `rolling` onto page 2, and tlaup would stop seeing it. The CalVer tags are never fetched (they have no releases, so no loss today). |
| `per_page` 30 is acceptable. | Allowed (the default), but 100 is the maximum and costs one request fewer pages. |
| Versions are built by walking tags in API order and joining to releases by `tag_name`; tags without a release are dropped. | Holds today: `v1.6.1`, `v1.5.0rc1`, and all CalVer tags have no release and are dropped. A release whose tag is beyond the fetched page is also dropped. |
| `install.py` line 61: default is the first entry in that list with `prerelease` false (`next(v for v in versions if not v.prerelease)`). | Gives `v1.7.4` today (skips `v1.8.0`, `rolling`), the correct answer, but only because tags come in version-descending order and the code never compares versions. It also falls back to `versions[0]` when all are prereleases, which would install a prerelease while calling it the default. |
| Release `prerelease` flag marks unstable builds. | Holds: both `v1.8.0` and `rolling` are flagged. |
| `published_at` is stored and used as a tiebreaker for local sorting (`resolver.py`). | Unsafe for `rolling`: its `published_at` is the first publish date (2026-10-23) while the jar changes daily. Not a valid freshness signal. |
| `_parse_semver` (`resolver.py`) accepts `vN.N.N` only. | `rolling` and CalVer names give `None`, so they sort below all semver names locally. That is the desired direction for `rolling` as "not stable", but nothing else orders them. |
| Jar asset named `tla2tools.jar`. | Holds for `v1.6.0` and later, `v1.7.x`, `v1.8.0`, and `rolling`. Releases `v1.4.8` to `v1.5.5` have no such asset. |

Not checked: `CommunityModules` use of the same code (its tags are date numbers such as `202611060952`, and its first tag names `outdated`, `latest` sort first), nor what `tlaup` does when GitHub returns a 403 rate-limit response beyond `requests.RequestException`.

## Implications for the roadmap

- Milestone 1: follow `Link: rel="next"` until it is absent, with `per_page=100`. Three requests cover everything upstream today.
- Choose "latest stable" by parsing release `tag_name` as a version and taking the maximum among releases with `prerelease == false` and `draft == false` and a `tla2tools.jar` asset. Do not use API order (releases order by `created_at` with an inversion; tags order is undocumented). `GET /releases/latest` agrees today (`v1.7.4`) and is a usable cross-check, not the primary source.
- Never fall back to `versions[0]` when no stable version exists; report that nothing stable is available.
- Milestone 3: `rolling` has no version, is a prerelease, shares a commit with `v1.8.0` right now, and its `published_at` is stale. Treat it as a special named channel: identify it by `tag_name == "rolling"`, compare freshness by the release `updated_at` or the asset's `updated_at` (today 2026-11-15T00:32:15Z), or by the tag's commit sha, not by `published_at`. It must never be picked as "latest stable".
- CalVer tags have no releases. The release list is the better source than the tag list for what can be downloaded; tags are needed only to get the commit sha (`tag.commit.sha`) that `RemoteVersion` stores.
- `v1.8.0` is a prerelease today. Whether upstream will clear that flag is unknown; the code must not hard-code that `v1.8.0` is stable or unstable.
- The ordering rule for tags is observation only; a fixture-based test should assert that the selection does not change when the list is shuffled.

## Open follow-ups

- Ask upstream (not done; searching and contacting were out of scope) whether `rolling` is meant to stay a prerelease and whether `v1.8.0` is to be released as stable.
- Check `CommunityModules` tags/releases (same code path via `community_modules` URLs) for its own ordering and latest-selection needs.
- Check how tlaup should behave on HTTP 403/429 from rate limiting (read `Retry-After` and `X-RateLimit-Reset`); only the headers were checked here.
- Whether the release list is ever longer than 100 for this repository: 17 today, so the `Link` loop is only needed for tags, but it should be written for both.

## Date checked

2026-11-14 (GitHub server timestamps read 2026-11-15 UTC).
