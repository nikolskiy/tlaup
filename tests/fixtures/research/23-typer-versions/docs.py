"""`typer <module> utils docs` and the public --show-completion: python3 docs.py <venv-python> <outdir>. Prints JSON."""
import hashlib, json, os, subprocess, sys
PY, OUTDIR = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG")}
os.makedirs(OUTDIR, exist_ok=True)
res = {}


def docs(label, env):
    path = os.path.join(OUTDIR, f"docs-{label}.md")
    if os.path.exists(path):
        os.unlink(path)
    r = subprocess.run([PY, "-m", "typer", "app.py", "utils", "docs", "--name", "app", "--output", path],
                       cwd=HERE, env=dict(BASE, **env), capture_output=True, text=True, timeout=60)
    d = {"code": r.returncode, "stderr": r.stderr.strip()[-150:]}
    if os.path.exists(path):
        t = open(path).read()
        d.update(bytes=len(t), sha=hashlib.sha256(t.encode()).hexdigest()[:10], has_ansi="\x1b[" in t,
                 mentions=[w for w in ("tool pin", "--n", "How many lines", "Pin a build", "--version", "Tool group", "lines") if w in t])
    return d


res["docs COLUMNS=100 NO_COLOR"] = docs("c100", {"COLUMNS": "100", "NO_COLOR": "1", "TERM": "dumb"})
res["docs COLUMNS=60 NO_COLOR"] = docs("c60", {"COLUMNS": "60", "NO_COLOR": "1", "TERM": "dumb"})
res["docs COLUMNS=100 color forced"] = docs("color", {"COLUMNS": "100", "FORCE_COLOR": "1", "TERM": "xterm-256color"})
res["docs again COLUMNS=100 (determinism)"] = docs("c100b", {"COLUMNS": "100", "NO_COLOR": "1", "TERM": "dumb"})
res["docs tool cmd head"] = None
try:
    t = open(os.path.join(OUTDIR, "docs-c100.md")).read()
    res["docs tool cmd head"] = t[:400]
except OSError:
    pass


print(json.dumps(res, indent=1))
