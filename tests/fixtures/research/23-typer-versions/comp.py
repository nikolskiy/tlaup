"""Completion protocol through real processes: python3 comp.py <venv-python>. Prints JSON."""
import json, os, subprocess, sys
PY = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app.py")
BASE = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG")}
BASE.update({"TERM": "dumb", "COLUMNS": "100"})


def call(env_extra, args=()):
    r = subprocess.run([PY, APP, *args], env=dict(BASE, **env_extra), capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    return {"code": r.returncode, "stdout": r.stdout.strip().replace("\n", " | ")[:200], "stderr": r.stderr.strip().replace("\n", " | ")[:120]}


res = {}
res["inner"] = json.loads(subprocess.run([PY, os.path.join(HERE, "comp_inner.py")], capture_output=True, text=True, env=BASE).stdout or "{}")
res["bash: tool pin <TAB> (init called)"] = call({"_APP_COMPLETE": "complete_bash", "COMP_WORDS": "app tool pin ", "COMP_CWORD": "3"})
res["bash: tool pin rolling @ <TAB> (split at @)"] = call({"_APP_COMPLETE": "complete_bash", "COMP_WORDS": "app tool pin rolling @ ", "COMP_CWORD": "5"})
res["bash: tool pin rolling@ (unsplit)"] = call({"_APP_COMPLETE": "complete_bash", "COMP_WORDS": "app tool pin rolling@", "COMP_CWORD": "3"})
res["fish: get-args"] = call({"_APP_COMPLETE": "complete_fish", "_TYPER_COMPLETE_ARGS": "app tool pin ", "_TYPER_COMPLETE_FISH_ACTION": "get-args"})
res["fish: is-args"] = call({"_APP_COMPLETE": "complete_fish", "_TYPER_COMPLETE_ARGS": "app tool pin r", "_TYPER_COMPLETE_FISH_ACTION": "is-args"})
res["zsh"] = call({"_APP_COMPLETE": "complete_zsh", "_TYPER_COMPLETE_ARGS": "app tool pin "})
res["bash without completion_init()"] = call({"_APP_COMPLETE": "complete_bash", "COMP_WORDS": "app tool pin ", "COMP_CWORD": "3", "APP_NO_INIT": "1"})
res["command names (bash, 'app lin<TAB>')"] = call({"_APP_COMPLETE": "complete_bash", "COMP_WORDS": "app lin", "COMP_CWORD": "1"})
print(json.dumps(res, indent=1))
