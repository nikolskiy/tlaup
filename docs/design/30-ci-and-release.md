# 30. Milestone 2: CI, release, build and hygiene

Covers every milestone 2 item outside "Testing approach", which is [01-testing.md](01-testing.md). Relies on decisions D2, D6, D15, D19, D21, D27, D44. Most of this touches no file under `src/` and can be built in parallel with milestone 1 from the start ([00, order of work](00-overview.md#order-of-work)).

State today: one workflow job runs lint and the unit tests on one Python with Java 17, after downloading a jar the unit tests should not need; `release.yml` builds, tests and creates the release page in one job with write access, then publishes; `scripts/release.sh` checks two things.

Nothing in this document was run: no workflow was executed or linted, and nothing was looked up on the network. What the design states about GitHub Actions comes from the two workflow files in the repository and from general knowledge of the platform, not from a check against today's documentation. The facts that need the network were collected in **question 29** of the roadmap's investigation list and answered on 2026-11-19 ([research 29](../research/29-ci-facts-and-recordings.md)); they were worked into the items below on 2026-11-20, marked "top-up". They age fast: the work package that writes the workflows looks the commit hashes up again on the day, since a week-old pin is already behind.

## I1 Integration job

Roadmap: "Integration job on every push, with a matrix over Java 11 and 25 ... and both supported TLC builds, on GitHub-hosted runners, macOS included; cache the jar. v1.7.4 can be pinned exactly. A rolling build cannot be downloaded again once upstream replaces it, so until milestone 3 the job runs against the current rolling build and records which build that was."

**Design.** A job `integration` in `test.yml`.

| Axis | Values |
| --- | --- |
| os | `ubuntu-latest`, `macos-latest` |
| java | `11`, `25` (Temurin) |
| tools | `v1.7.4`, `rolling` |

Eight jobs; `fail-fast: false`. Steps, in this order:

1. Check out; set up uv; `uv sync --locked`.
2. Set up Java with `actions/setup-java`.
3. **Restore the cache**: `actions/cache` on the store's tool folder inside a job-local `TLAUP_HOME`. For `v1.7.4` the key is `tools-1-v1.7.4-<sha256 of the jar>` (the value from research 18). For `rolling` the key is `tools-1-rolling-<digest>`, with the published digest fetched first by one API call (`gh api`, which the runner has), so a new upstream build misses the cache. That step has `GH_TOKEN: ${{ github.token }}` in its environment: `gh` does not run without a token there. The `1` in both keys is a number kept in the workflow file and raised by hand to abandon every stored entry (step 5). The restore comes **before** the install; the first version of this design had them the other way round, so a restored cache was never used.
4. **Get the jar with tlaup itself**: `uv run tlaup tool install <tools>`, with `GITHUB_TOKEN` from the workflow (read-only) so the API limit is not hit; the token goes to `api.github.com` only ([12 V7](12-tools-and-downloads.md#v7-github-client)). With the cache restored and the published build unchanged this is one API request and no download ([12 V12](12-tools-and-downloads.md#v12-install)); otherwise it downloads, and the cache action saves the folder at the end of the job. This is the first real use of the token support, which is why that item sits in milestone 1.
5. **Check, repair and record the build**: `uv run tlaup doctor`, which compares the jar with its recorded SHA-256 and so catches a damaged cache entry. Step 4 cannot catch one: for v1.7.4, which has no digest, "already installed" rests on the recorded size and upload time, not on the bytes on disk ([12 V12](12-tools-and-downloads.md#v12-install)). If `doctor` fails, the step runs `uv run tlaup tool install --force <tools>`, which downloads, verifies and repairs in place, then `doctor` again, and writes a warning to the job summary naming the cache key. The run is healed; the stored entry is not, because an entry cannot be saved again under a key that exists, so every later run would restore the damaged entry and repair it again, at one download each. The warning therefore says to raise the number in the keys (step 3), which makes the next run save a fresh entry. Then `uv run tlaup tool current` is written to the job summary. For rolling this is the only record of which build a given run used.
6. `TLAUP_TEST_JARS=<store> uv run poe test-integration` ([01 T9](01-testing.md#t9-integration-tests)).

Triggers: every push to a branch other than `main` and `archive/**`, **a weekly schedule**, and a run started by hand (`workflow_dispatch`). That is the branch flow of I9 since 2026-11-27; before it, pushes to `main` and to `build/**` branches and every pull request. A push to `main` is not run: `main` changes only by squash merges of pull requests whose head was tested with the same tree (I9). Every push to `main` runs the release workflow instead, which acts only on a release (L8). The weekly run and a run by hand are the ones that test `main` itself. The schedule is a design addition: a rolling build can change TLC's output between two pushes, and a weekly run turns "the next unrelated pull request fails mysteriously" into "the scheduled run failed on Monday". A failed scheduled run opens nothing by itself; GitHub notifies the maintainer.

When the rolling job fails because upstream changed its output, the fix is a new capture ([01 T3](01-testing.md#t3-golden-files)) and whatever parser change it needs. The rolling jobs are **required** checks like the others: a tool that claims to support the current rolling build (D19) should not merge while it does not.

**Rejected.** Running integration only on a schedule: a pull request that breaks trace parsing against real TLC must fail (the milestone's exit criterion). Marking rolling jobs as allowed to fail: nobody reads a job that is allowed to fail. A wider Java matrix (17, 21): the roadmap says oldest and newest, widen later.

**The Java 11 and macOS cells** (top-up). Both supported builds run on Java 11, on Linux and on the macOS and Ubuntu runners ([research 28](../research/28-java-11-and-macos-java.md)), so the two `java: 11` rows are expected to pass and the minimum stays 11. Temurin 11 exists for macOS on arm64 (11.0.33+10; [research 29](../research/29-ci-facts-and-recordings.md)), so no other distribution is needed; `macos-latest` is macOS 26 on arm64, whose image also has Temurin 11.0.32 preinstalled, which `setup-java` may take before downloading, and either is fine. A comment in the matrix says so. `macos-13` no longer exists; an Intel cell is not needed for anything this design checks (`macos-15-intel` is the label if one is ever wanted). The job keeps the `JAVA_HOME` that `setup-java` sets, so the tests run the Java of the cell and not the one the macOS `/usr/bin/java` stub would pick, which is the newest registered JDK (research 28).

**Risks.** An upstream change can turn `main` red with no change of ours; that is the accepted price (roadmap, risks). The cache holds a jar; a damaged cache entry is caught and repaired for the run by step 5, and replaced for good only when someone raises the number in the key. That a cache entry cannot be overwritten under its key is confirmed by the action's own documentation ("A cache today is immutable and cannot be updated", research 29); entries idle for a week are evicted, and the repository's limit is 10 GB.

**Depends on.** T9, V7, V12, G3.

## I2 Unit job

Roadmap: "Unit job on Python 3.11 and the newest release, plus one macOS job; select Python through `uv`, dropping the separate setup step; remove Java and the jar download from the unit job once the suite no longer needs them. Add a classifier for each Python version that is tested."

**Design.** A job `unit` with the matrix: `ubuntu-latest` with Python 3.11 and the newest release; `macos-latest` with the newest release. Three jobs.

- "The newest release" is the newest stable CPython that uv can install and for which every locked dependency has a wheel. Top-up (research 29): that is **3.15** today (3.15.2 from `setup-python` and from uv's own builds with a current uv; the runner images carry 3.14 as their newest, so either way it is a download). The matrix names 3.15, and H3 makes the classifiers say 3.11 and 3.15. `setup-uv` is left on its default, the latest uv, because an older uv does not know 3.15.2. Whether the code and the locked dependencies pass on 3.15 was not tried; the first run shows it, and the risk below covers a missing wheel.
- Python is chosen with `uv sync --locked --python <version>`; the `actions/setup-python` step goes.
- **The lifeline job** (decision D51; review finding TU3). A job `lifeline`, on `ubuntu-latest` and `macos-latest`, sets up Temurin 11 (the oldest supported Java, so the agent's `--release 11` classes are checked on it), compiles the agent's source with `javac --release 11`, compares the class files with those in `tlaup/java/lifeline.jar`, and runs the lifeline tests of [20 G3](20-groundwork.md#g3-java-launcher) (a JVM ends within three seconds of its parent's SIGKILL, also with `-Xrs` among its options; a JVM started with the id of a process that is gone exits at once; the reused-id stand-in, Linux only; `tlaup repl`'s JVM under a pseudo-terminal still reads a line from stdin, for which the job installs the current rolling build from the integration job's cache, since v1.7.4 has no REPL). The unit job below stays without Java; the lifeline tests carry the `lifeline` marker ([01 T10](01-testing.md#t10-coverage-policy-and-pytest-settings)), so that it skips them and this job runs them. A required check, like the unit job (I5).
- No Java and no jar: the steps "Set up Java" and "Download tla2tools.jar" are removed in the pull request that lands the isolation and the fakes and deletes the old tests ([01 T2](01-testing.md#t2-isolation), [T4](01-testing.md#t4-fakes-at-the-edges), decision D62).
- **The one old command CI runs** (D62's exception, [00](00-overview.md#what-every-package-must-respect)). D62's exception arises once: today's `tools install` step, which goes in 03b. Today's `test` job runs `uv run tlaup tools install`, which downloads a jar and starts Java on it to read its version, before the old tests; it is the only place a CI job runs real TLC through a command of 0.8.x, and the pull request above, 03b, which comes before any package changes `tools install`, removes it. After 03b no job runs real TLC through an old command: the unit job uses the fakes, and the integration job (I1) arrives after `tool install`, `tool current` and `doctor` exist ([00, order of work](00-overview.md#order-of-work), item 11) and runs only those. One old name may still appear for a while: the wheel check of I4, when its package lands before the tool commands are renamed (package 29a), runs `tlaup tools dir` in place of `tlaup tool dir` until 29a renames it. It starts no Java, so D62's exception does not arise there. `release.yml` has the same install step, but it runs only on a tag, nothing is tagged between packages (D6), and L2 rewrites the workflow before 0.9.0.
- Steps: `uv run poe test` (with coverage; the threshold from the last package of milestone 2 on, [01 T10](01-testing.md#t10-coverage-policy-and-pytest-settings)), then the clean-home check: fail if any tlaup folder, or the `.tlaplus` folder the REPL writes its history to, exists under the runner's home. The integration job (I1) runs the same check; its fixture points the JVM's `user.home` and `java.io.tmpdir` at temporary folders ([01 T9](01-testing.md#t9-integration-tests)).
- The real-process scenarios (signals, a pty, a closed pipe, passthrough, completion; [01 T5](01-testing.md#t5-feature-files-and-steps)) run here too, on both systems.

A job `lint`: `uv run poe lint` and `uv run ruff format --check .` on one Python.

**Risks.** The newest CPython may lack a wheel for one dependency for some weeks after its release; then the matrix names the one before and a comment says why.

(Stage 4 review, 2026-11-24: the lifeline job's list holds G3's `-Xrs` case and the REPL on a pseudo-terminal, index "Clerical"; the old command CI runs until the old tests go, D62; that exception in one wording, finding E12; the wheel check's `tools dir` until 29a, and no threshold before the end of milestone 2, findings H9 and E8.)

## I3 Newest dependencies job

Roadmap: "One job that installs the newest dependency versions the ranges allow, since users get those and CI tests only the lock file."

**Design.** A job `deps-newest`: `uv sync --upgrade` (which resolves again without honouring the lock file, in the runner's working copy only), then `uv run poe test`. The lock file is not committed back. It runs on pushes, pull requests and the weekly schedule; the scheduled run is the one that notices a new release of a dependency that breaks us.

It is **not** a required check: a breaking release of a dependency should not block an unrelated pull request. It is the one job that may be red on `main`, and a red run is fixed by a cap with a comment or by adapting the code.

**Rejected.** A lowest-versions job as well: useful, not asked for, and the minimums are fixed by hand in B2.

## I4 Build check

Roadmap: "Build check on every push: build, `twine check`, install the wheel and run `tlaup --version`, so a packaging break is not first seen at release."

**Design.** A job `build`: `uv build`; `uv run twine check dist/*.whl dist/*.tar.gz`; then in a fresh environment with nothing else installed, `uv venv /tmp/wheel-test && uv pip install --python /tmp/wheel-test dist/*.whl`, and run from it `tlaup --version`, `tlaup --help`, `tlaup tool dir`, and `python -c "import tlaup_parse"`. A script, `scripts/check_wheel.py`, asserts the wheel's file list: both import packages, `tlaup/resources/default_config.yaml`, `tlaup/java/lifeline.jar` (D51; a wheel without it would stop every Java start, review finding TU3), both `py.typed` files, no `tests/`, no `build/lib` leftovers. The jar is checked in ([20 G3](20-groundwork.md#g3-java-launcher), "The jar"), and the lifeline job of I2 compares it with its source, so this job needs no Java. (Stage 4 review, 2026-11-24: the checked-in jar recorded, finding F7.)

The same commands are the `poe check-release` task, so the release workflow and CI run one definition.

**Tests.** The job is the test.

## I5 Workflow hygiene

Roadmap: "Enforce `ruff format --check`; `uv sync --locked`; an explicit read-only `permissions` block, `timeout-minutes` and a concurrency group in each workflow; `shellcheck` on the release script."

**Design.**

- **Format first.** One commit, `style: apply ruff format`, formats the whole tree and nothing else, before any other work package branches off ([00, order of work](00-overview.md#order-of-work)). The locked ruff (0.17.5) also formats the Python code blocks in Markdown files, so the commit rewrites those blocks in the design documents and the package files too, and that is allowed: the blocks are code, and one format for all code is the point. From then on `ruff format --check .` runs in the `lint` job and as a pre-commit hook (H1), and both cover Markdown. [`docs/contributing/development.md`](../contributing/development.md) loses its section saying that formatting is not enforced. The commit's hash goes into `.git-blame-ignore-revs`.
- Every `uv sync` in a workflow has `--locked`.
- Every workflow starts with `permissions: contents: read`; a job that needs more says so itself (L2).
- Every job has `timeout-minutes` (10 for lint and build, 15 for unit, 30 for integration).
- `concurrency: group: ${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true` for every ref but `main` (every pushed branch since I9) and false for `main` (the weekly run and runs started by hand).
- `shellcheck scripts/*.sh` in the `lint` job (it is on the hosted Linux runners). Removed 2026-11-27 with the release script (L8): no shell script is left.
- A final job `Test` that `needs` every required job (`lint`, `unit`, `lifeline`, `integration`, `build`, and since L8 `release-check`; not `deps-newest`, I3). It has `if: always()`, and its one step fails unless every entry of `needs.*.result` is `success`. Both parts matter: without `if: always()` the job is skipped when a job it needs fails, and a required check that was skipped counts as passed, so a failing matrix would let a pull request merge. The ruleset (I7) requires only this one check name, so the matrix can change without touching the ruleset. Stated from knowledge of the platform, not tried; I7's hand-over to the maintainer includes opening a pull request with a deliberately failing test and seeing that it cannot merge.

(Stage 4 review, 2026-11-24: the format commit and the checks cover the code blocks in Markdown, question Q1; the lifeline job is among the required jobs; index, "Clerical".)

## I6 Pre-commit in CI

Roadmap: "Run the pre-commit hooks in CI, without the test hook, so the secret, YAML, TOML and large-file checks do not depend on a local install."

**Design.** In the `lint` job: `uv run pre-commit run --all-files`. Since 2026-11-27 there is no test hook (H1), so no stage or skip list is needed to leave the suite out. The `no-*` hooks against personal and machine data run here too, which is the point: they hold for every contributor and agent.

## I7 Ruleset on main

Roadmap: "Ruleset on `main`: changes arrive by pull request with the Test check passing; the maintainer can bypass (decision D21). Set once the check names are stable."

**Design.** A maintainer action, done once I5's `Test` job exists. The ruleset: target the default branch; require a pull request (no approvals required, since review by a separate agent stays a convention), with squash as the only allowed merge method; require the status check `Test`; block force pushes and deletion (already so); bypass list: empty. The maintainer's change of 2026-11-27, with the branch flow of I9, replaces the admin bypass the first version had (decision D21 named one): every change, the maintainer's and the release commits included, now reaches `main` through a pull request. Since L8 (2026-11-27) a release is a pull request too, and its tag is created by the release workflow after the upload. The required check `Test` is tied to the GitHub Actions app (`integration_id` 15368), so no other app can report a check of that name. The design gives the settings; the worker writes them as `gh api` commands in the pull request description for the maintainer to run, and does not run them. Before relying on it the maintainer checks it once: a pull request with one failing unit test must show `Test` as failed and be blocked (I5).

**Maintainer actions** (since 2026-11-27; the flow of I9 does not work without them):

1. The ruleset above.
2. Repository settings, pull requests: allow squash merging only, with merge commits and rebase merging off; the squash commit's default message is the pull request's title and description (`squash_merge_commit_title: PR_TITLE`, `squash_merge_commit_message: PR_BODY`); "Automatically delete head branches" off, since I9's archive renames the branch after the merge and finds nothing to rename if GitHub deleted it.
3. Actions settings, workflow permissions: read repository contents by default (each workflow asks for more itself), and "Allow GitHub Actions to create and approve pull requests" on, without which I9's draft pull request cannot be opened.

**Depends on.** I5.

## I8 Lint rules

Roadmap: "Lint rules: enable ruff's blind-except, naive-datetime and print rule groups (BLE, DTZ, T20) and fix what they flag, including the two `except Exception: pass`; review the global `PLW1510` ignore and the bandit skips B404, B603 and B607; replace the `Any` escape hatches in the formatter and models."

**Design.**

| Change | How |
| --- | --- |
| `BLE` | On. The two `except Exception: pass` are in `_show_diagnostic_info` (deleted, O2) and `modules/list.py` (becomes `except (OSError, ValueError)` reading `module.json`). Two blind excepts are allowed, each with `noqa: BLE001` and a comment: the last branch of `TlaupGroup.invoke` ([14 F10](14-config-and-cli.md#f10-no-tracebacks)), and the guard round each completer, which returns nothing whatever went wrong so that completion never prints an error into the user's prompt ([23 C3](23-command-layout.md#c3-completion)). |
| `DTZ` | On. `datetime.now()` in `modules/add.py` becomes UTC ([13 M2](13-modules-and-java.md#m2-build-in-a-temporary-folder)); the parser's `strptime` calls go because times are kept as text ([10 P3](10-parser.md#p3-result-model)). |
| `T20` | On for the whole tree. All printing in `src/` goes through `tlaup.ui` ([14 F6](14-config-and-cli.md#f6-messages)); `scripts/` and `tests/fakes/`, which print by design, are exempt per file. |
| `TID251` | On for `tests/`: bans `unittest.mock.patch` ([01 T12](01-testing.md#t12-rules-for-writing-tests)). |
| `PLW1510` (subprocess without `check`) | The global ignore is removed. After the launcher there are four `subprocess.run` calls (Java version, `javac`, `git`, the editor); each states `check=` explicitly. |
| bandit `B404`, `B603`, `B607` | `B404` (importing subprocess) and `B603` (subprocess without a shell) stay skipped globally: starting processes from argument lists is what the tool does, and the roadmap's "Keep" list requires exactly that form. `B607` (a partial executable path) is no longer skipped: every executable is an absolute path, from `locate` for `java` and `javac` (J2) and from `shutil.which` for `git` and the editor (D15, [00](00-overview.md#what-every-package-must-respect)). |
| `Any` in formatter and models | Gone with the rewrite: the model is typed ([10 P3](10-parser.md#p3-result-model)) and the reporter takes it. `sany_errors: list[Any]` becomes `list[Diagnostic]`. |
| Complexity `noqa` on three functions | Each of the three (`tlc`, `run_tlc`, `add_module`) is replaced by smaller functions; the markers are removed, not carried over. |
| mypy on tests | Stays off for `tests/` in this wave (roadmap, milestone 5 housekeeping); `tests/fakes/` and `scripts/` are checked. |

Each rule group is switched on in the pull request that fixes what it flags, not in one sweep, so no pull request carries unrelated fixes: one pull request for each row of the table that switches something on. (Stage 4 review, 2026-11-24: the completers' guard is the second allowed blind except; `git` and the editor are found with `shutil.which`; one pull request per rule group, review finding D15 (not decision D15); index, "Clerical" and "Readings to confirm".)

## I9 Branch flow

Not a roadmap item: the maintainer's change of 2026-11-27. It replaces the trunk-only flow of decision D2 for changes; the `v*` tags stay as they are. It needs the maintainer actions of I7.

**Design.**

- **Work happens on short-lived branches**, and incomplete work may be pushed. Every push to a branch other than `main` and `archive/**` runs `test.yml` (I1). A new branch is cut from `main`, after the last merge.
- **A draft pull request is opened automatically.** `.github/workflows/pull-request.yml`, on a push to a branch other than `main`, `archive/**`, `pkg/**` (stage 5's package branches, which merge into the stage's build branch) `dependabot/**` (Dependabot opens its own) and, since L8, `release/**` (the release script opens its own), opens a draft pull request to `main` when the branch has none open, has no pull request that was closed without merging (so closing a draft stops the drafts for that branch), and has commits `main` lacks. It is idempotent, and one run per branch at a time. Its title is the subject of the branch's first commit, its text says it was opened automatically and that the author writes the description before merging. The workflow holds `contents: read`; its job adds `pull-requests: write`. It checks nothing out and calls only the GitHub API through `gh`. The push run reports `Test` on the pull request's head commit; the required check matches by commit, which is enough.
- **Squash merge, the description as the message.** When the work is done and `Test` is green, the author writes the pull request's title (a Conventional Commits subject) and description, marks it ready, and squash-merges it. The repository's squash default (I7) takes the commit message from the pull request's title and description, so the description is what `main`'s history keeps.
- **The branch is archived.** `.github/workflows/archive-branch.yml`, on a pull request closed as merged into `main` from a branch of this repository, renames the branch to `archive/<name>` through the REST API. If that rename fails (the name is taken, for a branch name used twice), it retries once with the flat name `archive/pr<number>-<name with each / replaced by ->`. A branch that no longer exists ends the job with a message and success. Dependabot's branches (`dependabot/**`) are not archived: Dependabot deletes its own branch after the merge, and at the first two Dependabot merges the rename raced that deletion, once losing and once leaving an archived copy (changed 2026-11-27). The workflow holds `contents: read`; its job adds `contents: write`. GitHub keeps a pull request's commits even when the branch goes, so the archive is a convenience for bisecting the steps a squash folded together. Pushes to `archive/**` run nothing.
- **One run per push, none for `main` or a pull request** (changed 2026-11-27, after the first merge). `test.yml` has no `pull_request` trigger and no push trigger for `main`. The first version had both, and accepted that a push to a branch with a pull request ran twice. The first merge showed two more costs. A `pull_request` run for a pull request the workflow's bot opened is not skipped, as the first version assumed, but held as "action required" until the maintainer approves it. And the push of the squash commit to `main` ran the whole suite again on a tree already tested. Neither run is needed: the ruleset requires the branch to be up to date with `main` before it merges, so the push run has tested the tree the squash commit gets. The price: a pull request from a fork gets no CI run, since its branch is not pushed here. The maintainer pushes such a branch to this repository to test it. A merge of the run's result with a newer `main` is not tested separately either; the up-to-date rule makes that the same tree.
- **Cancelled runs show red.** A newer push to a branch cancels the older run (I5). Its `Test` job still runs, because of `if: always()`, and fails on the cancelled jobs, so the superseded commit shows a red `Test`. That is harmless: the required check reads the pull request's head commit. `if: always()` stays, since without it a failing job would leave `Test` skipped, which counts as passed.

**Seen at the first merge** (pull request #4, 2026-11-27):

- The draft pull request opened with the workflow's token, and the push run's `Test` satisfied the ruleset.
- A `pull_request` run for the bot's pull request was held as "action required" until approved; that is why the trigger was dropped (above).
- The squash default (`PR_TITLE`, `PR_BODY`) put the title and description into the commit on `main`. GitHub wraps the message body at 72 characters, so a description wrapped wider comes out ragged; write each paragraph and list item as one line. The commit's author is the pull request's author, here `github-actions[bot]`, with the maintainer as a `Co-authored-by` trailer.
- The rename to `archive/build/stage-5` worked through the REST API, and the renamed branch started no `test.yml` run.

**Not yet seen.** Whether a failed `Test` on the head commit blocks the merge as the ruleset says (I5's deliberately failing pull request, still to do).

## L1 Release script

**Replaced 2026-11-27 by L8**, before any release used it: the script is removed. `scripts/changelog_section.py` stays, used by L8's release check and by L2 and L3. What follows is the first design, kept for its reasons.

Roadmap: "Harden `scripts/release.sh`: on `main`, clean tree, `HEAD` equal to `origin/main` after a fetch, the tag absent both locally and on the remote, CI green for `HEAD`, lock file version equal to the project version, a proper `## [X.Y.Z] - date` changelog heading with nothing left under Unreleased, an annotated tag (decision D21), an atomic push, and the local tag removed if the push fails. Read the version robustly."

**Design.** The script stays a shell script, checked by shellcheck, and does these in order, stopping at the first failure with a message that says what to do:

1. `VERSION=$(uv version --short)`; `TAG=v$VERSION`.
2. Branch is `main`; `git status --porcelain` is empty.
3. `git fetch origin main --tags`; `HEAD` equals `origin/main`.
4. `refs/tags/$TAG` exists neither locally nor in `git ls-remote --tags origin`.
5. The `tlaup` entry in `uv.lock` has version `$VERSION` (`uv lock --check` passes and the version line matches).
6. `scripts/changelog_section.py "$VERSION"` succeeds: it prints the section under the heading `## [X.Y.Z] - YYYY-MM-DD` and fails if that heading is missing or malformed, if the section is empty, or if a `## [Unreleased]` section still has entries.
7. CI is green for `HEAD`'s tree: a check run `Test` of GitHub Actions completed with success, read with `gh api repos/{owner}/{repo}/commits/$SHA/check-runs`. A push to `main` starts no run (I9), so the check is read on `HEAD` itself when it has one (the weekly run, or one started by hand). Otherwise `HEAD` must be the squash merge of exactly one pull request into `main` (`commits/$SHA/pulls`), whose head commit has `HEAD`'s tree, and the check is read on that head. On either commit the newest `Test` counts, so a run by hand or a re-run replaces a failed one. A `test.yml` run still going on `HEAD` stops the script with "wait": its `Test` check appears only when the other jobs end, so it would otherwise go unseen. Anything else stops the script with the command that starts a run on `main` by hand. `origin` must be on github.com: an https, `git@` or `ssh://` address, or an SSH host alias whose host `ssh -G` resolves to github.com; the owner and name are the last two parts of the address. If `gh` is missing or not logged in, the script stops and says so; it does not skip the check. (Changed 2026-11-27 with I9's triggers; the first version read `Test` on `HEAD` only.)
8. `uv run poe check-release` (I4's commands).
9. `git tag -a "$TAG" -m "tlaup $VERSION"`.
10. `git push --atomic origin main "$TAG"`; on failure, `git tag -d "$TAG"` and stop.

`scripts/changelog_section.py` is plain Python with no dependencies and has unit tests on a sample changelog (a good heading, a missing one, a wrong date, entries left under Unreleased). It is used by step 6 and by L2 and L3.

**Tests.** shellcheck; the unit tests of the changelog script; a dry-run mode (`--check`) that performs steps 1 to 8 and stops, run by hand before the first release.

**Risks.** The script cannot be exercised end to end without making a release; step by step it is checked by `--check`.

## L2 Release workflow

**Changed 2026-11-27 by L8**: the workflow runs on every push to `main` instead of a pushed tag, a first job decides whether the commit is a release, and the last job creates the tag before the page. The jobs' permissions and pins below stay.

Roadmap: "Restructure `release.yml` into three jobs: a read-only build ..., then PyPI publish with the id-token permission only, then the release page with write access and no project code. Fail if the tag does not match the project version or the commit is not on `main`. Attach only the wheel and sdist ... Set `persist-credentials: false` on checkout. Pin the actions that hold write access by SHA, or replace the third-party release action with `gh release create`."

**Design.** Trigger: push of a `v*` tag. Workflow-level `permissions: contents: read`.

| Job | Permissions | Does |
| --- | --- | --- |
| `build` | `contents: read` | Checkout with `persist-credentials: false` and full history. No Java: the lifeline jar is checked in (G3), and the lifeline job of I2 has compared it with its source on every push. Fail unless `v$(uv version --short)` equals the tag and `git merge-base --is-ancestor $GITHUB_SHA origin/main`. `uv sync --locked`; lint; unit tests; `uv build`; `twine check`; the wheel check of I4. Write the changelog section to `release-notes.md` with `scripts/changelog_section.py`. Upload two artifacts: `dist` (exactly the `.whl` and the `.tar.gz`) and `release-notes`. |
| `publish` | `id-token: write` only; environment `pypi` | Needs `build`. Download `dist` with `actions/download-artifact`, pinned by commit hash; publish with the PyPA publish action, pinned by commit hash. No checkout, no project code (roadmap, "Keep"). Waits for the maintainer's approval (L5). |
| `release-page` | `contents: write` | Needs `publish`. Download both artifacts with `actions/download-artifact`, pinned by commit hash; then `gh release create "$TAG" dist/*.whl dist/*.tar.gz --title "tlaup $VERSION" --notes-file release-notes.md --verify-tag`, with `GH_TOKEN: ${{ github.token }}` and `GH_REPO: ${{ github.repository }}` in the step's environment, because there is no checkout for `gh` to read the repository from. No checkout, no project code. |

The stray `default.gitignore` on the 0.8.2 page came from `files: dist/*`; naming the two patterns fixes it. The order publish-then-page means a page never announces a version that is not on PyPI.

**Every action in a job that holds a sensitive permission is pinned by full commit hash**, with the version in a comment, and Dependabot (B1) proposes updates. That is two actions: the PyPA publish action in `publish`, and `actions/download-artifact` in both `publish` (`id-token: write`) and `release-page` (`contents: write`). The first version of this design pinned only the publish action and called `release-page` free of actions, which it is not; the roadmap item says "pin the actions that hold write access by SHA" and makes no exception for GitHub's own. The `softprops` release action is dropped in favour of `gh`, which is already on the runner. Top-up (2026-11-20): **every action in every workflow is pinned by full commit hash** with its release in a comment, not only those in the two sensitive jobs, because the investigating agent and the reviewer both recommend it and Dependabot (B1) moves the pins as it moves tags; the first wording kept version tags in the read-only `build` job. The commits research 29 found on 2026-11-19, to be looked up again on the day: `pypa/gh-action-pypi-publish` `7245906fb61fa33a13554f9d5fb856fe61758086` (v1.14.3; `release/v1`, which the workflow names today, is a branch and can move, so this pin is the largest gain), `actions/download-artifact` `9000827ccba6bdab643e8b6fd33ac0654aef8333` (v8.0.2), `actions/upload-artifact` `cf430e030ddbb5b0abf93d22962f4752f3646cd9` (v7.0.2), `actions/checkout` `3d3c42e5aac5ba805825da76410c181273ba90b1` (v7.0.1), `actions/setup-java` `d1374f8ac74474200d16ef8ecee22c7ae7a51880` (v6.3.0), `actions/setup-python` `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` (v7.1.0, if a workflow still uses it), `astral-sh/setup-uv` `68559e99cc807c1eb7e9238fd43a15bba460eec2` (v10.3.3; it has no major tag), `actions/cache` `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` (v6.1.0). Every one is several majors ahead of today's workflows.

**Tests.** The `build` job's checks are the same commands as `poe check-release`, which run on every push (I4). The tag and ancestry checks are tried once on a throwaway tag in a fork or with `act`; if neither is practical, the first real release is the test and the maintainer watches it. (Stage 4 review, 2026-11-24: the `build` job's row keeps only the checked-in lifeline jar, finding F7.)

## L3 Release pages

Roadmap: "Release pages: each page gets that version's changelog section as its text; backfill the existing pages from the changelog ...; PyPI's changelog link points at the GitHub releases page."

**Design.** New pages: L2. `project.urls.Changelog` in `pyproject.toml` becomes the releases page address. Backfill: a maintainer action after 0.9.0, as `gh release edit vX.Y.Z --notes-file <(scripts/changelog_section.py X.Y.Z)` for each tag that has a page; which tags have pages in this repository was not checked (the roadmap notes probably only 0.8.2). Whether older tags get pages is the maintainer's decision at that point, as the roadmap says.

## L4 Version bump task

Roadmap: "A `poe` task around `uv version --bump`, so `pyproject.toml` and `uv.lock` move together."

**Design.** `poe bump` takes `patch`, `minor` or `major`, runs `uv version --bump <part>` (which updates the lock file too) and prints the new version and the next step ("rename `## [Unreleased]` in CHANGELOG.md to `## [X.Y.Z] - <today>`"). It does not edit the changelog or commit. [`docs/contributing/releasing.md`](../contributing/releasing.md) is updated to name the task.

## L5 PyPI environment

Roadmap: "`pypi` environment: add the maintainer as required reviewer and switch off admin bypass (decision D21)."

A maintainer action in the repository settings: environment `pypi`, required reviewers: the maintainer; "allow administrators to bypass" off; deployment branches and tags: `v*` (in place). Since L8 (2026-11-27) the deployment rule is the branch `main` instead, since the upload now runs before the tag exists, and there is no required reviewer: the release script's confirmation and the merge are the go-ahead. Nothing to build. Its record is this milestone 2 item, which is ticked when the maintainer has done it.

## L6 Lock refresh before a release

Roadmap: "Before each release, refresh the lock file and let CI run before tagging."

A step of the release procedure, written into [`docs/contributing/releasing.md`](../contributing/releasing.md): `uv lock --upgrade`, commit, push, wait for green, then L1. Since L8 (2026-11-27) it is a question of the release script, yes by default. The weekly `deps-newest` run (I3) means the refresh is rarely a surprise.

## L7 Version rule

Roadmap: "Follow the version rule of decision D27 from 0.9.0 on." Already in the [conventions](../contributing/conventions.md#compatibility-and-versions). `poe bump` (L4) makes the choice explicit each time; nothing else to build.

## L8 Release by pull request

Not a roadmap item: the maintainer's change of 2026-11-27, made before the first release, so 0.9.0 is the first release made this way. It replaces the release script of L1 and changes L2's trigger, L5's environment rule and L6's lock refresh. It keeps L2's jobs and permissions, L3's pages, L4's bump and L7's rule.

**Why.** A `v*` tag cannot be moved or deleted (L5), and with L1 the tag came first: a release that failed after the tag needed a new version number. The upload to PyPI is the step that cannot be undone, since PyPI never takes a version number twice, even after a deletion. So everything that can fail runs before the upload, in a pull request where a fix is one more push, and the tag is made only after the upload succeeded. Each `v*` tag then names exactly the commit whose build is on PyPI. The maintainer starts a release with one command and one confirmation; the rest runs by itself.

**What makes a release.** A commit on `main` whose project version has no `v*` tag. Every merge into `main` runs the release workflow, and its first job decides. Normally the version is already tagged and the workflow ends there. A pull request that changes the version is therefore a release pull request, however it was made; `uv run poe release` is the usual way to make one.

**The release script.** `scripts/release.py`, run as `uv run poe release` on the maintainer's machine, with git, uv and a logged-in gh:

1. It checks the starting point: on `main`, a clean tree, `HEAD` equal to `origin/main` after a fetch, gh logged in, no open pull request from a `release/` branch, and entries under `## [Unreleased]`.
2. It shows the version and asks which part to bump, naming what each part gives, then whether to refresh `uv.lock` (default yes, L6).
3. On a new branch `release/vX.Y.Z` (refused if it exists on GitHub), `scripts/prepare_release.py <part>` runs `uv version --bump <part>`, which moves `pyproject.toml` and `uv.lock` together (L4), and renames `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - <today, UTC>` with an empty `## [Unreleased]` above it. With the refresh, `uv lock --upgrade`. Then the release check (below) must pass.
4. It shows the changelog section and the changed files, and asks to go ahead (default no). A no, Ctrl-D, a failure or Ctrl-C up to the push puts `main` back as it was and deletes the local branch it made; nothing has been pushed. If files were edited while the question waited, it undoes nothing and says so, and a yes is refused, since the release check did not see those edits. After the push, a failure says what is left on GitHub and how to finish or remove it.
5. It commits `chore(release): X.Y.Z`, pushes the branch with the maintainer's own login, opens the pull request with that title and a text that says what merging does followed by the changelog section, and turns on auto-merge (squash), naming the squash commit's subject (`chore(release): X.Y.Z (#N)`) and message (the pull request's text) so they do not rest on the repository's defaults. The push is an ordinary push, so it runs `test.yml` and reports `Test` on the head commit, as the ruleset requires (I7). A push made with a workflow's own token would start no workflow, and a run started by `workflow_dispatch` does not count as a pull request's required check, which is why the release starts on the maintainer's machine and not from the Actions tab.
6. GitHub squash-merges the pull request once `Test` is green; the text becomes the commit's message on `main`. The script follows the pull request and then the release run, and prints the PyPI page or what failed. Stopping it stops only the following.

A fix in the release pull request is an ordinary push to its branch. When `main` moves on, the up-to-date rule holds the auto-merge until the branch is updated (I9).

**No approval before the upload.** The `pypi` environment keeps its name, which PyPI's trusted publisher names, but has no required reviewer; it deploys only from `main`. The maintainer's go-ahead is the confirmation in step 4, and the merge needs a green `Test`. The cost: any merge that leaves `main` with an untagged version publishes it at once, a merge by an agent with the maintainer's login included. The approval did not stop such an agent either, since the same login can approve a deployment; what stops it is the ruleset on `main` and the rule that agents never release ([AGENTS.md](../../AGENTS.md)).

**The release check.** `scripts/release_check.py`, standard library only, reads the version from `pyproject.toml`, the `tlaup` version from `uv.lock`, the `v*` tags (the output of `git ls-remote --tags --refs origin`) and PyPI's JSON API. When the version is tagged, the commit is not a release and the check passes without asking PyPI. Otherwise the commit is a release candidate, and the check fails unless all of these hold:

- the version is higher than every `v*` tag;
- `uv.lock` has the same version;
- `CHANGELOG.md` has a dated section for it and nothing under Unreleased (`scripts/changelog_section.py`, L1);
- PyPI has no such version (a 404 from `https://pypi.org/pypi/tlaup/X.Y.Z/json`; any other answer but 200 is an error, not a pass).

It runs in three places: in the release script before the push; as a job `release-check` in `test.yml`, needed by `Test`, so a release pull request cannot merge while it fails; and as the first job of the release workflow. In the release workflow, a version that is untagged but already on PyPI means an earlier run uploaded and then failed to tag. The check then fails and says to re-run the failed jobs of that earlier run.

**The release workflow.** `.github/workflows/release.yml` keeps its file name and the `pypi` environment. Triggers: every push to `main`, and `workflow_dispatch` on `main`, to try again after a failure. `concurrency` keeps one run at a time and cancels none. Jobs:

| Job | Permissions | Does |
| --- | --- | --- |
| `check` | `contents: read` | The release check. Its outputs say whether this commit is a release, and which version. When it is not, the run ends here, green. |
| `build` | `contents: read` | Needs `check`, and runs only for a release. As in L2, without the tag and ancestry checks, since the commit is `main`'s: lint, unit tests, `poe check-release`, the changelog section to `release-notes.md`, the two artifacts. |
| `publish` | `id-token: write`; environment `pypi` | As in L2, without the wait for approval, and with `skip-existing`: a re-run after an upload that stopped half way sends only the files PyPI does not have yet. |
| `tag-and-page` | `contents: write` | Needs `publish`. Checks that PyPI's files for the version (`urls[].digests.sha256` in its JSON, asked again for up to three minutes, since it can lag the upload) are exactly this run's `dist` files, by SHA-256; a `publish` that skipped every file could otherwise tag a commit whose files another run uploaded. Then creates the annotated tag `vX.Y.Z` on the commit through the GitHub API (`git/tags`, then `git/refs`), with the message `tlaup X.Y.Z`, then the release page as in L2. A tag or page already there from an earlier try is kept when it names the same commit, so re-running the job is safe. No checkout, no project code. |

A failed run is retried by re-running its failed jobs, or after a fix merged into `main`, by the next push, since the version is still untagged. That has a side to it: while a release is merged but untagged, every commit on `main` is that release, so the next merge, a Dependabot one included, publishes that newer commit, and a feature branch cut meanwhile fails its `release-check`, since its Unreleased section has entries. With auto-merge and no approval that window is minutes, not hours; the release guide says to finish a release before merging other work.

**Changed elsewhere.** L1's script is removed, and with it the `shellcheck` step of the `lint` job, since no shell script is left. L5: the `pypi` environment deploys from the branch `main` instead of `v*` tags and has no required reviewer (maintainer actions). L6: the lock refresh is the release script's question, tested by the release pull request's own run. I7: the repository allows auto-merge (a maintainer action). I9: the draft pull request workflow skips `release/**`, since the script opens that pull request itself; the archive workflow archives `release/**` branches like any other, keeping any fixes pushed to them.

**Rejected.**

- Publishing from the release branch before the merge: an upload cannot be taken back, so failures after it would still burn a version, and if `main` moved on in the meantime the merged commit would no longer have the files that were published.
- Starting the release from the Actions tab: the workflow's own token can push the branch, but that push starts no workflow, and a `Test` run it starts by `workflow_dispatch` does not count as the pull request's required check. Making it work needs a push credential stored in the repository (a deploy key or a GitHub App), or an "approve and run" click on every release; the maintainer chose the local script instead.
- A TestPyPI upload from the pull request: it needs a second trusted publisher, and every retry burns a TestPyPI version too, while the wheel check of I4 already installs and runs the built wheel.

**Tests.** Unit tests of `scripts/prepare_release.py`, `scripts/release_check.py` and the questions and texts of `scripts/release.py`, on files the tests write, with PyPI replaced. The script's git and gh steps and the workflows are proven by the first release: that auto-merge squash-merges with the pull request's text as the message, that the tag is created through the API, and that publishing works from `main` under the changed environment rule.

## B1 Dependabot

Roadmap: "`.github/dependabot.yml` for the `uv` and `github-actions` ecosystems: one monthly run that groups all version updates into one pull request."

**Design** (decision D44). Two entries, `uv` and `github-actions`, each with one group matching `*`. That gives **one grouped pull request per ecosystem**, two a month at most. **They run two weeks apart** (changed 2026-11-27 by the maintainer): `uv` on the 1st of each month and `github-actions` on the 15th, both at 06:00 UTC, with `interval: cron`. The first version had `interval: monthly` for both, which runs on the 1st with no way to move it, so the two pull requests opened together. Under I7's up-to-date rule, merging one then sent the other back for a fresh run. The schedules use dates only, because cron fires when either a date or a weekday matches, so "the first Monday" cannot be said. 06:00 is after the weekly `Test` run on Mondays at 04:17. The roadmap item says "one pull request"; the maintainer chose one per ecosystem on 2026-11-15, because grouping within an ecosystem is the long-standing form, and the README lists it as a departure. Whether Dependabot can now group across ecosystems was not checked and no longer needs to be. Security updates stay as they are (on since 2026-11-14).

**Tests.** None; the file is checked by the YAML hook, and the first run of each schedule shows whether the cron schedule and the groups work.

## B2 Build fixes

Roadmap: "`setuptools>=77.0.3`, which the SPDX licence string needs; a real Pydantic minimum instead of the locked version; remove the `rich<14` cap; raise the `pre-commit<4` cap; delete the redundant `MANIFEST.in`."

| Change | Note |
| --- | --- |
| `requires = ["setuptools>=77.0.3"]` | As the roadmap says. |
| `pydantic>=2.12.5,<3.0.0` becomes the oldest 2.x the code works with, with no upper cap | `pydantic>=2.5.3` (top-up, D59, settled by the maintainer 2026-11-20; uncapped, settled 2026-11-21, see "Upper caps" below). Research 30 found a model shaped like F1 and F3 working on every Pydantic from 2.0 to 2.14.3 on Python 3.11, and the present unit tests passing with 2.8.0 on 3.13; installable wheels set a practical floor per Python (2.8 on 3.13, 2.12 on 3.14), which the installer picks by itself. 2.5.3 is the floor Typer 0.29 and later declare, so the bound never allows less than the locked Typer needs. No lowest-versions job is added for it (I3 stays rejected); the evidence for the floor is research 30. |
| `rich>=13.7.0,<14` becomes `rich>=13.8.0`, with no upper cap (top-up, D59) | `Console.on_broken_pipe`, which the 141 rests on, exists from 13.8.0, and Typer 0.25 and later require 13.8.0 too. The design leans on three things Rich does: the live display on the alternate screen ([22 O4](22-reporters.md#o4-live-display)), what a console does on a closed pipe, and what Typer's own console does there ([14 F10](14-config-and-cli.md#f10-no-tracebacks)). Research 30 tried all three on 13.8.0, 13.9.4, 14.0.0, 14.3.4 and 15.0.0 on Linux, and on all but 14.0.0 on macOS and, for the pipe cases, Windows (review finding TU8), and every version behaved the same, so the cap the roadmap asks to remove goes. The reporter's expected files (O6), the closed-pipe scenarios ([02 X1](02-cross-cutting.md#x1-exit-codes)) and the `deps-newest` job (I3) guard a later change. |
| `pre-commit>=3.5.0,<4` becomes `<5` | Development only. |
| `typer>=0.22.0,<1.0.0` becomes `typer>=0.27.2,<1.0.0` (top-up, D59) | Not in the roadmap item; added by the stage 3 review. The error handler and the `completion` command rest on Typer behaviour, including two private modules ([14 F10](14-config-and-cli.md#f10-no-tracebacks), [23 C3](23-command-layout.md#c3-completion)). Research 23 ran it on thirteen versions from 0.22.0 to 0.29.2: 0.27.2 is the first with a public `typer.TyperException`, which F10 names, and from there every version behaved as 0.29.1; before 0.26.0 Typer depends on a separate Click. A lower floor buys nothing for a command-line tool installed into its own environment and would double what has to be tested. The upper bound stays, and the newest-dependencies job (I3) tests each new release. |
| `MANIFEST.in` deleted | The wheel check (I4) asserts the packaged files are unchanged before and after. |
| `filelock>=4.2.1` added, with no upper cap (top-up, D59; uncapped, settled 2026-11-21, see "Upper caps" below) | New runtime dependency, for the store lock ([12 V11](12-tools-and-downloads.md#v11-concurrent-installs)), the visits of the run-folder sweep and `cache clean`, and `lock_descriptor` under the run's own lock ([11 R6](11-runner.md#r6-run-folders)). Research 30 tried every release on Linux and eight on macOS and Windows: the second look (a lock that notices its file was unlinked between opening and locking) arrived in 3.20.4, but 3.20.4 to 3.29.4 also delete the lock file by name on release, which breaks mutual exclusion in a new way, and 3.29.5 to 4.2.0 change the lock file's modification time when locking, which the one-hour rule reads. 4.2.1 is the first version where all of it holds, on all three systems; `lock_descriptor` exists from 3.30.0. The specs check the reason as a variant (`RunFolders-unlink-on-release`), and R6's unit tests pin each behaviour so that a later release that changes one fails on the newest-dependencies job. |
| Development dependencies of [00](00-overview.md#new-and-removed-dependencies) (top-up) | From research 30, which ran each as the test design uses it: `pytest-bdd>=9.0.1,<10` (the only version that runs on the locked pytest 9.2; it reaches into pytest's private fixture manager, so I3 is what catches the next break); `coverage>=7.10.6` (the subprocess patch works from 7.10; pytest-cov 7.1.0 needs 7.10.6); `responses>=0.23.3,<1`; `pytest-socket>=0.8.1,<1`; `pyte>=0.8.2,<1`. |

**Upper caps** (settled by the maintainer 2026-11-21, review finding TU8). Research 30 proposed `filelock<5` and `pydantic<3`; neither is taken, and the runtime dependencies tlaup relies on through their public interface get no cap below their next major version. Three reasons. First, a cap is published with every release and cannot be lifted afterwards: when a new major version turns out to work, every tlaup already released still refuses it, while a major version that breaks tlaup is answered by one new release that adds the cap, which is the rule I3 already states ("a red run is fixed by a cap with a comment"). Second, the guard is in place: the weekly `deps-newest` job (I3) installs the newest versions the ranges allow, and for `filelock` R6's unit tests pin each behaviour the design rests on (the second look, no unlink on release, the lock file's modification time, `lock_descriptor`), so a release that changes one turns the job red before most users upgrade; for `pydantic` the unit tests of the settings model (F1, F3) do the same. Third, `filelock` and `pydantic` are among the most widely shared Python libraries, and a cap on them is what makes a tool impossible to install beside others in one environment or to package for a distribution (the roadmap's nixpkgs and conda-forge item names "the dependency caps"), which is the cost `rich<14` showed. Rich's cap went for the same reasons. `typer<1.0.0` stays: Typer is still at 0.x, where a minor release may break, and tlaup reaches into two of its private modules ([14 F10](14-config-and-cli.md#f10-no-tracebacks), [23 C3](23-command-layout.md#c3-completion)). The caps on `requests` and `platformdirs` are outside this item and stay as they are. The development dependencies keep the caps listed above: they never reach users, and a break there blocks only CI.

## B3 Package metadata

Roadmap: "PyPI and GitHub metadata: keywords; the missing classifiers ...; replace the 'Build Tools' topic; Linux and macOS instead of 'OS Independent' (decision D15); GitHub topics; absolute links in the README; `pipx` and `uvx` install options."

**Design.** In `pyproject.toml`:

- `keywords = ["tla+", "tlaplus", "tlc", "model-checking", "formal-methods", "sany", "pluscal"]`.
- Classifiers added: `Environment :: Console`; `Intended Audience :: Developers`; `Intended Audience :: Science/Research`; `Topic :: Scientific/Engineering`; `Topic :: Software Development :: Quality Assurance`; `Typing :: Typed`; `Operating System :: POSIX :: Linux`; `Operating System :: MacOS`; one `Programming Language :: Python :: 3.x` per tested version (H3). Removed: `Operating System :: OS Independent`; `Topic :: Software Development :: Build Tools`.
- `description`: one sentence shared with the root help ([14 F7](14-config-and-cli.md#f7-help-text)).

Two points of this item are about the README, and they are done here, in this item's pull request, not handed to the documentation track's README rewrite, whose text names neither:

- every relative link in `README.md` becomes an absolute `https://github.com/...` address, because PyPI renders the same file and relative links are dead there; a unit test reads `README.md` and fails on a Markdown link whose target is neither absolute nor an in-page anchor;
- the install section gains the two commands the item asks for, `pipx install tlaup` and `uvx tlaup`, beside the existing ones.

The rewrite, when it comes, keeps both. GitHub topics are a maintainer action (`gh repo edit --add-topic`), listed in the pull request description.

## H1 Pre-commit hooks

Roadmap: "Pre-commit: move the test hook to pre-push; add a format hook; run mypy on the whole project instead of on staged files."

**Design.** In `.pre-commit-config.yaml`: the `pytest` hook gets `stages: [pre-push]` (superseded 2026-11-27, below); a `ruff-format` hook (`uv run ruff format --check --force-exclude`) is added after `ruff`, with `types_or: [python, pyi, markdown]`, so that a staged Markdown file is checked as I5's check checks it (Stage 4 review, 2026-11-24: question Q1); the `mypy` hook gets `pass_filenames: false` and runs `uv run mypy .`. `poe install-hooks` installs both hook types (`pre-commit install --install-hooks -t pre-commit -t pre-push`). A new local hook `no-typed-tool-output` fails on `@!@!@STARTMSG` in `tests/**/*.py` and `tests/**/*.feature` ([01 T12](01-testing.md#t12-rules-for-writing-tests), rule 3).

**Changed 2026-11-27 (the maintainer, with the branch flow of I9).** Every test run moved to GitHub CI, which runs on every pushed branch. The `pytest` hook is gone and nothing runs at push: `default_stages: [pre-commit]` at the top of the file keeps every hook at commit, so a pre-push hook left from an older install runs nothing, and `poe install-hooks` installs the pre-commit type only (`pre-commit install --install-hooks -t pre-commit`). The hooks are the fast checks: ruff, ruff format, bandit, mypy, the `no-*` hooks against personal and machine data, the T12 hooks, and the file checks. Fast smoke tests at commit may come later.

## H2 Clean task and gitignore

Roadmap: "`poe clean` also removes `build` and the egg-info folder ...; add `htmlcov/`, `coverage.xml`, `.direnv/` and editor folders to `.gitignore`."

**Design.** `clean` becomes a small Python task (not `rm -rf`, so it works on Windows): removes `dist`, `build`, `src/*.egg-info`, `.coverage`, `htmlcov`, `coverage.xml`. `.gitignore` gains `htmlcov/`, `coverage.xml`, `.direnv/` and `.hypothesis/`. The editor folders the roadmap item names, `.idea/` and `.vscode/`, are in `.gitignore` already (checked in the file), so that part needs nothing.

A `.gitattributes` file holds one rule, `tests/parse/golden/** -text`, so that Git never converts the line endings of a golden file ([01 T3](01-testing.md#t3-golden-files)). Under `core.autocrlf=true`, the default of Git for Windows, a checkout would otherwise turn every `\n` into `\r\n`: the parser would still read the files, since it strips either ending, but the exact-rebuild property and the synthetic `\r\n` case rest on the bytes as captured. A rewritten file would show only as a golden test failing on that one machine; the rule keeps it from being rewritten. (Stage 4 review, 2026-11-24: index, "Clerical".)

## H3 Python versions

Roadmap: "One story for Python versions: `.python-version`, the CI matrix, the classifiers and the mypy and ruff targets agree, and every advertised version is tested."

**Design.** One rule: **the lowest supported version is the target, and the edges are tested.**

| Place | Value |
| --- | --- |
| `requires-python` | `>=3.11` |
| ruff `target-version`, mypy `python_version` | 3.11 |
| `.python-version` (what `uv` uses locally) | 3.11, so local work catches use of anything newer: syntax, which ruff's target also catches, and the standard library, which it does not (`os.process_cpu_count`, new in 3.13, is the example the stage 3 review found in this design). It is 3.13 today. |
| CI unit matrix | 3.11 and the newest (I2) |
| Classifiers | 3.11 and the newest, and no version in between unless it is added to the matrix. "Every advertised version is tested" is met by advertising the two tested edges. |

A test reads `pyproject.toml`, `.python-version` and `test.yml` and asserts they agree, so the story cannot drift.

Two consequences are choices made in this design, which the README lists: local development moves from Python 3.13 to 3.11, and the classifiers for versions between the two tested edges are removed (the file lists 3.11, 3.12 and 3.13 today; with 3.15 as the newest tested version, research 29, the classifiers become 3.11 and 3.15). `requires-python` still admits them; they are no longer advertised as tested.

**Rejected.** Testing every version from 3.11 up: four or five jobs for a pure-Python tool whose risk is at the edges.

## H4 Security policy

Roadmap: "A two-line `SECURITY.md` pointing at GitHub private vulnerability reporting."

**Design.** `SECURITY.md` at the repository root: report a vulnerability through GitHub's "Report a vulnerability" button on the repository's Security tab (private vulnerability reporting, on since 2026-11-14); only the latest release is supported. No email address (the pre-commit hook would refuse one, rightly).
