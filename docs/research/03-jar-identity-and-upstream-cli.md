# 03: Jar identity, upstream's `tla` command, and which tags move

## Question

Three parts.

(a) How to tell which jar build is running: from inside a run (the version, commit and date that TLC, SANY and the others print), from the jar (manifest), and from a tool command; for v1.7.4 and the current rolling build.

(b) The state of upstream's official command-line entry point (open PR 1371 in tlaplus/tlaplus, a `tla` command): its entry point, packaging, subcommands, and whether it is merged and in which build.

(c) Which of the `v1.8.0` and `rolling` tags and releases upstream intends to keep moving, and what the immutable CalVer tags (started 2026-04-27) are.

## Source

- Jars downloaded and run locally (Java 25, Debian): `rolling`, `v1.8.0` and `v1.7.4` `tla2tools.jar` from the tlaplus/tlaplus GitHub releases.
- `gh api` and `git ls-remote` against tlaplus/tlaplus: PR 1371 and its comments, issues 783, 1165, 1272, 1277, 1380, the release objects, tags, and `.github/workflows/main.yml` at master (`bc1b506`) and its history.
- Upstream source at master and at `v1.7.4`: `tlc2/TLCGlobals.java`, `customBuild.xml`, `README.md`, `USE.md`.
- Captured data: `tests/fixtures/research/03-jar-identity/` (manifests, banners, sha256 sums, release JSON, the workflow file, the PR 1371 diff, the CalVer tag list).

## Short answer

(a) Three places carry identity, and they do not agree in kind:
- The jar manifest (readable without a JVM): v1.7.4 has `X-Git-Tag: v1.7.4`, `X-Git-ShortRevision: 5a47802`, `Implementation-Version: 2.0 2024-08-08`, and no `Build-TimeStamp`. The rolling build has `Build-TimeStamp: 2026-11-15T00:21:46.50Z`, `X-Git-Revision`/`X-Git-ShortRevision: bc1b506`, `X-Git-Commits-Count: 9089`, `X-Git-Tag:` empty, `Implementation-Version: 2.0 2026-11-15`.
- The TLC banner, which is the first line of every TLC run and appears even with no arguments (exit code 1): v1.7.4 prints `TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)`; the rolling build prints `TLC2 Version 2026.11.15.002146 (rev: bc1b506)`. The CalVer is the manifest `Build-TimeStamp` reformatted as `yyyy.MM.dd.HHmmss` in UTC, so the two always agree. With `-tool` the same line comes as message 2262.
- `tlc2.REPL` with `TLCGet("revision")` gives `count`, `timestamp`, `date`, `tag` (the short commit) and, in rolling only, `calver`. `tlc2.REPL` does not exist in v1.7.4.
There is no `-version` option in either build (TLC answers "unrecognized option", exit 1, after printing the banner). SANY, PlusCal and tla2tex print tool versions only (SANY "2.1 created 24 February 2014" in v1.7.4, "2.2 created 08 July 2020" in rolling; pcal 1.11 vs 1.12; tla2tex 1.0 in both), which do not identify the build. So: to know which build is running, use the TLC banner (or the manifest); SANY and pcal cannot tell you.

(b) PR 1371 is open, unmerged, has no reviews, and is not in any build. It adds two files under `general/cli/`: a 93-line bash script `tla` and a README. It is not a Java class and is not packaged in the jar. Subcommands: `tlc`, `sany`, `repl`, `pcal`, `tla2tex`, plus `help` and `--version` (prints the fixed text `tla CLI version 1.0`, not the jar version). It runs `java -cp $TLA_JAR <class> "$@"` with `tlc2.TLC`, `tla2sany.SANY`, `tlc2.REPL`, `pcal.trans`, `tla2tex.TLA`. Maintainers (ahelwer, lemmy) said on 2026-04-04 to 06 that the design is not settled: they want a thin wrapper over a new Java entry point in the jar (lemmy suggested a new class such as `TLC2`), a mailing-list discussion and a community-meeting discussion, and ahelwer said such commands could ship marked as changeable. Nothing happened after 2026-04-20 except a base-branch force-push on 2026-09-15. The jar's manifest `Main-class` is still `tlc2.TLC` in both builds. There is no stable "official command" for tlaup to call today. The entry points are the main classes.

(c) Both `v1.8.0` and `rolling` move on every push to master. `v1.8.0` is documented upstream as the moving rolling pre-release for the 1.8 line, and it is expected to be replaced by a new version name at the next version bump. `rolling` is the one upstream intends as the stable name that survives version bumps (commit 2ef2af8c7, 2026-10-23). Today they hold identical bytes (sha256 `7e53aa63...fb84f`). The CalVer tags are created by the same workflow on every master build: annotated git tags only, with no GitHub release and no downloadable jar (`.../releases/download/2026.11.15.002146/tla2tools.jar` returns 404). So a CalVer name tells you a build's identity but not where to download it. No upstream text says the jar behind any CalVer tag is kept.

## Confidence

Verified for (a) and (c) as to what the workflow and the releases do today, and for (b) as to the PR's state and content. Partly verified for upstream intent in (c): maintainers state that the pre-release is rolling, and the commit message states the purpose of `rolling`, but there is no written statement of how long `v1.8.0` keeps moving or whether old CalVer jars will ever be published. Not verified: the banner text of builds between 2026-02-25 and 2026-04-27 beyond what the source change says (no old jars are obtainable).

## Evidence

### (a) Identity of a running jar

Commands run (Java 25, scratch spec `T.tla`; outputs in the fixtures folder):

```
$ java -cp v1.7.4/tla2tools.jar tlc2.TLC          # exit 1
TLC2 Version 2.19 of 08 August 2024 (rev: 5a47802)
Error: Error: Missing input TLA+ module.
$ java -cp rolling/tla2tools.jar tlc2.TLC         # exit 1
TLC2 Version 2026.11.15.002146 (rev: bc1b506)
Error: Error: Missing input TLA+ module.
$ java -cp rolling/tla2tools.jar tlc2.TLC -nowarning -tool -workers 1 T.tla
@!@!@STARTMSG 2262:0 @!@!@
TLC2 Version 2026.11.15.002146 (rev: bc1b506)
@!@!@ENDMSG 2262 @!@!@
$ echo 'TLCGet("revision")' | java -cp rolling/tla2tools.jar tlc2.REPL
[count |-> 9089, timestamp |-> 1794702106, date |-> "2026-11-15T00:21:46.50Z", tag |-> "bc1b506", calver |-> "2026.11.15.002146"]
$ java -cp v1.7.4/tla2tools.jar tlc2.REPL
Error: Could not find or load main class tlc2.REPL
```

- `java -jar tla2tools.jar` runs `tlc2.TLC` (manifest `Main-class: tlc2.TLC`, both jars; `USE.md` says so too), so it prints the same banner.
- `-version` is not an option in either build; both print the banner and an "unrecognized option" error, exit code 1. `-help` prints a man page whose TLC line carries the same version text (v1.7.4: `Version 2.19 of 08 August 2024`; rolling: `Version 2026.11.15.002146`), also exit 1.
- The banner is cheap: no spec is needed, and the process exits at once. The cost is one JVM start. Message 2262 is the banner in `-tool` mode.
- SANY, pcal and tla2tex banners (run with a spec or `-help`):
  - SANY: v1.7.4 `****** SANY2 Version 2.1 created 24 February 2014`; rolling `SANY2 Version 2.2 created 08 July 2020`.
  - pcal.trans: v1.7.4 `Version 1.11 of 31 December 2020`; rolling `Version 1.12 of 01 July 2024`.
  - tla2tex.TLA: `Version 1.0 created 12 Apr 2013` in both.
  These are per-tool versions that change rarely. Two different builds can print the same value, so they do not identify a build. They do differ between v1.7.4 and rolling here, but a mid-2026 rolling build may print the same as another.
- Manifests (full text in `manifest-v174.txt`, `manifest-rolling.txt`):

| Attribute | v1.7.4 | rolling (bc1b506) |
|---|---|---|
| `Implementation-Version` | `2.0 2024-08-08` | `2.0 2026-11-15` |
| `Build-TimeStamp` | absent | `2026-11-15T00:21:46.50Z` |
| `X-Git-Revision` | `5a47802...` (full sha) | `bc1b506...` (full sha) |
| `X-Git-ShortRevision` | `5a47802` | `bc1b506` |
| `X-Git-Tag` | `v1.7.4` | empty |
| `X-Git-Branch` | `v1.7.4` | `master` |
| `X-Git-Commits-Count` | `7425` | `9089` |
| `Main-class` | `tlc2.TLC` | `tlc2.TLC` |
| `Class-Path` | `CommunityModules.jar` | `CommunityModules-deps.jar CommunityModules.jar` |

  `Build-Tag: ${env.BUILD_TAG}` and `Build-Rev: ${Build-Rev}` are unexpanded placeholders in both; do not read them. `Implementation-Version` is not unique: its date is the build day, and the leading "2.0" never changes.
- Source (`TLCGlobals.Version`): since commit 5a565e087 (2026-02-25, "Switch TLC's version number to CalVer") the number is the manifest `Build-TimeStamp` formatted `yyyy.MM.dd.HHmmss` in UTC; if there is no manifest it uses the current time. v1.7.4 has a fixed string, `versionOfTLC = "Version 2.19 of 08 August 2024"`. The maintenance branch keeps 2.x numbers (2.20 and up are reserved), and a year prefix cannot collide with them (commit message of 5a565e087).
- A rolling build can be told from a maintenance one by the banner: a version starting `20` followed by dots is rolling; `2.NN of <date>` is maintenance. CalVer sorts correctly as a plain string or as a dotted integer tuple, and every CalVer is greater than every `2.NN` as a tuple (2026 > 2).
- Identity check (hash only): the `rolling` and `v1.8.0` assets have the same sha256 `7e53aa636dac8a3cb0533f343115c0548e03fc0ce5edc7739becf58d3d0fb84f`, size 4510884, both in the GitHub API `digest` field and in my downloaded copies. `v1.7.4` is `936a2620...0e88`, size 2274532 (GitHub reports no digest for it).
- Question 14 covers reading the commit and CalVer from the manifest without a JVM; the table above is a by-product.

### (b) Upstream's `tla` command

- PR: https://github.com/tlaplus/tlaplus/pull/1371, "Add optional CLI wrapper for tla2tools.jar", by suckrowPierre, opened 2026-04-04, state OPEN, not draft, zero reviews, no labels, 7 comments. Two commits (04-04 and 04-10). Last activity: a base-branch force-push by lemmy on 2026-09-15; last comment 2026-04-20.
- Files (diff in `pr1371-files.txt`): `general/cli/tla` (93 lines, `#!/usr/bin/env bash`) and `general/cli/README.md` (44 lines).
- Behaviour: needs `TLA_JAR` set (no discovery, no download); uses `$JAVA_HOME/bin/java` or `java`; prints help with no args; `--version` prints `tla CLI version 1.0` (the wrapper's own, not the jar's); unknown commands exit 1; a leading `-` flag exits 0 quietly (for tab completion). Dispatch: `tlc` runs `tlc2.TLC`, `sany` runs `tla2sany.SANY`, `repl` runs `tlc2.REPL`, `pcal` runs `pcal.trans`, `tla2tex` runs `tla2tex.TLA`. It uses `exec` so exit codes pass through. It does not add the default flags tlaup wants, and does not pass `-XX:+UseParallelGC`.
- Maintainer position (comments on the PR):
  - ahelwer 2026-04-04: "one of those things we only have a chance to do once so it's important to get it right"; suggests a mailing-list discussion and the monthly community meeting; mentions hwayne's tlacli as input. Link to issue #783.
  - ahelwer 2026-04-05: backward compatibility has made the current CLI poor (example: SANY needs `-error-codes` to exit non-zero); "fine to prototype release them with the message that these commands can change at any time".
  - lemmy 2026-04-06: move as much as possible into the jar; wrapper minimal; introduce a new Java entry point (suggested `TLC2.java` or a better name) that the wrapper delegates to. ahelwer agreed.
  - suckrowPierre 2026-04-05 and 04-20: will take the discussion steps.
- Related: issue #783 "completely redo TLC and SANY command line interfaces" (open since 2023-01-28; lemmy 2023-02-20 floated redirect mains `tla.TLC`, `tla.SANY`, `tla.PCAL`; none exist in the current jar: `unzip -l` shows no `tla/` package). PR 1296 "stdio-based MCP server" (open) and branch `mku-mcp` are a separate entry point, not a CLI.
- State of the build: the rolling jar's manifest `Main-class` is `tlc2.TLC`; there is no new CLI class in the jar. `formatter.Main` exists in the rolling jar (formatter integrated 2026-03-16, PR 1347) but is not a general command. `USE.md` (master) still documents `java tla2sany.SANY`, `java tlc2.TLC`, `java tlc2.REPL`, `java pcal.trans`, `java tla2tex.TLA`, `java tla2sany.xml.XMLExporter`.

### (c) Which tags move

Workflow `.github/workflows/main.yml` at master (copy in `upstream-main.yml.txt`), job `build`, runs on every push to `master`:
- "Upload release assets": finds the release by the name `The Clarke release` (tag `v1.8.0`), deletes its old `tla2tools.jar` and uploads the new one, then rewrites the release notes and re-publishes it as a pre-release (so the release date refreshes; issue #1211).
- "Update tags": `git tag -f v1.8.0`, `git tag -f rolling`, then computes `CALVER` by running `tlc2.REPL 'TLCGet("revision").calver'` on the freshly built jar, validates it with `git check-ref-format`, makes the annotated tag `git tag -a "$CALVER" -m "TLA+ Tools $CALVER"`, and pushes everything with `--follow-tags --tags --force`.
- "Update rolling release": creates the release `rolling` (title "Rolling build", `--prerelease --latest=false`, notes "Most recent build of the master branch.") if absent, then `gh release upload rolling --clobber tla2tools.jar`. Comment in the file: "Unlike v1.8.0, the rolling tag survives version bumps, which gives consumers a stable download URL for the most recent build."
- Commit 2ef2af8c7 (2026-10-23, "Publish each master build to a rolling release with a fixed URL"): "The download URL of the latest tla2tools.jar contains the release tag, which is v1.8.0 today and changes with each version bump... A rolling tag and pre-release that CI moves to every master build give them one URL that does not change: https://github.com/tlaplus/tlaplus/releases/download/rolling/tla2tools.jar. The release is marked as not latest, so the GitHub 'latest release' link still points to the last stable release."
- Commit e3142ca3b (2026-04-27, first CalVer tag `2026.04.27.203507` points at it): "The CI used to push only the moving v1.8.0 tag. Add an immutable per-commit tag (e.g. 2026.04.27.094612) alongside it, so each rolling pre-release is reachable by a fixed git ref. This is a step toward the predictable release cadence in Github issue #1165."

Current state (checked 2026-11-15 UTC; see the date note below):
```
bc1b506bdcad  refs/heads/master
bc1b506bdcad  refs/tags/rolling
bc1b506bdcad  refs/tags/v1.8.0
bc1b506bdcad  refs/tags/2026.11.15.002146^{}   (annotated, tagger "TLA+ GitHub Action")
```
- Releases (`gh release list`): `rolling` "Rolling build" Pre-release, published 2026-10-23, asset updated 2026-11-15T00:32:15Z; `v1.8.0` "The Clarke release" Pre-release, published_at refreshed 2026-11-15T00:29:14Z, asset 00:27:39Z; `v1.7.4` "The Xenophanes release" is the one marked Latest (2024-08-05), asset not changed since 2024-08-08.
- The two assets were uploaded about five minutes apart by the same job and have the same digest, consistent with one build uploaded twice.
- 168 tags start with `2026`: 84 annotated CalVer tags (84 peeled `^{}` entries), the first `2026.04.27.203507`, the last `2026.11.15.002146`. Some commits have more than one: `2026.11.06.005304` (tagged 2026-11-06T01:45Z) and `2026.11.06.100558` (10:21Z) both peel to `3ec1cc4f`. So a CalVer names a build, not a commit; re-running the workflow on the same commit mints a second CalVer (and a different jar timestamp).
- No GitHub release exists for any CalVer tag (`gh release list --limit 100` shows none starting with `2026`; the download URL of the latest CalVer returns HTTP 404). The only repository ruleset is one named `master` targeting a branch; I found no tag ruleset, and the workflow itself pushes with `--force`. So "immutable" is by convention of the CalVer naming (each name is used once), not enforced by a visible rule. I could not check organization-level rules.
- Maintainers' statements:
  - Issue #1277 (2026-01-11), ahelwer: "1.8.0 is the rolling release. Look at the dates of the uploaded files."; and "Every commit to master is built and uploaded to the rolling release. The git commit is attached to the built artifact in its version info."
  - Issue #1272 (2026-01-03), lemmy: "pre-release ... would be more accurately described as a rolling release. We switched to a rolling release model some time ago"; the 1.7.x line is for "very long-term stability" and "released from a dedicated maintenance branch. The 1.8 pre-release is updated on every commit to master."
  - Issue #1380 (2026-04-25): a user's pinned sha256 of the `v1.8.0` jar changed; FedericoPonzi quoted the README ("every commit to the master branch is built & uploaded to the 1.8.0 Clarke pre-release") and said every merged commit updates the release. The reporter asked for a fixed name or a blob store keyed by version. ahelwer 2026-05-26: GitHub releases "are intentionally malleable in what artifacts they contain... you eventually run out of storage when you frequently upload binaries"; to pin, build from a commit.
  - Issue #1165, "Bring back regular releases and maintenance branches" (open since 2025-04-01): on 2026-11-06 hemp proposed an extra step to also push a CalVer release jar; lemmy answered with only the link `releases#release-rolling`. No decision recorded.
- README at master (last changed 2026-04-06) still says every commit is uploaded to "the 1.8.0 Clarke pre-release" and does not mention `rolling` or CalVer.

## Implications for the roadmap

Milestone 1b, other tools (keep sany, pcal and repl thin; check which jar build is running):
- Do not try to switch to upstream's own entry point now: it does not exist in any build. PR 1371 is a bash script outside the jar, requires `TLA_JAR`, is unreviewed, and the maintainers asked for a new Java entry point first. Keep calling `tlc2.TLC`, `tla2sany.SANY`, `tlc2.REPL`, `pcal.trans` directly.
- To prepare the switch, tlaup should detect the build from data it already has, with no JVM: read the manifest from the stored jar. Only `Build-TimeStamp` (CalVer source) and `X-Git-*` are reliable; `Build-Tag`/`Build-Rev` are placeholders. Capability checks should be on class presence (for example `tlc2/REPL.class` is missing in v1.7.4) or on the CalVer, not on the version string. When upstream adds a command, the cheapest test is whether its class is in the jar's file list.
- If a runtime check is wanted: running `tlc2.TLC` with no arguments gives the banner in one JVM start and exits 1; parse `Version (\S+)( of ...)? \(rev: (\w+)\)`. There is no `-version`. SANY, pcal and tla2tex versions cannot identify a build, so tlaup should not report them as the jar's version.
- The "rolling" detection rule: version text starts with four digits and a dot; maintenance builds look like `2.NN of <date>`.

Milestone 1, first-run prompt and typing versions (`latest`, `stable`, `rolling`):
- `stable` is the GitHub release marked Latest (v1.7.4). `rolling` should mean the release tagged `rolling`, not `v1.8.0`: upstream built `rolling` as the name that survives version bumps and said so in the workflow and the commit message. `v1.8.0` will stop being the rolling pre-release at the next version bump (the name `v1.8.0` is expected to move to whatever the next release is called, and, going by the workflow, the tag is moved by `git tag -f v1.8.0` only while that line is current). The README is behind: it still points at `v1.8.0`.
- What `latest` should mean (stable or rolling) is a design decision; the evidence is that GitHub's "latest" link deliberately stays on the stable release.

Milestone 3 (naming builds; no double download; sorting):
- Two names, one build: `rolling` and `v1.8.0` have the same sha256 today; compare by digest (the API gives `digest: sha256:...` for the 1.8 assets; v1.7.4 has none) or by CalVer/commit from the jar. Do not key the cache on the tag name: a tag name is not a version here (issue #1380: the same `v1.8.0` URL gave different bytes within days).
- The jar's own identity is the CalVer `Build-TimeStamp`: it sorts correctly as a string and is greater than any `2.NN` or `1.x`. A `rolling` that has no number can be given the CalVer read from the jar after download. Before download, the tag name `rolling` alone tells nothing about the CalVer; the remote CalVer is only knowable by listing git tags (`git ls-remote --tags`; the newest annotated 20xx tag whose peeled commit matches `refs/tags/rolling`), because the release asset has no CalVer in its name. That works on the day, but the CalVer tags have no download, so tlaup cannot fetch an older CalVer build from upstream.
- Each build's CalVer is unique per workflow run, but one commit can have several (2026.11.06.005304 and .100558). If tlaup names a stored build by commit it can collide; name by CalVer, and keep the commit as an attribute.
- Reproducibility: tlaup's download-once guarantee rests on its own cache (sha256 pinned on first download), since upstream replaces the asset on every master push and says that it does not guarantee old bytes.

## Open follow-ups

- Whether upstream will publish a downloadable artifact per CalVer tag (issue #1165, hemp's proposal 2026-11-06); would answer "how do I get CalVer X". The only way to find out is to watch that issue or ask maintainers; I did not contact anyone.
- Whether `v1.8.0` will keep being the name used by the Toolbox and `tlaplus/examples`-style consumers after the next version bump; a later check of the tag list after a bump would show it.
- Whether there is tag protection at the organization level (rulesets visible to repo admins only).
- The exact banner of rolling builds between 2026-02-25 and 2026-04-27 (CalVer in the banner, no CalVer tag yet); no jar of that period is obtainable, only the source change.
- How a downstream tool should detect a new upstream command class once one exists; unknowable until upstream picks a class name.
- Whether `Implementation-Version` should be used at all: it carries only a build date.

## Date checked

2026-11-14 (local time). The upstream data was read at about 2026-11-15 08:20 UTC; upstream's latest build, tag and release timestamps are 2026-11-15 UTC, so some dates above are one day later than the local date. Everything above is a snapshot of upstream at that moment: `rolling` and `v1.8.0` have already moved with each master push and will have changed by the time this is read.
