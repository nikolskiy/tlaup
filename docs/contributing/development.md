# Development

How to set up, run the checks, and find your way around the code as it is today. The code described here is release 0.8.x; the design documents in [`../design/`](../design/README.md) describe the code as it will be, and their packages, commands and test layout do not exist until the work packages are built.

## Environment and commands

Use `uv` for everything; do not call `pip` or a global Python.

```bash
uv sync --all-extras --dev     # set up the environment
uv run poe test                # unit tests with coverage
uv run poe lint                # ruff check, bandit, mypy (strict)
uv run poe format              # ruff format, Python files and Python blocks in Markdown
uv run poe check               # all pre-commit hooks on all files
uv run pytest tests/integration  # needs Java 11+ and `uv run tlaup tools install`
uv run poe check-release       # hooks, build, twine check
```

Run `uv run poe lint` and `uv run poe test` before committing.

## CI

`.github/workflows/test.yml` runs lint, the format check (`uv run ruff format --check .`) and unit tests on every push to `main` and on every pull request.

## Code map

- `src/tlaup/`: the package. `cli.py` builds the Typer app; `cmd/` holds one module per command or command group; `tlc/` runs TLC and parses its output; `versioning/` downloads and tracks jar builds; `java/` finds Java and builds classpaths; `config/` loads settings.
- `src/tlaup/resources/default_config.yaml`: packaged defaults. Its top-level `tla:` key holds upstream TLA+ download URLs; it is not the application name.
- `tests/unit/`: the default test suite. `tests/integration/`: needs Java and an installed jar, not run in CI yet. `tests/fixtures/research/`: captured evidence from the investigations, each folder with its own README.
- `docs/examples/`: example specs, some with custom Java modules.

## Where tlaup keeps its files

Config, toolsets, modules and the run cache live in the platform's user folders under the name `tlaup` (on Linux `~/.config/tlaup` and `~/.cache/tlaup`), set in `src/tlaup/paths.py`.

## Running tlaup without touching your own folders

A `tlaup` command run by hand, or by an agent checking something, uses those real folders: `tools uninstall` or a cache cleanup there removes the maintainer's own toolchain. Point tlaup at temporary folders instead, on the `tlaup` command only:

```bash
TLAUP_HOME=<tmp>/tlaup uv run tlaup tools list
```

`TLAUP_HOME` is tlaup's own variable, so it moves config, cache and data together and no other tool (`gh`, `git`, `uv`) reads it; `TLAUP_CONFIG_DIR`, `TLAUP_CACHE_DIR` and `TLAUP_DATA_DIR` move one folder each ([design 14 F2](../design/14-config-and-cli.md#f2-folder-overrides)). The test isolation uses it too ([design 01 T2](../design/01-testing.md#t2-isolation)).
