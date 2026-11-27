"""The fake ``javac`` (design 01 T4, package 03's contract).

Answers ``-version``, copies prepared class files for the sources it is given into the ``-d``
folder, or prints a recorded compiler error and exits 1. Standard library only.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tests.fakes import _fakelib
from tests.fakes._fakelib import CLASSES_DIR, JAVAC_ERRORS_DIR, Log, ScriptError

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_VERSION = "25.0.5"
VALUE_OPTIONS = frozenset(
    {
        "-d",
        "-cp",
        "-classpath",
        "--class-path",
        "-sourcepath",
        "--source-path",
        "--release",
        "-source",
        "-target",
        "-encoding",
        "-processorpath",
    }
)
NO_CLASS_EXIT = 2


def read_args(args: list[str]) -> tuple[Path | None, list[Path]]:
    """The ``-d`` folder and the ``.java`` sources among the arguments."""
    dest: Path | None = None
    sources: list[Path] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in VALUE_OPTIONS:
            if arg == "-d" and i + 1 < len(args):
                dest = Path(args[i + 1])
            i += 2
            continue
        if arg.endswith(".java"):
            sources.append(Path(arg))
        i += 1
    return dest, sources


def prepared_classes(classes: Path, source: Path) -> list[Path]:
    stem = source.stem
    found = [*classes.rglob(f"{stem}.class"), *classes.rglob(f"{stem}$*.class")]
    return sorted(found)


def act(script: Mapping[str, Any], log: Log) -> int:
    args = sys.argv[1:]
    log.write("start", **_fakelib.start_fields())
    _fakelib.sleep_ms(script.get("delay_ms"))
    if "-version" in args:
        sys.stdout.write(f"javac {script.get('version', DEFAULT_VERSION)}\n")
        sys.stdout.flush()
        return 0
    fail_with = script.get("fail_with")
    if fail_with is not None:
        error = _fakelib.text_or_file(fail_with, JAVAC_ERRORS_DIR) or b""
        sys.stderr.buffer.write(error)
        sys.stderr.buffer.flush()
        return 1
    dest, sources = read_args(args)
    if dest is None:
        # Written by stage 4: tlaup always passes -d, so a compile without it fails loudly (127).
        message = "no -d folder among the arguments"
        raise ScriptError(message)
    classes = Path(script.get("classes") or CLASSES_DIR)
    copies: list[tuple[Path, Path]] = []
    for source in sources:
        found = prepared_classes(classes, source)
        if not found:
            _fakelib.say(f"fake javac: no prepared class for {source.name}")
            return NO_CLASS_EXIT
        copies.extend((path, dest / path.relative_to(classes)) for path in found)
    for path, target in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return 0


def main(baked: str | None = None) -> int:
    return _fakelib.run_tool("javac", baked, act)


if __name__ == "__main__":
    sys.exit(main())
