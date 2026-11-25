# 56. Dependabot, build fixes and package metadata

Size: S. Suggested model: mid-tier. Status: ready.

## Goal

Dependabot proposes one grouped pull request a month per ecosystem; the build backend and the runtime bounds are those of D59; `MANIFEST.in` is gone with the packaged files unchanged; the PyPI page has real keywords, classifiers for the systems and Python versions that are tested, one summary sentence, absolute links in the README and the `pipx` and `uvx` install lines.

## Covers

- Roadmap items ([milestone 2](../roadmap.md#milestone-2-a-feedback-loop-that-catches-this), "Dependencies and build"):
  - "`.github/dependabot.yml` for the `uv` and `github-actions` ecosystems: one monthly run that groups all version updates into one pull request." (line 409). In full, as D44 changed it (one pull request per ecosystem).
  - "Build fixes (note 33): `setuptools>=77.0.3`, which the SPDX licence string needs; a real Pydantic minimum instead of the locked version; remove the `rich<14` cap; raise the `pre-commit<4` cap; delete the redundant `MANIFEST.in`." (line 410). In full, together with the bounds [16](16-ui-messages.md), [17](17-error-handler.md), [23](23-tool-store.md) and [03](03-test-foundation.md) set.
  - "PyPI and GitHub metadata (note 37): keywords; the missing classifiers ...; replace the 'Build Tools' topic; Linux and macOS instead of 'OS Independent' (decision D15); GitHub topics; absolute links in the README; `pipx` and `uvx` install options." (line 414). In full apart from the GitHub topics, a maintainer action.
  - "Unit job on Python 3.11 and the newest release ... Add a classifier for each Python version that is tested." (line 386). In part: the classifiers; the job is [53](53-ci-workflows.md).
- Design sections:
  - [30 B1](../design/30-ci-and-release.md#b1-dependabot): all of it.
  - [30 B2](../design/30-ci-and-release.md#b2-build-fixes): the rows listed under Files; the rows for `typer`, `rich`'s floor, `filelock` and the development dependencies are other packages' (Context).
  - [30 B3](../design/30-ci-and-release.md#b3-package-metadata): all of it.
  - [30 H3](../design/30-ci-and-release.md#h3-python-versions): the classifier row ("3.11 and the newest"). The rest of H3 is [57](57-repo-hygiene.md).

## Depends on

- [03](03-test-foundation.md): the development dependencies with their bounds (B2's last row), so this package only changes the `pre-commit` cap among them.
- [53](53-ci-workflows.md): `scripts/check_wheel.py`, whose wheel check and `--list` show that deleting `MANIFEST.in` changes no packaged file (B2: "The wheel check (I4) asserts the packaged files are unchanged before and after").
- [09](09-parse-package-and-model.md): `tlaup_parse` and its `py.typed` as package data, and the `MANIFEST.in` line 09 added (`include src/tlaup_parse/py.typed`), which goes with the file.

Changed from the draft (03): 53 and 09 are added, for the reasons above.

## Files

Creates:

- `.github/dependabot.yml` (B1).
- `tests/unit/test_readme_links.py` (B3): reads `README.md` and fails on a Markdown link whose target is neither an absolute `https://` address nor an in-page anchor (`#...`).

Changes:

- `pyproject.toml`, exactly these lines:
  - `[build-system] requires = ["setuptools>=77.0.3"]` (was `>=68.0`).
  - `pydantic>=2.12.5,<3.0.0` becomes `pydantic>=2.5.3`, no upper cap (D59).
  - `rich`: the cap goes, leaving `rich>=13.8.0` (D59). [16](16-ui-messages.md) raised the floor and left the cap for this package.
  - `pre-commit>=3.5.0,<4.0.0` becomes `pre-commit>=3.5.0,<5.0.0` (development; B2), unless 03 already changed it.
  - `typer`: if [17](17-error-handler.md) has merged, `typer>=0.27.2,<1.0.0` is already there and nothing changes; if not, write that line here, so that whichever of the two merges second meets an identical line. The same holds for `rich>=13.8.0` if 16 has not merged.
  - `description`: one sentence, shared with the root help (B3, [14 F7](../design/14-config-and-cli.md#f7-help-text)'s "One summary line"; [50](50-help-and-messages.md) reads it from the metadata).
  - `keywords` and `classifiers` (Interfaces).
  - Not touched: `filelock` ([23](23-tool-store.md) adds `filelock>=4.2.1` with no cap; if 23 has not merged, nothing is written for it here), `requests` and `platformdirs` with their caps ("outside this item and stay as they are", B2), `pyyaml`, `truststore`, the other development dependencies (03), `project.urls` ([55](55-release-tooling.md) changes `Changelog`).
- `uv.lock`: `uv lock` after the bounds change. Only the recorded requirements should change; if the resolver moves a locked version, the pull request says which and why.
- `README.md` (B3): every relative link becomes an absolute `https://github.com/...` address on the default branch, built from the `Repository` address in `pyproject.toml`; the install section gains `pipx install tlaup` and `uvx tlaup` beside `uv tool install tlaup`.

Deletes:

- `MANIFEST.in` (B2), and with it the line [09](09-parse-package-and-model.md) added for `tlaup_parse/py.typed`, which is package data after 09 and reaches the wheel and the sdist without it.

Shared files: `pyproject.toml` and `uv.lock` with 16, 17 and 23 (one dependency line each; the final text of each line is fixed by D59, so a conflict resolves to the same line), and with 53, 55, 57 (other sections). `README.md` with the switch packages [29](29-tool-commands.md), [31](31-module-commands.md) and [39](39-tlc-command.md), which change their own command lines; a relative link one of them adds later fails the new test, which is the point. Nothing under `src/` changes.

## Interfaces

**`.github/dependabot.yml`** (B1, D44):

```yaml
version: 2
updates:
  - package-ecosystem: uv
    directory: /
    schedule: {interval: monthly}
    groups:
      all: {patterns: ["*"]}
  - package-ecosystem: github-actions
    directory: /
    schedule: {interval: monthly}
    groups:
      all: {patterns: ["*"]}
```

One grouped pull request per ecosystem, at most two a month. The `github-actions` entry moves the hash pins of [53](53-ci-workflows.md) and [55](55-release-tooling.md) together with their release comments. Security updates stay as they are (on since 2026-11-14).

**Keywords and classifiers** (B3, H3):

```toml
keywords = ["tla+", "tlaplus", "tlc", "model-checking", "formal-methods", "sany", "pluscal"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: Science/Research",
    "Operating System :: MacOS",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.15",
    "Topic :: Scientific/Engineering",
    "Topic :: Software Development :: Quality Assurance",
    "Topic :: Utilities",
    "Typing :: Typed",
]
```

Removed: `Operating System :: OS Independent`, `Topic :: Software Development :: Build Tools`, and `Programming Language :: Python :: 3.12` and `3.13` (H3: "no version in between unless it is added to the matrix"). `Development Status`, the generic `Python :: 3` and `Topic :: Utilities` are kept as they are; B3 does not name them. The newest version is the one [53](53-ci-workflows.md)'s matrix names: 3.15, or 3.14 if 53 had to fall back (I2, Risks).

**`description`**: one sentence, the same text the root help shows. The design gives no wording. A sentence in the spirit of the project's own summary, for example "Install and pin TLA+ tool builds, compile Java override modules, and run TLC with readable output.", is the worker's to choose; it should name TLA+ and TLC and stay under about 100 characters, since PyPI and the root help both show it on one line.

Consumes: `scripts/check_wheel.py` and its `--list` (53).

## Tests that must pass

- `tests/unit/test_readme_links.py`, plain pytest, in the default suite: passes on the new README; fails on a README with one relative link (the test builds such a text itself and calls the same check, so it can fail, T12 rule 6).
- The wheel check: `uv run poe check-release` passes after `MANIFEST.in` is deleted; `scripts/check_wheel.py --list` run before and after the deletion gives the same wheel list and the same sdist list. Paste both diffs (empty) in the pull request. If the sdist list changes, stop and report: B2 says the packaged files are unchanged.
- B1 has no test (the YAML hook checks the file; the first monthly run shows whether the groups work).
- Every classifier is one PyPI knows: compare the list with the current `trove-classifiers` package once (for example `uv run --with trove-classifiers python -c ...`), and say so in the pull request. PyPI refuses an upload with an unknown classifier, and `twine check` does not look; `Programming Language :: Python :: 3.15` is the one to check (stage 4).

## Changelog

None. B1 to B3 have no Changelog paragraph, and nothing a user runs changes.

## Context for the worker

**The bounds and why** (B2, D59, "Upper caps", settled by the maintainer 2026-11-21). `typer>=0.27.2,<1.0.0`: 0.27.2 is the first with a public `typer.TyperException`, which [14 F10](../design/14-config-and-cli.md#f10-no-tracebacks) names; Typer is 0.x and tlaup reaches into two private modules, so the cap stays. `rich>=13.8.0`, no cap: `Console.on_broken_pipe` exists from 13.8.0, and research 30 found 13.8.0 to 15.0.0 behaving the same in the three ways tlaup relies on. `pydantic>=2.5.3`, no cap: the floor Typer 0.29 and later declare; research 30 found a model shaped like F1 and F3 working on every Pydantic 2.x on Python 3.11; installers pick the practical floor per Python by wheel availability. `filelock>=4.2.1`, no cap (23's line). No cap below the next major version for these runtime dependencies, for three reasons the design gives: a published cap cannot be lifted for releases already out; the weekly `deps-newest` job ([53](53-ci-workflows.md)) and the unit tests of R6 and F1 turn red when a new release breaks something, and a cap is then added in a new release; and caps on widely shared libraries make tlaup hard to install beside others or to package for a distribution. The development dependencies keep their caps.

**`setuptools>=77.0.3`**: the SPDX licence string `license = "MIT"` in `[project]` needs it. With it, setuptools adds the `LICENSE` file to the distributions by its default license-file patterns, which is one of the things `MANIFEST.in` did; the wheel and sdist lists before and after show whether that holds.

**`MANIFEST.in`** holds today `include LICENSE`, `include README.md`, `recursive-include src/tlaup/resources *.yaml`, `include src/tlaup/py.typed`, and after 09 the `tlaup_parse` line. Each is covered by the `readme` field, the licence default and the package data in `pyproject.toml`; the list comparison is the proof, not this reasoning. [06](06-lifeline-agent.md) notes that after the deletion only package data reaches the sdist, so the lifeline agent's Java source ships only if 06 made it package data. The jar itself is checked in and is package data (review finding A9), so it is in both lists before and after.

**The README links.** Today `README.md` has one relative link (`docs/examples/`); the switch packages may have added more by the time this runs. PyPI renders the same file and relative links are dead there. Use `https://github.com/<owner>/<repo>/tree/main/...` for a folder and `.../blob/main/...` for a file, with the owner and repository of the `Repository` address in `pyproject.toml`. The documentation track's README rewrite ([roadmap, line 494](../roadmap.md#documentation-track-parallel-start-with-milestone-1)) keeps both changes (B3); it is not designed and is not built here.

**Maintainer action** (B3): GitHub topics, with `gh repo edit --add-topic <topic>` for each keyword that makes sense as a topic. Write the command in the pull request description; do not run it.

**State of `main` when this starts.** `[build-system] requires = ["setuptools>=68.0"]`; `pydantic>=2.12.5,<3.0.0`; `rich>=13.8.0,<14.0.0` if 16 has merged (else `>=13.7.0,<14.0.0`); `typer>=0.27.2,<1.0.0` if 17 has merged; classifiers 3.11, 3.12, 3.13, `OS Independent`, `Build Tools`; `MANIFEST.in` present; `.python-version` 3.13 until [57](57-repo-hygiene.md).

## Done when

- `.github/dependabot.yml` exists as above.
- `pyproject.toml` has exactly the line changes listed; `uv lock` was run and `uv lock --check` passes.
- `MANIFEST.in` is gone and the before and after lists are identical.
- The README test passes and can fail; the README's links are absolute and the two install lines are there.
- The classifiers were checked against `trove-classifiers`.
- `uv run poe lint`, `uv run ruff format --check .`, `uv run poe test` and `uv run poe check-release` pass; CI is green, `deps-newest` included (it now installs the newest Rich and Pydantic).
- The pull request lists the GitHub topics command for the maintainer.

## Out of scope

- The `typer` floor (17), the `rich` floor (16), `filelock` (23), the development dependencies, and `pytest-mock`, which 03b removed with the old tests (decision D62).
- `.python-version` and the test that keeps the Python versions in step: [57](57-repo-hygiene.md).
- `project.urls.Changelog`: [55](55-release-tooling.md).
- The root help reading `description`: [50](50-help-and-messages.md).
- A lowest-versions CI job: rejected (I3).
- The README rewrite of the documentation track.

## Risks

- From B1: whether the groups behave as written is first seen on the first monthly run.
- From B2: the bounds rest on research 23 and 30; a new major release of Rich, Pydantic or filelock that breaks tlaup shows on `deps-newest`, and the answer is a cap with a comment in a new release.
- From the cut: four packages write lines of one `dependencies` list; each line's final text is fixed by D59, so a merge conflict is resolved by taking that text.
- If 53's matrix falls back from 3.15 to 3.14, the classifier must follow, and 57's test will say so.
