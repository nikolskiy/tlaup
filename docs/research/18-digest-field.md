# 18. The release asset `digest` field

## Question

Is the GitHub release asset `digest` field still present for `v1.8.0` and `rolling` of `tlaplus/tlaplus` and null for `v1.7.4`? Does it match the real bytes? Since when does GitHub provide it, is it backfilled, does it need a token, and is there any other published checksum for v1.7.4?

## Source

- `gh api repos/tlaplus/tlaplus/releases/tags/<tag>` (authenticated), plus one unauthenticated `curl` of the same endpoint.
- Downloads of each `tla2tools.jar` from the release URLs, hashed locally.
- GitHub changelog and public roadmap (URLs below). Trimmed API responses: `tests/fixtures/research/18-digest/` (one JSON per tag, `tla2tools.jar` asset only, plus `all-releases-tla2tools-digest.tsv`).

## Short answer

Yes. On 2026-11-15 UTC (the machine clock; 2026-11-14 local) the `tla2tools.jar` asset has `digest: "sha256:7e53aa63...fb84f"` for both `v1.8.0` and `rolling`, and `digest: null` for `v1.7.4`, `v1.7.3`, `v1.7.2`, `v1.7.1`, `v1.7.0`, `v1.6.0` and every older release (the field is null or the asset is absent in all 15 releases listed). Where present, the digest equals the SHA-256 of the downloaded bytes. GitHub added the field in June 2025 and computes it at upload time, so assets uploaded earlier have null; I found no backfill for this repository. The digest is returned without authentication. For v1.7.4 GitHub gives no SHA-256, but the release notes list a SHA-1 (`bee4a54f...`) that matches the downloaded jar. No Maven Central copy exists.

## Confidence

Verified for presence, null state, byte match, unauthenticated access, and the v1.7.4 release-notes checksum. Partly verified for "not backfilled": observed null on every old tlaplus release, but GitHub's pages I could read do not state a backfill policy (secondary source only, see Evidence).

## Evidence

Authenticated API, `tla2tools.jar` asset only:

| tag | digest | size | asset updated_at |
|---|---|---|---|
| v1.8.0 | sha256:7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f | 4510884 | 2026-11-15T00:27:39Z |
| rolling | sha256:7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f | 4510884 | 2026-11-15T00:32:15Z |
| v1.7.4 | null | 2274532 | 2024-08-08T13:30:40Z |
| v1.7.3 | null | 2274370 | 2024-08-02T17:12:32Z |
| v1.7.2 | null | 2274255 | 2022-02-02T22:16:29Z |
| v1.6.0 | null | 2115702 | 2019-07-11T16:29:32Z |

(v1.7.1, v1.7.0, v1.5.7 and v1.5.6 also null; v1.5.5 and older have no `tla2tools.jar` asset. See the TSV in the fixtures folder.) Every other v1.8.0 and v1.7.4 asset (Toolbox zips, deb, p2repository.zip) follows the same rule: v1.8.0 has digests, v1.7.4 has null.

Local SHA-256 of downloaded jars (`curl -L` then `sha256sum`):

- v1.8.0: `7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f`, equals the digest.
- rolling: identical bytes and hash to v1.8.0, equals the digest.
- v1.7.4: `936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88` (no digest to compare).
- v1.7.3: `ae7a33bbe99e5a3783c28d826d20e0028fc87f5a8cc8f9520afab00eabbc0bb1`
- v1.7.2: `fa18543e44ed5974a85bd2c60c0dc16620ae117680ea8e693d2691999ed90b22`
- v1.6.0: `71ce43150b6ee0a76cc33849ec45b2c6ae4323dc933b0acaef0928668ed0de72`

Observations on `rolling`: the release was published 2026-10-23, but the asset was replaced on 2026-11-15 00:32Z and its digest is that of the current bytes. A recorded digest for `rolling` goes stale whenever CI re-uploads. v1.8.0's assets were also all uploaded 2026-11-15 00:27 to 00:29Z, well after the tag (the release was published earlier; the jar was re-uploaded), so even a "release" asset can change. I did not check whether v1.8.0 is marked immutable.

Unauthenticated: `curl -H 'Accept: application/vnd.github+json' https://api.github.com/repos/tlaplus/tlaplus/releases/tags/rolling` (no token, rate limit header `x-ratelimit-limit: 60`) returned `"digest": "sha256:7e53aa63...fb84f"` for `tla2tools.jar`, and `null` for v1.7.4 assets. Checked once each.

When the field appeared: GitHub changelog, 2025-06-03, "Releases now expose digests for release assets": digests are SHA-256, "generated at upload time, immutable", shown in the UI, REST API, GraphQL API and `gh` CLI. https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/ . Roadmap item (opened 2025-05-29, shipped 2025-06-04): https://github.com/github/roadmap/issues/1136 . Neither page says anything about old assets. A web search summary of community threads (not read in full by me) says old releases return null and one thread dates collection from April 2025: https://github.com/orgs/community/discussions/23512 and https://github.com/jdx/mise/discussions/5464 . Treat that as secondary.

Other checksums for v1.7.4:

- The v1.7.4 release notes (`gh api repos/tlaplus/tlaplus/releases/tags/v1.7.4 --jq .body`) have a "Checksums" table of SHA-1 for three Toolbox zips and `tla2tools.jar`: `bee4a54f3ee3d4afc347c3240ec2d9e93b075104`. `sha1sum` of the downloaded jar gives the same value. This is published by the same account that hosts the asset, so it is no more independent than the asset itself, and SHA-1 is weak.
- No `.sha256`, `.sha1`, `.md5` or checksum asset exists in any release (listed all asset names of all releases).
- Maven Central: `https://repo1.maven.org/maven2/org/lamport/` returns 404, `.../org/lamport/tla2tools/1.7.4/tla2tools-1.7.4.jar` returns 404, and the Maven search API finds no artifact `tla2tools` or `tlaplus`. So org.lamport:tla2tools does not exist on Maven Central; there is nothing to compare.

## Implications for the roadmap

- Milestone 3's statement is confirmed as of today: present for v1.8.0 and rolling, null for older releases, no token needed.
- A digest can only be trusted for builds uploaded after about June 2025. For v1.7.4 and older, tlaup can offer only trust on first use (record the SHA-256 of the downloaded bytes) or a pinned table of known SHA-256 values shipped in tlaup. The hashes above for v1.7.4, v1.7.3, v1.7.2, v1.6.0 could seed such a table; they come from one download over HTTPS, not from an independent source.
- The v1.7.4 SHA-1 in the release notes is a second, weak cross-check that could be used once, to confirm a pinned SHA-256 for v1.7.4. It is not available for other versions.
- Because the digest comes from the same GitHub account as the file, it detects corruption and a download from a mismatched mirror, but not a compromised release. Say so in the documentation.
- `rolling` and re-uploaded releases change: compare the digest fetched at install time with the one recorded, and treat a change as an update, not an error (design decision for milestone 3).

## Open follow-ups

- Whether v1.8.0 is an immutable release (`"immutable"` field in the API) was not checked; it affects whether the digest can change after publishing.
- Why v1.8.0's assets show `updated_at` 2026-11-15, after the release was published (CI re-upload?), was not investigated.
- GitHub's own statement on backfilling old assets was not found; only observation on this repository.
- Digests for non-jar assets were seen in the API but only the jar bytes were hashed.

## Date checked

2026-11-14 (local), 2026-11-15 UTC on the machine clock.
