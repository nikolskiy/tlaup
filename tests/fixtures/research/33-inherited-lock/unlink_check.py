"""q33: the R6 rule "remove the lock file while holding it" with a child that holds the inherited lock.
Holder takes FileLock (on_acquired hook), starts a sleeping child with the descriptor, removes the lock file
(still holding), and is killed with SIGKILL. A third process then tries FileLock on the same path."""
import os, signal, subprocess, sys, time
import filelock
path = sys.argv[1]
if len(sys.argv) > 2 and sys.argv[2] == "holder":
    got = {}
    lk = filelock.FileLock(path, on_acquired=lambda d: got.__setitem__("fd", d)); lk.acquire()
    c = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(8)"], pass_fds=(got["fd"],))
    if sys.argv[3] == "unlink":
        os.unlink(path)
    print(c.pid, flush=True); time.sleep(600)
def attempt():
    lk = filelock.FileLock(path, timeout=0)
    try:
        lk.acquire()
    except filelock.Timeout:
        return "refused"
    st = os.fstat(lk._context.lock_file_fd); lk.release(); return f"granted (new inode {st.st_ino}, nlink {st.st_nlink})"
for mode in ("keep", "unlink"):
    if os.path.exists(path): os.unlink(path)
    h = subprocess.Popen([sys.executable, __file__, path, "holder", mode], stdout=subprocess.PIPE, text=True)
    cpid = int(h.stdout.readline()); time.sleep(0.3)
    ino = os.stat(f"/proc/{cpid}/fd/{[n for n in os.listdir(f'/proc/{cpid}/fd') if 'run.lock' in os.readlink(f'/proc/{cpid}/fd/{n}')][0]}").st_ino
    h.send_signal(signal.SIGKILL); h.wait(); time.sleep(0.3)
    print(f"{mode}: child {cpid} holds inode {ino}; path exists={os.path.exists(path)}; third FileLock: {attempt()}")
    while os.path.exists(f"/proc/{cpid}") and open(f"/proc/{cpid}/stat").read().split(")")[1].split()[0] != "Z":
        time.sleep(0.2)
