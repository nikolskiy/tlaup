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


def _tried(paths: list[Path]) -> str:
    return "tried:\n" + "\n".join(f"  {path}" for path in paths)


def _collapse(path: Path) -> Path:
    # R4 step 3 needs `..` collapsed as text, without touching the disk or following a link; Path has no such method.
    return Path(os.path.abspath(path))  # noqa: PTH100


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.samefile(b)
    except OSError:
        return False


def _absolute_form(path: Path, *, platform: str) -> Path | None:
    """The path with `..` removed as text when that names the same file, else as it is (None on Windows)."""
    textual = _collapse(path)
    if ".." not in path.parts or _same_file(textual, path):
        return textual
    return None if _is_windows(platform) else path


def resolve_spec(text: str, cwd: Path, *, platform: str = sys.platform) -> Path:
    """Find the spec file named by `text` (design 11 R5). The result is absolute, ends in `.tla` and is a file."""
    if text in ("", ".", ".."):
        raise UsageError("SPEC must be a TLA+ file or its name")  # noqa: TRY003
    typed = cwd / text  # an absolute text replaces cwd
    if text.endswith(_TLA):
        candidates = [typed]
    else:
        base = typed  # Path drops a trailing separator
        candidates = [base.parent / (base.name + _TLA), base.parent / SPEC_DIR / (base.name + _TLA)]
    for candidate in candidates:
        if candidate.is_file():
            found = _absolute_form(candidate, platform=platform)
            if found is None:
                break
            return found
    if not text.endswith(_TLA) and typed.is_dir():
        raise UsageError(f"SPEC is a folder: {text}", hint="name a .tla file or the spec's name")  # noqa: TRY003
    hint = None
    if typed.is_file():
        sibling = typed.with_suffix(_TLA)
        if sibling.is_file():
            hint = f"did you mean {sibling.name}?"
    raise SpecNotFound(f"spec not found: {text}", hint=hint, details=_tried(candidates))  # noqa: TRY003


def resolve_cfg(text: str, spec: Path, cwd: Path, project_root: Path | None) -> Path:
    """Find the cfg file named by `--cfg` (design 11 R4 step 5): only a name ending in `.cfg` is tried.

    An absolute name is tried alone; otherwise beside the spec, in the working folder, then in the project root.
    The path returned keeps any `..` as typed, because `config_arg` needs the path the operating system reads.
    """
    if text == "":
        raise UsageError("--cfg needs a file name")  # noqa: TRY003
    name = text if text.endswith(_CFG) else text + _CFG
    if Path(name).is_absolute():
        candidates = [Path(name)]
    else:
        folders = [spec.parent, cwd]
        if project_root is not None:
            folders.append(project_root)
        candidates = []
        seen: list[Path] = []
        for folder in folders:
            if any(_collapse(folder) == s or _same_file(folder, s) for s in seen):
                continue
            seen.append(_collapse(folder))
            candidates.append(folder / name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise CfgNotFound(f"cfg not found: {text}", details=_tried(candidates))  # noqa: TRY003


def config_arg(cfg: Path, spec: Path, *, platform: str = sys.platform) -> str:
    """The text given to TLC as `-config`: the cfg relative to the spec's folder (design 11 R4 step 4)."""
    if _is_windows(platform):
        try:
            return os.path.relpath(_collapse(cfg), _collapse(spec.parent))
        except ValueError:  # another drive
            return str(_collapse(cfg))
    return os.path.relpath(cfg.resolve(), spec.parent.resolve())
