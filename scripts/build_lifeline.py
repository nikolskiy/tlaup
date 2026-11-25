"""Build ``src/tlaup/java/lifeline.jar`` from the agent's source (design 20 G3, "The jar").

``uv run poe build-lifeline [output]``. The jar is checked in; the lifeline tests compile the same source with
``compile_agent`` and compare the class files. Build with the JDK the lifeline job uses (Temurin 11): the bytes
of a class file can differ between compilers.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "src" / "tlaup" / "java" / "lifeline" / "Lifeline.java"
DEFAULT_JAR = REPO_ROOT / "src" / "tlaup" / "java" / "lifeline.jar"
PREMAIN_CLASS = "tlaup.lifeline.Lifeline"
RELEASE = "11"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)  # fixed, so that the same classes make the same jar


def find_javac() -> str:
    """``javac`` from ``JAVA_HOME`` first, then ``PATH``."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        found = shutil.which("javac", path=str(Path(java_home) / "bin"))
        if found:
            return found
    found = shutil.which("javac")
    if found is None:
        msg = "javac not found: set JAVA_HOME to a JDK or put javac on PATH"
        raise SystemExit(msg)
    return found


def javac_version(javac: str) -> str:
    """The first line ``javac -version`` prints, for example ``javac 11.0.25``."""
    done = subprocess.run([javac, "-version"], capture_output=True, text=True, check=True)
    return (done.stdout + done.stderr).strip().splitlines()[0]


def compile_agent(out_dir: Path, javac: str | None = None) -> list[Path]:
    """Compile the agent with ``--release 11`` into ``out_dir``; return the class files, sorted."""
    subprocess.run(
        [javac or find_javac(), "--release", RELEASE, "-Xlint:all", "-Werror", "-d", str(out_dir), str(SOURCE)],
        check=True,
    )
    return sorted(out_dir.rglob("*.class"))


def write_jar(jar: Path, classes_dir: Path, classes: list[Path], built_with: str) -> None:
    manifest = f"Manifest-Version: 1.0\r\nPremain-Class: {PREMAIN_CLASS}\r\nCreated-By: {built_with}\r\n\r\n"
    jar.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as archive:
        entries = [("META-INF/MANIFEST.MF", manifest.encode("ascii"))]
        entries += [(path.relative_to(classes_dir).as_posix(), path.read_bytes()) for path in classes]
        for name, data in entries:
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_JAR, help="the jar to write")
    args = parser.parse_args(argv)
    javac = find_javac()
    with tempfile.TemporaryDirectory() as tmp:
        classes_dir = Path(tmp)
        classes = compile_agent(classes_dir, javac)
        write_jar(args.output, classes_dir, classes, javac_version(javac))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
