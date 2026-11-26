"""Turn what the user typed into the paths of a run (design 11 R4 steps 3 to 5, and R5).

The functions print nothing and read no environment: the working folder is an argument. Links are never resolved
in a spec path, because TLC never resolves them; only `config_arg` resolves them, to name the file TLC will open.
"""

import os
import sys
from pathlib import Path

from tlaup.errors import CfgNotFound, SpecNotFound, UsageError
from tlaup.project.core import SPEC_DIR

_TLA = ".tla"
_CFG = ".cfg"


def _is_windows(platform: str) -> bool:
    return platform.startswith("win")


def _tried(paths: list[str]) -> str:
    return "tried:\n" + "\n".join(f"  {path}" for path in paths)


def _same_file(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _absolute_form(path: str, *, platform: str) -> str | None:
    """The path with `..` removed as text when that names the same file, else as it is (None on Windows)."""
    if ".." not in path.replace("\\", "/").split("/"):
        return os.path.abspath(path)
    textual = os.path.abspath(path)
    if _same_file(textual, path):
        return textual
    return None if _is_windows(platform) else path


def resolve_spec(text: str, cwd: Path, *, platform: str = sys.platform) -> Path:
    """Find the spec file named by `text` (design 11 R5). The result is absolute, ends in `.tla` and is a file."""
    if text in ("", ".", ".."):
        raise UsageError("SPEC must be a TLA+ file or its name")  # noqa: TRY003
    typed = os.path.join(cwd, text)
    if text.endswith(_TLA):
        candidates = [typed]
    else:
        base = typed.rstrip("/\\") or typed
        parent, name = os.path.split(base)
        candidates = [base + _TLA, os.path.join(parent, SPEC_DIR, name + _TLA)]
    for candidate in candidates:
        if os.path.isfile(candidate):
            found = _absolute_form(candidate, platform=platform)
            if found is None:
                break
            return Path(found)
    if not text.endswith(_TLA) and os.path.isdir(typed):
        raise UsageError(f"SPEC is a folder: {text}", hint="name a .tla file or the spec's name")  # noqa: TRY003
    hint = None
    if os.path.isfile(typed):
        sibling = os.path.splitext(typed)[0] + _TLA
        if os.path.isfile(sibling):
            hint = f"did you mean {os.path.basename(sibling)}?"
    raise SpecNotFound(f"spec not found: {text}", hint=hint, details=_tried(candidates))  # noqa: TRY003


def resolve_cfg(text: str, spec: Path, cwd: Path, project_root: Path | None) -> Path:
    """Find the cfg file named by `--cfg` (design 11 R4 step 5): only a name ending in `.cfg` is tried.

    An absolute name is tried alone; otherwise beside the spec, in the working folder, then in the project root.
    The path returned keeps any `..` as typed, because `config_arg` needs the path the operating system reads.
    """
    if text == "":
        raise UsageError("--cfg needs a file name")  # noqa: TRY003
    name = text if text.endswith(_CFG) else text + _CFG
    if os.path.isabs(name):
        candidates = [name]
    else:
        folders = [str(spec.parent), str(cwd)]
        if project_root is not None:
            folders.append(str(project_root))
        candidates = []
        seen: list[str] = []
        for folder in folders:
            if any(os.path.abspath(folder) == s or _same_file(folder, s) for s in seen):
                continue
            seen.append(os.path.abspath(folder))
            candidates.append(os.path.join(folder, name))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return Path(candidate)
    raise CfgNotFound(f"cfg not found: {text}", details=_tried(candidates))  # noqa: TRY003


def config_arg(cfg: Path, spec: Path, *, platform: str = sys.platform) -> str:
    """The text given to TLC as `-config`: the cfg relative to the spec's folder (design 11 R4 step 4)."""
    if _is_windows(platform):
        try:
            return os.path.relpath(os.path.abspath(cfg), os.path.abspath(spec.parent))
        except ValueError:  # another drive
            return os.path.abspath(cfg)
    return os.path.relpath(os.path.realpath(cfg), os.path.realpath(spec.parent))
