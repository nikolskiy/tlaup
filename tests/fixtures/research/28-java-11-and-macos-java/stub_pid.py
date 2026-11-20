"""q28, second run: does a JVM started through the macOS /usr/bin/java stub keep the stub's process id?
Run from the ci folder: python q28/stub_pid.py. Always exits 0."""
import os
import platform
import subprocess
import tempfile
from pathlib import Path

OS = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(platform.system(), platform.system())
SRC = """public class Pid { public static void main(String[] a) throws Exception {
  ProcessHandle h = ProcessHandle.current();
  System.out.println("pid=" + h.pid() + " parent=" + h.parent().map(p -> String.valueOf(p.pid())).orElse("?")
    + " cmd=" + h.info().command().orElse("?"));
  Thread.sleep(3000); } }
"""
stub = "/usr/bin/java"
if OS != "macos" or not os.path.exists(stub):
    print(f"RESULT q28 stub-pid {OS} : skipped (no macOS stub)")
else:
    d = Path(tempfile.mkdtemp())
    (d / "Pid.java").write_text(SRC)
    for label, env_home in (("JAVA_HOME=21", os.environ.get("JAVA21_HOME")), ("JAVA_HOME-unset", None)):
        env = dict(os.environ)
        env.pop("JAVA_HOME", None)
        if env_home:
            env["JAVA_HOME"] = env_home
        try:
            p = subprocess.Popen([stub, str(d / "Pid.java")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            out, _ = p.communicate(timeout=60)
            text = out.decode(errors="replace").strip().replace("\n", " | ")
            same = f"pid={p.pid} " in text + " "
            print(f"RESULT q28 stub-pid-{label} {OS} : popen-pid={p.pid} same-pid={same} rc={p.returncode} | {text}")
        except Exception as e:  # noqa: BLE001
            print(f"RESULT q28 stub-pid-{label} {OS} : error {type(e).__name__}: {e}")
