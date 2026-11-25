"""The class-file reader and the override scan (design 13 M3), on the real class files of tests/fakes/classes/."""

from __future__ import annotations

import contextlib
import random
import shutil
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.fakes._fakelib import CLASSES_DIR
from tlaup.modules.classfile import ClassInfo, find_override_classes, read_class

if TYPE_CHECKING:
    from pathlib import Path

OVERRIDES = CLASSES_DIR / "tlc2" / "overrides"
ITLC = "tlc2.overrides.ITLCOverrides"


def info(name: str) -> ClassInfo:
    return read_class((OVERRIDES / f"{name}.class").read_bytes())


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("DirectOverrides", ClassInfo("tlc2.overrides.DirectOverrides", "java.lang.Object", (ITLC,), False, False)),
        ("NotAnOverride", ClassInfo("tlc2.overrides.NotAnOverride", "java.lang.Object", (), False, False)),
        ("AbstractOverrides", ClassInfo("tlc2.overrides.AbstractOverrides", "java.lang.Object", (ITLC,), True, False)),
        (
            "InheritedOverrides",
            ClassInfo("tlc2.overrides.InheritedOverrides", "tlc2.overrides.AbstractOverrides", (), False, False),
        ),
        ("Constants", ClassInfo("tlc2.overrides.Constants", "java.lang.Object", (), False, False)),
        ("ITLCOverrides", ClassInfo(ITLC, "java.lang.Object", (), True, True)),
        ("Strings", ClassInfo("tlc2.overrides.Strings", "java.lang.Object", (ITLC,), False, False)),
        ("Outer$Inner", ClassInfo("tlc2.overrides.Outer$Inner", "java.lang.Object", (ITLC,), False, False)),
    ],
)
def test_read_class_on_the_real_class_files(name: str, expected: ClassInfo) -> None:
    assert info(name) == expected


def test_the_constants_class_holds_the_two_slot_entries() -> None:
    data = (OVERRIDES / "Constants.class").read_bytes()
    assert b"\x05\x00\x00\x01\x1f\x71\xfb\x04\xcb" in data  # tag 5, the long 1234567890123
    assert b"\x06\x40\x09\x21\xf9\xf0\x1b\x86\x6e" in data  # tag 6, the double 3.14159


def test_the_strings_class_holds_modified_utf8() -> None:
    data = (OVERRIDES / "Strings.class").read_bytes()
    assert b"\xed\xa0\xbd\xed\xb8\x80" in data  # U+1F600 as a surrogate pair
    assert b"a\xc0\x80b" in data  # NUL as C0 80


@pytest.mark.parametrize(("old", "new"), [(b"Strings", b"Str\xc0\x80gs"), (b"Strings", b"S\xed\xa0\xbd\xed\xb8\x80gs")])
def test_a_class_name_in_modified_utf8(old: bytes, new: bytes) -> None:
    data = (OVERRIDES / "Strings.class").read_bytes()
    entry = b"\x01" + len(b"tlc2/overrides/" + old).to_bytes(2, "big") + b"tlc2/overrides/" + old
    assert data.count(entry) == 1
    changed = data.replace(entry, b"\x01" + len(b"tlc2/overrides/" + new).to_bytes(2, "big") + b"tlc2/overrides/" + new)
    name = read_class(changed).name
    assert name in ("tlc2.overrides.Str\x00gs", "tlc2.overrides.S\U0001f600gs")


@pytest.mark.parametrize("name", ["DirectOverrides", "Constants", "Outer$Inner"])
def test_every_truncation_is_a_value_error(name: str) -> None:
    data = (OVERRIDES / f"{name}.class").read_bytes()
    for length in range(len(data)):
        with pytest.raises(ValueError, match=r"."):
            read_class(data[:length])


def test_random_bytes_are_a_value_error() -> None:
    generator = random.Random(30)
    for _ in range(200):
        data = bytes(generator.randrange(256) for _ in range(generator.randrange(64)))
        with pytest.raises(ValueError, match=r"."):
            read_class(data)


def test_random_bytes_after_the_magic_number_are_a_value_error() -> None:
    generator = random.Random(31)
    for _ in range(200):
        data = b"\xca\xfe\xba\xbe" + bytes(generator.randrange(256) for _ in range(generator.randrange(200)))
        with pytest.raises(ValueError, match=r"."):
            read_class(data)


@given(st.binary())
def test_read_class_returns_or_raises_value_error(data: bytes) -> None:
    with contextlib.suppress(ValueError):
        read_class(data)


@given(st.binary(max_size=64))
def test_read_class_on_a_real_header_with_any_tail(tail: bytes) -> None:
    data = (OVERRIDES / "DirectOverrides.class").read_bytes()
    with contextlib.suppress(ValueError):
        read_class(data[:40] + tail)


def test_find_override_classes(tmp_path: Path) -> None:
    folder = tmp_path / "classes" / "tlc2" / "overrides"
    shutil.copytree(OVERRIDES, folder)
    assert find_override_classes(tmp_path / "classes") == [
        "tlc2.overrides.DirectOverrides",
        "tlc2.overrides.InheritedOverrides",
        "tlc2.overrides.Outer$Inner",
        "tlc2.overrides.Strings",
    ]


def test_find_override_classes_needs_the_superclass_among_them(tmp_path: Path) -> None:
    shutil.copyfile(OVERRIDES / "InheritedOverrides.class", tmp_path / "InheritedOverrides.class")
    assert find_override_classes(tmp_path) == []


def test_find_override_classes_names_a_file_that_is_not_a_class_file(tmp_path: Path) -> None:
    (tmp_path / "Broken.class").write_bytes(b"not a class")
    with pytest.raises(ValueError, match=r"Broken\.class"):
        find_override_classes(tmp_path)
