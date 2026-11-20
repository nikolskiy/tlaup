# 26: Do the jars of releases older than v1.7.4 carry a commit?

## Question

Do the `tla2tools.jar` assets of releases older than v1.7.4 carry `X-Git-Revision` (and the other `X-Git-*` entries, `Build-TimeStamp`) in `META-INF/MANIFEST.MF`? Which is the first release that has `X-Git-Revision`? Where tag and manifest both name a commit, do they agree? Decides how a build with no commit is named and printed ([design 12 V1](../design/12-tools-and-downloads.md#v1-version-store), [02 X3](../design/02-cross-cutting.md#x3-version-syntax)).

## Source

- Releases listed with `gh api --paginate repos/tlaplus/tlaplus/releases` (17 releases, checked 2026-11-19 UTC).
- Jars downloaded with `gh release download <tag> -R tlaplus/tlaplus -p tla2tools.jar`, one empty folder per tag (v1.5.6, v1.5.7, v1.6.0, v1.7.0, v1.7.1, v1.7.2, v1.7.3); v1.7.4 and v1.8.0 are the jars of research 14.
- Tag commits from `gh api repos/tlaplus/tlaplus/git/ref/tags/<tag>`, peeling annotated tags with `git/tags/<sha>`.
- Data in `tests/fixtures/research/26-old-jar-commits/`: `table.tsv` (every value below), `<tag>.MANIFEST.MF` (raw, CRLF kept; `rolling.MANIFEST.MF` is research 14's, byte-identical jar to v1.8.0), `tag-commits.txt`, `read_manifests.py` (the reader, handles continuation lines).
- Reading was done with Python `zipfile`, run as `python -I`. No Java was started.

## Short answer

Yes, every one of them. All seven older jars, and so every release that has a `tla2tools.jar` asset, carry `X-Git-Revision` (40 hex), `X-Git-ShortRevision`, `X-Git-Branch`, `X-Git-Tag`, `X-Git-BuildNumber` and `X-Git-Commits-Count`. The first release that has the entry is also the oldest release with a `tla2tools.jar`: **v1.5.6**. Older releases (v1.5.5 and earlier, back to v1.4.8) have no `tla2tools.jar` asset at all (only `tla.zip`, an unpacked class tree whose manifest is a bundled JavaMail one, and Toolbox zips), so tlaup never sees them.

None has `Build-TimeStamp`; only v1.8.0/rolling has. So no published jar is without a commit, but every jar older than v1.8.0 has a commit and no build time.

The tag's commit matches the manifest's revision in 8 of the 9 releases that have both. The exception is **v1.7.1**: the tag points at `be99a7d` (master, 2020-12-30) but the jar was built from `cdddf55` (the v1.7.1 release branch, 2020-12-31, 42 commits ahead of and 202 behind the tag's commit). The jar's revision is the better statement of what was built.

## Confidence

Verified: manifests of all nine jars read directly; release list complete (two pages not needed, 17 releases in one go; `--paginate` used). Tag comparison verified for all nine. Not checked: which upstream commit introduced `X-Git-*` (not needed: the oldest asset already has it); `X-Git-*` values of jars that were once attached and since replaced (an asset can be re-uploaded: v1.5.6's asset was created 2018-07-06, five months after the release's publish date; the file read here is what upstream serves now).

## Evidence

Release list (releases with a `tla2tools.jar` asset, newest first; `published` is the release's date, `asset` is the asset's `created_at`; size in bytes; GitHub's `digest` is null for every one older than rolling):

| Tag | Published | Asset created | Size | sha256 (computed) |
| --- | --- | --- | --- | --- |
| rolling | 2026-10-23 | 2026-11-15 00:32 | 4510884 | 7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f |
| v1.8.0 | 2026-11-15 | 2026-11-15 00:27 | 4510884 | 7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f |
| v1.7.4 | 2024-08-05 | 2024-08-08 | 2274532 | 936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88 |
| v1.7.3 | 2024-08-05 | 2024-08-02 | 2274370 | ae7a33bbe99e5a3783c28d826d20e0028fc87f5a8cc8f9520afab00eabbc0bb1 |
| v1.7.2 | 2022-02-02 | 2022-02-02 | 2274255 | fa18543e44ed5974a85bd2c60c0dc16620ae117680ea8e693d2691999ed90b22 |
| v1.7.1 | 2022-02-23 | 2022-02-23 | 2274805 | d532ba31aafe17afba1130f92410d9257454ff7393d1eb2fe032f0c07f352da5 |
| v1.7.0 | 2020-04-01 | 2020-04-25 | 2272471 | 8cce75caa1e59d0b0483bb8fb881ba33825edce8b2d98aba59d66ce685dd3d1a |
| v1.6.0 | 2019-07-11 | 2019-07-11 | 2115702 | 71ce43150b6ee0a76cc33849ec45b2c6ae4323dc933b0acaef0928668ed0de72 |
| v1.5.7 | 2018-07-18 | 2018-07-18 | 2453334 | 1626add371f8e198ea23f86d16d0c72166978456baaa61f1afec901283b92595 |
| v1.5.6 | 2018-01-30 | 2018-07-06 | 2401057 | a5400b857b1e4d9e17bf0a3e1c4b57fa3e98c657e3791bfba93f7013bc5574c1 |

Release dates are not in version order (v1.7.1 was published 2022-02-23, after v1.7.2; v1.7.3 and v1.7.4 the same day, with assets dated 2024-08-02 and 2024-08-08) and are not the build dates. v1.5.5, v1.5.4, v1.5.3, v1.5.2, v1.5.1, v1.5.0 and v1.4.8 have no `tla2tools.jar` asset (`tla.zip` and Toolbox zips only).

Manifest entries (`-` means the entry is absent; "empty" means present with no value). `Build-TimeStamp` is absent in all but v1.8.0/rolling.

| Tag | X-Git-Revision | X-Git-Branch | X-Git-Tag | X-Git-BuildNumber | Commits-Count | Implementation-Version | Built with |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v1.5.6 | 2cf41975209078368ae974e1af519c1aeb1cf4be | empty | `jenkins-os=master-87` | `_jenkins-os=master-87_2cf4197` | 5985 | 2.0 2018-01-29 | JDK 1.8.0_161, Ant 1.9.4 (Jenkins) |
| v1.5.7 | bfdbe00e3d0638b46a29ca408c91c0e17d832661 | empty | `jenkins-os=master-96` | `_jenkins-os=master-96_bfdbe00` | 6225 | 2.0 2018-07-18 | JDK 1.8.0_171, Ant 1.9.4 (Jenkins) |
| v1.6.0 | 0cae24f399ef687032220bceb9926806ad14de3b | master | empty | `master__0cae24f` | 6977 | 2.0 2019-07-10 | AdoptOpenJDK 11.0.2+9, Ant 1.9.4 |
| v1.7.0 | eb3ff99d167cc3216b4e9f6f822c112aba9597c5 | master | empty | `master__eb3ff99` | 7366 | 2.0 2020-04-25 | Azul 11.0.3+7, Ant 1.9.4 |
| v1.7.1 | cdddf55c262536c01adac3f15ecd5b71b9d1ec72 | v1.7.1 | empty | `v1.7.1__cdddf55` | 7408 | 2.0 2020-12-31 | Azul 11.0.3+7, Ant 1.9.4 |
| v1.7.2 | 3c7caa56d1186bfa8e1640b42000894d93e26c52 | v1.7.2 | empty | `v1.7.2__3c7caa5` | 7411 | 2.0 2022-02-02 | Azul 11.0.3+7, Ant 1.10.7 |
| v1.7.3 | 3ea322254974cd39a4dd336fff12b203a6743dd1 | v1.7.3 | `v1.7.3` | `v1.7.3_v1.7.3_3ea3222` | 7414 | 2.0 2024-08-02 | Azul 11.0.3+7, Ant 1.10.12 |
| v1.7.4 | 5a47802b5c391f59ecdd44117981f4ff8c0656ba | v1.7.4 | `v1.7.4` | `v1.7.4_v1.7.4_5a47802` | 7425 | 2.0 2024-08-08 | Azul 11.0.3+7, Ant 1.9.4 |
| v1.8.0 | bc1b506bdcad80bb518bf3776a9161c34ff0fc4c | master | empty | `master__bc1b506` | 9089 | 2.0 2026-11-15 | Adoptium 17.0.21+9, Ant 1.10.12 |

`X-Git-ShortRevision` is the first seven digits of the revision in every jar. `Build-Tag` is unexpanded or a Jenkins job name and `Build-Rev` is the unexpanded `${Build-Rev}` in all of them; as research 14 found, neither is usable. `X-Git-Tag` is not the release tag in six of nine jars (empty, or a Jenkins job name), so it is not usable either. Only the `Build-Tag` value of v1.5.6 and v1.5.7 wraps (a continuation line of one character at line 6, which `read_manifests.py` joins): the one real-jar case of a wrapped line, and not in an attribute tlaup reads. None of the `X-Git-*` values wraps.

Tag against manifest (tag ref peeled to its commit):

| Tag | Tag's commit | Equals manifest revision? |
| --- | --- | --- |
| v1.5.6 | 2cf4197 (2018-01-29) | yes (annotated tag) |
| v1.5.7 | bfdbe00 (2018-07-18) | yes (annotated tag) |
| v1.6.0 | 0cae24f (2019-07-10) | yes (annotated tag) |
| v1.7.0 | eb3ff99 (2020-04-25) | yes |
| v1.7.1 | be99a7d2fcf43a3c771f4678483ffa328ab37db0 (2020-12-30) | **no**: jar says cdddf55 (2020-12-31) |
| v1.7.2 | 3c7caa5 (2022-02-02) | yes (annotated tag) |
| v1.7.3 | 3ea3222 (2023-03-20) | yes |
| v1.7.4 | 5a47802 (2024-08-08) | yes |
| v1.8.0 | bc1b506 (2026-11-15) | yes |

v1.7.1 detail: `gh api repos/tlaplus/tlaplus/compare/be99a7d...cdddf55` gives status "diverged" (42 ahead, 202 behind); the jar's commit is "Add instructions how to get rid of outdated/legacy PlusCal divergence" on the `v1.7.1` branch, whose own message list includes "Build 1.7.1 release from v1.7.1 branch". The release's `target_commitish` is `master`, the tag is on master. A lookup that mistakes the name for a branch gets a third commit: `gh api repos/tlaplus/tlaplus/commits/v1.7.1` returns `3c037dd` (2023-03-20), the head of branch `v1.7.1`, because branches `v1.7.1` to `v1.7.4` exist beside the tags of the same names. Use `git/ref/tags/<tag>` (or `refs/tags/`), never the bare name.

## Implications for the roadmap

- A published jar with no commit does not exist today: all nine downloadable jars carry `X-Git-Revision`. The "no commit" form of a build name ([02 X3](../design/02-cross-cutting.md#x3-version-syntax) printing table, [12 V1](../design/12-tools-and-downloads.md#v1-version-store) `commit` null) is then reached only by a jar that is not from upstream's release list (a hand-built or foreign jar, or a future release with a broken build). It stays a required, tested path, but never appears for a release in the list. The "no commit and no build time" row (bare `name`) is likewise unreachable from releases.
- What is common is the other row of the printing table: every release before v1.8.0 has a commit and no build time, so each is printed `name@commit`, never `name@calver`. Only v1.8.0 and rolling builds have a build time.
- The post-download check of research 7 and 14 (jar's `X-Git-Revision` against the tag's commit) cannot be applied unchanged to old tags: v1.7.1 fails it though its jar is genuine, and its tag-side commit lookup must peel annotated tags (v1.5.6, v1.5.7, v1.6.0, v1.7.2 are annotated). It is safe for v1.7.4 and v1.8.0. Whether the design reads tags at all is its own decision ([12 V8](../design/12-tools-and-downloads.md#v8-remote-listing-and-its-cache) takes no commit from a tag); if a check against a tag commit is ever added, it has to be a warning, or skipped for releases older than v1.7.4.
- The jar's commit is what identifies the build, so `v1.7.1@cdddf55` is the right name for that jar, not `v1.7.1@be99a7d`. Test fixtures can use all nine recorded manifests (small jars built from them) instead of three.
- `Implementation-Version`'s date is the build day, and for v1.7.3 it (2024-08-02) differs from the release date; the design already ignores it.
- GitHub's `digest` is null for all releases older than rolling, v1.8.0 (research 18): tlaup computes SHA-256 for them, as the design says.

## Open follow-ups

- Asset replacement: v1.5.6's asset was uploaded five months after its release; assets could be replaced again, which would change a jar's SHA-256 under the same tag. Not observable from one snapshot.
- The `X-Git-Revision` check was not run on `tla.zip` or Toolbox archives; not needed, since tlaup downloads only `tla2tools.jar`.
- Whether any jar had a commit that does not exist upstream: all nine commits were found by `gh api commits/<sha>` (the seven older ones, checked directly), so none is orphaned today.

## Date checked

2026-11-19 UTC (the date of the data above). Linux x86-64, Python 3 with `-I`; no JVM used.
