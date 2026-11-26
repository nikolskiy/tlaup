"""The preflight `resolve_tlc_invocation` (design 20 G1, 11 R11) and the rules it applies: the passthrough table
(11 R8), the spec and cfg (11 R4), the path warning (11 R3), the per-run values (11 R6), the Java options (13 J1)
and the classpath of a run (13 M2). Inventory rows S7, S10 to S12, C6 and R25's builder half.

Real files under `tmp_path`, a hand-made `Build`, the fake `java` on PATH, a fixed clock and a seeded random source.
"""

from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.clock import FakeClock
from tlaup.config.loader import load_settings
from tlaup.errors import CfgNotFound, ConflictingOptions, NoPinnedBuild, SpecNotFound, UsageError
from tlaup.modules.registry import RegisteredModule, Registry, write_record
from tlaup.tlc.command import build_tlc_command
from tlaup.tlc.invocation import (
    FP_MAX,
    SEED_MAX,
    TlcInvocation,
    TlcRequest,
    find_recovered_run,
    new_run_id,
    resolve_tlc_invocation,
)
from tlaup.versioning.store import Build, Source

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.conftest import Isolated
    from tests.fakes.control import Fakes
    from tlaup.config.schema import Settings

DEFAULT_OPTS = ("-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC")
START = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
CAPABLE = frozenset({"calver", "overrides_property", "no_generate_spec_te"})


def make_build(folder: Path, capabilities: frozenset[str] = CAPABLE) -> Build:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "tla2tools.jar").write_bytes(b"jar")
    return Build(
        id=folder.name,
        name="rolling",
        commit=None,
        calver=None,
        built_at=None,
        sha256="0" * 64,
        size=3,
        prerelease=False,
        source=Source("github-release", "https://example.invalid/tla2tools.jar", 1, None, digest_checked=True),
        installed_at="2026-11-15T00:00:00Z",
        capabilities=capabilities,
        path=folder,
    )


def never() -> Build:
    pytest.fail("get_build was called")


@dataclass
class World:
    """A spec in a project under the working folder, the settings of an empty home, and the preflight's inputs."""

    isolated: Isolated
    tmp_path: Path
    build: Build
    settings: Settings
    env: dict[str, str]

    @property
    def cwd(self) -> Path:
        return self.isolated.work

    @property
    def runs(self) -> Path:
        return self.isolated.paths.runs

    def resolve(
        self,
        request: TlcRequest | None = None,
        *,
        get_build: Callable[[], Build] | None = None,
        cwd: Path | None = None,
        settings: Settings | None = None,
        seed: int = 1,
        platform: str = "linux",
        **request_fields: object,
    ) -> TlcInvocation:
        if request is None:
            request = TlcRequest(**{"spec": "project/Spec", **request_fields})  # type: ignore[arg-type]
        return resolve_tlc_invocation(
            request,
            paths=self.isolated.paths,
            settings=settings or self.settings,
            env=self.env,
            cwd=cwd or self.cwd,
            home=self.isolated.home,
            get_build=get_build or (lambda: self.build),
            now=FakeClock(START).now,
            rng=random.Random(seed),
            platform=platform,
        )


@pytest.fixture
def world(isolated: Isolated, tmp_path: Path, fakes: Fakes) -> World:
    fakes.script("java", {})  # answers -version with Java 25 and logs every start
    project = isolated.work / "project"
    (project / "modules").mkdir(parents=True)
    (project / "Spec.tla").write_text("---- MODULE Spec ----\n====\n", encoding="utf-8")
    build = make_build(isolated.paths.tools / "rolling-0123456789ab")
    settings = load_settings(isolated.paths, {}).settings
    env = {"PATH": str(isolated.bin), "LC_ALL": "C.UTF-8"}
    return World(isolated, tmp_path, build, settings, env)


# --- R8: the table, row by row -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "flag"),
    [
        ({"workers": "2"}, "-workers"),
        ({"coverage": True}, "-coverage"),
        ({"cfg": "Spec"}, "-config"),
    ],
)
def test_a_flag_that_a_tlaup_option_also_gives_conflicts(world: World, fields: dict[str, object], flag: str) -> None:
    with pytest.raises(ConflictingOptions) as caught:
        world.resolve(get_build=never, extra_args=(flag, "4"), **fields)
    assert caught.value.exit_code == 2
    assert flag in caught.value.message


def test_workers_among_tlcs_arguments_alone_passes_no_workers_of_tlaups(world: World) -> None:
    inv = world.resolve(extra_args=("-workers", "4"))
    assert inv.workers is None
    assert build_tlc_command(inv).args.count("-workers") == 1


def test_coverage_among_tlcs_arguments_alone_is_passed_through(world: World) -> None:
    inv = world.resolve(extra_args=("-coverage", "2"))
    assert inv.coverage is False
    assert inv.extra_args == ("-coverage", "2")


def test_config_among_tlcs_arguments_alone_is_passed_through_unvalidated(world: World) -> None:
    inv = world.resolve(extra_args=("-config", "Missing.cfg"))
    assert inv.cfg is None
    assert inv.config_arg is None
    assert build_tlc_command(inv).args[-3:] == ("-config", "Missing.cfg", str(inv.spec))


def test_metadir_among_tlcs_arguments_leaves_no_metadir_of_tlaups(world: World) -> None:
    inv = world.resolve(extra_args=("-metadir", "X"))
    assert inv.metadir is None
    assert inv.run_id  # still chosen: 35 names the run by it


@pytest.mark.parametrize("flag", ["-tool", "-difftrace"])
def test_tool_and_difftrace_are_passed_through(world: World, flag: str) -> None:
    inv = world.resolve(extra_args=(flag,))
    assert inv.extra_args == (flag,)
    assert inv.tool_mode is True  # two -tool in a parsed run are harmless
    assert build_tlc_command(inv).args[-2:] == (flag, str(inv.spec))


def test_a_flag_is_matched_exactly(world: World) -> None:
    inv = world.resolve(workers="2", extra_args=("-workers=4", "-COVERAGE"), coverage=True)
    assert inv.workers == "2"
    assert inv.extra_args == ("-workers=4", "-COVERAGE")


# --- workers -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["auto", "4", "1", "64"])
def test_workers_auto_or_a_positive_integer(world: World, text: str) -> None:
    assert world.resolve(workers=text).workers == text


def test_workers_take_the_setting_when_the_request_has_none(world: World) -> None:
    assert world.resolve().workers == "auto"
    settings = world.settings.model_copy(update={"tlc": world.settings.tlc.model_copy(update={"workers": 3})})
    assert world.resolve(settings=settings).workers == "3"


@pytest.mark.parametrize("text", ["0", "x", "+3", "AUTO", " auto ", "4 ", "-1", "", "2.0"])
def test_other_workers_values_are_a_usage_error(world: World, text: str) -> None:
    with pytest.raises(UsageError) as caught:
        world.resolve(get_build=never, workers=text, spec="Missing")
    assert caught.value.exit_code == 2
    assert not isinstance(caught.value, ConflictingOptions)


# --- the order (R11) -----------------------------------------------------------------------------------------------


def test_a_missing_spec_is_reported_before_the_build_is_asked_for(world: World) -> None:
    with pytest.raises(SpecNotFound):
        world.resolve(get_build=never, spec="Missing")


def test_conflicting_options_are_reported_before_a_missing_spec(world: World) -> None:
    with pytest.raises(ConflictingOptions):
        world.resolve(get_build=never, spec="Missing", workers="2", extra_args=("-workers", "4"))


def test_an_unbalanced_quote_in_the_java_options_is_reported_before_a_missing_spec(world: World) -> None:
    world.env["TLAUP_JAVA_OPTS"] = '-Dx="a'
    with pytest.raises(UsageError) as caught:
        world.resolve(get_build=never, spec="Missing")
    assert "TLAUP_JAVA_OPTS" in caught.value.message


def test_a_missing_cfg_is_reported_before_the_build_is_asked_for(world: World) -> None:
    with pytest.raises(CfgNotFound):
        world.resolve(get_build=never, cfg="Missing")


def test_a_failing_build_stops_before_java_is_asked(world: World, fakes: Fakes) -> None:
    def no_pin() -> Build:
        raise NoPinnedBuild("no version pinned")  # noqa: TRY003

    with pytest.raises(NoPinnedBuild):
        world.resolve(get_build=no_pin)
    assert fakes.log("java") == []  # step 4 was not reached


def test_java_is_asked_after_the_build(world: World, fakes: Fakes) -> None:
    inv = world.resolve()
    assert [entry["main"] for entry in fakes.log("java") if entry["event"] == "start"] == ["-version"]
    assert inv.java.tool.path == world.isolated.bin / "java"
    assert inv.java.major == 25


# --- R4: spec, cfg, working folder ---------------------------------------------------------------------------------


def test_the_spec_is_absolute_and_the_cwd_is_where_tlaup_started(world: World) -> None:
    inv = world.resolve()
    assert inv.spec.is_absolute()
    assert inv.spec == world.cwd / "project" / "Spec.tla"
    assert inv.cwd == world.cwd
    assert inv.project_root == world.cwd / "project"
    assert build_tlc_command(inv).cwd is None
    assert build_tlc_command(inv).args[-1] == str(inv.spec)


def test_a_cfg_outside_the_project_is_the_one_tlc_gets(world: World) -> None:
    outside = world.cwd / "outside"
    outside.mkdir()
    (outside / "out.cfg").write_text("INIT Init\n", encoding="utf-8")
    (world.cwd / "project" / "out.cfg").write_text("decoy\n", encoding="utf-8")  # same name in the project root
    inv = world.resolve(spec="Spec", cfg="../outside/out.cfg", cwd=world.cwd / "project")
    assert inv.cfg == world.cwd / "project" / ".." / "outside" / "out.cfg"
    assert inv.config_arg == os.path.join("..", "outside", "out.cfg")  # noqa: PTH118
    assert (inv.spec.parent / inv.config_arg).samefile(outside / "out.cfg")
    assert build_tlc_command(inv).args[-3:] == ("-config", inv.config_arg, str(inv.spec))


def test_without_cfg_nothing_is_checked_and_no_config_is_passed_row_s7(world: World) -> None:
    assert not (world.cwd / "project" / "Spec.cfg").exists()
    inv = world.resolve()
    assert inv.cfg is None
    assert inv.config_arg is None
    assert "-config" not in build_tlc_command(inv).args


# --- R3: the path warning ------------------------------------------------------------------------------------------


def make_spec(world: World, folder: str) -> str:
    path = world.cwd / folder / "Spec.tla"
    path.parent.mkdir(parents=True)
    path.write_text("---- MODULE Spec ----\n====\n", encoding="utf-8")
    return f"{folder}/Spec"


def test_a_non_ascii_spec_path_under_the_c_locale_gives_the_warning(world: World) -> None:
    spec = make_spec(world, "café")
    world.env["LC_ALL"] = "C"
    (warning,) = world.resolve(spec=spec).warnings
    assert "café" in warning
    assert "\n" not in warning
    assert warning.endswith(
        "has characters outside ASCII and the locale is not UTF-8; "
        "TLC cannot open it under the C locale: run with LC_ALL=C.UTF-8"
    )


def test_no_path_warning_on_windows(world: World) -> None:
    spec = make_spec(world, "café")
    world.env["LC_ALL"] = "C"
    assert world.resolve(spec=spec, platform="win32").warnings == ()


@pytest.mark.parametrize("locale", ["C.UTF-8", "en_US.utf8", "de_DE.UTF8"])
def test_a_non_ascii_spec_path_under_a_utf8_locale_gives_none(world: World, locale: str) -> None:
    spec = make_spec(world, "café")
    world.env["LC_ALL"] = locale
    assert world.resolve(spec=spec).warnings == ()


def test_the_first_locale_variable_that_is_set_decides(world: World) -> None:
    spec = make_spec(world, "café")
    world.env.update({"LC_ALL": "", "LC_CTYPE": "C", "LANG": "C.UTF-8"})
    assert len(world.resolve(spec=spec).warnings) == 1
    world.env.update({"LC_CTYPE": "", "LANG": "C.UTF-8"})
    assert world.resolve(spec=spec).warnings == ()
    for name in ("LC_ALL", "LC_CTYPE", "LANG"):
        del world.env[name]
    assert len(world.resolve(spec=spec).warnings) == 1  # nothing set: the C locale


def test_a_non_ascii_cfg_path_under_the_c_locale_gives_the_warning(world: World) -> None:
    (world.cwd / "project" / "Spécial.cfg").write_text("INIT Init\n", encoding="utf-8")
    world.env["LC_ALL"] = "C"
    (warning,) = world.resolve(cfg="Spécial").warnings
    assert "Spécial.cfg" in warning
    assert "cfg" in warning.split()[1]
    world.env["LC_ALL"] = "C.UTF-8"
    assert world.resolve(cfg="Spécial").warnings == ()


def test_an_ascii_path_under_the_c_locale_gives_none(world: World) -> None:
    world.env["LC_ALL"] = "C"
    assert world.resolve().warnings == ()


# --- the per-run values (R6) ---------------------------------------------------------------------------------------


def test_the_run_id_and_metadir_and_nothing_made(world: World) -> None:
    inv = world.resolve()
    assert re.fullmatch(r"20261115T100000Z-[0-9a-f]{8}", inv.run_id)
    assert inv.metadir == world.runs / inv.run_id
    assert not world.runs.exists() or list(world.runs.iterdir()) == []


def test_new_run_id_is_repeatable_with_one_seed() -> None:
    clock = FakeClock(START)
    assert new_run_id(clock.now, random.Random(5)) == new_run_id(clock.now, random.Random(5))
    assert new_run_id(clock.now, random.Random(5)) != new_run_id(clock.now, random.Random(6))


def test_new_run_id_is_in_utc() -> None:
    clock = FakeClock(datetime(2026, 11, 15, 11, 0, tzinfo=timezone(timedelta(hours=1))))
    assert new_run_id(clock.now, random.Random(1)).startswith("20261115T100000Z-")


@pytest.mark.parametrize("seed", range(20))
def test_fp_and_seed_are_drawn_when_tlcs_arguments_have_neither(world: World, seed: int) -> None:
    inv = world.resolve(seed=seed)
    assert inv.fp is not None
    assert 0 <= inv.fp <= FP_MAX
    assert inv.seed is not None
    assert 0 <= inv.seed <= SEED_MAX


def test_the_ranges_reach_their_ends() -> None:
    rng = random.Random(0)
    drawn = {rng.randint(0, FP_MAX) for _ in range(5000)}
    assert drawn == set(range(FP_MAX + 1))


def test_a_users_fp_is_kept_and_only_the_seed_is_drawn(world: World) -> None:
    inv = world.resolve(extra_args=("-fp", "3"))
    assert inv.fp is None
    assert inv.seed is not None
    args = build_tlc_command(inv).args
    assert args.count("-fp") == 1
    assert args.count("-seed") == 1


def test_a_users_seed_is_kept_and_only_the_fp_is_drawn(world: World) -> None:
    inv = world.resolve(extra_args=("-seed", "9"))
    assert inv.seed is None
    assert inv.fp is not None


def test_keep_the_request_wins_over_the_setting(world: World) -> None:
    keeping = world.settings.model_copy(update={"tlc": world.settings.tlc.model_copy(update={"keep": True})})
    assert world.resolve(keep=False, settings=keeping).keep is False
    assert world.resolve(keep=True).keep is True


def test_keep_takes_the_setting_when_the_request_has_none(world: World) -> None:
    keeping = world.settings.model_copy(update={"tlc": world.settings.tlc.model_copy(update={"keep": True})})
    assert world.resolve(settings=keeping).keep is True
    assert world.resolve().keep is False


def test_tool_mode_and_coverage(world: World) -> None:
    assert world.resolve(raw=True).tool_mode is False
    assert world.resolve(coverage=True).coverage is True


# --- find_recovered_run and its use --------------------------------------------------------------------------------


def make_run(runs: Path, run_id: str, record: object) -> Path:
    folder = runs / run_id
    (folder / "Spec-2026-11-15-10-00-00").mkdir(parents=True)
    if record is not None:
        text = record if isinstance(record, str) else json.dumps(record)
        (folder / "run.json").write_text(text, encoding="utf-8")
    return folder


RUN_ID = "20261114T090000Z-0badcafe"


def test_a_recovered_kept_run_gives_its_keep_fp_and_seed(world: World) -> None:
    folder = make_run(world.runs, RUN_ID, {"keep": True, "kept": False, "fp": 58, "seed": 7})
    inv = world.resolve(keep=False, extra_args=("-recover", str(folder / "Spec-2026-11-15-10-00-00")))
    assert (inv.keep, inv.fp, inv.seed) == (True, 58, 7)
    args = build_tlc_command(inv).args
    assert args[args.index("-fp") + 1] == "58"
    assert args[args.index("-seed") + 1] == "7"


def test_kept_true_counts_as_keep_finding_fc1(world: World) -> None:
    folder = make_run(world.runs, RUN_ID, {"keep": False, "kept": True, "fp": 58, "seed": 7})
    run = find_recovered_run(["-recover", str(folder)], world.cwd, world.runs)
    assert run is not None
    assert run.keep is True


def test_a_relative_recover_path_is_read_against_cwd(world: World) -> None:
    folder = make_run(world.runs, RUN_ID, {"keep": True, "fp": 58, "seed": 7})
    relative = os.path.relpath(folder / "Spec-2026-11-15-10-00-00", world.cwd)
    run = find_recovered_run(["-deadlock", "-recover", relative], world.cwd, world.runs)
    assert run is not None
    assert (run.run_id, run.folder, run.keep, run.fp, run.seed) == (RUN_ID, world.runs / RUN_ID, True, 58, 7)


def test_a_recover_path_through_a_link_into_the_run_folder_is_found(world: World) -> None:
    folder = make_run(world.runs, RUN_ID, {"keep": True, "fp": 58, "seed": 7})
    link = world.cwd / "last-run"
    try:
        link.symlink_to(folder, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links cannot be made here")
    run = find_recovered_run(["-recover", "last-run/Spec-2026-11-15-10-00-00"], world.cwd, world.runs)
    assert run is not None
    assert run.run_id == RUN_ID


def test_a_missing_folder_inside_an_existing_run_still_names_the_run_q9(world: World) -> None:
    folder = make_run(world.runs, RUN_ID, {"keep": True, "fp": 58, "seed": 7})
    run = find_recovered_run(["-recover", str(folder / "states")], world.cwd, world.runs)
    assert run is not None
    assert run.run_id == RUN_ID


@pytest.mark.parametrize("where", ["outside", "missing-outside", "no-such-run"])
def test_a_path_outside_a_run_folder_gives_none_and_fresh_values(world: World, where: str) -> None:
    make_run(world.runs, RUN_ID, {"keep": True, "fp": 58, "seed": 7})
    (world.cwd / "outside").mkdir()
    path = {
        "outside": world.cwd / "outside",
        "missing-outside": world.cwd / "nowhere" / "states",
        "no-such-run": world.runs / "20261113T000000Z-00000000" / "states",
    }[where]
    assert find_recovered_run(["-recover", str(path)], world.cwd, world.runs) is None
    inv = world.resolve(extra_args=("-recover", str(path)), seed=3)
    fresh = world.resolve(seed=3)
    assert inv.keep is False
    assert (inv.fp, inv.seed) == (fresh.fp, fresh.seed)


def test_the_runs_folder_itself_and_a_missing_word_give_none(world: World) -> None:
    make_run(world.runs, RUN_ID, {"keep": True})
    assert find_recovered_run(["-recover", str(world.runs)], world.cwd, world.runs) is None
    assert find_recovered_run(["-recover"], world.cwd, world.runs) is None
    assert find_recovered_run(["-deadlock"], world.cwd, world.runs) is None


@pytest.mark.parametrize("record", [None, "{not json", "[1, 2]", '{"keep": "yes", "fp": "58", "seed": true}'])
def test_an_unreadable_run_json_gives_no_keep_and_no_values(world: World, record: str | None) -> None:
    folder = make_run(world.runs, RUN_ID, record)
    run = find_recovered_run(["-recover", str(folder)], world.cwd, world.runs)
    assert run is not None
    assert (run.keep, run.fp, run.seed) == (False, None, None)
    inv = world.resolve(extra_args=("-recover", str(folder)))
    assert inv.keep is False
    assert inv.fp is not None
    assert inv.seed is not None


def test_a_recovered_value_fills_only_the_missing_one(world: World) -> None:
    folder = make_run(world.runs, RUN_ID, {"keep": False, "fp": 58, "seed": 7})
    inv = world.resolve(extra_args=("-recover", str(folder), "-fp", "3"))
    assert (inv.fp, inv.seed) == (None, 7)


# --- suppress_te_spec (D36) ----------------------------------------------------------------------------------------


def test_suppress_te_spec_on_a_build_with_the_capability(world: World) -> None:
    assert world.resolve().suppress_te_spec is True


def test_no_suppress_te_spec_on_a_build_without_it(world: World) -> None:
    world.build = make_build(world.tmp_path / "v1.7.4-build", frozenset())
    assert world.resolve().suppress_te_spec is False


@pytest.mark.parametrize("flag", ["-generateSpecTE", "-noGenerateSpecTE", "-teSpecOutDir"])
def test_no_suppress_te_spec_with_a_trace_spec_flag(world: World, flag: str) -> None:
    assert world.resolve(extra_args=(flag,)).suppress_te_spec is False


# --- Java options and warnings -------------------------------------------------------------------------------------


def test_the_default_java_options_reach_the_command_line_row_r25(world: World) -> None:
    assert not world.isolated.paths.config_file.exists()
    assert "TLAUP_JAVA_OPTS" not in world.env
    inv = world.resolve()
    assert inv.jvm_options == DEFAULT_OPTS
    argv = build_tlc_command(inv).argv()
    main = argv.index("tlc2.TLC")
    assert argv.index(DEFAULT_OPTS[0]) < main
    assert argv.index(DEFAULT_OPTS[1]) < main


def test_the_java_options_combine_the_three_sources(world: World) -> None:
    world.env["TLAUP_JAVA_OPTS"] = '-Xmx2g -Dx="a b"'
    world.env["JAVA_OPTS"] = "-Xmx1g"
    inv = world.resolve(java_opts=("-Xss8m",))
    assert inv.jvm_options == (*DEFAULT_OPTS, "-Xmx2g", "-Dx=a b", "-Xss8m")


def test_the_warnings_of_require_java_are_in_the_invocation(world: World) -> None:
    empty_jdk = world.tmp_path / "empty-jdk"
    (empty_jdk / "bin").mkdir(parents=True)
    world.env["JAVA_HOME"] = str(empty_jdk)
    inv = world.resolve()
    assert inv.java.tool.source == "PATH"
    assert len(inv.warnings) == 1
    assert "JAVA_HOME" in inv.warnings[0]
    assert inv.warnings == inv.java.warnings


# --- the classpath through the preflight (M2; rows S10 to S12, C6) -------------------------------------------------


def register(registry: Registry, name: str) -> Path:
    folder = registry.root / name
    (folder / "modules").mkdir(parents=True)
    (folder / "classes").mkdir()
    write_record(folder, RegisteredModule(name, folder, "2026-11-15T00:00:00Z", "/src", None, None, None, ()))
    return folder


def test_registered_modules_come_in_name_order(world: World) -> None:
    registry = Registry(world.isolated.paths.modules, now=FakeClock(START).now)
    beta = register(registry, "beta")  # the reverse of name order
    alpha = register(registry, "alpha")
    inv = world.resolve()
    project = world.cwd / "project"
    assert inv.tla_library == (project / "modules", alpha / "modules", beta / "modules")
    assert inv.classpath == (*inv.tla_library, alpha / "classes", beta / "classes", world.build.jar)
    assert inv.override_classes == ()


def test_a_relative_module_path_is_read_against_cwd_row_c6(world: World) -> None:
    started = world.tmp_path / "started-here"
    (started / "project").mkdir(parents=True)
    (started / "project" / "Spec.tla").write_text("---- MODULE Spec ----\n====\n", encoding="utf-8")
    (started / "mods").mkdir()
    (started / "jars").mkdir()
    (started / "jars" / "j.jar").write_bytes(b"jar")
    settings = world.settings.model_copy(update={"module_path": "mods", "module_lib_path": "jars"})
    assert Path.cwd() != started
    inv = world.resolve(cwd=started, settings=settings)
    assert inv.tla_library == (started / "mods",)
    assert inv.classpath == (started / "mods", world.build.jar, started / "jars" / "j.jar")
    java_inv = build_tlc_command(inv)
    assert dict(java_inv.system_properties)["TLA-Library"] == str(started / "mods")
    argv = java_inv.argv()
    classpath = argv[argv.index("-cp") + 1].split(os.pathsep)
    assert str(started / "mods") in classpath
    assert str(started / "jars" / "j.jar") in classpath


# --- override classes and their check (11 R7, package 34) ----------------------------------------------------------


def queue_and_project_classes(world: World) -> None:
    """A registered module whose class is QueueOverrides, and a project folder with its own TLCOverrides."""
    registry = Registry(world.isolated.paths.modules, now=FakeClock(START).now)
    classes = register(registry, "Queue") / "classes"
    fake = Path(__file__).resolve().parents[2] / "fakes" / "classes" / "tlc2" / "overrides" / "DirectOverrides.class"
    for folder, name in ((classes, "QueueOverrides"), (world.cwd / "project" / "classes", "TLCOverrides")):
        (folder / "tlc2" / "overrides").mkdir(parents=True, exist_ok=True)
        (folder / "tlc2" / "overrides" / f"{name}.class").write_bytes(fake.read_bytes())
    (classes / "META-INF" / "services").mkdir(parents=True)
    (classes / "META-INF" / "services" / "tlc2.overrides.ITLCOverrides").write_text("tlc2.overrides.QueueOverrides\n")


def test_a_build_with_the_property_gets_both_classes_and_no_override_warning(world: World) -> None:
    queue_and_project_classes(world)
    inv = world.resolve()
    assert inv.override_classes == ("tlc2.overrides.TLCOverrides", "tlc2.overrides.QueueOverrides")
    assert inv.warnings == inv.java.warnings


def test_a_build_without_the_property_warns_and_the_preflight_returns(world: World) -> None:
    queue_and_project_classes(world)
    old = make_build(world.tmp_path / "old-0123456789ab", frozenset())
    inv = world.resolve(get_build=lambda: old)
    assert inv.override_classes == ("tlc2.overrides.TLCOverrides", "tlc2.overrides.QueueOverrides")
    assert [w for w in inv.warnings if w not in inv.java.warnings] == [
        "TLC rolling loads Java overrides only from a class named tlc2.overrides.TLCOverrides; "
        "tlc2.overrides.QueueOverrides (module Queue) will not load, and the TLA+ definitions of its operators "
        "will be used"
    ]
