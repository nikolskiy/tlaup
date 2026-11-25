# 54. The integration job

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`test.yml` has a job `integration` that runs the integration tests of [52](52-integration-tests.md) on Linux and macOS, with Java 11 and 25 and both supported TLC builds, gets each jar with tlaup itself through a cache, records which rolling build it used, ends with the clean-home check, and is part of the one required `Test` check. It runs only commands of the new tree (`tool install`, `doctor`, `tool current`, `tool dir`), so no old command is kept working for it (decision D62). The lifeline job gets a rolling jar the same way, for the REPL case of [52](52-integration-tests.md). The workflow also runs every week.

## Covers

- Roadmap items:
  - "Integration job on every push, with a matrix over Java 11 and 25 (oldest and newest; widen later if other versions need support) and both supported TLC builds, on GitHub-hosted runners, macOS included ...; cache the jar. ... until milestone 3 the job runs against the current rolling build and records which build that was." ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this), line 391). In full.
- Design sections:
  - [30 I1](../design/30-ci-and-release.md#i1-integration-job): all of it.
  - [01 T2](../design/01-testing.md#t2-isolation), "Proof that it holds", and [01 T9](../design/01-testing.md#t9-integration-tests): the integration job "ends with the same 'nothing appeared in the home folder' check as the unit job, extended to `~/.tlaplus`".
  - [30 I5](../design/30-ci-and-release.md#i5-workflow-hygiene): for this job, `timeout-minutes: 30`, `--locked`, pinned actions, and the entry `integration` in the `needs` of the `Test` job.
  - [30 I2](../design/30-ci-and-release.md#i2-unit-job), in part: the jar the lifeline job needs for its REPL case ("`tlaup repl`'s JVM under a pseudo-terminal still reads a line from stdin"), for which I2 now says the job "installs the current rolling build from the integration job's cache"; how, below (finding H11).

## Depends on

- [52](52-integration-tests.md): `tests/integration/`, `TLAUP_TEST_JARS` and its accepted shape (a store's tool folder is one), `uv run poe test-integration`, and `tests/lifeline/test_repl_terminal.py`, which reads the same variable.
- [53](53-ci-workflows.md): `test.yml` as it rewrites it: the workflow-level permissions, concurrency and weekly schedule, the pinned action hashes and their comments, the `Test` job that this one joins, and the clean-home step's command.
- [46](46-doctor.md): `tlaup doctor`, which compares each installed jar with its recorded SHA-256 (step 5 of I1).
- Through 52: [29](29-tool-commands.md) (`tlaup tool install`, `tool install --force`, `tool current`, `tool dir`) and [24](24-github-client.md) (the token sent to `api.github.com` only, D41).

Changed from the draft (52, 53): 46 is added, for `doctor`, which no package 52 depends on provides.

## Files

Changes:

- `.github/workflows/test.yml`: the job `integration` (below), `integration` in the `needs` list of `Test`, and in the `lifeline` job the steps that give it a rolling jar (below). Nothing else in the file.
- `docs/contributing/development.md`: the CI section (which 53 rewrites) gains the integration job in a line or two, including how to abandon the jar cache (raise the number in the keys).

Creates, Deletes: nothing.

Shared files: `test.yml` with [57](57-repo-hygiene.md), which removes one line from the `lint` job and whose test reads the `unit` matrix; neither touches this job.

## Interfaces

The job, from [30 I1](../design/30-ci-and-release.md#i1-integration-job), step by step. What stage 4 adds to the design's words is marked.

| Axis | Values |
| --- | --- |
| `os` | `ubuntu-latest`, `macos-latest` |
| `java` | `11`, `25` (Temurin) |
| `tools` | `v1.7.4`, `rolling` |

Eight jobs, `fail-fast: false`, `timeout-minutes: 30`. A comment beside `java: 11` says that `macos-latest` is macOS 26 on arm64 and that its image has Temurin 11.0.32 preinstalled, which `setup-java` may take instead of downloading 11.0.33+10, and that either is fine (I1). Job-level environment (stage 4): `TLAUP_HOME: ${{ runner.temp }}/tlaup`, so the store is job-local and the cache path is fixed.

1. Check out (`persist-credentials: false`); set up uv; `uv sync --locked`.
2. `actions/setup-java` with `distribution: temurin` and `java-version: ${{ matrix.java }}`. Its `JAVA_HOME` is kept for every later step (I1), and 52's `isolated` fixture keeps it.
3. **Restore the cache**, before the install: `actions/cache` (restore and save, the action's default) on `${{ runner.temp }}/tlaup/cache/tool`, the store's tool folder under that `TLAUP_HOME` ([14 F2](../design/14-config-and-cli.md#f2-folder-overrides): `cache = $TLAUP_HOME/cache`; the tool folder is `<cache>/tool`).
   - `v1.7.4`: key `tools-1-v1.7.4-936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88`, the SHA-256 of the v1.7.4 jar (research 18, one download over HTTPS; the same value is in `tests/parse/golden/tlc/v1.7.4/build.toml`).
   - `rolling`: key `tools-1-rolling-<digest>`, where a step before the cache step reads the published digest of the rolling release's `tla2tools.jar` with one API call, for example `gh api repos/tlaplus/tlaplus/releases/tags/rolling --jq '.assets[] | select(.name == "tla2tools.jar") | .digest'`, and writes it to `$GITHUB_OUTPUT` (stage 4's command; the design says "the published digest fetched first by one API call (`gh api`)"). That step has `GH_TOKEN: ${{ github.token }}` in its environment: `gh` does not run without a token there. A new upstream build changes the digest, so it misses the cache.
   - The `1` in both keys is a number kept once in the workflow file (a workflow-level `env` value or a comment-marked literal) and raised by hand to abandon every stored entry.
4. **Install with tlaup**: `uv run tlaup tool install ${{ matrix.tools }}` with `GITHUB_TOKEN: ${{ github.token }}` in the step's environment (read-only, from the workflow's `contents: read`), so the API limit is not hit. With the cache restored and the published build unchanged this is one API request and no download ([12 V12](../design/12-tools-and-downloads.md#v12-install)); otherwise it downloads, and the cache action saves the folder at the end of the job.
5. **Check, repair and record**: `uv run tlaup doctor`. If it fails, `uv run tlaup tool install --force ${{ matrix.tools }}`, then `uv run tlaup doctor` again, and a warning in the job summary (`$GITHUB_STEP_SUMMARY`) that names the cache key and says to raise the number in the keys, because a stored entry cannot be saved again under an existing key and every later run would restore the damaged one and repair it again. Then `uv run tlaup tool current` is appended to the job summary: for rolling it is the only record of which build the run used.
6. `TLAUP_TEST_JARS=<the store's tool folder> uv run poe test-integration`. The folder is `${{ runner.temp }}/tlaup/cache/tool`, or what `uv run tlaup tool dir` prints; 52's discovery takes the build folders in it and skips `pin`, `.lock` and `.tmp/`.
7. **The clean-home check** (stage 4 places it last, as T9 says the job "ends with" it): the same command as the unit job's last step ([53](53-ci-workflows.md), using [03](03-test-foundation.md)'s `scripts/test_clean.py` in its check-only form), whose list already includes `~/.tlaplus`. It runs with `if: always()` after step 6 has started, so a failing test run still shows whether something leaked. `TLAUP_HOME` points outside the home folder here, so a tlaup folder under the home would itself be a leak.

**The lifeline job's jar** (I2: the current rolling build from the integration job's cache; [53](53-ci-workflows.md) built the job with Temurin 11 and no jar). In the `lifeline` job, after `actions/setup-java` and before `uv run poe test-lifeline`, the same steps 3 to 5 as above for `rolling` alone (the digest step, the cache restore with the `rolling` key, `uv run tlaup tool install rolling` with `GITHUB_TOKEN`, `uv run tlaup doctor`), with `TLAUP_HOME: ${{ runner.temp }}/tlaup` on the job; then `uv run poe test-lifeline` with `TLAUP_TEST_JARS` set to the store's tool folder. Rolling, because v1.7.4 has no REPL. The cache key is the integration job's, so the two jobs share one entry. The job's other tests ignore the variable.

Consumes: the `Test` job of 53 (`needs` gains `integration`); its weekly `schedule` trigger (53 adds it for the newest-dependencies job; this job runs on it too, which is I1's "weekly schedule"); the pinned hashes 53 recorded for `actions/checkout`, `astral-sh/setup-uv`, `actions/setup-java` and `actions/cache`, looked up again if more than a few days old.

## Tests that must pass

The job is the test. In the pull request:

- All eight cells green, with the summary of each showing `tool current` (the rolling cells name the build).
- Both `lifeline` cells green, with the REPL case run and not skipped (its line in the log).
- A second run of the same commit (re-run from the Actions page) restores the cache and makes no download: the step 4 log says the build is already installed.
- The `Test` job shows `integration` among its needs, and a red integration cell makes `Test` red (seen on the first run of a deliberately failing commit on the branch, or argued from 53's job if that was already shown there; say which).

No test file changes here.

## Changelog

None. CI only.

## Context for the worker

**Triggers** (I1): every push to `main`, every pull request, and the weekly schedule that 53 adds. A scheduled run that fails opens nothing; GitHub notifies the maintainer. The rolling cells are required checks like the others (I1, "Rejected": a job that is allowed to fail is not read); when one fails because upstream changed its output, the fix is a new capture ([01 T3](../design/01-testing.md#t3-golden-files)) and whatever parser change it needs, in a pull request of its own.

**The token** (D41, [12 V7](../design/12-tools-and-downloads.md#v7-github-client)). Step 4's `GITHUB_TOKEN` is the workflow's own read-only token; tlaup sends it to `api.github.com` only, never with the jar download. Do not pass it to step 6: the tests use no network (52), and the isolation fixture removes it anyway.

**Why the restore comes before the install** (I1): the first version of the design had them the other way round, so a restored cache was never used.

**Why `doctor` and not the install catches a damaged entry** (I1): for v1.7.4, which has no digest, "already installed" rests on the recorded size and upload time, not on the bytes on disk ([12 V12](../design/12-tools-and-downloads.md#v12-install)). `doctor` compares the jar with its recorded SHA-256.

**Facts from research 29 the design restates** (2026-11-19): Temurin 11 exists for macOS on arm64 (11.0.33+10), so no other distribution is needed; `macos-13` no longer exists; an Intel cell is not needed (`macos-15-intel` is the label if one is ever wanted). Both supported builds run on Java 11 on these runners (research 28), so the two `java: 11` rows are expected to pass. The cache action's documentation says "A cache today is immutable and cannot be updated"; entries idle for a week are evicted; the repository's limit is 10 GB.

**The C3 shell checks** in 52 run on the Linux cells only (52 skips them elsewhere); nothing here selects them.

**Maintainer actions this job touches** (not work for this package): after it is merged, the ruleset on `main` ([30 I7](../design/30-ci-and-release.md#i7-ruleset-on-main)) still requires only `Test`, so nothing changes there; and the roadmap's "Capture CI logs soon after a failure worth diagnosing" applies to the weekly runs, since log retention expires.

## Done when

- The job exists as above and all eight cells pass on the pull request; the summary of a rolling cell names the build; the `lifeline` job runs the REPL case.
- A re-run shows the cache hit and no download.
- `Test` needs `integration`.
- `uv run poe lint` and `uv run poe test` pass; the YAML hook passes on `test.yml`.
- The development guide's CI section names the job and the cache number.

## Out of scope

- The integration tests themselves: [52](52-integration-tests.md).
- The other jobs (apart from the lifeline job's jar steps), the triggers, permissions, concurrency, the `Test` job and the action pins: [53](53-ci-workflows.md).
- A wider Java matrix (17, 21) or a Windows cell: rejected (I1; D15).
- Pinning a rolling build so that it can be downloaded again: milestone 3.
- The ruleset on `main`: maintainer action ([30 I7](../design/30-ci-and-release.md#i7-ruleset-on-main)).

## Risks

- From I1: an upstream change can turn `main` red with no change of ours; accepted.
- From I1: a damaged cache entry is repaired for the run by step 5 and replaced for good only when someone raises the number in the keys.
- Eight cells with live TLC runs, among them 52's resume test of a few minutes, against a 30-minute timeout: if a cell comes near it, the pull request says so and the index decides (a larger timeout is a change to I5's number).
- From the cut: the digest step depends on the shape of GitHub's release API (the asset's `digest` field, research 18). If it went missing, the key would become `tools-1-rolling-` and every rolling run would share one entry; so the digest step fails when the value is empty (written by stage 4), and the change is seen at once.
