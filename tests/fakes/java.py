"""The fake ``java`` (design 01 T4, package 03's contract).

Reads its script from the launcher or ``TLAUP_FAKE_JAVA``, logs ``start``, ``signal``,
``checkpoint`` and ``exit`` lines, answers ``-version`` and replays one declared run per start.
Standard library only; no import of tlaup or pytest.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tests.fakes import _fakelib
from tests.fakes._fakelib import GOLDEN_DIR, GUARD_EXIT, GUARD_SECONDS, FakeExit, Log, ScriptError

if TYPE_CHECKING:
    from types import FrameType

VALUE_OPTIONS = frozenset({"-cp", "-classpath", "--class-path"})
VERSION_REQUEST = "-version"
DEFAULT_VERSION = "25.0.5"
POLL_SECONDS = 0.02

# The signals the fake handles, by name, guarded for systems that lack them (D15).
SIGNAL_NAMES = ("SIGINT", "SIGTERM", "SIGQUIT", "SIGHUP")
SIGHUP_EXIT = 129


@dataclass
class JavaArgs:
    jvm_options: list[str]
    main: str | None
    main_args: list[str]
    version_request: bool


def parse_args(args: list[str]) -> JavaArgs:
    """Read the arguments as ``java`` does: options until the first argument that is not one."""
    options: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if not arg.startswith("-"):
            return JavaArgs(options, arg, args[i + 1 :], version_request=False)
        if arg == VERSION_REQUEST:
            return JavaArgs(options, None, [], version_request=True)
        if arg in VALUE_OPTIONS:
            options.extend(args[i : i + 2])
            i += 2
            continue
        options.append(arg)
        i += 1
    return JavaArgs(options, None, [], version_request=False)


def banner(version: str) -> str:
    """The real three-line form, as research 28 captured it on a GitHub runner."""
    return (
        f'openjdk version "{version}" 2026-10-20\n'
        f"OpenJDK Runtime Environment Temurin-{version}+10 (build {version}+10)\n"
        f"OpenJDK 64-Bit Server VM Temurin-{version}+10 (build {version}+10, mixed mode)\n"
    )


def choose_run(script: Mapping[str, Any], main: str, log: Log) -> int | None:
    """The first entry of ``runs`` for ``main`` that no earlier ``start`` line took."""
    taken = {line.get("run") for line in log.read() if line.get("event") == "start"}
    for index, run in enumerate(script.get("runs") or []):
        if run.get("main") == main and index not in taken:
            return index
    return None


def install_signals(run: Mapping[str, Any], log: Log) -> list[str]:
    """Handlers for the four signals; one ignored at start stays ignored. Returns those names."""
    actions: dict[str, Any] = {
        "SIGINT": run.get("on_sigint", 130),
        "SIGTERM": run.get("on_sigterm", 143),
        "SIGQUIT": "ignore",
        "SIGHUP": SIGHUP_EXIT,
    }
    ignored: list[str] = []
    for name in SIGNAL_NAMES:
        if not hasattr(signal, name):
            continue
        number = getattr(signal, name)
        if signal.getsignal(number) == signal.SIG_IGN:
            ignored.append(name)
            continue
        signal.signal(number, _handler(name, actions[name], log))
    return ignored


def _handler(name: str, action: Any, log: Log) -> Callable[[int, FrameType | None], None]:
    def handle(_signum: int, _frame: FrameType | None) -> None:
        log.write("signal", name=name)
        if action != "ignore":
            raise FakeExit(int(action))

    return handle


def wait_until(condition: Callable[[], bool]) -> None:
    """Poll ``condition``; after the guard time, end with 124. A signal handler may end it sooner."""
    deadline = time.monotonic() + GUARD_SECONDS
    while not condition():
        if time.monotonic() >= deadline:
            raise FakeExit(GUARD_EXIT)
        time.sleep(POLL_SECONDS)


def hang() -> None:
    wait_until(lambda: False)


def metadir_of(args: JavaArgs) -> Path | None:
    rest = args.main_args
    for i, arg in enumerate(rest[:-1]):
        if arg == "-metadir":
            return Path(rest[i + 1])
    return None


def split_lines(data: bytes) -> list[bytes]:
    """Lines with their endings kept, so that joining them gives ``data`` byte for byte."""
    lines = data.split(b"\n")
    out = [line + b"\n" for line in lines[:-1]]
    if lines[-1]:
        out.append(lines[-1])
    return out


@dataclass
class Replay:
    """Writes the run's stdout line by line, with its pacing, hang and checkpoint."""

    run: Mapping[str, Any]
    log: Log
    folder: Path | None
    count: int = 0
    pipe_closed: bool = False
    replace: list[tuple[bytes, bytes]] = field(default_factory=list)

    def __post_init__(self) -> None:
        pairs = (self.run.get("replace") or {}).items()
        self.replace = [(str(k).encode("utf-8"), str(v).encode("utf-8")) for k, v in pairs]

    def lines(self) -> Iterator[bytes]:
        generate = self.run.get("generate_lines")
        if generate is not None:
            for i in range(1, int(generate) + 1):
                yield f"line {i}\n".encode()
            return
        data = _fakelib.text_or_file(self.run.get("stdout"), GOLDEN_DIR)
        if data is not None:
            yield from split_lines(data)

    def write(self, data: bytes) -> None:
        if self.pipe_closed:
            return
        try:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        except BrokenPipeError:
            # The JVM's PrintStream swallows a closed pipe and runs on; so does the fake.
            self.pipe_closed = True
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, 1)
            os.close(devnull)

    def after_line(self) -> None:
        checkpoint = self.run.get("checkpoint")
        if checkpoint and self.count == int(checkpoint["begin_after_line"]):
            self.begin_checkpoint(checkpoint)
        hang_after = self.run.get("hang_after_line")
        if hang_after is not None and self.count == int(hang_after):
            hang()

    def before_line(self) -> None:
        checkpoint = self.run.get("checkpoint")
        if checkpoint and self.count + 1 == int(checkpoint["commit_before_line"]):
            self.commit_checkpoint()
        _fakelib.sleep_ms(self.run.get("line_delay_ms"))

    def begin_checkpoint(self, checkpoint: Mapping[str, Any]) -> None:
        assert self.folder is not None
        for name in ("queue.tmp", "vars.tmp"):
            (self.folder / name).write_bytes(b"")
        self.log.write("checkpoint", folder=str(self.folder))
        release = checkpoint.get("release_file")
        if release is not None:
            release_path = Path(release)
            wait_until(release_path.exists)

    def commit_checkpoint(self) -> None:
        assert self.folder is not None
        for stem in ("queue", "vars"):
            tmp = self.folder / f"{stem}.tmp"
            if tmp.exists():
                tmp.replace(self.folder / f"{stem}.chkpt")

    def play(self) -> None:
        self.after_line()
        for line in self.lines():
            self.before_line()
            for old, new in self.replace:
                line = line.replace(old, new)  # noqa: PLW2901
            self.write(line)
            self.count += 1
            self.after_line()


def answer_version(script: Mapping[str, Any]) -> int:
    _fakelib.sleep_ms(script.get("version_delay_ms"))
    version = script.get("version", DEFAULT_VERSION)
    if isinstance(version, Mapping):
        sys.stdout.write(str(version.get("stdout") or ""))
        sys.stdout.flush()
        sys.stderr.write(str(version.get("stderr") or ""))
        sys.stderr.flush()
        return int(version.get("exit", 0))
    sys.stderr.write(banner(str(version)))
    sys.stderr.flush()
    return 0


def timestamped_folder(metadir: Path) -> Path:
    """A folder under ``-metadir`` named as TLC names it, for example ``26-11-14-22-32-49``."""
    folder = metadir / time.strftime("%y-%m-%d-%H-%M-%S")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def act(script: Mapping[str, Any], log: Log) -> int:
    args = parse_args(sys.argv[1:])
    if args.version_request:
        ignored = install_signals({}, log)
        log.write("start", **_fakelib.start_fields(main=VERSION_REQUEST, run=None, ignored_signals=ignored))
        return answer_version(script)
    if args.main is None:
        log.write("start", **_fakelib.start_fields(main=None, run=None, ignored_signals=[]))
        message = "no main class among the arguments"
        raise ScriptError(message)
    index = choose_run(script, args.main, log)
    run: Mapping[str, Any] = script["runs"][index] if index is not None else {}
    ignored = install_signals(run, log)
    log.write("start", **_fakelib.start_fields(main=args.main, run=index, ignored_signals=ignored))
    if index is None:
        message = f"no script for {args.main}"
        raise ScriptError(message)
    return play_run(run, args, log)


def play_run(run: Mapping[str, Any], args: JavaArgs, log: Log) -> int:
    folder = None
    into_metadir = run.get("write_into_metadir") or []
    if run.get("checkpoint") or into_metadir:
        metadir = metadir_of(args)
        if metadir is None:
            message = "checkpoint and write_into_metadir need -metadir among the arguments"
            raise ScriptError(message)
        folder = timestamped_folder(metadir)
        for name in into_metadir:
            (folder / name).write_bytes(b"")
    stderr = _fakelib.text_or_file(run.get("stderr"), GOLDEN_DIR)
    if stderr is not None:
        sys.stderr.buffer.write(stderr)
        sys.stderr.buffer.flush()
    replay = Replay(run, log, folder)
    replay.play()
    if run.get("echo_stdin"):
        for line in iter(sys.stdin.buffer.readline, b""):
            replay.write(line)
    return int(run.get("exit", 0))


def main(baked: str | None = None) -> int:
    return _fakelib.run_tool("java", baked, act)


if __name__ == "__main__":
    sys.exit(main())
