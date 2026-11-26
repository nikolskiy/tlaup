"""The editor of `tlaup config edit` (design 14 F5): which command to run, and running it on the config file.

Domain code: returns values or raises `TlaupError`, prints nothing.
"""

import contextlib
import os
import shlex
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence

from tlaup.config.loader import CONFIG_HEADER, LoadedSettings, load_settings
from tlaup.errors import Failed, FileOperationError, NotSetUp, ToolStartError
from tlaup.paths import AppPaths

_VARIABLES = ("VISUAL", "EDITOR")
_DEFAULTS_WINDOWS = ("notepad",)
_DEFAULTS_ELSEWHERE = ("sensible-editor", "nano", "vi")
_SET_EDITOR = "set EDITOR to the editor to use, with the flag that makes it wait, such as EDITOR='code --wait'"


def editor_command(
    env: Mapping[str, str],
    *,
    os_name: str = os.name,
    which: Callable[[str], str | None] = shutil.which,
) -> list[str]:
    """`$VISUAL`, else `$EDITOR` (an empty value counts as unset), else the first default found, as an argument list.

    The value is split like a shell would split it, and its first word is resolved with `which`. `os_name` and
    `which` are arguments so the default order can be tested on every system.
    """
    for name in _VARIABLES:
        value = env.get(name, "")
        try:
            words = shlex.split(value)
        except ValueError as e:
            raise NotSetUp(f"{name} cannot be read as a command: {e}", hint=_SET_EDITOR) from None  # noqa: TRY003
        if not words:
            continue
        program = which(words[0])
        if program is None:
            raise NotSetUp(  # noqa: TRY003
                f'{name} names "{words[0]}", which was not found on PATH',
                hint=f"install it, or {_SET_EDITOR}",
            )
        return [program, *words[1:]]
    for default in _DEFAULTS_WINDOWS if os_name == "nt" else _DEFAULTS_ELSEWHERE:
        program = which(default)
        if program is not None:
            return [program]
    raise NotSetUp("no editor was found", hint=_SET_EDITOR)  # noqa: TRY003


def _holds_only_the_header(paths: AppPaths) -> bool:
    try:
        return paths.config_file.read_text(encoding="utf-8").strip() == CONFIG_HEADER
    except (OSError, UnicodeDecodeError):
        return False


def edit_file(paths: AppPaths, env: Mapping[str, str], argv: Sequence[str]) -> LoadedSettings:
    """Run `argv` with the config file as its last argument, wait, and check the file afterwards.

    A file that is not there is created first holding only the header comment, and a file that still holds only that
    is removed again, so that opening the editor and quitting writes nothing. A non-zero exit is `Failed`; a file
    that is invalid afterwards is `ConfigInvalid` and stays as saved.
    """
    path = paths.config_file
    if not path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(CONFIG_HEADER + "\n", encoding="utf-8")
        except OSError as e:
            raise FileOperationError(f"cannot write {path}: {e.strerror or e}") from None  # noqa: TRY003
    try:
        try:
            done = subprocess.run([*argv, str(path)], check=False)
        except OSError as e:
            raise ToolStartError(f"cannot start the editor {argv[0]}: {e.strerror or e}") from None  # noqa: TRY003
    finally:
        if _holds_only_the_header(paths):
            with contextlib.suppress(OSError):
                path.unlink()
    if done.returncode != 0:
        raise Failed(f"the editor exited with code {done.returncode}")  # noqa: TRY003
    return load_settings(paths, env)
