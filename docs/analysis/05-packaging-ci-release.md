# 05 - Packaging, distribution, CI and release

Scope: `tlaplus-cli` 0.8.1 at commit `bac6ba1` (branch `dev`, identical to `main`), reviewed 2026-11-09.
Read-only review. Nothing in the repository was changed apart from this file.

## How this was checked

| Source | Status |
|---|---|
| Repository files and `git` history/tags | Read directly. |
| sdist and wheel contents | Built from a clean `git archive HEAD` export in a scratch directory (outside the repo) with `uv build`, then listed. |
| PyPI state | Read from the public JSON API (`pypi.org/pypi/tlaplus-cli/json`) and the PyPI integrity API. Verified. |
| GitHub releases, workflow runs, job steps, open issues | `gh` is **not authenticated** on this machine. Read instead from the unauthenticated public REST API. Verified for what that API exposes. |
| GitHub repo settings (branch protection, rulesets, `pypi` environment protection rules, secret scanning, default token permissions, Dependabot alerts) | **Not verifiable** without authentication. Labelled below wherever relevant. |
| Nix flake | `nixpkgs` package versions evaluated with `nix eval --no-write-lock-file`. A trial `nix build --no-link --no-write-lock-file .#default` was run; see section 5 for the outcome. |
| CI workflow logs | Not readable unauthenticated. Only job/step conclusions were seen. |

## Executive summary

The fundamentals are better than most projects of this size: PyPI trusted publishing (OIDC, no tokens) is in place and PEP 740 attestations are already being published; the version has one static source and is read at runtime from package metadata; the wheel and sdist contain exactly what they should; the release job runs lint and tests before building.

The weak point is the order of events in a release. CI only runs on `main` and on pull requests, development happens on a local-only `dev` branch, and `scripts/release.sh` pushes `main` and the tag in the same command. The first time CI ever sees new code is therefore the release run itself. The result is visible in the history: **0.3.0, 0.4.0 and 0.8.0 are tagged but were never published** because the release job failed on tests, and each needed a follow-up patch release. 0.8.1 exists solely for that reason.

The second notable problem is the Nix flake: **it does not build today** (verified with a trial build). The `rich<14` pin in `pyproject.toml` is rejected against `rich 15.0.0` in current `nixos-unstable`. The flake also has no `flake.lock`, hard-codes version `0.6.0`, and is not exercised in CI.

Top recommendations, ranked by value over effort (details in section 10):

1. Run CI on `dev` pushes (one line), so tests fail before the tag, not after.
2. Make `release.sh` refuse to tag unless on a clean, pushed `main` whose CI is green; push atomically.
3. Fix the flake: derive version from `pyproject.toml`, commit `flake.lock`, relax or drop the `rich` cap, add a `nix build` CI job.
4. Drop the `rich<14` upper bound and lower the needlessly high floors; raise the `setuptools` floor to match the PEP 639 `license = "MIT"` syntax.
5. Restrict GitHub Release assets to `*.whl` and `*.tar.gz` (every release currently ships a stray `default.gitignore`).
6. Split build from release permissions, set `persist-credentials: false`, add Dependabot for actions and `uv`.

---

## 1. Build configuration

### 1.1 Backend and metadata

- Backend is setuptools: `pyproject.toml:1-3` (`requires = ["setuptools>=68.0"]`).
- **Bug in the build requirement floor.** `pyproject.toml:23` uses the PEP 639 SPDX string form `license = "MIT"`. That form is only supported from setuptools 77.0.3. The declared floor of 68.0 is therefore wrong: with setuptools 68 to 76 the build fails validation. PyPI/uv/pip builds are unaffected (isolated builds pull the newest setuptools), but downstream packagers with a pinned older setuptools are. Fix: `requires = ["setuptools>=77.0.3"]`.
- The built metadata is correct: `Metadata-Version: 2.4`, `License-Expression: MIT`, `License-File: LICENSE`, `Requires-Python: >=3.11` (verified from the built wheel and from PyPI).
- No `License ::` classifier, which is correct under PEP 639.
- URLs present: Homepage, Repository, Issues, Changelog (`pyproject.toml:35-39`). No Documentation URL (there is no docs site, so acceptable).
- Gaps in discoverability metadata (`pyproject.toml:24-33`):
  - No `keywords` (e.g. `tla+`, `tlaplus`, `tlc`, `model-checking`, `formal-methods`).
  - Missing useful classifiers: `Environment :: Console`, `Intended Audience :: Developers`, `Intended Audience :: Science/Research`, `Topic :: Software Development :: Quality Assurance` or `Topic :: Scientific/Engineering`, `Typing :: Typed` (a `py.typed` is shipped).
  - `Topic :: Software Development :: Build Tools` is a questionable fit.
  - `Programming Language :: Python :: 3.14` is absent although `requires-python` permits it, and no CI evidence covers 3.11, 3.12 or 3.14 (section 4).
  - `Operating System :: OS Independent` is asserted but CI only runs on Linux. No platform-specific code was found by grep, so the claim is plausible but **unverified** for macOS and Windows.
  - The GitHub repo has no topics (verified via public API), which costs discoverability for free.
- `README.md:28` uses a relative link (`docs/examples/`). It works on GitHub and is broken on the PyPI project page, since the README is the PyPI long description (`pyproject.toml:9`). Use an absolute URL.
- The PyPI long description is the 40-line README. It does not mention that Java is required. For a tool whose core commands shell out to `java` and `javac`, that belongs in the first screen.

### 1.2 Dependency ranges (`pyproject.toml:11-19`)

| Dependency | Range | Locked (`uv.lock`) | Comment |
|---|---|---|---|
| typer | `>=0.22.0,<1.0.0` | 0.24.1 | Cap is defensible for a 0.x library. Floor is close to the lock. |
| requests | `>=2.31.0,<3.0.0` | 2.32.5 | Fine. |
| pyyaml | `>=6.0,<7.0` | 6.0.3 | Fine. |
| platformdirs | `>=4.0,<5.0` | 4.9.4 | Fine. |
| pydantic | `>=2.12.5,<3.0.0` | 2.12.5 | Floor equals the locked version. Almost certainly not a real minimum; it needlessly excludes distro-packaged pydantic. |
| truststore | `>=0.9.0,<1.0.0` | 0.10.4 | Fine for a 0.x library. |
| rich | `>=13.7.0,<14.0.0` | 13.9.4 | **Stale cap.** `nixos-unstable` ships rich 15.0.0 today (evaluated). The tool is held two majors back. |

Assessment for an installed CLI:

- Upper caps on every dependency are a trade-off. For an application installed in isolation (`uv tool`, `pipx`) they do not cause conflicts with other packages, and they do protect users from a breaking major. The cost is that somebody has to raise them, and nothing in this repo prompts that (no Dependabot or Renovate, section 4.6). `rich<14` shows the cost: it is now a hard blocker for the Nix build (section 5) and for any distro packaging.
- The wheel is installed without the lock file. Users therefore get the newest versions inside the ranges, while CI only ever tests the exact versions in `uv.lock`. Nothing tests the newest-allowed or oldest-allowed resolution. One extra CI job with `uv sync --upgrade` (or `--resolution lowest-direct`) closes this.
- Recommendation: drop the `rich` cap or raise it after a test run on rich 14 and 15; lower `pydantic` to a true minimum (likely `>=2.0` or the first version providing the features used); keep caps only on 0.x libraries (typer, truststore) if desired.

Dev group (`pyproject.toml:52-67`): `pre-commit>=3.5.0,<4.0.0` is behind (4.x has been current since late 2024); `bandit>=1.9.4` is the only uncapped entry (inconsistent, harmless). `twine` is only used for `twine check` (`pyproject.toml:128`).

### 1.3 What ships

Built from a clean export of `HEAD`:

- **Wheel** (`tlaplus_cli-0.8.1-py3-none-any.whl`, about 60 KB): the `tlaplus_cli` package, `tlaplus_cli/py.typed`, `tlaplus_cli/resources/default_config.yaml`, `dist-info` with `licenses/LICENSE` and the `tla` entry point. No tests, no docs, no examples, no jar. Correct.
- **sdist** (about 46 KB): `LICENSE`, `MANIFEST.in`, `README.md`, `pyproject.toml`, `setup.cfg` (generated), `src/tlaplus_cli/**`, egg-info. No `tests/`, no `docs/`, no `CHANGELOG.md`, no `uv.lock`, no `flake.nix`.
- The default config resource is included through `pyproject.toml:48-50` and loaded with `importlib.resources` (`src/tlaplus_cli/config/loader.py:64`), which is the robust approach (it fixed the 0.3.3 bug noted at `CHANGELOG.md:125`).
- Sizes match PyPI's 0.8.1 files within a few bytes (60689 and 46049 on PyPI), so the published artifacts have the same shape.

`MANIFEST.in` (4 lines) is **redundant but harmless**. Every line duplicates something setuptools already does: `LICENSE` is auto-included via license-files defaults, `README.md` via `readme =`, the YAML and `py.typed` via `[tool.setuptools.package-data]`. It can be deleted; the sdist stays identical. If kept, it is one more place to forget when adding a resource.

Optional: downstream packagers (nixpkgs, Debian, conda-forge) generally prefer an sdist that carries `tests/` so they can run the suite. Today the flake sets `doCheck = false` (`flake.nix:54`) anyway. Low priority.

---

## 2. Versioning of the tool

### 2.1 Source of truth

- Static `version = "0.8.1"` at `pyproject.toml:7`.
- Runtime reads it from installed metadata: `src/tlaplus_cli/cli.py:26-27` and `src/tlaplus_cli/versioning/app_version.py:50-54`. There is no `__version__` constant to drift. Good.
- Derived copies:
  - `uv.lock:1169` is in sync (0.8.1), maintained by `uv`.
  - `flake.nix:29` says `0.6.0` and has been wrong for three releases (0.7.0, 0.8.0, 0.8.1; verified by reading `flake.nix` at each tag). See section 5.
- Minor: `get_app_version` runs `git rev-parse` as a subprocess on every `tla --version` before it decides whether the install is a development one (`app_version.py:56-58`). For a PyPI install this is a wasted process spawn and prints nothing. Not a packaging defect; reorder the checks when convenient.

### 2.2 How it is bumped

Manually. `scripts/release.sh` only reads the version (`scripts/release.sh:13`); it does not bump it, despite `CHANGELOG.md:210-216` describing the script as simplifying "version bumping and tagging". The maintainer edits `pyproject.toml`, runs `uv lock` (or `uv sync`) to refresh `uv.lock`, and edits `CHANGELOG.md`. Nothing checks that `uv.lock` or `flake.nix` were updated. `uv version --bump patch|minor` would do the first two steps in one command.

### 2.3 Changelog discipline

`CHANGELOG.md` follows Keep a Changelog with dated sections and is generally well written and user-facing. Problems:

- **Entries for versions that were never published.** `CHANGELOG.md:13` documents 0.8.0 and `CHANGELOG.md:92` documents 0.4.0. Neither exists on PyPI or as a GitHub Release (section 3.4). A user reading the changelog cannot install them.
- Missing entries: 0.1.4, 0.1.5, 0.1.7, 0.2.0, 0.3.0 all have tags but no section (0.3.0's content was folded into 0.3.1 at `CHANGELOG.md:148`).
- No `[Unreleased]` section is kept at HEAD now, and no compare-link footer.
- At several tags the top heading was still `## [Unreleased]` above the release section (v0.2.0 to v0.5.0, v0.7.0). The script's check at `scripts/release.sh:23` is only `grep -q "\[VERSION\]"`, which passes if the string appears anywhere in the file.
- Dates drift from tags: 0.4.0 says 2026-04-20, tagged 2026-04-24; 0.3.5 says 2026-04-19, tagged 2026-04-18.
- The tag `v0.6.0` points at a commit titled "Release 0.5.0" (`3049502`).
- 0.8.1's only entry (`CHANGELOG.md:11`) is a test fix that does not change the shipped wheel at all, an artefact of the burned 0.8.0.

### 2.4 Semver adherence

`CHANGELOG.md:6` claims Semantic Versioning. Pre-1.0 semver permits anything, but the usual 0.x convention (minor = breaking or feature, patch = fix) is not followed consistently:

- 0.3.2 (patch) renamed `tla build` to `tla modules build` and changed `tla tools path` output (`CHANGELOG.md:144-145`): breaking changes in a patch.
- 0.3.2, 0.3.4, 0.3.5 (patches) each added commands or features.
- 0.2.1 and 0.3.1 carry explicitly labelled breaking changes, again because the corresponding `.0` was burned.
- 0.7.0 removed three commands (`CHANGELOG.md:44-47`) in a minor, which is fine at 0.x.
- From 0.4.0 on the pattern is consistent (features in minors, fixes in patches).

Cadence: 22 tags in 6 months, 14 actually published to PyPI. The classifier `Development Status :: 3 - Alpha` (`pyproject.toml:25`) matches this honestly.

---

## 3. Release process

### 3.1 What happens

`scripts/release.sh` (33 lines):

1. Reads the version from `pyproject.toml` (line 13).
2. Aborts if a local tag `v<version>` exists (lines 17-20).
3. Aborts if `[<version>]` is not found in `CHANGELOG.md` (lines 23-26).
4. `git tag "$TAG"` on the current `HEAD` (line 29).
5. `git push origin main "$TAG"` (line 30).

`.github/workflows/release.yml` on `v*` tags:

- Job `build-release` (`contents: write`): checkout, uv, Python, Java 17, `uv sync`, install tla2tools, lint, unit tests, `uv build`, upload artifact, create GitHub Release with `dist/*` and generated notes (lines 9-58).
- Job `pypi-publish` (`id-token: write`, environment `pypi`): download artifact, `pypa/gh-action-pypi-publish@release/v1` (lines 60-76).

### 3.2 What is good

- **Trusted publishing, no long-lived tokens.** `release.yml:63-65` uses the `pypi` environment and `id-token: write`, with no `password:` input. Confirmed from PyPI: the 0.8.1 provenance names publisher `GitHub / nikolskiy/tlaplus-cli / release.yml / environment pypi`.
- **Attestations already exist.** PyPI's integrity endpoint returns provenance for 0.8.1, 0.5.0 and even 0.1.7 (HTTP 200). This comes for free from the publish action's defaults.
- Build and publish are separate jobs; the publish job has no repository write access and never checks out or executes project code.
- Publishing is gated on lint and tests (`release.yml:39-43`, then `needs:` at line 61). The v0.8.0 run shows the gate working: "Run tests" failed, build and publish were skipped.
- Artifacts are built once and the same files go to both GitHub and PyPI.

### 3.3 Safety and repeatability problems in `release.sh`

| # | Problem | Evidence | Consequence |
|---|---|---|---|
| a | No check of the current branch. | `scripts/release.sh:29` tags `HEAD`, line 30 pushes `main`. | Run from the `dev` worktree with `dev` ahead of `main`, it tags the `dev` commit and pushes an unrelated (older) `main`. The release is then built from a commit that is not on `main`. The two-worktree layout makes this mistake easy. |
| b | No clean-tree check. | No `git status`/`git diff` call. | A version bump or changelog edit that is still uncommitted satisfies the checks (they read the working files) while the tag points at the previous commit, whose `pyproject.toml` has the old version. CI then builds and tries to upload the old version under the new tag. |
| c | Tests are not run locally and CI status is not consulted. | No test invocation. `poe check-release` exists (`pyproject.toml:130-136`) but is not called. | First test run happens after the tag is public. See 3.4. |
| d | `main` and the tag are pushed together, non-atomically. | `scripts/release.sh:30` has no `--atomic`. | If `main` is rejected (non-fast-forward) the tag can still be pushed and trigger a release from a commit that is not on remote `main`. |
| e | Tag existence is only checked locally. | `scripts/release.sh:17`. | Minor; the push would fail for an existing remote tag. |
| f | Lightweight, unsigned tags. | `git for-each-ref` shows object type `commit` for all 22 tags. | No tagger, date or message on the tag; `git describe` ignores them by default; nothing to verify. |
| g | The local tag is not removed on push failure. | `set -e` exits after line 30 fails. | Re-running hits "Tag already exists" and tells the user to change the version, which is the wrong remedy. |
| h | Changelog check is loose. | `scripts/release.sh:23`. | Passes on any mention of the version; does not check date or that `[Unreleased]` is empty. |
| i | `uv.lock` and `flake.nix` consistency are not checked. | No check present. | The flake drifted (section 5). |
| j | Fragile version parse. | `scripts/release.sh:13` greps the first line starting with `version`. | Works today; breaks if a `version`-prefixed key ever precedes it. |

### 3.4 Failure modes observed in practice

Cross-referencing tags, the public Actions run list, GitHub Releases and PyPI:

| Tag | Release workflow | GitHub Release | On PyPI | Notes |
|---|---|---|---|---|
| v0.1.3 to v0.1.6 | (older than the 30 runs inspected) | yes | **no** | GitHub Release created, PyPI upload failed. `CHANGELOG.md:215` confirms "invalid PyPI classifier ... caused upload failures". Four orphaned GitHub Releases. |
| v0.2.0 | not inspected | no | no | Burned. |
| v0.3.0 | failure | no | no | Burned. Test on `main` also failed. |
| v0.3.1 | success | yes | yes | The Test workflow on the **same commit** (`dcdd909`) failed while Release succeeded: both run the same suite, so the suite or its network setup was flaky. |
| v0.4.0 | failure | no | no | Burned. Yet documented at `CHANGELOG.md:92`. |
| v0.8.0 | failure at "Run tests" | no | no | Burned. Yet documented at `CHANGELOG.md:13`. Fixed 11 minutes later as 0.8.1. |
| all others | success | yes | yes | |

So of the last 16 release attempts, 4 burned a version number, and all four are attributable to CI seeing the code for the first time at tag push.

Two structural causes:

1. **Tests run after the point of no return.** By the time the release job fails, the tag is already public. The maintainer's response each time has been to bump the version rather than delete and re-push the tag (a reasonable instinct; moving public tags is worse).
2. **GitHub Release is created before PyPI publish** (`release.yml:54-58` precedes the `pypi-publish` job). If PyPI rejects the upload, a GitHub Release with assets already exists for a version PyPI does not have. That is exactly the state of v0.1.3 to v0.1.6.

Other release-workflow issues:

- **Every GitHub Release carries a junk asset `default.gitignore`** (verified on all 18 releases). `uv build` writes `dist/.gitignore`; `files: dist/*` at `release.yml:58` matches it and the release action renames it. It does not reach PyPI because `upload-artifact@v4` skips hidden files. Fix: `files: |` with `dist/*.whl` and `dist/*.tar.gz`.
- The workflow never verifies that the tag name equals the `pyproject.toml` version, nor that the tagged commit is on `main`. A hand-pushed `v9.9.9` tag would publish whatever version `pyproject.toml` says.
- `uv sync --all-extras --dev` (`release.yml:34`) lacks `--locked`, so a stale `uv.lock` is silently re-resolved in CI instead of failing. There are no extras, so `--all-extras` is a no-op.
- Release notes are auto-generated from PRs (`release.yml:57`). The project has no PRs, so the notes are effectively empty while a good hand-written changelog section exists and is unused. Extract the section for the tag and pass it as the body.
- No `twine check` or metadata check runs in CI (only in the local `poe check-release`). The 0.1.x classifier failures would have been caught by it.
- The built wheel is never installed and smoke-tested (`uv tool run --from dist/*.whl tla --version`). The 0.3.3 "missing config in `uv tool install`" bug (`CHANGELOG.md:125`) is the class of defect this catches; tests run against the editable install and cannot.
- `environment: pypi` protection rules (required reviewer, tag-only deployment) are **not verifiable** from here. If none are configured, the environment adds no gate beyond the trusted-publisher binding.

### 3.5 Recommended release shape

Keep it a small shell script; add the guards:

```
on main, tree clean, HEAD == origin/main after fetch
version in pyproject == version in uv.lock (== flake, until the flake derives it)
changelog has "## [X.Y.Z] - <today>"
CI for HEAD is green:  gh run list --commit "$(git rev-parse HEAD)" --workflow Test ...
git tag -a (or -s) "vX.Y.Z" -m "Release X.Y.Z"
git push --atomic origin main "vX.Y.Z"
```

With CI running on `dev` (section 4), the commit being tagged has already passed before the tag exists, and burned versions stop. In `release.yml`: verify tag equals version, build, smoke-test the wheel, publish to PyPI, and only then create the GitHub Release.

---

## 4. CI

`.github/workflows/test.yml` (43 lines) is the only CI besides the release workflow.

### 4.1 Triggers

- `push` to `main` and `pull_request` only (`test.yml:3-7`).
- Development happens on `dev`. Locally `dev` has **no upstream configured**; the remote `dev` branch exists but is stale at `8902f55` (2026-06-17) while local `dev` is at `bac6ba1`. All 30 most recent workflow runs are `push` events on `main` or tags; there are no pull-request runs.
- Net effect: CI never runs on work in progress. It runs once per release, simultaneously with the release job. This is the root cause of section 3.4. It also means work between releases (for example 5 commits from 2026-08-05 to 2026-08-13) existed only on the maintainer's disk.

Fix: add `dev` to `branches:` (or use `branches: ["**"]`) and push `dev` routinely.

### 4.2 Matrix

- One OS (`ubuntu-latest`), one Python, one Java (17).
- Python selection is muddled. `actions/setup-python` is given `python-version-file: "pyproject.toml"` (`test.yml:22-24`), which reads `requires-python = ">=3.11"` and installs some version satisfying it. `uv` then independently honours `.python-version` (`3.13`) for the project environment. Which interpreter actually runs the tests is **unverified** (logs not accessible); most likely 3.13 via uv, making the `setup-python` step redundant.
- The classifiers advertise 3.11, 3.12 and 3.13 (`pyproject.toml:27-29`); at most one of them is tested. The Nix package uses 3.12 (`flake.nix:26`), which CI does not cover either.
- The tool's own minimum Java is 11 (`src/tlaplus_cli/resources/default_config.yaml:25`); CI tests only 17.
- macOS is a primary platform for the TLA+ audience and is untested. Windows is claimed by "OS Independent" and untested.

Proportionate matrix: Python 3.11 and newest (3.13 or 3.14) on Ubuntu, plus one macOS job on a single Python. Use `uv sync --locked --python ${{ matrix.python }}` and delete the `setup-python` step. That is 3 jobs of about 30 to 40 seconds each (the current job takes about 25 to 40 seconds by the run timestamps).

### 4.3 Steps

- Lint: `poe lint` = `ruff check`, `bandit`, `mypy .` strict (`pyproject.toml:115-118`). Good coverage for the size.
- **No format check.** `ruff format` is neither in CI nor in pre-commit (`.pre-commit-config.yaml:59-64` runs only `ruff check`). Add `ruff format --check .` to `poe lint`.
- **Pre-commit hooks are not run in CI.** detect-secrets, check-yaml, check-toml, large-file and merge-conflict checks only run on the maintainer's machine, and only if hooks are installed.
- Tests: `poe test` = `pytest` with `testpaths = ["tests/unit"]` (`pyproject.toml:71`).
- **Integration tests never run in CI.** `tests/integration/` (three modules exercising real TLC and `javac`) is excluded by `testpaths`. CI nevertheless sets up Java and downloads `tla2tools.jar` (`test.yml:26-40`), with the comment "Running tests requires a TLC" (`test.yml:38`), yet the unit tests use fake jars throughout (for example `tests/unit/tools/conftest.py:54`). So CI pays for the real toolchain and then does not use it. Either add a step `uv run pytest tests/integration` (the environment is already there) or drop the Java and jar steps from the unit job.
- The jar download step calls the GitHub API unauthenticated; the code has no `GITHUB_TOKEN` support (grep finds none in `src/`). On shared runner IPs the 60 requests/hour anonymous limit is a known source of flakiness. This is a plausible explanation for the v0.3.1 run where Test failed and Release passed on the same commit (**unverified**, logs not readable). Supporting an optional token header would help CI and rate-limited users alike.
- Coverage is computed (`pyproject.toml:70`) but not reported anywhere or thresholded. Fine at this size.
- No build check in the test workflow: a packaging break is discovered at release time.

### 4.4 Caching

`setup-uv` with `enable-cache: true` keyed on `uv.lock` (`test.yml:16-19`). Appropriate. The `tla2tools.jar` download is not cached; caching it keyed on the pinned TLC version would remove the network dependency from most runs.

### 4.5 Workflow security

- `test.yml` has **no `permissions:` block**. The token gets the repository default, which is **unverified** (read-only for repos created since 2023 unless changed). Add `permissions: contents: read` at the top level of both workflows to be explicit.
- `release.yml` scopes permissions per job (lines 11-12 and 64-65), which is right, but the `build-release` job combines three things under a `contents: write` token: installing all dev dependencies, running the test suite, and creating the release. `actions/checkout@v4` defaults to `persist-credentials: true`, so that write-capable token sits in `.git/config` while third-party dev dependencies execute. Split into `build` (read-only, produces artifact), `publish` (id-token only), `github-release` (contents: write, no code execution), and set `persist-credentials: false` on checkout.
- Actions are pinned to mutable major tags (`@v4`, `@v5`, `@v2`) and one branch (`pypa/gh-action-pypi-publish@release/v1`, `release.yml:74`). `softprops/action-gh-release` is a third-party action running with write access. For a small project, SHA-pinning everything is optional if Dependabot is absent to maintain it; the pragmatic step is to SHA-pin the two actions in the privileged path (`softprops/action-gh-release`, `pypa/gh-action-pypi-publish`) or replace the former with `gh release create` (first-party CLI, already on runners), and let Dependabot keep pins current.
- No `pull_request_target`, no secrets used, no script injection from untrusted inputs in `run:` steps. Fork PRs get a read-only token. Good.
- No `concurrency:` group and no `timeout-minutes:`. A hung TLC or network call would run for the 6-hour default. Add `timeout-minutes: 10`.

### 4.6 Dependency update automation

None. No `.github/dependabot.yml` (absent locally and HTTP 404 on the remote), no Renovate config. Consequences already visible: `rich` two majors behind, `pre-commit<4`, action majors that will age. A minimal Dependabot config with two ecosystems (`github-actions` and `uv`), weekly, grouped into one PR each, costs about 15 lines and would also generate the PR-triggered CI runs that currently never happen.

Whether Dependabot **security alerts** are enabled in repo settings is **unverified**.

### 4.7 Secret scanning

- Local: `detect-secrets` pre-commit hook with a baseline (`.pre-commit-config.yaml:4-8`, `.secrets.baseline`). The baseline is clean (`"results": {}`), generated 2026-03-29, never refreshed. `detect-private-key` is also configured. This is only effective if `poe install-hooks` was run in each worktree; hooks live in the shared bare repo's `hooks/` directory, so one install covers both worktrees.
- Server side: GitHub secret scanning and push protection for this public repo are **unverified** (settings not readable). They are free for public repositories and should be on; they are the only control that does not depend on local setup.
- Since releases use OIDC there is no PyPI token to leak, which removes the highest-value secret.

---

## 5. The Nix flake

`flake.nix` (104 lines), added 2026-06-03 (`43046a8`), advertised in `README.md:37-40`.

| Finding | Evidence | Severity |
|---|---|---|
| **No `flake.lock`.** | File absent and not tracked. Input is `nixos-unstable` (`flake.nix:5`). | High. Every user resolves a different nixpkgs; builds are not reproducible and can break on any nixpkgs bump without a change in this repo. |
| **Version hard-coded and stale.** | `flake.nix:29` `version = "0.6.0"`; unchanged at tags v0.7.0, v0.8.0, v0.8.1. | Medium. The store path and `nix profile list` say 0.6.0. `tla --version` still prints the right number because it reads the wheel metadata built from `pyproject.toml`. |
| **Dependency constraint conflict with nixpkgs.** | `pyproject.toml:18` requires `rich<14.0.0`; `nixos-unstable` currently has rich `15.0.0` (also typer 0.27.2, pydantic 2.13.4, both within range). `buildPythonApplication` with `pyproject = true` runs the runtime dependency check hook, which fails on unsatisfied version constraints. | High. Confirmed by the trial build below. |
| Not tested in CI. | No Nix step in either workflow. | Medium. This is why the two items above went unnoticed. |
| `jre_headless` on PATH. | `flake.nix:57`. | `tla modules add` invokes `javac` (`src/tlaplus_cli/cmd/modules/add.py:106`). Whether nixpkgs' `jre_headless` includes `javac` depends on the nixpkgs revision (**unverified**). Use `pkgs.jdk_headless` to state the intent. |
| `--prefix PATH`. | `flake.nix:57`. | The bundled Java shadows whatever Java the user selected. `--suffix` would make it a fallback, which better suits a tool that has a `check-java` command and configurable JVM options. |
| Misleading comment and no-op setting. | `flake.nix:48-51`: `dontPatchShebangs = false` is the default and has nothing to do with YAML resources. | Cosmetic. Delete. |
| No checks at all. | `doCheck = false` (`flake.nix:54`), no `pythonImportsCheck`, no `checks` output. | Low. Add `pythonImportsCheck = [ "tlaplus_cli" ];` and expose the package under `checks` so `nix flake check` does something. |
| Python mismatch. | Package and dev shell use `python312` (`flake.nix:26`, `:77`); `.python-version` says 3.13; CI tests (probably) 3.13. | Low. The Nix build uses an interpreter nothing else tests. |
| `src = ./.` | `flake.nix:32`. | Fine for a flake (only git-tracked files are copied), but it copies the 576 KB example jar and tests into the source derivation. Harmless. |

**Trial build result: the flake does not build today (verified).** `nix build --no-link --no-write-lock-file .#default` on x86_64-linux at `bac6ba1`, against the current `nixos-unstable`, builds the wheel and then fails:

```
Running phase: pythonRuntimeDepsCheckHook
Checking runtime dependencies for tlaplus_cli-0.8.1-py3-none-any.whl
  - rich<14.0.0,>=13.7.0 not satisfied by version 15.0.0
... /nix/store/...-tlaplus-cli-0.6.0.drv   (exit 1)
```

So the install command in `README.md:39` currently fails for any user without an older cached nixpkgs. The derivation name also confirms the stale `0.6.0` label on a 0.8.1 wheel. The build left no `flake.lock` or `result` link in the repository.

What `nix profile install github:nikolskiy/tlaplus-cli` installs: the default branch (`main`) HEAD, built against whatever `nixos-unstable` is at that moment. Because `main` only moves at releases, users do get release commits. That is the single concrete benefit of the current branch model for Nix users, and it is replaceable by documenting `github:nikolskiy/tlaplus-cli/v0.8.1` or `?ref=`.

Fixes, all small:

```nix
version = (pkgs.lib.importTOML ./pyproject.toml).project.version;
pythonRelaxDeps = [ "rich" ];        # or fix the pin in pyproject.toml, which is better
pythonImportsCheck = [ "tlaplus_cli" ];
```

plus `nix flake lock`, commit `flake.lock`, and a CI job (`DeterminateSystems/nix-installer-action` or `cachix/install-nix-action`, then `nix build` and `nix flake check`; about 2 to 4 minutes uncached). A weekly `nix flake update` PR can be automated later; until then update the lock at release time.

---

## 6. The dev/main branch model

Observed facts:

- Bare repo with two worktrees, `dev` and `main`, at the same commit.
- 103 commits, **zero merge commits**. `main` is only ever fast-forwarded to `dev`.
- Remote `dev` is stale (2026-06-17); local `dev` has no upstream. Remote `main` is updated only by `release.sh`.
- No pull requests appear in the workflow history. Branch protection on `main` is **unverified**, but the script pushes directly to it, so it is not enforcing reviews or status checks.
- One maintainer, one external issue reporter (4 open issues, all from the same user).

What the model buys today:

- `main` always equals the latest release, so `nix profile install github:nikolskiy/tlaplus-cli`, the Changelog URL (`pyproject.toml:39`, points at `blob/main`) and the GitHub landing page show released state.

What it costs:

- CI is wired to the branch nobody develops on (section 4.1), which is the direct cause of the burned releases.
- Work in progress is not backed up to the remote.
- `release.sh` has to reason about two branches and currently gets it wrong (3.3 a, d).
- Two worktrees each need their own `.venv`, hooks awareness and mental bookkeeping.

Assessment: for a single maintainer with linear history and no PR review, the second branch adds process without adding a gate. "main equals latest release" is already expressed precisely by tags and PyPI. Two reasonable options:

- **Option A, trunk plus tags (recommended).** Develop on `main`, push freely, CI on every push, tag from a green commit. Delete `dev`. Point Nix users at a tag in the README if release-only installs matter. Removes one moving part from `release.sh` and makes every commit CI-tested. Effort: under an hour.
- **Option B, keep `dev`/`main` but make it earn its keep.** Push `dev` routinely with an upstream, run CI on `dev`, and promote by fast-forward only after CI is green (enforceable with a ruleset on `main` requiring the `test` status check, which also blocks a red `release.sh`). This preserves "main = released" for Nix and browsers. Effort: similar, slightly more to maintain.

Either option fixes the real problem; staying as-is does not. If contributors appear, Option A with PRs into `main` is the conventional shape and needs no further change.

---

## 7. Other distribution channels

Audience: people writing TLA+ specs. They already need a JVM. Many are on macOS; a fair number are not Python users. CI usage (running TLC on specs in a pipeline) is a natural second use case.

| Channel | Value for this audience | One-off cost | Ongoing cost | Verdict |
|---|---|---|---|---|
| `uv tool install` / `uvx` / `pipx` | High. Already works. | None. Document `pipx install tlaplus-cli` and `uvx --from tlaplus-cli tla ...` next to `uv tool` in `README.md:32-35`. | None. | Do now (documentation only). |
| Nix flake (existing) | Medium for a niche but overlapping audience. | Fix as in section 5 (1 to 2 hours). | Lock updates. | Fix or remove; it is advertised in the README and currently fails to build. |
| GitHub Action (`nikolskiy/setup-tla` or `tlaplus-cli-action`) | Potentially high. "Run TLC on my specs in CI" is a real need, and this tool's TLC version pinning and caching are the hard part. A composite action is: setup-java, `uv tool install tlaplus-cli==X`, cache the tools dir, `tla tools install`, run. | Half a day including a demo workflow; needs a token-aware GitHub API client first (section 4.3) and stable non-TTY output and exit codes. | Low; version bumps. | Best new channel. Do after CI output and exit-code behaviour is settled. |
| Homebrew tap (`nikolskiy/homebrew-tap`) | Medium to high on macOS. Lets non-Python users `brew install` and can declare `depends_on "openjdk"`. | 2 to 4 hours (formula with Python virtualenv resources; `brew update-python-resources` generates them). | Formula bump per release; automatable from `release.yml` with a tap token (which reintroduces a long-lived secret) or done by hand. | Worth it once release cadence slows; at a release every 2 to 4 weeks, hand-bumping is tolerable. homebrew-core is out of reach until the project has notable usage. |
| Docker image (GHCR) | Medium. Bundling JRE + Python + tool + a pinned `tla2tools.jar` gives a zero-setup, reproducible TLC runner, handy for CI systems other than GitHub. | 2 to 3 hours (Dockerfile, build-push job, GHCR permissions). | Base image CVE churn, multi-arch builds, image size (JRE about 200 MB). | Second priority after the Action. Could back the Action later. |
| nixpkgs | Low to medium. Gives `nix-shell -p tlaplus-cli` and binary caching. | PR and review cycle; needs the dependency caps fixed and ideally tests in the sdist. | Maintainer duty on nixpkgs bumps. | Defer until the flake is healthy and the tool is past alpha. |
| Standalone binaries (PyInstaller, Nuitka, PyApp) | Low. The user needs Java regardless, so "no runtime required" is not achievable; `uv tool install` is already a one-liner. | 1 to 2 days for a 3-OS build matrix. | macOS signing and notarization, Windows SmartScreen, per-OS bugs. | Not worth it. |
| conda-forge | Low to medium (scientific users; conda can also supply `openjdk`). | Feedstock PR. | Bot-driven bumps. | Defer. |
| Shell completions | Not a channel, but relevant to packaging: `add_completion=False` at `src/tlaplus_cli/cli.py:20` disables Typer's completion install. Homebrew and Nix packages normally ship completions. | Small. | None. | Consider when adding Homebrew. |

---

## 8. Supply-chain posture of the tool's own releases

Proportionate assessment for a small project:

| Control | State | Comment |
|---|---|---|
| Trusted publishing (OIDC) | In place, verified on PyPI. | The most important control. No token to steal. |
| PEP 740 attestations on PyPI | In place, verified for 0.1.7, 0.5.0, 0.8.1. | Free via the publish action. Mention in README if desired; no work needed. |
| Publish job isolation | Good. | Separate job, no checkout, no code execution, environment-scoped. |
| `pypi` environment protection | **Unverified.** | Recommended: restrict deployments to `v*` tags and, optionally, require self-approval. This turns a pushed tag into a two-step action and gives a last chance to cancel. In the PyPI trusted-publisher config, keep the environment name bound (it is). |
| Build job privilege | Weak (section 4.5). | Split jobs; `persist-credentials: false`. |
| Action pinning | Mutable tags/branch. | SHA-pin the privileged ones; add Dependabot. |
| Locked CI installs | `uv.lock` exists with hashes, but `uv sync` is not `--locked`. | Add `--locked`. |
| GitHub Release asset attestations | Absent. | Optional: `actions/attest-build-provenance` in the build job (needs `attestations: write`, `id-token: write`). About 5 lines. Low marginal value since PyPI already has provenance for the same files. |
| Signed tags | Absent (lightweight tags). | Use annotated tags at minimum; SSH-signed tags (`git tag -s` with `gpg.format=ssh`) if a key is already set up. Cheap, modest value. |
| SBOM | Absent. | Low value here: the wheel bundles no third-party code and its 7 dependencies are declared in metadata. Skip, or attach `uv export --format cyclonedx1.5` output to the GitHub Release if someone asks. |
| Branch/tag protection | **Unverified.** | A tag ruleset preventing deletion or update of `v*` tags is free and protects the release trigger. |
| 2FA on PyPI and GitHub | **Unverified** (PyPI enforces 2FA for all publishers; GitHub should have it on). | Account security is the residual risk once OIDC is used. |
| Downstream integrity (what the tool downloads) | Out of scope for this section, but noted: no checksum verification of downloaded `tla2tools.jar` was found (`grep` for sha256/checksum finds only the run cache). | A release tool that downloads and executes a jar inherits that trust. Covered by other analysis documents if applicable. |
| Vendored binary | `docs/examples/sequences-ext/lib/commons-lang3-3.12.0.jar` (576 KB) is committed. | Not shipped in wheel or sdist. An opaque binary in git cannot be reviewed; fetching it from Maven Central with a pinned checksum in the example's README or a script would be cleaner. Low priority. |

Overall: already above average thanks to OIDC and attestations. The remaining cheap wins are job splitting, `--locked`, environment and tag rules, and annotated tags.

---

## 9. Repository hygiene

### 9.1 `.gitignore` (21 lines)

Covers `__pycache__`, `build/`, `dist/`, `wheels/`, `*.egg-info/`, pytest/ruff/mypy caches, `.coverage`, `.venv`, plus project-specific `lib/*.jar`, `classes/`, `states/`. `git status --ignored` confirms everything stale in the tree is ignored and nothing unwanted is tracked.

Gaps, all minor:

- `result` and `result-*` (symlinks left by `nix build`), `.direnv/`.
- `htmlcov/`, `coverage.xml`.
- Editor directories (`.vscode/`, `.idea/`); the history mentions a VS Code setting fix (`00f61f0`).
- `lib/*.jar` (`.gitignore:17`) contains a slash, so it is anchored to the repo root and does not match example `lib/` directories. That is evidently intended (the example jar is tracked) but worth a comment.

### 9.2 Stale artifacts in the working tree (all untracked and ignored)

- `dist/tlaplus_cli-0.3.1*` from 2026-04-05, seven releases old.
- `build/lib/tlaplus_cli/` and `build/bdist.linux-x86_64/`, a stale copy of the package from in-tree setuptools builds.
- `src/tlaplus_cli.egg-info/` (2026-08-13).
- `.coverage`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, and `docs/examples/spec/states`.

Risks: a stale `build/lib` is the classic way removed modules get resurrected into a locally built setuptools wheel. Releases are built on clean CI runners so published artifacts are not affected, but `poe check-release` builds locally and `poe clean` only removes `dist` (`pyproject.toml:126`). The stale tree is also why mypy needs `exclude = ["build", ...]` (`pyproject.toml:142`). Recommendation: make `clean` remove `dist build src/*.egg-info`, and delete the current leftovers by hand.

### 9.3 Pre-commit (`.pre-commit-config.yaml`, 86 lines)

- All 13 hooks are `repo: local` with `language: system` and `uv run ...`. Upside: tool versions come from `uv.lock`, one source of truth, no `pre-commit autoupdate` to remember. Downside: hooks do not work without `uv sync` first, and `pre-commit-hooks` is carried as a dev dependency (`pyproject.toml:64`) purely to provide the console scripts. Coherent choice; keep.
- **Full `pytest` and strict `mypy` run on every commit** (`.pre-commit-config.yaml:73-85`). As the suite grows this pushes toward `--no-verify`. Move `pytest` (and arguably `mypy` and `bandit`) to `stages: [pre-push]` and rely on CI, once CI actually runs on `dev`.
- No `ruff format --check` hook, though `poe format` exists.
- The `mypy` hook receives staged filenames (`.pre-commit-config.yaml:73-79`) while `poe type-check` runs `mypy .`. File-list mode can produce different results from whole-project mode. Use `pass_filenames: false` with `mypy .` for consistency, as the bandit hook already does.
- `bandit` and `pytest` hooks ignore filenames and run fully on any Python change; fine but slow.
- The large-file exclusion hard-codes the example jar path (`.pre-commit-config.yaml:15`).
- `pre-commit>=3.5.0,<4.0.0` (`pyproject.toml:63`) is one major behind.
- `poe audit` (`pyproject.toml:124`) audits a baseline that has no results; harmless.
- Hooks are relevant to the project; none is dead. The gap is that CI does not run them (section 4.3).

### 9.4 Miscellaneous

- `.python-version` (3.13), `flake.nix` (3.12), `mypy python_version` and `ruff target-version` (3.11) are each defensible individually; together they mean local dev, Nix and the declared floor are three different interpreters with CI covering one.
- `scripts/release.sh` has no executable-bit or shellcheck verification in CI. A `shellcheck` step is one line.
- No `SECURITY.md`, `CONTRIBUTING.md`, issue templates or `CODEOWNERS`. Not needed at this size; a two-line `SECURITY.md` pointing to GitHub private vulnerability reporting is the only one worth adding.

---

## 10. Recommendations ranked by value versus effort

Effort: S = under 30 minutes, M = 1 to 3 hours, L = half a day or more.

### Tier 1: high value, small effort (do first)

| # | Recommendation | Effort | Addresses |
|---|---|---|---|
| 1 | Run the Test workflow on `dev` (add to `branches:` in `test.yml:5-6`), give local `dev` an upstream and push it routinely. Or move to trunk (section 6, option A). | S | Burned versions 0.3.0, 0.4.0, 0.8.0; unbacked-up work. |
| 2 | Harden `scripts/release.sh`: require branch `main`, clean tree, `HEAD == origin/main`; check CI is green for `HEAD`; use an annotated tag; `git push --atomic`; delete the local tag if the push fails. | S-M | 3.3 a to g. |
| 3 | Restrict release assets to `dist/*.whl` and `dist/*.tar.gz` (`release.yml:58`). | S | `default.gitignore` in all 18 releases. |
| 4 | Remove the `rich<14` cap (or raise after testing), lower the `pydantic` floor, set `setuptools>=77.0.3`. | S | Nix build, stale deps, wrong build floor. |
| 5 | Flake: derive version with `importTOML`, commit `flake.lock`, add `pythonImportsCheck`, delete the misleading comment. | S | Section 5. |
| 6 | Add `--locked` to `uv sync` in both workflows; add `permissions: contents: read` to `test.yml`; add `timeout-minutes`. | S | 4.5, 3.4. |
| 7 | Add `.github/dependabot.yml` for `github-actions` and `uv`, weekly, grouped. | S | 4.6. |
| 8 | In `release.yml`, fail if the tag does not equal `v` + the `pyproject.toml` version. | S | 3.4. |

### Tier 2: high value, medium effort

| # | Recommendation | Effort | Addresses |
|---|---|---|---|
| 9 | Restructure `release.yml`: `build` (read-only; lint, test, build, `twine check`, install wheel and run `tla --version`) then `pypi-publish` then `github-release` (contents: write, no project code, body taken from the changelog section). Set `persist-credentials: false`. | M | Orphaned GitHub Releases (0.1.3 to 0.1.6), privilege scope, empty release notes, untested wheel. |
| 10 | Run `tests/integration` in CI (Java and the jar are already set up) and cache the jar. | M | Integration tests never run; flaky network. |
| 11 | CI matrix: Python 3.11 and newest, plus one macOS job; drop `setup-python` in favour of `uv --python`. | M | Untested advertised versions and platforms. |
| 12 | Add a `nix build` / `nix flake check` CI job. | M | Flake rot. |
| 13 | Decide the branch model (section 6) and encode it: either delete `dev`, or add a ruleset on `main` requiring the `test` check. Add a ruleset protecting `v*` tags. Configure the `pypi` environment to deploy only from `v*` tags. | S-M | Process clarity; supply chain. |
| 14 | Changelog: keep an `[Unreleased]` section; mark 0.8.0 and 0.4.0 as "not published" (or merge into the following patch); make the script check for `## [X.Y.Z] - ` at a heading. | S | 2.3. |

### Tier 3: worthwhile polish

| # | Recommendation | Effort |
|---|---|---|
| 15 | Metadata: keywords, extra classifiers, 3.14 classifier once tested, absolute README links, Java prerequisite and `pipx`/`uvx` instructions in README, GitHub topics. | S |
| 16 | Add `ruff format --check` to `poe lint`; run `pre-commit run --all-files` (minus pytest) in CI; move `pytest` hook to pre-push; make the mypy hook whole-project. | S |
| 17 | Delete `MANIFEST.in`. | S |
| 18 | `poe clean` removes `build` and egg-info too; clear current stale artifacts; add `result`, `.direnv/`, `htmlcov/` to `.gitignore`. | S |
| 19 | Use `uv version --bump` in a `poe bump` task so `pyproject.toml` and `uv.lock` move together. | S |
| 20 | SHA-pin `softprops/action-gh-release` and `pypa/gh-action-pypi-publish` (or replace the former with `gh release create`). | S |
| 21 | Optional GitHub token support for GitHub API calls in the tool (helps CI and rate-limited users). | M |
| 22 | Flake: `jdk_headless` instead of `jre_headless`, `--suffix` instead of `--prefix`, align Python version with `.python-version`. | S |

### Tier 4: new channels, when the basics are solid

| # | Recommendation | Effort |
|---|---|---|
| 23 | A composite GitHub Action for running TLC in CI. | L |
| 24 | Docker image on GHCR. | M-L |
| 25 | Homebrew tap. | M, plus per-release bumps |
| 26 | nixpkgs, conda-forge. | L, external review |

Not recommended: standalone binaries (Java is required anyway), SBOM generation (no bundled third-party code), a heavier release tool such as semantic-release or release-please (the shell script with guards is enough for one maintainer).

---

## 11. Items that could not be verified

- Branch protection or rulesets on `main` and on tags.
- Protection rules on the `pypi` GitHub environment.
- Default `GITHUB_TOKEN` permissions for the repository.
- Whether GitHub secret scanning, push protection and Dependabot alerts are enabled.
- Which Python interpreter CI actually uses (logs are not readable unauthenticated).
- The cause of the failed runs for v0.3.0, v0.4.0 and the `dcdd909` Test run (only step conclusions were visible; for v0.8.0 the failing step was "Run tests", consistent with the 0.8.1 changelog entry).
- Whether v0.1.3 to v0.1.6 were ever on PyPI and later removed. PyPI's API lists 0.1.7 as the earliest release and the changelog mentions upload failures, so "never uploaded" is the most likely reading.
- Behaviour on macOS and Windows.
- Whether `jre_headless` in current nixpkgs provides `javac`.
- 2FA status of the maintainer's accounts.
