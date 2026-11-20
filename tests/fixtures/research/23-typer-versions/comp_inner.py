"""Run inside a venv: what the completion modules offer. Prints JSON."""
import importlib, inspect, json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
out = {}
for m in ("typer._completion_classes", "typer._completion_shared", "typer.completion", "typer._completion"):
    try:
        mod = importlib.import_module(m)
        out[m] = sorted(n for n in dir(mod) if not n.startswith("__") and n in (
            "completion_init", "get_completion_script", "install", "Shells", "shell_complete", "get_completion_inspect_parameters",
            "install_callback", "show_callback", "BashComplete", "ZshComplete", "FishComplete"))
    except ImportError as e:
        out[m] = f"ImportError: {e}"
try:
    from typer._completion_shared import get_completion_script
    out["get_completion_script_signature"] = str(inspect.signature(get_completion_script))
    scripts = {}
    for sh in ("bash", "zsh", "fish"):
        s = get_completion_script(prog_name="app", complete_var="_APP_COMPLETE", shell=sh)
        scripts[sh] = {"len": len(s), "has": [t for t in ("COMP_WORDS", "COMP_CWORD", "_TYPER_COMPLETE_ARGS", "_TYPER_COMPLETE_FISH_ACTION",
                                                       "complete_bash", "complete_zsh", "complete_fish", "_APP_COMPLETE") if t in s]}
    out["scripts"] = scripts
except Exception as e:
    out["get_completion_script_error"] = repr(e)
try:
    from typer._completion_classes import completion_init
    out["completion_init_signature"] = str(inspect.signature(completion_init))
except Exception as e:
    out["completion_init_error"] = repr(e)
print(json.dumps(out, indent=1))
