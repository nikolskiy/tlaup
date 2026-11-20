"""Typer's public completion route (add_completion=True): --show-completion. python3 pubcomp.py <venv-python>."""
import json, os, subprocess, sys, textwrap
PY = sys.argv[1]
code = textwrap.dedent('''
    import typer
    app = typer.Typer(name="app")
    @app.command()
    def hi(): print("hi")
    @app.command()
    def other(): pass
    app(prog_name="app")
''')
BASE = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG")}
res = {}
for label, args, env in [
    ("--show-completion (shell auto-detected, SHELL=/bin/bash)", ["--show-completion"], {"SHELL": "/bin/bash"}),
    ("--show-completion bash", ["--show-completion", "bash"], {"SHELL": "/bin/bash"}),
    ("--help lists the two options", ["--help"], {"COLUMNS": "100", "NO_COLOR": "1"}),
]:
    r = subprocess.run([PY, "-c", code, *args], env=dict(BASE, **env), capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    d = {"code": r.returncode, "stdout_head": r.stdout.strip()[:100].replace("\n", " | "), "stderr_head": r.stderr.strip()[-120:].replace("\n", " | ")}
    if "help" in label:
        d = {"code": r.returncode, "show_completion_listed": "--show-completion" in r.stdout, "install_completion_listed": "--install-completion" in r.stdout}
    res[label] = d
print(json.dumps(res, indent=1))
