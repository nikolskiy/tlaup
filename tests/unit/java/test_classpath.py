"""The classpath of a run (design 13 M2; inventory rows S10 to S12, M17, M18, C6), with module_dirs (package 30).

The path-returning methods of package 33 are the ones tested; the string forms go with the old runner (39).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.clock import FakeClock
from tlaup.config.loader import load_settings
from tlaup.java.classpath import ClasspathResolver
from tlaup.modules.registry import RegisteredModule, Registry, write_record

if TYPE_CHECKING:
    from tests.conftest import Isolated


def touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"jar")
    return path


def register(registry: Registry, name: str, jar: str) -> Path:
    folder = registry.root / name
    (folder / "modules").mkdir(parents=True)
    (folder / "classes").mkdir()
    touch(folder / "lib" / jar)
    write_record(folder, RegisteredModule(name, folder, "2026-11-15T00:00:00Z", "/src", None, None, None, ()))
    return folder


def make_resolver(isolated: Isolated, tmp_path: Path) -> tuple[ClasspathResolver, Path]:
    project = tmp_path / "project"
    (project / "classes").mkdir(parents=True)
    (project / "modules").mkdir()
    touch(project / "lib" / "b.jar")  # reverse name order
    touch(project / "lib" / "a.jar")
    shared = tmp_path / "shared-modules"
    shared.mkdir()
    settings = load_settings(isolated.paths, {}).settings.model_copy(
        update={"module_path": str(shared), "module_lib_path": str(project / "lib")}
    )
    registry = Registry(isolated.paths.modules, now=FakeClock().now)
    register(registry, "beta", "y.jar")  # the reverse of name order
    register(registry, "alpha", "x.jar")
    # A module in the old cache, which the resolver never reads: it takes the folders it is given.
    old = isolated.paths.cache / "modules" / "Old"
    (old / "classes").mkdir(parents=True)
    (old / "modules").mkdir()
    touch(old / "lib" / "old.jar")
    tool_jar = touch(tmp_path / "store" / "tla2tools.jar")
    resolver = ClasspathResolver(
        settings,
        project_root=project,
        tool_jar=tool_jar,
        module_dirs=[module.path for module in registry.list()],
    )
    return resolver, tmp_path


def test_the_runtime_classpath_in_the_five_steps(isolated: Isolated, tmp_path: Path) -> None:
    resolver, t = make_resolver(isolated, tmp_path)
    modules = isolated.paths.modules
    expected = [
        # 1. the project's classes
        t / "project" / "classes",
        # 2. the folders of TLA+ modules: the project's, module_path's, each registered module's, by name
        t / "project" / "modules",
        t / "shared-modules",
        modules / "alpha" / "modules",
        modules / "beta" / "modules",
        # 3. each registered module's classes, by name
        modules / "alpha" / "classes",
        modules / "beta" / "classes",
        # 4. the tool jar
        t / "store" / "tla2tools.jar",
        # 5. the jars: the project's lib/ (module_lib_path names it again: each once), then the modules', by name
        t / "project" / "lib" / "a.jar",
        t / "project" / "lib" / "b.jar",
        modules / "alpha" / "lib" / "x.jar",
        modules / "beta" / "lib" / "y.jar",
    ]
    classpath = resolver.runtime_classpath(isolated.work)
    assert classpath == expected
    assert resolver.tla_library(isolated.work) == expected[1:5]
    assert not any("Old" in entry.parts for entry in classpath)


def test_relative_module_paths_are_read_against_cwd_row_c6(isolated: Isolated, tmp_path: Path) -> None:
    cwd = tmp_path / "started-here"
    (cwd / "mods").mkdir(parents=True)
    touch(cwd / "jars" / "j.jar")
    settings = load_settings(isolated.paths, {}).settings.model_copy(
        update={"module_path": "mods", "module_lib_path": "jars"}
    )
    resolver = ClasspathResolver(settings, tool_jar=tmp_path / "tla2tools.jar", module_dirs=[])
    # The process's working folder is another one: only the cwd given counts.
    assert Path.cwd() != cwd
    assert resolver.tla_library(cwd) == [cwd / "mods"]
    assert resolver.runtime_classpath(cwd) == [cwd / "mods", tmp_path / "tla2tools.jar", cwd / "jars" / "j.jar"]
