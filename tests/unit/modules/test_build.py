"""The module build in a temporary folder (design 13 M2, M3; inventory row M5, its unit form), with the fake javac."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests.clock import FakeClock
from tests.fakes._fakelib import CLASSES_DIR, FAKES_DIR
from tlaup.errors import InvalidName, ModuleBuildError, NoPinnedBuild, PathNotFound
from tlaup.java.locate import JavaRuntime, JavaTool
from tlaup.modules.build import NO_OVERRIDES, build_module
from tlaup.modules.registry import Registry
from tlaup.versioning.store import Build, Source

if TYPE_CHECKING:
    from tests.conftest import Isolated
    from tests.fakes.control import Fakes
    from tlaup.modules.build import BuiltModule

JAVA_SRC = FAKES_DIR / "java-src" / "tlc2" / "overrides"
SERVICE = "META-INF/services/tlc2.overrides.ITLCOverrides"
COMMIT = "bc1b506" + "0" * 33  # 40 hex digits, as the store holds a commit


class Env:
    """The registry, the clock, the pinned build and the javac of one test."""

    def __init__(self, isolated: Isolated, fakes: Fakes, tmp_path: Path) -> None:
        self.clock = FakeClock()
        self.registry = Registry(isolated.paths.modules, now=self.clock.now)
        self.fakes = fakes
        self.tmp_path = tmp_path
        jar = tmp_path / "store" / "rolling-abc" / "tla2tools.jar"
        jar.parent.mkdir(parents=True)
        jar.write_bytes(b"not really a jar")
        self.build = Build(
            id="rolling-abc",
            name="rolling",
            commit=COMMIT,
            calver=None,
            built_at=None,
            sha256="0" * 64,
            size=1,
            prerelease=False,
            source=Source("github-release", "https://example.invalid/tla2tools.jar", 1, None, digest_checked=True),
            installed_at="2026-11-15T00:00:00Z",
            capabilities=frozenset(),
            path=jar.parent,
        )
        javac = shutil.which("javac")
        assert javac is not None
        self.runtime = JavaRuntime(JavaTool(Path(javac).absolute(), "PATH"), "25.0.5", 25, ())
        self.javac_calls = 0
        fakes.script("javac", {})

    @property
    def root(self) -> Path:
        return self.registry.root

    def get_build(self) -> Build:
        return self.build

    def get_javac(self) -> JavaRuntime:
        self.javac_calls += 1
        return self.runtime

    def add(self, source: Path, **kwargs: Any) -> BuiltModule:
        options: dict[str, Any] = {
            "registry": self.registry,
            "get_build": self.get_build,
            "get_javac": self.get_javac,
            "release": 11,
            "now": self.clock.now,
        }
        options.update(kwargs)
        return build_module(source, **options)

    def javac_starts(self) -> list[dict[str, Any]]:
        return [line for line in self.fakes.log("javac") if line["event"] == "start"]

    def tmp_entries(self) -> list[str]:
        tmp = self.root / ".tmp"
        return sorted(path.name for path in tmp.iterdir()) if tmp.exists() else []


@pytest.fixture
def env(isolated: Isolated, fakes: Fakes, tmp_path: Path) -> Env:
    return Env(isolated, fakes, tmp_path)


def make_source(
    folder: Path, *, java: tuple[str, ...] = ("DirectOverrides",), where: str = "tlc2/overrides", tla: bool = True
) -> Path:
    """A module folder: ``modules/<name>.tla`` and the named sources of tests/fakes/java-src/ under ``where``."""
    folder.mkdir(parents=True)
    if tla:
        (folder / "modules").mkdir()
        (folder / "modules" / f"{folder.name}.tla").write_text(f"---- MODULE {folder.name} ----\n====\n")
    for name in java:
        target = folder / where / f"{name}.java"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(JAVA_SRC / f"{name}.java", target)
    return folder


def fail(*_: object) -> Any:
    pytest.fail("called, though the module has no Java sources")


def snapshot(folder: Path) -> dict[str, bytes]:
    return {str(path.relative_to(folder)): path.read_bytes() for path in sorted(folder.rglob("*")) if path.is_file()}


def tree(folder: Path) -> list[str]:
    return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


def option(args: list[str], name: str) -> str:
    return args[args.index(name) + 1]


def test_a_module_of_tla_files_only(env: Env, tmp_path: Path) -> None:
    source = make_source(tmp_path / "Queue", java=())
    built = env.add(source, get_build=fail, get_javac=fail)
    assert built.path == env.root / "Queue"
    assert (built.replaced, built.override_classes, built.warnings) == (False, (), ())
    record = json.loads((built.path / "module.json").read_text(encoding="utf-8"))
    assert (record["javac"], record["release"], record["built_against"]) == (None, None, None)
    assert record["override_classes"] == []
    assert not (built.path / "classes").exists()
    assert (built.path / "modules" / "Queue.tla").is_file()
    assert env.javac_starts() == []
    assert env.tmp_entries() == []


def test_the_compile_classpath_is_narrow_row_m5(env: Env, tmp_path: Path) -> None:
    other = make_source(tmp_path / "Other")
    (other / "lib").mkdir()
    (other / "lib" / "other.jar").write_bytes(b"jar")
    env.add(other)
    assert (env.root / "Other" / "classes").is_dir()
    source = make_source(tmp_path / "Queue")
    (source / "lib").mkdir()
    (source / "lib" / "b.jar").write_bytes(b"b")
    (source / "lib" / "a.jar").write_bytes(b"a")
    env.add(source)
    args = env.javac_starts()[-1]["args"]
    copy = Path(option(args, "-d")).parent
    expected = [str(env.build.jar), str(copy / "lib" / "a.jar"), str(copy / "lib" / "b.jar")]
    assert option(args, "-cp") == os.pathsep.join(expected)


def test_a_module_with_java_sources(env: Env, tmp_path: Path) -> None:
    source = make_source(tmp_path / "Queue", java=("DirectOverrides", "NotAnOverride"))
    built = env.add(source)
    [start] = env.javac_starts()
    args = start["args"]
    out = Path(option(args, "-d"))
    assert out.parent.parent == env.root / ".tmp"
    assert out.name == "classes"
    sources = [str(out.parent / "tlc2" / "overrides" / f"{name}.java") for name in ("DirectOverrides", "NotAnOverride")]
    assert args == ["-encoding", "UTF-8", "--release", "11", "-cp", str(env.build.jar), "-d", str(out), *sources]
    assert Path(start["path"]) == env.runtime.tool.path
    classes = built.path / "classes"
    assert (classes / "tlc2" / "overrides" / "DirectOverrides.class").read_bytes() == (
        CLASSES_DIR / "tlc2" / "overrides" / "DirectOverrides.class"
    ).read_bytes()
    assert (classes / SERVICE).read_text(encoding="utf-8") == "tlc2.overrides.DirectOverrides\n"
    assert built.override_classes == ("tlc2.overrides.DirectOverrides",)
    assert built.replaced is False
    assert built.warnings == ()
    assert json.loads((built.path / "module.json").read_text(encoding="utf-8")) == {
        "schema": 1,
        "name": "Queue",
        "built_at": "2026-11-15T00:00:00Z",
        "source": str(source.resolve()),
        "javac": "25.0.5",
        "release": 11,
        "built_against": f"rolling@{COMMIT}",
        "override_classes": ["tlc2.overrides.DirectOverrides"],
    }
    assert [module.name for module in env.registry.list()] == ["Queue"]
    assert env.tmp_entries() == []


def test_sources_under_modules_are_compiled_too(env: Env, tmp_path: Path) -> None:
    source = make_source(tmp_path / "Queue", java=("DirectOverrides",), where="modules/tlc2/overrides")
    built = env.add(source)
    [start] = env.javac_starts()
    copy = Path(option(start["args"], "-d")).parent
    assert start["args"][-1] == str(copy / "modules" / "tlc2" / "overrides" / "DirectOverrides.java")
    assert built.override_classes == ("tlc2.overrides.DirectOverrides",)


def test_built_against_is_the_bare_name_without_a_commit(env: Env, tmp_path: Path) -> None:
    env.build = replace(env.build, commit=None)
    built = env.add(make_source(tmp_path / "Queue"))
    assert json.loads((built.path / "module.json").read_text())["built_against"] == "rolling"


def test_the_same_module_added_twice(env: Env, tmp_path: Path) -> None:
    source = make_source(tmp_path / "Queue")
    (source / "modules" / "First.tla").write_text("first")
    first = env.add(source)
    (source / "modules" / "First.tla").unlink()
    (source / "modules" / "Second.tla").write_text("second")
    env.clock.advance(60)
    second = env.add(source)
    assert (first.replaced, second.replaced) == (False, True)
    assert sorted(path.name for path in (second.path / "modules").iterdir()) == ["Queue.tla", "Second.tla"]
    assert json.loads((second.path / "module.json").read_text())["built_at"] == "2026-11-15T00:01:00Z"
    assert env.tmp_entries() == []


def test_a_compile_error_keeps_the_registered_module(env: Env, fakes: Fakes, tmp_path: Path) -> None:
    source = make_source(tmp_path / "Queue")
    env.add(source)
    before = snapshot(env.root / "Queue")
    fakes.script("javac", {"fail_with": "syntax-error.txt"})
    with pytest.raises(ModuleBuildError) as caught:
        env.add(source)
    recorded = (FAKES_DIR / "javac-errors" / "syntax-error.txt").read_text(encoding="utf-8").rstrip()
    assert caught.value.details is not None
    assert recorded in caught.value.details
    copy = Path(option(env.javac_starts()[-1]["args"], "-d")).parent
    assert f"classpath: {env.build.jar}" in caught.value.details
    assert not copy.exists()
    assert snapshot(env.root / "Queue") == before
    assert env.tmp_entries() == []


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_a_javac_that_does_not_finish(env: Env, fakes: Fakes, tmp_path: Path) -> None:
    source = make_source(tmp_path / "Queue")
    env.add(source)
    before = snapshot(env.root / "Queue")
    fakes.script("javac", {"delay_ms": 20_000})
    with pytest.raises(ModuleBuildError, match=r"javac did not finish in 0\.5 seconds"):
        env.add(source, timeout=0.5)
    start = env.javac_starts()[-1]
    if os.name == "posix":
        assert not _process_alive(start["pid"])
    assert snapshot(env.root / "Queue") == before
    assert env.tmp_entries() == []


@pytest.mark.parametrize("java", [("DirectOverrides",), ()])
def test_old_entries_of_tmp_are_removed(env: Env, tmp_path: Path, java: tuple[str, ...]) -> None:
    tmp = env.root / ".tmp"
    old = tmp / ((env.clock.now() - timedelta(days=1, minutes=1)).strftime("%Y%m%dT%H%M%SZ") + "-0a1b")
    young = tmp / ((env.clock.now() - timedelta(minutes=1)).strftime("%Y%m%dT%H%M%SZ") + "-2c3d")
    old_file = tmp / ((env.clock.now() - timedelta(days=2)).strftime("%Y%m%dT%H%M%SZ") + "-4e5f")
    timeless = tmp / "no-time-here"
    for folder in (old, young, timeless):
        (folder / "classes").mkdir(parents=True)
    old_file.write_text("left by a killed tlaup")
    env.add(make_source(tmp_path / "Queue", java=java))
    assert env.tmp_entries() == sorted([young.name, timeless.name])


def test_what_is_copied(env: Env, tmp_path: Path) -> None:
    source = make_source(tmp_path / "Queue")
    for name in ("lib", "test", "tests", "other"):
        (source / name).mkdir()
        (source / name / "file.txt").write_text(name)
    built = env.add(source)
    assert sorted(path.name for path in built.path.iterdir()) == ["classes", "lib", "module.json", "modules", "tlc2"]
    assert (built.path / "tlc2" / "overrides" / "DirectOverrides.java").is_file()
    assert (built.path / "lib" / "file.txt").read_text() == "lib"


def test_the_source_folders_own_service_file(env: Env, fakes: Fakes, tmp_path: Path) -> None:
    unreadable = tmp_path / "unreadable" / "tlc2" / "overrides"
    unreadable.mkdir(parents=True)
    (unreadable / "DirectOverrides.class").write_bytes(b"not a class file: reading it would fail the build")
    fakes.script("javac", {"classes": str(tmp_path / "unreadable")})
    source = make_source(tmp_path / "Queue")
    own = b"# the module's own\ntlc2.overrides.DirectOverrides  # trailing\n\na.Other\n"
    (source / SERVICE).parent.mkdir(parents=True)
    (source / SERVICE).write_bytes(own)
    built = env.add(source)
    assert (built.path / "classes" / SERVICE).read_bytes() == own
    assert built.override_classes == ("tlc2.overrides.DirectOverrides", "a.Other")
    assert built.warnings == ()


def test_no_override_class(env: Env, tmp_path: Path) -> None:
    built = env.add(make_source(tmp_path / "Queue", java=("NotAnOverride", "AbstractOverrides", "ITLCOverrides")))
    assert not (built.path / "classes" / SERVICE).exists()
    assert built.override_classes == ()
    assert built.warnings == (NO_OVERRIDES,)
    assert "no override index class was found" in NO_OVERRIDES


def test_a_string_with_slashes_does_not_make_an_override(env: Env, tmp_path: Path) -> None:
    source = make_source(tmp_path / "Queue", java=("NotAnOverride", "DirectOverrides"))
    text = (source / "tlc2" / "overrides" / "NotAnOverride.java").read_text(encoding="utf-8")
    assert 'String u = "http://x"; // implements ITLCOverrides' in text
    built = env.add(source)
    assert built.override_classes == ("tlc2.overrides.DirectOverrides",)


def test_override_classes_through_a_superclass_and_nested(env: Env, tmp_path: Path) -> None:
    java = ("AbstractOverrides", "InheritedOverrides", "Outer", "ITLCOverrides")
    built = env.add(make_source(tmp_path / "Queue", java=java))
    assert built.override_classes == ("tlc2.overrides.InheritedOverrides", "tlc2.overrides.Outer$Inner")


def test_the_javac_lookups_warnings(env: Env, tmp_path: Path) -> None:
    env.runtime = JavaRuntime(env.runtime.tool, None, None, ("could not read the version of javac",))
    built = env.add(make_source(tmp_path / "Queue"))
    assert built.warnings == ("could not read the version of javac",)
    assert json.loads((built.path / "module.json").read_text())["javac"] is None


def test_a_source_that_is_not_a_folder(env: Env, tmp_path: Path) -> None:
    (tmp_path / "file").write_text("")
    for source in (tmp_path / "missing", tmp_path / "file"):
        with pytest.raises(PathNotFound):
            env.add(source)
    assert not env.root.exists()


def test_a_source_folder_with_an_invalid_name(env: Env, tmp_path: Path) -> None:
    source = make_source(tmp_path / "my module")
    with pytest.raises(InvalidName) as caught:
        env.add(source)
    assert caught.value.hint is not None
    assert "rename the folder" in caught.value.hint
    assert not env.root.exists()
    assert env.javac_starts() == []


def test_the_root_folder_has_no_name(env: Env) -> None:
    with pytest.raises(InvalidName):
        env.add(Path(Path.cwd().anchor))


def test_no_pinned_build(env: Env, tmp_path: Path) -> None:
    def no_build() -> Build:
        raise NoPinnedBuild("no build is pinned")  # noqa: TRY003

    with pytest.raises(NoPinnedBuild):
        env.add(make_source(tmp_path / "Queue"), get_build=no_build)
    assert env.javac_calls == 0
    assert env.tmp_entries() == []
    assert env.javac_starts() == []
