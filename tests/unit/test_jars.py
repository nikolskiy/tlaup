"""``make_tools_jar`` (design 01 T4)."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from tests.jars import make_tools_jar

if TYPE_CHECKING:
    from pathlib import Path


def test_jar_is_a_valid_zip_with_the_manifest_unchanged(tmp_path: Path) -> None:
    manifest = b"Manifest-Version: 1.0\r\nMain-class: tlc2.TLC\r\n"
    jar = make_tools_jar(tmp_path / "a" / "tla2tools.jar", manifest)
    with zipfile.ZipFile(jar) as z:
        assert z.testzip() is None
        assert z.read("META-INF/MANIFEST.MF") == manifest
        assert z.read("tlc2/TLC.class") == b""
        assert "tlc2/REPL.class" not in z.namelist()


def test_repl_class_only_with_repl(tmp_path: Path) -> None:
    source = tmp_path / "m.MF"
    source.write_bytes(b"Manifest-Version: 1.0\n")
    jar = make_tools_jar(tmp_path / "b.jar", source, repl=True)
    with zipfile.ZipFile(jar) as z:
        assert "tlc2/REPL.class" in z.namelist()
        assert z.read("META-INF/MANIFEST.MF") == b"Manifest-Version: 1.0\n"
