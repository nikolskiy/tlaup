"""Run inside a version's venv: metadata, contract names, CliRunner exit codes. Prints JSON."""
import importlib, importlib.metadata as md, inspect, json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
out = {}
import typer, rich
out["typer"] = md.version("typer")
out["rich"] = md.version("rich")
try:
    out["click_installed"] = md.version("click")
except md.PackageNotFoundError:
    out["click_installed"] = None
try:
    import click  # noqa
    out["import_click"] = True
except ImportError:
    out["import_click"] = False
out["requires"] = md.requires("typer")
out["bundled_click"] = importlib.util.find_spec("typer._click") is not None
names = {}
for n in ("Exit", "Abort", "BadParameter", "TyperException", "Context"):
    names[n] = hasattr(typer, n)
out["public_names"] = names
import typer.core
out["TyperGroup_make_context"] = str(inspect.signature(typer.core.TyperGroup.make_context))
out["TyperGroup_invoke"] = str(inspect.signature(typer.core.TyperGroup.invoke))
mro = [f"{c.__module__}.{c.__name__}" for c in typer.core.TyperGroup.__mro__]
out["TyperGroup_mro"] = mro
import app as A
from typer.testing import CliRunner
r = CliRunner()
cases = [
    ["--help"], [], ["tool"], ["lines"], ["tool", "pin", "rolling"], ["tool", "pin", "nosuch"],
    ["boom"], ["interrupt"], ["abort"], ["eof"], ["exit", "1"], ["exit", "12"], ["badparam"],
    ["nosuchcmd"], ["lines", "--nosuch"], ["lines", "--n", "x"], ["tool", "pin"], ["--version"], ["prompt"],
]
res = {}
import os as _os
for c in cases:
    if c == ["prompt"] and _os.environ.get("SKIP_PROMPT"):
        continue   # Click < 8.2: CliRunner re-prompts forever on empty input
    key = " ".join(c) or "(none)"
    try:
        o = r.invoke(A.app, c, input="")
        res[key] = {"code": o.exit_code, "exc": type(o.exception).__name__ if o.exception and not isinstance(o.exception, SystemExit) else None,
                    "out": o.output[:80]}
    except Exception as e:
        res[key] = {"error": repr(e)}
import os
os.environ["APP_VERSION_RAISES"] = "1"
o = r.invoke(A.app, ["--version"])
res["--version (callback raises RuntimeError)"] = {"code": o.exit_code, "out": o.output[:80]}
out["runner"] = res
out["te_source"] = A.TE_SOURCE
print(json.dumps(out, indent=1))
