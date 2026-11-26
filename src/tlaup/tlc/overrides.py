"""Which Java override classes are passed to TLC, and the check before a run (design 11 R7).

Nothing here raises for a bad class or a bad jar and nothing prints: ``check_overrides`` returns texts, and the
preflight and ``build_module`` hand them on (decision D35, warn and run). The two hint functions are pure functions
of text, called by the terminal reporter.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tlaup.modules.classfile import OVERRIDES_INTERFACE, ClassInfo, read_class
from tlaup.modules.registry import read_record
from tlaup.versioning.spec import format_build

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from tlaup.versioning.store import Build

SERVICE_FILE = f"META-INF/services/{OVERRIDES_INTERFACE}"
DEFAULT_CLASS = "tlc2.overrides.TLCOverrides"
CAPABILITY = "overrides_property"
_JAVA_OBJECT = "java.lang.Object"
_CLASS_VERSION_OFFSET = 44  # class file version 55 is Java 11


@dataclass(frozen=True)
class OverrideClass:
    name: str  # "tlc2.overrides.QueueOverrides"
    declared_in: Path  # the classpath entry
    module: str | None  # the registered module's name, if the entry is one


class _Entry:
    """A classpath entry, a folder or a jar, read without extracting anything; a jar's file list is read once."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._names: frozenset[str] | None = None
        if path.is_file():
            try:
                with zipfile.ZipFile(path) as jar:
                    self._names = frozenset(jar.namelist())
            except (zipfile.BadZipFile, OSError):
                self._names = frozenset()  # a file that is not a readable jar holds nothing

    def read(self, name: str) -> bytes | None:
        """The bytes of ``name`` (a path with slashes) in this entry, or None if it holds no such file."""
        try:
            if self._names is not None:
                if name not in self._names:
                    return None
                with zipfile.ZipFile(self.path) as jar:
                    return jar.read(name)
            target = self.path / name
            return target.read_bytes() if target.is_file() else None
        except (zipfile.BadZipFile, OSError):
            return None

    def has(self, name: str) -> bool:
        if self._names is not None:
            return name in self._names
        return (self.path / name).is_file()


def _class_file(name: str) -> str:
    return name.replace(".", "/") + ".class"


def _service_names(data: bytes) -> list[str]:
    """The names in a service file: ``#`` starts a comment, as ``ServiceLoader`` reads it; blank lines are skipped."""
    lines = data.decode("utf-8", errors="replace").splitlines()
    names = (line.split("#", 1)[0].strip() for line in lines)
    return [name for name in names if name]


def _module_of(entry: Path) -> str | None:
    """The registered module's name when ``entry`` is its ``classes`` folder or a jar in its ``lib/`` (13 M2)."""
    folder = entry.parent.parent if entry.is_file() and entry.parent.name == "lib" else entry.parent
    return folder.name if read_record(folder) is not None else None


def collect_override_classes(classpath: Sequence[Path]) -> list[OverrideClass]:
    """For each entry in order: the names in its service file, then the default class if it holds that class file.

    The default is added for every entry that holds ``tlc2/overrides/TLCOverrides.class``, jars too, unless the
    service file already names it. Duplicates are dropped; the first wins.
    """
    found: dict[str, OverrideClass] = {}
    for path in classpath:
        entry = _Entry(path)
        module = _module_of(path)
        service = entry.read(SERVICE_FILE)
        names = [] if service is None else _service_names(service)
        if DEFAULT_CLASS not in names and entry.has(_class_file(DEFAULT_CLASS)):
            names.append(DEFAULT_CLASS)
        for name in names:
            found.setdefault(name, OverrideClass(name, path, module))
    return list(found.values())


def _label(item: OverrideClass) -> str:
    return item.name if item.module is None else f"{item.name} (module {item.module})"


def _read_info(data: bytes) -> ClassInfo | None:
    try:
        return read_class(data)
    except ValueError:
        return None


def _find(name: str, entries: Sequence[_Entry]) -> ClassInfo | None:
    data = next((found for entry in entries if (found := entry.read(_class_file(name))) is not None), None)
    return None if data is None else _read_info(data)


def _extends_interface(name: str, entries: Sequence[_Entry], seen: set[str]) -> bool | None:
    """Whether the interface ``name`` is or extends ``ITLCOverrides``; None when it cannot be ruled out."""
    if name == OVERRIDES_INTERFACE:
        return True
    if name.startswith("java.") or name in seen:
        return False  # the JDK's interfaces do not extend TLC's
    seen.add(name)
    info = _find(name, entries)
    if info is None:
        return None
    unsure = False
    for parent in info.interfaces:
        result = _extends_interface(parent, entries, seen)
        if result:
            return True
        unsure = unsure or result is None
    return None if unsure else False


def _is_override(data: bytes, readable: Sequence[_Entry]) -> bool | None:
    """Whether the class implements ``ITLCOverrides``, directly or through superclasses and interfaces found on the
    classpath.

    None (nothing is said) when the chain leaves what can be read: a file that is not a class file, a superclass or
    an interface that is nowhere in ``readable`` (the entries outside the tools jar). ``java.lang.Object`` ends the
    chain; with every interface ruled out the answer is then False.
    """
    info = _read_info(data)
    seen: set[str] = set()
    unsure = False
    while info is not None:
        for interface in info.interfaces:
            result = _extends_interface(interface, readable, set())
            if result:
                return True
            unsure = unsure or result is None
        if info.super_name is None or info.super_name == _JAVA_OBJECT:
            return None if unsure else False
        if info.super_name in seen:
            return None
        seen.add(info.super_name)
        info = _find(info.super_name, readable)
    return None


def check_overrides(classes: Sequence[OverrideClass], classpath: Sequence[Path], build: Build) -> list[str]:
    """One warning text per finding (R7 part 2); empty when every class will be loaded."""
    entries = [_Entry(path) for path in classpath]
    outside_tools = [entry for entry in entries if entry.path != build.jar]
    warnings: list[str] = []

    holders = [entry for entry in entries if entry.has(_class_file(DEFAULT_CLASS))]
    if len(holders) > 1:
        warnings.append(f"{len(holders)} classpath entries hold a class named {DEFAULT_CLASS}; only the first is used")

    for item in classes:
        data = next((found for entry in entries if (found := entry.read(_class_file(item.name))) is not None), None)
        if data is None:
            warnings.append(f"override class {_label(item)} is not on the classpath and will not load")
            continue
        if CAPABILITY not in build.capabilities and item.name != DEFAULT_CLASS:
            warnings.append(
                f"TLC {format_build(build)} loads Java overrides only from a class named {DEFAULT_CLASS}; "
                f"{_label(item)} will not load, and the TLA+ definitions of its operators will be used"
            )
            continue
        if _is_override(data, outside_tools) is False:
            warnings.append(
                f"{_label(item)} is not an override class (it does not implement {OVERRIDES_INTERFACE}) "
                "and TLC will ignore it"
            )
    return warnings


_TOO_NEW = re.compile(
    r"(?P<name>[\w$/.]+)\s+has\s+been\s+compiled\s+by\s+a\s+more\s+recent\s+version\s+of\s+the\s+Java\s+Runtime\s+"
    r"\(class\s+file\s+version\s+(?P<found>\d+)\.\d+\),\s+this\s+version\s+of\s+the\s+Java\s+Runtime\s+"
    r"only\s+recognizes\s+class\s+file\s+versions\s+up\s+to\s+(?P<runs>\d+)\.\d+"
)


def class_version_hint(text: str) -> str | None:
    """The hint for a class compiled for a newer Java, when ``text`` holds the JVM's sentence about it; else None."""
    match = _TOO_NEW.search(text)
    if match is None:
        return None
    name = match["name"].replace("/", ".")
    found, runs = int(match["found"]), int(match["runs"])
    return (
        f"the override class {name} was compiled for Java {found - _CLASS_VERSION_OFFSET} (class file {found}) "
        f"and TLC runs on Java {runs - _CLASS_VERSION_OFFSET} (up to {runs}); rebuild the module with "
        "`tlaup module add`, which compiles with `--release 11`, or run TLC on a newer Java"
    )


def load_failure_hint(classes: Sequence[str]) -> str:
    """The general hint for a load that failed inside TLC, naming the classes that were passed."""
    return (
        "TLC failed while loading the spec. If the error comes from a Java override, "
        f"one of these classes failed to load: {', '.join(classes)}"
    )
