"""q31: does TLC (JVM) keep running when its stdout reader has gone? Run from the ci folder."""
import os, subprocess, sys, tempfile, time, pathlib, platform

SPEC = """---- MODULE Mid ----
EXTENDS Naturals
VARIABLES a, b, c
Init == a = 0 /\\ b = 0 /\\ c = 0
Next == \\/ a < 120 /\\ a' = a + 1 /\\ UNCHANGED <<b, c>>
        \\/ b < 120 /\\ b' = b + 1 /\\ UNCHANGED <<a, c>>
        \\/ c < 120 /\\ c' = c + 1 /\\ UNCHANGED <<a, b>>
Spec == Init /\\ [][Next]_<<a, b, c>>
Inv == a + b + c < 360
====
"""
OS = platform.system().lower()

def one(label, jar):
    d = pathlib.Path(tempfile.mkdtemp(prefix="q31-"))
    (d / "Mid.tla").write_text(SPEC); (d / "Mid.cfg").write_text("SPECIFICATION Spec\nINVARIANT Inv\n")
    cmd = ["java", "-Xmx256m", "-jar", jar, "-workers", "1", "-metadir", str(d / "st"), "-nowarning", "Mid"]
    p = subprocess.Popen(cmd, cwd=d, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p.stdout.readline()          # one line, like head -1
    p.stdout.close()             # the reader exits
    t0 = time.time(); alive_after_2s = False
    time.sleep(2)
    alive_after_2s = p.poll() is None
    try:
        rc = p.wait(timeout=240)
        outcome = f"alive-2s-after-close={alive_after_2s} exit={rc} total={time.time()-t0:.0f}s"
    except subprocess.TimeoutExpired:
        p.kill(); p.wait()
        outcome = f"alive-2s-after-close={alive_after_2s} still-running-after-240s (killed)"
    print(f"RESULT q31 closed-stdout-{label} {OS} : {outcome}", flush=True)

for label, var in (("v174", "TLA2TOOLS_174"), ("rolling", "TLA2TOOLS_ROLLING")):
    try:
        one(label, os.environ[var])
    except Exception as e:
        print(f"RESULT q31 closed-stdout-{label} {OS} : error {e!r}", flush=True)
