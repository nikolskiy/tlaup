"""The settings schema (design 14 F1 and F3).

The packaged `default_config.yaml` is the one source of defaults: no field here has one.
"""

import json
import re
from typing import Annotated, Any, Literal, cast, get_origin
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, Field, PositiveInt, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo
from pydantic.types import JsonValue

from tlaup.errors import ConfigKeyNotFound

_HOST = re.compile(r"[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*")
_BAD_URL_CHARS = re.compile(r"[\s\x00-\x1f\x7f\\]")

# Fields a project layer may not set (design 14 F3, decision D41): the marker the loader reads.
_NOT_FOR_PROJECT: dict[str, JsonValue] = {"project_settable": False}


def show(value: object) -> str:
    """A value as the messages quote it: strings in double quotes, the rest as JSON."""
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return repr(value)


def _host(value: str) -> str:
    if not _HOST.fullmatch(value):
        msg = f"expected a bare host name such as ghe.example.com, no scheme, path, port or wildcard, got {show(value)}"
        raise ValueError(msg)
    return value.lower()


def _repository(value: str) -> str:
    problem = None
    if _BAD_URL_CHARS.search(value):
        problem = "no white space, control character or backslash"
    else:
        try:
            parts = urlsplit(value)
            _ = parts.port  # a bad port raises
        except ValueError:
            problem = "a well-formed address"
        else:
            if parts.scheme != "https" or not parts.hostname:
                problem = "an https address"
            elif parts.username is not None or parts.password is not None or "@" in parts.netloc:
                problem = "no user part"
            elif parts.query or parts.fragment or "?" in value or "#" in value:
                problem = "no query string or fragment"
    if problem:
        example = "https://api.github.com/repos/tlaplus/tlaplus"
        msg = f"expected an https address such as {example} ({problem}), got {show(value)}"
        raise ValueError(msg)
    return value


Host = Annotated[str, AfterValidator(_host)]
Repository = Annotated[str, AfterValidator(_repository)]


class ToolSettings(BaseModel):
    repository: Repository = Field(json_schema_extra=_NOT_FOR_PROJECT)
    token_hosts: list[Host] = Field(json_schema_extra=_NOT_FOR_PROJECT)


class JavaSettings(BaseModel):
    min_version: int
    opts: list[str]


class TlcSettings(BaseModel):
    workers: PositiveInt | Literal["auto"]
    refresh_interval: float
    plain: bool
    keep: bool


class Settings(BaseModel):
    tool: ToolSettings
    java: JavaSettings
    tlc: TlcSettings
    module_path: str | None
    module_lib_path: str | None


# The names F3 removed, in the order the one warning lists them. A section counts once.
REMOVED: tuple[str, ...] = ("workspace", "tla", "tlc.java_class", "tlc.overrides_class")

# What each key expects, for a value that is the wrong type (the validators of `Host` and `Repository` say their own).
_EXPECTS = {
    "tool.repository": "a string",
    "tool.token_hosts": "a list of host names",
    "java.min_version": "an integer",
    "java.opts": "a list of strings",
    "tlc.workers": 'a positive integer or "auto"',
    "tlc.refresh_interval": "a number",
    "tlc.plain": "true or false",
    "tlc.keep": "true or false",
    "module_path": "a string or null",
    "module_lib_path": "a string or null",
}


def _section_model(annotation: Any) -> type[BaseModel] | None:
    return annotation if isinstance(annotation, type) and issubclass(annotation, BaseModel) else None


def tree() -> dict[str, Any]:
    """The key tree: a section is a nested dictionary, a leaf key is None."""

    def walk(model: type[BaseModel]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, field in model.model_fields.items():
            section = _section_model(field.annotation)
            out[name] = walk(section) if section else None
        return out

    return walk(Settings)


def _field(key: str) -> FieldInfo | None:
    """The field of a dotted leaf key, or None."""
    model: type[BaseModel] = Settings
    parts = key.split(".")
    for index, part in enumerate(parts):
        field = model.model_fields.get(part)
        if field is None:
            return None
        section = _section_model(field.annotation)
        if index == len(parts) - 1:
            return None if section else field
        if section is None:
            return None
        model = section
    return None


def setting_keys() -> tuple[str, ...]:
    """Every dotted leaf key, in the order of the schema."""
    keys: list[str] = []

    def walk(node: dict[str, Any], prefix: str) -> None:
        for name, child in node.items():
            if child is None:
                keys.append(prefix + name)
            else:
                walk(child, f"{prefix}{name}.")

    walk(tree(), "")
    return tuple(keys)


def is_list_key(key: str) -> bool:
    """Whether the key holds a list."""
    field = _field(key)
    return field is not None and get_origin(field.annotation) is list


def not_for_project(key: str) -> bool:
    """Whether a project layer may not set the key (F3)."""
    field = _field(key)
    extra = field.json_schema_extra if field else None
    return isinstance(extra, dict) and extra.get("project_settable") is False


def _distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def closest_key(key: str) -> str | None:
    """A known key within edit distance 2 of `key` (the first such, nearest first), for "did you mean"."""
    best: tuple[int, str] | None = None
    for known in setting_keys():
        d = _distance(key, known)
        if d <= 2 and (best is None or d < best[0]):
            best = (d, known)
    return best[1] if best else None


def _adapter(field: FieldInfo) -> TypeAdapter[Any]:
    annotation: Any = field.annotation
    wrapped = Annotated[(annotation, *field.metadata)] if field.metadata else annotation
    return TypeAdapter(cast("type[Any]", wrapped))


def error_message(key: str, error: Any) -> str:
    """One validation problem as `key: expected X, got Y`; `error` is one entry of a `ValidationError`."""
    if error["type"] == "value_error":
        return f"{key}: {error['ctx']['error']}"
    expects = _EXPECTS.get(key, "a valid value")
    return f"{key}: expected {expects}, got {show(error['input'])}"


def key_of(loc: tuple[int | str, ...]) -> str:
    """The setting a Pydantic `loc` belongs to: the leading parts that are fields (a union adds its member's tag)."""
    node: dict[str, Any] | None = tree()
    parts: list[str] = []
    for part in loc:
        if node is None or not isinstance(part, str) or part not in node:
            break
        parts.append(part)
        node = node[part]
    return ".".join(parts)


def check_setting(key: str, value: object) -> object:
    """Validate one value for one key and return it as stored (host names lower-cased).

    An unknown key is `ConfigKeyNotFound`; a value that does not fit is a `ValueError` naming the key and what it
    expects. `config set` turns that into a usage error, the loader into `ConfigInvalid`.
    """
    field = _field(key)
    if field is None:
        node: Any = tree()
        for part in key.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, dict):
            inside = ", ".join(f"{key}.{name}" for name in node)
            raise ConfigKeyNotFound(f'"{key}" is a section, not a setting', hint=f"its settings: {inside}")  # noqa: TRY003
        close = closest_key(key)
        hint = f'did you mean "{close}"?' if close else "see `tlaup config show`"
        raise ConfigKeyNotFound(f'no such setting: "{key}"', hint=hint)  # noqa: TRY003
    try:
        return _adapter(field).validate_python(value)
    except ValidationError as e:
        raise ValueError(error_message(key, e.errors(include_url=False)[0])) from None


__all__ = ["REMOVED", "Settings", "check_setting", "closest_key", "setting_keys"]
