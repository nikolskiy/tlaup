"""The fake ``git`` (design 01 T4): prints a fixed short hash. Standard library only."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from tests.fakes import _fakelib

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tests.fakes._fakelib import Log

DEFAULT_STDOUT = "abc1234\n"


def act(script: Mapping[str, Any], log: Log) -> int:
    log.write("start", **_fakelib.start_fields())
    stdout = script.get("stdout", DEFAULT_STDOUT)
    sys.stdout.write(str(stdout or ""))
    sys.stdout.flush()
    return int(script.get("exit", 0))


def main(baked: str | None = None) -> int:
    return _fakelib.run_tool("git", baked, act)


if __name__ == "__main__":
    sys.exit(main())
