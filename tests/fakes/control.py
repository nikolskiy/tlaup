"""The launchers for the fakes and the ``Fakes`` object the ``fakes`` fixture returns (01 T4)."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, get_args

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pytest

Tool = Literal["java", "javac", "git", "editor"]
TOOLS: tuple[Tool, ...] = get_args(Tool)
FAKES_DIR = Path(__file__).resolve().parent
REPO_ROOT = FAKES_DIR.parent.parent
EXECUTE_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def script_variable(tool: Tool) -> str:
    return f"TLAUP_FAKE_{tool.upper()}"


def write_launcher(path: Path, fake: str, *, script: Path | None = None) -> Path:
    """One launcher: a script run by this interpreter that runs ``tests/fakes/<fake>.py``.

    Its first line is ``#!`` and ``sys.executable``, and the fake sees the launcher's own path
    as ``argv[0]``. On Windows a ``.cmd`` file beside it starts it. ``script`` is a script file
    baked into the launcher, read instead of ``TLAUP_FAKE_<TOOL>`` (for a JDK folder).
    """
    baked = str(script) if script is not None else None
    body = (
        f"#!{sys.executable}\n"
        "import sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        f"from tests.fakes import {fake} as fake\n"
        f"sys.exit(fake.main({baked!r}))\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | EXECUTE_BITS)
    if os.name == "nt":
        cmd = path.with_name(path.name + ".cmd")
        cmd.write_text(f'@"{sys.executable}" "%~dp0{path.name}" %*\r\n', encoding="utf-8")
    return path


def fake_bin_dir(tmp_path: Path) -> Path:
    """Writes ``bin/java``, ``bin/javac``, ``bin/git`` and ``bin/editor``; returns ``bin``."""
    bin_dir = tmp_path / "bin"
    for tool in TOOLS:
        write_launcher(bin_dir / tool, tool)
    return bin_dir


def _launcher_files(path: Path) -> list[Path]:
    return [path, path.with_name(path.name + ".cmd")]


class Fakes:
    """Scripts the fakes on ``PATH`` and reads what they logged."""

    def __init__(self, bin_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.bin = bin_dir
        self._dir = tmp_path / "fakes"
        self._monkeypatch = monkeypatch
        self._logs: dict[Tool, Path] = {tool: self._dir / f"{tool}.jsonl" for tool in TOOLS}
        self._jdks = 0

    def _write_script(self, name: str, data: Mapping[str, Any]) -> Path:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / name
        path.write_text(json.dumps(dict(data), indent=2), encoding="utf-8")
        return path

    def script(self, tool: Tool, data: Mapping[str, Any]) -> Path:
        """Writes the tool's script and sets ``TLAUP_FAKE_<TOOL>``; ``log`` defaults to the tool's log."""
        content = dict(data)
        if "log" in content:
            self._logs[tool] = Path(content["log"])
        else:
            content["log"] = str(self._logs[tool])
        path = self._write_script(f"{tool}.json", content)
        self._monkeypatch.setenv(script_variable(tool), str(path))
        return path

    def log(self, tool: Tool) -> list[dict[str, Any]]:
        """The log's lines, parsed; ``[]`` when nothing ran."""
        path = self._logs[tool]
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def remove(self, tool: Tool) -> None:
        """The tool is not installed."""
        for path in _launcher_files(self.bin / tool):
            path.unlink(missing_ok=True)

    def not_executable(self, tool: Tool) -> None:
        """The launcher is there but loses its execute bits."""
        for path in _launcher_files(self.bin / tool):
            if path.exists():
                path.chmod(path.stat().st_mode & ~EXECUTE_BITS)

    def jdk(self, folder: Path, data: Mapping[str, Any]) -> Path:
        """A JDK folder with ``bin/java`` and ``bin/javac`` of its own; returns it, for ``JAVA_HOME``.

        Both launchers carry ``data`` as their script, each logging to the same log as the
        tool's launcher on ``PATH``.
        """
        self._jdks += 1
        for tool in ("java", "javac"):
            content = {**data, "log": str(self._logs[tool])}
            script = self._write_script(f"jdk{self._jdks}-{tool}.json", content)
            write_launcher(folder / "bin" / tool, tool, script=script)
        return folder
