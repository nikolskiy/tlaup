"""Override classes: which are passed, and the check before a run (design 11 R7; inventory rows M7 and R24).

Real folders and real class files from tests/fakes/classes/; jars are made here with zipfile. A class file is
found by its path, so a copy of ``DirectOverrides.class`` stands for a class of any name.
"""

from __future__ import annotations

import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.clock import FakeClock
from tests.fakes._fakelib import CLASSES_DIR
from tlaup.modules.registry import RegisteredModule, Registry, write_record
from tlaup.tlc.overrides import (
    OverrideClass,
    check_overrides,
    class_version_hint,
    collect_override_classes,
    load_failure_hint,
)
from tlaup.versioning.store import Build, Source

if TYPE_CHECKING:
    from collections.abc import Mapping

GOLDEN = Path(__file__).resolve().parents[2] / "parse" / "golden" / "tlc"
SERVICE = "META-INF/services/tlc2.overrides.ITLCOverrides"
OVERRIDES = CLASSES_DIR / "tlc2" / "overrides"
START = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)


def class_bytes(name: str = "DirectOverrides") -> bytes:
    return (OVERRIDES / f"{name}.class").read_bytes()


def put_class(folder: Path, name: str, source: str = "DirectOverrides") -> None:
    """A class file at the path of ``name``; the bytes are those of a fake class."""
    target = folder / (name.replace(".", "/") + ".class")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(class_bytes(source))


def put_service(folder: Path, text: str) -> None:
    target = folder / SERVICE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def make_jar(path: Path, members: Mapping[str, bytes | str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as jar:
        for name, data in members.items():
            jar.writestr(name, data)
    return path


def make_build(folder: Path, *, capable: bool = True, name: str = "rolling") -> Build:
    """A build whose jar holds the interface, as the tools jar does."""
    jar = make_jar(folder / "tla2tools.jar", {"tlc2/overrides/ITLCOverrides.class": class_bytes("ITLCOverrides")})
    return Build(
        id=folder.name,
        name=name,
        commit=None,
        calver=None,
        built_at=None,
        sha256="0" * 64,
        size=jar.stat().st_size,
        prerelease=False,
        source=Source("github-release", "https://example.invalid/tla2tools.jar", 1, None, digest_checked=True),
        installed_at="2026-11-15T00:00:00Z",
        capabilities=frozenset({"overrides_property"}) if capable else frozenset(),
        path=folder,
    )


def names(classes: list[OverrideClass]) -> list[str]:
    return [item.name for item in classes]


# --- collect_override_classes (R7 part 1; row M7) -----------------------------------------------------------------


def test_a_folder_with_a_service_file(tmp_path: Path) -> None:
    folder = tmp_path / "classes"
    put_service(folder, "tlc2.overrides.A\ntlc2.overrides.B\n")
    assert collect_override_classes([folder]) == [
        OverrideClass("tlc2.overrides.A", folder, None),
        OverrideClass("tlc2.overrides.B", folder, None),
    ]


def test_a_bare_default_class_in_a_folder(tmp_path: Path) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.TLCOverrides")
    assert collect_override_classes([folder]) == [OverrideClass("tlc2.overrides.TLCOverrides", folder, None)]


def test_a_bare_default_class_in_a_jar_row_r7_fixed(tmp_path: Path) -> None:
    jar = make_jar(tmp_path / "lib" / "own.jar", {"tlc2/overrides/TLCOverrides.class": class_bytes()})
    assert collect_override_classes([jar]) == [OverrideClass("tlc2.overrides.TLCOverrides", jar, None)]


def test_a_jar_with_a_service_file(tmp_path: Path) -> None:
    jar = make_jar(tmp_path / "own.jar", {SERVICE: "tlc2.overrides.A\n"})
    assert names(collect_override_classes([jar])) == ["tlc2.overrides.A"]


def test_the_default_class_comes_after_the_service_files_names(tmp_path: Path) -> None:
    folder = tmp_path / "classes"
    put_service(folder, "tlc2.overrides.A\n")
    put_class(folder, "tlc2.overrides.TLCOverrides")
    assert names(collect_override_classes([folder])) == ["tlc2.overrides.A", "tlc2.overrides.TLCOverrides"]


def test_the_default_class_is_added_once_when_the_service_file_names_it(tmp_path: Path) -> None:
    folder = tmp_path / "classes"
    put_service(folder, "tlc2.overrides.TLCOverrides\ntlc2.overrides.A\n")
    put_class(folder, "tlc2.overrides.TLCOverrides")
    assert names(collect_override_classes([folder])) == ["tlc2.overrides.TLCOverrides", "tlc2.overrides.A"]


def test_comments_and_blank_lines_are_skipped(tmp_path: Path) -> None:
    folder = tmp_path / "classes"
    put_service(folder, "# the module's classes\n\ntlc2.overrides.A\n   \n  tlc2.overrides.B  # trailing\n")
    assert names(collect_override_classes([folder])) == ["tlc2.overrides.A", "tlc2.overrides.B"]


def test_two_entries_naming_one_class_the_first_wins(tmp_path: Path) -> None:
    first, second = tmp_path / "one", tmp_path / "two"
    put_service(first, "tlc2.overrides.A\n")
    put_service(second, "tlc2.overrides.A\ntlc2.overrides.B\n")
    assert collect_override_classes([first, second]) == [
        OverrideClass("tlc2.overrides.A", first, None),
        OverrideClass("tlc2.overrides.B", second, None),
    ]


def test_a_missing_entry_and_a_file_that_is_no_jar_hold_nothing(tmp_path: Path) -> None:
    broken = tmp_path / "broken.jar"
    broken.write_bytes(b"not a zip")
    assert collect_override_classes([tmp_path / "missing", broken]) == []


def registered(registry: Registry, name: str) -> Path:
    folder = registry.root / name
    (folder / "classes").mkdir(parents=True)
    write_record(folder, RegisteredModule(name, folder, "2026-11-15T00:00:00Z", "/src", None, None, None, ()))
    return folder


def test_a_registered_modules_service_file_and_a_projects_own_default_class_both_count_row_r24(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "modules", now=FakeClock(START).now)
    module = registered(registry, "Queue")
    put_service(module / "classes", "tlc2.overrides.QueueOverrides\n")
    project = tmp_path / "project" / "classes"
    put_class(project, "tlc2.overrides.TLCOverrides")
    assert collect_override_classes([project, module / "classes"]) == [
        OverrideClass("tlc2.overrides.TLCOverrides", project, None),
        OverrideClass("tlc2.overrides.QueueOverrides", module / "classes", "Queue"),
    ]


def test_the_module_is_known_by_its_record_for_a_classes_folder_and_a_jar_in_lib(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "modules", now=FakeClock(START).now)
    module = registered(registry, "Queue")
    jar = make_jar(module / "lib" / "extra.jar", {SERVICE: "tlc2.overrides.FromJar\n"})
    put_service(module / "classes", "tlc2.overrides.FromClasses\n")
    found = {item.name: item.module for item in collect_override_classes([module / "classes", jar])}
    assert found == {"tlc2.overrides.FromClasses": "Queue", "tlc2.overrides.FromJar": "Queue"}


def test_a_folder_without_a_record_is_not_a_module(tmp_path: Path) -> None:
    folder = tmp_path / "Queue" / "classes"
    put_service(folder, "tlc2.overrides.A\n")
    assert [item.module for item in collect_override_classes([folder])] == [None]


# --- check_overrides (R7 part 2) ----------------------------------------------------------------------------------


@pytest.fixture
def build(tmp_path: Path) -> Build:
    return make_build(tmp_path / "tools" / "rolling-abc")


def check(classes: list[str], classpath: list[Path], build: Build, module: str | None = None) -> list[str]:
    return check_overrides([OverrideClass(name, classpath[0], module) for name in classes], classpath, build)


def test_a_class_that_is_found_and_implements_the_interface_gives_no_warning(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.QueueOverrides")
    assert check(["tlc2.overrides.QueueOverrides"], [folder, build.jar], build) == []


def test_a_class_on_no_classpath_entry_is_not_on_the_classpath(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    folder.mkdir()
    assert check(["tlc2.overrides.Gone"], [folder, build.jar], build, "Queue") == [
        "override class tlc2.overrides.Gone (module Queue) is not on the classpath and will not load"
    ]


def test_the_module_is_left_out_of_a_warning_when_there_is_none(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    folder.mkdir()
    assert check(["tlc2.overrides.Gone"], [folder], build) == [
        "override class tlc2.overrides.Gone is not on the classpath and will not load"
    ]


def test_a_class_in_a_jar_is_found(tmp_path: Path, build: Build) -> None:
    jar = make_jar(tmp_path / "own.jar", {"tlc2/overrides/QueueOverrides.class": class_bytes()})
    assert check(["tlc2.overrides.QueueOverrides"], [jar, build.jar], build) == []


def test_a_build_without_the_property_loads_only_the_default_name(tmp_path: Path) -> None:
    old = make_build(tmp_path / "tools" / "v1.7.4-abc", capable=False, name="v1.7.4")
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.QueueOverrides")
    put_class(folder, "tlc2.overrides.TLCOverrides")
    assert check(["tlc2.overrides.QueueOverrides"], [folder, old.jar], old, "Queue") == [
        "TLC v1.7.4 loads Java overrides only from a class named tlc2.overrides.TLCOverrides; "
        "tlc2.overrides.QueueOverrides (module Queue) will not load, and the TLA+ definitions of its operators "
        "will be used"
    ]
    assert check(["tlc2.overrides.TLCOverrides"], [folder, old.jar], old) == []


def test_a_class_that_will_not_load_is_not_also_called_a_non_override(tmp_path: Path) -> None:
    old = make_build(tmp_path / "tools" / "v1.7.4-abc", capable=False, name="v1.7.4")
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.Plain", "NotAnOverride")
    warnings = check(["tlc2.overrides.Plain"], [folder, old.jar], old)
    assert len(warnings) == 1
    assert "will not load" in warnings[0]


def test_an_interface_that_cannot_be_ruled_out_says_nothing(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.WithMarker", "WithMarker")  # Marker.class is nowhere
    assert check(["tlc2.overrides.WithMarker"], [folder, build.jar], build) == []


def test_an_interface_that_is_found_and_does_not_extend_the_interface_is_ruled_out(
    tmp_path: Path, build: Build
) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.WithMarker", "WithMarker")
    put_class(folder, "tlc2.overrides.Marker", "Marker")
    assert len(check(["tlc2.overrides.WithMarker"], [folder, build.jar], build)) == 1


def test_an_interface_that_extends_the_interface_makes_the_class_an_override_class(
    tmp_path: Path, build: Build
) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.ViaSubInterface", "ViaSubInterface")
    put_class(folder, "tlc2.overrides.SubInterface", "SubInterface")
    assert check(["tlc2.overrides.ViaSubInterface"], [folder, build.jar], build) == []


def test_a_build_with_the_property_loads_any_name(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.QueueOverrides")
    assert "overrides_property" in build.capabilities
    assert check(["tlc2.overrides.QueueOverrides"], [folder, build.jar], build) == []


def test_two_entries_holding_the_default_class_warn_that_only_the_first_is_used(tmp_path: Path, build: Build) -> None:
    first, second = tmp_path / "one", tmp_path / "two"
    put_class(first, "tlc2.overrides.TLCOverrides")
    jar = make_jar(second / "own.jar", {"tlc2/overrides/TLCOverrides.class": class_bytes()})
    warnings = check(["tlc2.overrides.TLCOverrides"], [first, jar, build.jar], build)
    assert warnings == ["2 classpath entries hold a class named tlc2.overrides.TLCOverrides; only the first is used"]


def test_one_default_class_is_no_duplicate(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.TLCOverrides")
    assert check(["tlc2.overrides.TLCOverrides"], [folder, build.jar], build) == []


def test_a_class_that_implements_nothing_is_not_an_override_class(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.Plain", "NotAnOverride")
    assert check(["tlc2.overrides.Plain"], [folder, build.jar], build, "Queue") == [
        "tlc2.overrides.Plain (module Queue) is not an override class "
        "(it does not implement tlc2.overrides.ITLCOverrides) and TLC will ignore it"
    ]


def test_a_class_that_implements_the_interface_through_a_superclass_in_the_same_folder_is_not_warned_about(
    tmp_path: Path, build: Build
) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.InheritedOverrides", "InheritedOverrides")
    put_class(folder, "tlc2.overrides.AbstractOverrides", "AbstractOverrides")
    assert check(["tlc2.overrides.InheritedOverrides"], [folder, build.jar], build) == []


def test_the_superclass_may_be_in_another_entry_and_in_a_jar(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.InheritedOverrides", "InheritedOverrides")
    jar = make_jar(tmp_path / "base.jar", {"tlc2/overrides/AbstractOverrides.class": class_bytes("AbstractOverrides")})
    assert check(["tlc2.overrides.InheritedOverrides"], [folder, jar, build.jar], build) == []


def test_a_superclass_that_cannot_be_found_says_nothing(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.InheritedOverrides", "InheritedOverrides")
    assert check(["tlc2.overrides.InheritedOverrides"], [folder, build.jar], build) == []


def test_a_superclass_only_in_the_tools_jar_is_not_followed(tmp_path: Path) -> None:
    folder = tmp_path / "classes"
    put_class(folder, "tlc2.overrides.InheritedOverrides", "InheritedOverrides")
    tools = tmp_path / "tools" / "rolling-abc"
    jar = make_jar(
        tools / "tla2tools.jar", {"tlc2/overrides/AbstractOverrides.class": class_bytes("AbstractOverrides")}
    )
    tools_build = replace(make_build(tmp_path / "other"), path=tools)
    assert tools_build.jar == jar
    assert check(["tlc2.overrides.InheritedOverrides"], [folder, jar], tools_build) == []


def test_a_file_of_random_bytes_gives_no_warning_and_no_exception(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    target = folder / "tlc2" / "overrides" / "X.class"
    target.parent.mkdir(parents=True)
    target.write_bytes(bytes(range(256)))
    assert check(["tlc2.overrides.X"], [folder, build.jar], build) == []


def test_a_truncated_class_file_gives_no_warning(tmp_path: Path, build: Build) -> None:
    folder = tmp_path / "classes"
    target = folder / "tlc2" / "overrides" / "X.class"
    target.parent.mkdir(parents=True)
    target.write_bytes(class_bytes()[:40])
    assert check(["tlc2.overrides.X"], [folder, build.jar], build) == []


# --- the hints (R7 part 4), on research 28's captures --------------------------------------------------------------

BUILDS = sorted(path.name for path in GOLDEN.iterdir())


@pytest.mark.parametrize("build_name", BUILDS)
@pytest.mark.parametrize(
    ("case", "name"), [("override-class-too-new-index", "TLCOverrides"), ("override-class-too-new-listed", "Newer")]
)
def test_the_version_hint_names_both_java_versions_in_the_captures(build_name: str, case: str, name: str) -> None:
    text = (GOLDEN / build_name / f"{case}.out").read_text(encoding="utf-8")
    assert class_version_hint(text) == (
        f"the override class tlc2.overrides.{name} was compiled for Java 25 (class file 69) and TLC runs on "
        "Java 11 (up to 55); rebuild the module with `tlaup module add`, which compiles with `--release 11`, "
        "or run TLC on a newer Java"
    )


@pytest.mark.parametrize("build_name", BUILDS)
def test_the_version_hint_is_none_for_a_text_without_the_sentence(build_name: str) -> None:
    text = (GOLDEN / build_name / "success.out").read_text(encoding="utf-8")
    assert class_version_hint(text) is None
    assert class_version_hint("") is None


def test_the_sentence_may_be_wrapped_over_lines() -> None:
    text = (
        "x has been compiled by a more\nrecent version of the Java Runtime (class file version 65.0), this version "
        "of the Java Runtime only recognizes class file versions up to 61.0"
    )
    hint = class_version_hint(text)
    assert hint is not None
    assert "compiled for Java 21 (class file 65) and TLC runs on Java 17 (up to 61)" in hint


def test_the_general_hint_names_the_classes() -> None:
    assert load_failure_hint(["a.A", "b.B"]) == (
        "TLC failed while loading the spec. If the error comes from a Java override, "
        "one of these classes failed to load: a.A, b.B"
    )


# --- the classes of several modules (M20's property half, finding G1) ---------------------------------------------


def test_the_classes_of_several_modules_are_passed_first_wins_without_duplicates(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "modules", now=FakeClock(START).now)
    first, second = registered(registry, "Alpha"), registered(registry, "Beta")
    put_service(first / "classes", "tlc2.overrides.One\ntlc2.overrides.Two\n")
    put_service(second / "classes", "tlc2.overrides.Two\ntlc2.overrides.Three\n")
    classes = collect_override_classes([first / "classes", second / "classes"])
    assert [(item.name, item.module) for item in classes] == [
        ("tlc2.overrides.One", "Alpha"),
        ("tlc2.overrides.Two", "Alpha"),
        ("tlc2.overrides.Three", "Beta"),
    ]
