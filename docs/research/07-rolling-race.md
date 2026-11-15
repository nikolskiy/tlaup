# 07. The tag and asset race on rolling builds

## Question

Can the jar change while a download or a version lookup is in progress? What windows exist in which (a) the tag points at a new commit but the asset is still the old jar, (b) the asset is missing, (c) the redirect from an asset download URL serves a different blob than the API metadata (digest, size, updated_at) describes? How long does each last, how often do builds happen, and what does an in-flight download of a replaced asset see?

## Source

- `docs/analysis/01-merit-and-landscape.md` section 3.3 point 4 (reasoned from code, not reproduced).
- tlaup: `src/tlaup/versioning/api.py` (lookup), `downloader.py` (download).
- Upstream workflow `.github/workflows/main.yml` in tlaplus/tlaplus (read through `gh api repos/tlaplus/tlaplus/contents/.github/workflows/main.yml`, master at 2026-11-15), and the real run 43656441007 (https://github.com/tlaplus/tlaplus/actions/runs/43656441007), which wrote the current `rolling` and `v1.8.0` state.
- gh CLI source `pkg/cmd/release/shared/upload.go` (cli/cli), for what `--clobber` does.

Labels below: **[O]** observed (command run, output seen), **[R]** reasoning from code or docs, **[U]** not verified.

## Short answer

Yes. The jar and its tag change in separate steps of one CI run, with no lock, so windows exist. Measured on the run of 2026-11-15:

1. **v1.8.0, asset new / tag old: about 4.5 minutes** [O]. The `Upload release assets` step replaced the jar at 00:27:39Z; the `Update tags` step moved the tags at about 00:32:11Z. In between there is a 3-minute rsync to INRIA. Anyone who reads the tags API in that time gets the old commit and downloads the new jar.
2. **rolling, tag new / asset old: about 3 seconds** [O/R]. This is the reverse order from what the analysis report says. For `rolling` the tag is pushed first (00:32:10 to 00:32:12), then `gh release upload --clobber` runs (00:32:12 to 00:32:15, new asset created 00:32:14Z).
3. **Asset missing: about 1 to 3 seconds per replacement, for both releases** [O/R]. Both replacements are delete-then-upload (the v1.8.0 step does `curl -X DELETE` then `curl -X POST`; `gh release upload --clobber` is delete then upload in its source). During the gap the download URL answers 404 (not observed live; see below).
4. **Metadata vs blob mismatch (c): not seen, and not expected beyond the 1 to 3 second gaps.** After the build, the API digest, size and `updated_at` matched the downloaded bytes exactly [O]. Each asset id has its own blob, so a redirect for a given asset id cannot serve another asset's bytes [R]; the mismatch risk is that `browser_download_url` is addressed by tag name, not asset id, so it follows whatever asset is current at request time [R].
5. **The largest window comes from tlaup itself, not from upstream** [R]. `fetch_remote_versions` caches the tags and releases lookup for 3600 s (`api.py`, `time.time() - mtime < 3600`) and the jar is then fetched from a tag-named URL. A build that lands inside that hour makes the cached commit SHA wrong for the jar that is downloaded. Window up to one hour per build, longer than any upstream window.

Builds are frequent (below), so the windows are real but short; the realistic failure is "a jar installed under the old commit SHA", rarely "a truncated or missing jar".

## Confidence

Partly verified. The workflow order, step times, API digests, tag state and redirect behaviour are observed. Not observed live: any request landing inside a window (no build happened during my work; the last one finished 2026-11-15 00:32:41Z, I started about 08:15Z). The behaviour of an in-flight download during asset replacement is reasoning only.

## Evidence

### Upstream workflow order [O]

`.github/workflows/main.yml`, job `build`, ubuntu-latest only, on push to master / repository_dispatch / workflow_dispatch. No `concurrency:` group (grep returned nothing). Steps in order:

1. `Upload release assets`: finds the release named "The Clarke release" (tag `v1.8.0`), then for each asset (jar, Windows zip, Linux zips, deb, p2repository, macOS zips) does `GET assets` to find the id, `DELETE .../releases/assets/$ID`, `POST uploads.github.com/.../assets?name=...`. Then PATCHes the release body, then PATCHes `{"draft": true}` and `{"draft": false, "prerelease": true}` ("Refresh published_at", issue 1211). The comment says "if delete fails we still try to upload".
2. `Upload assets to INRIA` (rsync, minutes).
3. `Update tags`: `git tag -f v1.8.0`, `git tag -f rolling`, runs `tlc2.REPL 'TLCGet("revision").calver'` from the new jar, creates an annotated CalVer tag, then one `git push --follow-tags --tags --force`.
4. `Update rolling release`: `gh release view rolling || gh release create`, then `gh release upload rolling --clobber .../tla2tools.jar`.
5. `Upload to Maven Central`.

So the `v1.8.0` jar is replaced first and its tag later; the `rolling` tag moves first and its jar later.

### Step times of run 43656441007 [O]

Command: `gh run view 43656441007 -R tlaplus/tlaplus --json jobs --jq '.jobs[]|select(.name|test("ubuntu"))|.steps[]|[.name,.startedAt,.completedAt]'`

| Step | Start (UTC, 2026-11-15) | End |
|---|---|---|
| Build with Maven (Linux) | 00:20:47 | 00:27:32 |
| Upload release assets | 00:27:37 | 00:29:15 |
| Upload assets to INRIA | 00:29:15 | 00:32:10 |
| Update tags | 00:32:10 | 00:32:12 |
| Update rolling release | 00:32:12 | 00:32:15 |

Assets after the run (`gh api repos/tlaplus/tlaplus/releases`):

- `v1.8.0` / `tla2tools.jar`: id 749260120, `created_at` 00:27:39Z, size 4510884, digest `sha256:7e53aa63...80e9`. Release `published_at` 00:29:14Z (the draft toggle at the end of step 1).
- `rolling` / `tla2tools.jar`: id 749270023, `created_at` 00:32:14Z, `updated_at` 00:32:15Z, same size and digest. Release `published_at` stays 2026-10-23 (not refreshed).
- Both tags (`git/ref/tags/rolling`, `git/ref/tags/v1.8.0`) point to `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c`.

The step log (`gh run view --job 132635879863 --log`) contains no output for the curl calls (they run with `-s`), so the exact length of each delete-to-create gap is not logged. Bounds: step 1 started 00:27:37.4Z and the new jar's `created_at` is 00:27:39Z, so the first gap (which includes the id lookup, delete, and upload of 4.5 MB) is at most about 2 s; the rolling gap is at most 3 s (step 00:32:12 to 00:32:15, `created_at` 00:32:14Z).

Draft toggle [R from workflow]: for a short moment (between the two PATCH calls, probably 1 to 2 s, `published_at` shows 00:29:14Z) the `v1.8.0` release is a draft, so unauthenticated release listings do not contain it and `/releases/download/v1.8.0/...` should 404. In `_process_remote_versions` a tag without a matching release is silently skipped, so a lookup in that moment drops `v1.8.0` from the list. Not observed.

### Build frequency [O]

`gh run list -R tlaplus/tlaplus -w CI --branch master --limit 200` for runs created since 2026-09-15 (61 days): 62 runs, 57 successful. Median run length of successful runs 23 minutes; median gap between run starts 3.9 hours; shortest gap 0.7 minutes. Six pairs of runs overlap in time (e.g. 2026-10-26 22:15:34Z and 22:16:34Z, 22:16:34Z and 22:58:20Z). With no concurrency group, two overlapping runs can interleave their delete/upload and tag steps, so a state where the tag and asset belong to different runs is possible beyond the single-run windows [R]. Most recent runs: 2026-11-15 00:05, 2026-11-06 x4, 2026-11-03, 2026-11-02 x3.

Each build opens windows 1 to 3 (about 4.5 min plus a few seconds) once, so in a day with 2 builds the exposed share of time is about 0.5 percent for `v1.8.0` lookups and far less for `rolling`. Plus the cache effect in item 5 above.

### Does the download URL change under you? [O]

```
curl -sI https://github.com/tlaplus/tlaplus/releases/download/rolling/tla2tools.jar
HTTP/2 302
location: https://release-assets.githubusercontent.com/github-production-release-asset/50906927/eb0e246f-...?sv=2018-11-09&sr=b&...&se=2026-11-15T09%3A15%3A42Z&skt=2026-11-15T08%3A15%3A06Z&...&sig=...&jwt=...
```

- `v1.8.0` redirects to a different blob id (`e9ac73ab-...`), so each asset has its own stored blob even when the bytes are identical.
- The signed URL is valid for about 1 hour (`skt` to `se`), and the parameters (`sv=2018-11-09`, `sr=b`, `skt`/`ske`) are the shape of an Azure Blob SAS token [R: inference from the parameter names].
- Downloading the redirect target: `sha256sum` of the file = `7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f`, equal to the API digest of asset 749270023; the final response had `content-length: 4510884` = API `size`, `last-modified: Sun, 15 Nov 2026 00:32:15 GMT` = API `updated_at`.
- The jar identifies itself: `META-INF/MANIFEST.MF` has `X-Git-Revision: bc1b506bdcad80bb518bf3776a9161c34ff0fc4c` and `X-Git-ShortRevision: bc1b506`; `java -cp r.jar tlc2.REPL 'TLCGet("revision")'` returned `[count |-> 9089, ..., tag |-> "bc1b506", calver |-> "2026.11.15.002146"]`. That equals the tag commit, so the post-download check the roadmap item asks for is feasible, and it can be read without running Java (manifest) or with `TLCGet("revision")` when Java is available. (The manifest has `Build-Rev: ${Build-Rev}` unexpanded; only `X-Git-Revision` is usable.)
- Note: `Build-Rev` and `Build-Tag` in the manifest are unexpanded placeholders in this build.

### In-flight download when the asset is replaced [R, not tested]

I could not test this without replacing an asset on a repository I control, which means publishing on GitHub; I did not do it. Reasoning:

- The redirect resolves the tag name to the current asset at request time. After the 302, the client talks to a signed blob URL that names the blob, not the tag or the asset id. A new upload creates a new asset id and a new blob (the two releases show different blob ids), so the old blob is not overwritten by a replacement [R].
- Whether the old blob keeps serving after `DELETE` of the asset record (and for how long) is not documented that I could find; I did not find a GitHub documentation statement either way [U]. If the storage layer deletes it immediately, an in-flight read may fail with a truncated body; a 4.5 MB transfer takes seconds, so the chance is small, and a truncated body would be caught by a content-length check or a zip validity check.
- Because a new upload cannot change the bytes behind an already issued signed URL, the case "download completes with the other jar's bytes mixed in" should not occur [R]. The cases that can occur are: 404 or 302-then-error during the missing window; whole old jar (still consistent, but tag mismatched); whole new jar.

### What tlaup does today [O from code]

- `api.py`: `fetch_remote_versions` calls the tags API and then the releases API as two requests (`_fetch_from_api`), joins them by tag name, takes `commit.sha` from the tag and `browser_download_url` from the asset. Result cached 3600 s in `github_cache_<asset>.json`; a stale cache is used if the network fails.
- Not recorded: asset id, `digest`, `size`, `updated_at` (the releases response contains them; `_process_remote_versions` keeps only name, url, published_at, prerelease).
- `downloader.py`: `_download_jar` streams straight into `version_dir/tla2tools.jar` (no temp file, no rename, no length check against `content-length`, no zip check, no digest check). On `RequestException`/`OSError` the version dir is removed; a body cut short without an exception is not detected by this code. `write_version_metadata` stores `target.full_sha` taken from the earlier lookup. The directory is named `<tag>-<short_sha>` so a wrong SHA is a wrong directory name.
- `download_version_from_url`: no SHA at all, uses a UTC timestamp.

## Implications for the roadmap

1. Milestone 1 "compare the commit the jar reports about itself with the expected commit" is justified by the evidence: the mismatch window is about 4.5 min per build for `v1.8.0`, seconds for `rolling`, and up to 1 hour because of tlaup's own lookup cache. The jar reports its commit in `META-INF/MANIFEST.MF` as `X-Git-Revision` (full SHA) without running Java; use that field, not `Build-Rev`.
2. On mismatch there are two sensible outcomes to design (design question, not decided here): trust the jar and rename the version directory to the jar's own revision, or refuse and retry. The jar's own revision is the stronger identity because it is read from the bytes installed.
3. "Download to a temporary file, check it is a valid jar, then rename" is justified: it handles a truncated body and the 404-during-gap case. It does not fix the tag mismatch. Add checks that the evidence shows are available for free: `content-length` equals bytes written, and the GitHub asset `digest` (sha256) equals the file hash. Both are in the releases response and are not recorded today.
4. Fetch the release object once (`releases/tags/<tag>` includes the asset id, digest, size) rather than relying only on the two list calls, and download by the asset's API URL or compare the redirect result with the digest, so the bytes verified are the bytes the metadata described. The digest check also covers the case where a rebuild lands between lookup and download, because a new jar has a different digest: the install will then fail the digest check rather than silently install the new jar. Retrying once is cheap.
5. The 3600 s cache TTL for the lookup is the largest exposure; the digest and revision checks make a stale cache safe, but a retry-after-refresh path is needed for them to be useful rather than just an error.
6. A 404 or a missing `tla2tools.jar` in the releases list, and a missing `v1.8.0` entry, can be transient (about 1 to 3 s per build; draft toggle). A single retry after a short pause is justified; do not cache a "missing" result.
7. The analysis report's description of the order is wrong for `rolling` (tag first, asset second) and only half right for `v1.8.0` (asset first, tag 4.5 minutes later). Section 3.3 point 4 of `docs/analysis/01-merit-and-landscape.md` could be corrected; I did not edit it.

## Open follow-ups

- Observe a live build: poll `releases/tags/v1.8.0`, `git/ref/tags/v1.8.0` and `releases/tags/rolling` every second during the 00:27-00:33 style window of a CI run, and record 404s and mismatches. Needs a build to happen while polling (builds average one every 4 hours, 20 minute runtime).
- Test an in-flight download over a replaced asset on a throwaway repository owned by the maintainer (slow throttled download, replace the asset during it). I did not do it because it needs publishing on GitHub.
- Confirm that the draft toggle makes `/releases/download/v1.8.0/tla2tools.jar` 404 for about a second (reasoned only).
- Check whether the upstream project would consider ordering changes (tag before asset for both) or a concurrency group; this is outside this spike (no issue or discussion opened).
- Check whether `jar` `X-Git-Revision` is present in older builds (v1.7.4 and earlier, other tags) so the check can be skipped or relaxed for them. Only the current build was inspected.

## Date checked

2026-11-14 (the session clock and GitHub timestamps read 2026-11-15, 08:20Z; the workflow, run and API values above were read then). gh 2.100.0, openjdk 25.0.5.
