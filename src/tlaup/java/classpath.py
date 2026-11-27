from collections.abc import Callable, Sequence
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from tlaup.config.schema import Settings
from tlaup.modules.registry import Registry
from tlaup.project.core import CLASSES_DIR, LIB_DIR, MODULES_DIR


class SubdirType(Enum):
    """Types of project-local subdirectories."""

    MODULES = auto()
    CLASSES = auto()
    LIB = auto()


class ClasspathResolver:
    """
    Centralized component for resolving Java classpaths and system properties.
    Follows a strict Specific-to-General hierarchy: CLI > Project > Config > Global.
    """

    def __init__(  # noqa: PLR0913 - the signature package 30 gives
        self,
        config: Settings,
        project_root: Path | None = None,
        tool_jar: Path | None = None,
        extra_libs: list[str] | None = None,
        extra_modules: list[str] | None = None,
        *,
        module_dirs: Sequence[Path],
    ):
        """
        Initialize the resolver.

        Args:
            config: The global settings.
            project_root: The root of the TLA+ project (where .tla file is).
            tool_jar: Path to tla2tools.jar.
            extra_libs: Explicit library paths from CLI.
            extra_modules: Explicit module paths from CLI.
            module_dirs: The folders of the registered modules, in the order Registry.list() gives them.
        """
        self.config = config
        self.project_root = project_root
        self.tool_jar = tool_jar
        self.extra_libs = extra_libs or []
        self.extra_modules = extra_modules or []
        self.module_dirs = module_dirs

    def get_project_path(self, subdir: SubdirType) -> Path | None:
        """Helper to find a project-local directory."""
        if not self.project_root:
            return None

        subdir_name = {
            SubdirType.MODULES: MODULES_DIR,
            SubdirType.CLASSES: CLASSES_DIR,
            SubdirType.LIB: LIB_DIR,
        }[subdir]
        path = self.project_root / subdir_name
        if path.is_dir():
            return path

        return None

    def _layer_paths(self, cli_paths: list[str], subdir: SubdirType, config_path: str | None, cwd: Path) -> list[Path]:
        """
        Resolves a set of paths following the hierarchy: command line, project, config, registered modules.
        Relative paths are read against `cwd`. Deduplicates while preserving order; a lib folder gives its jars.
        """
        raw_paths: list[Path] = []

        # 1. CLI Arguments
        raw_paths.extend(cwd / p for p in cli_paths)

        # 2. Project-Local
        project_path = self.get_project_path(subdir)
        if project_path:
            raw_paths.append(cwd / project_path)

        # 3. Config
        if config_path:
            raw_paths.append(cwd / config_path)

        # 4. Managed Modules: the registered modules' folders
        for item in self.module_dirs:
            if subdir == SubdirType.LIB:
                mod_lib = item / "lib"
                if mod_lib.is_dir():
                    raw_paths.append(cwd / mod_lib)
            elif subdir == SubdirType.MODULES:
                mod_modules = item / "modules"
                if mod_modules.is_dir():
                    raw_paths.append(cwd / mod_modules)

        # Expand lib folders into their jars, sorted by name
        expanded: list[Path] = []
        for path in raw_paths:
            if path.is_dir() and subdir == SubdirType.LIB:
                expanded.extend(sorted(path.glob("*.jar")))
            else:
                expanded.append(path)
        return _first_places(expanded)

    def runtime_classpath(self, cwd: Path) -> list[Path]:
        """
        The classpath of a run (design 13 M2, "The classpath of a run"), each entry an absolute path, each once in
        its first place: the project's classes, the TLA+ module folders, the registered modules' classes, the tool
        jar, then the jars. A relative path in the settings is read against `cwd`.
        """
        classpath: list[Path] = []

        # Project-local classes shadow everything
        classes_dir = self.get_project_path(SubdirType.CLASSES)
        if classes_dir:
            classpath.append(cwd / classes_dir)

        # Module source directories containing .tla files
        classpath.extend(self.tla_library(cwd))

        # Registered modules' classes
        for item in self.module_dirs:
            mod_classes = item / "classes"
            if mod_classes.is_dir():
                classpath.append(cwd / mod_classes)

        # Tool JAR
        if self.tool_jar:
            classpath.append(cwd / self.tool_jar)

        # Libraries (CLI > Project > Config > registered modules)
        classpath.extend(self._layer_paths(self.extra_libs, SubdirType.LIB, self.config.module_lib_path, cwd))

        return _first_places(classpath)

    def tla_library(self, cwd: Path) -> list[Path]:
        """The folders of TLA+ modules, for -DTLA-Library: step 2 of the classpath, in the same order."""
        return self._layer_paths(self.extra_modules, SubdirType.MODULES, self.config.module_path, cwd)


def _first_places(paths: list[Path]) -> list[Path]:
    """Each path once, in its first place (compared as given: every path here is absolute)."""
    seen: set[Path] = set()
    kept: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            kept.append(path)
    return kept


def run_paths(  # noqa: PLR0913 - the pieces a run's paths come from
    settings: Settings,
    *,
    project_root: Path | None,
    tool_jar: Path,
    modules: Path,
    now: Callable[[], datetime],
    cwd: Path,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """The classpath and the TLA-Library folders of a run (13 M2): the one place a TLC run and the other tools
    that read a spec get them from. ``modules`` is ``AppPaths.modules``, whose registered modules are listed in
    name order; ``cwd`` is the folder tlaup was started in, which a relative setting is read against."""
    resolver = ClasspathResolver(
        settings,
        project_root=project_root,
        tool_jar=tool_jar,
        module_dirs=[module.path for module in Registry(modules, now=now).list()],
    )
    return tuple(resolver.runtime_classpath(cwd)), tuple(resolver.tla_library(cwd))
