# Instructions for AI agents

`tlaup` is a command-line tool for TLA+: it installs and pins `tla2tools.jar` builds, compiles Java operator-override modules, and runs TLC with formatted output. Its purpose is to bring the TLA+ tools together and help them work together; a reproducible toolchain, the same jar and modules on every machine, is an important part of that but not all of it. It was called `tlaplus-cli` (command `tla`) until 0.8.2; that project is archived and only forwards to this one.

## Start here

Read these before planning or changing anything:

1. `docs/analysis/00-summary.md`: what the six analysis reports found, with links to each report.
2. `docs/roadmap.md`: the single source of truth. It holds the purpose, how the work is done (a five-stage agent pipeline: completeness pass, investigation, design in waves, work packages, workers, with review gates between stages), the decisions (D1 to D45), the milestones and the investigation list. Ticked items are done; dated notes record partial progress.

3. `docs/design/README.md`: the index of the design documents (pipeline stage 3, first wave), written 2026-11-15, reviewed three times by fresh agents (twice that day, once on 2026-11-16) and revised after each; it awaits the maintainer's sign-off. It lists the decisions made in the wave, where the design departs from the roadmap, and what waits on an investigation; `review-2026-11-15.md` beside it holds the review's findings. Read `00-overview.md`, `01-testing.md`, `02-cross-cutting.md` and the document for the area you work on.

The completeness pass (pipeline stage 1) was reviewed and signed off on 2026-11-14. `docs/analysis/07-walkthrough-notes.md` is history: every decision in it is restated in the roadmap, nothing in it needs reading, and where the two differ the roadmap is right. Later stages read only the roadmap and the design documents. Stages 3 and 4 end with a review by a fresh agent and the maintainer's sign-off; do not start the next stage without it. Each worker pull request needs green CI and a separate agent's review before it merges.

The analysis reports describe release 0.8.1. Line numbers in them may drift as code changes; check the source before relying on one.

## Layout

- `src/tlaup/`: the package. `cli.py` builds the Typer app; `cmd/` holds one module per command or command group; `tlc/` runs TLC and parses its output; `versioning/` downloads and tracks jar builds; `java/` finds Java and builds classpaths; `config/` loads settings.
- `src/tlaup/resources/default_config.yaml`: packaged defaults. Its top-level `tla:` key holds upstream TLA+ download URLs; it is not the application name.
- `tests/unit/`: the default test suite. `tests/integration/`: needs Java and an installed jar, not run in CI yet.
- `docs/examples/`: example specs, some with custom Java modules.
- `docs/research/`: investigation results (pipeline stage 2), one file per question, indexed by its `README.md`.
- `docs/design/`: design documents (pipeline stage 3), one per area, indexed by its `README.md`. They describe the code as it will be, not as it is: the packages, commands and test layout they name do not exist until the work packages are built.

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
- No aliases, compatibility shims or migrations for old names, commands, folders or layouts. The project prefers clean breaks while it has few users (roadmap decision D14).
- From 0.9.0 on, minor versions carry breaking changes and features, and patch versions carry only fixes (roadmap decision D27).
- Line length is 120; target Python is 3.11; mypy runs in strict mode on `src`.
- When `detect-secrets` flags something, check the value. If it is a false positive, exclude only that value or that exact line shape (an `exclude_lines` pattern in `.secrets.baseline`), never a whole file or folder. Linters such as ruff may skip a folder.
- Never commit personal or machine-specific data: home folder paths, agent scratch paths, IP or MAC addresses, email addresses other than GitHub noreply ones, shell prompts showing a user and host, or local network host names. Use placeholders such as `<repo>` and `<tmp>` in captured output. The `no-*` hooks in `.pre-commit-config.yaml` check for them; an exception names the exact value in the hook's pattern (as `127.0.0.1` and `git@github.com` are) and is only for a value that is the same on every machine or is a public address. The `no-machine-files` hook and `.gitignore` also refuse whole files that carry such data: JVM crash logs, heap dumps, `.env` files, keys, stored credentials, shell and REPL history, editor settings and `.claude/settings.local.json`.
- Keep documentation plain and specific: say what was checked and what was not.

## Releases

1. Set the version: `uv version X.Y.Z`.
2. Rename `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD`.
3. Run `uv run poe check-release` and the tests; commit on `main`.
4. Run `scripts/release.sh` from a clean `main`. It checks the changelog entry, tags `vX.Y.Z` and pushes `main` and the tag.
5. `.github/workflows/release.yml` builds, creates the GitHub Release and publishes to PyPI through trusted publishing (environment `pypi`).

Repository rules: `main` cannot be deleted or force-pushed; `v*` tags cannot be moved or deleted by anyone, so a bad tag means a new version number; the `pypi` environment deploys only from `v*` tags.
