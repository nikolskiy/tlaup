"""Research question 35: what does each mechanism cost at start-up?

    python q35/check_startup.py [--runs N]

Medians of N runs (default 9) of: a JVM that starts and exits at once, with and without the lifeline agent;
TLC on a tiny spec (TLA2TOOLS_ROLLING), with and without the agent; the Popen call itself with a preexec_fn and
through setpriv (Linux); a watcher process's own start-up; creating and assigning a kill-on-close job (Windows).
Other work on the machine shifts the numbers; compare the pairs, not the absolutes.

Prints:  RESULT q35 startup-<what> <os> : <median ms> (...)
"""

from __future__ import annotations

import argparse
import os
import shutil
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as c  # noqa: E402


def med(f, n: int) -> tuple[float, float, float]:
    xs = []
    for _ in range(n):
        t0 = time.perf_counter()
        f()
        xs.append((time.perf_counter() - t0) * 1000)
    return statistics.median(xs), min(xs), max(xs)


def show(name: str, v: tuple[float, float, float]) -> None:
    c.result(f"startup-{name}", f"{v[0]:.1f} ms median (min {v[1]:.1f}, max {v[2]:.1f})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=9)
    n = ap.parse_args().runs
    os.makedirs(c.WORK, exist_ok=True)
    print(f"q35 check_startup on {c.host()}; java: {c.java_version()}", flush=True)
    jar, classes = c.build()
    dn = subprocess.DEVNULL
    sleeper = [c.JAVA, "-cp", classes, "q35.Sleeper", os.path.join(c.WORK, "startup.log"), "0"]
    agent = f"-javaagent:{jar}=pid={os.getpid()}"
    run = lambda argv, **kw: subprocess.run(argv, stdin=dn, stdout=dn, stderr=dn, check=True, **kw)  # noqa: E731
    run(sleeper)  # warm the file cache
    show("jvm-plain", med(lambda: run(sleeper), n))
    show("jvm-agent-pid", med(lambda: run([sleeper[0], agent, *sleeper[1:]]), n))
    if not c.IS_WIN:
        def piped():
            r, w = os.pipe()
            try:
                run([sleeper[0], f"-javaagent:{jar}=pipe=/dev/fd/{r}", *sleeper[1:]], pass_fds=(r,))
            finally:
                os.close(r)
                os.close(w)
        show("jvm-agent-pipe", med(piped, n))
    tools = os.environ.get("TLA2TOOLS_ROLLING")
    if tools:
        d = os.path.join(c.WORK, "tiny")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "Tiny.tla"), "w") as f:
            f.write("---- MODULE Tiny ----\nEXTENDS Naturals\nVARIABLE x\nInit == x = 0\nNext == x' = (x + 1) % 2\n====\n")
        with open(os.path.join(d, "Tiny.cfg"), "w") as f:
            f.write("INIT Init\nNEXT Next\n")
        md = os.path.join(d, "md")
        tlc = [c.JAVA, "-cp", tools, "tlc2.TLC", "-metadir", md, os.path.join(d, "Tiny.tla")]
        nt = max(3, n // 2)
        show("tlc-plain", med(lambda: run(tlc, cwd=d), nt))
        show("tlc-agent-pid", med(lambda: run([tlc[0], agent, *tlc[1:]], cwd=d), nt))
        shutil.rmtree(d, ignore_errors=True)
    # the Popen call alone (returns once the child has exec'd)
    true = ["true"] if not c.IS_WIN else [sys.executable, "-c", "0"]

    def popen_only(**kw):
        p = subprocess.Popen(true, stdin=dn, stdout=dn, stderr=dn, **kw)
        return p

    procs = []
    show("popen-plain", med(lambda: procs.append(popen_only()), n))
    if c.IS_LINUX:
        sys.path.insert(0, c.HERE)
        import parent  # noqa: E402

        fn = parent.pdeathsig_preexec(os.getpid(), 15)
        show("popen-preexec-pdeathsig", med(lambda: procs.append(popen_only(preexec_fn=fn)), n))
        if shutil.which("setpriv"):
            show("run-true-plain", med(lambda: run(true), n))
            show("run-true-via-setpriv", med(lambda: run(["setpriv", "--pdeathsig", "TERM", "--", *true]), n))
    for p in procs:
        p.wait()
    # watcher start-up: given a child that is already gone it returns at once, so this is its start cost
    gone = subprocess.Popen(true)
    gone.wait()
    show("watcher-process", med(lambda: run([sys.executable, "-I", os.path.join(c.HERE, "watcher.py"),
                                             str(os.getpid()), str(gone.pid)]), n))
    if c.IS_WIN:
        sys.path.insert(0, c.HERE)
        import parent  # noqa: E402

        def job():
            p = subprocess.Popen(true, stdin=dn, stdout=dn, stderr=dn)
            h, assign = parent.make_kill_on_close_job()
            assign(p)
            p.wait()
        show("popen-plus-job", med(job, n))
        show("popen-plain-wait", med(lambda: popen_only().wait(), n))


if __name__ == "__main__":
    main()
