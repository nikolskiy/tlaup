"""The classpath of a run (design 13 M2; inventory rows S11's first form, M17, M18), with module_dirs (package 30)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from tests.clock import FakeClock
from tlaup.config.loader import load_settings
from tlaup.java.classpath import ClasspathResolver, ResolveMode
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
    # A module in the old cache, which the resolver must not read when given module_dirs.
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
        str(t / "project" / "classes"),
        # 2. the folders of TLA+ modules: the project's, module_path's, each registered module's, by name
        str(t / "project" / "modules"),
        str(t / "shared-modules"),
        str(modules / "alpha" / "modules"),
        str(modules / "beta" / "modules"),
        # 3. each registered module's classes, by name
        str(modules / "alpha" / "classes"),
        str(modules / "beta" / "classes"),
        # 4. the tool jar
        str(t / "store" / "tla2tools.jar"),
        # 5. the jars: the project's lib/ (module_lib_path names it again: each once), then the modules', by name
        str(t / "project" / "lib" / "a.jar"),
        str(t / "project" / "lib" / "b.jar"),
        str(modules / "alpha" / "lib" / "x.jar"),
        str(modules / "beta" / "lib" / "y.jar"),
    ]
    assert resolver.resolve(ResolveMode.RUNTIME) == expected
    assert resolver.get_tla_library_property() == os.pathsep.join(expected[1:5])


def test_without_module_dirs_the_old_cache_is_walked(isolated: Isolated, tmp_path: Path) -> None:
    resolver, _ = make_resolver(isolated, tmp_path)
    old = ClasspathResolver(resolver.config, project_root=resolver.project_root, tool_jar=resolver.tool_jar)
    classpath = old.resolve(ResolveMode.RUNTIME)
    walked = isolated.paths.cache / "modules" / "Old"
    assert str(walked / "classes") in classpath
    assert str(walked / "lib" / "old.jar") in classpath
    assert not any(isolated.paths.modules in Path(entry).parents for entry in classpath)
