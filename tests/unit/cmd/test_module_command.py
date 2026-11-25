"""`tlaup module add` where a feature scenario cannot reach: the folder after `-d` and the exact `-cp` value.

Design 13 M2, decision D61, inventory row M5 in its command form (package 30 tests the unit form). The command runs
in-process through the app; the fake `javac`'s log says how it was started. The clock is injected into every store
and registry the test builds.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

import tlaup.cli
import tlaup.context
from tests.clock import FakeClock
from tests.fakes._fakelib import FAKES_DIR
from tests.steps._store import add_build
from tlaup.cmd.module.list import built_time
from tlaup.modules.build import build_module
from tlaup.modules.registry import Registry
from tlaup.versioning.store import ToolStore

if TYPE_CHECKING:
    from tests.conftest import Isolated
    from tests.fakes.control import Fakes

SOURCES = FAKES_DIR / "module-src"


def javac_compile(fakes: Fakes) -> list[str]:
    """The arguments of the one start of the fake `javac` that compiled (the version check has `-version`)."""
    starts = [line for line in fakes.log("javac") if line["event"] == "start" and "-version" not in line["args"]]
    assert len(starts) == 1
    return [str(arg) for arg in starts[0]["args"]]


def option(args: list[str], name: str) -> str:
    return args[args.index(name) + 1]


def test_the_compile_classpath_is_the_jar_and_the_modules_own_lib(
    isolated: Isolated, fakes: Fakes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = FakeClock()
    fakes.script("javac", {})
    build = add_build(ToolStore(isolated.paths, now=clock.now), tmp_path / "jars", "v1.7.4", pinned=True)
    # Another registered module, with a jar of its own: nothing of it may reach the compile classpath.
    other = tmp_path / "Other"
    (other / "modules").mkdir(parents=True)
    (other / "lib").mkdir()
    (other / "lib" / "other.jar").write_bytes(b"not a jar")
    (other / "modules" / "Other.tla").write_text("---- MODULE Other ----\n====\n", encoding="utf-8")
    registry = Registry(isolated.paths.modules, now=clock.now)
    build_module(
        other,
        registry=registry,
        get_build=lambda: build,
        get_javac=lambda: pytest.fail("no javac for a module without Java"),
        release=11,
        now=clock.now,
    )
    # module_lib_path names a folder with a jar: nothing of it either.
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "shared.jar").write_bytes(b"not a jar")
    monkeypatch.setenv("TLAUP_MODULE_LIB_PATH", str(shared))
    # The source's lib/ holds b.jar and a.jar: the classpath lists them by name.
    shutil.copytree(SOURCES / "Queue", Path.cwd() / "Queue")

    tlaup.context.reset()
    result = CliRunner().invoke(tlaup.cli.app, ["module", "add", "Queue"])
    assert result.exit_code == 0, result.stderr

    args = javac_compile(fakes)
    temporary = Path(option(args, "-d")).parent
    assert temporary.parent == isolated.paths.modules / ".tmp"
    assert Path(option(args, "-d")).name == "classes"
    expected = os.pathsep.join(
        [str(build.jar), str(temporary / "lib" / "a.jar"), str(temporary / "lib" / "b.jar")],
    )
    assert option(args, "-cp") == expected
    assert option(args, "--release") == "11"
    assert option(args, "-encoding") == "UTF-8"
    assert not (isolated.paths.modules / ".tmp" / temporary.name).exists()  # the temporary copy is gone


def test_a_build_time_is_shown_in_utc_to_the_minute_and_an_unreadable_one_as_it_is() -> None:
    assert built_time("2026-11-15T10:00:59Z") == "2026-11-15 10:00 UTC"
    assert built_time("yesterday") == "yesterday"
