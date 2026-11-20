import os, sys, tempfile, time, threading
import filelock
d = tempfile.mkdtemp(dir=os.environ["Q30_TMP"])
p = os.path.join(d, "x.lock")
a = filelock.FileLock(p); a.acquire()
out = []
for t in (0, 0.5, 2):
    b = filelock.FileLock(p)
    t0 = time.monotonic()
    try:
        b.acquire(timeout=t); out.append(f"t={t}:GOT"); b.release()
    except filelock.Timeout:
        out.append(f"t={t}:Timeout@{time.monotonic()-t0:.2f}s")
    except Exception as e:
        out.append(f"t={t}:{type(e).__name__}@{time.monotonic()-t0:.2f}s:{str(e)[:70]}")
# blocking=-1 in another call with a watchdog thread releasing a after 1s
def rel():
    time.sleep(1); 
b = filelock.FileLock(p)
t0 = time.monotonic()
try:
    b.acquire(timeout=-1, blocking=False); out.append("nonblocking:GOT")
except filelock.Timeout:
    out.append("nonblocking:Timeout")
except Exception as e:
    out.append(f"nonblocking:{type(e).__name__}")
print(filelock.__version__, "; ".join(out))
