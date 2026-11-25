"""The jar that ships holds exactly the classes its source compiles to (design 20 G3, "The jar")."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType


def test_class_files_equal_the_jar(jar: Path, build_script: ModuleType) -> None:
    javac = build_script.find_javac()
    ran = build_script.javac_version(javac)
    with zipfile.ZipFile(jar) as archive:
        in_jar = {name: archive.read(name) for name in archive.namelist() if name.endswith(".class")}
        built_with = next(
            (
                line
                for line in archive.read("META-INF/MANIFEST.MF").decode("ascii").splitlines()
                if "Created-By" in line
            ),
            "Created-By: unknown",
        )
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        compiled = {
            path.relative_to(folder).as_posix(): path.read_bytes() for path in build_script.compile_agent(folder)
        }
    hint = (
        f"the jar says `{built_with}`; this run used `{ran}`. Two JDKs need not write the same bytes: rebuild with "
        "`uv run poe build-lifeline` under the JDK of the lifeline job (Temurin 11) and commit the jar with the source."
    )
    assert set(compiled) == set(in_jar), f"class files differ: {sorted(set(compiled) ^ set(in_jar))}; {hint}"
    different = sorted(name for name in compiled if compiled[name] != in_jar[name])
    assert not different, f"class files differ in content: {different}; {hint}"
