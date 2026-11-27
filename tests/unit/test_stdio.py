"""The stream helpers (design 14 F10): pipes, the null device, the poll answer, Windows' closed pipe."""

import errno
import io
import os
import select
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from tlaup import stdio
from tlaup.stdio import (
    closed_pipe_on_windows,
    is_null_device,
    is_pipe,
    poll_says_gone,
    reader_gone,
    silence,
)

needs_poll = pytest.mark.skipif(not hasattr(select, "poll"), reason="select.poll does not exist here (Windows)")


class Pipe:
    def __init__(self) -> None:
        self.read, self.write = os.pipe()
        self._open = {self.read, self.write}

    def close_read(self) -> None:
        os.close(self.read)
        self._open.discard(self.read)

    def close(self) -> None:
        for fd in self._open:
            os.close(fd)


@pytest.fixture
def pipe() -> Iterator[Pipe]:
    made = Pipe()
    yield made
    made.close()


@pytest.mark.parametrize(
    ("revents", "gone"),
    [
        (stdio._POLLERR, True),
        (stdio._POLLHUP, True),
        (stdio._POLLOUT, False),
        (stdio._POLLNVAL, False),
    ],
    ids=["POLLERR", "POLLHUP", "POLLOUT alone", "POLLNVAL"],
)
def test_poll_says_gone(revents: int, gone: bool) -> None:
    assert poll_says_gone(revents) is gone


@needs_poll
def test_reader_gone_on_a_pipe_whose_reader_closed(pipe: Pipe) -> None:
    pipe.close_read()
    assert reader_gone(pipe.write) is True


@needs_poll
def test_reader_gone_is_false_while_the_reader_is_open(pipe: Pipe) -> None:
    assert reader_gone(pipe.write) is False


@needs_poll
def test_reader_gone_is_false_on_a_regular_file(tmp_path: Path) -> None:
    with (tmp_path / "out.txt").open("w") as f:
        assert reader_gone(f.fileno()) is False


def test_is_pipe_and_is_null_device_on_a_pipe(pipe: Pipe) -> None:
    assert is_pipe(pipe.write) is True
    assert is_null_device(pipe.write) is False


def test_is_pipe_and_is_null_device_on_a_file(tmp_path: Path) -> None:
    with (tmp_path / "out.txt").open("w") as f:
        assert is_pipe(f.fileno()) is False
        assert is_null_device(f.fileno()) is False


def test_is_pipe_and_is_null_device_on_the_null_device() -> None:
    with Path(os.devnull).open("w") as f:
        assert is_pipe(f.fileno()) is False
        assert is_null_device(f.fileno()) is True


def test_a_descriptor_that_is_not_open_is_neither(pipe: Pipe) -> None:
    closed = pipe.read
    pipe.close_read()
    assert is_pipe(closed) is False
    assert is_null_device(closed) is False


def _einval(filename: str | None = None) -> OSError:
    return OSError(errno.EINVAL, "Invalid argument", filename)


@pytest.mark.parametrize(
    ("os_name", "a_pipe", "expected"),
    [("nt", True, True), ("nt", False, False), ("posix", True, False), ("posix", False, False)],
)
def test_closed_pipe_on_windows(os_name: str, a_pipe: bool, expected: bool) -> None:
    assert closed_pipe_on_windows(_einval(), os_name=os_name, pipe=lambda _fd: a_pipe) is expected


def test_closed_pipe_on_windows_is_false_for_an_error_with_a_file_name() -> None:
    assert closed_pipe_on_windows(_einval("some-file"), os_name="nt", pipe=lambda _fd: True) is False


def test_closed_pipe_on_windows_is_false_for_another_error_number() -> None:
    error = OSError(errno.ENOSPC, "No space left on device")
    assert closed_pipe_on_windows(error, os_name="nt", pipe=lambda _fd: True) is False


def test_silence_on_a_stream_with_no_descriptor_does_nothing() -> None:
    stream = io.StringIO("kept")
    silence(stream)
    assert stream.getvalue() == "kept"


def test_silence_points_the_descriptor_at_the_null_device(tmp_path: Path) -> None:
    target = tmp_path / "out.txt"
    with target.open("w") as f:
        silence(f)
        assert is_null_device(f.fileno())
        f.write("dropped")
        f.flush()
    assert target.read_text() == ""


def test_write_errnos() -> None:
    assert {errno.ENOSPC, errno.EFBIG, errno.EIO} <= stdio.WRITE_ERRNOS
    assert errno.EPIPE not in stdio.WRITE_ERRNOS


def test_importing_stdio_loads_neither_typer_nor_rich() -> None:
    probe = (
        "import sys, tlaup.stdio\n"
        "loaded = sorted(m for m in sys.modules if m.split('.')[0] in ('typer', 'rich'))\n"
        "print(','.join(loaded))\n"
    )
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "", f"tlaup.stdio pulled in: {done.stdout.strip()}"
