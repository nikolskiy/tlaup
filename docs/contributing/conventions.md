# Conventions

Rules for commits, the changelog, code and what may be committed. They apply to people and agents alike.

## Commits

- Commits follow Conventional Commits: `feat:`, `fix:`, `docs(scope):`, `chore(deps):`, `test:`, `refactor:`; `!` marks a breaking change.
- No AI attribution or co-author trailers in commit messages or pull request descriptions.
- Commit and push only when the maintainer asks.
- Run `uv run poe lint` and `uv run poe test` before committing ([development](development.md#environment-and-commands)).
- Commits use the GitHub noreply address `nikolskiy@users.noreply.github.com`. GitHub rejects pushes that expose a private email.

## Changelog

Every user-visible change gets a `CHANGELOG.md` entry in the same commit, under `## [Unreleased]`, using the Keep a Changelog headings plus `Breaking` and `Removed`. For a rename or removal, say what it was and what it is now.

## Compatibility and versions

- No aliases, compatibility shims or migrations for old names, commands, folders or layouts. The project prefers clean breaks while it has few users (roadmap decision D14).
- From 0.9.0 on, minor versions carry breaking changes and features, and patch versions carry only fixes (roadmap decision D27).

## Code

Line length is 120; target Python is 3.11; mypy runs in strict mode on `src`.

## Secrets and personal data

- When `detect-secrets` flags something, check the value. If it is a false positive, exclude only that value or that exact line shape (an `exclude_lines` pattern in `.secrets.baseline`), never a whole file or folder. Linters such as ruff may skip a folder.
- Never commit personal or machine-specific data: home folder paths, agent scratch paths, IP or MAC addresses, email addresses other than GitHub noreply ones, shell prompts showing a user and host, or local network host names. Use placeholders such as `<repo>` and `<tmp>` in captured output. The `no-*` hooks in `.pre-commit-config.yaml` check for them; an exception names the exact value in the hook's pattern (as `127.0.0.1` and `git@github.com` are) and is only for a value that is the same on every machine or is a public address. The `no-machine-files` hook and `.gitignore` also refuse whole files that carry such data: JVM crash logs, heap dumps, `.env` files, keys, stored credentials, shell and REPL history, editor settings and `.claude/settings.local.json`.

## Documentation

- Keep documentation plain and specific: say what was checked and what was not.
- Organize it by progressive disclosure. `AGENTS.md` holds only what every task needs and points to [`docs/README.md`](../README.md); each index says, per document, when to read it; detail lives one level further down. A new document gets a line in the index above it, and nothing is said in two places: link instead of repeating.
