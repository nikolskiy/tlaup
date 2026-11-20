"""run_dfl.py NAME JARDIR [TLC args...]: start TLC (-workers 1, -metadir <tmp>/q25/meta/NAME) with SIGINT and SIGHUP
reset to their defaults in the child, so the JVM sees a SIGINT even when this script was started in the background
(a background job of a non-interactive shell inherits SIGINT as ignored, and the JVM then never sees it)."""
import os, signal, subprocess, sys, time
S = os.path.dirname(os.path.abspath(__file__))
name, jar, *args = sys.argv[1:]
jars = os.path.join(os.path.dirname(S), "jars")
os.makedirs(f"{S}/meta/{name}", exist_ok=True); os.makedirs(f"{S}/run/{name}", exist_ok=True)
def dfl():
    signal.signal(signal.SIGINT, signal.SIG_DFL); signal.signal(signal.SIGHUP, signal.SIG_DFL)
with open(f"{S}/logs/{name}.out", "wb") as out:
    p = subprocess.Popen(["java", "-cp", f"{jars}/{jar}/tla2tools.jar", "tlc2.TLC", "-workers", "1",
                          "-metadir", f"{S}/meta/{name}", *args, f"{S}/specs/Long.tla"],
                         cwd=f"{S}/run/{name}", stdout=out, stderr=subprocess.STDOUT, preexec_fn=dfl)
    open(f"{S}/logs/{name}.pid", "w").write(str(p.pid))
    open(f"{S}/logs/{name}.start", "w").write(time.strftime("%H:%M:%S"))
    rc = p.wait()
open(f"{S}/logs/{name}.exit", "w").write(f"{rc}\n")
