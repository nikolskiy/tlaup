"""Layered settings (design 14 F1): read the layers, merge them, validate once; `write_user_setting` writes."""

import contextlib
import importlib.resources
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from tlaup.config import schema
from tlaup.config.schema import REMOVED, Settings
from tlaup.context import get_context
from tlaup.errors import ConfigInvalid, FileOperationError
from tlaup.paths import AppPaths

CONFIG_HEADER = "# tlaup settings; see https://github.com/nikolskiy/tlaup/blob/main/docs/reference/configuration.md"

_USER_FILE = "config.yaml"
EDIT_HINT = "run `tlaup config edit` to fix the file"
_EMPTY_IS_UNSET = ("module_path", "module_lib_path")  # an empty variable means unset
_NOT_IN_ENV = "java.opts"  # TLAUP_JAVA_OPTS adds at run time instead (design 13 J1)
_KIND_LABELS = {"defaults": "default", "user": "user file", "project": "project file", "env": "environment"}
_KIND_FILES = {"defaults": "default_config.yaml", "user": _USER_FILE, "project": "project file"}


@dataclass(frozen=True)
class LoadedSettings:
    settings: Settings
    sources: dict[str, str]  # "tlc.workers" -> "default" | "user file" | "TLAUP_TLC_WORKERS" | "--workers"
    warnings: tuple[str, ...]  # unknown and removed keys


@dataclass(frozen=True)
class Layer:
    kind: str  # "defaults", "user", "project", "env" or "flags"
    data: Mapping[str, object]  # nested, as read
    labels: Mapping[str, str]  # dotted key -> what `sources` shows: "user file", ...


# --- reading ---------------------------------------------------------------------------------------------------


def _parse_yaml(text: str, name: str, *, hint: str | None) -> dict[str, object]:
    """Read YAML text with the safe loader into a mapping (empty for an empty file)."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f"line {mark.line + 1}, column {mark.column + 1}: " if mark is not None else ""
        problem = getattr(e, "problem", None) or "not valid YAML"
        raise ConfigInvalid(f"{name}: {where}{problem}", hint=hint) from None  # noqa: TRY003
    if data is None:
        return {}
    if not isinstance(data, dict) or not all(isinstance(k, str) for k in data):
        raise ConfigInvalid(f"{name}: expected a mapping of settings at the top level", hint=hint)  # noqa: TRY003
    return data


def _read_user_file(paths: AppPaths) -> dict[str, object] | None:
    path = paths.config_file
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        raise ConfigInvalid(f"{_USER_FILE}: not valid UTF-8 text", hint=EDIT_HINT) from None  # noqa: TRY003
    except OSError as e:
        raise FileOperationError(f"cannot read {path}: {e.strerror or e}") from None  # noqa: TRY003
    return _parse_yaml(text, _USER_FILE, hint=EDIT_HINT)


def _nest(flat: Mapping[str, object]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in flat.items():
        *parents, last = key.split(".")
        target = out
        for part in parents:
            target = target.setdefault(part, {})
        target[last] = value
    return out


def _env_layer(env: Mapping[str, str]) -> Layer:
    flat: dict[str, object] = {}
    labels: dict[str, str] = {}
    for key in schema.setting_keys():
        if key == _NOT_IN_ENV:
            continue
        variable = "TLAUP_" + key.replace(".", "_").upper()
        if variable not in env:
            continue
        text = env[variable]
        if schema.is_list_key(key):
            flat[key] = [item for item in (part.strip() for part in text.split(",")) if item]
        elif text == "" and key in _EMPTY_IS_UNSET:
            flat[key] = None
        else:
            flat[key] = text
        labels[key] = variable
    return Layer("env", _nest(flat), labels)


def _flags_layer(overrides: Mapping[str, object]) -> Layer:
    labels = {key: "--" + key.rsplit(".", 1)[-1].replace("_", "-") for key in overrides}
    return Layer("flags", _nest(overrides), labels)


def read_layers(paths: AppPaths, env: Mapping[str, str], overrides: Mapping[str, object] = {}) -> list[Layer]:
    """The four layers of the first wave, lowest first; raises `ConfigInvalid` for a file that does not parse."""
    packaged = importlib.resources.files("tlaup.resources").joinpath("default_config.yaml").read_text(encoding="utf-8")
    defaults = _parse_yaml(packaged, "default_config.yaml", hint=None)
    user = _read_user_file(paths)
    return [
        Layer("defaults", defaults, {}),
        Layer("user", user if user is not None else {}, {}),
        _env_layer(env),
        _flags_layer(overrides),
    ]


# --- merging ---------------------------------------------------------------------------------------------------


def _scan(layer: Layer) -> tuple[dict[str, object], list[str], list[str]]:
    """What a layer sets (dotted leaf keys), the removed names it holds, and its unknown-key warnings."""
    file = _KIND_FILES.get(layer.kind, layer.kind)
    removed: list[str] = []
    warnings: list[str] = []

    def walk(data: Mapping[str, object], node: dict[str, Any], prefix: str) -> dict[str, object]:
        out: dict[str, object] = {}
        for name, value in data.items():
            if not isinstance(name, str):
                edit = EDIT_HINT if layer.kind == "user" else None
                raise ConfigInvalid(f"{file}: {prefix}{name}: expected a setting name", hint=edit)  # noqa: TRY003
            key = prefix + name
            child = node.get(name, False)
            if key in REMOVED:
                removed.append(key)
            elif child is False:
                close = schema.closest_key(key)
                hint = f'; did you mean "{close}"?' if close else ""
                warnings.append(f'{file}: unknown key "{key}" (ignored){hint}')
            elif child is None:
                out[key] = value
            elif value is None:
                continue  # a section with every key commented out is an empty section
            elif not isinstance(value, Mapping):
                edit = EDIT_HINT if layer.kind == "user" else None
                got = schema.show(value)
                raise ConfigInvalid(f"{file}: {key}: expected a section of settings, got {got}", hint=edit)  # noqa: TRY003
            else:
                out.update(walk(value, child, f"{key}."))
        return out

    return walk(layer.data, schema.tree(), ""), removed, warnings


def merge_layers(layers: Sequence[Layer]) -> LoadedSettings:
    """Merge the layers (a later one wins, key by key, a list replaced), drop what a project layer may not set,
    warn about unknown and removed keys, and validate once."""
    flat: dict[str, object] = {}
    sources: dict[str, str] = {}
    warnings: list[str] = []
    removed: set[str] = set()
    removed_file = _USER_FILE
    for layer in layers:
        keys, gone, unknown = _scan(layer)
        if gone and not removed:
            removed_file = _KIND_FILES.get(layer.kind, layer.kind)
        removed.update(gone)
        warnings.extend(unknown)
        for key, value in keys.items():
            if layer.kind == "project" and schema.not_for_project(key):
                warnings.append(f'{_KIND_FILES["project"]}: "{key}" cannot be set here (ignored)')
                continue
            flat[key] = value
            sources[key] = layer.labels.get(key) or _KIND_LABELS.get(layer.kind, layer.kind)
    if removed:
        names = [name for name in REMOVED if name in removed]
        count = len(names)
        noun, them = ("settings are", "them") if count != 1 else ("setting is", "it")
        warnings.insert(
            0,
            f"{removed_file}: {count} {noun} no longer used ({', '.join(names)}); "
            f"run `tlaup config edit` and delete {them}",
        )
    try:
        settings = Settings.model_validate(_nest(flat))
    except ValidationError as e:
        raise _invalid(e, sources) from None
    return LoadedSettings(settings, sources, tuple(warnings))


def _invalid(error: ValidationError, sources: Mapping[str, str]) -> ConfigInvalid:
    lines: list[str] = []
    seen: set[str] = set()
    from_file = False
    for item in error.errors(include_url=False):
        key = schema.key_of(item["loc"])
        if key in seen:
            continue
        seen.add(key)
        label = sources.get(key, "default")
        in_file = label == "user file"
        from_file = from_file or in_file
        line = schema.error_message(key, item)
        # a value from the environment or a flag is named by its variable or option, a file's by the file
        prefix = _USER_FILE if in_file else label
        lines.append(line if label == "default" else f"{prefix}: {line}")
    hint = EDIT_HINT if from_file else None
    return ConfigInvalid(lines[0], hint=hint, details="\n".join(lines[1:]) or None)


def load_settings(paths: AppPaths, env: Mapping[str, str], overrides: Mapping[str, object] = {}) -> LoadedSettings:
    """`merge_layers(read_layers(...))`: what every command calls."""
    return merge_layers(read_layers(paths, env, overrides))


# --- writing ---------------------------------------------------------------------------------------------------


def parse_setting_text(text: str) -> object:
    """One command-line argument read as a YAML scalar or flow value (`config set`)."""
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        problem = getattr(e, "problem", None) or "not valid YAML"
        msg = f"cannot read the value {text!r}: {problem}"
        raise ValueError(msg) from None


def write_user_setting(paths: AppPaths, key: str, value: object) -> None:
    """Set one key in the user file and write the whole file again: the one writer.

    Comments, blank lines and quoting are not kept. A file that does not parse is not rewritten. The value is not
    checked here: the caller has called `check_setting`.
    """
    data = _read_user_file(paths) or {}
    *parents, last = key.split(".")
    target: dict[str, Any] = data
    for part in parents:
        child = target.get(part)
        if not isinstance(child, dict):
            child = {}
            target[part] = child
        target = child
    target[last] = value
    text = CONFIG_HEADER + "\n" + yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    path = paths.config_file
    temporary: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".config-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        if path.exists():
            Path(temporary).chmod(path.stat().st_mode & 0o7777)  # keep the old file's mode
        Path(temporary).replace(path)
        temporary = None
    except OSError as e:
        raise FileOperationError(f"cannot write {path}: {e.strerror or e}") from None  # noqa: TRY003
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                Path(temporary).unlink()


# --- for the old commands (goes with its last caller) ----------------------------------------------------------


def load_config() -> Settings:
    """The settings, for the old commands only; new code reads `get_context().settings`."""
    return get_context().settings


__all__ = [
    "CONFIG_HEADER",
    "EDIT_HINT",
    "Layer",
    "LoadedSettings",
    "load_config",
    "load_settings",
    "merge_layers",
    "parse_setting_text",
    "read_layers",
    "write_user_setting",
]
