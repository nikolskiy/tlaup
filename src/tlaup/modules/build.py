"""Building a module in a temporary folder and swapping it in (design 13 M2, M3).

``build_module`` prints nothing and asks nothing: it raises, and the command prints what it returns.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING

from tlaup.errors import FileOperationError, InvalidName, ModuleBuildError, PathNotFound, ToolStartError
from tlaup.modules.classfile import OVERRIDES_INTERFACE, find_override_classes
from tlaup.modules.registry import RegisteredModule, validate_module_name, write_record

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path

    from tlaup.java.locate import JavaRuntime
    from tlaup.modules.registry import Registry
    from tlaup.versioning.store import Build

COPIED = ("lib", "modules", "tlc2")  # the test/tests folders are not copied: nothing reads them
SOURCE_FOLDERS = ("modules/tlc2/overrides", "tlc2/overrides")
SERVICE_FILE = f"META-INF/services/{OVERRIDES_INTERFACE}"
NO_OVERRIDES = f"no override index class was found: no compiled class implements {OVERRIDES_INTERFACE}"


@dataclass(frozen=True)
class BuiltModule:
    name: str
    path: Path
    override_classes: tuple[str, ...]
    replaced: bool  # a module of this name was registered before
    warnings: tuple[str, ...]  # 11 R7's (package 34), and those of the javac lookup (J2, M3); the command prints them


@dataclass(frozen=True)
class _Compiled:
    javac: str | None
    built_against: str
    override_classes: tuple[str, ...]
    warnings: tuple[str, ...]


def _cannot(action: str, path: Path, error: OSError) -> FileOperationError:
    return FileOperationError(f"cannot {action} {path}: {error.strerror or error}")


def _module_name(source: Path) -> str:
    try:
        return validate_module_name(source.name)
    except InvalidName as error:
        raise InvalidName(  # noqa: TRY003
            f"the folder name {source.name!r} is not a valid module name",
            hint=f"rename the folder; {error.hint}",
        ) from None


def _copy(source: Path, folder: Path) -> None:
    for name in COPIED:
        if (source / name).is_dir():
            try:
                shutil.copytree(source / name, folder / name)
            except (OSError, shutil.Error) as error:
                raise FileOperationError(f"cannot copy {source / name}: {error}") from error  # noqa: TRY003


def _sources(folder: Path) -> list[Path]:
    found: list[Path] = []
    for sub in SOURCE_FOLDERS:
        if (folder / sub).is_dir():
            found.extend(path for path in (folder / sub).rglob("*.java") if path.is_file())
    return sorted(found)


def compile_classpath(build: Build, folder: Path) -> str:
    """The build's jar, then the jars directly in the module's own ``lib/``, by name (D61); nothing else."""
    lib = folder / "lib"
    jars = sorted((path for path in lib.glob("*.jar") if path.is_file()), key=lambda path: path.name)
    return os.pathsep.join([str(build.jar), *(str(jar) for jar in jars)])


def _run_javac(javac: JavaRuntime, argv: list[str], classpath: str, timeout: float) -> None:
    try:
        result = subprocess.run(  # an argument list, the javac require_javac found
            argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        raise ModuleBuildError(f"javac did not finish in {timeout:g} seconds") from None  # noqa: TRY003
    except OSError as error:
        raise ToolStartError(f"{javac.tool.path} could not be started: {error.strerror or error}") from error  # noqa: TRY003
    if result.returncode != 0:
        output = (result.stdout + result.stderr).decode("utf-8", errors="replace").rstrip()
        raise ModuleBuildError(  # noqa: TRY003
            f"javac failed with exit code {result.returncode}",
            details=f"{output}\n\nclasspath: {classpath}",
        )
    # On success javac's output is dropped: its warnings are shown only with --verbose (milestone 4).


def _service_names(text: str) -> tuple[str, ...]:
    names = (line.split("#", 1)[0].strip() for line in text.splitlines())
    return tuple(name for name in names if name)


def _overrides(source: Path, classes: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The override classes and the warnings; writes ``classes/META-INF/services/...`` when there are any (M3)."""
    service = classes / SERVICE_FILE
    own = source / SERVICE_FILE
    try:
        if own.is_file():
            service.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(own, service)
            return _service_names(own.read_text(encoding="utf-8", errors="replace")), ()
        try:
            found = find_override_classes(classes)
        except ValueError as error:
            raise ModuleBuildError(f"cannot read a compiled class: {error}") from error  # noqa: TRY003
        if not found:
            return (), (NO_OVERRIDES,)
        service.parent.mkdir(parents=True, exist_ok=True)
        service.write_text("".join(f"{name}\n" for name in found), encoding="utf-8")
    except OSError as error:
        raise _cannot("write", service, error) from error
    return tuple(found), ()


def _compile(  # noqa: PLR0913 - build_module's arguments, passed on
    source: Path,
    folder: Path,
    sources: list[Path],
    *,
    get_build: Callable[[], Build],
    get_javac: Callable[[], JavaRuntime],
    release: int,
    timeout: float,
) -> _Compiled:
    build = get_build()
    javac = get_javac()
    classes = folder / "classes"
    classes.mkdir()
    classpath = compile_classpath(build, folder)
    argv = [str(javac.tool.path), "-encoding", "UTF-8", "--release", str(release), "-cp", classpath]
    argv += ["-d", str(classes), *(str(path) for path in sources)]
    _run_javac(javac, argv, classpath, timeout)
    override_classes, notes = _overrides(source, classes)
    built_against = f"{build.name}@{build.commit}" if build.commit else build.name
    return _Compiled(javac.version, built_against, override_classes, (*javac.warnings, *notes))


def build_module(  # noqa: PLR0913 - the signature of design 13 M2
    source: Path,
    *,
    registry: Registry,
    get_build: Callable[[], Build],
    get_javac: Callable[[], JavaRuntime],
    release: int,
    now: Callable[[], datetime],
    timeout: float = 300.0,
) -> BuiltModule:
    """Build the module in ``source`` under ``<root>/.tmp/`` and swap it in under the modules lock (M2).

    ``get_build`` and ``get_javac`` are called only when the module has Java sources. On any failure
    the temporary folder is removed and the registered module, if any, is untouched.
    """
    source = source.resolve()
    if not source.is_dir():
        raise PathNotFound(f"{source} is not a folder")  # noqa: TRY003
    name = _module_name(source)
    registry.path_of(name)
    registry.clean_tmp(now())
    folder = registry.tmp_path(now())
    try:
        folder.mkdir(parents=True)
    except OSError as error:
        raise _cannot("create", folder, error) from error
    try:
        _copy(source, folder)
        sources = _sources(folder)
        compiled = None
        if sources:
            compiled = _compile(
                source, folder, sources, get_build=get_build, get_javac=get_javac, release=release, timeout=timeout
            )
        module = RegisteredModule(
            name=name,
            path=registry.root / name,
            built_at=now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            source=str(source),
            javac=compiled.javac if compiled else None,
            release=release if compiled else None,
            built_against=compiled.built_against if compiled else None,
            override_classes=compiled.override_classes if compiled else (),
        )
        write_record(folder, module)  # last: module.json marks a registered module's folder (34)
        replaced = registry.put(folder, name)
    finally:
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
    return BuiltModule(
        name=name,
        path=module.path,
        override_classes=module.override_classes,
        replaced=replaced,
        warnings=compiled.warnings if compiled else (),
    )
