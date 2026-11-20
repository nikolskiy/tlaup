"""Real-process checks for one venv: python3 proc.py <venv-python>. Prints JSON."""
import json, os, signal, subprocess, sys, time

PY = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app.py")
BASE = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG")}
BASE.update({"TERM": "dumb", "COLUMNS": "100", "NO_COLOR": "1"})


def run(args, mode="f10", out="pipe_dead", err="pipe_open", extra_env=None, timeout=20):
    """out/err: pipe_dead (reader closed before start), pipe_open (collected), same_dead (stderr on stdout's dead pipe)."""
    env = dict(BASE, **(extra_env or {}))
    if mode == "bare":
        env["APP_BARE"] = "1"
    fds = {}
    close = []
    if out == "pipe_dead" or err == "same_dead":
        r, w = os.pipe(); os.close(r); fds["w_dead"] = w; close.append(w)
    kw = {}
    kw["stdout"] = fds["w_dead"] if out == "pipe_dead" else subprocess.PIPE
    if err == "same_dead":
        kw["stderr"] = fds["w_dead"]
    elif err == "pipe_dead":
        r2, w2 = os.pipe(); os.close(r2); kw["stderr"] = w2; close.append(w2)
    else:
        kw["stderr"] = subprocess.PIPE
    p = subprocess.Popen([PY, APP] + args, env=env, stdin=subprocess.DEVNULL, **kw)
    try:
        o, e = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill(); o, e = p.communicate(); return {"code": "TIMEOUT"}
    finally:
        for fd in close:
            os.close(fd)
    tb = bool(e and b"Traceback" in e)
    return {"code": p.returncode, "traceback": tb}


def early_reader(args, mode="f10"):
    """Reader reads one line and leaves (the `| head -1` shape), through a real pipe."""
    env = dict(BASE)
    if mode == "bare":
        env["APP_BARE"] = "1"
    p = subprocess.Popen([PY, APP] + args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.stdout.readline(); p.stdout.close()
    try:
        e = p.stderr.read()
        p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill(); return {"code": "TIMEOUT"}
    return {"code": p.returncode, "traceback": b"Traceback" in e}


def bash_head(cmd_args, mode="f10"):
    env = dict(BASE)
    if mode == "bare":
        env["APP_BARE"] = "1"
    c = f'{PY} {APP} ' + " ".join(cmd_args) + ' | head -1 >/dev/null; echo ${PIPESTATUS[0]}'
    r = subprocess.run(["bash", "-c", c], env=env, capture_output=True, text=True, timeout=30)
    return {"code": int(r.stdout.strip().splitlines()[-1]), "traceback": "Traceback" in r.stderr}


def sigint(sub, mode="f10"):
    env = dict(BASE)
    if mode == "bare":
        env["APP_BARE"] = "1"
    # a shell starts background jobs with SIGINT ignored and Python then keeps it ignored: restore the default
    p = subprocess.Popen([PY, APP, sub], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
    p.stdout.readline()
    p.send_signal(signal.SIGINT)
    t = time.time()
    try:
        # keep draining so the pipe is alive
        o, e = p.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill(); return {"code": "TIMEOUT"}
    return {"code": p.returncode, "secs": round(time.time() - t, 2), "traceback": b"Traceback" in e}


res = {}
ONLY_SIGINT = len(sys.argv) > 2 and sys.argv[2] == "--sigint-only"   # merge into an existing proc.json
for mode in ("f10", "bare"):
    m = {}
    if ONLY_SIGINT:
        m["SIGINT during lines-forever (spin)"] = sigint("spin", mode)
        m["SIGINT during sleep (wait)"] = sigint("wait", mode)
        res[mode] = m
        continue
    m["lines 200000 | head -1 (python pipe, reader leaves)"] = early_reader(["lines", "--n", "200000"], mode)
    m["bash: lines 200000 | head -1"] = bash_head(["lines", "--n", "200000"], mode)
    m["bash: --help | head -1"] = bash_head(["--help"], mode)
    m["bash: tool --help | head -1"] = bash_head(["tool", "--help"], mode)
    m["bash: (no args) | head -1"] = bash_head([], mode)
    m["bash: --nosuch 2>&1 | head -1"] = bash_head(["--nosuch", "2>&1"], mode)
    for name, args, o, e in [
        ("--help, stdout dead", ["--help"], "pipe_dead", "pipe_open"),
        ("tool --help, stdout dead", ["tool", "--help"], "pipe_dead", "pipe_open"),
        ("no args, stdout dead", [], "pipe_dead", "pipe_open"),
        ("--nosuch, stdout+stderr dead", ["--nosuch"], "pipe_dead", "same_dead"),
        ("lines 3, stdout dead", ["lines"], "pipe_dead", "pipe_open"),
        ("--version, stdout dead", ["--version"], "pipe_dead", "pipe_open"),
        ("tool pin nosuch, stderr dead", ["tool", "pin", "nosuch"], "pipe_open", "pipe_dead"),
        ("boom, stderr dead", ["boom"], "pipe_open", "pipe_dead"),
        ("exit 1, stdout dead", ["exit", "1"], "pipe_dead", "pipe_open"),
        ("exit 12, stdout dead", ["exit", "12"], "pipe_dead", "pipe_open"),
        ("--help, open (control)", ["--help"], "pipe_open", "pipe_open"),
        ("--nosuch, open (control)", ["--nosuch"], "pipe_open", "pipe_open"),
        ("lines, open (control)", ["lines"], "pipe_open", "pipe_open"),
        ("tool pin nosuch, open", ["tool", "pin", "nosuch"], "pipe_open", "pipe_open"),
        ("boom, open", ["boom"], "pipe_open", "pipe_open"),
        ("interrupt command, open", ["interrupt"], "pipe_open", "pipe_open"),
        ("abort command, open", ["abort"], "pipe_open", "pipe_open"),
        ("eof command, open", ["eof"], "pipe_open", "pipe_open"),
        ("prompt at EOF, open", ["prompt"], "pipe_open", "pipe_open"),
        ("badparam, open", ["badparam"], "pipe_open", "pipe_open"),
        ("nosuchcmd, open", ["nosuchcmd"], "pipe_open", "pipe_open"),
        ("tool (group alone), open", ["tool"], "pipe_open", "pipe_open"),
    ]:
        m[name] = run(args, mode, o, e)
    m["--version raises RuntimeError, open"] = run(["--version"], mode, "pipe_open", "pipe_open", {"APP_VERSION_RAISES": "1"})
    m["SIGINT during lines-forever (spin)"] = sigint("spin", mode)
    m["SIGINT during sleep (wait)"] = sigint("wait", mode)
    res[mode] = m
if ONLY_SIGINT:
    path = os.path.join(os.path.dirname(os.path.dirname(PY)), "..", "..", "out", os.path.basename(os.path.dirname(os.path.dirname(PY))), "proc.json")
    old = json.load(open(path))
    for mode in res:
        old[mode].update(res[mode])
    json.dump(old, open(path, "w"), indent=1)
    print(json.dumps(res))
else:
    print(json.dumps(res, indent=1))
