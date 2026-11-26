"""A hook into ``fcntl.flock`` for the second look of the run folders' locks (design 11 R6; package 35a).

It wraps the standard library's ``flock``, not tlaup's code (T12 rule 2): the test needs the holder of a lock
to remove its file and release in the instant between the waiter's ``open`` and its ``flock``, which no
interleaving from outside the call can reach.
"""

from __future__ import annotations

import fcntl
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def before_the_next_flock(monkeypatch: pytest.MonkeyPatch) -> Callable[[Callable[[], None]], None]:
    """``before_the_next_flock(action)``: run ``action`` once, just before the next exclusive flock."""

    def arm(action: Callable[[], None]) -> None:
        real = fcntl.flock
        armed = [True]

        def flock(fd: int, operation: int) -> None:
            if armed[0] and operation & fcntl.LOCK_EX:
                armed[0] = False
                action()
            real(fd, operation)

        monkeypatch.setattr(fcntl, "flock", flock)

    return arm
