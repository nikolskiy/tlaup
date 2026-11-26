"""`resolve_tool_invocation` and `build_tool_command` (design 21, head and S1 step 7; 11 R11).

Real files under `tmp_path`, a stand-in `get_build` that counts its calls and returns a `Build` made with chosen
capabilities, the fake `java` whose log shows whether Java was started at all, and a fixed clock for the registry.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.clock import FakeClock
from tests.unit.tlc.test_invocation import make_build, register
from tlaup.config.loader import load_settings
from tlaup.errors import SpecNotFound, ToolNotInBuild, UsageError
from tlaup.modules.registry import Registry
from tlaup.tlc.invocation import TlcRequest, resolve_tlc_invocation
from tlaup.tools import ENTRY_POINTS
from tlaup.tools.invocation import ToolInvocation, build_tool_command, resolve_tool_invocation

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from tests.conftest import Isolated
    from tests.fakes.control import Fakes
    from tlaup.config.schema import Settings
    from tlaup.versioning.store import Build

START = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
SPEC_TEXT = "---- MODULE Spec ----\n====\n"


@dataclass
class World:
    """A spec in a project under the working folder, the settings of an empty home, and the preflight's inputs."""

    isolated: Isolated
    build: Build
    settings: Settings
    env: dict[str, str]
    calls: list[str] = field(default_factory=list)

    @property
    def cwd(self) -> Path:
        return self.isolated.work

    def get_build(self) -> Build:
        self.calls.append("get_build")
        return self.build

    def never(self) -> Build:
        pytest.fail("get_build was called")

    def resolve(
        self,
        tool: str = "sany",
        spec: str | None = "project/Spec",
        *,
        java_opts: Sequence[str] = (),
        extra_args: Sequence[str] = (),
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        settings: Settings | None = None,
        get_build: object = None,
    ) -> ToolInvocation:
        return resolve_tool_invocation(
            tool,  # type: ignore[arg-type]
            spec,
            java_opts=java_opts,
            extra_args=extra_args,
            paths=self.isolated.paths,
            settings=settings or self.settings,
            env=env if env is not None else self.env,
            cwd=cwd or self.cwd,
            home=self.isolated.home,
            get_build=get_build or self.get_build,  # type: ignore[arg-type]
            now=FakeClock(START).now,
        )

    def java_started(self, fakes: Fakes) -> bool:
        return bool(fakes.log("java"))


@pytest.fixture
def world(isolated: Isolated, fakes: Fakes) -> World:
    fakes.script("java", {})  # answers -version with Java 25 and logs every start
    project = isolated.work / "project"
    (project / "modules").mkdir(parents=True)
    (project / "Spec.tla").write_text(SPEC_TEXT, encoding="utf-8")
    build = make_build(isolated.paths.tools / "rolling-0123456789ab", frozenset({"repl"}))
    settings = load_settings(isolated.paths, {}).settings
    return World(isolated, build, settings, {"PATH": str(isolated.bin), "LC_ALL": "C.UTF-8"})


# --- the order: step 0, the spec, the build, the capability, Java -------------------------------------------------


def test_d_with_nothing_else_valid_is_a_usage_error_and_no_build_is_asked_for(world: World) -> None:
    with pytest.raises(UsageError) as caught:
        world.resolve(spec="no/such/Spec", extra_args=("-d",), get_build=world.never)
    assert caught.value.exit_code == 2
    assert "-d" in caught.value.message
    assert caught.value.hint is not None
    assert "tlaup tool path" in caught.value.hint


def test_a_missing_spec_is_not_found_and_no_build_is_asked_for(world: World, fakes: Fakes) -> None:
    with pytest.raises(SpecNotFound) as caught:
        world.resolve(spec="no/such/Spec", get_build=world.never)
    assert caught.value.exit_code == 4
    assert not world.java_started(fakes)


def test_an_unbalanced_quote_in_the_java_options_comes_before_the_spec_is_looked_at(world: World) -> None:
    env = {**world.env, "TLAUP_JAVA_OPTS": '-Dx="a b'}
    with pytest.raises(UsageError) as caught:
        world.resolve(spec="no/such/Spec", env=env, get_build=world.never)
    assert "TLAUP_JAVA_OPTS" in caught.value.message


def test_the_build_is_asked_for_once_and_java_after_it(world: World, fakes: Fakes) -> None:
    inv = world.resolve()
    assert world.calls == ["get_build"]
    assert [entry["main"] for entry in fakes.log("java") if entry["event"] == "start"] == ["-version"]
    assert inv.java.major == 25
    assert inv.warnings == inv.java.warnings


# --- the refusal of -d, exactly ---------------------------------------------------------------------------------------


def test_the_argument_d_is_refused(world: World) -> None:
    with pytest.raises(UsageError):
        world.resolve(extra_args=("-d",))


@pytest.mark.parametrize("argument", ["-dl", "-error-codes", "-D", "-d2", "d", "--d", "-ld"])
def test_anything_else_is_not_refused(world: World, argument: str) -> None:
    inv = world.resolve(extra_args=(argument,))
    assert inv.args == (argument,)


def test_d_is_refused_for_sany_alone(world: World) -> None:
    inv = world.resolve("pcal", extra_args=("-d",))
    assert inv.args == ("-d",)


# --- the capability -----------------------------------------------------------------------------------------------


def test_repl_without_the_capability_is_not_in_the_build_and_java_is_not_started(world: World, fakes: Fakes) -> None:
    world.build = make_build(world.isolated.paths.tools / "v1-0123456789ab", frozenset())
    with pytest.raises(ToolNotInBuild) as caught:
        world.resolve("repl", None)
    assert caught.value.exit_code == 3
    assert "REPL" in caught.value.message
    assert caught.value.hint is not None
    assert "tlaup tool install rolling" in caught.value.hint
    assert not world.java_started(fakes)


def test_repl_with_the_capability_is_built(world: World) -> None:
    inv = world.resolve("repl", None)
    assert inv.main_class == ENTRY_POINTS["repl"]


@pytest.mark.parametrize("tool", ["sany", "pcal"])
def test_sany_and_pcal_need_no_capability(world: World, tool: str) -> None:
    world.build = make_build(world.isolated.paths.tools / "v1-0123456789ab", frozenset())
    assert world.resolve(tool).main_class == ENTRY_POINTS[tool]


# --- what each tool gets ------------------------------------------------------------------------------------------


def test_sany_runs_in_the_spec_folder_as_named_with_the_spec_beside_the_arguments(world: World) -> None:
    inv = world.resolve(extra_args=("-xy",))
    assert inv.cwd == world.cwd / "project"
    assert inv.spec == world.cwd / "project" / "Spec.tla"
    assert inv.args == ("-xy",)
    assert inv.jvm_options == ("-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC")


def test_the_spec_folder_is_kept_as_named_when_reached_through_a_link(world: World) -> None:
    link = world.cwd / "link"
    try:
        link.symlink_to(world.cwd / "project", target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links cannot be made here")
    inv = world.resolve(spec="link/Spec")
    assert inv.cwd == link


def test_the_java_options_are_the_setting_then_the_variable_then_each_flag(world: World) -> None:
    env = {**world.env, "TLAUP_JAVA_OPTS": "-Dfrom.env=1"}
    inv = world.resolve(java_opts=("-Xss8m",), env=env)
    assert inv.jvm_options[-2:] == ("-Dfrom.env=1", "-Xss8m")


def test_sany_gets_the_classpath_and_library_of_a_tlc_run_of_the_same_spec(world: World) -> None:
    registry = Registry(world.isolated.paths.modules, now=FakeClock(START).now)
    register(registry, "beta")
    register(registry, "alpha")
    jars = world.cwd / "jars"
    jars.mkdir()
    (jars / "extra.jar").write_bytes(b"jar")
    settings = world.settings.model_copy(update={"module_lib_path": "jars"})
    tool = world.resolve(settings=settings)
    tlc = resolve_tlc_invocation(
        TlcRequest(spec="project/Spec"),
        paths=world.isolated.paths,
        settings=settings,
        env=world.env,
        cwd=world.cwd,
        home=world.isolated.home,
        get_build=lambda: world.build,
        now=FakeClock(START).now,
        rng=random.Random(1),
        platform="linux",
    )
    assert tool.classpath == tlc.classpath
    assert tool.tla_library == tlc.tla_library
    assert tool.tla_library[0] == world.cwd / "project" / "modules"
    assert len(tool.tla_library) == 3
    assert jars / "extra.jar" in tool.classpath


def test_pcal_gets_the_jar_alone(world: World) -> None:
    register(Registry(world.isolated.paths.modules, now=FakeClock(START).now), "alpha")
    inv = world.resolve("pcal")
    assert inv.classpath == (world.build.jar,)
    assert inv.tla_library == ()
    assert inv.cwd == world.cwd / "project"


def test_repl_has_no_spec_no_folder_and_the_paths_of_a_run_with_no_project_root(world: World) -> None:
    alpha = register(Registry(world.isolated.paths.modules, now=FakeClock(START).now), "alpha")
    inv = world.resolve("repl", None)
    assert inv.spec is None
    assert inv.cwd is None
    assert inv.tla_library == (alpha / "modules",)  # not the project's own modules/ folder
    assert inv.classpath == (alpha / "modules", alpha / "classes", world.build.jar)


# --- build_tool_command -------------------------------------------------------------------------------------------


def test_the_spec_file_name_is_the_last_argument_after_the_tools_arguments(world: World) -> None:
    java_inv = build_tool_command(world.resolve(extra_args=("-a", "-b")))
    assert java_inv.args == ("-a", "-b", "Spec.tla")
    assert java_inv.cwd == world.cwd / "project"
    assert java_inv.main_class == "tla2sany.SANY"
    assert java_inv.java == world.isolated.bin / "java"


def test_pcal_gets_its_file_name_last_too(world: World) -> None:
    java_inv = build_tool_command(world.resolve("pcal", extra_args=("-nocfg",)))
    assert java_inv.args == ("-nocfg", "Spec.tla")
    assert java_inv.main_class == "pcal.trans"
    assert dict(java_inv.system_properties) == {}


def test_repl_has_no_spec_argument_and_no_folder(world: World) -> None:
    java_inv = build_tool_command(world.resolve("repl", None, extra_args=("-x",)))
    assert java_inv.args == ("-x",)
    assert java_inv.cwd is None
    assert java_inv.main_class == "tlc2.REPL"


def test_the_library_property_is_the_folders_joined_and_absent_when_there_are_none(world: World) -> None:
    java_inv = build_tool_command(world.resolve())
    assert dict(java_inv.system_properties) == {"TLA-Library": str(world.cwd / "project" / "modules")}
    (world.cwd / "project" / "modules").rmdir()
    assert build_tool_command(world.resolve()).system_properties == ()
    argv = java_inv.argv()
    assert argv[argv.index("-cp") + 1].split(os.pathsep)[-1] == str(world.build.jar)
