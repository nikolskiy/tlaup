# Instructions for AI agents

`tlaup` is a command-line tool for TLA+: it installs and pins `tla2tools.jar` builds, compiles Java operator-override modules, and runs TLC with formatted output. Its purpose is a reproducible TLA+ toolchain, the same jar and modules on every machine. It was called `tlaplus-cli` (command `tla`) until 0.8.2; that project is archived and only forwards to this one.

## Start here

Read these before planning or changing anything:

1. `docs/analysis/00-summary.md`: what the six analysis reports found, with links to each report.
2. `docs/roadmap.md`: the decisions (D1 to D5) and the milestones. Ticked items are done; dated notes record partial progress.
3. `docs/analysis/07-walkthrough-notes.md`: decisions made with the maintainer after the reports. Note 4 describes how the work is done: a five-stage agent pipeline (completeness pass, investigation, design in waves, work packages, workers) with review gates between stages. The "Raised, not decided" list at the end is input for the completeness pass.

Until the completeness pass (pipeline stage 1) is finished, the notes are newer than the roadmap and win where they disagree. Once it is finished, the roadmap is the single source of truth, the notes are history, and later stages read only the roadmap and the design documents. Stages 1, 3 and 4 end with a review by a fresh agent and the maintainer's sign-off; do not start the next stage without it. Each worker pull request needs green CI and a separate agent's review before it merges.

The analysis reports describe release 0.8.1. Line numbers in them may drift as code changes; check the source before relying on one.

## Layout

- `src/tlaup/`: the package. `cli.py` builds the Typer app; `cmd/` holds one module per command or command group; `tlc/` runs TLC and parses its output; `versioning/` downloads and tracks jar builds; `java/` finds Java and builds classpaths; `config/` loads settings.
- `src/tlaup/resources/default_config.yaml`: packaged defaults. Its top-level `tla:` key holds upstream TLA+ download URLs; it is not the application name.
- `tests/unit/`: the default test suite. `tests/integration/`: needs Java and an installed jar, not run in CI yet.
- `docs/examples/`: example specs, some with custom Java modules.

Config, toolsets, modules and the run cache live in the platform's user folders under the name `tlaup` (on Linux `~/.config/tlaup` and `~/.cache/tlaup`), set by `_APP_NAME` in `src/tlaup/config/loader.py`.

## Commands

Use `uv` for everything; do not call `pip` or a global Python.

```bash
uv sync --all-extras --dev     # set up the environment
uv run poe test                # unit tests with coverage
uv run poe lint                # ruff check, bandit, mypy (strict)
uv run poe check               # all pre-commit hooks on all files
uv run pytest tests/integration  # needs Java 11+ and `uv run tlaup tools install`
uv run poe check-release       # hooks, build, twine check
```

CI (`.github/workflows/test.yml`) runs lint and unit tests on every push to `main` and on every pull request. Run `uv run poe lint` and `uv run poe test` before committing.

`ruff format` is not enforced yet and several files are unformatted. Do not reformat files you are not otherwise changing; format enforcement is its own roadmap item.

## Conventions

- Commits follow Conventional Commits: `feat:`, `fix:`, `docs(scope):`, `chore(deps):`, `test:`, `refactor:`; `!` marks a breaking change.
- No AI attribution or co-author trailers in commit messages or pull request descriptions.
- Commit and push only when the maintainer asks.
- Commits use the GitHub noreply address `nikolskiy@users.noreply.github.com`. GitHub rejects pushes that expose a private email.
- Every user-visible change gets a `CHANGELOG.md` entry in the same commit, under `## [Unreleased]`, using the Keep a Changelog headings plus `Breaking` and `Removed`. For a rename or removal, say what it was and what it is now.
- No aliases or compatibility shims for old names, commands or folders. The project prefers clean breaks while it has few users (walkthrough notes 8 and 44).
- Line length is 120; target Python is 3.11; mypy runs in strict mode on `src`.
- Keep documentation plain and specific: say what was checked and what was not.

## Releases

1. Set the version: `uv version X.Y.Z`.
2. Rename `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD`.
3. Run `uv run poe check-release` and the tests; commit on `main`.
4. Run `scripts/release.sh` from a clean `main`. It checks the changelog entry, tags `vX.Y.Z` and pushes `main` and the tag.
5. `.github/workflows/release.yml` builds, creates the GitHub Release and publishes to PyPI through trusted publishing (environment `pypi`).

Repository rules: `main` cannot be deleted or force-pushed; `v*` tags cannot be moved or deleted by anyone, so a bad tag means a new version number; the `pypi` environment deploys only from `v*` tags.
