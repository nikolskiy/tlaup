"""The real jars of the integration tests and the Java they run on (design 01 T9; package 52).

``TLAUP_TEST_JARS`` names a folder whose direct subfolders each hold one ``tla2tools.jar``: a folder made by hand
(``<root>/v1.7.4/tla2tools.jar``) or the store's own tool folder, whose build folders carry a ``build.json``. Each jar
is matched to a TLC golden folder by release line (T3). Shared by ``tests/integration/conftest.py``, the
``test-integration`` task and the REPL case of ``tests/lifeline/``; it reads the variable only when asked, so the
callers read it at collection time, before the isolation fixture removes every ``TLAUP_*`` variable.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from tests.parse.drive import build_folders, line_of
from tlaup.java.locate import locate
from tlaup.versioning.jarinfo import read_jar
from tlaup.versioning.store import Source, ToolStore

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from tlaup.paths import AppPaths
    from tlaup.versioning.jarinfo import JarInfo
    from tlaup.versioning.store import Build

VARIABLE = "TLAUP_TEST_JARS"
JAR = "tla2tools.jar"
RECORD = "build.json"  # a store's build folder (12 V1)

# Removed before every test, besides every TLAUP_* variable: the root isolation fixture's list without JAVA_HOME,
# and the JVM's own option variables, which would reach every real JVM (T2). Used by this folder's fixture and by
# the REPL case of tests/lifeline/.
REMOVED_VARIABLES = (
    "JAVA_OPTS",
    "JDK_JAVA_OPTIONS",
    "JAVA_TOOL_OPTIONS",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "EDITOR",
    "VISUAL",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "FORCE_COLOR",
    "CLICOLOR_FORCE",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)

HOW_TO_SET = f"""\
{VARIABLE} is not set: the integration tests need real jars and a JDK.
Set it to a folder that holds one subfolder per build, each with its {JAR}:

    <folder>/v1.7.4/{JAR}       the stable release, named by its tag
    <folder>/rolling/{JAR}      a rolling build (any name; its build time picks the rolling expectations)

A store's own tool folder (`tlaup tool dir`) has that shape too. Then run:

    {VARIABLE}=<folder> uv run poe test-integration
"""


@dataclass(frozen=True)
class TestJar:
    __test__ = False  # a dataclass, not a test class for pytest to collect

    build: str  # the build's name: build.json's "name" when the folder has one (a store's), else the folder's name
    jar: Path  # <TLAUP_TEST_JARS>/<folder>/tla2tools.jar
    info: JarInfo  # read_jar(jar)
    golden: Path  # the tlc/ golden folder matched by release line (T3, T9)
    line: str  # "stable" or "rolling", line_of(golden)


def jar_folders(root: Path) -> list[Path]:
    """The direct subfolders of ``root`` that hold a jar; hidden ones (a store's ``.tmp/``) are skipped."""
    return sorted(folder for folder in root.iterdir() if not folder.name.startswith(".") and (folder / JAR).is_file())


def _name(folder: Path) -> str:
    record = folder / RECORD
    if record.is_file():
        name = json.loads(record.read_text(encoding="utf-8")).get("name")
        if isinstance(name, str) and name:
            return name
    return folder.name


def _tags() -> dict[str, Path]:
    """The stable golden folders by tag, and the rolling one under the key ``rolling``."""
    found: dict[str, Path] = {}
    for golden in build_folders("tlc"):
        if line_of(golden) == "rolling":
            found["rolling"] = golden
        else:
            found[str(tomllib.loads((golden / "build.toml").read_text(encoding="utf-8"))["tag"])] = golden
    return found


def find_test_jars(root: Path) -> list[TestJar]:
    """Every build under ``root``, each with its golden folder; ``ValueError`` naming a jar that matches none."""
    folders = _tags()
    jars = []
    for folder in jar_folders(root):
        jar = folder / JAR
        info = read_jar(jar)
        name = _name(folder)
        golden = folders.get("rolling") if info.built_at is not None else folders.get(name)
        if golden is None:
            listed = ", ".join(f"{key} ({path.name})" for key, path in sorted(folders.items()))
            line = "a rolling build" if info.built_at is not None else f"a stable build named {name!r}"
            message = (
                f"{jar} is {line}, which matches no golden folder of tests/parse/golden/tlc/; "
                f"the folders there are: {listed}. A stable jar's folder (or its build.json) must be named by its tag."
            )
            raise ValueError(message)
        jars.append(TestJar(build=name, jar=jar, info=info, golden=golden, line=line_of(golden)))
    return jars


def find_java(env: Mapping[str, str]) -> str | None:
    """``java`` as tlaup finds it, by tlaup's own ``locate``: ``JAVA_HOME/bin`` first, then ``PATH`` (13 J2)."""
    tool = locate("java", env).tool
    return None if tool is None else str(tool.path)


def missing(env: Mapping[str, str]) -> str | None:
    """Why the integration tests cannot run here, or None: no variable, no folder, no jar in it, or no ``java``."""
    value = env.get(VARIABLE)
    if not value:
        return f"{VARIABLE} is not set"
    root = Path(value)
    if not root.is_dir():
        return f"{VARIABLE} names {value}, which is not a folder"
    if not jar_folders(root):
        return f"{VARIABLE} names {value}, which holds no <build>/{JAR}"
    if find_java(env) is None:
        return "java was found neither in JAVA_HOME/bin nor on PATH"
    return None


def install(paths: AppPaths, jar: TestJar) -> Build:
    """Copy ``jar`` into the store of ``paths`` through the store's own API and pin it (12 V1, package 23).

    ``add`` takes only a jar inside one of the store's temporary folders and needs the store lock, as ``pin`` does.
    """
    store = ToolStore(paths, now=lambda: datetime.now(UTC))
    source = Source(kind="local", url=jar.jar.as_uri(), asset_id=None, asset_updated_at=None, digest_checked=False)
    with store.locked():
        tmp = store.new_tmp()
        tmp.lock()
        try:
            tmp.make()
            copy = tmp.path / JAR
            shutil.copyfile(jar.jar, copy)
            name = "rolling" if jar.line == "rolling" else jar.build
            build = store.add(copy, jar.info, name=name, prerelease=jar.line == "rolling", source=source)
            store.pin(build)
        finally:
            tmp.release()
    return build


def main(argv: Sequence[str] | None = None) -> int:
    """``uv run poe test-integration``: refuse with nothing to run, else run ``tests/integration`` (package 52).

    A plain ``pytest tests/integration`` skips the folder with the reason instead; the task fails, so that a job
    whose jars or Java are missing cannot pass with nothing run.
    """
    reason = missing(os.environ)
    if reason is not None:
        if not os.environ.get(VARIABLE):
            print(HOW_TO_SET, file=sys.stderr)
        else:
            print(f"test-integration: {reason}", file=sys.stderr)
        return 1
    args = list(sys.argv[1:] if argv is None else argv)
    command = [sys.executable, "-m", "pytest", "tests/integration", "--no-cov", *args]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
