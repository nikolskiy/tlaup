"""The state one feature scenario carries between its steps, and the helpers the steps wrap (design 01 T5).

``given.py``, ``when.py`` and ``then.py`` are thin wrappers over the methods of ``Scenario``, so that
``tests/unit/test_harness.py`` can call the helpers without a feature file. The real-process and terminal
runners live in ``_process.py`` and ``_terminal.py``.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import stat
import sys
import time
import tomllib
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

import pytest
from typer.testing import CliRunner

import tlaup.cli
import tlaup.context
import tlaup.java
from tests.expected import assert_matches
from tests.fakes.control import write_launcher
from tlaup.errors import TlaupError
from tlaup.paths import AppPaths

if TYPE_CHECKING:
    from collections.abc import Callable

    import typer

    from tests.conftest import Isolated
    from tests.fakes.control import Fakes, Tool

TESTS_DIR = Path(__file__).resolve().parent.parent
GOLDEN_DIR = TESTS_DIR / "parse" / "golden"
SPECS_DIR = GOLDEN_DIR / "specs"
EXPECTED_DIR = TESTS_DIR / "features" / "expected"

# The main class of a golden case, from the tool its folder names (package 18, "Declaring runs").
TOOL_MAINS = {"tlc": "tlc2.TLC", "sany": "tla2sany.SANY", "pcal": "pcal.trans"}
# The fake java's script fields for the signals it can be told about (T4).
SIGNAL_FIELDS = {"SIGINT": "on_sigint", "SIGTERM": "on_sigterm"}
VERSION_START = "-version"
EXIT_WAIT_SECONDS = 10.0
POLL_SECONDS = 0.02
CLOSED_STREAM = "it was a closed pipe or the null device"
PASSTHROUGH = 'this command passes the terminal through; use "as a process"'

_STARTUP_ONLY_NAMES = frozenset({"LC_ALL", "LC_CTYPE", "LANG"})
_PLACEHOLDER = re.compile(r"\{(home|work|tools|modules|runs|config|kept)\}")
_AGENT_PID = re.compile(r"(=pid=)\d+$")
# The folder of the installed package that holds the lifeline agent's jar, written as <tlaup> (D51).
TLAUP_JAVA_DIR = Path(tlaup.java.__file__).resolve().parent
_WRITE_BITS = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH


def _is_startup_only(name: str) -> bool:
    return name.startswith("PYTHON") or name in _STARTUP_ONLY_NAMES


# The variables the interpreter reads only when it starts (T12 rule 10): set in-process they do nothing.
STARTUP_ONLY: Callable[[str], bool] = _is_startup_only


def fail(message: str) -> NoReturn:
    pytest.fail(message, pytrace=False)


@dataclass
class Outcome:
    """What the last When step left."""

    exit_code: int  # as a shell reports it: a process ended by signal s is 128 + s
    stdout: str | None  # None: the stream could not be read (a closed pipe, the null device)
    stderr: str | None
    terminal: bytes | None = None  # everything read from the pty, for the terminal steps
    terminal_size: tuple[int, int] | None = None
    pid: int | None = None  # tlaup's process id (real processes only)
    pgid: int | None = None  # tlaup's process group (real processes only)


def _new_run(main: str, **fields: Any) -> dict[str, Any]:
    """One entry of the fake java's ``runs``, with every field of T4 at its default."""
    run: dict[str, Any] = {
        "main": main,
        "stdout": None,
        "stderr": None,
        "generate_lines": None,
        "exit": 0,
        "line_delay_ms": 0,
        "hang_after_line": None,
        "on_sigint": 130,
        "on_sigterm": 143,
        "write_into_metadir": [],
        "checkpoint": None,
        "echo_stdin": False,
        "replace": {},
    }
    run.update(fields)
    return run


def _is_kept(folder: Path) -> bool:
    try:
        data = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("kept") is True


def _process_alive(pid: int) -> bool:
    """True while the process exists and is not a zombie (POSIX)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    status = Path(f"/proc/{pid}/stat")
    try:
        state = status.read_text(encoding="ascii").rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return True
    return state != "Z"


class Scenario:
    """One scenario's state: the declared runs of the fakes, what was written, and the last outcome."""

    def __init__(
        self,
        isolated: Isolated,
        fakes: Fakes,
        request: pytest.FixtureRequest,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        self.isolated = isolated
        self.fakes = fakes
        self.env_set: dict[str, str] = {}  # what "the environment variable ..." set, for rule 10's second check
        self.config_written: bytes | None = None  # what "the config file contains:" wrote
        self.java_runs: list[dict[str, Any]] = []  # the declared runs of the fake java, in order
        self.java_settings: dict[str, Any] = {}  # the rest of java's script: version, version_delay_ms
        self.javac_settings: dict[str, Any] = {}
        self.editor_settings: dict[str, Any] = {}
        self.jdk: tuple[Path, str] | None = None  # the JAVA_HOME folder and its version, while it is a JDK
        self.outcome: Outcome | None = None
        self.before_run: list[Callable[[], None]] = []  # called by every When step before it runs tlaup
        self.expected_dir = EXPECTED_DIR
        self.folder = tmp_path / "scenario"  # the scenario's own files: release files, JDK folders
        self._request = request
        self._monkeypatch = monkeypatch
        self._cleanups: list[Callable[[], None]] = []
        self._replaced = 0
        request.addfinalizer(self.cleanup)

    def cleanup(self) -> None:
        """Undo what the steps changed outside monkeypatch (the read-only folders); runs at the end."""
        while self._cleanups:
            self._cleanups.pop()()

    # Placeholders

    def paths(self) -> AppPaths:
        """tlaup's folders, from the environment as it is now."""
        try:
            return AppPaths.from_env(os.environ)
        except TlaupError as error:
            fail(f"tlaup's folders cannot be worked out from the environment: {error}")

    def placeholder(self, name: str) -> Path:
        if name == "home":
            return self.isolated.home
        if name == "work":
            return self.isolated.work
        if name == "kept":
            return self.kept()
        paths = self.paths()
        folders = {"tools": paths.tools, "modules": paths.modules, "runs": paths.runs, "config": paths.config}
        return folders[name]

    def kept(self) -> Path:
        """The one folder under ``{runs}`` whose ``run.json`` holds ``"kept": true``."""
        runs = self.paths().runs
        found = [f for f in sorted(runs.iterdir()) if f.is_dir() and _is_kept(f)] if runs.is_dir() else []
        if len(found) != 1:
            names = ", ".join(f.name for f in found) or "none"
            fail(f"{{kept}} needs exactly one kept run folder under {runs}; found {len(found)}: {names}")
        return found[0]

    def expand(self, text: str) -> str:
        """Replace the seven placeholders; any other brace is left alone."""
        return _PLACEHOLDER.sub(lambda match: str(self.placeholder(match.group(1))), text)

    def words(self, command: str) -> list[str]:
        """``shlex.split``, then each word expanded, so a path with a space stays one word."""
        words = [self.expand(word) for word in shlex.split(command)]
        if not words or words[0] != "tlaup":
            fail(f'a command starts with "tlaup": {command!r}')
        return words

    def path(self, text: str) -> Path:
        """A path from a step, expanded; a relative one is read from the current folder."""
        path = Path(self.expand(text))
        return path if path.is_absolute() else Path.cwd() / path

    # When: in-process

    def run_in_process(self, command: str, *, app: typer.Typer | None = None) -> Outcome:
        """``I run "<command>"``: the app through ``CliRunner``, with T12 rule 10's two refusals."""
        words = self.words(command)
        startup = sorted(name for name in self.env_set if STARTUP_ONLY(name))
        if startup:
            fail(f'{", ".join(startup)} is read only when the interpreter starts; use "as a process"')
        for hook in self.before_run:
            hook()
        seen = len(self.fakes.log("java"))
        tlaup.context.reset()
        result = CliRunner().invoke(app if app is not None else tlaup.cli.app, words[1:])
        if result.exception is not None and not isinstance(result.exception, SystemExit):
            assert result.exc_info is not None
            text = "".join(traceback.format_exception(*result.exc_info))
            fail(f"{command!r} raised past the error mapping, a fault of the harness or the mapping:\n{text}")
        for line in self.fakes.log("java")[seen:]:
            if line.get("event") == "start" and line.get("main") != VERSION_START and not line.get("stdout_pipe"):
                fail(PASSTHROUGH)
        self.outcome = Outcome(exit_code=result.exit_code, stdout=result.stdout, stderr=result.stderr)
        return self.outcome

    # Given: files

    def spec_from_golden(self, name: str) -> None:
        """Copy ``<name>.tla`` and its ``.cfg``, if there is one, from the golden specs into the current folder."""
        tla = SPECS_DIR / f"{name}.tla"
        if not tla.is_file():
            fail(f"no golden spec {name}: {tla} does not exist")
        for source in (tla, tla.with_suffix(".cfg")):
            if source.is_file():
                shutil.copyfile(source, Path.cwd() / source.name)

    def write_file(self, path: str, text: str) -> None:
        target = self.path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.expand(text).encode("utf-8"))

    def write_config(self, text: str) -> None:
        data = self.expand(text).encode("utf-8")
        config = self.paths().config_file
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_bytes(data)
        self.config_written = data

    def read_only(self, path: str) -> None:
        """Remove the folder's write bits and give them back when the scenario ends."""
        if os.name == "nt":
            pytest.skip("folder permissions do not stop writes on Windows (D15)")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            pytest.skip("permissions do not bind when the suite runs as root")
        folder = self.path(path)
        folder.mkdir(parents=True, exist_ok=True)
        mode = stat.S_IMODE(folder.stat().st_mode)
        folder.chmod(mode & ~_WRITE_BITS)
        self._cleanups.append(lambda: folder.chmod(mode))

    def enter_folder(self, path: str) -> None:
        folder = self.path(path)
        folder.mkdir(parents=True, exist_ok=True)
        self._monkeypatch.chdir(folder)

    def set_env(self, name: str, value: str) -> None:
        """Set as given, an empty value included, and remember it for rule 10."""
        expanded = self.expand(value)
        self._monkeypatch.setenv(name, expanded)
        self.env_set[name] = expanded

    # Given: what Java does (each declares one run)

    def write_java(self) -> None:
        self.fakes.script("java", {**self.java_settings, "runs": self.java_runs})
        self._write_jdk()

    def write_javac(self) -> None:
        self.fakes.script("javac", self.javac_settings)
        self._write_jdk()

    def _write_jdk(self) -> None:
        """The JDK's launchers carry a copy of the scripts with its own version; rewritten on each change."""
        if self.jdk is None:
            return
        folder, version = self.jdk
        data = {**self.javac_settings, **self.java_settings, "runs": self.java_runs, "version": version}
        self.fakes.jdk(folder, data)

    def declare(self, main: str, **fields: Any) -> dict[str, Any]:
        run = _new_run(main, **fields)
        self.java_runs.append(run)
        self.write_java()
        return run

    def java_replays(self, case: str, exit_code: int) -> None:
        """``case`` is a path under ``tests/parse/golden/`` without ``.out``; its tool's folder gives the main class."""
        out = GOLDEN_DIR / f"{case}.out"
        if not out.is_file():
            fail(f"no golden case {case}: {out} does not exist")
        tool = case.split("/", 1)[0]
        if tool not in TOOL_MAINS:
            fail(f"golden case {case} is not under tlc/, sany/ or pcal/, so no main class is known for it")
        self.declare(TOOL_MAINS[tool], stdout=f"{case}.out", stderr=self._golden_stderr(case), exit=exit_code)

    @staticmethod
    def _golden_stderr(case: str) -> str | None:
        """The case's ``.err`` file when its ``cases.toml`` table has a ``stderr`` key."""
        relative = Path(case)
        folder = GOLDEN_DIR / relative.parent
        table: dict[str, Any] = {}
        if (folder / "cases.toml").is_file():
            table = tomllib.loads((folder / "cases.toml").read_text(encoding="utf-8")).get(relative.name, {})
        elif folder.name == "plain" and (folder.parent / "cases.toml").is_file():
            cases = tomllib.loads((folder.parent / "cases.toml").read_text(encoding="utf-8"))
            table = cases.get("plain", {}).get(relative.name, {})
        stderr = table.get("stderr")
        return (relative.parent / stderr).as_posix() if stderr else None

    def java_prints(self, count: int) -> None:
        self.declare("tlc2.TLC", generate_lines=count)

    def java_writes(self, out: str, err: str) -> None:
        self.declare("tlc2.TLC", stdout={"text": self.expand(out) + "\n"}, stderr={"text": self.expand(err) + "\n"})

    def java_echoes(self) -> None:
        self.declare("tlc2.REPL", echo_stdin=True)

    # Given: changes to the run declared last

    def last_run(self) -> dict[str, Any]:
        if not self.java_runs:
            fail("no run of java is declared yet: a change needs java replays, prints, writes or echoes before it")
        return self.java_runs[-1]

    def change_run(self, **fields: Any) -> None:
        self.last_run().update(fields)
        self.write_java()

    def metadir_files(self, names: str) -> None:
        self.change_run(write_into_metadir=[name.strip() for name in names.split(",") if name.strip()])

    def checkpoint(self, begin_after: int, commit_before: int) -> None:
        """T4's ``checkpoint``, its release file in the scenario's folder and not there yet."""
        run = self.last_run()
        releases = self.folder / "releases"
        releases.mkdir(parents=True, exist_ok=True)
        release = releases / f"run-{len(self.java_runs) - 1}-checkpoint"
        checkpoint = {
            "begin_after_line": begin_after,
            "commit_before_line": commit_before,
            "release_file": str(release),
        }
        run["checkpoint"] = checkpoint
        self.write_java()

    def replace_output(self, old: str, new: str) -> None:
        """One entry of T4's ``replace``: ``old`` as written, ``new`` with the placeholders expanded."""
        run = self.last_run()
        run["replace"] = {**run["replace"], old: self.expand(new)}
        self.write_java()

    def on_signal(self, name: str, action: int | str) -> None:
        field = SIGNAL_FIELDS.get(name)
        if field is None:
            fail(f"the fake java can be told what to do on SIGINT or SIGTERM only, not on {name} (T4)")
        self.change_run(**{field: action})

    # Given: which Java there is

    def java_version(self, version: Any) -> None:
        self.java_settings["version"] = version
        self.write_java()

    def java_replaced_by(self, version: str) -> None:
        """A new launcher file on PATH, so its size and time change, with the script at that version."""
        self.java_version(version)
        self._replaced += 1
        launcher = self.fakes.bin / "java"
        launcher.unlink(missing_ok=True)
        write_launcher(launcher, "java")
        with launcher.open("a", encoding="utf-8") as handle:
            handle.write(f"# replaced {self._replaced}\n")

    def java_version_delay(self, seconds: int) -> None:
        self.java_settings["version_delay_ms"] = seconds * 1000
        self.write_java()

    def java_version_answer(self, text: str, stream: str, exit_code: int) -> None:
        """T4's object form of ``version``: the text and a newline on the stream named, nothing on the other."""
        line = self.expand(text) + "\n"
        answer = {"stdout": line if stream == "stdout" else "", "stderr": line if stream == "stderr" else ""}
        self.java_version({**answer, "exit": exit_code})

    def java_home_jdk(self, version: str) -> None:
        folder = self.folder / "jdk"
        self.jdk = (folder, version)
        self._write_jdk()
        self._monkeypatch.setenv("JAVA_HOME", str(folder))

    def java_home_empty(self) -> None:
        folder = self.folder / "jdk-empty"
        folder.mkdir(parents=True, exist_ok=True)
        self.jdk = None
        self._monkeypatch.setenv("JAVA_HOME", str(folder))

    def javac_version(self, version: str) -> None:
        self.javac_settings["version"] = version
        self.write_javac()

    def not_installed(self, tool: Tool) -> None:
        self.fakes.remove(tool)

    def not_executable(self, tool: Tool) -> None:
        self.fakes.not_executable(tool)

    # Given: the editor

    def editor(self, **fields: Any) -> None:
        self.editor_settings.update(fields)
        self.fakes.script("editor", self.editor_settings)

    # Then: the result

    def result(self) -> Outcome:
        if self.outcome is None:
            fail("no command has run yet: a When step comes first")
        return self.outcome

    def stream(self, name: str) -> str:
        """``stdout`` or ``stderr`` of the last run."""
        value: str | None = getattr(self.result(), name)
        if value is None:
            fail(f"{name} cannot be read: {CLOSED_STREAM}")
        return value

    def _show(self) -> str:
        outcome = self.result()
        return f"\n--- stdout ---\n{outcome.stdout}\n--- stderr ---\n{outcome.stderr}"

    def check_exit_code(self, code: int) -> None:
        actual = self.result().exit_code
        if actual != code:
            fail(f"the exit code is {actual}, not {code}{self._show()}")

    def check_contains(self, name: str, text: str, times: int | None = None) -> None:
        stream, wanted = self.stream(name), self.expand(text)
        if times is None:
            if wanted not in stream:
                fail(f"{name} does not contain {wanted!r}{self._show()}")
            return
        count = stream.count(wanted)
        if count != times:
            fail(f"{name} contains {wanted!r} {count} times, not {times}{self._show()}")

    def check_not_contains(self, name: str, text: str) -> None:
        wanted = self.expand(text)
        if wanted in self.stream(name):
            fail(f"{name} contains {wanted!r}{self._show()}")

    def check_exactly(self, name: str, text: str) -> None:
        stream, wanted = self.stream(name).removesuffix("\n"), self.expand(text)
        if stream != wanted:
            fail(f"{name} is {stream!r}, not {wanted!r}")

    def check_empty(self, name: str) -> None:
        if self.stream(name) != "":
            fail(f"{name} is not empty{self._show()}")

    def check_matches(self, actual: str, name: str) -> None:
        assert_matches(actual, self.expected_dir / name, self._request)

    # Then: files and the cache

    def check_file(self, path: str, *, exists: bool) -> None:
        target = self.path(path)
        if target.exists() != exists:
            fail(f"{target} {'does not exist' if exists else 'exists'}")

    def file_text(self, path: str) -> str:
        target = self.path(path)
        if not target.is_file():
            fail(f"{target} is not a file")
        return target.read_bytes().decode("utf-8", errors="replace")

    def check_file_contains(self, path: str, text: str) -> None:
        wanted = self.expand(text)
        if wanted not in self.file_text(path):
            fail(f"{self.path(path)} does not contain {wanted!r}")

    def check_config_unchanged(self) -> None:
        if self.config_written is None:
            fail('"the config file is unchanged" needs "the config file contains:" before it')
        config = self.paths().config_file
        actual = config.read_bytes() if config.is_file() else None
        if actual != self.config_written:
            fail(f"{config} changed: it holds {actual!r}, not {self.config_written!r}")

    def run_folders(self) -> list[Path]:
        runs = self.paths().runs
        return sorted(f for f in runs.iterdir() if f.is_dir()) if runs.is_dir() else []

    def check_run_folders(self, count: int) -> None:
        found = self.run_folders()
        if len(found) != count:
            fail(f"the cache holds {len(found)} run folders, not {count}: {[f.name for f in found]}")

    def check_no_lock_files(self) -> None:
        runs = self.paths().runs
        locks = sorted(runs.glob("*.lock")) if runs.is_dir() else []
        if locks:
            fail(f"the cache holds lock files: {[f.name for f in locks]}")

    # Then: the fakes

    def starts(self, tool: Tool) -> list[dict[str, Any]]:
        """Every ``start`` line of the scenario's log, the version check included."""
        return [line for line in self.fakes.log(tool) if line.get("event") == "start"]

    def check_started(self, tool: Tool, times: int) -> None:
        count = len(self.starts(tool))
        if count != times:
            fail(f"{tool} was started {count} times, not {times}: {self.starts(tool)}")

    def check_started_with(self, tool: Tool, argument: str, *, present: bool) -> None:
        wanted = self.expand(argument)
        found = any(wanted in line.get("args", []) for line in self.starts(tool))
        if found != present:
            verb = "was not" if present else "was"
            fail(f"{tool} {verb} started with {wanted!r}: {[line.get('args') for line in self.starts(tool)]}")

    def check_ran(self, main: str, times: int) -> None:
        count = sum(1 for line in self.starts("java") if line.get("main") == main)
        if count != times:
            fail(f"java ran {main} {count} times, not {times}")

    def last_tool_start(self) -> dict[str, Any]:
        """The last start of java with a main class, not the version check."""
        tools = [line for line in self.starts("java") if line.get("main") not in (None, VERSION_START)]
        if not tools:
            fail("java never ran a tool")
        return tools[-1]

    def check_started_in(self, path: str) -> None:
        actual, wanted = Path(self.last_tool_start()["cwd"]).resolve(), self.path(path).resolve()
        if actual != wanted:
            fail(f"java was started in {actual}, not {wanted}")

    def check_ran_from(self, launcher: Path) -> None:
        actual = Path(self.last_tool_start()["path"]).resolve()
        if actual != launcher.resolve():
            fail(f"java ran from {actual}, not {launcher}")

    def check_ran_from_java_home(self) -> None:
        java_home = os.environ.get("JAVA_HOME")
        if not java_home:
            fail("JAVA_HOME is not set")
        self.check_ran_from(Path(java_home) / "bin" / "java")

    def check_ran_from_path(self) -> None:
        self.check_ran_from(self.fakes.bin / "java")

    def java_command(self) -> str:
        """The last tool start's arguments, one per line, with the values that change from run to run replaced.

        The scenario's folders become their placeholders (longest path first), the lifeline agent's process
        id ``<pid>``, the folder of the agent's jar ``<tlaup>``, and the run id of the ``-metadir`` path
        ``<run-id>`` (T5's note; T8's helper is untouched).
        """
        args = [str(arg) for arg in self.last_tool_start()["args"]]
        folders: list[tuple[str, str]] = [("home", str(self.isolated.home)), ("work", str(self.isolated.work))]
        try:
            paths = AppPaths.from_env(os.environ)
        except TlaupError:
            paths = None
        if paths is not None:
            for name in ("tools", "modules", "runs", "config"):
                folders.append((name, str(getattr(paths, name))))
        folders.sort(key=lambda item: len(item[1]), reverse=True)
        run_id = None
        if paths is not None and "-metadir" in args[:-1]:
            metadir = Path(args[args.index("-metadir") + 1])
            if metadir.is_relative_to(paths.runs) and metadir != paths.runs:
                run_id = metadir.relative_to(paths.runs).parts[0]
        lines = []
        for arg in args:
            text = arg.replace(f"{TLAUP_JAVA_DIR}{os.sep}", "<tlaup>/")
            for name, folder in folders:
                text = text.replace(folder, f"{{{name}}}")
            if run_id is not None:
                text = text.replace(f"{{runs}}{os.sep}{run_id}", "{runs}/<run-id>")
            if text.startswith("-javaagent:"):
                text = _AGENT_PID.sub(r"\1<pid>", text)
            lines.append(text)
        return "\n".join(lines) + "\n"

    def check_java_exited(self, timeout: float = EXIT_WAIT_SECONDS) -> None:
        """Every process id of a java ``start`` line no longer exists, waited for up to ``timeout``."""
        if os.name == "nt" or sys.platform == "win32":
            pytest.skip("process ids are checked the POSIX way; no Windows CI (D15)")
        pids = {int(line["pid"]) for line in self.starts("java")}
        deadline = time.monotonic() + timeout
        alive = sorted(pid for pid in pids if _process_alive(pid))
        while alive:
            if time.monotonic() >= deadline:
                fail(f"java processes still running after {timeout} seconds: {alive}")
            time.sleep(POLL_SECONDS)
            alive = sorted(pid for pid in alive if _process_alive(pid))
