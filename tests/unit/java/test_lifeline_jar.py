"""The lifeline jar needs no Java to check: a broken one would stop every Java start (20 G3)."""

from __future__ import annotations

import zipfile
from importlib import resources
from pathlib import Path

import pytest

JAR = Path(str(resources.files("tlaup.java").joinpath("lifeline.jar")))
JAVA_11_MAJOR = 55


@pytest.fixture
def archive() -> zipfile.ZipFile:
    assert JAR.is_file(), "tlaup/java/lifeline.jar is missing: run `uv run poe build-lifeline`"
    return zipfile.ZipFile(JAR)


def test_jar_is_where_the_java_package_is_installed() -> None:
    assert JAR.parent == Path(str(resources.files("tlaup.java")))


def test_jar_is_a_zip(archive: zipfile.ZipFile) -> None:
    assert archive.testzip() is None


def test_manifest_names_the_premain_class_and_the_jar_holds_it(archive: zipfile.ZipFile) -> None:
    manifest = archive.read("META-INF/MANIFEST.MF").decode("ascii")
    lines = dict(line.split(": ", 1) for line in manifest.splitlines() if ": " in line)
    premain = lines["Premain-Class"]
    assert premain.replace(".", "/") + ".class" in archive.namelist()


def test_class_files_are_java_11(archive: zipfile.ZipFile) -> None:
    classes = [name for name in archive.namelist() if name.endswith(".class")]
    assert classes
    for name in classes:
        header = archive.read(name)[:8]
        assert header[:4] == b"\xca\xfe\xba\xbe", name
        assert int.from_bytes(header[6:8], "big") == JAVA_11_MAJOR, name
