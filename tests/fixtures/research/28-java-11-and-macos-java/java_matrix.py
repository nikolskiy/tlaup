"""Question 28, parts 1 and 2: both TLC builds on several Javas, and override
classes compiled for a newer Java loaded on an older one.

Run from the `ci` folder:  python q28/java_matrix.py [--work DIR]

Inputs (environment):
  TLA2TOOLS_174, TLA2TOOLS_ROLLING   the two jars (required)
  JAVA11_HOME, JAVA21_HOME, JAVA25_HOME   JDK folders (each optional; the
      `java` on PATH is used as well, labelled by its own version)
Every JDK that has a `javac` compiles the override module with its default
release, and with --release 11 and --release 21 where it can. Every class
set is then loaded by every Java with both jars.

Prints `RESULT q28 <check> <os> : <outcome>` lines and keeps full output under
<work>/out/. Exits 0 whatever the outcome.
"""
import argparse
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

OS = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(platform.system(), platform.system())
EXE = ".exe" if os.name == "nt" else ""
TIMEOUT = 240

SPECS = {
    # name: (tla, cfg)
    "pass": ("""---- MODULE pass ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x' = (x + 1) % 5
TypeOK == x \\in 0..4
====
""", "INIT Init\nNEXT Next\nINVARIANT TypeOK\n"),
    "violation": ("""---- MODULE violation ----
EXTENDS Naturals
VARIABLE x
Init == x = 0
Next == x' = (x + 1) % 5
Small == x < 3
====
""", "INIT Init\nNEXT Next\nINVARIANT Small\n"),
    "liveness_ok": ("""---- MODULE liveness_ok ----
EXTENDS Naturals
VARIABLE x
vars == <<x>>
Init == x = 0
Next == x' = (x + 1) % 5
Spec == Init /\\ [][Next]_vars /\\ WF_vars(Next)
Reach3 == <>(x = 3)
====
""", "SPECIFICATION Spec\nPROPERTY Reach3\n"),
    "liveness_violated": ("""---- MODULE liveness_violated ----
EXTENDS Naturals
VARIABLE x
vars == <<x>>
Init == x = 0
Next == x' = (x + 1) % 5
Spec == Init /\\ [][Next]_vars
Reach3 == <>(x = 3)
====
""", "SPECIFICATION Spec\nPROPERTY Reach3\n"),
}

OVR_SPEC = """---- MODULE spec ----
EXTENDS Naturals, TLC, Ovr
VARIABLE x
Init == x = Add2(1, 2)
Next == x' = x
Inv == PrintT(<<"Inv sees", x, Add2(10, 20)>>)
====
"""
OVR_CFG = "INIT Init\nNEXT Next\nINVARIANT Inv\n"
OVR_MOD = """---- MODULE Ovr ----
EXTENDS Naturals
Add2(a, b) == a + b + 1000
====
"""
OVR_JAVA = """package tlc2.overrides;
import tlc2.value.impl.*;
public class TLCOverrides implements ITLCOverrides {
    @TLAPlusOperator(identifier = "Add2", module = "Ovr", warn = true)
    public static Value Add2(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val); }
    @Override public Class[] get() { return new Class[]{ TLCOverrides.class }; }
}
"""

MIXED_INDEX = """package tlc2.overrides;
public class TLCOverrides implements ITLCOverrides {
    @Override public Class[] get() { return new Class[]{ Newer.class }; }
}
"""
MIXED_LISTED = """package tlc2.overrides;
import tlc2.value.impl.*;
public class Newer {
    @TLAPlusOperator(identifier = "Add2", module = "Ovr", warn = true)
    public static Value Add2(final IntValue a, final IntValue b) { return IntValue.gen(a.val + b.val); }
}
"""


def run(cmd, cwd=None, timeout=TIMEOUT):
    try:
        p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as e:  # run() has killed the child
        return "timeout", (e.stdout or b"").decode("utf-8", "replace")
    except OSError as e:
        return "start-error", str(e)


def java_major(java):
    code, out = run([str(java), "-version"], timeout=30)
    m = re.search(r'version "(\d+)(?:\.(\d+))?', out)
    if not m:
        return None, out.strip().splitlines()[:1]
    major = int(m.group(1))
    if major == 1:
        major = int(m.group(2))
    return major, out.strip().splitlines()[:3]


def find_javas():
    javas = {}  # label -> (java path, javac path or None, version lines)
    homes = [os.environ.get(v) for v in ("JAVA11_HOME", "JAVA21_HOME", "JAVA25_HOME")]
    cands = [Path(h) / "bin" / f"java{EXE}" for h in homes if h]
    on_path = shutil.which("java")
    if on_path:
        cands.append(Path(on_path))
    for j in cands:
        if not j.is_file():
            continue
        major, lines = java_major(j)
        if major is None or f"java{major}" in javas:
            continue
        javac = j.with_name(f"javac{EXE}")
        javas[f"java{major}"] = (j, javac if javac.is_file() else None, lines)
    return dict(sorted(javas.items(), key=lambda kv: int(kv[0][4:])))


def classfile_major(path):
    with open(path, "rb") as f:
        head = f.read(8)
    return struct.unpack(">H", head[6:8])[0]


def key_lines(out):
    keep = []
    for line in out.splitlines():
        if re.match(r"@!@!@STARTMSG (1000|2173|2110|2111|2112|2116|2168|2185|2186|2193|2400|2402|2403|2154|2262):", line) \
                or "UnsupportedClassVersionError" in line or "Inv sees" in line \
                or "has been compiled by a more recent version" in line \
                or line.startswith(("Error:", "Exception", "TLC2 Version")):
            keep.append(line.strip())
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="q28-work")
    a = ap.parse_args()
    work = Path(a.work).resolve()
    out_dir = work / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    jars = {"v1.7.4": os.environ.get("TLA2TOOLS_174"), "rolling": os.environ.get("TLA2TOOLS_ROLLING")}
    jars = {k: Path(v).resolve() for k, v in jars.items() if v and Path(v).is_file()}
    javas = find_javas()
    print(f"q28 os={OS} jars={list(jars)}")
    for label, (j, jc, lines) in javas.items():
        print(f"q28 {label}: javac={'yes' if jc else 'no'} | " + " | ".join(lines))
    if not jars or not javas:
        print(f"RESULT q28 setup {OS} : missing jars or java")
        return

    # Part 1: four specs per jar per Java.
    specs = work / "specs"
    specs.mkdir(exist_ok=True)
    for name, (tla, cfg) in SPECS.items():
        (specs / f"{name}.tla").write_text(tla)
        (specs / f"{name}.cfg").write_text(cfg)
    for jl, jar in jars.items():
        for label, (java, _, _) in javas.items():
            for name in SPECS:
                meta = tempfile.mkdtemp(prefix="md-", dir=work)
                cmd = [str(java), "-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC", "-cp", str(jar),
                       "tlc2.TLC", "-workers", "1", "-metadir", meta, "-config", f"{name}.cfg", "-tool", f"{name}.tla"]
                code, out = run(cmd, cwd=specs)
                shutil.rmtree(meta, ignore_errors=True)
                (out_dir / f"{jl}-{label}-{name}.txt").write_text(out)
                (out_dir / f"{jl}-{label}-{name}.exit").write_text(f"{code}\n")
                codes = sorted(set(re.findall(r"@!@!@STARTMSG (\d+):", out)), key=int)
                print(f"RESULT q28 run-{jl}-{label}-{name} {OS} : exit={code}")
                print(f"  message codes: {' '.join(codes)}")

    # Part 2: compile the override with each javac and release, load on each Java.
    builds = {}  # build label -> classes dir
    for label, (java, javac, _) in javas.items():
        if not javac:
            continue
        major = int(label[4:])
        for rel in [None, 11, 21]:
            if rel is not None and (rel > major or rel == major):
                continue
            bl = f"javac{major}-" + ("default" if rel is None else f"release{rel}")
            src = work / "ovr-src" / "tlc2" / "overrides"
            src.mkdir(parents=True, exist_ok=True)
            (src / "TLCOverrides.java").write_text(OVR_JAVA)
            classes = work / "builds" / bl
            shutil.rmtree(classes, ignore_errors=True)
            classes.mkdir(parents=True)
            jar = jars.get("rolling") or next(iter(jars.values()))
            cmd = [str(javac), "-encoding", "UTF-8"] + (["--release", str(rel)] if rel else []) + \
                  ["-cp", str(jar), "-d", str(classes), str(src / "TLCOverrides.java")]
            code, out = run(cmd)
            cls = classes / "tlc2" / "overrides" / "TLCOverrides.class"
            if code != 0 or not cls.is_file():
                print(f"RESULT q28 compile-{bl} {OS} : failed exit={code}")
                print("  " + out.strip().replace("\n", "\n  "))
                continue
            print(f"RESULT q28 compile-{bl} {OS} : ok classfile major={classfile_major(cls)}"
                  + (f" warnings: {out.strip()}" if out.strip() else ""))
            builds[bl] = classes
    # Mixed: index class built for 11, the class it lists built by the newest javac's default.
    newest = [(int(l[4:]), jc) for l, (_, jc, _) in javas.items() if jc]
    if newest and max(newest)[0] > 11:
        major, javac = max(newest)
        jar = jars.get("rolling") or next(iter(jars.values()))
        src = work / "mixed-src" / "tlc2" / "overrides"
        src.mkdir(parents=True, exist_ok=True)
        (src / "TLCOverrides.java").write_text(MIXED_INDEX)
        (src / "Newer.java").write_text(MIXED_LISTED)
        bl = f"mixed-index-release11-listed-javac{major}-default"
        classes = work / "builds" / bl
        shutil.rmtree(classes, ignore_errors=True)
        classes.mkdir(parents=True)
        c1, o1 = run([str(javac), "-encoding", "UTF-8", "--release", "11", "-cp", str(jar), "-d", str(classes),
                      str(src / "TLCOverrides.java"), str(src / "Newer.java")])
        c2, o2 = run([str(javac), "-encoding", "UTF-8", "-cp", os.pathsep.join([str(classes), str(jar)]),
                      "-d", str(classes), str(src / "Newer.java")])
        idx = classes / "tlc2" / "overrides" / "TLCOverrides.class"
        lst = classes / "tlc2" / "overrides" / "Newer.class"
        if c1 == 0 and c2 == 0:
            print(f"RESULT q28 compile-{bl} {OS} : ok index major={classfile_major(idx)} listed major={classfile_major(lst)}")
            builds[bl] = classes
        else:
            print(f"RESULT q28 compile-{bl} {OS} : failed {c1} {c2} {o1} {o2}")
    case = work / "ovr-case"
    (case / "modules").mkdir(parents=True, exist_ok=True)
    (case / "spec.tla").write_text(OVR_SPEC)
    (case / "spec.cfg").write_text(OVR_CFG)
    (case / "modules" / "Ovr.tla").write_text(OVR_MOD)
    for bl, classes in builds.items():
        for jl, jar in jars.items():
            for label, (java, _, _) in javas.items():
                meta = tempfile.mkdtemp(prefix="md-", dir=work)
                for tool in (True, False):
                    cmd = [str(java), "-XX:+IgnoreUnrecognizedVMOptions", "-XX:+UseParallelGC",
                           f"-DTLA-Library={case / 'modules'}",
                           "-Dtlc2.overrides.TLCOverrides=tlc2.overrides.TLCOverrides",
                           "-cp", os.pathsep.join([str(classes), str(case / "modules"), str(jar)]),
                           "tlc2.TLC", "-workers", "1", "-metadir", meta, "-config", "spec.cfg"] + \
                          (["-tool"] if tool else []) + ["spec.tla"]
                    code, out = run(cmd, cwd=case)
                    mode = "tool" if tool else "plain"
                    stem = f"ovr-{bl}-{jl}-{label}-{mode}"
                    (out_dir / f"{stem}.txt").write_text(out)
                    (out_dir / f"{stem}.exit").write_text(f"{code}\n")
                    if "<<\"Inv sees\", 3, 30>>" in out:
                        what = "override used"
                    elif "has been compiled by a more recent version" in out:
                        what = "class version refused (UnsupportedClassVersionError text)"
                    elif "<<\"Inv sees\", 1003, 1030>>" in out:
                        what = "override NOT used (TLA+ body ran)"
                    else:
                        what = "other"
                    print(f"RESULT q28 override-{bl}-{jl}-{label}-{mode} {OS} : exit={code} {what}")
                    if what != "override used":
                        for k in key_lines(out)[:12]:
                            print("  " + k[:400])
                shutil.rmtree(meta, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # the result is the output, never the exit code
        print(f"RESULT q28 java_matrix {OS} : script error {type(e).__name__}: {e}")
    sys.exit(0)
