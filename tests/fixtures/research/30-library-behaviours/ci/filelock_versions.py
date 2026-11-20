"""Question 30: run filelock_probe.py against several filelock versions, each in its own uv environment.

Needs `uv` on PATH (it downloads the filelock wheels from PyPI). Run from the `ci` folder:
    python q30/filelock_versions.py
The versions are the edges found on Linux: 3.20.3 (no re-check), 3.20.4 (first re-check, deletes on release),
3.29.4 (last that deletes on release), 3.29.5 (keeps the file, truncates it), 4.2.0 (last that truncates),
4.2.1 (first with everything R6 relies on on Linux), 4.2.10 (locked), and the newest release.
Exits 0 whatever the outcome.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

VERSIONS = ["3.20.3", "3.20.4", "3.29.4", "3.29.5", "4.2.0", "4.2.1", "4.2.10", None]
OS = {"linux": "linux", "darwin": "macos", "win32": "windows"}.get(sys.platform, sys.platform)
PROBE = Path(__file__).with_name("filelock_probe.py")


def main() -> None:
    uv = shutil.which("uv")
    if uv is None:
        print(f"RESULT q30 filelock-versions {OS} : SKIP - uv is not on PATH")
        return
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    for v in VERSIONS:
        spec = f"filelock=={v}" if v else "filelock"
        print(f"--- {spec} (Python {py})", flush=True)
        try:
            out = subprocess.run(
                [uv, "run", "--no-project", "-q", "-p", py, "--with", spec, "python", str(PROBE)],
                capture_output=True, text=True, timeout=300, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            sys.stdout.write(out.stdout)
            if out.returncode or not out.stdout.strip():
                tail = "\n".join(out.stderr.strip().splitlines()[-5:])
                print(f"RESULT q30 filelock-versions {OS} : ERROR for {spec}, exit {out.returncode}: {tail}")
        except subprocess.TimeoutExpired:
            print(f"RESULT q30 filelock-versions {OS} : ERROR for {spec}: timed out after 300 s")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
    sys.exit(0)
