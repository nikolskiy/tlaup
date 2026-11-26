"""Check the built wheel and sdist, and run the wheel in a fresh environment (design 30 I4).

``dist/`` (or ``--dist``) must hold exactly one wheel and one sdist. The wheel must carry the
files a run needs, nothing from ``tests/``, and no Python module without a file under ``src/``
(what a stale ``build/lib`` leaves behind). The wheel is then installed into a new virtual
environment with nothing else in it, and its commands are run there with ``HOME``,
``USERPROFILE`` and ``TLAUP_HOME`` under a temporary folder.

``--list`` prints the wheel's and the sdist's file lists, sorted, and checks nothing else.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED = (
    "tlaup/__init__.py",
    "tlaup_parse/__init__.py",
    "tlaup/resources/default_config.yaml",
    "tlaup/java/lifeline.jar",
    "tlaup/py.typed",
    "tlaup_parse/py.typed",
)
# Commands run from the installed wheel; each must exit 0. 29 renamed the group to `tool`.
SMOKE_COMMANDS = (
    ("tlaup", "--version"),
    ("tlaup", "--help"),
    ("tlaup", "tool", "dir"),
    ("python", "-c", "import tlaup_parse"),
)


def find_dist_files(dist: Path) -> tuple[Path, Path]:
    """The one wheel and the one sdist in ``dist``, or ``SystemExit`` naming what is there."""
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        found = ", ".join(p.name for p in sorted(dist.iterdir())) if dist.is_dir() else "no folder"
        message = f"check-wheel: {dist} must hold exactly one .whl and one .tar.gz; found: {found}"
        raise SystemExit(message)
    return wheels[0], sdists[0]


def wheel_names(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        return sorted(archive.namelist())


def sdist_names(sdist: Path) -> list[str]:
    with tarfile.open(sdist) as archive:
        return sorted(archive.getnames())


def content_problems(names: list[str], src: Path) -> list[str]:
    """What is wrong with the wheel's file list."""
    problems = [f"missing from the wheel: {name}" for name in REQUIRED if name not in names]
    problems += [f"in the wheel but must not be: {name}" for name in names if name.startswith(("tests/", "tests\\"))]
    for name in names:
        is_module = name.endswith(".py") and name.split("/")[0] in ("tlaup", "tlaup_parse")
        if is_module and not (src / name).is_file():
            problems.append(f"a module with no file under src/ (stale build/lib?): {name}")
    return problems


def smoke_env(tmp: Path) -> dict[str, str]:
    env = dict(os.environ)
    for name in ("PYTHONPATH", "VIRTUAL_ENV", "UV_PYTHON"):
        env.pop(name, None)
    home = tmp / "home"
    home.mkdir()
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        TLAUP_HOME=str(tmp / "tlaup-home"),
        NO_COLOR="1",
    )
    return env


def install_and_run(wheel: Path) -> list[str]:
    """Install the wheel into a new environment and run the smoke commands."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="check-wheel-") as name:
        tmp = Path(name)
        env = smoke_env(tmp)
        venv = tmp / "venv"
        subprocess.run(["uv", "venv", str(venv)], check=True, env=env)
        bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
        suffix = ".exe" if os.name == "nt" else ""
        subprocess.run(["uv", "pip", "install", "--python", str(venv), str(wheel)], check=True, env=env)
        for command in SMOKE_COMMANDS:
            argv = [str(bin_dir / (command[0] + suffix)), *command[1:]]
            result = subprocess.run(argv, env=env, cwd=tmp, capture_output=True, text=True, check=False)
            shown = " ".join(command)
            if result.returncode != 0:
                problems.append(f"`{shown}` exited {result.returncode}: {result.stderr.strip()[-500:]}")
            else:
                print(f"check-wheel: ok: {shown}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=REPO_ROOT / "dist")
    parser.add_argument("--list", action="store_true", help="print the file lists and stop")
    args = parser.parse_args(argv)
    wheel, sdist = find_dist_files(args.dist)
    if args.list:
        print(f"== {wheel.name}")
        print("\n".join(wheel_names(wheel)))
        print(f"== {sdist.name}")
        print("\n".join(sdist_names(sdist)))
        return 0
    problems = content_problems(wheel_names(wheel), REPO_ROOT / "src")
    if not problems:
        problems = install_and_run(wheel)
    for problem in problems:
        print(f"check-wheel: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"check-wheel: {wheel.name} and {sdist.name} are as expected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
