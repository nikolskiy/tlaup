"""Project root discovery (design 11 R10) and the folder names it uses."""

import os
from pathlib import Path

SPEC_DIR = "spec"
MODULES_DIR = "modules"
CLASSES_DIR = "classes"
LIB_DIR = "lib"

# A spec in a folder with one of these names may have its project root in the parent folder.
SPEC_FOLDER_NAMES = (SPEC_DIR, "specs", "test", "tests")


def _has_marker(directory: Path) -> bool:
    return any((directory / name).is_dir() for name in (MODULES_DIR, CLASSES_DIR, LIB_DIR))


def _is_home_or_filesystem_root(directory: Path, home: Path) -> bool:
    # By file identity, so that a home folder reached through a link is still refused.
    if directory.parent == directory or directory.resolve().parent == directory.resolve():
        return True
    try:
        return os.path.samefile(directory, home)
    except OSError:
        return directory == home


def find_project_root(spec: Path, home: Path) -> Path | None:
    """Return the project root of a spec, or None.

    1. The spec's own folder, if it holds `modules/`, `classes/` or `lib/`.
    2. Otherwise its parent folder, if that holds one of them and the spec's folder is named `spec`, `specs`,
       `test` or `tests`.
    3. Never the home folder or a filesystem root.
    The folder returned is built from the path as given; no link is resolved.
    """
    folder = spec.parent
    candidates = [folder]
    if folder.name in SPEC_FOLDER_NAMES:
        candidates.append(folder.parent)
    for candidate in candidates:
        if _has_marker(candidate) and not _is_home_or_filesystem_root(candidate, home):
            return candidate
    return None
