# 05. Does upstream attach, or plan to attach, a jar to each CalVer tag?

## Question

Does github.com/tlaplus/tlaplus attach a `tla2tools.jar` to each CalVer tag (immutable tags `YYYY.MM.DD.HHmmss`, started 2026-04-27), or plan to? Is there any other place where old builds are kept (nightly.tlapl.us, Maven, Actions artifacts), and with what retention?

## Source

- `gh` (release, tag, search, api calls) and `curl` against tlaplus/tlaplus, nightly.tlapl.us and central.sonatype.com, 2026-11-14/15.
- `.github/workflows/main.yml` and `pr.yml` on master, README.md, `tlatools/org.lamport.tlatools/ossrh.xml.README`.
- Issues #1165, #1380, #1277, PRs #1328, #1383.
- Google Group thread "Historical tla2tools.jar rolling builds" (Jan 2024): https://groups.google.com/g/tlaplus/c/ohE2v4BEs8M/m/0pixmATGBQAJ

## Short answer

No, and nothing upstream says they plan to. CalVer tags are plain annotated git tags with no GitHub release and no assets. The only jars on GitHub are in two releases whose single `tla2tools.jar` is overwritten on every master build (`rolling`, and `v1.8.0`). A maintainer (ahelwer, 2026-05-26) said explicitly that GitHub releases are not a package store and told a user who wanted a pinnable jar to build from a commit. No other upstream location keeps old master builds: nightly.tlapl.us holds only the latest jar (plus one stray 2023 build), and Maven snapshots expose only the latest timestamped build and, per Sonatype, are removed after 90 days. Building from source at the CalVer tag is therefore the only upstream-supported way to get an older build.

## Confidence

Verified for: no releases or assets on CalVer tags, the workflow behaviour, the maintainer statements, nightly.tlapl.us listing, current Maven snapshot state.
Partly verified for: "plans": absence of any issue or PR proposing it was checked with GitHub search (keyword search, not exhaustive). Maven snapshot retention (90 days) comes from Sonatype's docs for snapshots in general; I did not observe an old snapshot being deleted, and could not list the repo's history. The retention on the Actions artifacts of `main.yml` was not readable (see below).

## Evidence

### CalVer tags have no releases or assets

- `gh api repos/tlaplus/tlaplus/tags --paginate`: 84 tags start with `20` (newest `2026.11.15.002146`, oldest `2026.04.27.203507`), plus `rolling`, `v1.8.0`, older `v1.x`.
- `gh api repos/tlaplus/tlaplus/releases --paginate -q '.[].tag_name' | grep -c '^20'` printed `0`. `gh release list` shows only `rolling` (pre-release), `v1.8.0` (pre-release) and the older `v1.x` releases (latest stable: v1.7.4, 2024-08-05).
- `gh release view v1.8.0` assets: `tla2tools.jar` (4,510,884 bytes), Toolbox zips and deb, `p2repository.zip`. `gh release view rolling` assets: `tla2tools.jar` (4,510,884 bytes, updated 2026-11-15T00:32:15Z). Same size and same-day timestamps: both hold the latest build only.

### Workflow that creates the tags (`.github/workflows/main.yml`, runs on push to master)

- Step "Update tags": `git tag -f v1.8.0`, `git tag -f rolling`, computes `CALVER` by running `java -cp dist/tla2tools.jar tlc2.REPL 'TLCGet("revision").calver'`, then `git tag -a "$CALVER" -m "TLA+ Tools $CALVER"` and `git push ... --follow-tags --tags --force`. Nothing is attached to the CalVer tag.
- Step "Upload release assets": finds the release named "The Clarke release" (`v1.8.0`), deletes the existing `tla2tools.jar` asset and uploads the new one (same for the Toolbox files).
- Step "Update rolling release": `gh release upload rolling --clobber .../dist/tla2tools.jar`. The comment says the rolling tag gives "a stable download URL for the most recent build".
- Step "Upload to Maven Central" (continue-on-error): strips `javax/*`, `com/*`, mail files from the jar and deploys to `https://central.sonatype.com/repository/maven-snapshots/` (version `1.8.0-SNAPSHOT`).
- The same `rsync` step pushes `dist/tla2tools.jar` with `--delete` to `github@upload.tlapl.us:dist/` (what nightly.tlapl.us serves).
- `main.yml` uploads only unit-test results (`testresults-<os>`) as Actions artifacts, not the jar.

### Issues and pull requests

- PR #1383 (merged 2026-04-27), "Add TLCGet("revision").calver and use it to tag every master build": "Add an immutable per-commit tag ... so each rolling pre-release is reachable by a fixed git ref. This is a step toward the predictable release cadence in Github issue #1165." The goal is a git ref, not a jar.
- PR #1328 (merged 2026-02-24): TLC version becomes CalVer, derived from the jar manifest build timestamp.
- Issue #1165 "Bring back regular releases and maintenance branches" (open, lemmy, 2025-04-01), the umbrella for the CalVer work. Comment 2026-11-06 by `hemp` (not a maintainer): "what if `main.yml` had an extra step to also push a CalVer release jar?" The only reply (lemmy, member, 2026-11-06) is a link to `https://github.com/tlaplus/tlaplus/releases#release-rolling`, with no agreement. No other comment on this.
- Issue #1380 "release checksum changed for 1.8.0 tla2tools.jar" (closed, 2026-04-25). The reporter (a Bazel user) suggested a release named HEAD/main and "upload to a blob store as well as github, permitting older versions to be resolved". lemmy replied only with a link to #1165. ahelwer (2026-05-26): "GitHub releases are not a package management system and are intentionally malleable in what artifacts they contain. The reason ... is that you eventually run out of storage when you frequently upload binaries." and "Instead consider cloning the repository at a particular commit then building it yourself." This is the closest thing to a position on jar per tag, and it is a no.
- Issue #1277 (closed): maintainers explain 1.8.0 is the rolling release whose jar is replaced.
- Keyword searches for archive, retention, old builds, older build, nightly archive, pin version, jar per release found no other open or closed issue or PR proposing a per-tag jar or an archive (queries run with `gh search issues/prs --repo tlaplus/tlaplus`). GitHub Discussions are empty (`discussions.totalCount` = 0 via GraphQL).

### The 2024 request

Google Group thread "Historical tla2tools.jar rolling builds", January 2024 (fetched via WebFetch, summary of messages):
- Andrew Helwer, 2024-01-06: asked whether historical builds exist, "perhaps organized by commit hash", and (2024-01-06 23:23) whether the per-commit builds uploaded to the 1.8.0 rolling pre-release are "archived anywhere or just overwritten".
- Markus Kuppe, 2024-01-07: they do not currently archive them; open a GitHub issue if archiving is needed; use `git bisect` for regressions. Earlier he said he had shared private builds of older versions.
- Helwer, 2024-01-07: wants reproducible builds (Nix, Guix) and says keeping all rolling builds may matter but needs research.
- No GitHub issue for this was found (searches above); I did not check later posts in the thread or other threads beyond the two links the search returned.

### Other places old builds are kept

- nightly.tlapl.us: `https://nightly.tlapl.us/dist/` lists `tla2tools.jar` (4.3M, modified 2026-11-15 01:22), `tla2tools-1a92ec7.jar` (3.3M, 2023-09-25) and a `1a92ec7/` folder. The workflow's `rsync --delete` means only the latest is kept; the 2023 files are leftovers from before. No per-commit or per-CalVer archive.
- Maven snapshots (`https://central.sonatype.com/repository/maven-snapshots/org/lamport/tla2tools/`): the `maven-metadata.xml` lists only `1.8.0-SNAPSHOT`; its metadata shows the latest timestamped build `1.8.0-20261115.003216-126` (buildNumber 126, which is the jar, stripped of bundled dependencies per the workflow). The jar for that build returned HTTP 200; a made-up older build name returned 404. Build number 126 for a snapshot that has been published since 2026 suggests older timestamped builds are cleaned (not confirmed). Sonatype's docs for snapshots say they are cleaned up after a period, currently 90 days (https://central.sonatype.org/publish/publish-portal-snapshots/, text matched by grep, not read in full). The upstream `ossrh.xml.README` says "so far we have only pushed snapshots". `https://repo1.maven.org/maven2/org/lamport/tla2tools/` returned 404: no release versions on Maven Central under that name.
- GitHub Actions artifacts: `pr.yml` uploads an artifact named `tla2tools` for pull-request runs (12 listed under that name among the 100 most recent artifacts, e.g. created 2026-11-14T23:23:14Z, `expires_at` 2027-02-12T23:14:15Z, i.e. about 90 days). These are from PR branches, not master builds. `main.yml` uploads only `testresults-*` (expire after about 90 days: 2026-11-06 created, 2027-02-04 expires). Repo-level retention setting returned HTTP 403 for my account; the observed `expires_at` values are the evidence.

## Implications for the roadmap

- D12 stands as written: building from source at the CalVer tag is the only upstream-supported route to an older rolling build. There is no sign the jar-per-tag logic will become removable soon.
- Building at a tag gives the full fat jar with bundled dependencies (like the rolling jar), unlike the Maven snapshot jar, which is stripped. This confirms dropping Maven snapshots. A rebuilt jar will not be byte-identical to the original (the manifest Build-TimeStamp, and thus the CalVer string, comes from build time); this was not tested here. The CalVer tag points at the commit, so rebuilt jars will report a different CalVer than the tag unless the build time can be fixed (open question, see below).
- The maintainer stance in #1380 means a request to attach a jar to each tag may be turned down; the same stance points to "build from commit" as upstream's own advice.
- Note for the Milestone 3 wording: `v1.8.0` is also a moving pre-release (jar replaced each build), so it cannot serve as a pin either.

## Open follow-ups

- Maintainer decision: whether to ask upstream (probably as a comment on #1165, which is open and which the maintainers use for this topic) to attach the jar to each CalVer tag or keep a per-tag archive. Evidence suggests a cost objection (release storage); a possible smaller ask is a retained store such as nightly.tlapl.us keeping dated copies. Not done by me.
- Check whether a source rebuild at a CalVer tag works and what the resulting jar reports (CalVer string, manifest timestamp) by building one old tag; this belongs to the work for Milestone 3, not to this question.
- Confirm Maven snapshot retention by finding when an older timestamped build disappears (could be checked by fetching a recorded build URL again after some days).
- Read the rest of the Google Group thread and later threads for decisions after January 2024.

## Date checked

2026-11-14 (server responses dated 2026-11-15 UTC).
