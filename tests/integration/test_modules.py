"""Operator overrides with real Java: registered modules and a project's own class (01 T9; inventory R32 to R34).

``tlaup module add`` runs in-process (``CliRunner``) with the real ``javac``; the run is ``run_tlc``. Everything runs
on copies in the work folder, so that what TLC writes beside a spec never lands in the repository.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

import tlaup.cli
from tests.integration.live import EXAMPLES, SPECS, copy_folder, run_live_tlc
from tlaup_parse import ErrorKind, Verdict

if TYPE_CHECKING:
    from pathlib import Path

    from tests.integration.conftest import Isolated
    from tests.integration.discovery import TestJar
    from tests.integration.live import Live
    from tlaup.versioning.store import Build

OVERRIDES_PROPERTY = "overrides_property"  # a build that loads the classes the property names (00, research 13)


def module_add(source: Path) -> None:
    """``tlaup module add <a copy of source>``, in-process."""
    result = CliRunner().invoke(tlaup.cli.app, ["module", "add", str(source)])
    assert result.exit_code == 0, result.output


def run_example(isolated: Isolated, build: Build, spec_name: str, monkeypatch: pytest.MonkeyPatch) -> Live:
    specs = copy_folder(EXAMPLES / "spec", isolated.work / "spec")
    monkeypatch.chdir(specs)
    return run_live_tlc(isolated.paths, build, specs / f"{spec_name}.tla", cwd=specs, home=isolated.home)


def test_queue_module(live_build: Build, isolated: Isolated, monkeypatch: pytest.MonkeyPatch) -> None:
    """R32: the module's class is not TLCOverrides, so only a build that honours the property loads it (R7)."""
    module_add(copy_folder(EXAMPLES / "QueueModule", isolated.work / "QueueModule"))
    live = run_example(isolated, live_build, "queue", monkeypatch)
    result = live.outcome.result
    assert result is not None
    if OVERRIDES_PROPERTY in live_build.capabilities:
        assert live.outcome.exit_code == 0, result.errors
        assert result.verdict is Verdict.NO_ERROR, result.errors
        assert not live.outcome.warnings
    else:  # v1.7.4: R7's warning names the class, and the TLA+ definition's Assert fails (research 13)
        assert any("QueueOverrides" in text for text in live.outcome.warnings), live.outcome.warnings
        assert [error.kind for error in result.errors] == [ErrorKind.ASSERTION], result.errors


def test_project_override_class(live_build: Build, isolated: Isolated, monkeypatch: pytest.MonkeyPatch) -> None:
    """R33: the project's own TLCOverrides in its classes/, compiled here with the real javac, is the one TLC loads."""
    project = copy_folder(SPECS / "naming_fixed", isolated.work / "naming_fixed")
    javac = shutil.which("javac")
    assert javac is not None, "javac is not on PATH"
    source = project / "modules" / "tlc2" / "overrides" / "TLCOverrides.java"
    classes = project / "classes"
    command = [javac, "--release", "11", "-cp", str(live_build.jar), "-d", str(classes), str(source)]
    compiled = subprocess.run(command, capture_output=True, text=True, check=False)
    assert compiled.returncode == 0, compiled.stderr
    spec = project / "spec" / "test_spec.tla"
    monkeypatch.chdir(spec.parent)
    live = run_live_tlc(isolated.paths, live_build, spec, cwd=spec.parent, home=isolated.home)
    result = live.outcome.result
    assert result is not None
    assert live.outcome.exit_code == 0, result.errors
    assert result.verdict is Verdict.NO_ERROR, result.errors
    assert live.reporter.run is not None and live.reporter.run.project_root == project
    assert "OVERRIDE_ACTIVE_TLCOverrides" in result.output, result.output  # the marker the class prints


def test_sequences_ext(
    live_build: Build, test_jar: TestJar, isolated: Isolated, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R34: a module with a jar in lib/ and several TLA+ modules; the spec says when its overrides are loaded."""
    if test_jar.line == "stable":
        # Package 52 asks for success on both builds, but the module's Java sources do not compile against v1.7.4
        # (tlc2.value.impl.KSubsetValue and FunctionValue are missing, so is Evaluation.silent): `module add` fails
        # with javac's errors. The 0.8.x test ran on v1.8.0 only. Reported to the lead; skipped until decided.
        pytest.skip("the sequences-ext sources do not compile against v1.7.4 (finding of package 52a)")
    module_add(copy_folder(EXAMPLES / "sequences-ext", isolated.work / "sequences-ext"))
    live = run_example(isolated, live_build, "SequencesExtTest", monkeypatch)
    result = live.outcome.result
    assert result is not None
    assert live.outcome.exit_code == 0, result.errors
    assert result.verdict is Verdict.NO_ERROR, result.errors
    assert any("SUCCESS: Java overrides are loaded!" in line for line in result.output), result.output
