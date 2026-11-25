"""The fake editor (design 01 T4): writes its text into the file it is given, or leaves it alone.

Standard library only.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tests.fakes import _fakelib
from tests.fakes._fakelib import Log, ScriptError

if TYPE_CHECKING:
    from collections.abc import Mapping


def act(script: Mapping[str, Any], log: Log) -> int:
    args = sys.argv[1:]
    log.write("start", **_fakelib.start_fields())
    text = script.get("write")
    if text is not None:
        if not args:
            message = "no file to write among the arguments"
            raise ScriptError(message)
        Path(args[-1]).write_bytes(str(text).encode("utf-8"))
    return int(script.get("exit", 0))


def main(baked: str | None = None) -> int:
    return _fakelib.run_tool("editor", baked, act)


if __name__ == "__main__":
    sys.exit(main())
