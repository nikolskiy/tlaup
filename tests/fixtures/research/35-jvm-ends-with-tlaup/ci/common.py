"""Shared helpers for the question 35 checks (standard library only)."""

from __future__ import annotations

import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"
OS = "linux" if IS_LINUX else "windows" if IS_WIN else "macos" if IS_MAC else sys.platform
WORK = os.environ.get("Q35_WORK") or os.path.join(HERE, "_work")
JAVA = os.environ.get("Q35_JAVA") or shutil.which("java") or "java"


def result(check: str, outcome: str) -> None:
    print(f"RESULT q35 {check} {OS} : {outcome}", flush=True)


def java_version(java: str = JAVA) -> str:
    try:
        out = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=30).stderr
        return out.strip().splitlines()[0] if out.strip() else "?"
    except Exception as e:  # noqa: BLE001
        return f"? ({e})"


def javac() -> str:
    j = os.path.join(os.path.dirname(os.path.realpath(JAVA)), "javac" + (".exe" if IS_WIN else ""))
    return j if os.path.exists(j) else (shutil.which("javac") or "javac")


def build() -> tuple[str, str]:
    """Compile the agent and the sleeper; return (agent jar, classes folder)."""
    classes = os.path.join(WORK, "classes")
    jar = os.path.join(WORK, "lifeline.jar")
    os.makedirs(classes, exist_ok=True)
    srcs = [os.path.join(HERE, "java", n) for n in ("Lifeline.java", "Sleeper.java")]
    subprocess.run([javac(), "--release", "11", "-d", classes, *srcs], check=True, timeout=120)
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("META-INF/MANIFEST.MF",
                   "Manifest-Version: 1.0\r\nPremain-Class: q35.Lifeline\r\nAgent-Class: q35.Lifeline\r\n\r\n")
        z.write(os.path.join(classes, "q35", "Lifeline.class"), "q35/Lifeline.class")
    return jar, classes


def alive(pid: int) -> bool:
    if IS_WIN:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = wintypes.DWORD()
        k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # a zombie counts as gone
    if IS_LINUX:
        try:
            with open(f"/proc/{pid}/stat") as f:
                return f.read().rsplit(")", 1)[1].split()[0] != "Z"
        except OSError:
            return False
    try:
        st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=10).stdout
        return bool(st.strip()) and not st.strip().startswith("Z")
    except Exception:  # noqa: BLE001
        return True


def parent_of(pid: int) -> str:
    if IS_WIN:
        return "?"
    try:
        return subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True,
                              timeout=10).stdout.strip() or "?"
    except Exception:  # noqa: BLE001
        return "?"


def hard_kill(pid: int) -> None:
    """SIGKILL on POSIX, TerminateProcess on Windows."""
    try:
        os.kill(pid, signal.SIGTERM if IS_WIN else signal.SIGKILL)
    except OSError:
        pass


def wait_gone(pid: int, timeout: float) -> float | None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if not alive(pid):
            return time.monotonic() - t0
        time.sleep(0.05)
    return None


def popen_parent(args: list[str], env: dict | None = None, **kw) -> subprocess.Popen:
    """Start parent.py so that killing it reaches it alone (own session / process group)."""
    extra: dict = {}
    if IS_WIN:
        extra["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        extra["start_new_session"] = True
    extra.update(kw)
    return subprocess.Popen([sys.executable, os.path.join(HERE, "parent.py"), *args], env=env,
                            stdout=subprocess.PIPE, text=True, **extra)


def read_until_ready(p: subprocess.Popen, timeout: float = 60.0) -> dict:
    """Read parent.py's lines up to READY (a reader thread, so a dead parent cannot hang us)."""
    import queue
    import threading

    q: queue.Queue = queue.Queue()

    def rd() -> None:
        for line in p.stdout:
            q.put(line)
        q.put(None)

    threading.Thread(target=rd, daemon=True).start()
    info: dict = {}
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            line = q.get(timeout=0.5)
        except Exception:  # noqa: BLE001
            continue
        if line is None:
            break
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "READY":
            info["ready"] = True
            break
        info[parts[0]] = parts[1] if len(parts) > 1 else ""
    info["_q"] = q
    return info


def host() -> str:
    return f"{platform.system()} {platform.machine()}, Python {platform.python_version()}"
