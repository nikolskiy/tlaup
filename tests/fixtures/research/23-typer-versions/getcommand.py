"""Run inside a venv: what typer.main.get_command(app) offers for a reference script (C5). Prints one JSON line."""
import json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import typer, typer.main, app as A
g = typer.main.get_command(A.app)
sub = g.commands["tool"].commands["pin"]
print(json.dumps({
    "root_type": f"{type(g).__module__}.{type(g).__name__}",
    "root_commands": len(g.commands), "root_help": g.help, "root_epilog": g.epilog,
    "root_params": [p.name for p in g.params],
    "pin_params": [(p.name, type(p).__name__, getattr(p, "required", None), getattr(p, "help", None)) for p in sub.params],
    "pin_help": sub.help,
    "tool_is_group": hasattr(g.commands["tool"], "commands"),
}))
