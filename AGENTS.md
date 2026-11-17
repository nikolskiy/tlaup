# Instructions for AI agents

`tlaup` is a command-line tool for TLA+: it installs and pins `tla2tools.jar` builds, compiles Java operator-override modules, and runs TLC with formatted output.

## Where to find more

Read [`docs/README.md`](docs/README.md) next. It lists every part of the documentation with when to read it; open only what the task needs. Before any planned work, read the roadmap's "How the work is done": it says which stage the work is in and what that stage may do.

## Always

- Use `uv` for everything; never `pip` or a global Python.
- Commit and push only when the maintainer asks. Before committing, read [`docs/contributing/conventions.md`](docs/contributing/conventions.md).
- No AI attribution or co-author trailers in commits or pull requests.
- Never commit personal or machine-specific data such as home folder paths or email addresses.
- This file stays short on purpose: put detail in the docs, link it from the index above it, and do not add it here. `CLAUDE.md` only includes this file; add nothing there either ([documentation conventions](docs/contributing/conventions.md#documentation)).
