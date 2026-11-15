"""Send a signal directly to a TLC JVM and record how it exits.
usage: signal_jvm.py JAR SIGNAL(INT|TERM|HUP|KILL) OUTFILE
Popen returncode: N>0 = JVM called exit(N); -N = killed by signal N."""
import os, signal, subprocess, sys, tempfile, time
jar, sig, out = sys.argv[1:4]
here = os.path.dirname(os.path.abspath(__file__))
md = tempfile.mkdtemp()
with open(out, "w") as f:
    p = subprocess.Popen(["java", "-cp", jar, "tlc2.TLC", "-metadir", md, "-config", "Long.cfg", "Long.tla"],
                         cwd=os.path.join(here, "specs"), stdout=f, stderr=subprocess.STDOUT)
    print("java pid", p.pid, flush=True)
    time.sleep(8)
    t0 = time.time()
    p.send_signal(getattr(signal, "SIG" + sig))
    try:
        rc = p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        rc = "TIMEOUT"; p.kill(); p.wait()
print(f"{sig}: returncode={rc} after {time.time()-t0:.1f}s")
