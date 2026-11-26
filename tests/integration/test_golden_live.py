"""The golden facts on live TLC runs (design 01 T3, T9; package 52).

Every case of the matched golden folder's ``cases.toml`` that a live run can reproduce runs through ``run_tlc`` with a
``CollectingReporter``, on a copy of ``golden/specs/`` in the work folder, and every fact of ``facts_for(case, line)``
must hold for the live result. A fact that fails here and passes on the capture means upstream changed its output:
the answer is a new capture, never a weaker fact or a new entry in ``LIVE_SKIP`` (T3, Risks).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.integration.discovery import install
from tests.integration.live import copy_folder, facts_failures, run_live_tlc
from tests.parse.drive import build_folders, cases_of, golden_root, line_of

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tests.integration.conftest import Isolated
    from tests.integration.discovery import TestJar

# The cases a live run cannot reproduce for a reason cases.toml does not carry, each with that reason (package 52).
LIVE_SKIP: dict[str, str] = {
    "tool-oom": "exhausting a 64 MB heap depends on the JVM and the machine",
    "big-states": (
        "v1.7.4 with four workers sometimes stops this run of 2.2 million states with an ArithmeticException "
        "(division by zero, message 1000), a race of the build that depends on the JVM and the machine: 1 run in 16 "
        "of plain java with no tlaup, on JDK 25.0.4, 2026-11-26"
    ),
}

# The keys of cases.toml that leave a case out of the live runs, with the reason (package 52, Context).
_NEEDS_JAVA = ("java_sources", "classpath")
_NOT_REPRODUCIBLE = ("stopped", "recover_from")
_OVERRIDE_PROPERTY = "-Dtlc2.overrides.TLCOverrides"

# The roadmap's four (T9): a failing spec, a trace, a SANY error, a coverage run.
NAMED = ("violation", "sany-semantic-error", "coverage")


def left_out(name: str, table: dict[str, object]) -> str | None:
    """Why a case does not run live, or None (package 52, "Which golden cases run live")."""
    if "spec" not in table:
        return "no spec: run_tlc needs one"
    if table.get("plain"):
        return "a plain case: replayed by raw-mode scenarios, not parsed"
    if any(key in table for key in _NEEDS_JAVA):
        return "its spec needs a Java class"
    jvm_options = table.get("jvm_options", [])
    assert isinstance(jvm_options, list)
    if any(str(option).startswith(_OVERRIDE_PROPERTY) for option in jvm_options):
        return "its JVM options name an override class"
    if any(key in table for key in _NOT_REPRODUCIBLE):
        return "a live run cannot reproduce how the capture ended"
    return LIVE_SKIP.get(name)


def live_cases(golden: Path) -> list[str]:
    """The cases of a golden folder that run live, in ``cases.toml``'s order (called by the conftest)."""
    return [name for name, table in cases_of(golden).items() if left_out(name, table) is None]


def test_case_live(live_case: tuple[TestJar, str], isolated: Isolated, monkeypatch: pytest.MonkeyPatch) -> None:
    jar, name = live_case
    build = install(isolated.paths, jar)
    table = cases_of(jar.golden)[name]
    specs = copy_folder(golden_root() / "specs", isolated.work / "specs")
    spec = specs / f"{table['spec']}.tla"
    cwd = specs / str(table["cwd"]) if "cwd" in table else spec.parent
    monkeypatch.chdir(cwd)
    metadir = isolated.work / "meta"
    args = [str(arg).replace("<metadir>", str(metadir)) for arg in table.get("args", [])]  # type: ignore[attr-defined]
    workers = None if "-workers" in args else "1"  # the facts assume one worker where a case names none (08a)
    live = run_live_tlc(
        isolated.paths,
        build,
        spec,
        cwd=cwd,
        home=isolated.home,
        workers=workers,
        java_opts=[str(option) for option in table.get("jvm_options", [])],  # type: ignore[attr-defined]
        extra_args=args,
    )
    outcome = live.outcome
    assert outcome.result is not None
    failures = facts_failures(name, jar.line, outcome.result)
    if "exit" in table and outcome.exit_code != table["exit"]:
        failures.append(f"exit code: expected {table['exit']}, got {outcome.exit_code}")
    assert not failures, f"{jar.build}/{name}, against {jar.golden.name}:\n" + "\n".join(failures)


def test_named_cases_run() -> None:
    for golden in build_folders("tlc"):
        running = live_cases(golden)
        missing = [name for name in NAMED if name not in running]
        assert not missing, f"{golden.name} ({line_of(golden)}): {missing} do not run live"


def test_skip_table() -> None:
    names = {name for golden in build_folders("tlc") for name in cases_of(golden)}
    for name, reason in LIVE_SKIP.items():
        assert name in names, f"LIVE_SKIP names {name}, which no cases.toml has"
        assert reason.strip(), f"LIVE_SKIP gives {name} no reason"
