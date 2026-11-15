# 04: Does upstream TLC fire the CommunityModules repository_dispatch trigger?

## Question

Do upstream TLC builds (tlaplus/tlaplus) fire the `repository_dispatch` trigger of tlaplus/CommunityModules, so that a CommunityModules release could be tied to a TLC build by date? And how else could a CommunityModules release be matched to a TLC build?

## Source

- https://github.com/tlaplus/CommunityModules/blob/master/.github/workflows/main.yml (workflow "CI")
- https://github.com/tlaplus/tlaplus/blob/master/.github/workflows/main.yml (workflow "main", the rolling/release build)
- Other tlaplus/tlaplus workflows listed with `gh api repos/tlaplus/tlaplus/contents/.github/workflows` and searched for `dispatch` and `community`: pr.yml, perf.yml, dependency-submission.yml, rrsync-inria.yml, test-*.yml.
- Run history from `gh run list`, release data from `gh release list` / `gh api`, and the jar of CommunityModules release 202611060952.

## Short answer

Yes, the dispatch is sent, but it does not make a release, so it cannot be used for matching.

- CommunityModules `main.yml` listens to `repository_dispatch` (any event type, no `types:` filter) and to pushes to `master`.
- tlaplus/tlaplus `main.yml` ends every successful ubuntu build with `gh api repos/tlaplus/CommunityModules/dispatches` (event type `tlaplus-dispatch`, payload `{"source":"tlaplus"}`).
- On a dispatch run, CommunityModules builds and tests against the new TLC, but the steps "Create Release" and "Upload ... Asset" carry `if: github.event_name == 'push'`. So a dispatch run publishes nothing. Releases come only from pushes to `master`.
- Therefore a CommunityModules release carries no link to a TLC build: no TLC version or commit in the notes (empty), the jar manifest, or the assets. Matching has to use timestamps, and the timestamps only tell which `rolling` jar was current when the CommunityModules push build ran, not which TLC it was compiled against with certainty.

## Confidence

Verified for the workflow logic, the dispatch direction and the run history. The by-date matching rule itself is an inference from timestamps: not verified, and it cannot be checked from upstream data (no recorded TLC build id).

## Evidence

### CommunityModules workflow

`main.yml` (`name: CI`):

```
on:
 repository_dispatch:
 push:
    branches: ['master']
    paths-ignore: [README.md]
```

- Branch is `master`, not `main`.
- Tag and release name is `date +'%Y%m%d%H%M'` taken at build start (UTC runner clock), e.g. `202611060952`.
- Steps `Create Release`, `Upload Release Asset` (x2) and `Upload dateless Release Asset` (x2) all have `if: github.event_name == 'push' && matrix.os == 'ubuntu-latest'`.
- Last step `Repository Dispatch` (`if: github.event.client_payload.source != 'tlaplus'`) sends event type `tlaplus-dispatch` with payload `{"source":"CommunityModules"}` to tlaplus/tlaplus, using `peter-evans/repository-dispatch@v3`. So a CommunityModules push also triggers a TLC build. The `source` check prevents a loop.
- Second job `tlaps` verifies the `*_proofs.tla` modules with TLAPS 1.6.0-pre.

### tlaplus/tlaplus senders

`grep -n -i -E "dispatch|community"` over all workflow files:

- `main.yml` lines 4-5: `repository_dispatch:` and `workflow_dispatch:` as triggers; line 54 echoes `client_payload.source`.
- `main.yml` lines 326-336, the step "Integration tests with CommunityModules", `if: matrix.operating-system == 'ubuntu-latest' && github.event.client_payload.source != 'CommunityModules'`:

```
gh api repos/tlaplus/CommunityModules/dispatches --method POST \
  --input - <<< '{"event_type":"tlaplus-dispatch","client_payload":{"source":"tlaplus"}}'
```

  The comment in the file calls it "integration tests". The same step block also dispatches to tlaplus/examples and tlaplus/vscode-tlaplus. It uses the secret `COMMUNITYMODULES_ACCESS_TOKEN`.
- `pr.yml` lines 86-99: pull-request builds clone CommunityModules and build it with the PR's tla2tools.jar (`ant -f communitymodules/build.xml -Dskip.download=true`). No dispatch.
- `perf.yml` line 63: downloads `releases/latest/download/CommunityModules-deps.jar`. No dispatch.
- Other workflows: no match for `repository_dispatch` or CommunityModules.

### Run history

`gh run list -R tlaplus/CommunityModules --event repository_dispatch -L 20` returns 20 successful `CI` runs, all headSha unchanged from the last push, for example: 2026-11-15T00:32:28Z, 2026-11-06T22:34:58Z, 2026-11-06T18:39:41Z, 2026-11-06T01:45:37Z, 2026-11-03T18:18:06Z, 2026-11-02T16:57:01Z ... 2026-10-13T00:14:05Z. They are dispatch runs, about 10 to 17 minutes each.

Compared with tlaplus/tlaplus `main.yml` runs (`gh run list -R tlaplus/tlaplus -w main.yml`, created to updated):

| tlaplus build (push) | ended | CommunityModules dispatch run |
|---|---|---|
| 2026-11-06T22:08:58Z | 22:35:01Z | 2026-11-06T22:34:58Z |
| 2026-11-06T18:15:44Z | 18:39:43Z | 2026-11-06T18:39:41Z |
| 2026-11-06T00:39:10Z | 01:45:40Z | 2026-11-06T01:45:37Z |
| 2026-11-03T17:53:23Z | 18:18:07Z | 2026-11-03T18:18:06Z |
| 2026-11-02T16:31:58Z | 16:57:26Z | 2026-11-02T16:57:01Z |

Each dispatch run starts within seconds of the end of a tlaplus build, so the sender works. The dispatch is sent at the very end of the build, after the jar is uploaded to the `rolling` release.

The reverse direction is also visible: CommunityModules push at 2026-11-06T09:52:27Z, then a tlaplus `repository_dispatch` run at 2026-11-06T09:53:23Z (ended 10:22:05Z). That tlaplus run did not send a dispatch back (source was CommunityModules). The dispatch run at 2026-11-06T09:53 does not appear in the CommunityModules list afterwards, consistent with the loop guard.

Releases vs runs: `gh release list -R tlaplus/CommunityModules` shows 202611060952 (Latest, 2026-11-06T09:53:15Z), 202610262215, 202610240123, 202610131629, 202610040242, ... Only one release exists for 2026-11-06, although four dispatch runs happened that day and ten in the previous three weeks. The release times match push runs (e.g. push run 2026-11-06T09:52:27Z, tag 202611060952), never the dispatch runs. So the dispatch runs create no releases.

Note: the newest `rolling` and tlaplus run times (2026-11-15) are later than the stated date of this check, so the runner/API clock and the check date differ; only the order of events matters here.

### Can a release be matched to a TLC build from the release itself?

- Release 202611060952: notes empty, assets `CommunityModules.jar` and `CommunityModules-202611060952.jar` (145180 bytes), `CommunityModules-deps.jar` and `CommunityModules-deps-202611060952.jar` (4930534 bytes).
- `unzip -p CommunityModules.jar META-INF/MANIFEST.MF` gives only `Manifest-Version`, `Ant-Version: Apache Ant 1.10.14`, `Created-By: 17.0.21+9 (Eclipse Adoptium)`. The `-deps` jar manifest is the same. No TLC version, commit or build date.
- The jar entry timestamps (e.g. 2026-11-06 09:52) equal the build time, which equals the tag.
- tlaplus `rolling` release: `created_at` 2026-10-23T14:04:03Z (the release object is old and reused), its asset `tla2tools.jar` has `updated_at` per build (2026-11-15T00:32:15Z for the latest). So the TLC build time of the current rolling jar is the asset `updated_at`, but older rolling jars are overwritten and not kept, so a past TLC build can only be dated from what the user installed (its own record), not looked up later.

## Implications for the roadmap

- The dispatch does not give a tighter match. It tests the CommunityModules `master` HEAD against each new TLC build, but publishes nothing. The newest release can be older than the TLC build by weeks (the latest release is 2026-11-06T09:52, while TLC builds on 2026-11-06T18:15, 2026-11-06T22:08 and 2026-11-15 happened later).
- Decision D11 ("the release published after the TLC build and before the next one") often has no candidate: releases are rare compared to TLC builds (about 5 releases in 8 weeks against more than 14 TLC builds in the same period), so most TLC builds have no CommunityModules release published in their window. A rule that tolerates "no release in the window" is needed, for example fall back to the latest release published before the TLC build, which was built against the previous `rolling` jar. Which fallback is acceptable is a design question.
- A dispatch run that passed is a (weak) positive signal that CommunityModules `master` HEAD works with that TLC, but it is not recorded in any release or asset. It is visible only in the run list, which needs an authenticated or rate-limited API call and is not a stable interface.
- The project file should record the CommunityModules release tag and the jar digest, since neither the jar nor the release states the TLC build.
- The tool cannot verify that a CommunityModules release really was compiled against the user's TLC jar. It can only report the dates.

## Open follow-ups

- Check CommunityModules `build.xml` to confirm it downloads the `rolling` tla2tools.jar (reported by others, not re-verified here) and whether the compile-time API surface changes often enough to matter. If overrides only use stable APIs, matching by date may be unnecessary and "latest release" would do.
- Test whether a release built against an older `rolling` jar loads and runs on a newer or older TLC (an experiment, not done here). That would answer whether date matching is needed at all.
- Ask the CommunityModules maintainers whether they would add the TLC build id to the release notes or manifest. That is outside this spike (no contact made).
- Not checked: whether the CommunityModules repository has another published `repository_dispatch` consumer (`tlaplus/examples`, `vscode-tlaplus` and `ValidationTestSuite` also listen; their use is irrelevant here).

## Date checked

2026-11-14 (run and release data are as returned by the GitHub API at the time of the check; see the clock note above).
