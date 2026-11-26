"""The runner with real TLC: encoding, cfg rows, run folders, workers and the Java check (01 T9; package 52).

11 R3 (``LC_ALL=C``), R4 (rows F1 to F14 and research 24's link rows, as package 32's unit test builds them),
R6 (no leftovers; a kept checkpoint resumed to the exact count, D52 and D54), R8 (``--workers auto`` under
``taskset``) and 13 J3 (the Java check remembered). Every spec runs from a copy in the test's own folders.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

import tlaup.cli
from tests.integration.discovery import find_java
from tests.integration.live import (
    SPECS,
    copy_folder,
    run_folders,
    run_live_pcal,
    run_live_tlc,
    still_alive,
    wait_until,
)
from tests.parse.drive import golden_root, read_lines
from tests.unit.spec.test_resolve_cfg import F_ROWS, R_ROWS
from tlaup.reporters.text import format_count
from tlaup.tlc.rundirs import complete_checkpoint
from tlaup_parse import TlcParser, Verdict

if TYPE_CHECKING:
    from tests.integration.conftest import Isolated
    from tests.integration.discovery import TestJar
    from tests.integration.live import Reaper
    from tlaup.versioning.store import Build

VIOLATION = 12  # TLC's code for an invariant violation (D63), the golden `violation` case's
INTERRUPTED = 130
CHECKPOINT_SECONDS = 600.0  # -checkpoint 1 writes the first one a minute after the JVM starts; slow runners take longer
RESUME_SECONDS = 900.0
NO_TRACE_SPEC = "-noGenerateSpecTE"  # passed on rolling builds only (11 R6)


def golden_spec(isolated: Isolated, name: str) -> Path:
    """A golden spec and its cfg, copied into the work folder; the path of the copied ``.tla``."""
    folder = isolated.work / "golden"
    folder.mkdir(exist_ok=True)
    for suffix in (".tla", ".cfg"):
        shutil.copyfile(golden_root() / "specs" / f"{name}{suffix}", folder / f"{name}{suffix}")
    return folder / f"{name}.tla"


# --- R3 ---------------------------------------------------------------------------------------------------------


def test_non_ascii_output(live_build: Build, isolated: Isolated, monkeypatch: pytest.MonkeyPatch) -> None:
    """R3: under ``LC_ALL=C`` the launcher's encoding options still bring é and 日 through TLC and the translator."""
    folder = copy_folder(SPECS / "non-ascii", isolated.work / "non-ascii")
    monkeypatch.chdir(folder)
    monkeypatch.setenv("LC_ALL", "C")
    live = run_live_tlc(isolated.paths, live_build, folder / "Accents.tla", cwd=folder, home=isolated.home, workers="1")
    result = live.outcome.result
    assert result is not None
    assert live.outcome.exit_code == VIOLATION, result.errors
    trace = result.errors[0].trace
    assert trace is not None
    assert [variable.value.scalar for state in trace.states for variable in state.variables] == ["é", "日"]

    spec = folder / "AccentsPcal.tla"
    before = [line for line in spec.read_bytes().splitlines() if not line.isascii()]
    outcome, _ = run_live_pcal(isolated.paths, live_build, spec, cwd=folder, home=isolated.home)
    assert outcome.exit_code == 0
    after = spec.read_bytes().splitlines()
    assert len(before) == 3  # the spec's three comment lines with é and 日
    assert [line for line in before if line not in after] == []


# --- R4 ---------------------------------------------------------------------------------------------------------

# Research 16's tree (the unit test's `tree` fixture): every cfg there sets C to its own path.
F_TREE = (
    "proj/Spec.cfg",
    "proj/a.cfg",
    "proj/sub/a.cfg",
    "proj/cfgs/b.cfg",
    "proj/my cfgs/with space.cfg",
    "outside/out.cfg",
    "work/Spec.cfg",
    "work/a.cfg",
    "work/sub/a.cfg",
    "rootproj/spec/Spec.cfg",
    "rootproj/spec/sib.cfg",
    "rootproj/cfgs/x.cfg",
    "rootproj/root.cfg",
    "rootproj/out.cfg",
    "rootproj/my cfgs/sp.cfg",
)
F_SPECS = ("proj/Spec.tla", "rootproj/spec/Spec.tla")
# Research 24's link tree (the unit test's `links` fixture): (link, target) after the files.
R_TREE = (
    "real/proj/Spec.cfg",
    "real/proj/sub/a.cfg",
    "real/out.cfg",
    "real/other/o.cfg",
    "outside/o.cfg",
    "L/out.cfg",
    "deep/a/b/Spec.cfg",
    "deep/a/out.cfg",
    "deep/out.cfg",
    "L2/out.cfg",
    "Lf/Spec.cfg",
    "work/out.cfg",
)
R_SPECS = ("real/proj/Spec.tla", "deep/a/b/Spec.tla")
R_LINKS = (("L/lnk", "../real/proj"), ("L2/lnk", "../deep/a/b"), ("Lf/Spec.tla", "../real/proj/Spec.tla"))
CFG_ROWS = [pytest.param("F", *row[1:5], id=row[0]) for row in F_ROWS] + [
    pytest.param("R", "", *row[1:4], id=row[0]) for row in R_ROWS
]


def make_tree(root: Path, cfgs: tuple[str, ...], specs: tuple[str, ...]) -> None:
    for name in cfgs:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'CONSTANT C = "{name}"\nINIT Init\nNEXT Next\n', encoding="utf-8")
    for name in specs:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SPECS / "cfg-rows" / "Spec.tla", root / name)


@pytest.mark.parametrize(("tree", "work", "spec_text", "cfg_text", "validated"), CFG_ROWS)
def test_cfg_rows(
    live_build: Build,
    isolated: Isolated,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tree: str,
    work: str,
    spec_text: str,
    cfg_text: str,
    validated: str,
) -> None:
    """R4: real TLC reads the cfg that was validated; each cfg's constant is its own path, and the spec prints it."""
    root = tmp_path / "rows"
    if tree == "F":
        make_tree(root, F_TREE, F_SPECS)
        (root / "rootproj" / "lib").mkdir()
        (root / "rootproj" / "modules").mkdir()
        cwd = root / work
    else:
        make_tree(root, R_TREE, R_SPECS)
        for link, target in R_LINKS:
            try:
                (root / link).symlink_to(target, target_is_directory=not target.endswith(".tla"))
            except OSError as error:
                pytest.skip(f"links cannot be made here: {error}")
        cwd = root
    monkeypatch.chdir(cwd)
    spec = Path(spec_text.replace("<T>", str(root)))
    cfg = cfg_text.replace("<T>", str(root))
    live = run_live_tlc(isolated.paths, live_build, spec, cwd=cwd, home=isolated.home, workers="1", cfg=cfg)
    result = live.outcome.result
    assert result is not None
    assert live.outcome.exit_code == 0, (result.errors, result.output)
    assert f'"{validated}"' in result.output, result.output


# --- R6 ---------------------------------------------------------------------------------------------------------


def test_no_leftovers_rolling(
    live_build: Build, test_jar: TestJar, isolated: Isolated, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R6: a real violation leaves nothing under the runs folder and, on a rolling build, no ``_TTrace_`` file
    beside the spec; v1.7.4 does not know ``-noGenerateSpecTE``, so its command has none."""
    spec = golden_spec(isolated, "Violation")
    monkeypatch.chdir(spec.parent)
    live = run_live_tlc(isolated.paths, live_build, spec, cwd=spec.parent, home=isolated.home, workers="1")
    assert live.outcome.exit_code == VIOLATION
    assert not isolated.paths.runs.exists() or list(isolated.paths.runs.iterdir()) == []
    if test_jar.line == "rolling":
        assert NO_TRACE_SPEC in live.command.args
        assert [path.name for path in spec.parent.iterdir() if "_TTrace_" in path.name] == []
    else:
        assert NO_TRACE_SPEC not in live.command.args


def _resume_words(stderr: str) -> list[str]:
    lines = [line for line in stderr.splitlines() if line.startswith("Resume with: ")]
    assert len(lines) == 1, stderr
    words = shlex.split(lines[0].removeprefix("Resume with: "))
    assert words[0] == "tlaup", words
    return words[1:]


def test_keep_and_resume_exact(
    live_build: Build, isolated: Isolated, reaper: Reaper, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R6, D52, D54: interrupted after its first complete checkpoint under ``--keep``, the run is kept, and the
    printed resume command finishes with the count the spec has by construction, not marked approximate. It also
    shows that both builds take the ``-fp`` and ``-seed`` tlaup passes."""
    if not hasattr(signal, "SIGINT"):
        pytest.skip("SIGINT does not exist here; no Windows CI (D15)")
    folder = copy_folder(SPECS / "counted", isolated.work / "counted")
    match = re.search(r"\bK = (\d+)", (folder / "Counted.cfg").read_text(encoding="utf-8"))
    assert match is not None
    expected = (int(match.group(1)) + 1) ** 4
    monkeypatch.chdir(folder)
    run = reaper.start(["tlc", "Counted.tla", "--keep", "--workers", "2", "--", "-checkpoint", "1"], tmp_path / "run")
    jvm = reaper.watch(run.jvm(isolated.paths))

    def checkpoint() -> Path | None:
        return next((found for path in run_folders(isolated.paths) if (found := complete_checkpoint(path))), None)

    what = "a complete checkpoint (if the run ended first, make the spec in specs/counted larger)"
    wait_until(checkpoint, what=what, timeout=CHECKPOINT_SECONDS, ended=run.ended)
    run.send(signal.SIGINT)
    assert run.wait() == INTERRUPTED, run.output()
    assert still_alive(jvm) == []
    [kept] = run_folders(isolated.paths)
    record = json.loads((kept / "run.json").read_text(encoding="utf-8"))
    assert record["kept"] is True, record
    assert str(record["seed"]) in run.stderr() and str(record["fp"]) in run.stderr(), run.output()

    resume = reaper.start(_resume_words(run.stderr()), tmp_path / "resume")
    assert resume.wait(timeout=RESUME_SECONDS) == 0, resume.output()
    out = resume.stdout()
    assert f"{format_count(expected)} distinct" in out, resume.output()
    assert format_count(expected, approximate=True) not in out, resume.output()
    assert run_folders(isolated.paths) == [], "a resume that finished removes the kept folder (R6)"


# --- R8 ---------------------------------------------------------------------------------------------------------


def test_workers_auto_one_cpu(
    live_build: Build, isolated: Isolated, reaper: Reaper, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R8: ``--workers auto`` under ``taskset -c 0`` makes TLC report one worker in its start message (2187).

    Run raw with TLC's ``-tool`` among its arguments, so that stdout is TLC's framed output, read by the parser.
    """
    taskset = shutil.which("taskset")
    if taskset is None or not sys.platform.startswith("linux"):
        pytest.skip("taskset is Linux only and must be on PATH")
    spec = golden_spec(isolated, "Success")
    monkeypatch.chdir(spec.parent)
    run = reaper.start(
        ["tlc", spec.name, "--workers", "auto", "--raw", "--", "-tool"], tmp_path / "run", prefix=[taskset, "-c", "0"]
    )
    assert run.wait() == 0, run.output()
    parser = TlcParser()
    for line in read_lines(run.stdout_file):
        parser.feed(line)
    parser.close()
    assert parser.result.workers == 1, run.output()
    assert parser.result.verdict is Verdict.NO_ERROR


# --- J3 ---------------------------------------------------------------------------------------------------------


def test_java_check_remembered(live_build: Build, isolated: Isolated, monkeypatch: pytest.MonkeyPatch) -> None:
    """J3: after one real run the Java check holds the real ``java``; a second run leaves the file as it was."""
    spec = golden_spec(isolated, "Success")
    monkeypatch.chdir(spec.parent)
    first = CliRunner().invoke(tlaup.cli.app, ["tlc", spec.name, "--workers", "1"])
    assert first.exit_code == 0, first.output
    cache = isolated.paths.java_cache
    java = find_java(os.environ)
    assert java is not None
    entries = json.loads(cache.read_text(encoding="utf-8"))["entries"]
    assert {java, str(Path(java).resolve())} & set(entries), entries
    content, stat = cache.read_bytes(), cache.stat()
    second = CliRunner().invoke(tlaup.cli.app, ["tlc", spec.name, "--workers", "1"])
    assert second.exit_code == 0, second.output
    after = cache.stat()
    assert cache.read_bytes() == content
    assert (after.st_ino, after.st_size, after.st_mtime_ns) == (stat.st_ino, stat.st_size, stat.st_mtime_ns)
