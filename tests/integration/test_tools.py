"""SANY, the PlusCal translator and the REPL on the real jars (design 01 T9, 21 S1 to S3; package 52).

Through the API where T9 says so (``run_sany`` and ``run_pcal`` with a collecting sink); ``tlaup sany`` and
``tlaup repl`` as real processes, the first for its printed excerpt (finding H3), the second because it passes the
terminal through (T5, situation 1). Every spec is a copy in the work folder: ``pcal`` rewrites its spec.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

import tlaup.cli
from tests.integration.live import EXAMPLES, SPECS, copy_folder, run_live_pcal, run_live_sany, run_tlaup
from tests.parse.drive import golden_root

if TYPE_CHECKING:
    from tests.integration.conftest import Isolated
    from tests.integration.discovery import TestJar
    from tlaup.versioning.store import Build

SANY_ERROR = 150  # a spec with an error (D29, D55)
EDITOR_FORM = re.compile(r"^(?P<file>[^\s:][^:]*):(?P<line>\d+):(?P<column>\d+): error: ")
GUTTER = re.compile(r"^\s*(?P<number>\d+) \| (?P<text>.*)$")
MARKS = re.compile(r"^\s+\| [\t ]*\^+$")


def golden_spec(name: str, folder: Path) -> Path:
    """A copy of ``golden/specs/<name>.tla`` in ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copy(golden_root() / "specs" / f"{name}.tla", folder))


def test_sany_good_and_bad(live_build: Build, isolated: Isolated) -> None:
    for name, errors in (("Good", 0), ("SemErr", 2), ("ParseErr", 1)):
        spec = golden_spec(name, isolated.work / name)
        outcome, sink = run_live_sany(isolated.paths, live_build, spec, cwd=isolated.work, home=isolated.home)
        found = [d for d in sink.diagnostics if d.severity == "error"]
        assert len(found) == errors, f"{name}: {sink.diagnostics}"
        assert outcome.exit_code == (SANY_ERROR if errors else 0), name
        for diagnostic in found:
            assert diagnostic.file is not None and diagnostic.file.endswith(f"{name}.tla"), diagnostic
            assert diagnostic.location is not None and diagnostic.location.line > 0, diagnostic
            assert diagnostic.location.column > 0, diagnostic


def test_sany_streams_and_modules(live_build: Build, test_jar: TestJar, isolated: Isolated) -> None:
    # A module that does not exist: the missing-module diagnostic, and v1.7.4's stderr line is not lost (S1).
    spec = golden_spec("MissingMod", isolated.work / "missing")
    outcome, sink = run_live_sany(isolated.paths, live_build, spec, cwd=isolated.work, home=isolated.home)
    assert outcome.exit_code == SANY_ERROR
    assert any("NoSuchModule" in d.message for d in sink.diagnostics), sink.diagnostics
    if test_jar.line == "stable":
        # The line v1.7.4 writes to stderr, kept by the one pipe of S1 (package 52 names it).
        found = [line for line in outcome.result.other if line.startswith("File does not exist")]
        assert any("NoSuchModule.tla" in line for line in found), outcome.result.other

    # A registered module is found (research 27).
    module = copy_folder(EXAMPLES / "QueueModule", isolated.work / "QueueModule")
    added = CliRunner().invoke(tlaup.cli.app, ["module", "add", str(module)])
    assert added.exit_code == 0, added.output
    uses = copy_folder(SPECS / "sany-registered", isolated.work / "registered") / "UsesQueue.tla"
    outcome, sink = run_live_sany(isolated.paths, live_build, uses, cwd=isolated.work, home=isolated.home)
    assert outcome.exit_code == 0, sink.diagnostics
    assert not sink.diagnostics

    # A module beside the spec wins over one of the same name in the starting folder (S1: SANY runs in the spec's
    # folder). Each copy of M has its own unknown name, so the diagnostic's file and line say which copy was read.
    shadow = copy_folder(SPECS / "sany-shadow", isolated.work / "shadow")
    own = shadow / "project" / "M.tla"
    line = next(n for n, text in enumerate(own.read_text().splitlines(), 1) if "== UnknownBesideTheSpec" in text)
    main = shadow / "project" / "Main.tla"
    outcome, sink = run_live_sany(isolated.paths, live_build, main, cwd=shadow / "start", home=isolated.home)
    assert outcome.exit_code == SANY_ERROR
    [diagnostic] = sink.diagnostics
    assert diagnostic.file is not None and Path(diagnostic.file).resolve() == own.resolve(), diagnostic
    assert diagnostic.location is not None and diagnostic.location.line == line, diagnostic


def test_sany_excerpt(live_build: Build, isolated: Isolated) -> None:
    """``tlaup sany`` as a real process: each editor-form line has the excerpt of the file on disk under it (D66)."""
    spec = golden_spec("SemErr", isolated.work)
    lines = spec.read_text(encoding="utf-8").splitlines()
    done = run_tlaup(["sany", spec.name])
    assert done.exit_code == SANY_ERROR, done
    printed = done.stdout.splitlines()
    heads = [index for index, text in enumerate(printed) if EDITOR_FORM.match(text)]
    assert len(heads) == 2, done.stdout
    for index in heads:
        match = EDITOR_FORM.match(printed[index])
        assert match is not None
        assert match["file"] == spec.name, printed[index]
        first, column = int(match["line"]), int(match["column"])
        before = list(range(max(first - 2, 1), first + 1))
        after = list(range(first + 1, min(first + 2, len(lines)) + 1))
        block = printed[index + 1 : index + 1 + len(before) + 2 + len(after)]
        numbered = [GUTTER.match(text) for text in block[: len(before)] + block[len(before) + 2 :]]
        assert all(numbered), block
        assert [int(m["number"]) for m in numbered if m] == before + after, block
        assert [m["text"] for m in numbered if m] == [lines[n - 1] for n in before + after], block
        assert MARKS.match(block[len(before)]), block
        assert f"line {first}, col {column}" in block[len(before) + 1], block


def test_pcal_copy(live_build: Build, isolated: Isolated) -> None:
    spec = golden_spec("Pcal", isolated.work / "pcal")
    outcome, sink = run_live_pcal(isolated.paths, live_build, spec, cwd=isolated.work, home=isolated.home)
    assert outcome.exit_code == 0, sink
    assert not sink.diagnostics
    assert sorted(path.name for path in spec.parent.iterdir()) == ["Pcal.cfg", "Pcal.old", "Pcal.tla"]


def _generated_cfg(live_build: Build, isolated: Isolated) -> list[str]:
    """The cfg the translator writes where there is none: its ``SPECIFICATION`` line and its marker line."""
    spec = golden_spec("Pcal", isolated.work / "first")
    outcome, _ = run_live_pcal(isolated.paths, live_build, spec, cwd=isolated.work, home=isolated.home)
    assert outcome.exit_code == 0
    return spec.with_suffix(".cfg").read_text(encoding="utf-8").splitlines()


def test_pcal_existing_cfg(live_build: Build, isolated: Isolated) -> None:
    generated = _generated_cfg(live_build, isolated)
    specification = [text for text in generated if text.startswith("SPECIFICATION")]
    markers = [text for text in generated if text.strip() and not text.startswith("SPECIFICATION")]
    assert len(specification) == 1 and len(markers) == 1, generated
    [marker] = markers

    # With the marker line: the lines after it are kept.
    spec = golden_spec("Pcal", isolated.work / "with-marker")
    cfg = spec.with_suffix(".cfg")
    cfg.write_text("\n".join([*generated, "\\* a line of the user's"]) + "\n", encoding="utf-8")
    outcome, _ = run_live_pcal(isolated.paths, live_build, spec, cwd=isolated.work, home=isolated.home)
    assert outcome.exit_code == 0
    kept = cfg.read_text(encoding="utf-8").splitlines()
    assert kept[kept.index(marker) + 1 :] == ["\\* a line of the user's"], kept

    # Without one: the user's lines under a new marker, and the generated SPECIFICATION line lost (research 12).
    spec = golden_spec("Pcal", isolated.work / "without-marker")
    cfg = spec.with_suffix(".cfg")
    cfg.write_text("SPECIFICATION Foo\nINVARIANT Bar\n", encoding="utf-8")
    outcome, _ = run_live_pcal(isolated.paths, live_build, spec, cwd=isolated.work, home=isolated.home)
    assert outcome.exit_code == 0
    rewritten = [text for text in cfg.read_text(encoding="utf-8").splitlines() if text.strip()]
    assert rewritten == [marker, "SPECIFICATION Foo", "INVARIANT Bar"], rewritten
    assert specification[0] not in rewritten


def test_repl_piped(live_build: Build, isolated: Isolated) -> None:
    if "repl" not in live_build.capabilities:
        pytest.skip(f"{live_build.name} has no REPL; the refusal with exit 3 is a scenario of repl.feature")
    home_before = sorted(path.name for path in isolated.home.iterdir())
    done = run_tlaup(["repl"], stdin=b"1+1\n")
    assert done.exit_code == 0, done
    assert any(text.split()[-1:] == ["2"] for text in done.stdout.splitlines()), done.stdout  # after the prompt
    # The REPL's history (~/.tlaplus/history.repl, research 12) went to the JVM's moved user.home, not HOME (T9).
    assert (isolated.user_home / ".tlaplus").is_dir()
    assert any(isolated.tmp.iterdir()), "nothing in the moved java.io.tmpdir"
    assert sorted(path.name for path in isolated.home.iterdir()) == home_before
