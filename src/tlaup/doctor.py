"""The checks behind `tlaup doctor` (design 23 C1): one `Check` per thing a run depends on.

Nothing here prints, and no check raises a `TlaupError`: each failure becomes a `Check`, so one fault does not hide
the next. The one thing written is the remembered Java check (`java.json`), through `require_java(refresh=True)`.
"""

from __future__ import annotations

import hashlib
import importlib.resources
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import yaml

from tlaup.config.loader import Layer, load_settings, merge_layers
from tlaup.errors import (
    ConfigInvalid,
    Failed,
    FileOperationError,
    InvalidName,
    JavacNotFound,
    JavaNotFound,
    JavaTooOld,
    PinnedBuildMissing,
    TlaupError,
)
from tlaup.java.locate import JavaRuntime, ask_version, require_java, require_javac
from tlaup.modules.registry import LOCK as MODULE_LOCK
from tlaup.modules.registry import RECORD as MODULE_RECORD
from tlaup.modules.registry import TMP as MODULE_TMP
from tlaup.modules.registry import Registry, validate_module_name
from tlaup.versioning.github import token_from_env
from tlaup.versioning.spec import format_build
from tlaup.versioning.store import Build, ToolStore

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from tlaup.config.schema import Settings
    from tlaup.java.locate import AskVersion
    from tlaup.paths import AppPaths

Level = Literal["ok", "warning", "error"]

TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN")
CHUNK = 1 << 20
DOCTOR_SUFFIX = ", or run `tlaup doctor`"  # 20's hint for a version check that timed out; pointless here
NOT_WRITABLE_HINT = "make the folder writable, or point TLAUP_HOME (or the folder's own variable) elsewhere"


@dataclass(frozen=True)
class Check:
    name: str
    level: Level
    detail: str  # one line: what was found
    hint: str | None = None  # the next command, for a warning or an error


def _line(text: str | None) -> str:
    """A message on one line: its own lines joined."""
    return " ".join((text or "").split())


def _failure(error: TlaupError) -> str:
    """An error's message with its details (what a tool printed, a JAVA_HOME note), on one line."""
    return _line(f"{error.message}: {error.details}" if error.details else error.message)


# ---- folders --------------------------------------------------------------------------------------------------


def _nearest_existing(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _writable(path: Path) -> tuple[bool, str]:
    """Whether a run could write `path`, and the words for it; a missing folder counts by its nearest parent."""
    if path.exists():
        if not path.is_dir():
            return False, f"{path} (exists, but is not a folder)"
        ok = os.access(path, os.W_OK | os.X_OK)
        return ok, f"{path} (exists, {'writable' if ok else 'not writable'})"
    parent = _nearest_existing(path)
    ok = parent.is_dir() and os.access(parent, os.W_OK | os.X_OK)
    return ok, f"{path} (not there yet; {'its nearest existing parent is writable' if ok else 'no parent is writable'})"


def _folder(name: str, path: Path, failure: Level) -> Check:
    ok, detail = _writable(path)
    if ok:
        return Check(name, "ok", detail)
    return Check(name, failure, detail, NOT_WRITABLE_HINT)


# ---- Java -----------------------------------------------------------------------------------------------------


def _packaged_settings() -> Settings:
    """The packaged defaults alone: what the Java checks use when the config does not load."""
    text = importlib.resources.files("tlaup.resources").joinpath("default_config.yaml").read_text(encoding="utf-8")
    return merge_layers([Layer("defaults", yaml.safe_load(text), {})]).settings


def _runtime_detail(runtime: JavaRuntime) -> str:
    version = runtime.version if runtime.version is not None else "version not known"
    detail = f"{version} at {runtime.tool.path} (from {runtime.tool.source})"
    if runtime.warnings:
        detail += "; " + "; ".join(_line(warning) for warning in runtime.warnings)
    return detail


def _java_check(  # noqa: PLR0913, PLR0917
    name: Literal["java", "javac"], env: Mapping[str, str], paths: AppPaths, minimum: int, ask: AskVersion, note: str
) -> Check:
    require = require_java if name == "java" else require_javac
    failure: Level = "error" if name == "java" else "warning"
    try:
        runtime = require(env, min_version=minimum, cache_file=paths.java_cache, ask_version=ask, refresh=True)
    except (JavaNotFound, JavacNotFound, JavaTooOld, Failed) as error:
        hint = None if error.hint is None else error.hint.removesuffix(DOCTOR_SUFFIX)
        return Check(name, failure, _failure(error) + note, hint)
    level: Level = "warning" if runtime.warnings else "ok"
    hint = "check JAVA_HOME and PATH, then run `tlaup doctor` again" if level == "warning" else None
    return Check(name, level, _runtime_detail(runtime) + note, hint)


# ---- the pinned build -----------------------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned_check(store: ToolStore) -> Check:
    name = "pinned build"
    try:
        build = store.pinned()
        if build is None:
            if store.builds():
                return Check(name, "error", "nothing is pinned", "run `tlaup tool pin <version>`")
            return Check(name, "error", "nothing is pinned and no build is installed", "run `tlaup tool install`")
        return _verify(store, build)
    except PinnedBuildMissing as error:
        return Check(name, "error", _failure(error), error.hint)
    except FileOperationError as error:
        return Check(name, "error", _failure(error))


def _verify(store: ToolStore, build: Build) -> Check:
    name = "pinned build"
    shown = format_build(build, store.builds())
    try:
        actual = _sha256(build.jar)
    except OSError as error:
        detail = f"{shown}: cannot read {build.jar}: {error.strerror or error}"
        return Check(name, "error", detail, f"run `tlaup tool install --force {shown}`")
    if actual != build.sha256:
        detail = f"{shown}: the jar {build.jar} does not match its recorded SHA-256 (damaged or changed)"
        return Check(name, "error", detail, f"run `tlaup tool install --force {shown}`")
    return Check(name, "ok", f"{shown} at {build.jar}")


# ---- folders with contents ------------------------------------------------------------------------------------


def _tool_folder_check(paths: AppPaths, store: ToolStore) -> Check:
    name = "tool folder"
    ok, detail = _writable(paths.tools)
    try:
        leftovers = store.leftovers()
    except FileOperationError as error:
        return Check(name, "error", f"{detail}; {_failure(error)}")
    if leftovers:
        detail += "; not a build (tlaup never removes them): " + ", ".join(entry.name for entry in leftovers)
    if not ok:
        return Check(name, "error", detail, NOT_WRITABLE_HINT)
    if leftovers:
        return Check(name, "warning", detail, "delete them by hand if they are not needed; a newer tlaup may own them")
    return Check(name, "ok", detail)


def _module_problem(entry: Path) -> str:
    try:
        validate_module_name(entry.name)
    except InvalidName:
        return "not a valid module name"
    if not entry.is_dir():
        return "not a module: a file"
    return f"not a module: no readable {MODULE_RECORD}"


def _module_folder_check(paths: AppPaths, now: Callable[[], datetime]) -> Check:
    name = "module folder"
    ok, detail = _writable(paths.modules)
    registry = Registry(paths.modules, now=now)
    try:
        entries = sorted(paths.modules.iterdir(), key=lambda entry: entry.name)
    except FileNotFoundError:
        entries = []
    except OSError as error:
        return Check(name, "error", f"{detail}; cannot read it: {error.strerror or error}", NOT_WRITABLE_HINT)
    registered = {module.name for module in registry.list()}
    skipped = {MODULE_TMP, MODULE_LOCK}
    strays = [entry for entry in entries if entry.name not in registered and entry.name not in skipped]
    if strays:
        detail += "; not modules (tlaup never removes them): " + ", ".join(
            f"{entry.name} ({_module_problem(entry)})" for entry in strays
        )
    if not ok:
        return Check(name, "error", detail, NOT_WRITABLE_HINT)
    if strays:
        return Check(name, "warning", detail, "delete them by hand if they are not needed")
    return Check(name, "ok", detail)


# ---- the config file ------------------------------------------------------------------------------------------


def _config_check(paths: AppPaths, env: Mapping[str, str]) -> tuple[Check, Settings | None]:
    name = "config file"
    try:
        loaded = load_settings(paths, env)
    except ConfigInvalid as error:
        return Check(name, "error", _failure(error), error.hint), None
    except FileOperationError as error:
        return Check(name, "error", _failure(error)), None
    where = (
        str(paths.config_file) if paths.config_file.exists() else f"{paths.config_file}: not present (defaults in use)"
    )
    if loaded.warnings:
        detail = f"{where}; " + "; ".join(_line(warning) for warning in loaded.warnings)
        return Check(name, "warning", detail, "run `tlaup config edit`"), loaded.settings
    return Check(name, "ok", where), loaded.settings


# ---- the token ------------------------------------------------------------------------------------------------


def _token_check(env: Mapping[str, str]) -> Check:
    token = token_from_env(env)
    if token is None:
        return Check("GitHub token", "ok", "not set; GitHub allows 60 requests an hour without one")
    variable = next(variable for variable in TOKEN_VARIABLES if env.get(variable) == token)
    return Check("GitHub token", "ok", f"set (from {variable})")


# ---- all of them ----------------------------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(UTC)


def run_checks(
    paths: AppPaths,
    env: Mapping[str, str],
    *,
    ask_version: AskVersion = ask_version,
    now: Callable[[], datetime] = _utc_now,
) -> list[Check]:
    """Every check, in the order of the report; never raises a `TlaupError`."""
    config, settings = _config_check(paths, env)
    if settings is None:
        minimum = _packaged_settings().java.min_version
        note = f" (minimum {minimum}, the packaged default: the settings are invalid)"
    else:
        minimum, note = settings.java.min_version, ""
    store = ToolStore(paths, now=now)
    return [
        _java_check("java", env, paths, minimum, ask_version, note),
        _java_check("javac", env, paths, minimum, ask_version, note),
        _pinned_check(store),
        _tool_folder_check(paths, store),
        config,
        _module_folder_check(paths, now),
        _folder("config folder", paths.config, "warning"),
        _folder("cache folder", paths.cache, "error"),
        _folder("data folder", paths.data, "warning"),
        _folder("run folder", paths.runs, "error"),
        _token_check(env),
    ]
