"""How the standard streams stand: closed pipes, the null device, failed writes (design 14 F10).

The launcher polls `reader_gone(1)` and must not pull in Typer, so this module imports the standard library only.
"""

import errno
import os
import select
import stat
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

# A write to a stream that is already open failed for want of room or of a working device.
WRITE_ERRNOS: frozenset[int] = frozenset(
    code
    for code in (errno.ENOSPC, getattr(errno, "EDQUOT", None), errno.EFBIG, errno.EIO)
    if code is not None  # EDQUOT is missing on some systems
)

# The poll bits; select has none of them where poll does not exist (Windows). Linux and macOS share these values.
_POLLOUT: int = getattr(select, "POLLOUT", 0x004)
_POLLERR: int = getattr(select, "POLLERR", 0x008)
_POLLHUP: int = getattr(select, "POLLHUP", 0x010)
_POLLNVAL: int = getattr(select, "POLLNVAL", 0x020)


def is_pipe(fd: int) -> bool:
    """The descriptor is a pipe (a FIFO); false when it cannot be judged."""
    try:
        return stat.S_ISFIFO(os.fstat(fd).st_mode)
    except OSError:
        return False


def is_null_device(fd: int) -> bool:
    """The descriptor is the null device; false when it cannot be judged."""
    try:
        here = os.fstat(fd)
        null = Path(os.devnull).stat()
    except OSError:
        return False
    return (here.st_dev, here.st_ino) == (null.st_dev, null.st_ino)


def poll_says_gone(revents: int) -> bool:
    """`POLLERR` (Linux) or `POLLHUP` (macOS) means the reader has gone; `POLLNVAL` means nothing can be said."""
    if revents & _POLLNVAL:
        return False
    return bool(revents & (_POLLERR | _POLLHUP))


def reader_gone(fd: int) -> bool:
    """The descriptor is a pipe whose reader has gone; asked of `select.poll` with no wait, false where it is absent."""
    if not hasattr(select, "poll"):
        return False
    try:
        poller = select.poll()
        poller.register(fd, _POLLOUT)  # macOS reports nothing for an empty mask
        answer = poller.poll(0)
    except (OSError, ValueError):
        return False
    return any(poll_says_gone(revents) for _, revents in answer)


def silence(stream: TextIO) -> None:
    """Point the stream's descriptor at the null device, so later writes and flushes cannot fail."""
    try:
        fd = stream.fileno()
    except (AttributeError, ValueError, OSError):  # no descriptor: the in-process runner's streams
        return
    try:
        null = os.open(os.devnull, os.O_WRONLY)
    except OSError:
        return
    try:
        os.dup2(null, fd)
    except OSError:
        pass
    finally:
        os.close(null)


def closed_pipe_on_windows(e: OSError, *, os_name: str = os.name, pipe: Callable[[int], bool] = is_pipe) -> bool:
    """An `OSError(EINVAL)` with no file name while stdout or stderr is a pipe: how Windows shows a closed pipe
    (decision D57); nowhere else is it treated so."""
    return os_name == "nt" and e.errno == errno.EINVAL and e.filename is None and (pipe(1) or pipe(2))
