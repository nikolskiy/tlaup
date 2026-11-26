"""The `cache` group (design 23 C1, 11 R6): `dir`, `list` and `clean`.

Each command parses its arguments, calls the run-folder functions of `tlaup.tlc.rundirs` and prints through the
context's `Ui`. No network, no Java and no settings: only `AppPaths` is read. Installed tools and modules, which
live under the cache folder until milestone 3, are never touched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from tlaup.errors import ConflictingOptions

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime
    from pathlib import Path

    from tlaup.context import AppContext
    from tlaup.paths import AppPaths
    from tlaup.tlc.rundirs import RunRecord

GROUP_HELP = "Show and clean what tlaup keeps in its cache folder: run folders, remembered lookups, the Java check."
DIR_HELP = "Print the cache folder, whether or not it exists."
LIST_HELP = (
    "List the run folders: id, spec, build, when it started and last changed, size, whether it is in use, "
    "whether it is kept and why, and whether its checkpoint is complete; then the total of the kept ones."
)
CLEAN_HELP = (
    "Remove what nothing will use again: run folders that no run holds and that are not kept, and the "
    "remembered GitHub lookups. A kept run folder, and one that asked to be kept and holds a complete checkpoint, "
    "stay unless --all or its RUN_ID says so. A run folder in use is never removed. "
    "It never touches installed tools or modules."
)
RUN_ID_HELP = "Remove this one run folder, kept or not, if no run holds it (`cache list` shows the ids)."
RUNS_HELP = "Clean run folders only (and their stale lock files)."
REMOTE_HELP = "Clean the remembered GitHub lookups only."
ALL_HELP = (
    "Widen what is cleaned: with --runs, kept and resumable run folders too; with --remote, no change; "
    "with no kind named, both of those and the remembered Java check."
)

NOTHING_REMOVED = "nothing was removed"

app = typer.Typer(name="cache", help=GROUP_HELP, no_args_is_help=True)


# ---------------------------------------------------------------------- cache dir


def dir_command(ctx: typer.Context) -> None:
    app_context: AppContext = ctx.find_root().obj
    app_context.ui.result(str(app_context.paths.cache))


# ---------------------------------------------------------------------- cache list


def _time(moment: datetime | None) -> str:
    """F8's form for a time: `2026-11-15 10:00 UTC`."""
    from datetime import UTC

    return "-" if moment is None else f"{moment.astimezone(UTC):%Y-%m-%d %H:%M} UTC"


def _shown_kept(record: RunRecord) -> bool:
    """What the list shows as kept: a kept folder, and an unsettled resumable one; the total counts the same."""
    return record.kept or record.reason is not None


def _state(record: RunRecord) -> str:
    """`in use`, whether it is kept and why, and the checkpoint, in words."""
    parts: list[str] = []
    if record.in_use:
        parts.append("in use")
    if record.cannot_lock:
        parts.append("lock file unreadable")
    if not record.has_run_json:
        parts.append("no run.json")
        return ", ".join(parts)
    if _shown_kept(record):
        parts.append(f"kept: {record.reason}" if record.reason else "kept")
    else:
        parts.append("not kept")
    parts.append("checkpoint complete" if record.checkpoint_complete else "checkpoint incomplete")
    return ", ".join(parts)


def render_runs(records: Sequence[RunRecord]) -> list[str]:
    """The lines of `cache list`: one per record, oldest first, then the total of the kept ones; none for none."""
    from pathlib import PurePath

    from tlaup.tlc.rundirs import format_size

    if not records:
        return []
    ordered = sorted(records, key=lambda record: (record.started or record.last_change, record.run_id))
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for record in ordered:
        files = " ".join(PurePath(name).name for name in (record.spec, record.cfg) if name) or "-"
        started = f"started {_time(record.started)}" if record.started is not None else ""
        rows.append(
            (
                record.run_id,
                files,
                record.build or "-",
                started,
                f"changed {_time(record.last_change)}",
                format_size(record.size),
                _state(record),
            )
        )
    widths = [max(len(row[column]) for row in rows) for column in range(6)]
    lines = []
    for row in rows:
        cells = [row[0].ljust(widths[0]), row[1].ljust(widths[1]), row[2].ljust(widths[2])]
        cells += [row[3].ljust(widths[3]), row[4].ljust(widths[4]), row[5].rjust(widths[5]), row[6]]
        lines.append("  ".join(cells).rstrip())
    kept = [record for record in records if _shown_kept(record)]
    total = format_size(sum(record.size for record in kept))
    noun = "folder holds" if len(kept) == 1 else "folders hold"
    lines.append(f"{len(kept)} kept run {noun} {total}")
    return lines


def list_command(ctx: typer.Context) -> None:
    app_context: AppContext = ctx.find_root().obj
    from tlaup.tlc.rundirs import list_runs

    lines = render_runs(list_runs(app_context.paths))
    if lines:
        app_context.ui.result("\n".join(lines))


# ---------------------------------------------------------------------- cache clean


def _file_error(action: str, path: Path, error: OSError) -> Exception:
    from tlaup.errors import FileOperationError

    return FileOperationError(f"cannot {action} {path}: {error.strerror or error}")


def _tree_bytes(path: Path) -> int:
    """Bytes of the files under ``path``, symbolic links counted as themselves and never followed."""
    import os

    total = 0
    for folder, _, names in os.walk(path, followlinks=False):
        for name in names:
            try:
                total += os.lstat(os.path.join(folder, name)).st_size  # noqa: PTH118
            except OSError:
                continue
    return total


def _remove_entry(entry: Path) -> int:
    """Remove one file, link or folder; a link is removed as a link, never followed. Returns the bytes freed."""
    import shutil

    try:
        info = entry.lstat()
    except FileNotFoundError:
        return 0  # a lookup written and renamed away at this moment
    except OSError as error:
        raise _file_error("read", entry, error) from error
    try:
        if entry.is_symlink() or not entry.is_dir():
            entry.unlink(missing_ok=True)
            return info.st_size
        size = _tree_bytes(entry)
        shutil.rmtree(entry)
    except FileNotFoundError:
        return 0
    except OSError as error:
        raise _file_error("remove", entry, error) from error
    return size


def clear_remote(paths: AppPaths) -> tuple[int, int]:
    """Empty ``<cache>/remote/`` entry by entry (V8), temporary files included; the folder itself stays.

    Returns the number of entries removed and their bytes. A ``remote`` that is itself a link is not followed:
    it is `FileOperationError`.
    """
    from tlaup.errors import FileOperationError

    folder = paths.remote
    if folder.is_symlink():
        message = f"{folder} is a symbolic link; not following it"
        raise FileOperationError(message)
    try:
        entries = list(folder.iterdir())
    except FileNotFoundError:
        return 0, 0
    except OSError as error:
        raise _file_error("read", folder, error) from error
    count = size = 0
    for entry in entries:
        freed = _remove_entry(entry)
        count += 1
        size += freed
    return count, size


def clear_java_check(paths: AppPaths) -> int | None:
    """Remove ``<cache>/java.json`` (J3). Returns its bytes, or None when there was none."""
    path = paths.java_cache
    try:
        size = path.lstat().st_size
        path.unlink()  # a link is removed as a link; a folder of that name is an error, not removed
    except FileNotFoundError:
        return None
    except OSError as error:
        raise _file_error("remove", path, error) from error
    return size


def _clean_kinds(app_context: AppContext, *, runs: bool, remote: bool, all_kinds: bool) -> tuple[int, bool]:
    """The kinds C1 names: no kind given is both run folders and lookups; `--all` widens the run folders and, with
    no kind named, adds the Java check. Returns the bytes freed and whether anything was removed."""
    from tlaup.cmd.tool._shared import utc_now
    from tlaup.tlc.rundirs import clean_lock_files, clean_runs

    paths, ui = app_context.paths, app_context.ui
    freed = 0
    removed_any = False
    if runs or not remote:
        report = clean_runs(paths, include_kept=all_kinds)
        locks = clean_lock_files(paths, utc_now)
        for name in report.removed:
            ui.note(f"removed run folder {name}")
        for name in report.in_use:
            ui.note(f"left run folder {name}: in use by another tlaup run")
        for name in report.cannot_lock:
            ui.note(f"left run folder {name}: its lock file cannot be opened")
        if locks:
            ui.note(f"removed {locks} stale lock file{'' if locks == 1 else 's'}")
        freed += report.freed
        removed_any = bool(report.removed or locks)
    if remote or not runs:
        count, size = clear_remote(paths)
        if count:
            ui.note("removed the remembered GitHub lookups")
            freed += size
            removed_any = True
    if all_kinds and not runs and not remote:  # C1: the Java check belongs to neither kind
        size_or_none = clear_java_check(paths)
        if size_or_none is not None:
            ui.note("removed the remembered Java check")
            freed += size_or_none
            removed_any = True
    return freed, removed_any


def clean_command(
    ctx: typer.Context,
    run_id: Annotated[str | None, typer.Argument(metavar="RUN_ID", help=RUN_ID_HELP, show_default=False)] = None,
    runs: bool = typer.Option(False, "--runs", help=RUNS_HELP),
    remote: bool = typer.Option(False, "--remote", help=REMOTE_HELP),
    all_kinds: bool = typer.Option(False, "--all", help=ALL_HELP),
) -> None:
    app_context: AppContext = ctx.find_root().obj
    if run_id is not None and (runs or remote or all_kinds):
        option = "--runs" if runs else "--remote" if remote else "--all"
        message = f"a run id cannot be given with {option}"
        raise ConflictingOptions(message, hint="`cache clean RUN_ID` removes that one run folder and nothing else")
    from tlaup.tlc.rundirs import clean_runs, format_size

    if run_id is not None:
        report = clean_runs(app_context.paths, include_kept=True, run_id=run_id)
        for name in report.removed:
            app_context.ui.note(f"removed run folder {name}")
        freed, removed_any = report.freed, bool(report.removed)
    else:
        freed, removed_any = _clean_kinds(app_context, runs=runs, remote=remote, all_kinds=all_kinds)
    app_context.ui.note(f"freed {format_size(freed)}" if removed_any else NOTHING_REMOVED)


app.command(name="dir", help=DIR_HELP)(dir_command)
app.command(name="list", help=LIST_HELP)(list_command)
app.command(name="clean", help=CLEAN_HELP)(clean_command)
