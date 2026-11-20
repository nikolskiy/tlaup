"""Question 20: does TLC create a missing -metadir folder and its parents?
Run from the ci folder: python q20/metadir_creation.py
Needs java on PATH and TLA2TOOLS_174 / TLA2TOOLS_ROLLING. Always exits 0; the result is the output."""
import os, platform, shutil, subprocess, sys, tempfile
from pathlib import Path

OS = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(platform.system(), platform.system())
JARS = {"v1.7.4": os.environ.get("TLA2TOOLS_174"), "rolling": os.environ.get("TLA2TOOLS_ROLLING")}
SPEC = "---- MODULE Small ----\nEXTENDS Naturals\nVARIABLE x\nInit == x = 0\nNext == x < 5 /\\ x' = x + 1\nSpec == Init /\\ [][Next]_x\n====\n"
CFG = "SPECIFICATION Spec\nCHECK_DEADLOCK FALSE\n"


def tlc(jar, cwd, metadir, spec):
    try:
        p = subprocess.run(["java", "-cp", jar, "tlc2.TLC", "-workers", "1", "-metadir", metadir, str(spec)],
                           cwd=cwd, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return -1, "timeout"


def tree(root):
    root = Path(root)
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*")) if root.exists() else []


def main():
    base = Path(tempfile.mkdtemp(prefix="q20-"))
    spec = base / "Small.tla"
    spec.write_text(SPEC)
    (base / "Small.cfg").write_text(CFG)
    for ver, jar in JARS.items():
        if not jar or not Path(jar).exists():
            print(f"RESULT q20 setup {OS} : jar for {ver} missing")
            continue
        w = base / ver
        cwd = w / "cwd"
        cwd.mkdir(parents=True)
        (w / "afile").write_text("x")
        cases = [
            ("existing", str(w / "exist"), True),
            ("one-missing", str(w / "b1"), False),
            ("three-missing", str(w / "c1" / "c2" / "c3"), False),
            ("relative-missing", "rel1/rel2", False),
            ("parent-is-file", str(w / "afile" / "md"), False),
        ]
        (w / "exist").mkdir()
        if OS != "windows":
            (w / "ro").mkdir()
            os.chmod(w / "ro", 0o555)
            cases.append(("parent-not-writable", str(w / "ro" / "md"), False))
        for name, md, _ in cases:
            rc, out = tlc(jar, cwd, md, spec)
            created = "-"
            tgt = (cwd / md) if not os.path.isabs(md) else Path(md)
            created = "dir-exists" if tgt.is_dir() else "no-dir"
            reason = ""
            if rc != 0:
                reason = " | " + " ".join(l.strip() for l in out.splitlines() if "could not make" in l or "xception" in l)[:160].replace(str(base), "<ws>")
            print(f"RESULT q20 {ver}/{name} {OS} : exit={rc} metadir={created}{reason}")
        if OS != "windows":
            os.chmod(w / "ro", 0o755)
    shutil.rmtree(base, ignore_errors=True)


try:
    main()
except Exception as e:  # never fail the job
    print(f"RESULT q20 script-error {OS} : {type(e).__name__}")
