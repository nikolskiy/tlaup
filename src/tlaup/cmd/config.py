"""The `config` group (design 14 F1, F4, F5, 23 C1): `path`, `show`, `get`, `set` and `edit`.

Each command parses its arguments, calls the loader or the editor function and prints through the context's `Ui`.
`path` and `edit` never load the settings before the editor has run, so a broken file leaves them working (F4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import typer

from tlaup.cmd.completion import complete_config_key
from tlaup.errors import UsageError

if TYPE_CHECKING:
    from tlaup.context import AppContext

GROUP_HELP = "Show and change tlaup's settings."
PATH_HELP = "Print the path of the config file, whether or not it exists."
SHOW_HELP = "Print the settings in effect as YAML, each with the layer it came from: default, user file or environment."
GET_HELP = "Print one setting, in the form `config set` reads it."
SET_HELP = (
    "Set one setting in the config file. Rewrites the config file. "
    "Comments in it are not kept; use `tlaup config edit` to keep them."
)
EDIT_HELP = (
    "Open the config file in $VISUAL or $EDITOR, then check it. Give the editor's wait flag, as in "
    "EDITOR='code --wait'; an editor that returns at once leaves nothing to check."
)
KEY_HELP = "A setting, as section.name (tlc.workers); `config show` lists them."
VALUE_HELP = "The new value, read as YAML: 4, auto, true, or '[ghe.example.com]' for a list. Quote it for the shell."

app = typer.Typer(name="config", help=GROUP_HELP, no_args_is_help=True)


def format_value(value: object) -> str:
    """A value as `config set` reads it back: `auto`, `4`, `[ghe.example.com]`, `null`."""
    import yaml

    text = yaml.safe_dump(value, default_flow_style=True, allow_unicode=True, width=2**30)
    return text.removesuffix("\n").removesuffix("\n...")


def _value_of(settings: Any, key: str) -> object:
    value: Any = settings
    for part in key.split("."):
        value = getattr(value, part)
    return value


def _require_key(key: str) -> None:
    """A leaf key that exists, or `ConfigKeyNotFound` with its hint (a section's keys, or the nearest key)."""
    from tlaup.config.schema import check_setting, setting_keys

    if key not in setting_keys():
        check_setting(key, None)  # raises for a key that is not one, with the hint


def path_command(ctx: typer.Context) -> None:
    app_context: AppContext = ctx.find_root().obj
    app_context.ui.result(str(app_context.paths.config_file))


def show_command(ctx: typer.Context) -> None:
    app_context: AppContext = ctx.find_root().obj
    from tlaup.config.loader import load_settings
    from tlaup.config.schema import tree

    loaded = load_settings(app_context.paths, app_context.env)
    for warning in loaded.warnings:
        app_context.ui.warning(warning)
    lines: list[str] = []

    def walk(node: dict[str, Any], prefix: str, indent: str) -> None:
        for name, child in node.items():
            key = prefix + name
            if child is None:
                lines.append(
                    f"{indent}{name}: {format_value(_value_of(loaded.settings, key))}  # {loaded.sources[key]}"
                )
            else:
                lines.append(f"{indent}{name}:")
                walk(child, f"{key}.", indent + "  ")

    walk(tree(), "", "")
    app_context.ui.result("\n".join(lines))


def get_command(
    ctx: typer.Context,
    key: str = typer.Argument(..., metavar="KEY", help=KEY_HELP, autocompletion=complete_config_key),
) -> None:
    app_context: AppContext = ctx.find_root().obj
    _require_key(key)
    app_context.ui.result(format_value(_value_of(app_context.settings, key)))


def set_command(
    ctx: typer.Context,
    key: str = typer.Argument(..., metavar="KEY", help=KEY_HELP, autocompletion=complete_config_key),
    value: str = typer.Argument(..., metavar="VALUE", help=VALUE_HELP),
) -> None:
    app_context: AppContext = ctx.find_root().obj
    from tlaup.config.loader import parse_setting_text, write_user_setting
    from tlaup.config.schema import check_setting

    _require_key(key)  # 4 before 2, and both before 3
    try:
        checked = check_setting(key, parse_setting_text(value))
    except ValueError as e:
        raise UsageError(str(e)) from None
    _ = app_context.settings  # the whole file must load (3), and its warnings are printed, before it is written
    write_user_setting(app_context.paths, key, checked)
    app_context.ui.note(f"set {key} to {format_value(checked)} in {app_context.paths.config_file}")


def edit_command(ctx: typer.Context) -> None:
    app_context: AppContext = ctx.find_root().obj
    from tlaup.config.editor import edit_file, editor_command

    argv = editor_command(app_context.env)
    loaded = edit_file(app_context.paths, app_context.env, argv)
    for warning in loaded.warnings:
        app_context.ui.warning(warning)
