"""Startup cost (design 14 F9): what a fresh interpreter loads, read from `sys.modules`, never from a clock."""

import json
import os
import subprocess
import sys

HEAVY = "('requests','yaml','truststore','rich.progress','rich.live','tlaup.config.schema','tlaup.versioning.github')"
LOADED = f"print(sorted(m for m in {HEAVY} if m in sys.modules))"


def child(code: str) -> subprocess.CompletedProcess[str]:
    """Run the code in a new interpreter with the isolated environment of the test."""
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=dict(os.environ),
        timeout=60,
    )


def test_importing_the_cli_loads_none_of_the_heavy_modules() -> None:
    done = child(f"import tlaup.cli, sys; {LOADED}")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"


def test_a_command_without_settings_or_network_loads_none_of_them_either() -> None:
    code = (
        "import sys\n"
        "from typer.testing import CliRunner\n"
        "from tlaup.cli import app\n"
        "result = CliRunner().invoke(app, ['tool', 'dir'])\n"
        "print(result.exit_code)\n"
        f"{LOADED}\n"
    )
    done = child(code)
    assert done.returncode == 0, done.stderr
    assert done.stdout.split("\n")[:2] == ["0", "[]"]


def test_completion_is_off_unless_asked() -> None:
    code = (
        "import json, tlaup.cli\n"
        "import typer._click.shell_completion as sc\n"
        "print(json.dumps(sorted(sc._available_shells)))\n"
        "from typer._completion_classes import completion_init\n"
        "completion_init()\n"
        "print(json.dumps(sorted(sc._available_shells)))\n"
    )
    done = child(code)
    assert done.returncode == 0, done.stderr
    before, after = done.stdout.strip().split("\n")
    assert before == "[]"
    assert {"bash", "zsh", "fish"} <= set(json.loads(after))
