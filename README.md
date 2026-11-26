# tlaup

Command-line tool for working with TLA+ specifications and the TLC model checker.

> **Formerly `tlaplus-cli`.** The project, the PyPI package and the command were renamed to `tlaup` in 0.8.2.
> The old `tla` command is gone; use `tlaup` instead. From the next release `tlaup` keeps its toolsets, modules and config in its own `tlaup` folders,
> so install toolsets and add modules again. Nothing is moved over; the old `tla` folders (on Linux `~/.config/tla` and `~/.cache/tla`) can be deleted.

## Project Goals

1. Simplify managing TLA+ tools such as TLC, community modules, custom modules, etc.
2. Run TLA tools in a single CLI interface.
3. Manage and display the tool outputs.

## Quick Start & Usage

### 1. Toolset Management (`tlaup tool`)
* `tlaup check-java`: Verify Java installation and compatibility.
* `tlaup tool list`: List available and installed toolset versions (`tla2tools.jar`).
* `tlaup tool install [vX.Y.Z]`: Download and install a toolset version.
* `tlaup tool pin <version>`: Set default toolset version for TLC runs.

### 2. Model Checking (`tlaup tlc`)
* `tlaup tlc <spec>`: Execute TLC model checker on a specification.
* `tlaup tlc <spec> --show-command`: Inspect exact JVM command before execution.

### 3. Custom Java Modules (`tlaup module`)
* `tlaup module add <path>`: Compile Java operator overrides and register the module under the folder's name.
* `tlaup module list`: Display the registered modules and when each was built (UTC).
* `tlaup module remove <name>`: Remove a registered module.
* `tlaup module dir`: Print the folder that holds the registered modules.

For complete, runnable specifications and Java module examples, see [docs/examples](docs/examples/).

## Quick Installation

### Via `uv tool`
```bash
uv tool install tlaup
```

If you installed the old package, remove it first:
```bash
uv tool uninstall tlaplus-cli
```
