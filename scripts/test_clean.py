"""The clean-home check (design 01 T2, "Proof that it holds"; 30 I2).

Without arguments: run the test suite with ``HOME`` and ``USERPROFILE`` set to an empty
temporary folder and the ``XDG_*`` and ``TLAUP_*`` variables removed, then fail if a tlaup
folder or ``.tlaplus`` appeared in it. Arguments after ``--`` go to pytest.

With ``--home <folder>``: only the check, on that folder (CI's last step, on the runner's home).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Where tlaup 0.8.x and the new tool keep their folders under a home, on every system.
TLAUP_FOLDERS = (
    Path(".config/tlaup"),
    Path(".cache/tlaup"),
    Path(".local/share/tlaup"),
    Path("Library/Application Support/tlaup"),
    Path("Library/Caches/tlaup"),
    Path(".tlaplus"),
)
REPO_ROOT = Path(__file__).resolve().parent.parent


def find_tlaup_folders(home: Path) -> list[Path]:
    """The tlaup folders, and ``.tlaplus``, that exist under ``home``."""
    return [home / folder for folder in TLAUP_FOLDERS if (home / folder).exists()]


def check(home: Path) -> int:
    found = find_tlaup_folders(home)
    for folder in found:
        print(f"test-clean: tlaup folder found under the home: {folder}", file=sys.stderr)
    if found:
        return 1
    print(f"test-clean: no tlaup folder under {home}")
    return 0


def run_suite(home: Path, pytest_args: list[str]) -> int:
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("XDG_", "TLAUP_")) and name not in {"HOME", "USERPROFILE"}
    }
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    command = [sys.executable, "-m", "pytest", *pytest_args]
    return subprocess.run(command, cwd=REPO_ROOT, env=env, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", type=Path, help="check this folder only; run no tests")
    parser.add_argument("pytest_args", nargs="*", help="passed to pytest (after --)")
    options = parser.parse_args(argv)
    if options.home is not None:
        return check(options.home)
    with tempfile.TemporaryDirectory(prefix="tlaup-clean-home-") as folder:
        home = Path(folder)
        code = run_suite(home, options.pytest_args)
        for entry in sorted(home.rglob("*")):
            print(f"test-clean: left in the home: {entry.relative_to(home)}")
        found = check(home)
    return code or found


if __name__ == "__main__":
    sys.exit(main())
