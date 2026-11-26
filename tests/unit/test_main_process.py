"""`main()` as a real process (design 14 F10, 02 X1 rule 8): closed pipes, the null device, a full disk, SIGINT.

A closed pipe is made with `os.pipe()` and its read end closed before the child starts, never `| head -1`,
which races with short output (01 T5). Each child starts with SIGINT at its default disposition.
"""

import os
import select
import signal
import subprocess
import sys
from collections.abc import Iterator, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX pipes, signals and preexec_fn (D15: no Windows CI)")

APPS = Path(__file__).with_name("handler_apps.py")
TLAUP = [sys.executable, "-m", "tlaup"]
TIMEOUT = 30  # seconds; a wait's limit, not a measurement
linux_only = pytest.mark.skipif(not Path("/dev/full").exists(), reason="/dev/full exists on Linux only")


def small(*args: str) -> list[str]:
    return [sys.executable, str(APPS), *args]


def _default_sigint() -> None:
    signal.signal(signal.SIGINT, signal.SIG_DFL)


@dataclass
class Done:
    code: int
    stdout: str | None
    stderr: str | None


class Streams:
    """The arrangements of a child's two streams: open pipes, a dead pipe, the null device, /dev/full."""

    def __init__(self, stack: ExitStack) -> None:
        self._stack = stack
        self._dead: int | None = None

    def dead(self) -> int:
        """A pipe whose reader has gone before the child starts; the same one each time it is asked for."""
        if self._dead is None:
            read, write = os.pipe()
            os.close(read)
            self._stack.callback(os.close, write)
            self._dead = write
        return self._dead

    def file(self, path: str) -> IO[bytes]:
        return self._stack.enter_context(Path(path).open("wb"))


@pytest.fixture
def streams() -> Iterator[Streams]:
    with ExitStack() as stack:
        yield Streams(stack)


PIPE = subprocess.PIPE


def run(argv: Sequence[str], *, stdout: Any = PIPE, stderr: Any = PIPE) -> Done:
    with subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        preexec_fn=_default_sigint,  # noqa: PLW1509 - test code: the child must see SIGINT (01 T5)
    ) as child:
        out, err = child.communicate(timeout=TIMEOUT)
    return Done(
        child.returncode,
        None if out is None else out.decode(),
        None if err is None else err.decode(),
    )


def no_traceback(done: Done) -> None:
    if done.stderr is not None:
        assert "Traceback" not in done.stderr, done.stderr


# --- Typer's own printing: help, no arguments, usage errors ---


@pytest.mark.parametrize("args", [["--help"], ["config", "--help"], []], ids=["help", "config help", "no arguments"])
def test_help_into_a_closed_stdout_is_141(args: list[str], streams: Streams) -> None:
    done = run([*TLAUP, *args], stdout=streams.dead())
    assert done.code == 141
    no_traceback(done)


def test_unknown_option_with_both_streams_on_the_closed_pipe_is_141(streams: Streams) -> None:
    assert run([*TLAUP, "--nosuch"], stdout=streams.dead(), stderr=streams.dead()).code == 141


def test_unknown_option_with_stdout_on_null_and_stderr_closed_is_141(streams: Streams) -> None:
    assert run([*TLAUP, "--nosuch"], stdout=streams.file(os.devnull), stderr=streams.dead()).code == 141


def test_unknown_option_with_nothing_closed_is_2() -> None:
    done = run([*TLAUP, "--nosuch"])
    assert done.code == 2
    assert done.stdout == ""
    no_traceback(done)


def test_help_into_an_open_pipe_is_0() -> None:
    done = run([*TLAUP, "--help"])
    assert done.code == 0
    assert "Usage:" in (done.stdout or "")
    no_traceback(done)


# --- errors reported while a reader has gone ---


@pytest.mark.parametrize("case", ["domain-error", "internal-error"])
@pytest.mark.parametrize("stdout", ["open", "same dead pipe", "null device"])
def test_an_error_with_stderrs_reader_gone_is_141(case: str, stdout: str, streams: Streams) -> None:
    out = {"open": PIPE, "same dead pipe": streams.dead(), "null device": streams.file(os.devnull)}[stdout]
    assert run(small(case), stdout=out, stderr=streams.dead()).code == 141


def test_a_domain_error_with_only_stdouts_reader_gone_keeps_its_code(streams: Streams) -> None:
    done = run(small("domain-error"), stdout=streams.dead())
    assert done.code == 3
    assert (done.stderr or "").splitlines()[0] == "error: the config is broken"
    no_traceback(done)


@pytest.mark.parametrize("count", ["3", "200000"])
def test_printing_through_ui_into_a_dead_reader_is_141(count: str, streams: Streams) -> None:
    done = run(small("lines", count), stdout=streams.dead())
    assert done.code == 141
    no_traceback(done)


@pytest.mark.parametrize("code", [1, 12, 0])
def test_a_command_exit_keeps_its_code_with_both_readers_gone(code: int, streams: Streams) -> None:
    assert run(small("exit", str(code)), stdout=streams.dead(), stderr=streams.dead()).code == code


# --- a full disk ---


@linux_only
def test_a_commands_output_onto_dev_full_is_5(streams: Streams) -> None:
    done = run(small("lines", "3"), stdout=streams.file("/dev/full"))
    assert done.code == 5
    assert "cannot write output" in (done.stderr or "")
    no_traceback(done)


@linux_only
def test_help_onto_dev_full_is_5(streams: Streams) -> None:
    done = run([*TLAUP, "--help"], stdout=streams.file("/dev/full"))
    assert done.code == 5
    no_traceback(done)


@linux_only
def test_unknown_option_with_stderr_onto_dev_full_is_5(streams: Streams) -> None:
    assert run([*TLAUP, "--nosuch"], stderr=streams.file("/dev/full")).code == 5


@linux_only
def test_a_domain_error_with_stderr_onto_dev_full_keeps_its_code(streams: Streams) -> None:
    assert run(small("domain-error"), stderr=streams.file("/dev/full")).code == 3


# --- SIGINT while the reader is alive and not reading ---


@pytest.mark.parametrize("both", [False, True], ids=["stdout alone", "both streams"])
def test_sigint_while_the_reader_does_not_read_is_130(both: bool) -> None:
    read, write = os.pipe()
    try:
        with subprocess.Popen(
            small("forever"),
            stdin=subprocess.DEVNULL,
            stdout=write,
            stderr=write if both else subprocess.PIPE,
            preexec_fn=_default_sigint,  # noqa: PLW1509 - test code: the child must see SIGINT (01 T5)
        ) as child:
            os.close(write)
            write = -1
            ready, _, _ = select.select([read], [], [], TIMEOUT)  # the command has begun printing
            assert ready, "the child printed nothing"
            child.send_signal(signal.SIGINT)
            _, err = child.communicate(timeout=TIMEOUT)
            code = child.returncode
    finally:
        os.close(read)
        if write != -1:
            os.close(write)
    assert code == 130
    if not both:
        assert "Traceback" not in err.decode(), err.decode()


# --- two calls of run_app in one process ---


def test_the_second_run_app_in_a_process_is_judged_afresh(streams: Streams) -> None:
    assert run(small("twice"), stdout=streams.dead()).code == 141


# --- the installed command (preserved-behaviour row P1) ---


def test_version_is_the_same_from_python_m_and_the_console_script_row_p1() -> None:
    script = Path(sys.executable).parent / ("tlaup.exe" if os.name == "nt" else "tlaup")
    assert script.is_file(), f"no console script named tlaup beside {sys.executable}"
    by_module = run([*TLAUP, "--version"])
    by_script = run([str(script), "--version"])
    assert by_module.code == by_script.code == 0
    assert by_module.stdout == by_script.stdout
    assert (by_module.stdout or "").startswith("tlaup ")
