"""Signal tlaup (or its process group) while it runs a long TLC and report exit code and java child fate.
usage: signal_tlaup.py TLAUP_BIN XDG_DIR SCENARIO [--raw]
SCENARIO: term-parent | int-parent | int-group | term-group | int-parent-twice
Run from any cwd; the spec is in ./specs next to this script. tlaup runs in its own session/process group,
so signals sent to the group never reach the caller."""
import os, signal, subprocess, sys, time
tlaup, xdg, scen = sys.argv[1:4]
raw = ["--raw"] if "--raw" in sys.argv else []
here = os.path.dirname(os.path.abspath(__file__))
env = dict(os.environ, XDG_CONFIG_HOME=f"{xdg}/config", XDG_CACHE_HOME=f"{xdg}/cache")
out = open(f"{xdg}/tlaup_{scen}{'_raw' if raw else ''}.out", "w")
p = subprocess.Popen([tlaup, "tlc", "Long", "--cfg", "Long", *raw], cwd=f"{here}/specs", env=env,
                     stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
def kids(pid):
    r = subprocess.run(["ps", "-o", "pid=", "--ppid", str(pid)], capture_output=True, text=True)
    return [int(x) for x in r.stdout.split()]
def alive(pid):
    return subprocess.run(["ps", "-p", str(pid), "-o", "stat="], capture_output=True, text=True).stdout.strip()
time.sleep(10)
j = [k for k in kids(p.pid) if "java" in open(f"/proc/{k}/comm").read()]
assert j, "no java child"
jpid = j[0]
print(f"[{scen}{' raw' if raw else ''}] tlaup pid {p.pid} (pgid {os.getpgid(p.pid)}), java pid {jpid}, java ppid {os.popen(f'ps -o ppid= -p {jpid}').read().strip()}")
sigs = {"term-parent": lambda: os.kill(p.pid, signal.SIGTERM), "int-parent": lambda: os.kill(p.pid, signal.SIGINT),
        "int-group": lambda: os.killpg(p.pid, signal.SIGINT), "term-group": lambda: os.killpg(p.pid, signal.SIGTERM),
        "int-parent-twice": lambda: (os.kill(p.pid, signal.SIGINT), time.sleep(0.3), os.kill(p.pid, signal.SIGINT))}
sigs[scen]()
try:
    rc = p.wait(timeout=30); print(f"  tlaup returncode = {rc}  (negative = killed by that signal; shell $? would be 128+n)")
except subprocess.TimeoutExpired:
    print("  tlaup still running after 30 s"); rc = None
time.sleep(3)
st = alive(jpid)
print(f"  java {jpid} after tlaup exit: {'GONE' if not st else 'ALIVE stat=' + st}")
if st:
    cpu1 = os.popen(f"ps -o cputime= -p {jpid}").read().strip(); time.sleep(5)
    print(f"  java cputime {cpu1} -> {os.popen(f'ps -o cputime= -p {jpid}').read().strip()}, ppid now {os.popen(f'ps -o ppid= -p {jpid}').read().strip()}")
    os.kill(jpid, signal.SIGKILL); print(f"  killed leftover java {jpid}")
if rc is None:
    os.killpg(p.pid, signal.SIGKILL)
