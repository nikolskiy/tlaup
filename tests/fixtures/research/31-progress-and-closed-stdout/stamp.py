#!/usr/bin/env python3
"""Run a command, write each stdout/stderr line with seconds since start; stop after LIMIT seconds by pid.
usage: stamp.py OUT LIMIT cmd..."""
import subprocess, sys, time, threading, signal
out, limit, cmd = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
t0 = time.monotonic()
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
f = open(out, "w")
f.write(f"# cmd: {' '.join(cmd)}\n# pid {p.pid}\n"); f.flush()
def stop():
    time.sleep(limit)
    if p.poll() is None:
        f.write(f"# t={time.monotonic()-t0:.3f} sending SIGTERM to {p.pid} (time limit)\n"); f.flush()
        p.terminate()
threading.Thread(target=stop, daemon=True).start()
for line in p.stdout:
    f.write(f"{time.monotonic()-t0:9.3f} {line.decode(errors='replace').rstrip()}\n"); f.flush()
rc = p.wait()
f.write(f"# t={time.monotonic()-t0:.3f} exit {rc}\n"); f.close()
