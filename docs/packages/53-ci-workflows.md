# 53. The test workflow

Size: M. Suggested model: mid-tier. Status: ready.

## Goal

`.github/workflows/test.yml` is rewritten into the jobs of [30](../design/30-ci-and-release.md): `lint` (with pre-commit and shellcheck), `unit` on three cells with Python chosen through `uv`, `lifeline` with a real Temurin 11 (a required check), `deps-newest`, `build` with the wheel check, and one final `Test` job that the ruleset on `main` can require. Every action is pinned by commit hash, every job has a timeout, the workflow is read-only, and the unit cells end with the clean-home check. The integration job is added to this workflow by [54](54-integration-job.md).

## Covers

- Roadmap items ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this)):
  - "Unit job on Python 3.11 and the newest release, plus one macOS job; select Python through `uv`, dropping the separate setup step; remove Java and the jar download from the unit job ...; add a classifier for each Python version that is tested." (line 386). In part: the job. Java and the jar download were removed by [03](03-test-foundation.md); the classifiers are [56](56-build-and-metadata.md), and the test that keeps them in step with this matrix is [57](57-repo-hygiene.md).
  - "One job that installs the newest dependency versions the ranges allow ..." (line 389). In full.
  - "Build check on every push: build, `twine check`, install the wheel and run `tlaup --version` ..." (line 390). In full.
  - "Enforce `ruff format --check`; `uv sync --locked`; an explicit read-only `permissions` block, `timeout-minutes` and a concurrency group in each workflow; `shellcheck` on the release script." (line 391). In part: everything except the format commit and its first check, which [01](01-ruff-format.md) did, and the release workflow's own block, which [55](55-release-tooling.md) writes with the rest of that file.
  - "Run the pre-commit hooks in CI, without the test hook ..." (line 392). In full, with [57](57-repo-hygiene.md) removing the temporary skip (Context).
  - "Isolation is automatic and total ..." (line 359). In part: the clean-home check on every cell of the unit matrix, macOS included, which 03 left for the matrix.
- Design sections:
  - [30 I2](../design/30-ci-and-release.md#i2-unit-job): all of it, including the lifeline job with its revised list of tests (the `-Xrs` case and the REPL under a pseudo-terminal) and the `lifeline` marker, and D62's consequence for CI (the one old command CI ran, `tlaup tools install`, went with the old tests in 03b).
  - [30 I3](../design/30-ci-and-release.md#i3-newest-dependencies-job): all of it.
  - [30 I4](../design/30-ci-and-release.md#i4-build-check): all of it, including `scripts/check_wheel.py` and the `poe check-release` task.
  - [30 I5](../design/30-ci-and-release.md#i5-workflow-hygiene): every bullet but the first ("Format first", 01), for `test.yml`, with the lifeline job among the required jobs. The same rules for `release.yml` are 55.
  - [30 I6](../design/30-ci-and-release.md#i6-pre-commit-in-ci): all of it.
  - [30 L2](../design/30-ci-and-release.md#l2-release-workflow), the paragraph on pins: "every action in every workflow is pinned by full commit hash", for this workflow.
  - [01 T2](../design/01-testing.md#t2-isolation), "Proof that it holds": the CI part, on every unit cell.
  - [20 G3](../design/20-groundwork.md#g3-java-launcher), "The lifeline, with a real JVM": the CI job that runs [06](06-lifeline-agent.md)'s tests.

## Depends on

- [01](01-ruff-format.md): the format check step in `test.yml`, which moves into the `lint` job.
- [03](03-test-foundation.md): `uv run poe test` with coverage (no `fail_under` until [59](59-closing.md), [01 T10](../design/01-testing.md#t10-coverage-policy-and-pytest-settings)); the `lifeline` marker; `scripts/test_clean.py` and its check-only form, which 03 put as the last step of today's job; Java, the jar download and the `uv run tlaup tools install` step already gone from `test.yml` with the old tests (03b, decision D62).
- [06](06-lifeline-agent.md): `uv run poe test-lifeline`, which compiles the agent's source with `javac --release 11` and compares the class files with the checked-in `src/tlaup/java/lifeline.jar` (the jar is checked in, not built per release: the coordinator's pick for the choice G3 left to the package, review finding A9), and 06's choice whether the agent's Java source ships as package data, which `check_wheel.py` must match.
- [09](09-parse-package-and-model.md): the `tlaup_parse` package and its `py.typed` as package data, which the wheel check asserts.

Changed from the draft (03, 06): 01 and 09 are added; 09 because I4's wheel check names "both import packages" and "both `py.typed` files", which do not exist before 09.

## Files

Changes:

- `.github/workflows/test.yml`: rewritten (Interfaces).
- `pyproject.toml`: the `check-release` sequence becomes `clean`, `build`, `twine-check`, `check-wheel`; a new task `check-wheel` runs `scripts/check_wheel.py`. Today's sequence starts with `check` (all pre-commit hooks); it leaves the sequence, because the `lint` job runs the hooks and `poe check` stays as its own task (say so in the pull request: `poe check-release` no longer runs the hooks).
- `docs/contributing/development.md`: the "CI" section describes the jobs, which are required (through `Test`), that `deps-newest` is not, and the weekly run; the commands list's `check-release` line says what it now runs.

Creates:

- `scripts/check_wheel.py` (Interfaces). Standard library only, typed for `mypy --strict`, which `uv run poe lint` applies to `scripts/`.

Deletes: nothing. `release.yml` is not touched here (55).

Shared files: `pyproject.toml` with every package that changes a task or a dependency (two task lines here); `test.yml` later with [54](54-integration-job.md) (adds a job and one `needs` entry) and [57](57-repo-hygiene.md) (removes one `SKIP` line; its test reads the `unit` matrix); `docs/contributing/development.md` with 52, 54 and 57 (other sections or lines). [29](29-tool-commands.md) also names `test.yml`: it removes `uv run tlaup tools install` if that step is still there, and 03 already removed it, so after this package 29 has nothing to do in `test.yml`. Nothing under `src/` changes, so this package conflicts with no code package.

## Interfaces

**The workflow**, `.github/workflows/test.yml`. Workflow name `Test`. Marked "stage 4" where the design gives no value.

```yaml
on:
  push: {branches: [main]}
  pull_request:
  schedule:
    - cron: "17 4 * * 1"        # stage 4: Mondays 04:17 UTC; I1 and I3 ask for a weekly run
permissions:
  contents: read
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

| Job | Runs on | Timeout | Steps |
| --- | --- | --- | --- |
| `lint` | `ubuntu-latest`, the Python of `.python-version` | 10 | checkout; set up uv; `uv sync --locked`; `uv run poe lint`; `uv run ruff format --check .` (01's step, moved here); `shellcheck scripts/*.sh`; `uv run pre-commit run --all-files --hook-stage pre-commit`, with `SKIP: pytest` in the step's environment and a comment that [57](57-repo-hygiene.md) removes it when the test hook moves to `pre-push` (Context). |
| `unit` | matrix `include`: `ubuntu-latest` with `"3.11"`; `ubuntu-latest` with `"3.15"`; `macos-latest` with `"3.15"` | 15 | job environment `UV_PYTHON: ${{ matrix.python }}` (Context); checkout; set up uv; `uv sync --locked`; `uv run poe test`; the clean-home check, exactly the command 03 wrote for it. No Java, no jar. |
| `lifeline` | matrix `os`: `ubuntu-latest`, `macos-latest` | 10 (stage 4) | checkout; set up uv; `actions/setup-java` with `temurin` and `11`; `uv sync --locked`; `uv run poe test-lifeline`. [54](54-integration-job.md) later adds the steps that give its REPL case a jar. |
| `deps-newest` | `ubuntu-latest` | 15 (stage 4) | checkout; set up uv; `uv sync --upgrade` (no `--locked`: the one exception, Context); `uv run --no-sync poe test`. The changed `uv.lock` is not committed. |
| `build` | `ubuntu-latest` | 10 | checkout; set up uv; `uv sync --locked`; `uv run poe check-release`. No Java: the lifeline jar is checked in. |
| `Test` | `ubuntu-latest` | 5 (stage 4) | `name: Test`; `needs: [lint, unit, lifeline, build]`; `if: always()`; one step that fails unless every entry of `needs.*.result` is `success` (below). No checkout and no action. |

`fail-fast: false` on both matrices (stage 4: I1 says so for the integration matrix; a cell that fails should not hide the others). Every checkout sets `persist-credentials: false` (stage 4: L2 asks it for the release workflow; no job here pushes). `setup-uv` stays on its default uv version, the latest, because an older uv does not know Python 3.15.2 (I2).

The final step of `Test`, as a sketch:

```yaml
    steps:
      - name: Every required job succeeded
        env:
          RESULTS: ${{ join(needs.*.result, ' ') }}
        run: |
          for r in $RESULTS; do
            if [ "$r" != success ]; then echo "a required job ended with: $r"; exit 1; fi
          done
```

Both `if: always()` and the check matter (I5): without `if: always()` the job is skipped when a job it needs fails, and a required check that was skipped counts as passed; with it and no check, a failure would pass. `deps-newest` is not in `needs` (I3). [54](54-integration-job.md) adds `integration` to `needs`. `lifeline` is in `needs`: I2 calls it "a required check, like the unit job", and I5's list of required jobs names it.

**Pins** (L2, top-up). Every `uses:` is a full 40-character commit hash with the release in a comment, for example `uses: actions/checkout@<hash>  # v7.0.1`. The values research 29 found on 2026-11-19, to be looked up again on the day the pull request is opened:

| Action | Release | Commit (2026-11-19) |
| --- | --- | --- |
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `astral-sh/setup-uv` | v10.3.3 (it has no major tag) | `68559e99cc807c1eb7e9238fd43a15bba460eec2` |
| `actions/setup-java` | v6.3.0 | `d1374f8ac74474200d16ef8ecee22c7ae7a51880` |
| `actions/cache` (used by 54) | v6.1.0 | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` |

To look one up: `git ls-remote --tags https://github.com/<owner>/<repo> 'refs/tags/<release>*'`; for an annotated tag take the line ending `^{}`, which is the commit. Use the newest release of the same major the table names unless a newer major exists, and then read its release notes for a breaking change before taking it. `actions/setup-python` is no longer used in this workflow.

**`scripts/check_wheel.py`** (I4; the details of how are stage 4's):

```
scripts/check_wheel.py [--dist DIST] [--list]
```

- `dist/` (or `--dist`) holds exactly one `.whl` and one `.tar.gz`; otherwise it fails naming what it found.
- The wheel holds `tlaup/__init__.py`, `tlaup_parse/__init__.py`, `tlaup/resources/default_config.yaml`, `tlaup/java/lifeline.jar` (D51: a wheel without it would stop every Java start; the same checked-in bytes in every wheel), `tlaup/py.typed` and `tlaup_parse/py.typed`; nothing under `tests/`; and no Python module that has no file under `src/` (that is what a stale `build/lib` leaves behind, H2). If 06 made the agent's Java source package data, it is allowed; nothing else is required of it.
- In a fresh environment with nothing else installed: `uv venv <tmp>/venv` and `uv pip install --python <tmp>/venv <wheel>`, where `<tmp>` is a new temporary folder (not `/tmp/wheel-test`, so that it also works off Linux, D15), then from that environment `tlaup --version`, `tlaup --help`, `tlaup tool dir` and `python -c "import tlaup_parse"` each exit 0. They run with `HOME`, `USERPROFILE` and `TLAUP_HOME` pointed under `<tmp>` and `NO_COLOR=1`, so the check writes nothing into the runner's or a developer's home (stage 4). The environment's executables are under `bin/`, or `Scripts/` on Windows.
- `--list` prints the wheel's and the sdist's file lists, sorted, and checks nothing else: [56](56-build-and-metadata.md) uses it to show that deleting `MANIFEST.in` changes neither.

`poe check-release` (I4: "The same commands are the `poe check-release` task, so the release script and CI run one definition"): `clean`, `build` (`uv build`), `twine-check`, `check-wheel`. The release script (55, L1 step 8) and the release workflow's build job (55, L2) call it.

Consumes: `poe test`, `poe test-clean`'s check-only form (03); `poe test-lifeline` (06); `poe lint`, `poe clean`, `poe build`, `poe twine-check` (today's tasks; 57 rewrites `clean`).

## Tests that must pass

The workflow is the test (I4: "The job is the test"). In the pull request:

- Every job green on the pull request's own run, on all cells; the macOS unit cell is the first run of the suite on macOS ([02](02-errors-and-paths.md) names its folder fallback as first checked there). The `lint` job's `ruff format --check .` covers the Python code blocks of the Markdown files too (the locked ruff reads them; question Q1: one format for all code, [30 I5](../design/30-ci-and-release.md#i5-workflow-hygiene)), which 01's format commit rewrote.
- `Test` shown failed when one required job fails. I5's hand-over check (a pull request with one failing unit test must show `Test` as failed) is the maintainer's once the ruleset exists (I7); here, push one commit to the branch with a deliberately failing unit test, show `Test` red in the description, and remove the commit before review.
- `uv run poe check-release` passes locally, and `scripts/check_wheel.py` fails on a wheel with `lifeline.jar` removed (tried once by hand; say so).
- `shellcheck scripts/*.sh` passes. It was not run during the cut (no `shellcheck` on the machine); if today's `release.sh` fails it, fix only what shellcheck reports, in a commit of its own, since 55 rewrites the script.

No test file changes.

## Changelog

None. CI only.

## Context for the worker

**Python through uv** (I2). "The newest release" is the newest stable CPython that uv can install and for which every locked dependency has a wheel: 3.15 (3.15.2) on 2026-11-19 (research 29). The runner images carry 3.14 as their newest, so it is a download either way. The design writes `uv sync --locked --python <version>`; this package sets `UV_PYTHON` for the whole job instead, which gives the same choice to `uv sync` and to every `uv run` after it. With `--python` on the sync alone, a later `uv run` reads `.python-version` (3.13 today, 3.11 after [57](57-repo-hygiene.md)) and may build the environment again with that version; this was not tried, and `UV_PYTHON` avoids the question. Say in the pull request which form was used. Whether the code and the locked dependencies pass on 3.15 was not tried; the first run shows it. If one dependency has no wheel for 3.15 yet, the matrix names 3.14 with a comment saying why (I2, Risks), and the index is told, because 56 and 57 then advertise 3.14.

**The one sync without `--locked`.** I5: "Every `uv sync` in a workflow has `--locked`." I3: `uv sync --upgrade`, "which resolves again without honouring the lock file". Both cannot hold for `deps-newest`; I3 names the command, so it is the one exception. `uv run --no-sync` keeps the next step from syncing again against the rewritten lock (stage 4; not tried).

**Pre-commit in CI** (I6). `--hook-stage pre-commit` excludes the test hook only once [57](57-repo-hygiene.md) gives it `stages: [pre-push]` (H1). Until then the hook has no stage and runs in every stage, so the lint job would run the whole unit suite a second time. `SKIP: pytest` for that one step bridges the gap; 57 removes it in the same pull request that moves the hook. The `no-*` hooks against personal and machine data run here too, which is the point of I6: they hold for every contributor and agent.

**The lifeline job** (D51; I2). It exists to run the lifeline tests (marker `lifeline`, folder `tests/lifeline/`) on the oldest supported Java on both CI systems: the checked-in jar matches its source compiled with `javac --release 11`, the JVM ends within three seconds of its parent's SIGKILL (also with `-Xrs` among its options), a JVM started with the id of a process that is gone exits at once, the reused-id stand-in on Linux, and `tlaup repl`'s JVM under a pseudo-terminal still reads a line from stdin. The first four are 06's and exist when this package starts. The REPL case needs `tlaup repl` and a real `tla2tools.jar` with the REPL; [52](52-integration-tests.md) writes it, skipped with its reason while no jar is given, and [54](54-integration-job.md) adds the steps that give this job a rolling jar. 06's tests treat a missing JDK as an error, so this job cannot pass with nothing run. What [21](21-java-launcher.md) adds later (the agent in every Java start through tlaup's launcher) is checked by the integration tests of 52 in 54's job. The unit job stays without Java (I2); the hosted runners still have some `java` on `PATH`, which is why 06 keeps its tests out of the default run by folder and marker rather than by "skip without Java". 06 warns that the reused-id test may need privileges the runner gives only through `sudo` (`unshare --pid --fork`); if the first run shows that, report it to the index with the error, and do not add `sudo` or a skip on your own.

**The clean-home check** (T2). Each unit cell ends with it, so it runs on Linux and macOS (`~/Library/...` there; 03's script lists both). The jar download that would have written into the runner's home is already gone (03).

**The wheel smoke commands and the `tool` group.** I4 names `tlaup tool dir`. Until [29](29-tool-commands.md) switches the group, the command is `tlaup tools dir`. If 29 has merged, write `tool dir`. If not, write `tools dir` with a comment; 29's Files already say that 29 then changes that one word in `scripts/check_wheel.py`.

**`check-release` and the lifeline jar.** The jar is checked in (A9; I4: "checking it in, with the lifeline job's comparison, is the simpler of the two"), so the build job needs no Java: the lifeline job compares the jar with its source on every push, and every test run and every wheel carries the same bytes.

**Concurrency.** With `cancel-in-progress: false` on `main`, GitHub keeps one running and one pending run per group and cancels an older pending one when a newer arrives (from knowledge of the platform, not checked). On `main` that means a commit pushed while two runs wait may get no run of its own; the release script checks `HEAD` only (55, L1 step 7), so this is accepted. Pull requests cancel their older run.

**Maintainer actions that wait on this package** (not work here): the ruleset on `main` ([30 I7](../design/30-ci-and-release.md#i7-ruleset-on-main)) requires the status check `Test`, which this package creates; the design says the worker writes the ruleset as a `gh api` command in the pull request description for the maintainer to run, and does not run it. Write it: target the default branch; require a pull request with no approvals required; require the status check `Test`; block force pushes and deletion; bypass list the repository admin role, "always" (D21). The maintainer then checks it once with a pull request that has one failing unit test.

**State of `main` when this starts.** `test.yml` has one job: checkout, setup-uv, setup-python, `uv sync --all-extras --dev`, `uv run poe lint`, `uv run ruff format --check .` (01), `uv run poe test`, and 03's clean-home step; Java and the jar download are gone (03). Action versions are `@v4` and `@v5` tags. `release.yml` is unchanged (55's).

## Done when

- `test.yml` has the six jobs above, all green on the pull request on every cell, every action pinned by hash with its release in a comment, the workflow-level `permissions: contents: read`, a timeout on every job, the concurrency group, and the weekly schedule.
- `Test` was shown red with one deliberately failing test and green without it.
- `uv run poe check-release` passes locally and in the build job; `scripts/check_wheel.py` passes `mypy --strict` and ruff.
- The `gh api` command for the ruleset is in the pull request description.
- `uv run poe lint`, `uv run ruff format --check .` and `uv run poe test` pass; the development guide's CI section is updated.

## Out of scope

- The integration job: [54](54-integration-job.md).
- `release.yml` and its permissions, pins and jobs: [55](55-release-tooling.md).
- Moving the test hook to `pre-push`, the `mypy` hook, `.python-version`, and the agreement test of Python versions: [57](57-repo-hygiene.md).
- The classifiers: [56](56-build-and-metadata.md).
- Dependabot, which will move these pins: [56](56-build-and-metadata.md).
- The ruleset itself and the `pypi` environment: maintainer actions (I7, L5).
- Windows cells (D15). A lowest-versions job (rejected in I3).

## Risks

- From I2: the newest CPython may lack a wheel for a dependency for some weeks; then the matrix names the one before, with a comment.
- From I3: `deps-newest` may be red on `main`; it is the one job allowed to be, and a red run is fixed by a cap with a comment or by adapting the code. A pull request shows it red too, without being blocked.
- From I5: the `Test` construction is stated from knowledge of the platform, not tried before this package; the deliberate red run above is its test.
- The macOS cells run the suite and the lifeline tests there for the first time. A failure that appears only there is a finding against the package that owns the code; report it, and do not skip the test here.
- From the cut: action hashes age fast; the table above is a week old when the cut is made.
