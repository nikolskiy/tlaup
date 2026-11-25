"""Fixtures of the lifeline tests (design 20 G3; package 06). They need a real JDK and run only when asked for."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.lifeline.procs import find_tool

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
JAR = REPO_ROOT / "src" / "tlaup" / "java" / "lifeline.jar"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_lifeline.py"
JAVA_SOURCES = Path(__file__).parent / "java"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    here = Path(__file__).parent
    for item in items:
        if here in Path(str(item.path)).parents:
            item.add_marker(pytest.mark.lifeline)


@pytest.fixture(autouse=True)
def isolated() -> Iterator[None]:
    """Replaces the root fixture of the same name: these tests keep the real PATH and JAVA_HOME (01 T10)."""
    yield


@pytest.fixture(scope="session")
def jar() -> Path:
    """The jar that ships, not one built for the test."""
    assert JAR.is_file(), f"{JAR} is missing: run `uv run poe build-lifeline`"
    return JAR


@pytest.fixture(scope="session")
def java() -> str:
    return find_tool("java")


@pytest.fixture(scope="session")
def build_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_lifeline_script", BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def test_classes(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The folder with the classes the tests start: a JVM that sleeps, and the reused-id stand-in."""
    out = tmp_path_factory.mktemp("classes")
    sources = sorted(str(path) for path in JAVA_SOURCES.glob("*.java"))
    subprocess.run([find_tool("javac"), "--release", "11", "-d", str(out), *sources], check=True)
    return out
