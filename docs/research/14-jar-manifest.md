# 14: What a jar says about itself, readable without a JVM

## Question

Can the commit and CalVer a tla2tools.jar reports about itself be read without starting a JVM (manifest entry or a file in the jar)? What does v1.7.4 report? For v1.7.4, v1.8.0 and the rolling jar: which manifest attributes hold commit, build date, version, CalVer; do they agree with what the jar prints when run; where upstream gets them and since when; can Python's zipfile read them; are `rolling` and `v1.8.0` the same bytes.

## Source

- Jars downloaded with `gh release download <tag> -R tlaplus/tlaplus -p tla2tools.jar` (tags v1.7.4, v1.8.0, rolling).
- Upstream: `tlatools/org.lamport.tlatools/customBuild.xml` and `.../src/tlc2/TLCGlobals.java` in https://github.com/tlaplus/tlaplus (master at bc1b506bdcad80bb518bf3776a9161c34ff0fc4c; also customBuild.xml at tag v1.7.4).
- Manifests saved in `tests/fixtures/research/14-jar-manifest/` (`v1.7.4.MANIFEST.MF`, `v1.8.0.MANIFEST.MF`, `rolling.MANIFEST.MF`; CRLF line endings kept).

## Short answer

Yes. All three jars carry a `META-INF/MANIFEST.MF` with the full git commit in `X-Git-Revision` (40 hex) and the short one in `X-Git-ShortRevision`; Python's `zipfile` reads it. There is no version/build properties file to read instead (the only `.properties` file is `tlc2/output/messages.properties`, message text).

- The commit the jar reports when run, `(rev: <short>)`, is the manifest `X-Git-ShortRevision`, so the two agree by construction (upstream source below, and observed).
- CalVer is not stored. TLC computes it at run time from `Build-TimeStamp` formatted `yyyy.MM.dd.HHmmss` in UTC. The same value can be derived in Python from the manifest: v1.8.0/rolling `Build-TimeStamp: 2026-11-15T00:21:46.50Z` gives `2026.11.15.002146`, which is exactly what the jar prints.
- v1.7.4 predates CalVer. It reports `X-Git-Revision: 5a47802b5c391f59ecdd44117981f4ff8c0656ba`, `X-Git-Tag: v1.7.4`, `Implementation-Version: 2.0 2024-08-08` and prints `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`. It has no `Build-TimeStamp`; the "2.19 of 08 August 2024" string is not in the manifest (its date matches the date part of `Implementation-Version`, and 2.19 is not in the manifest at all).
- Right now `rolling` and `v1.8.0` are byte-identical (same SHA-256), and the jar says it was built from branch `master`, with an empty `X-Git-Tag`. The tag v1.8.0 does point at that same commit, so tag commit and jar commit agree today.

## Confidence

Verified for the manifest contents, the run-time output, the Python read, the upstream source and the SHA-256 comparison. Partly verified for "since when" (see Evidence 6): the commit that added `Build-TimeStamp` was found by a search of the build file history, not by reading every commit.

## Evidence

### 1. Manifest attributes (exact names and values)

`unzip -p tla2tools.jar META-INF/MANIFEST.MF`:

| Attribute | v1.7.4 | v1.8.0 and rolling (identical) |
|---|---|---|
| `Implementation-Title` | `TLA+ Tools` | `TLA+ Tools` |
| `Implementation-Version` | `2.0 2024-08-08` | `2.0 2026-11-15` |
| `Build-TimeStamp` | absent | `2026-11-15T00:21:46.50Z` |
| `X-Git-Revision` | `5a47802b5c391f59ecdd44117981f4ff8c0656ba` | `bc1b506bdcad80bb518bf3776a9161c34ff0fc4c` |
| `X-Git-ShortRevision` | `5a47802` | `bc1b506` |
| `X-Git-Branch` | `v1.7.4` | `master` |
| `X-Git-Tag` | `v1.7.4` | empty |
| `X-Git-BuildNumber` | `v1.7.4_v1.7.4_5a47802` | `master__bc1b506` |
| `X-Git-Commits-Count` | `7425` | `9089` |
| `Build-Tag`, `Build-Rev` | unexpanded `${env.BUILD_TAG}`, `${Build-Rev}` (useless) | same |
| `Ant-Version`, `Created-By` | Ant 1.9.4, JDK 11.0.3+7 Azul | Ant 1.10.12, JDK 17.0.21+9 Adoptium |
| `Class-Path` | `CommunityModules.jar` | `CommunityModules-deps.jar CommunityModules.jar` |

Notes: `Implementation-Version` is `${version} ${TODAY}` where `version` is a fixed "2.0" and `TODAY` is the build date (local build date, `yyyy-MM-dd`), so it is neither the TLC version nor the CalVer. The manifest has no field called CalVer or version number. The 8 lines of git data come from the jgit-buildnumber Ant task.

### 2. Properties files

`unzip -l | grep -i -E 'version|build|properties|git'` shows only class files with those words in their names (gson, jline, `tlc2/TLCGlobals$Version.class` in v1.8.0) and `tlc2/output/messages.properties` (1214 bytes in v1.7.4, 1352 in v1.8.0/rolling). No version or git-info file.

### 3. What the jar prints (Java 25, `/usr/bin/java`)

`java -cp tla2tools.jar tlc2.TLC -version` is not an option in any of the three ("unrecognized option: -version"), but the first line printed before the error is the banner:

```
v1.7.4:  TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
v1.8.0:  TLC2 Version 2026.11.15.002146 (rev: bc1b506)
rolling: TLC2 Version 2026.11.15.002146 (rev: bc1b506)
```

Agreement: the `rev:` value equals `X-Git-ShortRevision` in all three. For v1.8.0/rolling, `2026.11.15.002146` equals `Build-TimeStamp` `2026-11-15T00:21:46.50Z` reformatted. For v1.7.4 the banner text is old-style, hard-coded in that release's source, not from the manifest.

### 4. Python can read it

```
uv run python -I -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); m=z.read('META-INF/MANIFEST.MF').decode(); ..." <jar>
```

printed, for v1.7.4: `X-Git-Revision 5a47802b5c391f59ecdd44117981f4ff8c0656ba, X-Git-Tag v1.7.4, X-Git-ShortRevision 5a47802, Build-TimeStamp None`; for v1.8.0 and rolling: `X-Git-Revision bc1b506bdcad80bb518bf3776a9161c34ff0fc4c, X-Git-Tag '', Build-TimeStamp 2026-11-15T00:21:46.50Z`. Line endings are CRLF. Manifest lines wrap at 72 bytes in general; none of the values above wrapped, but a parser should handle continuation lines (a line starting with a space). I split on `: ` without handling continuation in this check.

### 5. Upstream source

- Manifest is written by the `jar` task in `customBuild.xml` (the attribute list above; `Build-TimeStamp` value is `${ISO8601}`, from `<tstamp><format property="ISO8601" pattern="yyyy-MM-dd'T'HH:mm:ss.S'Z'" timezone="UTC"/>`). https://github.com/tlaplus/tlaplus/blob/master/tlatools/org.lamport.tlatools/customBuild.xml
- `tlc2/TLCGlobals.java` nested class `Version`: `number()` formats `Build-TimeStamp` as `yyyy.MM.dd.HHmmss` in UTC (falls back to `new Date()` if absent); `revision()` returns manifest `X-Git-ShortRevision`; `scmCommits()` reads `X-Git-Commits-Count`. The manifest is found by scanning classpath `META-INF/MANIFEST.MF` entries for `Implementation-Title` = `TLA+ Tools`. The source comment says the rolling release switched to CalVer so that it cannot collide with the 2.x maintenance numbers. https://github.com/tlaplus/tlaplus/blob/master/tlatools/org.lamport.tlatools/src/tlc2/TLCGlobals.java
- Consequence: a development build with no manifest prints the current time as its version and "development" as rev.

### 6. Since when

- `X-Git-*` attributes: already in customBuild.xml at tag v1.7.4 (lines 236-241), and jgit-buildnumber is in the build; seen in the v1.7.4 jar.
- `Build-TimeStamp`: added by upstream commit 041598b, 2021-07-20, "Add tag, count, timestamp, and date to TLCGet("revision")..." (found via the history of customBuild.xml). It is on master but not in the v1.7.4 jar, so not on the maintenance branch.
- CalVer from the timestamp: commit 5a565e0, 2026-02-25, "Switch TLC's version number to CalVer (YYYY.MM.DD.HHmmss)". Refactored by 28dd32e, 2026-02-27, to defer manifest reading. I did not check which release tags first contain these.

### 7. rolling vs v1.8.0

`gh release view` and `sha256sum` on the downloaded files:

```
7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f  v1.8.0/tla2tools.jar  (4510884 bytes)
7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f  rolling/tla2tools.jar (4510884 bytes)
936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88  v1.7.4/tla2tools.jar  (2274532 bytes)
```

GitHub's asset digest for both rolling and v1.8.0 also reads `sha256:7e53aa63...`; v1.7.4's asset has `digest: null` (older upload). Release dates seen: v1.7.4 published 2024-08-05, asset updated 2024-08-08; rolling published 2026-10-23, asset updated 2026-11-15T00:32:15Z; v1.8.0 published 2026-11-15T00:29:14Z (about 3 minutes after its jar was uploaded), asset updated 2026-11-15T00:27:39Z. The v1.8.0 release is hours old and the rolling asset was re-uploaded after it. This equality is only a snapshot: rolling moves with each master build, so the two will differ after the next one.
Tag refs: `v1.8.0` -> bc1b506bdcad80bb518bf3776a9161c34ff0fc4c, `v1.7.4` -> 5a47802b5c391f59ecdd44117981f4ff8c0656ba (both lightweight pointing at commits; checked with `gh api repos/tlaplus/tlaplus/git/ref/tags/...`). master head at the time of the check: bc1b506.

## Implications for the roadmap

- Milestone 1 downloads: after download, open the jar with `zipfile`, read `X-Git-Revision` and compare with the commit the tag resolves to (40-hex full match, not the short form). It works for all three jars checked, including v1.7.4. No JVM needed.
- For a rolling jar the expected commit cannot come from the tag alone: the rolling tag/release moves, so compare against master/tag at the time of download, and expect races (tag and asset are updated at different moments, 2026-11-15 00:27 to 00:32 UTC above).
- Do not rely on `X-Git-Tag`: it is empty for jars built from master, even for v1.8.0. Do not use `Implementation-Version` (build day, "2.0") or `Build-Tag`/`Build-Rev` (unexpanded placeholders).
- Milestone 1 Java ("read the TLC version from saved metadata"): the CalVer is derivable from `Build-TimeStamp` (UTC, `%Y.%m.%d.%H%M%S`) for jars that have it. For older jars (v1.7.4, no `Build-TimeStamp`) the displayed version "2.19 of 08 August 2024" is not in the manifest; if it is needed, a small table keyed by commit, or running Java once, is required.
- Milestone 3 project file: tag, full commit (from `X-Git-Revision`), CalVer (derived) and SHA-256 can all be recorded; the digest still has to be computed (or taken from the GitHub asset digest where not null).
- `tlc2.TLC -version` does not exist; a version check by running Java would need parsing the banner line.

## Open follow-ups

- Which release tags between v1.7.4 and v1.8.0 (if any) carry `Build-TimeStamp`, and so can give CalVer without a JVM; only these three jars were opened.
- Whether the "2.19 of 08 August 2024" banner can be recovered without a JVM for old jars (probably only via a lookup table).
- Manifest continuation lines (72-byte wrapping) were not exercised by these three jars; a parser should be tested with a long attribute.
- Whether the rolling and tag updates ever leave the jar behind or ahead of the tag for longer than minutes (needs observation over several upstream builds).

## Date checked

2026-11-14 (local date; the GitHub timestamps above are UTC and fall on 2026-11-15). Java 25 at /usr/bin/java.
