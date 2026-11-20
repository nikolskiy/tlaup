"""Research question 35: does the JVM end when its parent is killed hard, per mechanism?

    python q35/check_kill.py [--child sleeper,tlc174,tlcrolling] [--mechanisms a,b] [--kills KILL,SEGV,TERM] [--xrs]

For each mechanism that applies on this OS, a parent.py (standing in for tlaup) starts a java child with it; this
script waits until the child runs, kills the parent alone (SIGKILL / a crash signal on POSIX, TerminateProcess on
Windows), and reports whether the child is still there after a few seconds and how it ended. Mechanism "none" is
the control: its child is expected to survive. Exits 0 whatever the outcome; every child is stopped at the end.

Prints one line per case:  RESULT q35 kill-<child>-<mechanism>[-xrs]-<kill> <os> : <outcome>
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c  # noqa: E402

AFTER_KILL = 8.0  # seconds a child may take to end after its parent was killed


def mechanisms() -> list[tuple[str, list[str]]]:
    """(name, extra parent.py args)"""
    out = [("none", [])]
    if c.IS_LINUX:
        out += [("pdeathsig-preexec", []), ("pdeathsig-preexec-thread", ["--from-thread"])]
        if shutil.which("setpriv"):
            out += [("pdeathsig-setpriv", []), ("pdeathsig-setpriv-thread", ["--from-thread"])]
    if not c.IS_WIN:
        out.append(("agent-pipe", []))
    out += [("agent-stdin", []), ("agent-pid", []), ("agent-onexit", []), ("watcher", [])]
    if c.IS_WIN:
        out.append(("job", []))
    return out


def kills() -> list[str]:
    return ["TERMINATE"] if c.IS_WIN else ["KILL", "SEGV", "TERM"]


def write_spec() -> str:
    d = os.path.join(c.WORK, "spec")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "Long.tla"), "w") as f:
        f.write("---- MODULE Long ----\nEXTENDS Naturals\nVARIABLE x\nInit == x = 0\n"
                "Next == x < 1000000000 /\\ x' = x + 1\nSpec == Init /\\ [][Next]_x\n====\n")
    with open(os.path.join(d, "Long.cfg"), "w") as f:
        f.write("SPECIFICATION Spec\n")
    return d


def child_cmd(kind: str, classes: str, log: str, xrs: bool, n: int) -> tuple[list[str], float]:
    user = ["-Xrs"] if xrs else []  # stands for the user's own Java options
    if kind == "sleeper":
        return [c.JAVA, *user, "-cp", classes, "q35.Sleeper", log, "120"], 1.5
    jar = os.environ.get("TLA2TOOLS_174" if kind == "tlc174" else "TLA2TOOLS_ROLLING")
    if not jar:
        return [], 0
    spec = write_spec()
    md = os.path.join(c.WORK, f"md-{n}")
    return [c.JAVA, *user, "-cp", jar, "tlc2.TLC", "-workers", "1", "-metadir", md,
            os.path.join(spec, "Long.tla")], 3.0


def one(kind: str, mech: str, margs: list[str], kill: str, jar: str, classes: str, xrs: bool, n: int) -> None:
    name = f"kill-{kind}-{mech}{'-xrs' if xrs else ''}-{kill}"
    log = os.path.join(c.WORK, f"log-{n}.txt")
    if os.path.exists(log):
        os.remove(log)
    cmd, settle = child_cmd(kind, classes, log, xrs, n)
    if not cmd:
        c.result(name, "skipped (jar variable not set)")
        return
    env = dict(os.environ, Q35_WATCHER_LOG=log)
    base = mech.replace("-thread", "")
    p = c.popen_parent(["--mechanism", base, "--agent-jar", jar, "--agent-log", log, "--lifetime", "60", *margs,
                        "--", *cmd], env=env)
    info = c.read_until_ready(p)
    cpid = int(info.get("CHILD", "0") or 0)
    wpid = int(info.get("WATCHER", "0") or 0)
    try:
        if not info.get("ready") or not cpid:
            c.result(name, f"ERROR parent did not start the child ({info})")
            return
        time.sleep(settle)
        if not c.alive(cpid):
            # e.g. pdeathsig from a thread that has ended: the child is gone before any kill
            q = info["_q"]
            extra = []
            while not q.empty():
                ln = q.get()
                if ln:
                    extra.append(ln.strip())
            c.result(name, f"child ENDED BEFORE THE KILL (parent still alive={p.poll() is None}; "
                           f"parent said {extra}; log {read(log)})")
            return
        t_kill = time.monotonic()
        if c.IS_WIN:
            p.kill()  # TerminateProcess
        else:
            os.kill(p.pid, getattr(signal, "SIG" + kill))
        p.wait(timeout=10)
        gone = c.wait_gone(cpid, AFTER_KILL)
        time.sleep(0.5)  # the watcher writes its line after the child has gone
        if gone is None:
            c.result(name, f"child STILL RUNNING {AFTER_KILL:.0f}s after the parent was killed "
                           f"(parent rc {p.returncode}, child's parent now {c.parent_of(cpid)}; log {read(log)})")
        else:
            c.result(name, f"child ENDED {gone:.2f}s after the parent was killed (parent rc {p.returncode}; "
                           f"how: {how(read(log), kind)})")
        del t_kill
    finally:
        for pid in (cpid, wpid):
            if pid and c.alive(pid):
                c.hard_kill(pid)
                c.wait_gone(pid, 5)
        if p.poll() is None:
            p.kill()
            p.wait()


def read(path: str) -> str:
    try:
        with open(path) as f:
            return " | ".join(ln.split(" t=")[0].strip() for ln in f if ln.strip() and not ln.startswith("main"))
    except OSError:
        return "-"


def how(log: str, kind: str) -> str:
    bits = []
    if "lifeline eof" in log or "lifeline parent-gone" in log:
        bits.append("agent saw the parent go and called System.exit")
    if "watcher" in log:
        bits.append(log[log.index("watcher"):].split(" |")[0])
    if kind == "sleeper":
        bits.append("shutdown hook ran (orderly exit, as after SIGTERM)" if "hook" in log
                    else "no shutdown hook (hard kill)")
    return "; ".join(bits) or f"log: {log}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", default="sleeper,tlc174,tlcrolling")
    ap.add_argument("--mechanisms", default="")
    ap.add_argument("--kills", default="")
    ap.add_argument("--xrs", action="store_true", help="add -Xrs (a user Java option that drops the JVM's handlers)")
    a = ap.parse_args()
    os.makedirs(c.WORK, exist_ok=True)
    print(f"q35 check_kill on {c.host()}; java: {c.java_version()}", flush=True)
    try:
        jar, classes = c.build()
    except Exception as e:  # noqa: BLE001
        c.result("kill-build", f"ERROR could not build the agent: {e}")
        return
    want = set(filter(None, a.mechanisms.split(",")))
    kl = list(filter(None, a.kills.split(","))) or (kills()[:1] if a.xrs else kills())
    n = 0
    for kind in a.child.split(","):
        for mech, margs in mechanisms():
            if want and mech not in want:
                continue
            for kill in (kl if kind == "sleeper" else kl[:1]):
                n += 1
                try:
                    one(kind, mech, margs, kill, jar, classes, a.xrs, n)
                except Exception as e:  # noqa: BLE001
                    c.result(f"kill-{kind}-{mech}-{kill}", f"ERROR {type(e).__name__}: {e}")
    shutil.rmtree(os.path.join(c.WORK, "spec"), ignore_errors=True)
    for d in os.listdir(c.WORK):
        if d.startswith("md-"):
            shutil.rmtree(os.path.join(c.WORK, d), ignore_errors=True)


if __name__ == "__main__":
    main()
