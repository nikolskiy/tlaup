"""Research question 35, Linux: is TLC's last checkpoint usable after the JVM is stopped at a chosen point of
writing one? Stops are placed with jdb breakpoints inside ModelChecker.checkpoint() and
DiskStateQueue.commitChkpt(); then the JVM is killed (SIGKILL while suspended, or SIGTERM after resuming), the
folder is listed, and `-recover` is run to the end. With a spec of known size, a recovered run that finishes with the
right number of distinct states is the proof that the checkpoint was whole.

    python ckpt_kill.py --jar JAR --java JAVA --bound B --line-set rolling|v174 --scenarios a,b --out DIR

Kills only processes it started, by pid.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import signal
import socket
import subprocess
import threading
import time

LINES = {
    # ModelChecker.checkpoint() and DiskStateQueue.commitChkpt() line numbers, read from the jars' LineNumberTable
    "rolling": dict(mc="tlc2.tool.ModelChecker", begin_mid=762, begun=776, queue_committed=777, fp_committed=779,
                    settings_left=784, dsq_pools_deleted=218, dsq_before_rename=220),
    "v174": dict(mc="tlc2.tool.ModelChecker", begin_mid=709, begun=718, queue_committed=719, fp_committed=721,
                 settings_left=None, dsq_pools_deleted=197, dsq_before_rename=199),
}

# scenario -> (checkpoints that must have completed before the breakpoint is set, breakpoint key, how to kill)
SCENARIOS = {
    "first-begun": (0, "begun", "KILL"),
    "first-queue-committed": (0, "queue_committed", "KILL"),
    "later-begin-mid": (1, "begin_mid", "KILL"),
    "later-begun": (1, "begun", "KILL"),
    "later-pools-deleted": (1, "dsq_pools_deleted", "KILL"),
    "later-chkpt-deleted": (1, "dsq_before_rename+renameTo", "KILL"),
    "later-queue-committed": (1, "queue_committed", "KILL"),
    "later-fp-committed": (1, "fp_committed", "KILL"),
    "later-begun-TERM": (1, "begun", "TERM"),
    "later-queue-committed-TERM": (1, "queue_committed", "TERM"),
    "between": (1, None, "KILL"),
    "between-TERM": (1, None, "TERM"),
}


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def write_spec(d: str, bound: int) -> str:
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "Wide.tla"), "w") as f:
        f.write("---- MODULE Wide ----\nEXTENDS Naturals\nVARIABLE f\nInit == f = [i \\in 1..6 |-> 0]\n"
                f"Next == \\E i \\in 1..6 : f[i] < {bound} /\\ f' = [f EXCEPT ![i] = f[i] + 1]\n"
                "Spec == Init /\\ [][Next]_f\n====\n")
    with open(os.path.join(d, "Wide.cfg"), "w") as f:
        f.write("SPECIFICATION Spec\n")
    return os.path.join(d, "Wide.tla")


class Lines:
    def __init__(self, stream, tag: str, log: str):
        self.q: queue.Queue = queue.Queue()
        self.all: list[str] = []
        self.log = open(log, "a")

        def rd() -> None:
            for line in iter(stream.readline, ""):
                self.all.append(line)
                self.log.write(line)
                self.log.flush()
                self.q.put(line)
            self.q.put(None)

        threading.Thread(target=rd, daemon=True).start()

    def wait_for(self, pred, timeout: float) -> str | None:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                ln = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            if ln is None:
                return None
            if pred(ln):
                return ln
        return None


def listing(folder: str) -> list[str]:
    out = []
    for n in sorted(os.listdir(folder)):
        if n.isdigit():
            continue
        out.append(f"{n}:{os.path.getsize(os.path.join(folder, n))}")
    pools = sorted(int(n) for n in os.listdir(folder) if n.isdigit())
    out.append(f"pools:{len(pools)}" + (f"[{pools[0]}..{pools[-1]}]" if pools else ""))
    return out


def run(a, name: str, workdir: str) -> dict:
    need, bp, kill = SCENARIOS[name]
    L = LINES[a.line_set]
    spec = write_spec(os.path.join(workdir, "spec"), a.bound)
    md = os.path.join(workdir, "md")
    port = free_port()
    props = ["-Dtlc2.TLCGlobals.chkpt=1000"]
    if a.line_set == "rolling":
        props.append("-Dtlc2.TLC.progressInterval=2")
    cmd = [a.java, f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=127.0.0.1:{port}", *props,
           "-cp", a.jar, "tlc2.TLC", "-deadlock", "-workers", a.workers, "-metadir", md, spec]
    res: dict = {"scenario": name, "kill": kill, "breakpoint": bp}
    tlc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=workdir)
    out = Lines(tlc.stdout, "tlc", os.path.join(workdir, "run1.txt"))
    jdb = None
    try:
        done = 0
        while done < need:
            if out.wait_for(lambda s: s.startswith("Checkpointing completed"), 400) is None:
                res["error"] = "no checkpoint completed in time (run ended or too slow)"
                return res
            done += 1
        if bp is None:
            # between checkpoints: kill right after one completed
            time.sleep(0.3)
        else:
            jdb = subprocess.Popen([a.jdb, "-attach", f"127.0.0.1:{port}"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            jo = Lines(jdb.stdout, "jdb", os.path.join(workdir, "jdb.txt"))
            time.sleep(1.5)
            first, _, then = bp.partition("+")
            cls = L["mc"] if not first.startswith("dsq") else "tlc2.tool.queue.DiskStateQueue"
            jdb.stdin.write(f"stop at {cls}:{L[first]}\n")
            jdb.stdin.flush()
            if jo.wait_for(lambda s: "Breakpoint hit" in s, 400) is None:
                res["error"] = "breakpoint never hit"
                return res
            if then == "renameTo":
                jdb.stdin.write("clear\nstop in java.io.File.renameTo\ncont\n")
                jdb.stdin.flush()
                if jo.wait_for(lambda s: "Breakpoint hit" in s, 60) is None:
                    res["error"] = "renameTo breakpoint never hit"
                    return res
        folder = os.path.join(md, os.listdir(md)[0])
        if kill == "KILL":
            res["files_at_kill"] = listing(folder)
            tlc.send_signal(signal.SIGKILL)
        else:
            tlc.send_signal(signal.SIGTERM)  # the JVM handles it once its threads run again
            if jdb:
                jdb.stdin.write("clear\nresume\n")
                jdb.stdin.flush()
        tlc.wait(timeout=60)
        res["rc1"] = tlc.returncode
        res["files_after"] = listing(folder)
        res["has_star_chkpt"] = any(n.endswith(".chkpt") for n in os.listdir(folder))
        res["has_queue_chkpt"] = os.path.exists(os.path.join(folder, "queue.chkpt"))
    finally:
        for p in (jdb, tlc):
            if p and p.poll() is None:
                p.kill()
                p.wait()
    # recover, no further checkpoints, run to the end
    rcmd = [a.java, "-Dtlc2.TLCGlobals.chkpt=0", "-cp", a.jar, "tlc2.TLC", "-deadlock", "-workers", a.workers, "-recover", folder, spec]
    t0 = time.monotonic()
    try:
        r = subprocess.run(rcmd, capture_output=True, text=True, timeout=a.recover_timeout, cwd=workdir)
        text, rc = r.stdout + r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        text, rc = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout"
    with open(os.path.join(workdir, "recover.txt"), "w") as f:
        f.write(text)
    res["recover_rc"] = rc
    res["recover_s"] = round(time.monotonic() - t0, 1)
    m = re.search(r"Recovery completed\. (\d+) states examined\. (\d+) states on queue", text)
    res["recovery"] = m.group(0) if m else None
    m = re.findall(r"([\d,]+) distinct states found", text)
    res["distinct"] = int(m[-1].replace(",", "")) if m else None
    res["expected"] = (a.bound + 1) ** 6
    errs = [ln.strip() for ln in text.splitlines() if re.search(r"Error|Exception|cannot|No such file", ln)]
    res["errors"] = errs[:4]
    res["verdict"] = ("RECOVERED, complete and correct" if rc == 0 and res["distinct"] == res["expected"]
                      else "RECOVERED but WRONG state count" if rc == 0
                      else "NOT RECOVERABLE")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", required=True)
    ap.add_argument("--java", default="java")
    ap.add_argument("--jdb", default="jdb")
    ap.add_argument("--bound", type=int, default=10)
    ap.add_argument("--workers", default="2")
    ap.add_argument("--line-set", choices=list(LINES), required=True)
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--recover-timeout", type=float, default=900)
    a = ap.parse_args()
    a.jar, a.out = os.path.abspath(a.jar), os.path.abspath(a.out)
    os.makedirs(a.out, exist_ok=True)
    for name in a.scenarios.split(","):
        if SCENARIOS[name][1] == "settings_left" and LINES[a.line_set]["settings_left"] is None:
            continue
        wd = os.path.join(a.out, name)
        shutil.rmtree(wd, ignore_errors=True)
        os.makedirs(wd)
        t0 = time.monotonic()
        try:
            res = run(a, name, wd)
        except Exception as e:  # noqa: BLE001
            res = {"scenario": name, "error": f"{type(e).__name__}: {e}"}
        res["total_s"] = round(time.monotonic() - t0, 1)
        print(json.dumps(res), flush=True)
        shutil.rmtree(os.path.join(wd, "md"), ignore_errors=True)


if __name__ == "__main__":
    main()
