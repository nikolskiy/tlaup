"""Finding `java` and `javac`, checking their version, and remembering the answer (design 13 J2, J3, M3).

Nothing here prints: warnings travel in the values returned, and the caller prints them after every
check has passed (D45).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from tlaup.errors import Failed, JavacNotFound, JavaNotFound, JavaTooOld, ToolStartError

TIMEOUT_SECONDS = 10.0
KILL_GRACE_SECONDS = 2.0
SCHEMA = 1
WINDOWS = os.name == "nt"
MACOS_PLATFORM = "darwin"
MACOS_USR_BIN = Path("/usr/bin")
MACOS_JAVA_HOME_STUB = Path("/usr/libexec/java_home")
SHEBANG = b"#!"
LEGACY_MAJOR = 1  # "1.8.0_202" means Java 8

# The two `java` patterns (row J1 of the preserved-behaviour inventory); `javac` has its own (M3).
JAVA_PATTERNS = (
    re.compile(r'version "(\d+(\.\d+)*(_\d+)?(-\w+)?)"'),
    re.compile(r"version (\d+(\.\d+)*)"),
)
JAVAC_PATTERN = re.compile(r"^javac (\d+(\.\d+)*(_\d+)?(-\w+)?)", re.MULTILINE)


@dataclass(frozen=True)
class JavaTool:
    path: Path
    source: str  # "JAVA_HOME" or "PATH"


@dataclass(frozen=True)
class Located:
    tool: JavaTool | None
    warning: str | None  # for example a JAVA_HOME that holds no such tool


@dataclass(frozen=True)
class JavaRuntime:
    tool: JavaTool
    version: str | None  # "25.0.5"; None when the answer could not be read (J3)
    major: int | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class VersionAnswer:
    """What `<tool> -version` printed (both streams) and its exit status."""

    text: str
    exit_code: int


AskVersion = Callable[[Path], VersionAnswer]


def _is_executable_file(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def locate(name: Literal["java", "javac"], env: Mapping[str, str]) -> Located:
    """`$JAVA_HOME/bin/<name>` when it is an executable file, else `<name>` on `PATH`."""
    warning: str | None = None
    java_home = env.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home).absolute() / "bin" / (name + ".exe" if WINDOWS else name)
        if _is_executable_file(candidate):
            return Located(JavaTool(candidate, "JAVA_HOME"), None)
        warning = f"JAVA_HOME is set to {java_home} but it holds no executable bin/{name}; using PATH"
    # An empty string, not None: None would make `which` read the process environment.
    found = shutil.which(name, path=env.get("PATH", ""))
    if found is None:
        return Located(None, warning)
    return Located(JavaTool(Path(found).absolute(), "PATH"), warning)


def _kill(process: subprocess.Popen[bytes]) -> None:
    if WINDOWS:
        process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except OSError:  # already gone
        process.kill()


def ask_version(tool: Path, timeout: float = TIMEOUT_SECONDS) -> VersionAnswer:
    """Runs `<tool> -version` and returns what it printed on either stream, with the exit status."""
    try:
        process = subprocess.Popen(
            [str(tool), "-version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=not WINDOWS,  # a group of its own, so a shim's children can be killed too
        )
    except OSError as error:
        message = f"{tool} could not be started: {error.strerror or error}"
        raise ToolStartError(message, hint="check that the file is a Java program for this machine") from error
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        _kill(process)
        try:
            process.communicate(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:  # something outside the group still holds the pipes
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
            process.wait()
        seconds = f"{timeout:g}"
        message = f"{tool} -version did not answer within {seconds} seconds"
        raise Failed(message, hint="check that this Java starts, or run `tlaup doctor`") from error
    text = out.decode("utf-8", errors="replace") + err.decode("utf-8", errors="replace")
    return VersionAnswer(text, process.returncode)


def parse_version(text: str, name: Literal["java", "javac"]) -> tuple[str, int] | None:
    """The version string and the major number in `text`, or None when it holds no version."""
    patterns = (JAVAC_PATTERN,) if name == "javac" else JAVA_PATTERNS
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            version = match.group(1)
            return version, _major(version)
    return None


def _major(version: str) -> int:
    numbers = [int(n) for n in re.findall(r"\d+", re.split(r"[_-]", version)[0])]
    if numbers[0] == LEGACY_MAJOR and len(numbers) > 1:
        return numbers[1]
    return numbers[0]


# ---- the remembered answers (J3) -------------------------------------------------------------


def _is_remembered(path: Path, platform: str, usr_bin: Path, java_home_stub: Path) -> bool:
    """Only a plain binary named java or javac is remembered (J3)."""
    resolved = path.resolve()
    expected = ("java.exe", "javac.exe") if WINDOWS else ("java", "javac")
    name = resolved.name.lower() if WINDOWS else resolved.name
    if name not in expected:
        return False
    try:
        with resolved.open("rb") as handle:
            if handle.read(len(SHEBANG)) == SHEBANG:
                return False
    except OSError:
        return False
    if platform == MACOS_PLATFORM:
        if usr_bin.resolve() in (path.absolute().parent, resolved.parent):
            return False
        with contextlib.suppress(OSError):
            if java_home_stub.exists() and resolved.samefile(java_home_stub):
                return False
    return True


def _read_entries(cache_file: Path) -> dict[str, Any]:
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}


def _remembered(cache_file: Path, resolved: Path) -> tuple[str, int] | None:
    entry = _read_entries(cache_file).get(str(resolved))
    try:
        stat = resolved.stat()
    except OSError:
        return None
    if not isinstance(entry, dict):
        return None
    version, major = entry.get("version"), entry.get("major")
    if entry.get("size") != stat.st_size or entry.get("mtime_ns") != stat.st_mtime_ns:
        return None
    if not isinstance(version, str) or not isinstance(major, int) or isinstance(major, bool):
        return None
    return version, major


def _forget(cache_file: Path, resolved: Path) -> None:
    """Drops a stale entry after a refresh that found no version."""
    entries = _read_entries(cache_file)
    if entries.pop(str(resolved), None) is not None:
        _write_entries(cache_file, entries)


def _remember(cache_file: Path, resolved: Path, version: str, major: int) -> None:
    """Best effort, atomic: write beside the file, then rename. A failure only costs one more Java start."""
    try:
        stat = resolved.stat()
    except OSError:
        return
    entries = _read_entries(cache_file)
    entries[str(resolved)] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "version": version, "major": major}
    _write_entries(cache_file, entries)


def _write_entries(cache_file: Path, entries: dict[str, Any]) -> None:
    temp: str | None = None
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=cache_file.parent, prefix=cache_file.name + ".", suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({"schema": SCHEMA, "entries": entries}, stream)
        Path(temp).replace(cache_file)
        temp = None
    except OSError:
        pass
    finally:
        if temp is not None:
            with contextlib.suppress(OSError):
                Path(temp).unlink()


# ---- the two entry points ----------------------------------------------------------------------


def _not_found(name: Literal["java", "javac"], min_version: int, details: str | None) -> JavaNotFound | JavacNotFound:
    if name == "javac":
        return JavacNotFound(
            "javac was not found; `module add` needs a JDK, not only a Java runtime",
            hint=f"install a JDK {min_version} or newer",
            details=details,
        )
    return JavaNotFound(
        "Java was not found (looked in JAVA_HOME and PATH)",
        hint=f"install Java {min_version} or newer",
        details=details,
    )


def _require(  # noqa: PLR0913
    name: Literal["java", "javac"],
    env: Mapping[str, str],
    *,
    min_version: int,
    cache_file: Path,
    ask: AskVersion,
    refresh: bool,
    platform: str,
    usr_bin: Path,
    java_home_stub: Path,
) -> JavaRuntime:
    located = locate(name, env)
    tool = located.tool
    if tool is None:
        raise _not_found(name, min_version, located.warning)
    warnings = (located.warning,) if located.warning else ()
    resolved = tool.path.resolve()
    remember = _is_remembered(tool.path, platform, usr_bin, java_home_stub)

    parsed = None if (refresh or not remember) else _remembered(cache_file, resolved)
    if parsed is None:
        answer = ask(tool.path)
        parsed = parse_version(answer.text, name)
        if parsed is None:
            printed = answer.text.strip()
            if remember:
                _forget(cache_file, resolved)
            if answer.exit_code != 0:
                raise _not_found(name, min_version, printed or None)
            shown = printed or "nothing"
            warning = f"could not read a version from `{tool.path} -version`; it printed: {shown}"
            return JavaRuntime(tool, None, None, (*warnings, warning))
        if remember:
            _remember(cache_file, resolved, *parsed)
    version, major = parsed
    if major < min_version:
        raise _too_old(name, tool, major, min_version)
    return JavaRuntime(tool, version, major, warnings)


def _too_old(name: Literal["java", "javac"], tool: JavaTool, major: int, min_version: int) -> JavaTooOld:
    subject = "javac" if name == "javac" else "Java"
    message = f"{subject} {min_version} or newer is needed; {tool.path} is version {major}"
    if tool.source == "JAVA_HOME":
        message += " (found through JAVA_HOME)"
        hint = f"point JAVA_HOME at a newer JDK or unset it, or install {subject} {min_version} or newer"
    else:
        hint = f"install {'a JDK' if name == 'javac' else 'Java'} {min_version} or newer"
    return JavaTooOld(message, hint=hint)


def require_java(  # noqa: PLR0913
    env: Mapping[str, str],
    *,
    min_version: int,
    cache_file: Path,
    ask_version: AskVersion = ask_version,
    refresh: bool = False,
    platform: str = sys.platform,
    usr_bin: Path = MACOS_USR_BIN,
    java_home_stub: Path = MACOS_JAVA_HOME_STUB,
) -> JavaRuntime:
    """Finds `java`, checks its version; raises JavaNotFound, JavaTooOld, Failed, ToolStartError."""
    return _require(
        "java",
        env,
        min_version=min_version,
        cache_file=cache_file,
        ask=ask_version,
        refresh=refresh,
        platform=platform,
        usr_bin=usr_bin,
        java_home_stub=java_home_stub,
    )


def require_javac(  # noqa: PLR0913
    env: Mapping[str, str],
    *,
    min_version: int,
    cache_file: Path,
    ask_version: AskVersion = ask_version,
    refresh: bool = False,
    platform: str = sys.platform,
    usr_bin: Path = MACOS_USR_BIN,
    java_home_stub: Path = MACOS_JAVA_HOME_STUB,
) -> JavaRuntime:
    """As `require_java` for `javac` (M3); raises JavacNotFound instead of JavaNotFound."""
    return _require(
        "javac",
        env,
        min_version=min_version,
        cache_file=cache_file,
        ask=ask_version,
        refresh=refresh,
        platform=platform,
        usr_bin=usr_bin,
        java_home_stub=java_home_stub,
    )
