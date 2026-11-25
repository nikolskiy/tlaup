"""Reading a class file's header, and finding the override classes among compiled classes (design 13 M3).

A class file states its superclass and its interfaces exactly, so the override classes are found in
the compiled output, not in the source text. Standard library only.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

OVERRIDES_INTERFACE = "tlc2.overrides.ITLCOverrides"

_MAGIC = 0xCAFEBABE
_ACC_INTERFACE = 0x0200
_ACC_ABSTRACT = 0x0400
_UTF8, _LONG, _DOUBLE, _CLASS = 1, 5, 6, 7
# The size of each constant pool entry after its tag, for the tags whose size is fixed.
_SIZES = {3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 16: 2, 19: 2, 20: 2, 15: 3, 9: 4, 10: 4, 11: 4, 12: 4, 17: 4, 18: 4}


@dataclass(frozen=True)
class ClassInfo:
    name: str  # "tlc2.overrides.QueueOverrides"
    super_name: str | None
    interfaces: tuple[str, ...]
    is_abstract: bool
    is_interface: bool


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, size: int) -> bytes:
        end = self.pos + size
        if end > len(self.data):
            message = "the class file ends early"
            raise ValueError(message)
        chunk = self.data[self.pos : end]
        self.pos = end
        return chunk

    def u2(self) -> int:
        value: int = struct.unpack(">H", self.take(2))[0]
        return value

    def u4(self) -> int:
        value: int = struct.unpack(">I", self.take(4))[0]
        return value

    def skip_members(self) -> None:
        """The fields or the methods: each with its attributes, skipped by their lengths."""
        for _ in range(self.u2()):
            self.take(6)  # access flags, name, descriptor
            self.skip_attributes()

    def skip_attributes(self) -> None:
        for _ in range(self.u2()):
            self.take(2)
            self.take(self.u4())


def _modified_utf8(data: bytes) -> str:
    """Decode a class file's modified UTF-8: ``C0 80`` is NUL, and a character beyond the BMP is a surrogate pair."""
    text = data.replace(b"\xc0\x80", b"\x00").decode("utf-8", errors="surrogatepass")
    return text.encode("utf-16-le", errors="surrogatepass").decode("utf-16-le")


def _read(data: bytes) -> ClassInfo:
    reader = _Reader(data)
    if reader.u4() != _MAGIC:
        message = "no class file magic number"
        raise ValueError(message)
    reader.take(4)  # minor and major version
    utf8: dict[int, bytes] = {}
    classes: dict[int, int] = {}
    count = reader.u2()
    index = 1
    while index < count:
        tag = reader.take(1)[0]
        if tag == _UTF8:
            utf8[index] = reader.take(reader.u2())  # decoded only when a name is read
        elif tag == _CLASS:
            classes[index] = reader.u2()
        elif tag in _SIZES:
            reader.take(_SIZES[tag])
        else:
            message = f"unknown constant pool tag {tag}"
            raise ValueError(message)
        index += 2 if tag in (_LONG, _DOUBLE) else 1

    def class_name(entry: int) -> str:
        return _modified_utf8(utf8[classes[entry]]).replace("/", ".")

    flags = reader.u2()
    name = class_name(reader.u2())
    super_index = reader.u2()
    super_name = class_name(super_index) if super_index else None
    interfaces = tuple(class_name(reader.u2()) for _ in range(reader.u2()))
    reader.skip_members()  # fields
    reader.skip_members()  # methods
    reader.skip_attributes()
    if reader.pos != len(data):
        message = "bytes after the end of the class file"
        raise ValueError(message)
    return ClassInfo(name, super_name, interfaces, bool(flags & _ACC_ABSTRACT), bool(flags & _ACC_INTERFACE))


def read_class(data: bytes) -> ClassInfo:
    """The class's name, superclass, interfaces and flags; ``ValueError`` if ``data`` is not a class file."""
    try:
        return _read(data)
    except (struct.error, IndexError, KeyError) as error:
        message = f"not a class file: {error!r}"
        raise ValueError(message) from error


def find_override_classes(classes_dir: Path) -> list[str]:
    """The classes under ``classes_dir`` that implement ``ITLCOverrides``, sorted.

    Directly or through a superclass found among them; abstract classes and interfaces are skipped.
    An interface that extends ``ITLCOverrides`` is not followed (M3). A file that is not a class file
    is ``ValueError`` naming it; a file that cannot be read is ``OSError``.
    """
    infos: dict[str, ClassInfo] = {}
    for path in sorted(classes_dir.rglob("*.class")):
        try:
            info = read_class(path.read_bytes())
        except ValueError as error:
            message = f"{path}: {error}"
            raise ValueError(message) from error
        infos[info.name] = info

    def implements(name: str) -> bool:
        seen: set[str] = set()
        current: str | None = name
        while current is not None and current in infos and current not in seen:
            seen.add(current)
            info = infos[current]
            if OVERRIDES_INTERFACE in info.interfaces:
                return True
            current = info.super_name
        return False

    concrete = [info for info in infos.values() if not (info.is_abstract or info.is_interface)]
    return sorted(info.name for info in concrete if implements(info.name))
