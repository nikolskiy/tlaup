"""`build_tlc_command` on hand-built invocations (design 20 G1): one expected file per combination that changes it.

Each expected file holds `replace(java_inv, lifeline=False).argv()`, one argument per line, so that it does not
depend on a process id. The paths are invented; nothing is read.
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.expected import assert_matches
from tlaup.java.locate import JavaRuntime, JavaTool
from tlaup.tlc.command import build_tlc_command
from tlaup.tlc.invocation import TlcInvocation, TlcRequest
from tlaup.versioning.store import Build, Source

if TYPE_CHECKING:
    from typing import Any

EXPECTED = Path(__file__).parent / "expected" / "command"
ROOT = Path("/invented")  # nothing exists under it
SPEC = ROOT / "project" / "Spec.tla"
BUILD = Build(
    id="rolling-0123456789ab",
    name="rolling",
    commit=None,
    calver=None,
    built_at=None,
    sha256="0" * 64,
    size=1,
    prerelease=False,
    source=Source("github-release", "https://example.invalid/tla2tools.jar", 1, None, digest_checked=True),
    installed_at="2026-11-15T00:00:00Z",
    capabilities=frozenset({"calver", "overrides_property", "no_generate_spec_te"}),
    path=ROOT / "cache" / "tool" / "rolling-0123456789ab",
)
JAVA = JavaRuntime(JavaTool(ROOT / "jdk" / "bin" / "java", "PATH"), "25.0.5", 25, ())

# The plain parsed run: -tool, a run folder, workers, -fp and -seed, two module folders, no overrides, no cfg.
PLAIN = TlcInvocation(
    request=TlcRequest(spec="Spec"),
    build=BUILD,
    java=JAVA,
    spec=SPEC,
    cfg=None,
    config_arg=None,
    project_root=ROOT / "project",
    cwd=ROOT / "work",
    classpath=(
        ROOT / "project" / "classes",
        ROOT / "project" / "modules",
        BUILD.jar,
        ROOT / "project" / "lib" / "a.jar",
    ),
    tla_library=(ROOT / "project" / "modules", ROOT / "shared"),
    override_classes=(),
    warnings=(),
    jvm_options=("-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC"),
    workers="auto",
    coverage=False,
    tool_mode=True,
    suppress_te_spec=False,
    keep=False,
    fp=58,
    seed=8556987057680880581,
    extra_args=(),
    run_id="20261115T100000Z-3fa9c1d2",
    metadir=ROOT / "cache" / "runs" / "20261115T100000Z-3fa9c1d2",
)

CASES: dict[str, dict[str, Any]] = {
    "plain": {},
    "raw": {"tool_mode": False},
    "coverage": {"coverage": True},
    "cfg": {"cfg": ROOT / "outside" / "out.cfg", "config_arg": "../outside/out.cfg"},
    "workers_absent": {"workers": None, "extra_args": ("-workers", "4")},
    "workers_number": {"workers": "4"},
    "overrides": {"override_classes": ("tlc2.overrides.QueueOverrides", "tlc2.overrides.TLCOverrides")},
    "user_metadir": {"metadir": None, "extra_args": ("-metadir", "states")},
    "suppress_te_spec": {"suppress_te_spec": True},
    "only_seed": {"fp": None, "extra_args": ("-fp", "3")},
    "empty_tla_library": {"tla_library": ()},
    "extra_args": {"extra_args": ("-deadlock", "-simulate", "num=10", "-dump", "dot,colorize", "out.dot")},
    "everything": {
        "coverage": True,
        "suppress_te_spec": True,
        "workers": "2",
        "cfg": ROOT / "project" / "Spec.cfg",
        "config_arg": "Spec.cfg",
        "override_classes": ("tlc2.overrides.TLCOverrides",),
        "extra_args": ("-deadlock",),
    },
}


def argv_text(inv: TlcInvocation) -> str:
    return "\n".join(replace(build_tlc_command(inv), lifeline=False).argv()) + "\n"


@pytest.mark.skipif(os.name == "nt", reason="the expected files are written with POSIX paths and separators (D15)")
@pytest.mark.parametrize("name", sorted(CASES))
def test_the_command_line(name: str, request: pytest.FixtureRequest) -> None:
    assert_matches(argv_text(replace(PLAIN, **CASES[name])), EXPECTED / f"{name}.txt", request)


def test_the_fields_the_builder_fills() -> None:
    java_inv = build_tlc_command(PLAIN)
    assert java_inv.java == JAVA.tool.path
    assert java_inv.cwd is None  # D34: no working folder is set
    assert java_inv.lifeline is True  # left at its default; the launcher adds it
    assert java_inv.main_class == "tlc2.TLC"
    assert java_inv.classpath == PLAIN.classpath
    assert java_inv.jvm_options == PLAIN.jvm_options
    assert java_inv.system_properties == (("TLA-Library", os.pathsep.join(str(p) for p in PLAIN.tla_library)),)
    assert java_inv.args[-1] == str(SPEC)


def test_override_classes_are_joined_with_the_path_separator() -> None:
    java_inv = build_tlc_command(replace(PLAIN, override_classes=("a.A", "b.B")))
    assert ("tlc2.overrides.TLCOverrides", f"a.A{os.pathsep}b.B") in java_inv.system_properties


def test_coverage_comes_before_the_spec_and_the_extra_args_unchanged_before_it() -> None:
    args = build_tlc_command(replace(PLAIN, coverage=True, extra_args=("-deadlock", "x y"))).args
    assert args[-3:] == ("-deadlock", "x y", str(SPEC))
    assert args.index("-coverage") < args.index("-deadlock")
    assert args[args.index("-coverage") + 1] == "1"


def test_the_builder_reads_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        pytest.fail("build_tlc_command touched the disk")

    inv = replace(PLAIN, cfg=ROOT / "nowhere.cfg", config_arg="../nowhere.cfg")
    assert not any(path.exists() for path in (SPEC, BUILD.jar, JAVA.tool.path, *PLAIN.classpath))
    with monkeypatch.context() as patched:
        for name in ("stat", "lstat", "resolve", "exists", "is_file", "is_dir", "absolute"):
            patched.setattr(Path, name, refuse)
        for name in ("stat", "lstat", "getcwd", "listdir", "scandir"):
            patched.setattr(os, name, refuse)
        patched.setattr(os, "environ", {})
        java_inv = build_tlc_command(inv)
    assert java_inv.args[-3:] == ("-config", "../nowhere.cfg", str(SPEC))
