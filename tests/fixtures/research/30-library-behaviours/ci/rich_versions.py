"""Question 30: run the Rich probes against several Rich versions, each in its own uv environment.

Needs `uv` on PATH (it downloads rich, typer and pyte from PyPI). Run from the `ci` folder:
    python q30/rich_versions.py
rich_pipe_probe.py runs on every OS (the `| head -1` cases only on POSIX); rich_live_pty_probe.py runs where
Python has a pty (Linux, macOS) and prints SKIP elsewhere. Exits 0 whatever the outcome.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# 13.8.0: first with Console.on_broken_pipe and the lowest Typer 0.29.1 allows; 13.9.4: locked; then the newest
# 14.x and the newest release.
VERSIONS = ["13.8.0", "13.9.4", "14.3.4", None]
OS = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
HERE = Path(__file__).parent


def run(args: list[str], label: str) -> None:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=300)
        sys.stdout.write(out.stdout)
        if out.returncode or "RESULT" not in out.stdout:
            tail = "\n".join(out.stderr.strip().splitlines()[-5:])
            print(f"RESULT q30 rich-versions {OS} : ERROR for {label}, exit {out.returncode}: {tail}")
    except subprocess.TimeoutExpired:
        print(f"RESULT q30 rich-versions {OS} : ERROR for {label}: timed out after 300 s")
    sys.stdout.flush()


def main() -> None:
    uv = shutil.which("uv")
    if uv is None:
        print(f"RESULT q30 rich-versions {OS} : SKIP - uv is not on PATH")
        return
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    for v in VERSIONS:
        rich = f"rich=={v}" if v else "rich"
        print(f"--- {rich} (Python {py})", flush=True)
        base = [uv, "run", "--no-project", "-q", "-p", py, "--with", rich]
        run([*base, "--with", "typer==0.29.1", "python", str(HERE / "rich_pipe_probe.py")], f"{rich} pipe")
        run([*base, "--with", "pyte", "python", str(HERE / "rich_live_pty_probe.py")], f"{rich} live")


if __name__ == "__main__":
    main()
    sys.exit(0)
